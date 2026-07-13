"""Create deterministic, non-clinical PDF fixtures used by source-pipeline tests."""

from __future__ import annotations

from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont


def create_fixtures(directory: str | Path) -> tuple[Path, Path]:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    digital = target / "synthetic-digital.pdf"
    scanned = target / "synthetic-scanned.pdf"

    if not digital.exists():
        document = fitz.open()
        page = document.new_page(width=612, height=792)
        page.insert_text((72, 80), "Synthetic Digital Clinical Source", fontsize=18)
        page.insert_text((72, 120), "TEAE definition: events after first dose are treatment-emergent.", fontsize=11)
        page.draw_rect(fitz.Rect(72, 160, 280, 250), color=(0.0, 0.25, 0.5), fill=(0.85, 0.93, 1.0))
        page.insert_text((85, 205), "Synthetic figure evidence", fontsize=12)
        document.save(digital)
        document.close()

    if not scanned.exists():
        image = Image.new("RGB", (1200, 1600), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        draw.rectangle((80, 80, 1120, 1520), outline="black", width=4)
        draw.text((140, 190), "SYNTHETIC SCANNED SOURCE", fill="black", font=font)
        draw.text((140, 270), "No embedded PDF text layer.", fill="black", font=font)
        image_path = target / "synthetic-scanned-source.png"
        image.save(image_path)
        document = fitz.open()
        page = document.new_page(width=612, height=792)
        page.insert_image(page.rect, filename=image_path)
        document.save(scanned)
        document.close()
        image_path.unlink()
    return digital, scanned


if __name__ == "__main__":
    create_fixtures(Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "pdf")
