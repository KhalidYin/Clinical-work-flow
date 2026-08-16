"""PostgreSQL and object-store adapter for the Release governance workbench."""

from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from service.db.models import EvaluationRun, Release, ReleaseItem, ReleasePointer
from service.evaluation import ReleaseEvaluationRun
from service.object_store import ObjectStoreError

from .repository import ReleaseStateError, SqlAlchemyReleaseRepository
from .workbench import (
    ReleaseGateFact,
    ReleaseSummaryRecord,
    ReleaseWorkbenchSnapshot,
)


class ReleaseCandidateNotFoundError(LookupError):
    """The requested candidate does not exist or is no longer a candidate."""


class SqlAlchemyReleaseWorkbenchRepository:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        releases: SqlAlchemyReleaseRepository,
    ) -> None:
        self._sessions = session_factory
        self._releases = releases

    def load_workbench(
        self,
        *,
        candidate_id: str | None,
    ) -> ReleaseWorkbenchSnapshot:
        with self._sessions() as session:
            pointer = session.get(ReleasePointer, "current")
            current_id = pointer.current_release_id if pointer is not None else None
            rows = tuple(
                session.scalars(
                    select(Release).order_by(
                        Release.created_at.desc(),
                        Release.release_id,
                    )
                )
            )
            counts = dict(
                session.execute(
                    select(ReleaseItem.release_id, func.count()).group_by(ReleaseItem.release_id)
                ).all()
            )
            summaries = tuple(
                _summary(row, counts.get(row.release_id, 0), current_id) for row in rows
            )
            candidates = tuple(row for row in rows if row.status == "candidate")
            if candidate_id is None:
                candidate_row = candidates[0] if candidates else None
            else:
                candidate_row = next(
                    (row for row in candidates if row.release_id == candidate_id),
                    None,
                )
                if candidate_row is None:
                    raise ReleaseCandidateNotFoundError(candidate_id)
            candidate_summary = (
                _summary(
                    candidate_row,
                    counts.get(candidate_row.release_id, 0),
                    current_id,
                )
                if candidate_row is not None
                else None
            )
            current_row = next(
                (row for row in rows if row.release_id == current_id),
                None,
            )
            current_summary = (
                _summary(
                    current_row,
                    counts.get(current_row.release_id, 0),
                    current_id,
                )
                if current_row is not None
                else None
            )
            history = tuple(summary for summary in summaries if summary.status == "released")

        if candidate_summary is None:
            return ReleaseWorkbenchSnapshot(
                current=current_summary,
                candidate=None,
                history=history,
                candidate_manifest=None,
                base_manifest=None,
                gates=(),
            )

        gates: list[ReleaseGateFact] = []
        try:
            prepared = self._releases.get_candidate(candidate_summary.release_id)
            if prepared is None:
                raise ReleaseStateError("Release candidate is unavailable")
        except (ObjectStoreError, ReleaseStateError, ValueError):
            gates.append(
                ReleaseGateFact(
                    code="candidate_integrity",
                    passed=False,
                    reason="candidate_integrity_failed",
                )
            )
            return ReleaseWorkbenchSnapshot(
                current=current_summary,
                candidate=candidate_summary,
                history=history,
                candidate_manifest=None,
                base_manifest=None,
                gates=tuple(gates),
            )

        gates.append(
            ReleaseGateFact(
                code="candidate_integrity",
                passed=True,
                reason="candidate_hash_verified",
            )
        )
        base_matches = candidate_summary.base_release_id == current_id
        gates.append(
            ReleaseGateFact(
                code="base_release_current",
                passed=base_matches,
                reason=("base_matches_current" if base_matches else "base_release_is_stale"),
            )
        )
        evaluation_passed = self._evaluation_passed(
            evaluation_run_id=prepared.evaluation_run_id,
            candidate_id=prepared.release_id,
        )
        gates.append(
            ReleaseGateFact(
                code="evaluation_passed",
                passed=evaluation_passed,
                reason=("evaluation_passed" if evaluation_passed else "evaluation_not_publishable"),
            )
        )
        try:
            self._releases.validate_candidate(prepared)
        except (ObjectStoreError, ReleaseStateError, ValueError):
            snapshot_valid = False
        else:
            snapshot_valid = True
        gates.append(
            ReleaseGateFact(
                code="publication_snapshot",
                passed=snapshot_valid,
                reason=(
                    "publication_snapshot_valid"
                    if snapshot_valid
                    else "publication_snapshot_blocked"
                ),
            )
        )

        base_manifest = None
        if prepared.base_release_id is not None:
            try:
                base = self._releases.get_released(prepared.base_release_id)
            except (ObjectStoreError, ReleaseStateError, ValueError):
                base = None
            base_manifest = base.manifest if base is not None else None
        return ReleaseWorkbenchSnapshot(
            current=current_summary,
            candidate=candidate_summary,
            history=history,
            candidate_manifest=prepared.manifest,
            base_manifest=base_manifest,
            gates=tuple(gates),
        )

    def _evaluation_passed(
        self,
        *,
        evaluation_run_id: str,
        candidate_id: str,
    ) -> bool:
        with self._sessions() as session:
            row = session.get(EvaluationRun, evaluation_run_id)
            if row is None or row.metrics is None or row.release_id is not None:
                return False
            try:
                run = ReleaseEvaluationRun.model_validate(row.metrics)
            except ValidationError:
                return False
            return (
                row.evaluation_run_id == run.evaluation_run_id
                and row.suite_version == run.suite_version
                and row.status == run.status
                and run.status == "completed"
                and run.outcome == "passed"
                and run.target_id == candidate_id
            )


def _summary(
    row: Release,
    item_count: int,
    current_release_id: str | None,
) -> ReleaseSummaryRecord:
    return ReleaseSummaryRecord(
        release_id=row.release_id,
        version=row.version,
        status=row.status,
        base_release_id=row.previous_release_id,
        item_count=item_count,
        is_current=row.release_id == current_release_id,
        created_at=row.created_at,
        published_at=row.published_at,
    )


__all__ = [
    "ReleaseCandidateNotFoundError",
    "SqlAlchemyReleaseWorkbenchRepository",
]
