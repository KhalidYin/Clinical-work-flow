"""Download and validate the single official ICH E9 POC source asset."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import fitz


ICH_E9_URL = "https://database.ich.org/sites/default/files/E9_Guideline.pdf"
ICH_E9_MEDIA_TYPE = "application/pdf"
ICH_E9_DOCUMENT_ID = "ICH-E9-1998"
ICH_E9_SHA256 = "0c0ddc93cb427a70265dbcb0e7c25bfc9a3f7b52e178212b3630ea2408ad9c7e"
DEFAULT_DESTINATION = Path(".poc-assets/ich-e9/E9_Guideline.pdf")
DEFAULT_RECEIPT = Path(".poc-assets/ich-e9/E9_Guideline.asset.json")


class E9AssetValidationError(RuntimeError):
    """The downloaded bytes do not match the approved E9 identity."""


@dataclass(frozen=True, slots=True)
class E9AssetReceipt:
    document_id: str
    source_url: str
    resolved_url: str
    media_type: str
    sha256: str
    size_bytes: int
    page_count: int
    text_extractable: bool
    downloaded_at: str
    redistribution: str
    destination: str
    created: bool

    def to_json_dict(self) -> dict[str, Any]:
        facts = asdict(self)
        return {
            "documentId": facts["document_id"],
            "sourceUrl": facts["source_url"],
            "resolvedUrl": facts["resolved_url"],
            "mediaType": facts["media_type"],
            "sha256": facts["sha256"],
            "sizeBytes": facts["size_bytes"],
            "pageCount": facts["page_count"],
            "textExtractable": facts["text_extractable"],
            "downloadedAt": facts["downloaded_at"],
            "redistribution": facts["redistribution"],
            "destination": facts["destination"],
        }


AssetFetcher = Callable[[str], tuple[bytes, str, str]]


def download_ich_e9(
    *,
    destination: Path = DEFAULT_DESTINATION,
    receipt_path: Path = DEFAULT_RECEIPT,
    expected_sha256: str = ICH_E9_SHA256,
    fetcher: AssetFetcher | None = None,
) -> E9AssetReceipt:
    """Download E9 once, validate its pinned identity, and write a local receipt."""

    if len(expected_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in expected_sha256
    ):
        raise ValueError("expected_sha256 must be lowercase SHA-256")
    destination = destination.resolve()
    receipt_path = receipt_path.resolve()
    if destination.exists():
        content = destination.read_bytes()
        page_count, text_extractable = _validate_pdf(content, expected_sha256)
        existing = _read_receipt(receipt_path)
        downloaded_at = existing.get("downloadedAt") if existing else None
        receipt = E9AssetReceipt(
            document_id=ICH_E9_DOCUMENT_ID,
            source_url=ICH_E9_URL,
            resolved_url=(existing.get("resolvedUrl", ICH_E9_URL) if existing else ICH_E9_URL),
            media_type=ICH_E9_MEDIA_TYPE,
            sha256=expected_sha256,
            size_bytes=len(content),
            page_count=page_count,
            text_extractable=text_extractable,
            downloaded_at=downloaded_at or _now(),
            redistribution="not_committed_to_git",
            destination=str(destination),
            created=False,
        )
        if not existing:
            _write_receipt(receipt_path, receipt)
        return receipt

    fetch = fetcher or _fetch
    content, resolved_url, media_type = fetch(ICH_E9_URL)
    if media_type.split(";", maxsplit=1)[0].strip().lower() != ICH_E9_MEDIA_TYPE:
        raise E9AssetValidationError("ICH E9 response media type is not application/pdf")
    page_count, text_extractable = _validate_pdf(content, expected_sha256)
    receipt = E9AssetReceipt(
        document_id=ICH_E9_DOCUMENT_ID,
        source_url=ICH_E9_URL,
        resolved_url=resolved_url,
        media_type=ICH_E9_MEDIA_TYPE,
        sha256=expected_sha256,
        size_bytes=len(content),
        page_count=page_count,
        text_extractable=text_extractable,
        downloaded_at=_now(),
        redistribution="not_committed_to_git",
        destination=str(destination),
        created=True,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_asset = destination.with_suffix(destination.suffix + ".tmp")
    try:
        temporary_asset.write_bytes(content)
        os.replace(temporary_asset, destination)
        _write_receipt(receipt_path, receipt)
    except Exception:
        temporary_asset.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        receipt_path.unlink(missing_ok=True)
        raise
    return receipt


def _fetch(url: str) -> tuple[bytes, str, str]:
    request = Request(url, headers={"User-Agent": "clinical-knowledge-poc/1.0"})
    with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed HTTPS URL
        return (
            response.read(),
            response.geturl(),
            response.headers.get_content_type(),
        )


def _validate_pdf(content: bytes, expected_sha256: str) -> tuple[int, bool]:
    actual_sha256 = sha256(content).hexdigest()
    if actual_sha256 != expected_sha256:
        raise E9AssetValidationError(
            f"ICH E9 SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    if not content.startswith(b"%PDF"):
        raise E9AssetValidationError("ICH E9 asset is not a PDF")
    display_errors = bool(fitz.TOOLS.mupdf_display_errors())
    try:
        fitz.TOOLS.mupdf_display_errors(False)
        document = fitz.open(stream=content, filetype="pdf")
        text = "".join(page.get_text() for page in document)
        page_count = document.page_count
        document.close()
    except Exception as exc:
        raise E9AssetValidationError("ICH E9 PDF cannot be parsed") from exc
    finally:
        fitz.TOOLS.mupdf_display_errors(display_errors)
    normalized = " ".join(text.upper().split())
    if "STATISTICAL PRINCIPLES FOR CLINICAL TRIALS" not in normalized:
        raise E9AssetValidationError("ICH E9 title was not found in extracted text")
    if "ADDENDUM ON ESTIMANDS AND SENSITIVITY ANALYSIS" in normalized:
        raise E9AssetValidationError("E9(R1) addendum is outside the approved POC scope")
    if page_count < 1 or not normalized:
        raise E9AssetValidationError("ICH E9 PDF has no extractable pages")
    return page_count, True


def _write_receipt(path: Path, receipt: E9AssetReceipt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(receipt.to_json_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _read_receipt(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the pinned official ICH E9 PDF")
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    receipt = download_ich_e9(destination=args.destination, receipt_path=args.receipt)
    print(json.dumps({**receipt.to_json_dict(), "created": receipt.created}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
