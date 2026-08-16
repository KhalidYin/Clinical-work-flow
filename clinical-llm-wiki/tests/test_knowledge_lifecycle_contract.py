from __future__ import annotations

import pytest
from pydantic import ValidationError

from service import knowledge


def _contract(name: str) -> object:
    assert hasattr(knowledge, name), f"P17 lifecycle contract is missing: {name}"
    return getattr(knowledge, name)


def test_chunk_profile_v1_keeps_the_approved_token_boundaries() -> None:
    profile_type = _contract("ChunkProfileContract")

    profile = profile_type(
        chunk_profile_id="chunk-profile-v1",
        version="v1",
        tokenizer_id="p17-test-tokenizer-v1",
        format_rules={"major_section_boundary": True, "table_row_atomic": True},
    )

    assert profile.target_min_tokens == 400
    assert profile.target_max_tokens == 700
    assert profile.hard_max_tokens == 900
    assert profile.overlap_tokens == 80
    assert profile.table_hard_max_tokens == 1200
    assert {
        "profile_sha256",
        "rules_sha256",
        "locator_sha256",
    }.isdisjoint(profile_type.model_fields)

    with pytest.raises(ValidationError, match="overlap_tokens"):
        profile_type(
            chunk_profile_id="chunk-profile-invalid",
            version="invalid",
            tokenizer_id="p17-test-tokenizer-v1",
            target_min_tokens=400,
            target_max_tokens=700,
            hard_max_tokens=900,
            overlap_tokens=400,
            table_hard_max_tokens=1200,
            format_rules={"major_section_boundary": True},
        )


def test_retrieval_chunk_identity_is_deterministic_without_profile_hash() -> None:
    identity = _contract("retrieval_chunk_identity")

    first = identity(
        profile_version="v1",
        source_version_id="source-version-1",
        ordinal=3,
        evidence_spans=(("evidence-1", 0, 120, "primary"),),
        content_sha256="a" * 64,
    )
    repeated = identity(
        profile_version="v1",
        source_version_id="source-version-1",
        ordinal=3,
        evidence_spans=(("evidence-1", 0, 120, "primary"),),
        content_sha256="a" * 64,
    )
    changed = identity(
        profile_version="v1",
        source_version_id="source-version-1",
        ordinal=4,
        evidence_spans=(("evidence-1", 0, 120, "primary"),),
        content_sha256="a" * 64,
    )

    assert first == repeated
    assert first.startswith("chunk-")
    assert changed != first


def test_evidence_impact_requires_a_change_specific_mapping_shape() -> None:
    impact_type = _contract("EvidenceImpactRecord")
    change_type = _contract("EvidenceChangeType")
    mapping_basis = _contract("EvidenceMappingBasis")

    added = impact_type(
        evidence_impact_id="impact-added",
        change_type=change_type.ADDED,
        from_evidence_id=None,
        to_evidence_id="evidence-new",
        mapping_basis=mapping_basis.UNMATCHED,
        details={},
    )
    assert added.from_evidence_id is None

    with pytest.raises(ValidationError, match="modified"):
        impact_type(
            evidence_impact_id="impact-invalid",
            change_type=change_type.MODIFIED,
            from_evidence_id="evidence-old",
            to_evidence_id=None,
            mapping_basis=mapping_basis.ORDERED_ALIGNMENT,
            details={},
        )


def test_impact_assessment_is_immutable_and_compares_distinct_versions() -> None:
    assessment_type = _contract("ImpactAssessmentRecord")
    impact_type = _contract("EvidenceImpactRecord")
    change_type = _contract("EvidenceChangeType")
    mapping_basis = _contract("EvidenceMappingBasis")

    impact = impact_type(
        evidence_impact_id="impact-1",
        change_type=change_type.UNCHANGED,
        from_evidence_id="evidence-old",
        to_evidence_id="evidence-new",
        mapping_basis=mapping_basis.CONTENT_EXACT,
        details={},
    )
    assessment = assessment_type(
        assessment_id="assessment-1",
        from_source_version_id="source-v1",
        to_source_version_id="source-v2",
        comparison_profile_version="comparison-v1",
        impacts=(impact,),
    )
    assert assessment.impacts == (impact,)
    with pytest.raises(ValidationError, match="distinct"):
        assessment_type(
            assessment_id="assessment-invalid",
            from_source_version_id="source-v1",
            to_source_version_id="source-v1",
            comparison_profile_version="comparison-v1",
            impacts=(impact,),
        )
    with pytest.raises(ValidationError, match="frozen"):
        assessment.to_source_version_id = "source-v3"


def test_rotation_decision_requires_reviewer_and_target_shape() -> None:
    command_type = _contract("RotationDecisionCommand")
    receipt_type = _contract("RotationDecisionReceipt")
    outcome = _contract("RotationOutcome")

    command = command_type(
        rotation_case_id="rotation-case-1",
        expected_case_version=2,
        outcome=outcome.REPLACE,
        target_knowledge_revision_id="revision-2",
        idempotency_key="rotation-decision-001",
        rationale="Source evidence changed.",
    )
    assert command.target_knowledge_revision_id == "revision-2"

    with pytest.raises(ValidationError, match="target"):
        command_type(
            rotation_case_id="rotation-case-1",
            expected_case_version=2,
            outcome=outcome.RETIRE,
            target_knowledge_revision_id="revision-2",
            idempotency_key="rotation-decision-002",
        )

    with pytest.raises(ValidationError, match="reviewer"):
        receipt_type(
            rotation_decision_id="rotation-decision-1",
            rotation_case_id="rotation-case-1",
            outcome=outcome.REPLACE,
            expected_case_version=2,
            target_knowledge_revision_id="revision-2",
            actor_id="release-manager-1",
            actor_role="release_manager",
            idempotency_key="rotation-decision-003",
        )


def test_rotation_state_machine_rejects_skips_and_terminal_mutation() -> None:
    require_transition = _contract("require_rotation_transition")
    status = _contract("RotationCaseStatus")
    transition_error = _contract("InvalidRotationTransitionError")

    require_transition(status.OPEN, status.IN_REVIEW)
    require_transition(status.IN_REVIEW, status.DECIDED)
    require_transition(status.DECIDED, status.INCLUDED_IN_RELEASE)
    require_transition(status.DECIDED, status.CLOSED)

    with pytest.raises(transition_error, match="open.*decided"):
        require_transition(status.OPEN, status.DECIDED)
    with pytest.raises(transition_error, match="terminal"):
        require_transition(status.CLOSED, status.IN_REVIEW)
