"""Machine visual QA for PDF-derived renders and figure-coordinate evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from scripts.pdf.source_pipeline import sha256_file


class VisualQaError(RuntimeError):
    """Raised when a derived render or provenance locator is not trustworthy."""


def render_pdf_pages(pdf_path: str | Path, output_dir: str | Path, *, dpi: int = 144) -> list[Path]:
    """Render every physical PDF page to a lossless PNG for human inspection."""

    import fitz

    pdf = Path(pdf_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    document = fitz.open(pdf)
    rendered: list[Path] = []
    try:
        for number, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
            target = output / f"page-{number:03d}.png"
            pixmap.save(str(target))
            rendered.append(target)
    finally:
        document.close()
    return rendered


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_pdf_visual_evidence(package_dir: str | Path) -> dict[str, Any]:
    """Validate page renders, hashes, image decodability and page-coordinate bounds."""

    package = Path(package_dir)
    source = _load_json(package / "source-manifest.json")
    derived = package / "derived"
    extraction = _load_json(derived / "extraction.json")
    figures = _load_json(derived / "figures.json")
    manifest = _load_json(derived / "manifest.json")
    pages = extraction["pages"]
    if len(pages) != source["page_count"]:
        raise VisualQaError("Rendered page count does not match the quarantined source")
    if len(figures["figures"]) < len(pages):
        raise VisualQaError("Every page must retain at least one visual-evidence crop")

    checked: list[str] = []
    for page in pages:
        path = package / page["render_relative_path"]
        if not path.is_file():
            raise VisualQaError(f"Missing rendered page: {path}")
        with Image.open(path) as image:
            image.verify()
        if sha256_file(path) != page["render_sha256"]:
            raise VisualQaError(f"Rendered page hash mismatch: {path}")
        if page["render_relative_path"] not in manifest["outputs"]:
            raise VisualQaError(f"Rendered page absent from derivation manifest: {path}")
        width, height = page["width_points"], page["height_points"]
        for word in page["words"]:
            x0, y0, x1, y1 = word["bbox"]
            if not (0 <= x0 <= x1 <= width and 0 <= y0 <= y1 <= height):
                raise VisualQaError(f"Word bbox is outside physical page {page['physical_page']}")
        checked.append(page["render_relative_path"])
    for figure in figures["figures"]:
        page = pages[figure["physical_page"] - 1]
        x0, y0, x1, y1 = figure["bbox"]
        if not (0 <= x0 < x1 <= page["width_points"] and 0 <= y0 < y1 <= page["height_points"]):
            raise VisualQaError(f"Figure bbox is outside physical page {figure['physical_page']}")
        path = package / figure["relative_path"]
        with Image.open(path) as image:
            image.verify()
        if sha256_file(path) != figure["sha256"]:
            raise VisualQaError(f"Figure crop hash mismatch: {path}")
    return {
        "status": "passed",
        "source_id": source["source_id"],
        "checked_renders": checked,
        "checked_figures": len(figures["figures"]),
    }
