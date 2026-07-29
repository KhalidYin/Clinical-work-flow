"""Fail-closed validation merge, failure diagnosis, and stage gate policy.

The policy keeps deterministic and independent validation evidence authoritative.
LLM findings may add evidence or raise severity, but they cannot lower an existing
finding.  Automatic rework is bounded to one attempt; unresolved high-risk or
disputed findings require the existing human Review Protocol.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from .agent_backend import FindingSeverity, ValidationFinding
from .pipeline_contract import StrictContractModel


IDENTIFIER_PATTERN = r"^[a-z][a-z0-9._-]{2,127}$"
_SEVERITY_RANK = {
    FindingSeverity.INFO: 0,
    FindingSeverity.MINOR: 1,
    FindingSeverity.MAJOR: 2,
    FindingSeverity.CRITICAL: 3,
}


class ValidationPolicyError(ValueError):
    """Validation evidence cannot be merged or evaluated safely."""


class FindingOrigin(StrEnum):
    DETERMINISTIC = "deterministic"
    INDEPENDENT_EXECUTION = "independent_execution"
    LLM_VALIDATOR = "llm_validator"


class FailureCategory(StrEnum):
    KNOWLEDGE_COVERAGE_GAP = "knowledge_coverage_gap"
    RETRIEVAL_SELECTION_FAILURE = "retrieval_selection_failure"
    MODEL_APPLICATION_FAILURE = "model_application_failure"
    TOOL_OR_CONTRACT_FAILURE = "tool_or_contract_failure"
    STUDY_EVIDENCE_GAP = "study_evidence_gap"
    AMBIGUOUS_FAILURE = "ambiguous_failure"


class GateDisposition(StrEnum):
    PASS = "pass"
    PASS_WITH_FINDINGS = "pass_with_findings"
    AUTO_REWORK = "auto_rework"
    HUMAN_REVIEW = "human_review"


class SourcedFinding(StrictContractModel):
    origin: FindingOrigin
    source_ref: str = Field(pattern=IDENTIFIER_PATTERN)
    finding: ValidationFinding


class MergedFinding(StrictContractModel):
    finding_id: str = Field(pattern=IDENTIFIER_PATTERN)
    severity: FindingSeverity
    category: str = Field(pattern=IDENTIFIER_PATTERN)
    statement: str = Field(min_length=1, max_length=1000)
    artifact_id: str = Field(pattern=IDENTIFIER_PATTERN)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    proposed_correction: str | None = Field(default=None, max_length=1000)
    origins: tuple[FindingOrigin, ...] = Field(min_length=1)
    source_refs: tuple[str, ...] = Field(min_length=1)

    @field_validator("evidence_refs", "origins", "source_refs")
    @classmethod
    def reject_duplicates(cls, value: tuple[object, ...]) -> tuple[object, ...]:
        if len(value) != len(set(value)):
            raise ValueError("merged finding lists must not contain duplicates")
        return value


class FailureDiagnosis(StrictContractModel):
    diagnosis_id: str = Field(pattern=IDENTIFIER_PATTERN)
    failure_ref: str = Field(pattern=IDENTIFIER_PATTERN)
    category: FailureCategory
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    rationale: str = Field(min_length=1, max_length=2000)
    knowledge_usage_ref: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    candidate_eligible: bool
    requires_human_confirmation: bool

    @model_validator(mode="after")
    def derive_governance_flags_from_category(self) -> Self:
        expected_candidate = self.category is FailureCategory.KNOWLEDGE_COVERAGE_GAP
        if self.candidate_eligible is not expected_candidate:
            raise ValueError(
                "candidate_eligible is true only for knowledge_coverage_gap"
            )
        expected_confirmation = self.category is FailureCategory.AMBIGUOUS_FAILURE
        if self.requires_human_confirmation is not expected_confirmation:
            raise ValueError(
                "requires_human_confirmation is true only for ambiguous_failure"
            )
        return self


class GateDecision(StrictContractModel):
    disposition: GateDisposition
    max_severity: FindingSeverity | None
    finding_ids: tuple[str, ...]
    disputed_finding_ids: tuple[str, ...] = ()
    rework_attempts: int = Field(ge=0, le=1)
    reason_codes: tuple[str, ...] = Field(min_length=1)

    @field_validator("finding_ids", "disputed_finding_ids", "reason_codes")
    @classmethod
    def reject_duplicates(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("gate decision lists must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_disposition_shape(self) -> Self:
        if self.disposition is GateDisposition.PASS:
            if self.finding_ids or self.max_severity is not None:
                raise ValueError("pass requires no findings")
        elif not self.finding_ids or self.max_severity is None:
            raise ValueError("non-pass decisions require findings and max_severity")
        if not set(self.disputed_finding_ids).issubset(self.finding_ids):
            raise ValueError("disputed findings must be present in finding_ids")
        if (
            self.disposition is GateDisposition.AUTO_REWORK
            and self.rework_attempts != 0
        ):
            raise ValueError("automatic rework is allowed only before the first attempt")
        return self


def merge_validation_findings(
    findings: tuple[SourcedFinding, ...],
) -> tuple[MergedFinding, ...]:
    """Merge findings by stable ID without allowing severity downgrades."""

    grouped: dict[str, list[SourcedFinding]] = {}
    seen_sources: set[tuple[str, FindingOrigin, str]] = set()
    for sourced in findings:
        source_key = (
            sourced.finding.finding_id,
            sourced.origin,
            sourced.source_ref,
        )
        if source_key in seen_sources:
            raise ValidationPolicyError(
                f"duplicate validation evidence: {sourced.finding.finding_id}"
            )
        seen_sources.add(source_key)
        grouped.setdefault(sourced.finding.finding_id, []).append(sourced)

    merged: list[MergedFinding] = []
    origin_order = {
        FindingOrigin.DETERMINISTIC: 0,
        FindingOrigin.INDEPENDENT_EXECUTION: 1,
        FindingOrigin.LLM_VALIDATOR: 2,
    }
    for finding_id in sorted(grouped):
        group = grouped[finding_id]
        categories = {item.finding.category for item in group}
        artifacts = {item.finding.artifact_id for item in group}
        if len(categories) != 1 or len(artifacts) != 1:
            raise ValidationPolicyError(
                f"finding {finding_id} has conflicting category or artifact identity"
            )
        authoritative = min(
            group,
            key=lambda item: (
                -_SEVERITY_RANK[item.finding.severity],
                origin_order[item.origin],
                item.source_ref,
            ),
        )
        evidence_refs = tuple(
            dict.fromkeys(
                evidence
                for item in sorted(
                    group,
                    key=lambda value: (
                        origin_order[value.origin],
                        value.source_ref,
                    ),
                )
                for evidence in item.finding.evidence_refs
            )
        )
        origins = tuple(
            sorted({item.origin for item in group}, key=origin_order.__getitem__)
        )
        source_refs = tuple(sorted({item.source_ref for item in group}))
        merged.append(
            MergedFinding(
                finding_id=finding_id,
                severity=authoritative.finding.severity,
                category=authoritative.finding.category,
                statement=authoritative.finding.statement,
                artifact_id=authoritative.finding.artifact_id,
                evidence_refs=evidence_refs,
                proposed_correction=authoritative.finding.proposed_correction,
                origins=origins,
                source_refs=source_refs,
            )
        )
    return tuple(merged)


def evaluate_validation_gate(
    findings: tuple[MergedFinding, ...],
    *,
    rework_attempts: int = 0,
    disputed_finding_ids: tuple[str, ...] = (),
) -> GateDecision:
    """Return a deterministic gate decision with at most one automatic rework."""

    if rework_attempts not in {0, 1}:
        raise ValidationPolicyError("rework_attempts must be 0 or 1")
    finding_ids = tuple(item.finding_id for item in findings)
    if len(finding_ids) != len(set(finding_ids)):
        raise ValidationPolicyError("merged finding IDs must be unique")
    unknown_disputes = set(disputed_finding_ids) - set(finding_ids)
    if unknown_disputes:
        raise ValidationPolicyError(
            f"disputed findings are unknown: {sorted(unknown_disputes)}"
        )
    if not findings:
        return GateDecision(
            disposition=GateDisposition.PASS,
            max_severity=None,
            finding_ids=(),
            disputed_finding_ids=(),
            rework_attempts=rework_attempts,
            reason_codes=("no_findings",),
        )

    max_severity = max(
        (item.severity for item in findings),
        key=_SEVERITY_RANK.__getitem__,
    )
    normalized_disputes = tuple(sorted(set(disputed_finding_ids)))
    if normalized_disputes:
        disposition = GateDisposition.HUMAN_REVIEW
        reason_codes = ("validator_dispute",)
    elif max_severity is FindingSeverity.CRITICAL:
        disposition = GateDisposition.HUMAN_REVIEW
        reason_codes = ("critical_finding",)
    elif max_severity is FindingSeverity.MAJOR and rework_attempts == 0:
        disposition = GateDisposition.AUTO_REWORK
        reason_codes = ("major_finding_first_attempt",)
    elif max_severity is FindingSeverity.MAJOR:
        disposition = GateDisposition.HUMAN_REVIEW
        reason_codes = ("major_finding_after_rework",)
    else:
        disposition = GateDisposition.PASS_WITH_FINDINGS
        reason_codes = ("minor_or_info_findings",)
    return GateDecision(
        disposition=disposition,
        max_severity=max_severity,
        finding_ids=finding_ids,
        disputed_finding_ids=normalized_disputes,
        rework_attempts=rework_attempts,
        reason_codes=reason_codes,
    )
