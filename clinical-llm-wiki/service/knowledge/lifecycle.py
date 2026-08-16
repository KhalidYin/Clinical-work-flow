"""Strict P17 contracts for derived retrieval chunks and knowledge rotation."""

from __future__ import annotations

from enum import Enum
import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictLifecycleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ChunkProfileContract(StrictLifecycleModel):
    chunk_profile_id: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=120)
    tokenizer_id: str = Field(min_length=1, max_length=240)
    target_min_tokens: int = Field(default=400, gt=0)
    target_max_tokens: int = Field(default=700, gt=0)
    hard_max_tokens: int = Field(default=900, gt=0)
    overlap_tokens: int = Field(default=80, ge=0)
    table_hard_max_tokens: int = Field(default=1200, gt=0)
    format_rules: dict[str, Any] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_token_boundaries(self) -> "ChunkProfileContract":
        if not self.target_min_tokens <= self.target_max_tokens <= self.hard_max_tokens:
            raise ValueError(
                "target_min_tokens <= target_max_tokens <= hard_max_tokens is required"
            )
        if self.overlap_tokens >= self.target_min_tokens:
            raise ValueError("overlap_tokens must be smaller than target_min_tokens")
        if self.table_hard_max_tokens < self.hard_max_tokens:
            raise ValueError("table_hard_max_tokens cannot be smaller than hard_max_tokens")
        return self


class EvidenceChangeType(str, Enum):
    UNCHANGED = "unchanged"
    MOVED = "moved"
    MODIFIED = "modified"
    ADDED = "added"
    REMOVED = "removed"
    RIGHTS_CHANGED = "rights_changed"
    AMBIGUOUS = "ambiguous"


class EvidenceMappingBasis(str, Enum):
    CONTENT_EXACT = "content_exact"
    LOCATOR_EXACT = "locator_exact"
    ORDERED_ALIGNMENT = "ordered_alignment"
    UNMATCHED = "unmatched"
    AMBIGUOUS = "ambiguous"


class EvidenceImpactRecord(StrictLifecycleModel):
    evidence_impact_id: str = Field(min_length=1, max_length=160)
    change_type: EvidenceChangeType
    from_evidence_id: str | None = Field(default=None, max_length=160)
    to_evidence_id: str | None = Field(default=None, max_length=160)
    mapping_basis: EvidenceMappingBasis
    details: dict[str, Any]

    @model_validator(mode="after")
    def validate_mapping_shape(self) -> "EvidenceImpactRecord":
        has_from = self.from_evidence_id is not None
        has_to = self.to_evidence_id is not None
        if self.change_type is EvidenceChangeType.ADDED and (has_from or not has_to):
            raise ValueError("added impact requires only to_evidence_id")
        if self.change_type is EvidenceChangeType.REMOVED and (not has_from or has_to):
            raise ValueError("removed impact requires only from_evidence_id")
        if self.change_type in {
            EvidenceChangeType.UNCHANGED,
            EvidenceChangeType.MOVED,
            EvidenceChangeType.MODIFIED,
            EvidenceChangeType.RIGHTS_CHANGED,
        } and not (has_from and has_to):
            raise ValueError(
                f"{self.change_type.value} impact requires from_evidence_id and to_evidence_id"
            )
        if self.change_type is EvidenceChangeType.AMBIGUOUS and not (has_from or has_to):
            raise ValueError("ambiguous impact requires at least one evidence reference")
        return self


class ImpactAssessmentRecord(StrictLifecycleModel):
    assessment_id: str = Field(min_length=1, max_length=160)
    from_source_version_id: str = Field(min_length=1, max_length=160)
    to_source_version_id: str = Field(min_length=1, max_length=160)
    comparison_profile_version: str = Field(min_length=1, max_length=120)
    impacts: tuple[EvidenceImpactRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_distinct_versions(self) -> "ImpactAssessmentRecord":
        if self.from_source_version_id == self.to_source_version_id:
            raise ValueError("impact assessment requires distinct source versions")
        impact_ids = [impact.evidence_impact_id for impact in self.impacts]
        if len(impact_ids) != len(set(impact_ids)):
            raise ValueError("impact assessment evidence impact IDs must be unique")
        return self


class RotationCaseStatus(str, Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    DECIDED = "decided"
    INCLUDED_IN_RELEASE = "included_in_release"
    CLOSED = "closed"


class RotationOutcome(str, Enum):
    CARRY_FORWARD = "carry_forward"
    REPLACE = "replace"
    RETIRE = "retire"
    NO_ACTION = "no_action"


class RotationCaseRecord(StrictLifecycleModel):
    rotation_case_id: str = Field(min_length=1, max_length=160)
    impact_assessment_id: str = Field(min_length=1, max_length=160)
    knowledge_revision_id: str = Field(min_length=1, max_length=160)
    status: RotationCaseStatus
    proposed_outcome: RotationOutcome | None = None
    proposed_by_actor_id: str | None = Field(default=None, max_length=160)
    case_version: int = Field(ge=1)
    included_release_id: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def validate_release_shape(self) -> "RotationCaseRecord":
        if (
            self.status is RotationCaseStatus.INCLUDED_IN_RELEASE
            and self.included_release_id is None
        ):
            raise ValueError("included_in_release case requires included_release_id")
        if self.status in {RotationCaseStatus.OPEN, RotationCaseStatus.IN_REVIEW}:
            if self.included_release_id is not None:
                raise ValueError("open or in_review case cannot reference a release")
        return self


class RotationDecisionCommand(StrictLifecycleModel):
    rotation_case_id: str = Field(min_length=1, max_length=160)
    expected_case_version: int = Field(ge=1)
    outcome: RotationOutcome
    target_knowledge_revision_id: str | None = Field(default=None, max_length=160)
    idempotency_key: str = Field(min_length=8, max_length=160)
    rationale: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_target_shape(self) -> "RotationDecisionCommand":
        _validate_rotation_target(self.outcome, self.target_knowledge_revision_id)
        return self


class RotationProposalCommand(StrictLifecycleModel):
    rotation_case_id: str = Field(min_length=1, max_length=160)
    expected_case_version: int = Field(ge=1)
    outcome: RotationOutcome
    target_knowledge_revision_id: str | None = Field(default=None, max_length=160)
    idempotency_key: str = Field(min_length=8, max_length=160)
    rationale: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_target_shape(self) -> "RotationProposalCommand":
        _validate_rotation_target(self.outcome, self.target_knowledge_revision_id)
        return self


class RotationDecisionReceipt(StrictLifecycleModel):
    rotation_decision_id: str = Field(min_length=1, max_length=160)
    rotation_case_id: str = Field(min_length=1, max_length=160)
    outcome: RotationOutcome
    expected_case_version: int = Field(ge=1)
    target_knowledge_revision_id: str | None = Field(default=None, max_length=160)
    actor_id: str = Field(min_length=1, max_length=160)
    actor_role: str = Field(min_length=1, max_length=80)
    idempotency_key: str = Field(min_length=8, max_length=160)
    rationale: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def validate_reviewer_and_target(self) -> "RotationDecisionReceipt":
        if self.actor_role != "reviewer":
            raise ValueError("rotation decision receipt actor_role must be reviewer")
        _validate_rotation_target(self.outcome, self.target_knowledge_revision_id)
        return self


class InvalidRotationTransitionError(RuntimeError):
    """The durable rotation case cannot move directly to the requested state."""


class RotationCaseNotFoundError(LookupError):
    """The requested durable rotation case does not exist."""


class StaleRotationCaseError(RuntimeError):
    """The caller's expected case version no longer matches canonical state."""

    def __init__(
        self,
        *,
        rotation_case_id: str,
        expected_case_version: int,
        actual_case_version: int,
    ) -> None:
        super().__init__(
            f"rotation case {rotation_case_id} expected version "
            f"{expected_case_version}, actual {actual_case_version}"
        )
        self.rotation_case_id = rotation_case_id
        self.expected_case_version = expected_case_version
        self.actual_case_version = actual_case_version


_ROTATION_TRANSITIONS = {
    RotationCaseStatus.OPEN: frozenset({RotationCaseStatus.IN_REVIEW}),
    RotationCaseStatus.IN_REVIEW: frozenset({RotationCaseStatus.DECIDED}),
    RotationCaseStatus.DECIDED: frozenset(
        {RotationCaseStatus.INCLUDED_IN_RELEASE, RotationCaseStatus.CLOSED}
    ),
    RotationCaseStatus.INCLUDED_IN_RELEASE: frozenset(),
    RotationCaseStatus.CLOSED: frozenset(),
}


def require_rotation_transition(
    current: RotationCaseStatus,
    target: RotationCaseStatus,
) -> None:
    allowed = _ROTATION_TRANSITIONS[current]
    if target in allowed:
        return
    if not allowed:
        raise InvalidRotationTransitionError(
            f"rotation case state {current.value} is terminal; cannot move to {target.value}"
        )
    raise InvalidRotationTransitionError(
        f"rotation case cannot move from {current.value} to {target.value}"
    )


def retrieval_chunk_identity(
    *,
    profile_version: str,
    source_version_id: str,
    ordinal: int,
    evidence_spans: tuple[tuple[str, int, int, str], ...],
    content_sha256: str,
) -> str:
    """Build a stable chunk ID without introducing a stored profile hash."""

    if not profile_version or not source_version_id:
        raise ValueError("profile_version and source_version_id are required")
    if ordinal < 0:
        raise ValueError("ordinal must be nonnegative")
    if not evidence_spans:
        raise ValueError("at least one evidence span is required")
    if len(content_sha256) != 64 or any(character not in "0123456789abcdef" for character in content_sha256):
        raise ValueError("content_sha256 must be lowercase SHA-256")
    for evidence_id, start_offset, end_offset, span_role in evidence_spans:
        if not evidence_id or start_offset < 0 or end_offset <= start_offset:
            raise ValueError("evidence span requires an ID and increasing nonnegative offsets")
        if span_role not in {"primary", "overlap"}:
            raise ValueError("evidence span role must be primary or overlap")
    canonical = json.dumps(
        {
            "content_sha256": content_sha256,
            "evidence_spans": evidence_spans,
            "ordinal": ordinal,
            "profile_version": profile_version,
            "source_version_id": source_version_id,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"chunk-{uuid5(NAMESPACE_URL, canonical).hex}"


def _validate_rotation_target(
    outcome: RotationOutcome,
    target_knowledge_revision_id: str | None,
) -> None:
    if outcome in {RotationOutcome.CARRY_FORWARD, RotationOutcome.REPLACE}:
        if target_knowledge_revision_id is None:
            raise ValueError(f"{outcome.value} outcome requires a target knowledge revision")
    elif target_knowledge_revision_id is not None:
        raise ValueError(f"{outcome.value} outcome must not include a target knowledge revision")
