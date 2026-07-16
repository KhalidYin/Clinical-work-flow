"""Sample study scaffold contract tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from src.application_api import ApplicationApiConfig, create_app


ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = ROOT.parent
STUDIES_ROOT = PLATFORM_ROOT / "clinical-studies"
SAMPLE_STUDY = STUDIES_ROOT / "SAMPLE-AE-001"
STUDY_TEMPLATE = ROOT / "study_template"


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    assert isinstance(loaded, dict)
    return loaded


def _missing_inventory_sources(study_dir: Path, inventory: dict) -> list[str]:
    missing: list[str] = []
    for source in inventory["sources"]:
        source_path = study_dir / source["path"]
        if not source_path.is_file():
            missing.append(source["path"])
    return missing


def test_sample_study_scaffold_keeps_raw_inputs_non_json() -> None:
    assert SAMPLE_STUDY.exists()

    json_inputs = sorted(
        path.relative_to(SAMPLE_STUDY).as_posix() for path in (SAMPLE_STUDY / "input").rglob("*.json")
    )

    assert json_inputs == []
    assert (SAMPLE_STUDY / "work" / "derived").exists()
    assert (SAMPLE_STUDY / "work" / "mapping").exists()
    assert (SAMPLE_STUDY / "programs" / "edc_to_sdtm" / "r").exists()
    assert (SAMPLE_STUDY / "programs" / "edc_to_sdtm" / "python").exists()
    assert (SAMPLE_STUDY / "programs" / "edc_to_sdtm" / "sas").exists()
    assert not (SAMPLE_STUDY / "runtime-manifest.yaml").exists()
    assert (SAMPLE_STUDY / "runtime-manifest.draft.yaml").exists()


def test_study_template_contains_real_study_source_and_program_boundaries() -> None:
    assert (STUDY_TEMPLATE / "source-inventory.yaml").exists()
    assert (STUDY_TEMPLATE / "work" / "derived").exists()
    assert (STUDY_TEMPLATE / "work" / "mapping").exists()
    assert (STUDY_TEMPLATE / "programs" / "edc_to_sdtm" / "python").exists()
    assert (STUDY_TEMPLATE / "programs" / "edc_to_sdtm" / "r").exists()
    assert (STUDY_TEMPLATE / "programs" / "edc_to_sdtm" / "sas").exists()

    project = _load_yaml(STUDY_TEMPLATE / "project.yaml")
    inventory = _load_yaml(STUDY_TEMPLATE / "source-inventory.yaml")

    assert project["source_policy"]["input_json_allowed"] is False
    assert project["source_policy"]["missing_required_source"] == "fail_closed"
    assert project["programming_chain"]["dataset_output_format_current_poc"] == "csv"
    assert project["programming_chain"]["sas_execution"] == "generate_only_until_runtime_configured"
    assert inventory["gate_policy"]["chain"] == "linear_fail_closed"
    assert inventory["supported_input_formats"]["current_poc_auto_parse"] == ["txt", "csv"]
    assert "json" in inventory["supported_input_formats"]["forbidden_in_input"]


def test_sample_source_inventory_declares_required_sources_and_gate_policy() -> None:
    project = _load_yaml(SAMPLE_STUDY / "project.yaml")
    inventory = _load_yaml(SAMPLE_STUDY / "source-inventory.yaml")

    assert inventory["input_json_allowed"] is False
    assert inventory["review_required_before_execution"] is True
    assert inventory["gate_policy"] == {
        "chain": "linear_fail_closed",
        "source_intake_required_before_parser": True,
        "parser_review_required_before_mapping": True,
        "mapping_review_required_before_programming": True,
        "program_review_required_before_canonical_output": True,
    }
    assert project["source_policy"]["input_json_allowed"] is False
    assert project["source_policy"]["missing_required_source"] == "fail_closed"
    assert project["source_policy"]["current_poc_auto_parse_formats"] == ["txt", "csv"]
    assert project["programming_chain"]["test_phase_executor"] == "python"
    assert project["programming_chain"]["required_code_artifacts_current_poc"] == ["python", "r", "sas"]
    assert project["programming_chain"]["dataset_output_format_current_poc"] == "csv"
    assert project["programming_chain"]["sas_execution"] == "generate_only_until_runtime_configured"

    required_roles = set(inventory["required_source_roles"])
    actual_roles = {source["role"] for source in inventory["sources"]}
    assert required_roles <= actual_roles


def test_sample_source_inventory_files_exist_and_use_supported_input_formats() -> None:
    inventory = _load_yaml(SAMPLE_STUDY / "source-inventory.yaml")
    supported = set(inventory["supported_input_formats"]["accepted_source_storage"])
    current_poc_formats = set(inventory["supported_input_formats"]["current_poc_auto_parse"])

    assert _missing_inventory_sources(SAMPLE_STUDY, inventory) == []

    for source in inventory["sources"]:
        source_path = SAMPLE_STUDY / source["path"]
        assert source_path.is_relative_to(SAMPLE_STUDY / "input")
        assert source["format"] in supported
        assert source_path.suffix.lstrip(".").lower() == source["format"]
        assert source["format"] in current_poc_formats


def test_missing_required_source_is_detected_before_execution(tmp_path: Path) -> None:
    study_copy = tmp_path / "SAMPLE-AE-001"
    shutil.copytree(SAMPLE_STUDY, study_copy)
    inventory = _load_yaml(study_copy / "source-inventory.yaml")

    removed_source = inventory["sources"][0]["path"]
    (study_copy / removed_source).unlink()

    assert _missing_inventory_sources(study_copy, inventory) == [removed_source]


def test_sample_study_is_visible_to_application_api_without_artifacts() -> None:
    client = TestClient(create_app(ApplicationApiConfig(container_roots={"clinical-studies": STUDIES_ROOT})))

    studies = client.get("/api/v1/studies").json()
    study_ids = [study["study_id"] for study in studies["studies"]]
    assert "SAMPLE-AE-001" in study_ids

    status = client.get("/api/v1/studies/SAMPLE-AE-001/status").json()
    assert status["study_id"] == "SAMPLE-AE-001"
    assert status["run_state"] == "idle"
    assert status["knowledge_lock"]["status"] == "missing"

    artifacts = client.get("/api/v1/studies/SAMPLE-AE-001/artifacts").json()
    assert artifacts["artifacts"] == []
