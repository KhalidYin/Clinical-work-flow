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


def create_structure_fixtures(directory: str | Path) -> tuple[Path, Path]:
    """Create a multi-page PDF + workbook pair for structure-map tests."""

    from openpyxl import Workbook

    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    pdf_path = target / "synthetic-structure.pdf"
    xlsx_path = target / "synthetic-structure.xlsx"

    if not pdf_path.exists():
        document = fitz.open()
        for _ in range(4):
            document.new_page(width=612, height=792)
        pages = [document.load_page(index) for index in range(4)]
        pages[0].insert_text((72, 90), "Synthetic Structure Source", fontsize=20)
        pages[1].insert_text((72, 72), "1 Synthetic Fundamentals", fontsize=18)
        pages[1].insert_text(
            (72, 112),
            "This page provides non-clinical navigation text for testing.",
            fontsize=11,
        )
        pages[1].insert_text((520, 760), "1", fontsize=9)

        pages[2].insert_text((72, 72), "1.1 Synthetic Adverse Events", fontsize=16)
        pages[2].insert_text((72, 112), "AE Specification - Segment 1", fontsize=13)
        pages[2].draw_rect(fitz.Rect(72, 135, 540, 700), color=(0, 0, 0))
        pages[2].insert_text((84, 165), "Variable | Label | Core", fontsize=10)
        pages[2].insert_text((84, 195), "AETERM | Synthetic reported term | Req", fontsize=10)
        pages[2].insert_text((520, 760), "2", fontsize=9)

        pages[3].insert_text((72, 72), "AE Specification - Segment 2", fontsize=13)
        pages[3].draw_rect(fitz.Rect(72, 95, 540, 500), color=(0, 0, 0))
        pages[3].insert_text((84, 125), "Variable | Label | Core", fontsize=10)
        pages[3].insert_text((84, 155), "AEDECOD | Synthetic coded term | Req", fontsize=10)
        pages[3].insert_text((72, 540), "AE - Assumptions", fontsize=13)
        pages[3].insert_text(
            (84, 570),
            "1. This synthetic assumption is informative test content.",
            fontsize=10,
        )
        pages[3].insert_text((520, 760), "3", fontsize=9)
        document.set_toc(
            [
                [1, "1 Synthetic Fundamentals", 2],
                [2, "1.1 Synthetic Adverse Events", 3],
            ]
        )
        document.save(pdf_path)
        document.close()

    if not xlsx_path.exists():
        workbook = Workbook()
        datasets = workbook.active
        datasets.title = "Datasets"
        datasets.append(["Dataset Name", "Description", "Class"])
        datasets.append(["AE", "Synthetic Adverse Events", "EVENTS"])
        variables = workbook.create_sheet("Variables")
        variables.append(["Dataset Name", "Variable Name", "Variable Label", "Core"])
        variables.append(["AE", "AETERM", "Synthetic reported term", "Req"])
        variables.append(["AE", "AEDECOD", "Synthetic coded term", "Req"])
        workbook.save(xlsx_path)
        workbook.close()

    return pdf_path, xlsx_path


if __name__ == "__main__":
    fixture_root = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "pdf"
    create_fixtures(fixture_root)
    create_structure_fixtures(fixture_root)
