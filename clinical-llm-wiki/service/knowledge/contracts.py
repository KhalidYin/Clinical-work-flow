"""Strict contracts for evidence-backed candidate and revision governance."""

from __future__ import annotations

from enum import Enum
from hashlib import sha256
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from service.sources import RightsClassification


class StrictKnowledgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CandidateStatus(str, Enum):
    AUTHOR_CONFIRMATION_REQUIRED = "author_confirmation_required"
    AUTHOR_CONFIRMED = "author_confirmed"
    SUPERSEDED = "superseded"


class KnowledgeRevisionStatus(str, Enum):
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"
    RELEASED = "released"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class ReviewOutcome(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class RelationType(str, Enum):
    APPLIES_TO = "applies_to"
    CONFLICTS_WITH = "conflicts_with"
    DEPENDS_ON = "depends_on"
    DERIVED_FROM = "derived_from"
    SUPERSEDES = "supersedes"
    SUPPORTS = "supports"
    USED_BY = "used_by"


class EvidenceRights(StrictKnowledgeModel):
    classification: RightsClassification
    storage_allowed: bool
    citation_required: bool = True

    @model_validator(mode="after")
    def require_storage_rights(self) -> "EvidenceRights":
        if not self.storage_allowed:
            raise ValueError("evidence rights do not permit storage")
        return self


class EvidenceReference(StrictKnowledgeModel):
    evidence_id: str = Field(min_length=1, max_length=160)
    source_version_id: str = Field(min_length=1, max_length=160)
    locator: dict[str, Any] = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rights: EvidenceRights


class RelationProposal(StrictKnowledgeModel):
    relation_type: RelationType
    target_knowledge_unit_id: str = Field(min_length=1, max_length=160)
    evidence_ids: tuple[str, ...] = Field(min_length=1)


class KnowledgeCandidateDraft(StrictKnowledgeModel):
    candidate_group_id: str = Field(min_length=1, max_length=160)
    parent_candidate_id: str | None = Field(default=None, max_length=160)
    run_id: str = Field(min_length=1, max_length=160)
    revision_number: int = Field(ge=1)
    knowledge_type: str = Field(min_length=1, max_length=100)
    claim: str = Field(min_length=1)
    scope: dict[str, Any] = Field(min_length=1)
    applicability: dict[str, Any] = Field(min_length=1)
    conditions: tuple[dict[str, Any], ...] = ()
    exceptions: tuple[dict[str, Any], ...] = ()
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    relation_proposals: tuple[RelationProposal, ...] = ()
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_edge_evidence(self) -> "KnowledgeCandidateDraft":
        if self.revision_number == 1 and self.parent_candidate_id is not None:
            raise ValueError("first candidate revision cannot have a parent")
        if self.revision_number > 1 and self.parent_candidate_id is None:
            raise ValueError("later candidate revision requires a parent")
        candidate_evidence = {reference.evidence_id for reference in self.evidence}
        if len(candidate_evidence) != len(self.evidence):
            raise ValueError("candidate evidence IDs must be unique")
        for proposal in self.relation_proposals:
            unknown = set(proposal.evidence_ids) - candidate_evidence
            if unknown:
                raise ValueError("relation edge evidence must belong to the candidate")
        return self


class KnowledgeCandidateRecord(KnowledgeCandidateDraft):
    candidate_id: str = Field(min_length=1, max_length=160)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: CandidateStatus
    author_actor_id: str | None = Field(default=None, max_length=160)


class KnowledgeRevisionRecord(StrictKnowledgeModel):
    knowledge_revision_id: str = Field(min_length=1, max_length=160)
    knowledge_unit_id: str = Field(min_length=1, max_length=160)
    candidate_id: str = Field(min_length=1, max_length=160)
    revision_number: int = Field(ge=1)
    status: KnowledgeRevisionStatus
    claim: str = Field(min_length=1)
    scope: dict[str, Any] = Field(min_length=1)
    applicability: dict[str, Any] = Field(min_length=1)
    conditions: tuple[dict[str, Any], ...] = ()
    exceptions: tuple[dict[str, Any], ...] = ()
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    author_actor_id: str = Field(min_length=1, max_length=160)


class AuthorConfirmationCommand(StrictKnowledgeModel):
    candidate_id: str = Field(min_length=1, max_length=160)
    expected_revision_number: int = Field(ge=1)
    expected_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=8, max_length=160)


class ReviewDecisionCommand(StrictKnowledgeModel):
    candidate_id: str = Field(min_length=1, max_length=160)
    knowledge_revision_id: str = Field(min_length=1, max_length=160)
    expected_revision_number: int = Field(ge=1)
    expected_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: ReviewOutcome
    idempotency_key: str = Field(min_length=8, max_length=160)
    rationale: str | None = Field(default=None, max_length=4000)


class CandidateRevisionCommand(StrictKnowledgeModel):
    candidate_id: str = Field(min_length=1, max_length=160)
    expected_revision_number: int = Field(ge=1)
    expected_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    claim: str = Field(min_length=1)
    scope: dict[str, Any] = Field(min_length=1)
    applicability: dict[str, Any] = Field(min_length=1)
    conditions: tuple[dict[str, Any], ...] = ()
    exceptions: tuple[dict[str, Any], ...] = ()
    idempotency_key: str = Field(min_length=8, max_length=160)


class AuthorConfirmationReceipt(StrictKnowledgeModel):
    candidate: KnowledgeCandidateRecord
    revision: KnowledgeRevisionRecord
    decision_id: str


class ReviewDecisionReceipt(StrictKnowledgeModel):
    revision: KnowledgeRevisionRecord
    decision_id: str


class ReleasedRevisionImmutableError(RuntimeError):
    """A released content revision cannot be altered in place."""


def candidate_content_sha256(draft: KnowledgeCandidateDraft) -> str:
    """Hash governed content, excluding run, confidence, and relation suggestions."""

    payload = {
        "applicability": draft.applicability,
        "claim": draft.claim,
        "conditions": list(draft.conditions),
        "evidence": [
            {
                "content_sha256": item.content_sha256,
                "evidence_id": item.evidence_id,
                "source_version_id": item.source_version_id,
                "locator": item.locator,
            }
            for item in draft.evidence
        ],
        "exceptions": list(draft.exceptions),
        "knowledge_type": draft.knowledge_type,
        "scope": draft.scope,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def require_revision_mutable(revision: KnowledgeRevisionRecord) -> None:
    if revision.status is KnowledgeRevisionStatus.RELEASED:
        raise ReleasedRevisionImmutableError(
            "released revision is immutable; supersede or retire it with a new governance fact"
        )
