from src.runtime.review_protocol import (
    Decision,
    FindingCategory,
    FindingDecision,
    RejectionReason,
    ReviewFinding,
    ReviewType,
    Severity,
    Urgency,
    new_review_packet,
    validate_decision_receipt,
    validate_review_packet,
)


def test_review_packet_requires_audit_fields_and_auto_approved():
    finding = ReviewFinding(
        id="F-001",
        category=FindingCategory.MAPPING,
        severity=Severity.WARNING,
        location="AE.AETERM",
        title="Confirm AE term mapping",
        current_value="AE_TERM",
        proposed_value="AETERM",
        rationale="Direct CRF to SDTM mapping with CDISC evidence.",
        evidence_refs=["SDTMIG 3.4 AE"],
        auto_approved=False,
    )

    packet = new_review_packet(
        review_type=ReviewType.SDTM_SPEC,
        source_documents=["input/protocol/protocol.pdf"],
        agent_summary="Generated AE mapping findings for review.",
        generated_by="DataStandardsAgent",
        findings=[finding],
        urgency=Urgency.BLOCKING,
        domain_or_dataset="ae",
    )

    assert validate_review_packet(packet.to_dict()) == []


def test_rejected_decision_requires_structured_feedback():
    receipt = {
        "review_id": "sdtm_spec_ae_v1_001",
        "reviewer": "Lead Programmer",
        "timestamp": "2026-06-22T00:00:00Z",
        "decisions": [
            {"finding_id": "F-001", "decision": "rejected"},
            {
                "finding_id": "F-002",
                "decision": "rejected",
                "rejection_reason": "incorrect_derivation",
            },
        ],
    }

    violations = validate_decision_receipt(receipt)

    assert "Decision[0]: decision=rejected requires rejection_reason" in violations
    assert (
        "Decision[1]: rejected decision requires human_correction "
        "with at least 10 characters"
    ) in violations


def test_insufficient_evidence_rejection_can_omit_correction():
    receipt = {
        "review_id": "sdtm_spec_ae_v1_001",
        "reviewer": "Lead Programmer",
        "timestamp": "2026-06-22T00:00:00Z",
        "decisions": [
            {
                "finding_id": "F-001",
                "decision": "rejected",
                "rejection_reason": "insufficient_evidence",
            },
        ],
    }

    assert validate_decision_receipt(receipt) == []


def test_finding_decision_round_trips_rejection_feedback():
    decision = FindingDecision(
        finding_id="F-001",
        decision=Decision.REJECTED,
        rejection_reason=RejectionReason.INCORRECT_DERIVATION,
        human_correction="Use RFSTDTC rather than TRTSDT for this derivation.",
        reference="SAP Section 5.2",
    )

    restored = FindingDecision.from_dict(decision.to_dict())

    assert restored.rejection_reason == RejectionReason.INCORRECT_DERIVATION
    assert restored.human_correction == decision.human_correction
    assert restored.reference == "SAP Section 5.2"
