"""P7-P1 AE fixture and MappingSpec contract baseline."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "studies" / "ae-pilot"
WIKI_PACKAGE = (
    ROOT
    / "tests"
    / "fixtures"
    / "knowledge"
    / "sdtmig34-poc"
    / "sources"
    / "packages"
    / "src-cdisc-sdtmig-3-4"
)

REQUIRED_SCENARIO_TYPES = {
    "success",
    "knowledge_gap",
    "missing_study_field",
    "rule_conflict",
    "program_failure",
    "validation_failure",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_ae_pilot_fixture_manifest_is_hash_locked_and_synthetic_only() -> None:
    manifest = _read_json(FIXTURE / "fixture-manifest.json")
    project = yaml.safe_load((FIXTURE / "project.yaml").read_text(encoding="utf-8"))

    assert manifest["synthetic_only"] is True
    assert project["synthetic_only"] is True
    assert project["study_id"] == manifest["study_id"] == "SYNTH-AE-001"
    assert manifest["phase_boundary"] == {
        "does_not_generate_program": True,
        "does_not_execute_transform": True,
        "does_not_modify_wiki": True,
    }

    for entry in manifest["source_files"]:
        path = FIXTURE / entry["path"]
        assert path.is_file(), entry["path"]
        assert _sha256(path) == entry["sha256"], entry["path"]
        assert entry["sha256"] != "0" * 64

    forbidden_suffixes = {".sas", ".r", ".py", ".xpt"}
    assert not [
        path
        for path in FIXTURE.rglob("*")
        if path.is_file() and path.suffix.lower() in forbidden_suffixes
    ]


def test_ae_mapping_spec_and_failure_scenarios_match_local_contracts() -> None:
    mapping_schema = _read_json(FIXTURE / "contracts" / "ae-mapping-spec.schema.json")
    scenario_schema = _read_json(FIXTURE / "contracts" / "ae-pilot-scenario.schema.json")
    mapping_spec = _read_json(FIXTURE / "mapping-specs" / "ae-mapping-spec-success.json")
    scenarios = _read_json(FIXTURE / "scenarios" / "failure-scenarios.json")

    Draft202012Validator.check_schema(mapping_schema)
    Draft202012Validator.check_schema(scenario_schema)
    Draft202012Validator(mapping_schema).validate(mapping_spec)
    for scenario in scenarios:
        Draft202012Validator(scenario_schema).validate(scenario)

    assert {scenario["scenario_type"] for scenario in scenarios} == REQUIRED_SCENARIO_TYPES
    assert all(scenario["synthetic_only"] is True for scenario in scenarios)


def test_ae_mapping_spec_rule_refs_and_gap_refs_are_closed_against_p6_outputs() -> None:
    mapping_spec = _read_json(FIXTURE / "mapping-specs" / "ae-mapping-spec-success.json")
    approved_release = _read_json(WIKI_PACKAGE / "approved-proposal-release.json")
    citation_bundle = _read_json(WIKI_PACKAGE / "ae-citation-bundle.json")

    approved_statement_ids = {
        statement["statement_id"]
        for statement in approved_release["extraction_package"]["statements"]
        if statement["review_status"] == "approved"
    }
    bundle_gap_ids = {gap["gap_id"] for gap in citation_bundle["coverage_gaps"]}
    study_context_ids = {
        ref["ref_id"]
        for ref in _read_json(FIXTURE / "input" / "study-context" / "approved-context.json")[
            "approved_context_refs"
        ]
    }

    assert mapping_spec["p6_context"] == {
        "snapshot_id": "snapshot-sdtmig34-core-events-ae-v1",
        "citation_bundle_id": "ae-citation-bundle-sdtmig34-core-events-ae-v1",
        "query_benchmark_id": "query-benchmark-sdtmig34-core-events-ae-v1",
    }

    for mapping in mapping_spec["mappings"]:
        assert mapping["material"] is True
        assert set(mapping["rule_refs"]).issubset(approved_statement_ids)
        if mapping.get("study_decision_refs"):
            assert set(mapping["study_decision_refs"]).issubset(study_context_ids)

    target_variables = {item["name"]: item for item in mapping_spec["target_variables"]}
    mapped_variables = {mapping["target_variable"] for mapping in mapping_spec["mappings"]}
    gap_variables = {gap["target_variable"] for gap in mapping_spec["gaps"]}
    assert set(target_variables) == set(_read_json(FIXTURE / "fixture-manifest.json")["expected_target_variables"])
    assert mapped_variables | gap_variables == set(target_variables)
    assert mapped_variables.isdisjoint(gap_variables)
    assert {"AEDECOD", "AESEV", "AEENRF"} == gap_variables
    for gap in mapping_spec["gaps"]:
        assert gap["source_gap_id"] in bundle_gap_ids
        assert gap["blocking"] is True


def test_ae_source_fields_and_expected_output_are_internally_consistent() -> None:
    mapping_spec = _read_json(FIXTURE / "mapping-specs" / "ae-mapping-spec-success.json")
    crf = _read_json(FIXTURE / "input" / "crf" / "ae-crf-fields.json")
    raw_rows = _csv_rows(FIXTURE / "input" / "raw" / "ae.csv")
    subject_rows = _csv_rows(FIXTURE / "input" / "raw" / "subject-reference.csv")
    expected_rows = _csv_rows(FIXTURE / "expected" / "sdtm" / "ae.csv")

    raw_columns = set(raw_rows[0])
    subject_columns = set(subject_rows[0])
    crf_columns = {field["raw_column"] for field in crf["fields"]}
    assert raw_columns == crf_columns
    assert {"STUDYID", "USUBJID", "RFSTDTC"}.issubset(subject_columns)

    for source in mapping_spec["source_inputs"]:
        assert _sha256(FIXTURE / source["path"]) == source["sha256"]
    for output in mapping_spec["expected_outputs"]:
        assert _sha256(FIXTURE / output["path"]) == output["sha256"]
        assert len(expected_rows) == output["row_count"]

    assert [row["DOMAIN"] for row in expected_rows] == ["AE", "AE", "AE"]
    assert [row["AESEQ"] for row in expected_rows] == ["1", "2", "1"]
    assert [row["AESTDY"] for row in expected_rows] == ["2", "-1", "4"]
    assert [row["AEENDY"] for row in expected_rows] == ["3", "1", ""]
    assert "AEDECOD" not in expected_rows[0]
    assert "AESEV" not in expected_rows[0]
    assert "AEENRF" not in expected_rows[0]


@pytest.mark.parametrize(
    "field",
    ["rule_refs", "source_refs"],
)
def test_material_mapping_requires_core_references(field: str) -> None:
    schema = _read_json(FIXTURE / "contracts" / "ae-mapping-spec.schema.json")
    mapping_spec = _read_json(FIXTURE / "mapping-specs" / "ae-mapping-spec-success.json")
    mapping_spec["mappings"][0].pop(field)

    errors = list(Draft202012Validator(schema).iter_errors(mapping_spec))
    assert errors
