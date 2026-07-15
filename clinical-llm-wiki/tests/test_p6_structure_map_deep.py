"""P6-P2-C deep Core/Events/AE locator gates."""

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
from scripts.pdf.structure_map_builder import build_structure_map, write_structure_outputs
from scripts.pdf.structure_map_contract import (
    canonical_structure_map_bytes,
    validate_structure_map,
)
from scripts.pdf.structure_map_deep import (
    DeepStructureMapError,
    ScopeInterval,
    build_deep_structure_map,
    write_deep_structure_outputs,
)


ROOT = Path(__file__).resolve().parents[1]
REAL_PACKAGE = ROOT / "sources" / "packages" / "src-cdisc-sdtmig-3-4"
REAL_REPORT = REAL_PACKAGE / "deep-structure-summary.json"


def _synthetic_package(tmp_path: Path) -> Path:
    pdf_path, xlsx_path = create_structure_fixtures(tmp_path / "fixtures")
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
    base, base_report = build_structure_map(package)
    write_structure_outputs(
        base,
        base_report,
        map_path=package / "derived" / "structure-map.json",
        report_path=package / "structure-map-summary.json",
    )
    return package


def _synthetic_scope() -> list[ScopeInterval]:
    return [ScopeInterval("events", 3, 0.0, 4, 792.0)]


def test_deep_builder_merges_ae_table_and_aligns_every_variable(tmp_path: Path) -> None:
    payload, report = build_deep_structure_map(
        _synthetic_package(tmp_path), scopes=_synthetic_scope()
    )

    validate_structure_map(payload)
    coverage = report["coverage"]
    assert coverage["event_domain_count"] == 1
    assert coverage["event_xlsx_variable_rows"] == 2
    assert coverage["event_pdf_variable_rows"] == 2
    assert coverage["event_missing_variables"] == {}
    assert coverage["event_order_mismatches"] == {}
    assert coverage["event_ambiguous_spec_hits"] == 0
    assert coverage["ae_specification_segments"] == 2
    assert coverage["pdf_xlsx_alignment_references"] == 2
    assert coverage["deep_role_assumption"] >= 1
    assert coverage["deep_example_units"] >= 1

    ae_table = next(
        unit for unit in payload["units"] if unit["unit_id"].endswith("-ae-spec-table")
    )
    assert len(ae_table["locator_ids"]) == 2


def test_deep_builder_is_byte_deterministic_and_writes_hash_report(
    tmp_path: Path,
) -> None:
    package = _synthetic_package(tmp_path)
    first, first_report = build_deep_structure_map(package, scopes=_synthetic_scope())
    second, second_report = build_deep_structure_map(package, scopes=_synthetic_scope())

    assert canonical_structure_map_bytes(first) == canonical_structure_map_bytes(second)
    assert first_report == second_report
    map_path = tmp_path / "deep" / "map.json"
    report_path = tmp_path / "deep" / "report.json"
    write_deep_structure_outputs(
        first, first_report, map_path=map_path, report_path=report_path
    )
    assert map_path.read_bytes() == canonical_structure_map_bytes(first)
    assert json.loads(report_path.read_text(encoding="utf-8")) == first_report


def test_deep_builder_rejects_base_map_hash_drift(tmp_path: Path) -> None:
    package = _synthetic_package(tmp_path)
    report_path = package / "structure-map-summary.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["structure_map_sha256"] = "0" * 64
    report_path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(DeepStructureMapError, match="base structure map hash"):
        build_deep_structure_map(package, scopes=_synthetic_scope())


def test_committed_sdtmig34_deep_summary_closes_p2c_scope() -> None:
    report = json.loads(REAL_REPORT.read_text(encoding="utf-8"))
    coverage = report["coverage"]

    assert coverage["deep_physical_pages"] == 100
    assert coverage["event_domain_count"] == 7
    assert coverage["event_xlsx_variable_rows"] == 204
    assert coverage["event_pdf_variable_rows"] == 204
    assert coverage["event_missing_variables"] == {}
    assert coverage["event_order_mismatches"] == {}
    assert coverage["event_ambiguous_spec_hits"] == 0
    assert coverage["ae_xlsx_variable_rows"] == 60
    assert coverage["ae_pdf_variable_rows"] == 60
    assert coverage["ae_specification_segments"] == 4
    assert coverage["gold_locator_hits"] == coverage["gold_locator_expected"] == 7
    assert coverage["gold_locator_field_matches"] == 7
    assert coverage["gold_locator_field_differences"] == {}
    assert coverage["unresolved_textual_references"] == 0
    assert coverage["unresolved_section_labels"] == {}


def test_local_deep_map_matches_committed_summary_when_present() -> None:
    map_path = REAL_PACKAGE / "derived" / "structure-map-deep.json"
    if not map_path.is_file():
        pytest.skip("rebuildable restricted-local deep structure map is not present")
    payload = json.loads(map_path.read_text(encoding="utf-8"))
    report = json.loads(REAL_REPORT.read_text(encoding="utf-8"))
    validate_structure_map(payload)
    from scripts.pdf.structure_map_contract import structure_map_sha256

    assert structure_map_sha256(payload) == report["deep_structure_map_sha256"]
