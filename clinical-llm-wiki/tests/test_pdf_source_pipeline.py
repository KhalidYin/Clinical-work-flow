from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.pdf import source_pipeline
from scripts.pdf.create_synthetic_fixtures import create_fixtures
from scripts.pdf.source_pipeline import OcrResult, SourceIntegrityError, build_derived_package, ingest_pdf, sha256_file
from scripts.quality.pdf_visual_qa import render_pdf_pages, validate_pdf_visual_evidence


FIXTURES = Path(__file__).parent / "fixtures" / "pdf"


@pytest.fixture(scope="session", autouse=True)
def synthetic_fixtures() -> None:
    create_fixtures(FIXTURES)


def test_digital_pdf_ingestion_preserves_immutable_original_and_coordinates(tmp_path: Path) -> None:
    fixture = FIXTURES / "synthetic-digital.pdf"
    package = tmp_path / "src-digital"
    source = ingest_pdf(fixture, package, source_id="src-synthetic-digital", rights_status="cleared")
    original = package / source["original_relative_path"]
    before = original.read_bytes()
    before_hash = sha256_file(original)

    derived = build_derived_package(package)
    extraction = json.loads((package / "derived" / "extraction.json").read_text(encoding="utf-8"))

    assert original.read_bytes() == before
    assert sha256_file(original) == before_hash == source["original_sha256"]
    assert derived["source_sha256"] == before_hash
    assert extraction["source_type"] == "digital"
    assert extraction["pages"][0]["physical_page"] == 1
    assert extraction["pages"][0]["words"]
    assert len(extraction["pages"][0]["words"][0]["bbox"]) == 4
    assert "Synthetic" in extraction["pages"][0]["text"]


def test_conflicting_reingestion_is_rejected_not_overwritten(tmp_path: Path) -> None:
    package = tmp_path / "src-conflict"
    ingest_pdf(FIXTURES / "synthetic-digital.pdf", package, source_id="src-synthetic-digital")
    with pytest.raises(SourceIntegrityError):
        ingest_pdf(FIXTURES / "synthetic-scanned.pdf", package, source_id="src-synthetic-digital")


def test_scanned_pdf_records_ocr_unavailable_without_faking_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / "src-scan"
    ingest_pdf(FIXTURES / "synthetic-scanned.pdf", package, source_id="src-synthetic-scanned")
    monkeypatch.setattr(source_pipeline, "_default_ocr", lambda _: OcrResult("unavailable", "", "test OCR unavailable"))
    manifest = build_derived_package(package)
    extraction = json.loads((package / "derived" / "extraction.json").read_text(encoding="utf-8"))

    assert manifest["source_type"] == "scanned"
    assert manifest["ocr"]["status"] == "unavailable"
    assert extraction["ocr"]["status"] == "unavailable"
    assert extraction["pages"][0]["words"] == []


def test_visual_qa_renders_and_checks_page_and_figure_provenance(tmp_path: Path) -> None:
    package = tmp_path / "src-visual"
    source = ingest_pdf(FIXTURES / "synthetic-digital.pdf", package, source_id="src-synthetic-visual", rights_status="cleared")
    build_derived_package(package)
    result = validate_pdf_visual_evidence(package)
    independent = render_pdf_pages(package / source["original_relative_path"], tmp_path / "manual-render")

    assert result["status"] == "passed"
    assert result["checked_figures"] == 1
    assert independent[0].is_file()


def test_derived_material_is_rebuildable_from_unchanged_original(tmp_path: Path) -> None:
    package = tmp_path / "src-rebuild"
    source = ingest_pdf(FIXTURES / "synthetic-digital.pdf", package, source_id="src-synthetic-rebuild")
    original_hash = sha256_file(package / source["original_relative_path"])
    first = build_derived_package(package)
    first_extraction = (package / "derived" / "extraction.json").read_bytes()
    shutil.rmtree(package / "derived")
    second = build_derived_package(package)

    assert sha256_file(package / source["original_relative_path"]) == original_hash
    assert (package / "derived" / "extraction.json").read_bytes() == first_extraction
    assert first["output_manifest_sha256"] == second["output_manifest_sha256"]
