"""PostgreSQL adapter for atomic candidate and two-person governance writes."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from service.db.models import (
    AuditEvent,
    CandidateEvidence,
    CandidateRelationProposal,
    Evidence,
    KnowledgeCandidate,
    KnowledgeRevision,
    KnowledgeUnit,
    ProcessingRun,
    RelationProposalEvidence,
    ReviewDecision,
    SourceVersion,
)
from service.knowledge import (
    CandidateStatus,
    EvidenceReference,
    KnowledgeCandidateRecord,
    KnowledgeRevisionRecord,
    KnowledgeRevisionStatus,
    RelationProposal,
    ReviewOutcome,
)

from .service import (
    CandidateEligibilityError,
    CandidateNotFoundError,
    DuplicateDecisionError,
    InvalidGovernanceTransitionError,
    RevisionNotFoundError,
    StaleRevisionError,
)


class SqlAlchemyGovernanceRepository:
    """Keep each business transition in one explicit database transaction."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def run_status(self, run_id: str) -> str | None:
        with self._session_factory() as session:
            return session.scalar(
                select(ProcessingRun.status).where(ProcessingRun.run_id == run_id)
            )

    def evidence_exists(self, evidence_id: str) -> bool:
        with self._session_factory() as session:
            return (
                session.scalar(
                    select(Evidence.evidence_id).where(Evidence.evidence_id == evidence_id)
                )
                is not None
            )

    def knowledge_unit_exists(self, knowledge_unit_id: str) -> bool:
        with self._session_factory() as session:
            return session.get(KnowledgeUnit, knowledge_unit_id) is not None

    def get_candidate(self, candidate_id: str) -> KnowledgeCandidateRecord | None:
        with self._session_factory() as session:
            candidate = session.get(KnowledgeCandidate, candidate_id)
            if candidate is None:
                return None
            return _candidate_record(session, candidate)

    def get_revision(self, revision_id: str) -> KnowledgeRevisionRecord | None:
        with self._session_factory() as session:
            revision = session.get(KnowledgeRevision, revision_id)
            if revision is None:
                return None
            candidate = session.get(KnowledgeCandidate, revision.candidate_id)
            if (
                candidate is None
                or revision.author_actor_id is None
                or revision.applicability is None
            ):
                raise InvalidGovernanceTransitionError(
                    "revision lacks canonical author or applicability facts"
                )
            return _revision_record(revision, author_actor_id=revision.author_actor_id)

    def decision_exists(self, *, actor_id: str, idempotency_key: str) -> bool:
        with self._session_factory() as session:
            return (
                session.scalar(
                    select(ReviewDecision.decision_id).where(
                        ReviewDecision.actor_subject == actor_id,
                        ReviewDecision.idempotency_key == idempotency_key,
                    )
                )
                is not None
            )

    def create_candidate(
        self,
        *,
        candidate: KnowledgeCandidateRecord,
        actor_id: str,
    ) -> None:
        with self._session_factory.begin() as session:
            run = session.scalar(
                select(ProcessingRun)
                .where(ProcessingRun.run_id == candidate.run_id)
                .with_for_update()
            )
            if run is None or run.status not in {"evidence_ready", "processing"}:
                raise InvalidGovernanceTransitionError("run is not eligible for enrichment")
            if session.get(KnowledgeCandidate, candidate.candidate_id) is not None:
                raise InvalidGovernanceTransitionError("candidate revision already exists")
            self._validate_candidate_facts(session, run=run, candidate=candidate)

            session.add(
                KnowledgeCandidate(
                    candidate_id=candidate.candidate_id,
                    candidate_group_id=candidate.candidate_group_id,
                    parent_candidate_id=candidate.parent_candidate_id,
                    run_id=candidate.run_id,
                    revision_number=candidate.revision_number,
                    status=candidate.status.value,
                    knowledge_type=candidate.knowledge_type,
                    claim=candidate.claim,
                    scope=candidate.scope,
                    applicability=candidate.applicability,
                    conditions=list(candidate.conditions),
                    exceptions=list(candidate.exceptions),
                    confidence=candidate.confidence,
                    content_sha256=candidate.content_sha256,
                    author_actor_id=None,
                    author_subject=None,
                )
            )
            session.flush()
            for reference in candidate.evidence:
                session.add(
                    CandidateEvidence(
                        candidate_id=candidate.candidate_id,
                        evidence_id=reference.evidence_id,
                        evidence_role="supports",
                    )
                )
            for proposal in candidate.relation_proposals:
                proposal_id = _stable_id(
                    "relprop",
                    f"{candidate.candidate_id}:{proposal.relation_type.value}:"
                    f"{proposal.target_knowledge_unit_id}",
                )
                session.add(
                    CandidateRelationProposal(
                        proposal_id=proposal_id,
                        candidate_id=candidate.candidate_id,
                        relation_type=proposal.relation_type.value,
                        target_knowledge_unit_id=proposal.target_knowledge_unit_id,
                        status="proposed",
                    )
                )
                for evidence_id in proposal.evidence_ids:
                    session.add(
                        RelationProposalEvidence(
                            proposal_id=proposal_id,
                            evidence_id=evidence_id,
                        )
                    )
            run.status = "author_confirmation_required"
            run.updated_at = datetime.now(timezone.utc)
            session.add(
                _audit_event(
                    actor_id=actor_id,
                    action="candidate.created",
                    entity_type="knowledge_candidate",
                    entity_id=candidate.candidate_id,
                    run_id=candidate.run_id,
                    details={
                        "candidate_group_id": candidate.candidate_group_id,
                        "revision_number": candidate.revision_number,
                        "content_sha256": candidate.content_sha256,
                        "permission": "candidate:write",
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
        with self._session_factory.begin() as session:
            stored = session.scalar(
                select(KnowledgeCandidate)
                .where(KnowledgeCandidate.candidate_id == parent.candidate_id)
                .with_for_update()
            )
            if stored is None:
                raise CandidateNotFoundError(parent.candidate_id)
            _reject_stale_candidate(stored, parent)
            run = session.scalar(
                select(ProcessingRun)
                .where(ProcessingRun.run_id == parent.run_id)
                .with_for_update()
            )
            if run is None:
                raise InvalidGovernanceTransitionError("processing run does not exist")
            if stored.status == CandidateStatus.AUTHOR_CONFIRMED.value:
                revision = session.scalar(
                    select(KnowledgeRevision).where(
                        KnowledgeRevision.candidate_id == stored.candidate_id
                    )
                )
                if (
                    revision is None
                    or revision.status != KnowledgeRevisionStatus.CHANGES_REQUESTED.value
                    or run.status != "evidence_ready"
                ):
                    raise InvalidGovernanceTransitionError(
                        "confirmed candidate has no current change request"
                    )
            elif (
                stored.status != CandidateStatus.AUTHOR_CONFIRMATION_REQUIRED.value
                or run.status != "author_confirmation_required"
            ):
                raise InvalidGovernanceTransitionError("candidate cannot be revised")
            if session.get(KnowledgeCandidate, candidate.candidate_id) is not None:
                raise InvalidGovernanceTransitionError("candidate revision already exists")
            self._validate_candidate_facts(session, run=run, candidate=candidate)

            stored.status = CandidateStatus.SUPERSEDED.value
            session.add(
                KnowledgeCandidate(
                    candidate_id=candidate.candidate_id,
                    candidate_group_id=candidate.candidate_group_id,
                    parent_candidate_id=parent.candidate_id,
                    run_id=candidate.run_id,
                    revision_number=candidate.revision_number,
                    status=candidate.status.value,
                    knowledge_type=candidate.knowledge_type,
                    claim=candidate.claim,
                    scope=candidate.scope,
                    applicability=candidate.applicability,
                    conditions=list(candidate.conditions),
                    exceptions=list(candidate.exceptions),
                    confidence=candidate.confidence,
                    content_sha256=candidate.content_sha256,
                    author_actor_id=None,
                    author_subject=None,
                )
            )
            session.flush()
            for reference in candidate.evidence:
                session.add(
                    CandidateEvidence(
                        candidate_id=candidate.candidate_id,
                        evidence_id=reference.evidence_id,
                        evidence_role="supports",
                    )
                )
            for proposal in candidate.relation_proposals:
                proposal_id = _stable_id(
                    "relprop",
                    f"{candidate.candidate_id}:{proposal.relation_type.value}:"
                    f"{proposal.target_knowledge_unit_id}",
                )
                session.add(
                    CandidateRelationProposal(
                        proposal_id=proposal_id,
                        candidate_id=candidate.candidate_id,
                        relation_type=proposal.relation_type.value,
                        target_knowledge_unit_id=proposal.target_knowledge_unit_id,
                        status="proposed",
                    )
                )
                for evidence_id in proposal.evidence_ids:
                    session.add(
                        RelationProposalEvidence(
                            proposal_id=proposal_id,
                            evidence_id=evidence_id,
                        )
                    )
            run.status = "author_confirmation_required"
            run.updated_at = datetime.now(timezone.utc)
            session.add(
                _audit_event(
                    actor_id=actor_id,
                    action="candidate.revised",
                    entity_type="knowledge_candidate",
                    entity_id=candidate.candidate_id,
                    run_id=candidate.run_id,
                    details={
                        "parent_candidate_id": parent.candidate_id,
                        "revision_number": candidate.revision_number,
                        "permission": "candidate:write",
                        "correlation_id": idempotency_key,
                        "input_sha256": parent.content_sha256,
                        "output_sha256": candidate.content_sha256,
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
        with self._session_factory.begin() as session:
            self._reject_duplicate(
                session,
                actor_id=actor_id,
                idempotency_key=idempotency_key,
            )
            stored = session.scalar(
                select(KnowledgeCandidate)
                .where(KnowledgeCandidate.candidate_id == candidate.candidate_id)
                .with_for_update()
            )
            if stored is None:
                raise CandidateNotFoundError(candidate.candidate_id)
            if stored.status != CandidateStatus.AUTHOR_CONFIRMATION_REQUIRED.value:
                raise InvalidGovernanceTransitionError(
                    "candidate is not awaiting author confirmation"
                )
            _reject_stale_candidate(stored, candidate)
            run = session.scalar(
                select(ProcessingRun).where(ProcessingRun.run_id == stored.run_id).with_for_update()
            )
            if run is None or run.status != "author_confirmation_required":
                raise InvalidGovernanceTransitionError("run is not awaiting author confirmation")

            unit = session.get(KnowledgeUnit, revision.knowledge_unit_id)
            if unit is None:
                unit = KnowledgeUnit(
                    knowledge_unit_id=revision.knowledge_unit_id,
                    stable_key=candidate.candidate_group_id,
                    knowledge_type=candidate.knowledge_type,
                )
                session.add(unit)
                session.flush()
            elif (
                unit.stable_key != candidate.candidate_group_id
                or unit.knowledge_type != candidate.knowledge_type
            ):
                raise InvalidGovernanceTransitionError(
                    "knowledge unit identity conflicts with the candidate"
                )

            stored.status = CandidateStatus.AUTHOR_CONFIRMED.value
            stored.author_actor_id = actor_id
            session.add(
                KnowledgeRevision(
                    knowledge_revision_id=revision.knowledge_revision_id,
                    knowledge_unit_id=revision.knowledge_unit_id,
                    candidate_id=revision.candidate_id,
                    revision_number=revision.revision_number,
                    status=revision.status.value,
                    claim=revision.claim,
                    scope=revision.scope,
                    applicability=revision.applicability,
                    conditions=list(revision.conditions),
                    exceptions=list(revision.exceptions),
                    content_sha256=revision.content_sha256,
                    author_actor_id=actor_id,
                )
            )
            session.add(
                ReviewDecision(
                    decision_id=decision_id,
                    candidate_id=candidate.candidate_id,
                    knowledge_revision_id=None,
                    decision="author_confirmed",
                    candidate_revision_number=candidate.revision_number,
                    content_sha256=candidate.content_sha256,
                    idempotency_key=idempotency_key,
                    actor_subject=actor_id,
                    actor_role="knowledge_curator",
                    rationale=None,
                    invalidated_step_ids=[],
                )
            )
            run.status = "review_required"
            run.updated_at = datetime.now(timezone.utc)
            session.add(
                _audit_event(
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
                        "permission": "candidate:submit",
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
        with self._session_factory.begin() as session:
            self._reject_duplicate(
                session,
                actor_id=actor_id,
                idempotency_key=idempotency_key,
            )
            stored = session.scalar(
                select(KnowledgeRevision)
                .where(KnowledgeRevision.knowledge_revision_id == revision.knowledge_revision_id)
                .with_for_update()
            )
            if stored is None:
                raise RevisionNotFoundError(revision.knowledge_revision_id)
            if stored.status != KnowledgeRevisionStatus.REVIEW_REQUIRED.value:
                raise InvalidGovernanceTransitionError(
                    "knowledge revision is not awaiting independent review"
                )
            _reject_stale_revision(stored, revision)
            candidate = session.get(KnowledgeCandidate, stored.candidate_id)
            if candidate is None:
                raise CandidateNotFoundError(stored.candidate_id)
            run = session.scalar(
                select(ProcessingRun)
                .where(ProcessingRun.run_id == candidate.run_id)
                .with_for_update()
            )
            if run is None or run.status != "review_required":
                raise InvalidGovernanceTransitionError("run is not awaiting independent review")

            stored.status = decision.value
            if decision is ReviewOutcome.APPROVED:
                stored.approved_at = datetime.now(timezone.utc)
                run.status = "approved"
            else:
                run.status = "evidence_ready"
            run.updated_at = datetime.now(timezone.utc)
            session.add(
                ReviewDecision(
                    decision_id=decision_id,
                    candidate_id=candidate.candidate_id,
                    knowledge_revision_id=stored.knowledge_revision_id,
                    decision=decision.value,
                    candidate_revision_number=stored.revision_number,
                    content_sha256=stored.content_sha256,
                    idempotency_key=idempotency_key,
                    actor_subject=actor_id,
                    actor_role="reviewer",
                    rationale=rationale,
                    invalidated_step_ids=[],
                )
            )
            session.add(
                _audit_event(
                    actor_id=actor_id,
                    action=f"knowledge_revision.{decision.value}",
                    entity_type="knowledge_revision",
                    entity_id=stored.knowledge_revision_id,
                    run_id=candidate.run_id,
                    details={
                        "decision_id": decision_id,
                        "candidate_id": candidate.candidate_id,
                        "revision_number": stored.revision_number,
                        "content_sha256": stored.content_sha256,
                        "rationale": rationale,
                        "permission": "review:decide",
                        "correlation_id": idempotency_key,
                        "input_sha256": stored.content_sha256,
                        "output_sha256": stored.content_sha256,
                        "result": decision.value,
                    },
                )
            )

    def _validate_candidate_facts(
        self,
        session: Session,
        *,
        run: ProcessingRun,
        candidate: KnowledgeCandidateRecord,
    ) -> None:
        for reference in candidate.evidence:
            row = session.execute(
                select(Evidence, SourceVersion)
                .join(
                    SourceVersion,
                    SourceVersion.source_version_id == Evidence.source_version_id,
                )
                .where(Evidence.evidence_id == reference.evidence_id)
            ).one_or_none()
            if row is None:
                raise CandidateEligibilityError(f"evidence {reference.evidence_id} does not exist")
            evidence, source_version = row
            rights = source_version.rights
            if (
                evidence.source_version_id != run.source_version_id
                or evidence.source_version_id != reference.source_version_id
                or evidence.locator != reference.locator
                or evidence.content_sha256 != reference.content_sha256
                or not isinstance(rights, dict)
                or rights != reference.rights.model_dump(mode="json")
                or not rights.get("storage_allowed")
            ):
                raise CandidateEligibilityError(
                    f"evidence {reference.evidence_id} provenance or rights mismatch"
                )
        for proposal in candidate.relation_proposals:
            if session.get(KnowledgeUnit, proposal.target_knowledge_unit_id) is None:
                raise CandidateEligibilityError(
                    f"relation target {proposal.target_knowledge_unit_id} does not exist"
                )

    @staticmethod
    def _reject_duplicate(
        session: Session,
        *,
        actor_id: str,
        idempotency_key: str,
    ) -> None:
        existing = session.scalar(
            select(ReviewDecision.decision_id)
            .where(
                ReviewDecision.actor_subject == actor_id,
                ReviewDecision.idempotency_key == idempotency_key,
            )
            .with_for_update()
        )
        if existing is not None:
            raise DuplicateDecisionError("governance decision already exists")


def _candidate_record(
    session: Session,
    candidate: KnowledgeCandidate,
) -> KnowledgeCandidateRecord:
    if (
        candidate.candidate_group_id is None
        or candidate.content_sha256 is None
        or candidate.applicability is None
    ):
        raise InvalidGovernanceTransitionError(
            "legacy candidate lacks P2-B1 revision or applicability facts"
        )
    evidence_rows = list(
        session.execute(
            select(Evidence, SourceVersion)
            .join(
                CandidateEvidence,
                CandidateEvidence.evidence_id == Evidence.evidence_id,
            )
            .join(
                SourceVersion,
                SourceVersion.source_version_id == Evidence.source_version_id,
            )
            .where(CandidateEvidence.candidate_id == candidate.candidate_id)
            .order_by(Evidence.evidence_id)
        )
    )
    references = tuple(
        EvidenceReference(
            evidence_id=evidence.evidence_id,
            source_version_id=evidence.source_version_id,
            locator=evidence.locator,
            content_sha256=evidence.content_sha256,
            rights=source_version.rights,
        )
        for evidence, source_version in evidence_rows
    )
    proposal_rows = list(
        session.scalars(
            select(CandidateRelationProposal)
            .where(CandidateRelationProposal.candidate_id == candidate.candidate_id)
            .order_by(CandidateRelationProposal.proposal_id)
        )
    )
    proposals: list[RelationProposal] = []
    for proposal in proposal_rows:
        evidence_ids = tuple(
            session.scalars(
                select(RelationProposalEvidence.evidence_id)
                .where(RelationProposalEvidence.proposal_id == proposal.proposal_id)
                .order_by(RelationProposalEvidence.evidence_id)
            )
        )
        proposals.append(
            RelationProposal(
                relation_type=proposal.relation_type,
                target_knowledge_unit_id=proposal.target_knowledge_unit_id,
                evidence_ids=evidence_ids,
            )
        )
    return KnowledgeCandidateRecord(
        candidate_id=candidate.candidate_id,
        candidate_group_id=candidate.candidate_group_id,
        parent_candidate_id=candidate.parent_candidate_id,
        run_id=candidate.run_id,
        revision_number=candidate.revision_number,
        status=candidate.status,
        knowledge_type=candidate.knowledge_type,
        claim=candidate.claim,
        scope=candidate.scope,
        applicability=candidate.applicability,
        conditions=tuple(candidate.conditions),
        exceptions=tuple(candidate.exceptions),
        evidence=references,
        relation_proposals=tuple(proposals),
        confidence=(float(candidate.confidence) if candidate.confidence is not None else None),
        content_sha256=candidate.content_sha256,
        author_actor_id=candidate.author_actor_id,
    )


def _revision_record(
    revision: KnowledgeRevision,
    *,
    author_actor_id: str,
) -> KnowledgeRevisionRecord:
    if revision.applicability is None:
        raise InvalidGovernanceTransitionError("revision has no applicability")
    return KnowledgeRevisionRecord(
        knowledge_revision_id=revision.knowledge_revision_id,
        knowledge_unit_id=revision.knowledge_unit_id,
        candidate_id=revision.candidate_id,
        revision_number=revision.revision_number,
        status=revision.status,
        claim=revision.claim,
        scope=revision.scope,
        applicability=revision.applicability,
        conditions=tuple(revision.conditions),
        exceptions=tuple(revision.exceptions),
        content_sha256=revision.content_sha256,
        author_actor_id=author_actor_id,
    )


def _reject_stale_candidate(
    stored: KnowledgeCandidate,
    candidate: KnowledgeCandidateRecord,
) -> None:
    if (
        stored.revision_number != candidate.revision_number
        or stored.content_sha256 != candidate.content_sha256
    ):
        raise StaleRevisionError("candidate revision or content hash is stale")


def _reject_stale_revision(
    stored: KnowledgeRevision,
    revision: KnowledgeRevisionRecord,
) -> None:
    if (
        stored.revision_number != revision.revision_number
        or stored.content_sha256 != revision.content_sha256
    ):
        raise StaleRevisionError("knowledge revision or content hash is stale")


def _audit_event(
    *,
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    run_id: str,
    details: dict[str, object],
) -> AuditEvent:
    audit_event_id = _stable_id(
        "audit",
        f"{actor_id}:{action}:{entity_type}:{entity_id}:"
        f"{details.get('decision_id', details.get('content_sha256', ''))}",
    )
    return AuditEvent(
        audit_event_id=audit_event_id,
        actor_subject=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        run_id=run_id,
        details=details,
    )


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{uuid5(NAMESPACE_URL, value).hex}"
