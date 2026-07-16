"""Sample study scaffold contract tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from src.application_api import ApplicationApiConfig, create_app
from src.config.project import load_project_config
from src.runtime.review_protocol import validate_review_packet_schema


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


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        loaded = json.load(handle)
    assert isinstance(loaded, dict)
    return loaded


def _missing_inventory_sources(study_dir: Path, inventory: dict) -> list[str]:
    missing: list[str] = []
    for source in inventory["sources"]:
        if source.get("required_in_repository") is False:
            continue
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
    assert inventory["gate_policy"]["chain"] == "artifact_gates_fail_closed"
    assert inventory["supported_input_formats"]["current_poc_auto_parse"] == [
        "txt",
        "csv",
        "sas7bdat",
    ]
    assert inventory["target_artifact_profiles"] == {}
    assert "json" in inventory["supported_input_formats"]["forbidden_in_input"]


def test_sample_source_inventory_declares_required_sources_and_gate_policy() -> None:
    project = _load_yaml(SAMPLE_STUDY / "project.yaml")
    inventory = _load_yaml(SAMPLE_STUDY / "source-inventory.yaml")

    assert inventory["input_json_allowed"] is False
    assert inventory["review_required_before_execution"] is True
    assert inventory["gate_policy"] == {
        "chain": "artifact_gates_fail_closed",
        "source_intake_required_before_parser": True,
        "parser_review_required_before_mapping": True,
        "mapping_review_required_before_programming": True,
        "program_review_required_before_canonical_output": True,
    }
    assert project["source_policy"]["input_json_allowed"] is False
    assert project["source_policy"]["missing_required_source"] == "fail_closed"
    assert project["source_policy"]["current_poc_auto_parse_formats"] == [
        "txt",
        "csv",
        "sas7bdat",
    ]
    assert project["source_policy"]["p9_planned_auto_parse_formats"] == []
    assert project["source_policy"]["source_requirements"] == "target_artifact_profile"
    assert project["programming_chain"]["test_phase_executor"] == "python"
    assert project["programming_chain"]["required_code_artifacts_current_poc"] == ["python", "r", "sas"]
    assert project["programming_chain"]["dataset_output_format_current_poc"] == "csv"
    assert project["programming_chain"]["sas_execution"] == "generate_only_until_runtime_configured"
    assert set(project["review_assignments"]) >= {
        "source_intake",
        "parser_output",
        "sdtm_programming",
        "sdtm_spec",
    }

    profile = inventory["target_artifact_profiles"]["sdtm_ae_dataset"]
    required_roles = set(profile["required_source_roles"])
    actual_roles = {source["role"] for source in inventory["sources"]}
    assert required_roles <= actual_roles
    assert profile["optional_source_roles"] == ["study_design_context", "analysis_context"]

    sas_source = next(source for source in inventory["sources"] if source["format"] == "sas7bdat")
    assert sas_source["role"] == "ae_source_data"
    assert sas_source["storage_policy"] == "local_untracked_raw"
    assert sas_source["required_in_repository"] is False
    assert sas_source["parser_status"] == "implemented"
    assert sas_source["sha256"] == "2a6d72e9e5fa4bb8e3cc14b0c412fce3c37e519f3ab9105cdcff33ba031e8749"


def test_sample_project_yaml_can_be_loaded_as_scaffold_config() -> None:
    config = load_project_config(SAMPLE_STUDY, required=True)

    assert config is not None
    assert config.study_id == "SAMPLE-AE-001"
    assert config.therapeutic_area == "synthetic_safety"
    assert config.synthetic_only is True
    assert config.scaffold_status == "scaffold_review"
    assert config.source_policy is not None
    assert config.source_policy["input_json_allowed"] is False
    assert config.programming_chain is not None
    assert config.programming_chain["test_phase_executor"] == "python"
    assert config.review_assignments.source_intake is not None
    assert config.review_assignments.source_intake.reviewers == ["clinical_programmer"]
    assert config.paths.work_dir == "work"
    assert config.paths.program_dir == "programs"


def test_sample_source_inventory_files_exist_and_use_supported_input_formats() -> None:
    inventory = _load_yaml(SAMPLE_STUDY / "source-inventory.yaml")
    supported = set(inventory["supported_input_formats"]["accepted_source_storage"])
    current_poc_formats = set(inventory["supported_input_formats"]["current_poc_auto_parse"])
    planned_poc_formats = set(inventory["supported_input_formats"]["p9_planned_auto_parse"])

    assert _missing_inventory_sources(SAMPLE_STUDY, inventory) == []

    for source in inventory["sources"]:
        source_path = SAMPLE_STUDY / source["path"]
        assert source_path.is_relative_to(SAMPLE_STUDY / "input")
        assert source["format"] in supported
        assert source_path.suffix.lstrip(".").lower() == source["format"]
        if source.get("parser_status", "implemented") == "implemented":
            assert source["format"] in current_poc_formats
        else:
            assert source["format"] in planned_poc_formats


def test_missing_required_source_is_detected_before_execution(tmp_path: Path) -> None:
    study_copy = tmp_path / "SAMPLE-AE-001"
    shutil.copytree(SAMPLE_STUDY, study_copy)
    inventory = _load_yaml(study_copy / "source-inventory.yaml")

    removed_source = inventory["sources"][0]["path"]
    (study_copy / removed_source).unlink()

    assert _missing_inventory_sources(study_copy, inventory) == [removed_source]


def test_source_intake_review_packet_is_valid_chinese_and_blocks_parser() -> None:
    packet_path = SAMPLE_STUDY / ".review_queue" / "source_intake_sample_ae_v1_002.json"
    report_path = SAMPLE_STUDY / "work" / "derived" / "source-intake" / "source-intake-report-v1.json"
    superseded_report_path = (
        SAMPLE_STUDY / "work" / "derived" / "source-intake" / "source-intake-report-v0.json"
    )

    packet = _load_json(packet_path)
    report = _load_json(report_path)
    superseded_report = _load_json(superseded_report_path)

    assert validate_review_packet_schema(packet) == []
    assert packet["review_type"] == "source_intake"
    assert packet["urgency"] == "blocking"
    assert "审核" in packet["agent_summary"]
    assert "Parser/Derived Gate" in packet["agent_summary"]
    assert packet["required_reviewers"][0]["role"] == "clinical_programmer"
    assert report["status"] == "pending_human_review"
    assert report["policy_checks"]["input_json_files"] == []
    assert report["supersedes"] == "source-intake-sample-ae-001-v0"
    assert superseded_report["status"] == "superseded"
    assert superseded_report["superseded_by"] == report["report_id"]
    assert report["registered_sources"][0]["format"] == "sas7bdat"
    assert report["registered_sources"][0]["parser_status"] == "planned_p9_p2"
    assert report["gate_recommendation"]["allow_registered_sas7bdat_use_before_p2_adapter"] is False

    source_documents = set(packet["source_documents"])
    assert "work/derived/source-intake/source-intake-report-v1.json" in source_documents
    assert "input/edc/ae09jun2025.sas7bdat" not in source_documents

    finding_text = "\n".join(
        f"{finding['title']}\n{finding['current_value']}\n{finding['proposed_value']}\n{finding['rationale']}"
        for finding in packet["findings"]
    )
    assert "正式登记" in finding_text
    assert "不提交到 Git" in finding_text
    assert "P2" in finding_text


def test_sample_sas_parser_artifacts_are_traceable_and_reviewable() -> None:
    artifact_root = SAMPLE_STUDY / "work" / "derived" / "edc"
    metadata = _load_json(artifact_root / "source-metadata.json")
    profile = _load_json(artifact_root / "source-data-profile.json")
    validation = _load_json(artifact_root / "source-parser-validation.json")
    preview_manifest = _load_json(artifact_root / "source-preview-manifest.json")
    packet = _load_json(
        SAMPLE_STUDY / ".review_queue" / "source_intake_parser_ae_v1_001.json"
    )

    expected_hash = "2a6d72e9e5fa4bb8e3cc14b0c412fce3c37e519f3ab9105cdcff33ba031e8749"
    assert metadata["artifact_type"] == "source_metadata"
    assert metadata["source"]["sha256"] == expected_hash
    assert metadata["dataset"]["row_count"] == 1066
    assert metadata["dataset"]["column_count"] == 73
    assert metadata["metadata_availability"]["column_labels"]["available_count"] == 73
    assert metadata["metadata_availability"]["formats"]["available_count"] == 73
    assert metadata["metadata_availability"]["value_labels"]["status"] == "unavailable"
    assert profile["source"]["sha256"] == expected_hash
    assert validation["valid"] is True
    assert validation["checks"]["source_sha256_matches_inventory"] == "passed"
    assert preview_manifest["preview"]["storage_policy"] == "local_untracked_noncanonical"
    assert validate_review_packet_schema(packet) == []
    assert packet["review_type"] == "source_intake"
    assert "Parser/Derived 审核" in packet["agent_summary"]
    assert all(finding["auto_approved"] is False for finding in packet["findings"])


def test_sample_study_is_visible_with_source_parser_and_mapping_reviews() -> None:
    client = TestClient(create_app(ApplicationApiConfig(container_roots={"clinical-studies": STUDIES_ROOT})))

    studies = client.get("/api/v1/studies").json()
    study_ids = [study["study_id"] for study in studies["studies"]]
    assert "SAMPLE-AE-001" in study_ids

    status = client.get("/api/v1/studies/SAMPLE-AE-001/status").json()
    assert status["study_id"] == "SAMPLE-AE-001"
    assert status["run_state"] == "blocked_review"
    assert status["knowledge_lock"]["status"] == "missing"

    artifacts = client.get("/api/v1/studies/SAMPLE-AE-001/artifacts").json()
    review_artifact_ids = {
        artifact["artifact_id"]
        for artifact in artifacts["artifacts"]
        if artifact["artifact_type"] == "review_receipt"
    }
    assert review_artifact_ids == {
        "review_queue--source_intake_sample_ae_v1_002.json",
        "review_queue--source_intake_parser_ae_v1_001.json",
        "review_queue--sdtm_spec_sample_ae_001_mapping_v1_001.json",
    }

    reviews = client.get("/api/v1/studies/SAMPLE-AE-001/reviews").json()
    reviews_by_id = {review["review_id"]: review for review in reviews["reviews"]}
    assert set(reviews_by_id) == {
        "source_intake_sample_ae_v1_002",
        "source_intake_parser_ae_v1_001",
        "sdtm_spec_sample_ae_001_mapping_v1_001",
    }
    assert reviews_by_id["source_intake_sample_ae_v1_002"]["review_type"] == "source_intake"
    assert reviews_by_id["source_intake_parser_ae_v1_001"]["review_type"] == "source_intake"
    mapping = reviews_by_id["sdtm_spec_sample_ae_001_mapping_v1_001"]
    assert mapping["review_type"] == "sdtm_spec"
    assert "AE Mapping" in mapping["findings"][0]["title"]
    assert all(review["decision_state"] == "pending" for review in reviews_by_id.values())
