from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.knowledge.evolution import (
    EvaluationOutcome,
    EvaluationResult,
    EvidenceUnit,
    KnowledgeChangeType,
    KnowledgeEvolutionError,
    KnowledgeEvolutionReceipt,
    KnowledgeGapReport,
    KnowledgeUsageEntry,
    KnowledgeUsageManifest,
    SnapshotReference,
    create_knowledge_candidate,
)
from src.knowledge.models import RightsStatus
from src.runtime.validation_policy import FailureCategory, FailureDiagnosis


def _diagnosis(category: FailureCategory) -> FailureDiagnosis:
    return FailureDiagnosis(
        diagnosis_id=f"diagnosis.{category.value}.001",
        failure_ref="failure.sap.method.001",
        category=category,
        evidence_refs=("evidence.sap.validation.001",),
        rationale="Synthetic P11 failure attribution.",
        knowledge_usage_ref="usage-sap-001",
        candidate_eligible=category is FailureCategory.KNOWLEDGE_COVERAGE_GAP,
        requires_human_confirmation=category is FailureCategory.AMBIGUOUS_FAILURE,
    )


def _gap(category: FailureCategory) -> KnowledgeGapReport:
    diagnosis = _diagnosis(category)
    return KnowledgeGapReport(
        gap_report_id=f"gap-{category.value.replace('_', '-')}-001",
        usage_manifest_id="usage-sap-001",
        diagnosis=diagnosis,
        gap_statement="The locked snapshot lacks the required method rule.",
        required_scope=("sap-generation", "primary-method"),
        evidence_refs=("evidence.sap.validation.001",),
        candidate_allowed=diagnosis.candidate_eligible,
    )


def _evidence(
    *,
    rights_status: RightsStatus = RightsStatus.CLEARED,
    allowed_uses: tuple[str, ...] = (),
) -> EvidenceUnit:
    return EvidenceUnit(
        evidence_unit_id="evidence-unit-method-001",
        source_id="src-method-guidance-001",
        source_version="2026-07",
        source_sha256="a" * 64,
        locator_ref="section-4.2",
        statement="Use the prespecified stratified analysis for the primary endpoint.",
        statement_sha256="b" * 64,
        rights_status=rights_status,
        allowed_uses=allowed_uses,
        derivation_ref="derivation-method-extract-001",
    )


def _evaluation(
    *,
    suffix: str,
    outcome: EvaluationOutcome,
    snapshot: SnapshotReference,
    model_profile_sha256: str = "d" * 64,
    regression_failures: tuple[str, ...] = (),
) -> EvaluationResult:
    return EvaluationResult(
        evaluation_id=f"evaluation-method-{suffix}",
        case_id="evaluation-case-method-001",
        outcome=outcome,
        run_input_sha256="c" * 64,
        model_profile_sha256=model_profile_sha256,
        prompt_sha256="e" * 64,
        toolchain_sha256="f" * 64,
        snapshot=snapshot,
        regression_failures=regression_failures,
    )


def test_usage_manifest_requires_citations_or_explicit_gap() -> None:
    entry = KnowledgeUsageEntry(
        knowledge_id="kr-method-primary-001",
        knowledge_version="1.0.0",
        knowledge_sha256="1" * 64,
        source_ids=("src-method-guidance-001",),
        locator_refs=("section-4.2",),
        artifact_refs=("output/sap/sap.yaml",),
    )
    manifest = KnowledgeUsageManifest(
        manifest_id="usage-sap-001",
        run_id="run.synthetic.001",
        stage_id="sap_generation",
        snapshot_id="snapshot-method-s0",
        snapshot_sha256="2" * 64,
        query_id="query-method-001",
        query_sha256="3" * 64,
        selected_units=(entry,),
        citation_refs=("citation-method-001",),
    )
    assert manifest.selected_units == (entry,)

    with pytest.raises(ValidationError, match="selected knowledge units require"):
        KnowledgeUsageManifest.model_validate(
            {
                **manifest.model_dump(mode="json"),
                "citation_refs": [],
            }
        )


def test_only_knowledge_coverage_gap_can_create_candidate() -> None:
    candidate = create_knowledge_candidate(
        candidate_id="candidate-method-001",
        gap_report=_gap(FailureCategory.KNOWLEDGE_COVERAGE_GAP),
        change_type=KnowledgeChangeType.ADD,
        title="Primary endpoint stratified method",
        proposed_content="Apply the prespecified stratified analysis.",
        applicability_scope=("p11-synthetic-study",),
        evidence_units=(_evidence(),),
    )

    assert candidate.status == "proposed"
    assert candidate.release_scope == "p11-poc-test-only"

    for category in (
        FailureCategory.MODEL_APPLICATION_FAILURE,
        FailureCategory.RETRIEVAL_SELECTION_FAILURE,
        FailureCategory.AMBIGUOUS_FAILURE,
    ):
        with pytest.raises(KnowledgeEvolutionError, match="only knowledge_coverage_gap"):
            create_knowledge_candidate(
                candidate_id=f"candidate-{category.value.replace('_', '-')}-001",
                gap_report=_gap(category),
                change_type=KnowledgeChangeType.ADD,
                title="Invalid candidate",
                proposed_content="This content must not be promoted.",
                applicability_scope=("p11-synthetic-study",),
                evidence_units=(_evidence(),),
            )


def test_candidate_does_not_inherit_approval_and_requires_usable_rights() -> None:
    candidate = create_knowledge_candidate(
        candidate_id="candidate-method-001",
        gap_report=_gap(FailureCategory.KNOWLEDGE_COVERAGE_GAP),
        change_type=KnowledgeChangeType.ADD,
        title="Primary endpoint stratified method",
        proposed_content="Apply the prespecified stratified analysis.",
        applicability_scope=("p11-synthetic-study",),
        evidence_units=(_evidence(),),
    )
    payload = candidate.model_dump(mode="json")
    payload["approval_status"] = "approved"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        candidate.__class__.model_validate(payload)

    with pytest.raises(KnowledgeEvolutionError, match="rights"):
        create_knowledge_candidate(
            candidate_id="candidate-rights-001",
            gap_report=_gap(FailureCategory.KNOWLEDGE_COVERAGE_GAP),
            change_type=KnowledgeChangeType.ADD,
            title="Rights blocked candidate",
            proposed_content="This content cannot be used.",
            applicability_scope=("p11-synthetic-study",),
            evidence_units=(_evidence(rights_status=RightsStatus.PROHIBITED),),
        )


def test_revise_and_retire_require_explicit_superseded_ids() -> None:
    common = {
        "candidate_id": "candidate-method-001",
        "gap_report": _gap(FailureCategory.KNOWLEDGE_COVERAGE_GAP),
        "title": "Primary endpoint stratified method",
        "proposed_content": "Apply the prespecified stratified analysis.",
        "applicability_scope": ("p11-synthetic-study",),
        "evidence_units": (_evidence(),),
    }
    with pytest.raises(ValidationError, match="require superseded"):
        create_knowledge_candidate(
            **common,
            change_type=KnowledgeChangeType.REVISE,
        )

    revised = create_knowledge_candidate(
        **common,
        change_type=KnowledgeChangeType.REVISE,
        supersedes_knowledge_ids=("kr-method-primary-001",),
    )
    assert revised.supersedes_knowledge_ids == ("kr-method-primary-001",)


def test_evolution_receipt_proves_snapshot_only_fail_to_pass_change() -> None:
    before_snapshot = SnapshotReference(
        snapshot_id="snapshot-method-s0",
        version="1.0.0",
        sha256="0" * 64,
    )
    after_snapshot = SnapshotReference(
        snapshot_id="snapshot-method-s1",
        version="1.0.1",
        sha256="1" * 64,
        parent_snapshot_id=before_snapshot.snapshot_id,
    )
    receipt = KnowledgeEvolutionReceipt(
        receipt_id="evolution-method-001",
        candidate_id="candidate-method-001",
        review_receipt_ref="review.knowledge.method.001",
        before=_evaluation(
            suffix="s0",
            outcome=EvaluationOutcome.FAIL,
            snapshot=before_snapshot,
            regression_failures=("regression-existing-001",),
        ),
        after=_evaluation(
            suffix="s1",
            outcome=EvaluationOutcome.PASS,
            snapshot=after_snapshot,
            regression_failures=(),
        ),
    )
    assert receipt.changed_dimensions == ("knowledge_snapshot",)


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("model", "invariants changed"),
        ("same_snapshot", "new immutable snapshot"),
        ("wrong_parent", "locked prior snapshot"),
        ("new_regression", "introduced regression"),
    ],
)
def test_evolution_receipt_rejects_non_causal_or_mutating_transition(
    mutation: str,
    error: str,
) -> None:
    before_snapshot = SnapshotReference(
        snapshot_id="snapshot-method-s0",
        version="1.0.0",
        sha256="0" * 64,
    )
    after_snapshot = SnapshotReference(
        snapshot_id="snapshot-method-s1",
        version="1.0.1",
        sha256="1" * 64,
        parent_snapshot_id=before_snapshot.snapshot_id,
    )
    before = _evaluation(
        suffix="s0",
        outcome=EvaluationOutcome.FAIL,
        snapshot=before_snapshot,
    )
    after = _evaluation(
        suffix="s1",
        outcome=EvaluationOutcome.PASS,
        snapshot=after_snapshot,
    )
    if mutation == "model":
        after = _evaluation(
            suffix="s1",
            outcome=EvaluationOutcome.PASS,
            snapshot=after_snapshot,
            model_profile_sha256="9" * 64,
        )
    elif mutation == "same_snapshot":
        after = _evaluation(
            suffix="s1",
            outcome=EvaluationOutcome.PASS,
            snapshot=before_snapshot,
        )
    elif mutation == "wrong_parent":
        after = _evaluation(
            suffix="s1",
            outcome=EvaluationOutcome.PASS,
            snapshot=SnapshotReference(
                snapshot_id="snapshot-method-s1",
                version="1.0.1",
                sha256="1" * 64,
                parent_snapshot_id="snapshot-unrelated-001",
            ),
        )
    else:
        after = _evaluation(
            suffix="s1",
            outcome=EvaluationOutcome.PASS,
            snapshot=after_snapshot,
            regression_failures=("regression-new-001",),
        )

    with pytest.raises(ValidationError, match=error):
        KnowledgeEvolutionReceipt(
            receipt_id="evolution-method-001",
            candidate_id="candidate-method-001",
            review_receipt_ref="review.knowledge.method.001",
            before=before,
            after=after,
        )
