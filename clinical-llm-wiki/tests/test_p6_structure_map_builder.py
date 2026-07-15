"""P6-P2-B deterministic full-navigation map gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.pdf.create_synthetic_fixtures import create_structure_fixtures
from scripts.pdf.source_pipeline import (
    build_derived_package,
    build_xlsx_derivative,
    ingest_companion_artifact,
    ingest_pdf,
)
from scripts.pdf.structure_map_builder import (
    StructureMapBuildError,
    build_structure_map,
    write_structure_outputs,
)
from scripts.pdf.structure_map_contract import (
    canonical_structure_map_bytes,
    validate_structure_map,
)


ROOT = Path(__file__).resolve().parents[1]
REAL_PACKAGE = ROOT / "sources" / "packages" / "src-cdisc-sdtmig-3-4"
REAL_REPORT = REAL_PACKAGE / "structure-map-summary.json"


def _synthetic_package(tmp_path: Path) -> Path:
    fixture_dir = tmp_path / "fixtures"
    pdf_path, xlsx_path = create_structure_fixtures(fixture_dir)
    package = tmp_path / "src-synthetic-structure"
    ingest_pdf(
        pdf_path,
        package,
        source_id="src-synthetic-structure",
        rights_status="cleared",
    )
    ingest_companion_artifact(
        xlsx_path,
        package,
        artifact_id="artifact-synthetic-structure-xlsx",
    )
    build_derived_package(package, dpi=72)
    build_xlsx_derivative(
        package, artifact_id="artifact-synthetic-structure-xlsx"
    )
    return package


def test_builder_maps_every_page_outline_table_and_workbook_row(tmp_path: Path) -> None:
    payload, report = build_structure_map(_synthetic_package(tmp_path))

    validate_structure_map(payload)
    assert payload["page_count"] == 4
    assert len(payload["pages"]) == 4
    assert all(page["primary_unit_id"] for page in payload["pages"])
    expected_coverage = {
        "physical_pages_expected": 4,
        "physical_pages_mapped": 4,
        "unexplained_pages": 0,
        "outline_entries": 2,
        "dataset_rows": 1,
        "variable_rows": 2,
    }
    assert all(
        report["coverage"][key] == value
        for key, value in expected_coverage.items()
    )
    assert report["coverage"]["table_boundaries"] >= 2
    assert report["unit_counts"]["dataset"] == 1
    assert report["unit_counts"]["variable_row"] == 2
    assert any(unit["unit_type"] == "front_matter" for unit in payload["units"])


def test_table_marker_does_not_promote_narrative_specification_text(
    tmp_path: Path,
) -> None:
    payload, _ = build_structure_map(_synthetic_package(tmp_path))
    titles = {unit["title"] for unit in payload["units"] if unit["unit_type"] == "table"}

    assert any("AE - Specification" in title for title in titles)
    assert len(titles) >= 2
    assert not any(title.startswith("This page provides") for title in titles)


def test_builder_is_byte_deterministic_and_writes_hash_bound_report(
    tmp_path: Path,
) -> None:
    package = _synthetic_package(tmp_path)
    first, first_report = build_structure_map(package)
    second, second_report = build_structure_map(package)

    assert canonical_structure_map_bytes(first) == canonical_structure_map_bytes(second)
    assert first_report == second_report

    map_path = tmp_path / "outputs" / "structure-map.json"
    report_path = tmp_path / "outputs" / "summary.json"
    write_structure_outputs(
        first, first_report, map_path=map_path, report_path=report_path
    )
    assert map_path.read_bytes() == canonical_structure_map_bytes(first)
    assert json.loads(report_path.read_text(encoding="utf-8")) == first_report


def test_builder_fails_closed_when_pdf_derivative_hash_is_wrong(tmp_path: Path) -> None:
    package = _synthetic_package(tmp_path)
    extraction_path = package / "derived" / "extraction.json"
    extraction = json.loads(extraction_path.read_text(encoding="utf-8"))
    extraction["source_sha256"] = "0" * 64
    extraction_path.write_text(json.dumps(extraction), encoding="utf-8")

    with pytest.raises(StructureMapBuildError, match="PDF derivative"):
        build_structure_map(package)


def test_committed_sdtmig34_summary_proves_p2b_full_navigation_coverage() -> None:
    report = json.loads(REAL_REPORT.read_text(encoding="utf-8"))
    source = json.loads(
        (REAL_PACKAGE / "source-manifest.json").read_text(encoding="utf-8")
    )

    assert report["source_id"] == source["source_id"]
    assert report["source_sha256"] == source["original_sha256"]
    assert report["coverage"]["physical_pages_expected"] == 461
    assert report["coverage"]["physical_pages_mapped"] == 461
    assert report["coverage"]["unexplained_pages"] == 0
    assert report["coverage"]["outline_entries"] == 220
    assert report["coverage"]["dataset_rows"] == 63
    assert report["coverage"]["variable_rows"] == 1917
    assert report["coverage"]["table_boundaries"] > 0


def test_local_generated_sdtmig34_map_matches_committed_summary_when_present() -> None:
    map_path = REAL_PACKAGE / "derived" / "structure-map.json"
    if not map_path.is_file():
        pytest.skip("rebuildable restricted-local structure map is not present")

    payload = json.loads(map_path.read_text(encoding="utf-8"))
    report = json.loads(REAL_REPORT.read_text(encoding="utf-8"))
    validate_structure_map(payload)
    assert payload["structure_map_id"] == report["structure_map_id"]
    from scripts.pdf.structure_map_contract import structure_map_sha256

    assert structure_map_sha256(payload) == report["structure_map_sha256"]
