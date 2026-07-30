"""Fail-closed state transitions for the two human knowledge gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from service.auth import (
    ActorContext,
    AuthorizationError,
    Permission,
    PrincipalType,
    WorkerPool,
    require_independent_review,
    require_permission,
)
from service.knowledge import (
    AuthorConfirmationCommand,
    AuthorConfirmationReceipt,
    CandidateRevisionCommand,
    CandidateStatus,
    KnowledgeCandidateDraft,
    KnowledgeCandidateRecord,
    KnowledgeRevisionRecord,
    KnowledgeRevisionStatus,
    ReviewDecisionCommand,
    ReviewDecisionReceipt,
    ReviewOutcome,
    candidate_content_sha256,
)


class GovernanceError(RuntimeError):
    """Base class for deterministic governance failures."""


class CandidateNotFoundError(GovernanceError):
    """The requested candidate does not exist."""


class RevisionNotFoundError(GovernanceError):
    """The requested knowledge revision does not exist."""


class InvalidGovernanceTransitionError(GovernanceError):
    """The current durable state does not permit the requested transition."""


class StaleRevisionError(GovernanceError):
    """The caller acted on an older revision or content hash."""


class DuplicateDecisionError(GovernanceError):
    """The same governance decision was already submitted."""


class CandidateEligibilityError(GovernanceError):
    """Candidate evidence or relation references are not canonical facts."""


@dataclass(frozen=True, slots=True)
class AuditRecord:
    actor_id: str
    action: str
    entity_type: str
    entity_id: str
    run_id: str
    details: dict[str, object]


class GovernanceRepository(Protocol):
    def run_status(self, run_id: str) -> str | None: ...

    def evidence_exists(self, evidence_id: str) -> bool: ...

    def knowledge_unit_exists(self, knowledge_unit_id: str) -> bool: ...

    def get_candidate(self, candidate_id: str) -> KnowledgeCandidateRecord | None: ...

    def get_revision(self, revision_id: str) -> KnowledgeRevisionRecord | None: ...

    def decision_exists(self, *, actor_id: str, idempotency_key: str) -> bool: ...

    def create_candidate(
        self,
        *,
        candidate: KnowledgeCandidateRecord,
        actor_id: str,
    ) -> None: ...

    def create_candidate_revision(
        self,
        *,
        parent: KnowledgeCandidateRecord,
        candidate: KnowledgeCandidateRecord,
        actor_id: str,
        idempotency_key: str,
    ) -> None: ...

    def confirm_candidate(
        self,
        *,
        candidate: KnowledgeCandidateRecord,
        revision: KnowledgeRevisionRecord,
        actor_id: str,
        idempotency_key: str,
        decision_id: str,
    ) -> None: ...

    def decide_revision(
        self,
        *,
        revision: KnowledgeRevisionRecord,
        actor_id: str,
        idempotency_key: str,
        decision_id: str,
        decision: ReviewOutcome,
        rationale: str | None,
    ) -> None: ...


class KnowledgeGovernanceService:
    def __init__(self, *, repository: GovernanceRepository) -> None:
        self._repository = repository

    def register_candidate(
        self,
        *,
        actor: ActorContext,
        draft: KnowledgeCandidateDraft,
    ) -> KnowledgeCandidateRecord:
        require_permission(actor, Permission.CANDIDATE_WRITE)
        if draft.relation_proposals:
            require_permission(actor, Permission.RELATION_PROPOSE)
        candidate_id = _stable_id(
            "cand",
            f"{draft.candidate_group_id}:{draft.revision_number}",
        )
        existing = self._repository.get_candidate(candidate_id)
        if existing is not None:
            proposed = KnowledgeCandidateRecord(
                **draft.model_dump(),
                candidate_id=candidate_id,
                content_sha256=candidate_content_sha256(draft),
                status=CandidateStatus.AUTHOR_CONFIRMATION_REQUIRED,
            )
            if (
                existing.content_sha256 == proposed.content_sha256
                and existing.run_id == proposed.run_id
            ):
                return existing
            raise InvalidGovernanceTransitionError("candidate revision already exists")
        run_status = self._repository.run_status(draft.run_id)
        if run_status not in {"evidence_ready", "processing"}:
            raise InvalidGovernanceTransitionError(
                "candidate can be registered only from evidence_ready or enrichment processing"
            )
        if run_status == "processing" and (
            actor.principal_type is not PrincipalType.SERVICE_ACCOUNT
            or actor.worker_pool is not WorkerPool.ENRICHMENT
        ):
            raise InvalidGovernanceTransitionError(
                "only the enrichment worker may register during processing"
            )
        for reference in draft.evidence:
            if not self._repository.evidence_exists(reference.evidence_id):
                raise CandidateEligibilityError(
                    f"evidence {reference.evidence_id} is not a canonical fact"
                )
        for proposal in draft.relation_proposals:
            if not self._repository.knowledge_unit_exists(proposal.target_knowledge_unit_id):
                raise CandidateEligibilityError(
                    f"relation target {proposal.target_knowledge_unit_id} does not exist"
                )

        candidate = KnowledgeCandidateRecord(
            **draft.model_dump(),
            candidate_id=candidate_id,
            content_sha256=candidate_content_sha256(draft),
            status=CandidateStatus.AUTHOR_CONFIRMATION_REQUIRED,
        )
        self._repository.create_candidate(candidate=candidate, actor_id=actor.actor_id)
        return candidate

    def revise_candidate(
        self,
        *,
        actor: ActorContext,
        command: CandidateRevisionCommand,
    ) -> KnowledgeCandidateRecord:
        _require_human(actor, Permission.CANDIDATE_WRITE)
        parent = self._repository.get_candidate(command.candidate_id)
        if parent is None:
            raise CandidateNotFoundError(command.candidate_id)
        if (
            parent.revision_number != command.expected_revision_number
            or parent.content_sha256 != command.expected_content_sha256
        ):
            raise StaleRevisionError("candidate revision or content hash is stale")
        if parent.status not in {
            CandidateStatus.AUTHOR_CONFIRMATION_REQUIRED,
            CandidateStatus.AUTHOR_CONFIRMED,
        }:
            raise InvalidGovernanceTransitionError("candidate cannot create another revision")
        draft = KnowledgeCandidateDraft(
            candidate_group_id=parent.candidate_group_id,
            parent_candidate_id=parent.candidate_id,
            run_id=parent.run_id,
            revision_number=parent.revision_number + 1,
            knowledge_type=parent.knowledge_type,
            claim=command.claim,
            scope=command.scope,
            applicability=command.applicability,
            conditions=command.conditions,
            exceptions=command.exceptions,
            evidence=parent.evidence,
            relation_proposals=parent.relation_proposals,
            confidence=parent.confidence,
        )
        candidate = KnowledgeCandidateRecord(
            **draft.model_dump(),
            candidate_id=_stable_id(
                "cand",
                f"{draft.candidate_group_id}:{draft.revision_number}",
            ),
            content_sha256=candidate_content_sha256(draft),
            status=CandidateStatus.AUTHOR_CONFIRMATION_REQUIRED,
        )
        self._repository.create_candidate_revision(
            parent=parent,
            candidate=candidate,
            actor_id=actor.actor_id,
            idempotency_key=command.idempotency_key,
        )
        return candidate

    def confirm_candidate(
        self,
        *,
        actor: ActorContext,
        command: AuthorConfirmationCommand,
    ) -> AuthorConfirmationReceipt:
        _require_human(actor, Permission.CANDIDATE_SUBMIT)
        if self._repository.decision_exists(
            actor_id=actor.actor_id,
            idempotency_key=command.idempotency_key,
        ):
            raise DuplicateDecisionError("author confirmation already exists")
        candidate = self._repository.get_candidate(command.candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(command.candidate_id)
        _require_current_candidate(candidate, command)
        if candidate.status is not CandidateStatus.AUTHOR_CONFIRMATION_REQUIRED:
            raise InvalidGovernanceTransitionError("candidate is not awaiting author confirmation")

        confirmed = candidate.model_copy(
            update={
                "status": CandidateStatus.AUTHOR_CONFIRMED,
                "author_actor_id": actor.actor_id,
            }
        )
        revision = KnowledgeRevisionRecord(
            knowledge_revision_id=_stable_id("krev", candidate.candidate_id),
            knowledge_unit_id=_stable_id("ku", candidate.candidate_group_id),
            candidate_id=candidate.candidate_id,
            revision_number=candidate.revision_number,
            status=KnowledgeRevisionStatus.REVIEW_REQUIRED,
            claim=candidate.claim,
            scope=candidate.scope,
            applicability=candidate.applicability,
            conditions=candidate.conditions,
            exceptions=candidate.exceptions,
            content_sha256=candidate.content_sha256,
            author_actor_id=actor.actor_id,
        )
        decision_id = _stable_id(
            "decision",
            f"{actor.actor_id}:{command.idempotency_key}",
        )
        self._repository.confirm_candidate(
            candidate=confirmed,
            revision=revision,
            actor_id=actor.actor_id,
            idempotency_key=command.idempotency_key,
            decision_id=decision_id,
        )
        return AuthorConfirmationReceipt(
            candidate=confirmed,
            revision=revision,
            decision_id=decision_id,
        )

    def review_revision(
        self,
        *,
        actor: ActorContext,
        command: ReviewDecisionCommand,
    ) -> ReviewDecisionReceipt:
        _require_human(actor, Permission.REVIEW_DECIDE)
        if self._repository.decision_exists(
            actor_id=actor.actor_id,
            idempotency_key=command.idempotency_key,
        ):
            raise DuplicateDecisionError("review decision already exists")
        candidate = self._repository.get_candidate(command.candidate_id)
        if candidate is None:
            raise CandidateNotFoundError(command.candidate_id)
        if candidate.status is CandidateStatus.AUTHOR_CONFIRMATION_REQUIRED:
            raise InvalidGovernanceTransitionError(
                "author confirmation is required before independent review"
            )
        if candidate.author_actor_id is None:
            raise InvalidGovernanceTransitionError("candidate has no confirmed author")
        require_independent_review(actor, author_actor_id=candidate.author_actor_id)

        revision = self._repository.get_revision(command.knowledge_revision_id)
        if revision is None or revision.candidate_id != candidate.candidate_id:
            raise RevisionNotFoundError(command.knowledge_revision_id)
        _require_current_revision(revision, command)
        if revision.status is not KnowledgeRevisionStatus.REVIEW_REQUIRED:
            raise InvalidGovernanceTransitionError(
                "knowledge revision is not awaiting independent review"
            )

        decided = revision.model_copy(
            update={"status": KnowledgeRevisionStatus(command.decision.value)}
        )
        decision_id = _stable_id(
            "decision",
            f"{actor.actor_id}:{command.idempotency_key}",
        )
        self._repository.decide_revision(
            revision=decided,
            actor_id=actor.actor_id,
            idempotency_key=command.idempotency_key,
            decision_id=decision_id,
            decision=command.decision,
            rationale=command.rationale,
        )
        return ReviewDecisionReceipt(revision=decided, decision_id=decision_id)


class InMemoryGovernanceRepository:
    """Deterministic adapter for contract tests and later replay fixtures."""

    def __init__(
        self,
        *,
        runs: dict[str, str] | None = None,
        evidence_ids: set[str] | None = None,
        knowledge_unit_ids: set[str] | None = None,
    ) -> None:
        self._runs = dict(runs or {})
        self._evidence_ids = set(evidence_ids or ())
        self._knowledge_unit_ids = set(knowledge_unit_ids or ())
        self._candidates: dict[str, KnowledgeCandidateRecord] = {}
        self._revisions: dict[str, KnowledgeRevisionRecord] = {}
        self._decisions: set[tuple[str, str]] = set()
        self.audit_events: list[AuditRecord] = []

    @property
    def candidates(self) -> tuple[KnowledgeCandidateRecord, ...]:
        return tuple(self._candidates.values())

    def run_status(self, run_id: str) -> str | None:
        return self._runs.get(run_id)

    def evidence_exists(self, evidence_id: str) -> bool:
        return evidence_id in self._evidence_ids

    def knowledge_unit_exists(self, knowledge_unit_id: str) -> bool:
        return knowledge_unit_id in self._knowledge_unit_ids

    def get_candidate(self, candidate_id: str) -> KnowledgeCandidateRecord | None:
        return self._candidates.get(candidate_id)

    def get_revision(self, revision_id: str) -> KnowledgeRevisionRecord | None:
        return self._revisions.get(revision_id)

    def decision_exists(self, *, actor_id: str, idempotency_key: str) -> bool:
        return (actor_id, idempotency_key) in self._decisions

    def create_candidate(
        self,
        *,
        candidate: KnowledgeCandidateRecord,
        actor_id: str,
    ) -> None:
        if candidate.candidate_id in self._candidates:
            raise InvalidGovernanceTransitionError("candidate revision already exists")
        if self._runs.get(candidate.run_id) not in {"evidence_ready", "processing"}:
            raise InvalidGovernanceTransitionError("run is not eligible for enrichment")
        self._candidates[candidate.candidate_id] = candidate
        self._runs[candidate.run_id] = "author_confirmation_required"
        self.audit_events.append(
            AuditRecord(
                actor_id=actor_id,
                action="candidate.created",
                entity_type="knowledge_candidate",
                entity_id=candidate.candidate_id,
                run_id=candidate.run_id,
                details={
                    "candidate_group_id": candidate.candidate_group_id,
                    "revision_number": candidate.revision_number,
                    "content_sha256": candidate.content_sha256,
                    "permission": Permission.CANDIDATE_WRITE.value,
                    "correlation_id": candidate.run_id,
                    "input_sha256": candidate.evidence[0].content_sha256,
                    "output_sha256": candidate.content_sha256,
                    "result": candidate.status.value,
                },
            )
        )

    def create_candidate_revision(
        self,
        *,
        parent: KnowledgeCandidateRecord,
        candidate: KnowledgeCandidateRecord,
        actor_id: str,
        idempotency_key: str,
    ) -> None:
        current = self._candidates.get(parent.candidate_id)
        if current != parent:
            raise StaleRevisionError("candidate revision or content hash is stale")
        if candidate.candidate_id in self._candidates:
            raise InvalidGovernanceTransitionError("candidate revision already exists")
        if parent.status is CandidateStatus.AUTHOR_CONFIRMED:
            revision = self._revisions.get(_stable_id("krev", parent.candidate_id))
            if revision is None or revision.status is not KnowledgeRevisionStatus.CHANGES_REQUESTED:
                raise InvalidGovernanceTransitionError("confirmed candidate has no change request")
        elif parent.status is not CandidateStatus.AUTHOR_CONFIRMATION_REQUIRED:
            raise InvalidGovernanceTransitionError("candidate cannot be revised")
        self._candidates[parent.candidate_id] = parent.model_copy(
            update={"status": CandidateStatus.SUPERSEDED}
        )
        self._candidates[candidate.candidate_id] = candidate
        self._runs[candidate.run_id] = "author_confirmation_required"
        self._decisions.add((actor_id, idempotency_key))
        self.audit_events.append(
            AuditRecord(
                actor_id=actor_id,
                action="candidate.revised",
                entity_type="knowledge_candidate",
                entity_id=candidate.candidate_id,
                run_id=candidate.run_id,
                details={
                    "parent_candidate_id": parent.candidate_id,
                    "revision_number": candidate.revision_number,
                    "input_sha256": parent.content_sha256,
                    "output_sha256": candidate.content_sha256,
                    "correlation_id": idempotency_key,
                    "permission": Permission.CANDIDATE_WRITE.value,
                    "result": candidate.status.value,
                },
            )
        )

    def confirm_candidate(
        self,
        *,
        candidate: KnowledgeCandidateRecord,
        revision: KnowledgeRevisionRecord,
        actor_id: str,
        idempotency_key: str,
        decision_id: str,
    ) -> None:
        current = self._candidates.get(candidate.candidate_id)
        if current is None:
            raise CandidateNotFoundError(candidate.candidate_id)
        if current.status is not CandidateStatus.AUTHOR_CONFIRMATION_REQUIRED:
            raise InvalidGovernanceTransitionError("candidate is not awaiting author confirmation")
        self._candidates[candidate.candidate_id] = candidate
        self._revisions[revision.knowledge_revision_id] = revision
        self._runs[candidate.run_id] = "review_required"
        self._decisions.add((actor_id, idempotency_key))
        self.audit_events.append(
            AuditRecord(
                actor_id=actor_id,
                action="candidate.author_confirmed",
                entity_type="knowledge_candidate",
                entity_id=candidate.candidate_id,
                run_id=candidate.run_id,
                details={
                    "decision_id": decision_id,
                    "knowledge_revision_id": revision.knowledge_revision_id,
                    "revision_number": revision.revision_number,
                    "content_sha256": revision.content_sha256,
                    "permission": Permission.CANDIDATE_SUBMIT.value,
                    "correlation_id": idempotency_key,
                    "input_sha256": candidate.content_sha256,
                    "output_sha256": revision.content_sha256,
                    "result": revision.status.value,
                },
            )
        )

    def decide_revision(
        self,
        *,
        revision: KnowledgeRevisionRecord,
        actor_id: str,
        idempotency_key: str,
        decision_id: str,
        decision: ReviewOutcome,
        rationale: str | None,
    ) -> None:
        current = self._revisions.get(revision.knowledge_revision_id)
        if current is None:
            raise RevisionNotFoundError(revision.knowledge_revision_id)
        if current.status is not KnowledgeRevisionStatus.REVIEW_REQUIRED:
            raise InvalidGovernanceTransitionError(
                "knowledge revision is not awaiting independent review"
            )
        candidate = self._candidates[revision.candidate_id]
        self._revisions[revision.knowledge_revision_id] = revision
        self._runs[candidate.run_id] = (
            "approved" if decision is ReviewOutcome.APPROVED else "evidence_ready"
        )
        self._decisions.add((actor_id, idempotency_key))
        self.audit_events.append(
            AuditRecord(
                actor_id=actor_id,
                action=f"knowledge_revision.{decision.value}",
                entity_type="knowledge_revision",
                entity_id=revision.knowledge_revision_id,
                run_id=candidate.run_id,
                details={
                    "decision_id": decision_id,
                    "candidate_id": candidate.candidate_id,
                    "revision_number": revision.revision_number,
                    "content_sha256": revision.content_sha256,
                    "rationale": rationale,
                    "permission": Permission.REVIEW_DECIDE.value,
                    "correlation_id": idempotency_key,
                    "input_sha256": revision.content_sha256,
                    "output_sha256": revision.content_sha256,
                    "result": decision.value,
                },
            )
        )


def _require_human(actor: ActorContext, permission: Permission) -> None:
    if actor.principal_type is not PrincipalType.HUMAN:
        raise AuthorizationError("governance decisions require a human actor")
    require_permission(actor, permission)


def _require_current_candidate(
    candidate: KnowledgeCandidateRecord,
    command: AuthorConfirmationCommand,
) -> None:
    if (
        candidate.revision_number != command.expected_revision_number
        or candidate.content_sha256 != command.expected_content_sha256
    ):
        raise StaleRevisionError("candidate revision or content hash is stale")


def _require_current_revision(
    revision: KnowledgeRevisionRecord,
    command: ReviewDecisionCommand,
) -> None:
    if (
        revision.revision_number != command.expected_revision_number
        or revision.content_sha256 != command.expected_content_sha256
    ):
        raise StaleRevisionError("knowledge revision or content hash is stale")


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{uuid5(NAMESPACE_URL, value).hex}"
