from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.runtime.agent_backend import FindingSeverity, ValidationFinding
from src.runtime.validation_policy import (
    FailureCategory,
    FailureDiagnosis,
    FindingOrigin,
    GateDisposition,
    SourcedFinding,
    ValidationPolicyError,
    evaluate_validation_gate,
    merge_validation_findings,
)


def _finding(
    *,
    finding_id: str = "finding.trace.001",
    severity: FindingSeverity = FindingSeverity.MAJOR,
    category: str = "traceability",
    artifact_id: str = "artifact.sdtm.dm",
    statement: str = "The source trace is incomplete.",
) -> ValidationFinding:
    return ValidationFinding(
        finding_id=finding_id,
        severity=severity,
        category=category,
        statement=statement,
        artifact_id=artifact_id,
        evidence_refs=("evidence.trace.001",),
        proposed_correction="Restore the missing trace reference.",
    )


def _sourced(
    origin: FindingOrigin,
    *,
    source_ref: str,
    finding: ValidationFinding | None = None,
) -> SourcedFinding:
    return SourcedFinding(
        origin=origin,
        source_ref=source_ref,
        finding=finding or _finding(),
    )


@pytest.mark.parametrize("category", tuple(FailureCategory))
def test_failure_diagnosis_exposes_exactly_six_fail_closed_categories(
    category: FailureCategory,
) -> None:
    diagnosis = FailureDiagnosis(
        diagnosis_id=f"diagnosis.{category.value}.001",
        failure_ref="failure.synthetic.001",
        category=category,
        evidence_refs=("evidence.synthetic.001",),
        rationale="Synthetic diagnosis used to verify the governance flags.",
        knowledge_usage_ref="usage.synthetic.001",
        candidate_eligible=category is FailureCategory.KNOWLEDGE_COVERAGE_GAP,
        requires_human_confirmation=category is FailureCategory.AMBIGUOUS_FAILURE,
    )

    assert diagnosis.candidate_eligible is (
        category is FailureCategory.KNOWLEDGE_COVERAGE_GAP
    )
    assert diagnosis.requires_human_confirmation is (
        category is FailureCategory.AMBIGUOUS_FAILURE
    )


def test_failure_diagnosis_rejects_manual_candidate_or_confirmation_override() -> None:
    with pytest.raises(ValidationError, match="candidate_eligible"):
        FailureDiagnosis(
            diagnosis_id="diagnosis.model.001",
            failure_ref="failure.synthetic.001",
            category=FailureCategory.MODEL_APPLICATION_FAILURE,
            evidence_refs=("evidence.synthetic.001",),
            rationale="The rule existed but the producer applied it incorrectly.",
            knowledge_usage_ref="usage.synthetic.001",
            candidate_eligible=True,
            requires_human_confirmation=False,
        )

    with pytest.raises(ValidationError, match="requires_human_confirmation"):
        FailureDiagnosis(
            diagnosis_id="diagnosis.ambiguous.001",
            failure_ref="failure.synthetic.001",
            category=FailureCategory.AMBIGUOUS_FAILURE,
            evidence_refs=("evidence.synthetic.001",),
            rationale="The evidence does not support a unique failure category.",
            knowledge_usage_ref="usage.synthetic.001",
            candidate_eligible=False,
            requires_human_confirmation=False,
        )


def test_finding_merge_preserves_deterministic_severity_floor() -> None:
    deterministic = _sourced(
        FindingOrigin.DETERMINISTIC,
        source_ref="validation.deterministic.001",
        finding=_finding(severity=FindingSeverity.MAJOR),
    )
    llm = _sourced(
        FindingOrigin.LLM_VALIDATOR,
        source_ref="validation.llm.001",
        finding=_finding(
            severity=FindingSeverity.MINOR,
            statement="The validator considered the issue minor.",
        ),
    )

    merged = merge_validation_findings((llm, deterministic))

    assert len(merged) == 1
    assert merged[0].severity is FindingSeverity.MAJOR
    assert merged[0].statement == deterministic.finding.statement
    assert merged[0].origins == (
        FindingOrigin.DETERMINISTIC,
        FindingOrigin.LLM_VALIDATOR,
    )


def test_finding_merge_rejects_identity_conflict_or_duplicate_source() -> None:
    deterministic = _sourced(
        FindingOrigin.DETERMINISTIC,
        source_ref="validation.deterministic.001",
    )
    conflicting = _sourced(
        FindingOrigin.LLM_VALIDATOR,
        source_ref="validation.llm.001",
        finding=_finding(artifact_id="artifact.sdtm.ae"),
    )
    with pytest.raises(ValidationPolicyError, match="conflicting"):
        merge_validation_findings((deterministic, conflicting))

    with pytest.raises(ValidationPolicyError, match="duplicate"):
        merge_validation_findings((deterministic, deterministic))


def test_gate_policy_allows_only_one_automatic_rework() -> None:
    major = merge_validation_findings(
        (
            _sourced(
                FindingOrigin.INDEPENDENT_EXECUTION,
                source_ref="validation.independent.001",
            ),
        )
    )

    first = evaluate_validation_gate(major, rework_attempts=0)
    second = evaluate_validation_gate(major, rework_attempts=1)

    assert first.disposition is GateDisposition.AUTO_REWORK
    assert second.disposition is GateDisposition.HUMAN_REVIEW


def test_gate_policy_never_auto_passes_critical_or_disputed_findings() -> None:
    critical = merge_validation_findings(
        (
            _sourced(
                FindingOrigin.DETERMINISTIC,
                source_ref="validation.deterministic.001",
                finding=_finding(severity=FindingSeverity.CRITICAL),
            ),
        )
    )
    minor = merge_validation_findings(
        (
            _sourced(
                FindingOrigin.LLM_VALIDATOR,
                source_ref="validation.llm.001",
                finding=_finding(severity=FindingSeverity.MINOR),
            ),
        )
    )

    assert (
        evaluate_validation_gate(critical).disposition
        is GateDisposition.HUMAN_REVIEW
    )
    assert (
        evaluate_validation_gate(
            minor,
            disputed_finding_ids=(minor[0].finding_id,),
        ).disposition
        is GateDisposition.HUMAN_REVIEW
    )
    assert (
        evaluate_validation_gate(minor).disposition
        is GateDisposition.PASS_WITH_FINDINGS
    )
    assert evaluate_validation_gate(()).disposition is GateDisposition.PASS


def test_gate_policy_rejects_unknown_dispute_and_unbounded_rework() -> None:
    findings = merge_validation_findings(
        (
            _sourced(
                FindingOrigin.DETERMINISTIC,
                source_ref="validation.deterministic.001",
            ),
        )
    )
    with pytest.raises(ValidationPolicyError, match="unknown"):
        evaluate_validation_gate(
            findings,
            disputed_finding_ids=("finding.unknown.001",),
        )
    with pytest.raises(ValidationPolicyError, match="0 or 1"):
        evaluate_validation_gate(findings, rework_attempts=2)
