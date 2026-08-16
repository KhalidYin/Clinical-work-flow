from __future__ import annotations

from hashlib import sha256
from importlib import import_module
import json
from pathlib import Path
import subprocess
import sys

import fitz
import pytest


ROOT = Path(__file__).resolve().parents[1]


def _module():
    try:
        return import_module("scripts.ich_e9_asset")
    except ModuleNotFoundError as exc:
        pytest.fail(f"P17 P2 ICH E9 asset helper is missing: {exc}")


def _e9_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        "ICH E9\nSTATISTICAL PRINCIPLES FOR CLINICAL TRIALS\nStep 4, 5 February 1998",
    )
    content = document.tobytes()
    document.close()
    return content


def test_e9_asset_contract_uses_only_the_official_non_r1_document() -> None:
    module = _module()

    assert module.ICH_E9_URL == (
        "https://database.ich.org/sites/default/files/E9_Guideline.pdf"
    )
    assert "R1" not in module.ICH_E9_URL.upper()
    assert module.ICH_E9_MEDIA_TYPE == "application/pdf"
    assert module.ICH_E9_DOCUMENT_ID == "ICH-E9-1998"
    assert len(module.ICH_E9_SHA256) == 64


def test_download_is_hash_checked_atomic_and_idempotent(tmp_path: Path) -> None:
    module = _module()
    content = _e9_pdf()
    expected_sha256 = sha256(content).hexdigest()
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        return content, url, "application/pdf"

    first = module.download_ich_e9(
        destination=tmp_path / "E9_Guideline.pdf",
        receipt_path=tmp_path / "E9_Guideline.asset.json",
        expected_sha256=expected_sha256,
        fetcher=fetcher,
    )
    repeated = module.download_ich_e9(
        destination=tmp_path / "E9_Guideline.pdf",
        receipt_path=tmp_path / "E9_Guideline.asset.json",
        expected_sha256=expected_sha256,
        fetcher=fetcher,
    )

    assert first.created is True
    assert repeated.created is False
    assert calls == [module.ICH_E9_URL]
    assert first.sha256 == expected_sha256
    assert first.page_count == 1
    assert first.text_extractable is True
    assert first.document_id == "ICH-E9-1998"
    receipt = json.loads((tmp_path / "E9_Guideline.asset.json").read_text("utf-8"))
    assert receipt["sourceUrl"] == module.ICH_E9_URL
    assert receipt["resolvedUrl"] == module.ICH_E9_URL
    assert receipt["sha256"] == expected_sha256
    assert receipt["redistribution"] == "not_committed_to_git"


def test_hash_or_document_identity_failure_leaves_no_asset(tmp_path: Path) -> None:
    module = _module()
    content = _e9_pdf()
    destination = tmp_path / "E9_Guideline.pdf"

    with pytest.raises(module.E9AssetValidationError, match="SHA-256"):
        module.download_ich_e9(
            destination=destination,
            receipt_path=tmp_path / "receipt.json",
            expected_sha256="0" * 64,
            fetcher=lambda url: (content, url, "application/pdf"),
        )

    assert not destination.exists()
    assert not (tmp_path / "receipt.json").exists()


def test_e9_pdf_and_generated_receipt_are_ignored_by_git() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert ".poc-assets/" in ignore


def test_downloaded_official_e9_validation_keeps_json_channel_clean() -> None:
    module = _module()
    destination = (ROOT / module.DEFAULT_DESTINATION).resolve()
    if not destination.exists():
        pytest.skip("official E9 local asset is not downloaded")

    result = subprocess.run(
        [sys.executable, "-m", "scripts.ich_e9_asset"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout)["documentId"] == "ICH-E9-1998"
