"""Fail-closed loading and projection of approved Study decisions."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.knowledge.compatibility import sha256_bytes, sha256_canonical_json
from src.knowledge.models import RuleLayer, WorkflowStage
from src.knowledge.study_decisions import (
    StudyDecisionError,
    load_study_decision,
    load_study_decisions,
    project_study_decision,
)


DECISION_ID = "study-decision-synth-onco-001-teae"
REVIEW_ID = "adam_spec_adae_v1_001"
FINDING_ID = "F-001"


def _teae_rule() -> dict[str, object]:
    return {
        "rule_type": "teae_window",
        "target_dataset": "ADAE",
        "target_variable": "TRTEMFL",
        "event_start_date": "ADAE.ASTDT",
        "treatment_start_date": "ADSL.TRTSDT",
        "treatment_end_date": "ADSL.TRTEDT",
        "start_offset_days": 0,
        "end_offset_days": 30,
        "lower_bound_inclusive": True,
        "upper_bound_inclusive": True,
        "incomplete_event_date_policy": "review_required",
        "missing_treatment_date_policy": "review_required",
        "multiple_treatment_period_policy": "review_required",
        "pre_treatment_worsening_policy": "include_if_worsened",
    }


def _write_json(path: Path, payload: dict[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return sha256_bytes(path.read_bytes())


def _core_decision() -> dict[str, object]:
    return {
        "decision_id": DECISION_ID,
        "schema_version": "1.0.0",
        "version": "1.0.0",
        "study_id": "SYNTH-ONCO-001",
        "stage": "adam_spec",
        "priority": 700,
        "title": "Synthetic study TEAE window",
        "statement": "Apply the approved study TEAE window to ADAE.TRTEMFL.",
        "source_ids": ["kr-teae-safety-window"],
        "structured_rule": _teae_rule(),
    }


def _build_project(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    project = tmp_path / "study"
    core = _core_decision()
    content_sha256 = sha256_canonical_json(core)
    archive = project / ".review_queue" / "archive"

    packet = {
        "review_id": REVIEW_ID,
        "review_type": "adam_spec",
        "source_documents": ["knowledge/decisions/teae-window.json"],
        "agent_summary": "Approve the structured TEAE Study decision.",
        "findings": [
            {
                "id": FINDING_ID,
                "category": "derivation",
                "severity": "critical",
                "location": "knowledge/decisions/teae-window.json#structured_rule",
                "title": "Approve structured TEAE window",
                "current_value": "unapproved",
                "proposed_value": "approved structured rule",
                "rationale": "ADAE execution requires an explicit reviewed Study rule.",
                "evidence_refs": [
                    f"study-decision:{DECISION_ID}",
                    f"sha256:{content_sha256}",
                ],
                "auto_approved": False,
            }
        ],
        "urgency": "blocking",
        "created_at": "2026-07-13T00:00:00Z",
        "generated_by": "DataStandardsAgent",
        "auto_approved_count": 0,
    }
    receipt = {
        "review_id": REVIEW_ID,
        "reviewer": "Lead Statistical Programmer",
        "timestamp": "2026-07-13T00:01:00Z",
        "decisions": [{"finding_id": FINDING_ID, "decision": "approved"}],
    }
    confirmation = {
        "review_id": REVIEW_ID,
        "applied_at": "2026-07-13T00:02:00Z",
        "generated_by": "AgentRuntime",
        "results": [
            {
                "finding_id": FINDING_ID,
                "original_decision": "approved",
                "application_status": "applied",
                "actual_value": "approved structured rule",
            }
        ],
        "summary": {"total": 1, "applied": 1, "adjusted": 0, "failed": 0},
    }

    packet_path = archive / f"{REVIEW_ID}.json"
    receipt_path = archive / f"{REVIEW_ID}_decision.json"
    confirmation_path = archive / f"{REVIEW_ID}_confirmation.json"
    evidence = {
        "review_id": REVIEW_ID,
        "finding_id": FINDING_ID,
        "packet_path": packet_path.relative_to(project).as_posix(),
        "packet_sha256": _write_json(packet_path, packet),
        "decision_path": receipt_path.relative_to(project).as_posix(),
        "decision_sha256": _write_json(receipt_path, receipt),
        "confirmation_path": confirmation_path.relative_to(project).as_posix(),
        "confirmation_sha256": _write_json(confirmation_path, confirmation),
    }
    decision = {
        **core,
        "approval_evidence": evidence,
        "content_sha256": content_sha256,
    }
    decision_path = project / "knowledge" / "decisions" / "teae-window.json"
    _write_json(decision_path, decision)
    return project, decision_path, decision


def _load(project: Path, decision_path: Path):
    decision = load_study_decision(
        project_dir=project,
        decision_path=decision_path,
        expected_study_id="SYNTH-ONCO-001",
        expected_stage=WorkflowStage.ADAM_SPEC,
    )
    rule, provenance = project_study_decision(decision)
    return decision, rule, provenance


def test_loads_approved_decision_and_projects_rule_and_provenance(tmp_path: Path) -> None:
    project, decision_path, decision = _build_project(tmp_path)

    loaded, rule, provenance = _load(project, decision_path)

    assert loaded.content_sha256 == decision["content_sha256"]
    assert rule.rule_id == DECISION_ID
    assert rule.layer is RuleLayer.STUDY
    assert rule.source_ids == (
        DECISION_ID,
        "kr-teae-safety-window",
    )
    assert rule.source_sha256 == decision["content_sha256"]
    assert rule.approval_receipt_id == REVIEW_ID
    assert rule.structured_rule is not None
    assert rule.structured_rule.end_offset_days == 30
    assert provenance.object_id == DECISION_ID
    assert provenance.object_sha256 == decision["content_sha256"]
    assert provenance.source_kind == "study_decision"


def test_loads_stage_decisions_in_stable_order_and_allows_empty_directory(
    tmp_path: Path,
) -> None:
    project, _decision_path, _decision = _build_project(tmp_path)

    decisions = load_study_decisions(
        project,
        study_id="SYNTH-ONCO-001",
        stage=WorkflowStage.ADAM_SPEC,
    )

    assert [item.decision_id for item in decisions] == [DECISION_ID]
    assert load_study_decisions(
        tmp_path / "empty-study",
        study_id="SYNTH-ONCO-001",
        stage=WorkflowStage.ADAM_SPEC,
    ) == ()


def test_rejects_decision_outside_project_decision_directory(tmp_path: Path) -> None:
    project, _decision_path, decision = _build_project(tmp_path)
    outside = tmp_path / "outside.json"
    _write_json(outside, decision)

    with pytest.raises(StudyDecisionError, match="knowledge/decisions"):
        _load(project, outside)


@pytest.mark.parametrize(
    ("study_id", "stage", "message"),
    [
        ("OTHER-STUDY", WorkflowStage.ADAM_SPEC, "study_id"),
        ("SYNTH-ONCO-001", WorkflowStage.SDTM_SPEC, "stage"),
    ],
)
def test_rejects_study_or_stage_mismatch(
    tmp_path: Path,
    study_id: str,
    stage: WorkflowStage,
    message: str,
) -> None:
    project, decision_path, _decision = _build_project(tmp_path)

    with pytest.raises(StudyDecisionError, match=message):
        load_study_decision(
            project_dir=project,
            decision_path=decision_path,
            expected_study_id=study_id,
            expected_stage=stage,
        )


def test_rejects_modified_decision_content_without_matching_hash(tmp_path: Path) -> None:
    project, decision_path, decision = _build_project(tmp_path)
    changed = deepcopy(decision)
    changed["structured_rule"]["end_offset_days"] = 60
    _write_json(decision_path, changed)

    with pytest.raises(StudyDecisionError, match="content_sha256"):
        _load(project, decision_path)


@pytest.mark.parametrize("decision_value", ["modified", "rejected"])
def test_requires_an_approved_finding_decision(
    tmp_path: Path,
    decision_value: str,
) -> None:
    project, decision_path, decision = _build_project(tmp_path)
    receipt_path = project / decision["approval_evidence"]["decision_path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["decisions"][0]["decision"] = decision_value
    if decision_value == "modified":
        receipt["decisions"][0]["modified_value"] = "changed"
    else:
        receipt["decisions"][0]["rejection_reason"] = "incorrect_method"
        receipt["decisions"][0]["human_correction"] = "Do not approve this rule."
    decision["approval_evidence"]["decision_sha256"] = _write_json(receipt_path, receipt)
    _write_json(decision_path, decision)

    with pytest.raises(StudyDecisionError, match="approved"):
        _load(project, decision_path)


@pytest.mark.parametrize("application_status", ["applied_with_adjustment", "failed"])
def test_requires_confirmation_that_approved_finding_was_applied(
    tmp_path: Path,
    application_status: str,
) -> None:
    project, decision_path, decision = _build_project(tmp_path)
    path = project / decision["approval_evidence"]["confirmation_path"]
    confirmation = json.loads(path.read_text(encoding="utf-8"))
    confirmation["results"][0]["application_status"] = application_status
    confirmation["summary"] = {
        "total": 1,
        "applied": 0,
        "adjusted": int(application_status == "applied_with_adjustment"),
        "failed": int(application_status == "failed"),
    }
    decision["approval_evidence"]["confirmation_sha256"] = _write_json(path, confirmation)
    _write_json(decision_path, decision)

    with pytest.raises(StudyDecisionError, match="applied"):
        _load(project, decision_path)


def test_rejects_missing_confirmation_and_evidence_tampering(tmp_path: Path) -> None:
    project, decision_path, decision = _build_project(tmp_path)
    confirmation = project / decision["approval_evidence"]["confirmation_path"]
    confirmation.unlink()
    with pytest.raises(StudyDecisionError, match="confirmation"):
        _load(project, decision_path)

    project, decision_path, decision = _build_project(tmp_path / "tamper")
    packet = project / decision["approval_evidence"]["packet_path"]
    packet.write_text(packet.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(StudyDecisionError, match="packet.*SHA-256"):
        _load(project, decision_path)


@pytest.mark.parametrize(
    "evidence_refs",
    [
        [f"study-decision:{DECISION_ID}"],
        [f"sha256:{'0' * 64}"],
        [f"study-decision:{DECISION_ID}-other", "sha256:" + "0" * 64],
    ],
)
def test_packet_evidence_must_exactly_identify_decision_and_hash(
    tmp_path: Path,
    evidence_refs: list[str],
) -> None:
    project, decision_path, decision = _build_project(tmp_path)
    path = project / decision["approval_evidence"]["packet_path"]
    packet = json.loads(path.read_text(encoding="utf-8"))
    packet["findings"][0]["evidence_refs"] = evidence_refs
    decision["approval_evidence"]["packet_sha256"] = _write_json(path, packet)
    _write_json(decision_path, decision)

    with pytest.raises(StudyDecisionError, match="evidence_refs"):
        _load(project, decision_path)


def test_review_packet_receipt_and_confirmation_must_share_review_and_finding(
    tmp_path: Path,
) -> None:
    project, decision_path, decision = _build_project(tmp_path)
    path = project / decision["approval_evidence"]["confirmation_path"]
    confirmation = json.loads(path.read_text(encoding="utf-8"))
    confirmation["review_id"] = "another_review"
    decision["approval_evidence"]["confirmation_sha256"] = _write_json(path, confirmation)
    _write_json(decision_path, decision)

    with pytest.raises(StudyDecisionError, match="review_id"):
        _load(project, decision_path)

    project, decision_path, decision = _build_project(tmp_path / "finding")
    receipt_path = project / decision["approval_evidence"]["decision_path"]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["decisions"][0]["finding_id"] = "F-002"
    decision["approval_evidence"]["decision_sha256"] = _write_json(
        receipt_path,
        receipt,
    )
    _write_json(decision_path, decision)

    with pytest.raises(StudyDecisionError, match="finding_id"):
        _load(project, decision_path)


def test_evidence_path_cannot_escape_project(tmp_path: Path) -> None:
    project, decision_path, decision = _build_project(tmp_path)
    decision["approval_evidence"]["packet_path"] = "../outside.json"
    _write_json(decision_path, decision)

    with pytest.raises(StudyDecisionError, match="inside the Study project"):
        _load(project, decision_path)
