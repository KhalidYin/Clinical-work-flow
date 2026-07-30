"""P2-B1 backfill from the legacy Evidence terminal state to evidence_ready."""

from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from service.db.models import Evidence, KnowledgeCandidate, ProcessingRun
from service.db.session import (
    create_database_engine,
    create_session_factory,
    database_url_from_environment,
)


@dataclass(frozen=True)
class RunReadiness:
    run_id: str
    status: str
    evidence_count: int
    candidate_count: int


class LockedReadinessPage(Protocol):
    facts: tuple[RunReadiness, ...]

    def mark_evidence_ready(self, run_ids: tuple[str, ...]) -> int: ...


class EvidenceReadyBackfillRepository(Protocol):
    def locked_page(
        self,
        *,
        batch_size: int,
        after_key: str | None,
    ) -> AbstractContextManager[LockedReadinessPage]: ...


class EvidenceReadyBackfillService:
    def __init__(self, repository: EvidenceReadyBackfillRepository) -> None:
        self._repository = repository

    def run_page(
        self,
        *,
        batch_size: int,
        after_key: str | None,
    ) -> tuple[int, str | None]:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        with self._repository.locked_page(
            batch_size=batch_size,
            after_key=after_key,
        ) as page:
            facts = page.facts
            run_ids = select_evidence_ready_run_ids(facts)
            processed = page.mark_evidence_ready(run_ids) if run_ids else 0
            if processed != len(run_ids):
                raise RuntimeError("evidence-ready backfill lost a locked run")
            next_key = facts[-1].run_id if len(facts) == batch_size else None
        return processed, next_key


class _SqlAlchemyLockedReadinessPage:
    def __init__(
        self,
        session: Session,
        facts: tuple[RunReadiness, ...],
    ) -> None:
        self._session = session
        self.facts = facts

    def mark_evidence_ready(self, run_ids: tuple[str, ...]) -> int:
        result = self._session.execute(
            update(ProcessingRun)
            .where(
                ProcessingRun.run_id.in_(run_ids),
                ProcessingRun.status == "author_confirmation_required",
            )
            .values(status="evidence_ready", updated_at=func.now())
        )
        return int(result.rowcount or 0)


class SqlAlchemyEvidenceReadyBackfillRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @contextmanager
    def locked_page(
        self,
        *,
        batch_size: int,
        after_key: str | None,
    ) -> Iterator[_SqlAlchemyLockedReadinessPage]:
        evidence_count = (
            select(func.count(Evidence.evidence_id))
            .where(Evidence.source_version_id == ProcessingRun.source_version_id)
            .correlate(ProcessingRun)
            .scalar_subquery()
        )
        candidate_count = (
            select(func.count(KnowledgeCandidate.candidate_id))
            .where(KnowledgeCandidate.run_id == ProcessingRun.run_id)
            .correlate(ProcessingRun)
            .scalar_subquery()
        )
        statement = (
            select(
                ProcessingRun.run_id,
                ProcessingRun.status,
                evidence_count.label("evidence_count"),
                candidate_count.label("candidate_count"),
            )
            .where(ProcessingRun.status == "author_confirmation_required")
            .order_by(ProcessingRun.run_id)
            .limit(batch_size)
            .with_for_update(of=ProcessingRun, skip_locked=True)
        )
        if after_key is not None:
            statement = statement.where(ProcessingRun.run_id > after_key)

        with self._session_factory.begin() as session:
            facts = tuple(
                RunReadiness(
                    run_id=row.run_id,
                    status=row.status,
                    evidence_count=int(row.evidence_count),
                    candidate_count=int(row.candidate_count),
                )
                for row in session.execute(statement)
            )
            yield _SqlAlchemyLockedReadinessPage(session, facts)


def select_evidence_ready_run_ids(
    facts: Sequence[RunReadiness],
) -> tuple[str, ...]:
    return tuple(
        fact.run_id
        for fact in facts
        if fact.status == "author_confirmation_required"
        and fact.evidence_count > 0
        and fact.candidate_count == 0
    )


def run_from_environment(
    batch_size: int,
    after_key: str | None,
) -> tuple[int, str | None]:
    engine = create_database_engine(database_url_from_environment())
    try:
        service = EvidenceReadyBackfillService(create_session_repository(engine))
        return service.run_page(batch_size=batch_size, after_key=after_key)
    finally:
        engine.dispose()


def create_session_repository(engine) -> SqlAlchemyEvidenceReadyBackfillRepository:
    return SqlAlchemyEvidenceReadyBackfillRepository(create_session_factory(engine))
