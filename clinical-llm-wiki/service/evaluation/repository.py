"""PostgreSQL authority for immutable P17 EvaluationRun records."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from service.db.models import EvaluationRun

from .release_gate import ReleaseEvaluationRun


class EvaluationRunImmutableError(RuntimeError):
    """An EvaluationRun ID is already bound to different facts."""


class SqlAlchemyEvaluationRunRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def get(self, evaluation_run_id: str) -> ReleaseEvaluationRun | None:
        with self._sessions() as session:
            row = session.get(EvaluationRun, evaluation_run_id)
            return _run_from_row(row) if row is not None else None

    def record(self, run: ReleaseEvaluationRun) -> ReleaseEvaluationRun:
        with self._sessions.begin() as session:
            existing = session.scalar(
                select(EvaluationRun)
                .where(EvaluationRun.evaluation_run_id == run.evaluation_run_id)
                .with_for_update()
            )
            if existing is not None:
                if _run_from_row(existing) != run:
                    raise EvaluationRunImmutableError("immutable EvaluationRun drift")
                return run
            session.add(
                EvaluationRun(
                    evaluation_run_id=run.evaluation_run_id,
                    release_id=None,
                    suite_version=run.suite_version,
                    status=run.status,
                    metrics=run.model_dump(mode="json"),
                    completed_at=datetime.now(timezone.utc),
                )
            )
            session.flush()
        return run


def _run_from_row(row: EvaluationRun) -> ReleaseEvaluationRun:
    if row.metrics is None:
        raise EvaluationRunImmutableError("EvaluationRun metrics are missing")
    try:
        run = ReleaseEvaluationRun.model_validate(row.metrics)
    except ValueError as exc:
        raise EvaluationRunImmutableError(
            "immutable EvaluationRun payload drift"
        ) from exc
    if (
        row.evaluation_run_id != run.evaluation_run_id
        or row.suite_version != run.suite_version
        or row.status != run.status
        or row.release_id is not None
    ):
        raise EvaluationRunImmutableError("immutable EvaluationRun column drift")
    return run


__all__ = ["EvaluationRunImmutableError", "SqlAlchemyEvaluationRunRepository"]
