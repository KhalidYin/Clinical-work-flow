"""Use-case-driven knowledge growth contracts for P11.

These models describe evidence and governance; they do not write Wiki content,
approve a candidate, or mutate a locked snapshot.  A candidate can be created
only from a confirmed knowledge-coverage diagnosis, and an evolution receipt
must prove that the knowledge snapshot was the only changed evaluation input.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from src.runtime.validation_policy import FailureCategory, FailureDiagnosis

from .models import (
    NonEmptyString,
    RightsStatus,
    SemVerString,
    Sha256,
    StableId,
    StrictContractModel,
    WorkflowStage,
)

RuntimeIdentifier = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9._-]{2,127}$"),
]


class KnowledgeEvolutionError(ValueError):
    """Knowledge growth cannot satisfy the approved governance boundary."""


class KnowledgeChangeType(StrEnum):
    ADD = "add"
    REVISE = "revise"
    RETIRE = "retire"


class EvaluationOutcome(StrEnum):
    FAIL = "fail"
    PASS = "pass"


class KnowledgeUsageEntry(StrictContractModel):
    knowledge_id: StableId
    knowledge_version: SemVerString
    knowledge_sha256: Sha256
    source_ids: tuple[StableId, ...] = Field(min_length=1)
    locator_refs: tuple[NonEmptyString, ...] = Field(min_length=1)
    artifact_refs: tuple[NonEmptyString, ...] = Field(min_length=1)

    @field_validator("source_ids", "locator_refs", "artifact_refs")
    @classmethod
    def reject_duplicates(cls, value: tuple[object, ...]) -> tuple[object, ...]:
        if len(value) != len(set(value)):
            raise ValueError("knowledge usage lists must not contain duplicates")
        return value


class KnowledgeUsageManifest(StrictContractModel):
    manifest_id: StableId
    schema_version: Literal["0.1.0"] = "0.1.0"
    run_id: NonEmptyString
    stage_id: WorkflowStage
    snapshot_id: StableId
    snapshot_sha256: Sha256
    query_id: StableId
    query_sha256: Sha256
    selected_units: tuple[KnowledgeUsageEntry, ...] = ()
    citation_refs: tuple[NonEmptyString, ...] = ()
    explicit_gap_ids: tuple[StableId, ...] = ()

    @field_validator("citation_refs", "explicit_gap_ids")
    @classmethod
    def reject_duplicates(cls, value: tuple[object, ...]) -> tuple[object, ...]:
        if len(value) != len(set(value)):
            raise ValueError("knowledge manifest lists must not contain duplicates")
        return value

    @model_validator(mode="after")
    def require_usage_or_explicit_gap(self) -> Self:
        if not self.selected_units and not self.explicit_gap_ids:
            raise ValueError(
                "knowledge usage manifest requires selected units or explicit gaps"
            )
        if self.selected_units and not self.citation_refs:
            raise ValueError("selected knowledge units require citation_refs")
        return self


class KnowledgeGapReport(StrictContractModel):
    gap_report_id: StableId
    schema_version: Literal["0.1.0"] = "0.1.0"
    usage_manifest_id: StableId
    diagnosis: FailureDiagnosis
    gap_statement: NonEmptyString
    required_scope: tuple[NonEmptyString, ...] = Field(min_length=1)
    evidence_refs: tuple[NonEmptyString, ...] = Field(min_length=1)
    candidate_allowed: bool

    @field_validator("required_scope", "evidence_refs")
    @classmethod
    def reject_duplicates(cls, value: tuple[object, ...]) -> tuple[object, ...]:
        if len(value) != len(set(value)):
            raise ValueError("knowledge gap lists must not contain duplicates")
        return value

    @model_validator(mode="after")
    def align_with_failure_diagnosis(self) -> Self:
        if self.diagnosis.knowledge_usage_ref != self.usage_manifest_id:
            raise ValueError(
                "gap report and failure diagnosis must reference the same usage manifest"
            )
        if self.candidate_allowed is not self.diagnosis.candidate_eligible:
            raise ValueError(
                "candidate_allowed must be derived from the failure diagnosis"
            )
        return self


class EvidenceUnit(StrictContractModel):
    evidence_unit_id: StableId
    source_id: StableId
    source_version: NonEmptyString
    source_sha256: Sha256
    locator_ref: NonEmptyString
    statement: NonEmptyString
    statement_sha256: Sha256
    rights_status: RightsStatus
    allowed_uses: tuple[NonEmptyString, ...] = ()
    derivation_ref: NonEmptyString

    @field_validator("allowed_uses")
    @classmethod
    def reject_duplicate_allowed_uses(
        cls, value: tuple[NonEmptyString, ...]
    ) -> tuple[NonEmptyString, ...]:
        if len(value) != len(set(value)):
            raise ValueError("allowed_uses must not contain duplicates")
        return value


class KnowledgeCandidate(StrictContractModel):
    candidate_id: StableId
    schema_version: Literal["0.1.0"] = "0.1.0"
    status: Literal["proposed"] = "proposed"
    release_scope: Literal["p11-poc-test-only"] = "p11-poc-test-only"
    change_type: KnowledgeChangeType
    gap_report_id: StableId
    diagnosis_id: RuntimeIdentifier
    title: NonEmptyString
    proposed_content: NonEmptyString
    applicability_scope: tuple[NonEmptyString, ...] = Field(min_length=1)
    evidence_units: tuple[EvidenceUnit, ...] = Field(min_length=1)
    supersedes_knowledge_ids: tuple[StableId, ...] = ()

    @field_validator(
        "applicability_scope", "evidence_units", "supersedes_knowledge_ids"
    )
    @classmethod
    def reject_duplicates(cls, value: tuple[object, ...]) -> tuple[object, ...]:
        if len(value) != len(set(value)):
            raise ValueError("knowledge candidate lists must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_change_shape(self) -> Self:
        if (
            self.change_type is KnowledgeChangeType.ADD
            and self.supersedes_knowledge_ids
        ):
            raise ValueError("add candidates cannot supersede existing knowledge")
        if (
            self.change_type in {KnowledgeChangeType.REVISE, KnowledgeChangeType.RETIRE}
            and not self.supersedes_knowledge_ids
        ):
            raise ValueError("revise/retire candidates require superseded knowledge IDs")
        return self


class SnapshotReference(StrictContractModel):
    snapshot_id: StableId
    version: SemVerString
    sha256: Sha256
    parent_snapshot_id: StableId | None = None


class EvaluationResult(StrictContractModel):
    evaluation_id: StableId
    case_id: StableId
    outcome: EvaluationOutcome
    run_input_sha256: Sha256
    model_profile_sha256: Sha256
    prompt_sha256: Sha256
    toolchain_sha256: Sha256
    snapshot: SnapshotReference
    regression_failures: tuple[StableId, ...] = ()

    @field_validator("regression_failures")
    @classmethod
    def reject_duplicate_failures(
        cls, value: tuple[StableId, ...]
    ) -> tuple[StableId, ...]:
        if len(value) != len(set(value)):
            raise ValueError("regression_failures must not contain duplicates")
        return value


class KnowledgeEvolutionReceipt(StrictContractModel):
    receipt_id: StableId
    schema_version: Literal["0.1.0"] = "0.1.0"
    candidate_id: StableId
    review_receipt_ref: NonEmptyString
    before: EvaluationResult
    after: EvaluationResult
    changed_dimensions: tuple[Literal["knowledge_snapshot"], ...] = (
        "knowledge_snapshot",
    )

    @model_validator(mode="after")
    def prove_snapshot_only_causal_change(self) -> Self:
        if self.changed_dimensions != ("knowledge_snapshot",):
            raise ValueError("knowledge snapshot must be the only changed dimension")
        invariant_fields = (
            "case_id",
            "run_input_sha256",
            "model_profile_sha256",
            "prompt_sha256",
            "toolchain_sha256",
        )
        changed = [
            field
            for field in invariant_fields
            if getattr(self.before, field) != getattr(self.after, field)
        ]
        if changed:
            raise ValueError(f"evaluation invariants changed: {changed}")
        if self.before.outcome is not EvaluationOutcome.FAIL:
            raise ValueError("before evaluation must fail")
        if self.after.outcome is not EvaluationOutcome.PASS:
            raise ValueError("after evaluation must pass")
        if (
            self.before.snapshot.snapshot_id == self.after.snapshot.snapshot_id
            or self.before.snapshot.sha256 == self.after.snapshot.sha256
        ):
            raise ValueError("evolution requires a new immutable snapshot")
        if self.after.snapshot.parent_snapshot_id != self.before.snapshot.snapshot_id:
            raise ValueError("new snapshot must name the locked prior snapshot as parent")
        new_regressions = set(self.after.regression_failures) - set(
            self.before.regression_failures
        )
        if new_regressions:
            raise ValueError(
                f"knowledge evolution introduced regression failures: {sorted(new_regressions)}"
            )
        return self


def create_knowledge_candidate(
    *,
    candidate_id: str,
    gap_report: KnowledgeGapReport,
    change_type: KnowledgeChangeType,
    title: str,
    proposed_content: str,
    applicability_scope: tuple[str, ...],
    evidence_units: tuple[EvidenceUnit, ...],
    supersedes_knowledge_ids: tuple[str, ...] = (),
) -> KnowledgeCandidate:
    """Create a proposed test-only candidate from an eligible coverage gap."""

    if (
        gap_report.diagnosis.category
        is not FailureCategory.KNOWLEDGE_COVERAGE_GAP
        or not gap_report.candidate_allowed
    ):
        raise KnowledgeEvolutionError(
            "only knowledge_coverage_gap can create a knowledge candidate"
        )
    if not evidence_units:
        raise KnowledgeEvolutionError("knowledge candidate requires evidence units")
    for evidence in evidence_units:
        rights_allowed = evidence.rights_status is RightsStatus.CLEARED or (
            evidence.rights_status is RightsStatus.RESTRICTED
            and "p11-poc-test-only" in evidence.allowed_uses
        )
        if not rights_allowed:
            raise KnowledgeEvolutionError(
                f"evidence rights do not allow candidate use: {evidence.evidence_unit_id}"
            )
    return KnowledgeCandidate(
        candidate_id=candidate_id,
        change_type=change_type,
        gap_report_id=gap_report.gap_report_id,
        diagnosis_id=gap_report.diagnosis.diagnosis_id,
        title=title,
        proposed_content=proposed_content,
        applicability_scope=applicability_scope,
        evidence_units=evidence_units,
        supersedes_knowledge_ids=supersedes_knowledge_ids,
    )
