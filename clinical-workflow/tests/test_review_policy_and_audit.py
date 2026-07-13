import json
from datetime import datetime, timezone

import pytest

from src.change_management import ImpactAnalyzer, KnowledgeProvenance
from src.runtime.review_protocol import (
    ConsensusRule,
    Decision,
    DecisionReceipt,
    FindingCategory,
    FindingDecision,
    QueueScope,
    ReviewFinding,
    ReviewPacket,
    ReviewPolicyState,
    ReviewQueue,
    ReviewQueueScopeError,
    ReviewType,
    ReviewerAssignment,
    Severity,
    TimeoutConfig,
    Urgency,
    evaluate_review_policy,
    validate_review_packet_schema,
)


def _packet(**overrides):
    packet = ReviewPacket(
        review_id="sdtm_spec_ae_v1_001",
        review_type=ReviewType.SDTM_SPEC,
        source_documents=["input/protocol/protocol.pdf"],
        agent_summary="Review structured AE mapping before specification generation.",
        findings=[
            ReviewFinding(
                id="F-001",
                category=FindingCategory.MAPPING,
                severity=Severity.WARNING,
                location="output/sdtm/ae.yaml#AETERM",
                title="Confirm adverse event term mapping",
                current_value="AE_TERM",
                proposed_value="AETERM",
                rationale="The mapping needs CDISC terminology confirmation before use.",
                evidence_refs=["SDTMIG 3.4"],
            )
        ],
        urgency=Urgency.BLOCKING,
        generated_by="DataStandardsAgent",
        **overrides,
    )
    return packet


def _receipt(role: str, decision: Decision = Decision.APPROVED) -> DecisionReceipt:
    return DecisionReceipt(
        review_id="sdtm_spec_ae_v1_001",
        reviewer=f"{role} reviewer",
        reviewer_role=role,
        decisions=[FindingDecision("F-001", decision)],
    )


def test_review_policy_enforces_assignments_consensus_and_timeout():
    packet = _packet(
        required_reviewers=[
            ReviewerAssignment(role="biostatistician"),
            ReviewerAssignment(role="lead_programmer"),
            ReviewerAssignment(role="qa"),
        ],
        consensus_rule=ConsensusRule.MAJORITY,
        timeout_config=TimeoutConfig(reminder_hours=2, escalation_hours=4, stale_hours=8),
        created_at="2026-07-12T00:00:00+00:00",
    )

    timed_out = evaluate_review_policy(
        packet, [], now=datetime(2026, 7, 12, 5, tzinfo=timezone.utc)
    )
    assert timed_out.state == ReviewPolicyState.ESCALATION_DUE
    assert not timed_out.can_close

    ready = evaluate_review_policy(
        packet,
        [_receipt("biostatistician"), _receipt("lead_programmer")],
    )
    assert ready.state == ReviewPolicyState.READY
    assert ready.can_close
    assert ready.pending_roles == ["qa"]


def test_queue_scope_marker_prevents_study_wiki_queue_reuse_and_writes_audit(tmp_path):
    study_queue = ReviewQueue(tmp_path, scope=QueueScope.STUDY)
    packet = _packet()
    study_queue.submit_packet(packet)
    study_queue.submit_decision(_receipt("lead_programmer"))

    with pytest.raises(ReviewQueueScopeError, match="physically separate"):
        ReviewQueue(tmp_path, scope=QueueScope.WIKI)

    audit_events = [
        json.loads(line)["event"]
        for line in (tmp_path / "audit_trail.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert audit_events == ["packet_submitted", "decision_submitted"]
    marker = json.loads((tmp_path / ".review_queue" / ".queue_scope.json").read_text())
    assert marker["scope"] == "study"


def test_review_queue_schema_validation_blocks_unknown_packet_fields(tmp_path):
    packet = _packet()
    invalid = packet.to_dict() | {"unapproved_control_field": "skip_stage"}
    assert validate_review_packet_schema(invalid)

    queue = ReviewQueue(tmp_path)
    packet.generated_by = ""  # required by the shared JSON Schema
    with pytest.raises(ValueError, match="does not satisfy schema"):
        queue.submit_packet(packet)


def test_impact_analysis_carries_immutable_knowledge_manifest_provenance():
    provenance = KnowledgeProvenance(
        kind="workflow_playbook",
        record_id="wp-sdtm-spec-baseline",
        version="1.0.0",
        content_hash="a" * 64,
        snapshot_id="snapshot-20260713",
        manifest_hash="b" * 64,
    )

    result = ImpactAnalyzer().analyze(
        "protocol/endpoints.yaml", knowledge_provenance=[provenance]
    )

    assert result.knowledge_provenance == [provenance]
    assert result.knowledge_provenance[0].to_dict()["snapshot_id"] == "snapshot-20260713"
    assert "sap/sap_draft.yaml" in result.direct_impact
