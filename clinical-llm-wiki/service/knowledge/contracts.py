"""Strict contracts for evidence-backed candidate and revision governance."""

from __future__ import annotations

from enum import Enum
from hashlib import sha256
import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

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


class CandidateAdvisorySignalType(str, Enum):
    POSSIBLE_DUPLICATE = "possible_duplicate"
    POSSIBLE_CONFLICT = "possible_conflict"
    EXPLICIT_GAP = "explicit_gap"


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


class CandidateAdvisorySignal(StrictKnowledgeModel):
    signal_type: CandidateAdvisorySignalType
    description: str = Field(min_length=1, max_length=2000)
    target_knowledge_unit_id: str | None = Field(default=None, max_length=160)
    evidence_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_target_shape(self) -> "CandidateAdvisorySignal":
        if not self.description.strip():
            raise ValueError("advisory signal description must contain non-whitespace text")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("advisory signal evidence IDs must be unique")
        if self.signal_type is CandidateAdvisorySignalType.EXPLICIT_GAP:
            if self.target_knowledge_unit_id is not None:
                raise ValueError("explicit_gap must not identify a knowledge unit")
        elif not self.target_knowledge_unit_id:
            raise ValueError(f"{self.signal_type.value} requires a target knowledge unit")
        return self


class RelationEdgeFact(StrictKnowledgeModel):
    source_knowledge_unit_id: str = Field(min_length=1, max_length=160)
    relation_type: RelationType
    target_knowledge_unit_id: str = Field(min_length=1, max_length=160)


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
    advisory_signals: tuple[CandidateAdvisorySignal, ...] = ()
    origin_model_invocation_id: str | None = Field(default=None, max_length=160)
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
        proposal_keys: set[tuple[RelationType, str]] = set()
        for proposal in self.relation_proposals:
            if len(set(proposal.evidence_ids)) != len(proposal.evidence_ids):
                raise ValueError("relation edge evidence IDs must be unique")
            unknown = set(proposal.evidence_ids) - candidate_evidence
            if unknown:
                raise ValueError("relation edge evidence must belong to the candidate")
            key = (proposal.relation_type, proposal.target_knowledge_unit_id)
            if key in proposal_keys:
                raise ValueError("candidate relation proposals must be unique")
            proposal_keys.add(key)
        signal_keys: set[tuple[CandidateAdvisorySignalType, str | None]] = set()
        for signal in self.advisory_signals:
            unknown = set(signal.evidence_ids) - candidate_evidence
            if unknown:
                raise ValueError("advisory signal evidence must belong to the candidate")
            key = (signal.signal_type, signal.target_knowledge_unit_id)
            if key in signal_keys:
                raise ValueError("candidate advisory signals must be unique")
            signal_keys.add(key)
        conflict_targets = {
            signal.target_knowledge_unit_id
            for signal in self.advisory_signals
            if signal.signal_type is CandidateAdvisorySignalType.POSSIBLE_CONFLICT
        }
        duplicate_targets = {
            signal.target_knowledge_unit_id
            for signal in self.advisory_signals
            if signal.signal_type is CandidateAdvisorySignalType.POSSIBLE_DUPLICATE
        }
        relation_conflict_targets = {
            proposal.target_knowledge_unit_id
            for proposal in self.relation_proposals
            if proposal.relation_type is RelationType.CONFLICTS_WITH
        }
        if conflict_targets != relation_conflict_targets:
            raise ValueError(
                "possible_conflict signals and conflicts_with proposals must match"
            )
        supersedes_targets = {
            proposal.target_knowledge_unit_id
            for proposal in self.relation_proposals
            if proposal.relation_type is RelationType.SUPERSEDES
        }
        if not supersedes_targets <= duplicate_targets:
            raise ValueError("supersedes proposals require possible_duplicate signals")
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
    """Hash governed content, excluding provenance and advisory model suggestions."""

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


ACYCLIC_RELATION_TYPES = frozenset(
    {
        RelationType.DEPENDS_ON,
        RelationType.DERIVED_FROM,
        RelationType.SUPERSEDES,
    }
)


def knowledge_unit_id_for_candidate_group(candidate_group_id: str) -> str:
    return f"ku-{uuid5(NAMESPACE_URL, candidate_group_id).hex}"


def validate_candidate_relation_semantics(
    draft: KnowledgeCandidateDraft,
    *,
    existing_relations: tuple[RelationEdgeFact, ...],
    governed_knowledge_unit_ids: frozenset[str],
) -> None:
    """Validate typed relation meaning without trusting model confidence."""

    source_id = knowledge_unit_id_for_candidate_group(draft.candidate_group_id)
    proposed = tuple(
        RelationEdgeFact(
            source_knowledge_unit_id=source_id,
            relation_type=proposal.relation_type,
            target_knowledge_unit_id=proposal.target_knowledge_unit_id,
        )
        for proposal in draft.relation_proposals
    )
    for edge in proposed:
        if edge.source_knowledge_unit_id == edge.target_knowledge_unit_id:
            raise ValueError("candidate relation cannot target its own knowledge unit")
        if (
            edge.relation_type is RelationType.SUPERSEDES
            and edge.target_knowledge_unit_id not in governed_knowledge_unit_ids
        ):
            raise ValueError("supersedes target must have a governed revision")

    types_by_target: dict[str, set[RelationType]] = {}
    for edge in proposed:
        types_by_target.setdefault(edge.target_knowledge_unit_id, set()).add(
            edge.relation_type
        )
    for relation_types in types_by_target.values():
        if RelationType.SUPPORTS in relation_types and relation_types.intersection(
            {RelationType.CONFLICTS_WITH, RelationType.SUPERSEDES}
        ):
            raise ValueError(
                "supports cannot coexist with conflicts_with or supersedes for one target"
            )

    # A candidate revision replaces its own prior outgoing proposal set. Incoming
    # edges remain relevant to cycle detection.
    retained_existing = tuple(
        edge
        for edge in existing_relations
        if edge.source_knowledge_unit_id != source_id
    )
    for edge in proposed:
        if edge.relation_type is not RelationType.CONFLICTS_WITH:
            continue
        if any(
            existing.relation_type is RelationType.CONFLICTS_WITH
            and existing.source_knowledge_unit_id == edge.target_knowledge_unit_id
            and existing.target_knowledge_unit_id == source_id
            for existing in retained_existing
        ):
            raise ValueError("conflicts_with edge is already represented in reverse")

    for relation_type in ACYCLIC_RELATION_TYPES:
        edges = {
            (edge.source_knowledge_unit_id, edge.target_knowledge_unit_id)
            for edge in (*retained_existing, *proposed)
            if edge.relation_type is relation_type
        }
        proposed_pairs = {
            (edge.source_knowledge_unit_id, edge.target_knowledge_unit_id)
            for edge in proposed
            if edge.relation_type is relation_type
        }
        for source, target in proposed_pairs:
            without_current = edges - {(source, target)}
            if _path_exists(target, source, without_current):
                raise ValueError(f"{relation_type.value} proposal creates a cycle")
            if _path_exists(source, target, without_current):
                raise ValueError(
                    f"{relation_type.value} proposal duplicates transitive closure"
                )


def _path_exists(source: str, target: str, edges: set[tuple[str, str]]) -> bool:
    adjacency: dict[str, set[str]] = {}
    for edge_source, edge_target in edges:
        adjacency.setdefault(edge_source, set()).add(edge_target)
    pending = list(adjacency.get(source, ()))
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(adjacency.get(current, ()))
    return False


def require_revision_mutable(revision: KnowledgeRevisionRecord) -> None:
    if revision.status is KnowledgeRevisionStatus.RELEASED:
        raise ReleasedRevisionImmutableError(
            "released revision is immutable; supersede or retire it with a new governance fact"
        )
