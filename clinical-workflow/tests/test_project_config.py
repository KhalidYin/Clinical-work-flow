import json
from pathlib import Path

import pytest

from src.config.project import (
    ProjectConfigError,
    load_project_config,
    resolve_project_path,
)
from src.runtime.agent_loop import AgentRuntime


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_STUDY = ROOT / "tests" / "fixtures" / "studies" / "minimal"


def test_project_schema_declares_required_runtime_contract():
    schema = json.loads((ROOT / "schemas" / "project.schema.json").read_text(encoding="utf-8"))

    assert set(schema["required"]) >= {
        "study_id",
        "protocol_id",
        "trial_phase",
        "therapeutic_area",
        "standards",
        "review_timeout",
        "review_assignments",
        "paths",
    }
    assert "phase_iv" in schema["properties"]["trial_phase"]["enum"]
    assert "sdtm_spec" in schema["properties"]["review_assignments"]["required"]


def test_load_project_config_from_fixture():
    config = load_project_config(FIXTURE_STUDY, required=True)

    assert config is not None
    assert config.study_id == "STUDY-MIN-001"
    assert config.trial_phase == "phase_ii"
    assert config.therapeutic_area == "oncology"
    assert config.standards.sdtmig_version == "3.4"
    assert config.review_timeout.stale_action == "continue"
    assert config.review_assignments.sdtm_spec.reviewers == [
        "lead_programmer",
        "data_manager",
    ]
    assert resolve_project_path(FIXTURE_STUDY, config.paths.output_dir) == (
        FIXTURE_STUDY / "output"
    )


def test_load_project_config_reports_missing_required_field(tmp_path):
    (tmp_path / "project.yaml").write_text(
        """
protocol_id: "PROT-MISSING-STUDY"
trial_phase: "phase_iii"
therapeutic_area: "oncology"
primary_language: "sas"
qc_language: "r"
sponsor: "Example Sponsor"
created_at: "2026-06-22T00:00:00Z"
standards:
  sdtm_version: "2.0"
  sdtmig_version: "3.4"
  adam_version: "2.1"
  adamig_version: "1.3"
  ct_version: "2024-03"
review_timeout:
  reminder_hours: 24
  escalation_hours: 72
  stale_hours: 168
  stale_action: "continue"
review_assignments:
  sap_review: {reviewers: ["lead"], consensus: "all_must_approve"}
  sdtm_spec: {reviewers: ["lead"], consensus: "all_must_approve"}
  adam_spec: {reviewers: ["lead"], consensus: "all_must_approve"}
  tfl_shell: {reviewers: ["lead"], consensus: "all_must_approve"}
  tfl_qc: {reviewers: ["lead"], consensus: "all_must_approve"}
  submission: {reviewers: ["lead"], consensus: "all_must_approve"}
paths:
  input_dir: "input"
  output_dir: "output"
  review_queue_dir: ".review_queue"
  audit_log: "audit_trail.jsonl"
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ProjectConfigError, match="study_id"):
        load_project_config(tmp_path, required=True)


def test_load_project_config_validates_timeout_order(tmp_path):
    project_yaml = (FIXTURE_STUDY / "project.yaml").read_text(encoding="utf-8")
    project_yaml = project_yaml.replace("reminder_hours: 24", "reminder_hours: 96")
    (tmp_path / "project.yaml").write_text(project_yaml, encoding="utf-8")

    with pytest.raises(ProjectConfigError, match="reminder_hours"):
        load_project_config(tmp_path, required=True)


def test_runtime_uses_project_yaml_over_default_context(tmp_path):
    project_yaml = (FIXTURE_STUDY / "project.yaml").read_text(encoding="utf-8")
    (tmp_path / "project.yaml").write_text(project_yaml, encoding="utf-8")

    runtime = AgentRuntime(
        project_dir=tmp_path,
        study_id="CLI-STUDY",
        trial_phase="phase_i",
        therapeutic_area="non_oncology",
        git_auto_commit=False,
    )
    context = runtime._assess_context("status")

    assert runtime.project_config is not None
    assert runtime.study_id == "STUDY-MIN-001"
    assert runtime.trial_phase == "phase_ii"
    assert runtime.therapeutic_area == "oncology"
    assert runtime.state.study_id == "STUDY-MIN-001"
    assert runtime.output_dir == tmp_path / "output"
    assert runtime.review_queue.queue_dir == tmp_path / ".review_queue"
    assert runtime.audit_log_path == tmp_path / "audit_trail.jsonl"
    assert context["project_config"]["protocol_id"] == "PROT-MIN-001"
