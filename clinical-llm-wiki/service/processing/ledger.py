"""PostgreSQL durable ledger for discrete, resumable processing attempts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from service.auth import (
    ActorContext,
    AuthorizationError,
    Permission,
    PrincipalType,
    WorkerPool,
    require_permission,
)
from service.db.models import JobStep, ProcessingRun, StepAttempt

from .contracts import (
    AttemptStatus,
    ClaimedStepAttempt,
    RunStatus,
    StepDefinition,
    StepOutcome,
    StepStatus,
    validate_step_graph,
)


class LedgerError(RuntimeError):
    """Base error for invalid durable-ledger operations."""


class LeaseConflictError(LedgerError):
    """The caller no longer owns an active attempt lease."""


class RetryNotAllowedError(LedgerError):
    """A completed or active step cannot be retried."""


class ProcessingLedgerPort(Protocol):
    def recover_expired_leases(
        self,
        *,
        actor: ActorContext,
        pool: WorkerPool,
    ) -> int: ...

    def claim_next(
        self,
        *,
        actor: ActorContext,
        worker_id: str,
        supported_step_keys: frozenset[str],
        lease_seconds: int,
    ) -> ClaimedStepAttempt | None: ...

    def heartbeat(
        self,
        *,
        actor: ActorContext,
        worker_id: str,
        attempt_id: str,
        lease_seconds: int,
    ) -> None: ...

    def save_checkpoint(
        self,
        *,
        actor: ActorContext,
        worker_id: str,
        attempt_id: str,
        checkpoint: dict[str, Any],
    ) -> None: ...

    def complete_attempt(
        self,
        *,
        actor: ActorContext,
        worker_id: str,
        attempt_id: str,
        outcome: StepOutcome,
    ) -> None: ...

    def fail_attempt(
        self,
        *,
        actor: ActorContext,
        worker_id: str,
        attempt_id: str,
        error_type: str,
        error_message: str,
    ) -> None: ...


class PostgresProcessingLedger:
    """Transactional claim/lease/checkpoint implementation using SKIP LOCKED."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def create_run(
        self,
        *,
        source_version_id: str,
        requested_by_subject: str,
        steps: list[StepDefinition],
        run_id: str | None = None,
    ) -> str:
        definitions = validate_step_graph(steps)
        if not definitions:
            raise ValueError("processing run requires at least one step")
        resolved_run_id = run_id or f"run-{uuid4()}"
        now = _utcnow()
        with self._sessions.begin() as session:
            session.add(
                ProcessingRun(
                    run_id=resolved_run_id,
                    source_version_id=source_version_id,
                    status=RunStatus.QUEUED.value,
                    requested_by_subject=requested_by_subject,
                    failure_code=None,
                    updated_at=now,
                )
            )
            session.flush()
            for definition in definitions:
                step_id = f"step-{uuid4()}"
                session.add(
                    JobStep(
                        step_id=step_id,
                        run_id=resolved_run_id,
                        step_key=definition.step_key,
                        pool=definition.pool.value,
                        status=StepStatus.QUEUED.value,
                        depends_on=list(definition.depends_on),
                        input_sha256=definition.input_sha256,
                        output_sha256=None,
                        checkpoint=None,
                        updated_at=now,
                    )
                )
                session.flush()
                session.add(
                    StepAttempt(
                        attempt_id=f"attempt-{uuid4()}",
                        run_id=resolved_run_id,
                        step_id=step_id,
                        attempt_number=1,
                        previous_attempt_id=None,
                        status=AttemptStatus.QUEUED.value,
                        worker_id=None,
                        leased_until=None,
                        input_sha256=definition.input_sha256,
                        output_sha256=None,
                        checkpoint=None,
                        artifact_manifest=None,
                        error_type=None,
                        error_message=None,
                        started_at=None,
                        completed_at=None,
                    )
                )
        return resolved_run_id

    def claim_next(
        self,
        *,
        actor: ActorContext,
        worker_id: str,
        supported_step_keys: frozenset[str],
        lease_seconds: int,
    ) -> ClaimedStepAttempt | None:
        pool = _require_worker(actor)
        if not supported_step_keys:
            return None
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        now = _utcnow()
        with self._sessions.begin() as session:
            candidates = session.execute(
                select(StepAttempt, JobStep, ProcessingRun)
                .join(
                    JobStep,
                    (JobStep.step_id == StepAttempt.step_id)
                    & (JobStep.run_id == StepAttempt.run_id),
                )
                .join(ProcessingRun, ProcessingRun.run_id == StepAttempt.run_id)
                .where(
                    StepAttempt.status == AttemptStatus.QUEUED.value,
                    JobStep.status == StepStatus.QUEUED.value,
                    JobStep.pool == pool.value,
                    JobStep.step_key.in_(supported_step_keys),
                    ProcessingRun.status.in_(
                        [RunStatus.QUEUED.value, RunStatus.PROCESSING.value]
                    ),
                )
                .order_by(StepAttempt.created_at, StepAttempt.attempt_id)
                .limit(50)
                .with_for_update(skip_locked=True, of=StepAttempt)
            ).all()
            for attempt, step, run in candidates:
                if not self._dependencies_succeeded(session, step):
                    continue
                attempt.status = AttemptStatus.LEASED.value
                attempt.worker_id = worker_id
                attempt.leased_until = now + timedelta(seconds=lease_seconds)
                attempt.started_at = now
                step.status = StepStatus.PROCESSING.value
                step.updated_at = now
                run.status = RunStatus.PROCESSING.value
                run.updated_at = now
                return _claimed(attempt, step)
        return None

    def heartbeat(
        self,
        *,
        actor: ActorContext,
        worker_id: str,
        attempt_id: str,
        lease_seconds: int,
    ) -> None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        now = _utcnow()
        with self._sessions.begin() as session:
            attempt, _ = self._active_attempt(
                session, actor=actor, worker_id=worker_id, attempt_id=attempt_id, now=now
            )
            attempt.leased_until = now + timedelta(seconds=lease_seconds)

    def save_checkpoint(
        self,
        *,
        actor: ActorContext,
        worker_id: str,
        attempt_id: str,
        checkpoint: dict[str, Any],
    ) -> None:
        now = _utcnow()
        with self._sessions.begin() as session:
            attempt, _ = self._active_attempt(
                session, actor=actor, worker_id=worker_id, attempt_id=attempt_id, now=now
            )
            # Attempt history is authoritative. JobStep.checkpoint remains null until contract.
            attempt.checkpoint = checkpoint

    def complete_attempt(
        self,
        *,
        actor: ActorContext,
        worker_id: str,
        attempt_id: str,
        outcome: StepOutcome,
    ) -> None:
        now = _utcnow()
        with self._sessions.begin() as session:
            attempt, step = self._active_attempt(
                session, actor=actor, worker_id=worker_id, attempt_id=attempt_id, now=now
            )
            attempt.status = AttemptStatus.SUCCEEDED.value
            attempt.output_sha256 = outcome.output_sha256
            attempt.artifact_manifest = outcome.artifact_manifest.model_dump(mode="json")
            attempt.leased_until = None
            attempt.completed_at = now
            step.status = StepStatus.SUCCEEDED.value
            step.output_sha256 = outcome.output_sha256
            step.updated_at = now
            run = session.get(ProcessingRun, attempt.run_id)
            if run is not None:
                run.updated_at = now

    def fail_attempt(
        self,
        *,
        actor: ActorContext,
        worker_id: str,
        attempt_id: str,
        error_type: str,
        error_message: str,
    ) -> None:
        if len(error_type) > 80 or len(error_message) > 500:
            raise ValueError("ledger errors must be bounded and sanitized")
        now = _utcnow()
        with self._sessions.begin() as session:
            attempt, step = self._active_attempt(
                session, actor=actor, worker_id=worker_id, attempt_id=attempt_id, now=now
            )
            attempt.status = AttemptStatus.FAILED.value
            attempt.error_type = error_type
            attempt.error_message = error_message
            attempt.leased_until = None
            attempt.completed_at = now
            step.status = StepStatus.FAILED.value
            step.updated_at = now
            run = session.get(ProcessingRun, attempt.run_id)
            if run is not None:
                run.status = RunStatus.FAILED.value
                run.failure_code = error_type
                run.updated_at = now
                run.completed_at = now

    def recover_expired_leases(
        self,
        *,
        actor: ActorContext,
        pool: WorkerPool,
    ) -> int:
        actor_pool = _require_worker(actor)
        if actor_pool is not pool:
            raise AuthorizationError("worker actor cannot recover another pool")
        now = _utcnow()
        recovered = 0
        with self._sessions.begin() as session:
            rows = session.execute(
                select(StepAttempt, JobStep)
                .join(
                    JobStep,
                    (JobStep.step_id == StepAttempt.step_id)
                    & (JobStep.run_id == StepAttempt.run_id),
                )
                .where(
                    StepAttempt.status == AttemptStatus.LEASED.value,
                    StepAttempt.leased_until <= now,
                    JobStep.pool == pool.value,
                )
                .order_by(StepAttempt.leased_until, StepAttempt.attempt_id)
                .with_for_update(skip_locked=True, of=StepAttempt)
            ).all()
            for expired, step in rows:
                expired.status = AttemptStatus.EXPIRED.value
                expired.leased_until = None
                expired.completed_at = now
                session.add(
                    StepAttempt(
                        attempt_id=f"attempt-{uuid4()}",
                        run_id=expired.run_id,
                        step_id=expired.step_id,
                        attempt_number=expired.attempt_number + 1,
                        previous_attempt_id=expired.attempt_id,
                        status=AttemptStatus.QUEUED.value,
                        worker_id=None,
                        leased_until=None,
                        input_sha256=expired.input_sha256,
                        output_sha256=None,
                        checkpoint=expired.checkpoint,
                        artifact_manifest=None,
                        error_type=None,
                        error_message=None,
                        started_at=None,
                        completed_at=None,
                    )
                )
                step.status = StepStatus.QUEUED.value
                step.updated_at = now
                run = session.get(ProcessingRun, expired.run_id)
                if run is not None and run.status != RunStatus.CANCELLED.value:
                    run.status = RunStatus.QUEUED.value
                    run.updated_at = now
                    run.completed_at = None
                    run.failure_code = None
                recovered += 1
        return recovered

    def retry_step(self, *, actor: ActorContext, run_id: str, step_id: str) -> str:
        if actor.principal_type is not PrincipalType.HUMAN:
            raise AuthorizationError("only a human actor may request a retry")
        require_permission(actor, Permission.PROCESSING_RETRY)
        now = _utcnow()
        with self._sessions.begin() as session:
            step = session.scalar(
                select(JobStep)
                .where(JobStep.run_id == run_id, JobStep.step_id == step_id)
                .with_for_update()
            )
            if step is None:
                raise RetryNotAllowedError("step does not exist")
            latest = session.scalar(
                select(StepAttempt)
                .where(StepAttempt.run_id == run_id, StepAttempt.step_id == step_id)
                .order_by(StepAttempt.attempt_number.desc())
                .limit(1)
                .with_for_update()
            )
            if latest is None or latest.status not in {
                AttemptStatus.FAILED.value,
                AttemptStatus.EXPIRED.value,
            }:
                raise RetryNotAllowedError("only a failed or expired latest attempt may retry")
            retry_id = f"attempt-{uuid4()}"
            session.add(
                StepAttempt(
                    attempt_id=retry_id,
                    run_id=run_id,
                    step_id=step_id,
                    attempt_number=latest.attempt_number + 1,
                    previous_attempt_id=latest.attempt_id,
                    status=AttemptStatus.QUEUED.value,
                    worker_id=None,
                    leased_until=None,
                    input_sha256=latest.input_sha256,
                    output_sha256=None,
                    checkpoint=latest.checkpoint,
                    artifact_manifest=None,
                    error_type=None,
                    error_message=None,
                    started_at=None,
                    completed_at=None,
                )
            )
            step.status = StepStatus.QUEUED.value
            step.updated_at = now
            run = session.get(ProcessingRun, run_id)
            if run is None or run.status == RunStatus.CANCELLED.value:
                raise RetryNotAllowedError("cancelled or missing run cannot retry")
            run.status = RunStatus.QUEUED.value
            run.failure_code = None
            run.completed_at = None
            run.updated_at = now
        return retry_id

    def cancel_run(self, *, actor: ActorContext, run_id: str) -> None:
        if actor.principal_type is not PrincipalType.HUMAN:
            raise AuthorizationError("only a human actor may cancel a run")
        # The frozen P1-C matrix treats cancellation as lifecycle control by a run starter.
        require_permission(actor, Permission.PROCESSING_START)
        now = _utcnow()
        with self._sessions.begin() as session:
            run = session.scalar(
                select(ProcessingRun)
                .where(ProcessingRun.run_id == run_id)
                .with_for_update()
            )
            if run is None:
                raise LedgerError("run does not exist")
            if run.status in {RunStatus.RELEASED.value, RunStatus.CANCELLED.value}:
                raise LedgerError("terminal run cannot be cancelled")
            run.status = RunStatus.CANCELLED.value
            run.updated_at = now
            run.completed_at = now
            for step in session.scalars(
                select(JobStep).where(
                    JobStep.run_id == run_id,
                    JobStep.status.in_([StepStatus.QUEUED.value, StepStatus.PROCESSING.value]),
                )
            ):
                step.status = StepStatus.CANCELLED.value
                step.updated_at = now
            for attempt in session.scalars(
                select(StepAttempt).where(
                    StepAttempt.run_id == run_id,
                    StepAttempt.status.in_(
                        [AttemptStatus.QUEUED.value, AttemptStatus.LEASED.value]
                    ),
                )
            ):
                attempt.status = AttemptStatus.CANCELLED.value
                attempt.leased_until = None
                attempt.completed_at = now

    @staticmethod
    def _dependencies_succeeded(session: Session, step: JobStep) -> bool:
        dependencies = tuple(step.depends_on or ())
        if not dependencies:
            return True
        rows = session.execute(
            select(JobStep.step_key, JobStep.status).where(
                JobStep.run_id == step.run_id,
                JobStep.step_key.in_(dependencies),
            )
        ).all()
        statuses = {key: status for key, status in rows}
        return all(statuses.get(key) == StepStatus.SUCCEEDED.value for key in dependencies)

    @staticmethod
    def _active_attempt(
        session: Session,
        *,
        actor: ActorContext,
        worker_id: str,
        attempt_id: str,
        now: datetime,
    ) -> tuple[StepAttempt, JobStep]:
        pool = _require_worker(actor)
        row = session.execute(
            select(StepAttempt, JobStep)
            .join(
                JobStep,
                (JobStep.step_id == StepAttempt.step_id)
                & (JobStep.run_id == StepAttempt.run_id),
            )
            .where(StepAttempt.attempt_id == attempt_id)
            .with_for_update(of=StepAttempt)
        ).one_or_none()
        if row is None:
            raise LeaseConflictError("attempt does not exist")
        attempt, step = row
        if step.pool != pool.value:
            raise AuthorizationError("worker actor cannot mutate another pool")
        if (
            attempt.status != AttemptStatus.LEASED.value
            or attempt.worker_id != worker_id
            or attempt.leased_until is None
            or attempt.leased_until <= now
        ):
            raise LeaseConflictError("attempt lease is not active for this worker")
        return attempt, step


def _require_worker(actor: ActorContext) -> WorkerPool:
    if actor.principal_type is not PrincipalType.SERVICE_ACCOUNT or actor.worker_pool is None:
        raise AuthorizationError("ledger execution requires a service account worker")
    require_permission(actor, Permission.PROCESSING_EXECUTE)
    return actor.worker_pool


def _claimed(attempt: StepAttempt, step: JobStep) -> ClaimedStepAttempt:
    return ClaimedStepAttempt(
        run_id=attempt.run_id,
        step_id=attempt.step_id,
        step_key=step.step_key,
        pool=WorkerPool(step.pool),
        attempt_id=attempt.attempt_id,
        attempt_number=attempt.attempt_number,
        previous_attempt_id=attempt.previous_attempt_id,
        input_sha256=attempt.input_sha256,
        checkpoint=attempt.checkpoint,
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
