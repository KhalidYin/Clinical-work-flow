"""Authoritative read projection for immutable EvaluationRun records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Literal, Protocol, Sequence
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from service.db.models import EvaluationRun

from .contracts import EvaluationReport, StrictEvaluationModel
from .release_gate import ReleaseEvaluationRun


EvaluationPurpose = Literal["retrieval_baseline", "release_gate_synthetic"]
EvaluationOutcome = Literal["informational", "passed", "failed"]


class EvaluationReadIntegrityError(RuntimeError):
    """Stored EvaluationRun facts cannot be validated without guessing."""


class RetrievalBaselineRun(StrictEvaluationModel):
    """Immutable envelope that gives an E9 report a durable run identity."""

    evaluation_run_id: str = Field(min_length=1, max_length=160)
    purpose: Literal["retrieval_baseline"] = "retrieval_baseline"
    status: Literal["completed"] = "completed"
    outcome: Literal["informational"] = "informational"
    report: EvaluationReport

    @classmethod
    def from_report(cls, report: EvaluationReport) -> "RetrievalBaselineRun":
        identity = json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return cls(
            evaluation_run_id=f"evaluation-{uuid5(NAMESPACE_URL, identity).hex}",
            report=report,
        )


@dataclass(frozen=True, slots=True)
class EvaluationThresholdReadRecord:
    metric: str
    observed: float
    minimum: float
    passed: bool


@dataclass(frozen=True, slots=True)
class EvaluationCaseReadRecord:
    case_id: str
    topic: str | None
    question: str | None
    query_id: str | None
    outcome: str
    failure_category: str
    hit_at_5: bool
    hit_at_10: bool
    first_relevant_rank: int | None
    expected_evidence_ids: tuple[str, ...]
    retrieved_evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvaluationReadRecord:
    evaluation_run_id: str
    suite_id: str
    suite_version: str
    purpose: EvaluationPurpose
    target_id: str
    status: str
    outcome: EvaluationOutcome
    case_count: int
    recall_at_5: float
    recall_at_10: float
    threshold_checks: tuple[EvaluationThresholdReadRecord, ...]
    failure_reasons: tuple[str, ...]
    case_results: tuple[EvaluationCaseReadRecord, ...]
    external_model_requests: int
    evaluation_notice: str
    started_at: datetime
    completed_at: datetime | None


class EvaluationReadPort(Protocol):
    def list_runs(
        self,
        *,
        suite_id: str | None,
        purpose: EvaluationPurpose | None,
        outcome: EvaluationOutcome | None,
    ) -> tuple[Sequence[EvaluationReadRecord], Sequence[str]]: ...

    def get_run(self, *, evaluation_run_id: str) -> EvaluationReadRecord | None: ...


class SqlAlchemyEvaluationReadRepository:
    """Read and append E9 baselines without weakening Release Gate validation."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def record_retrieval_baseline(
        self,
        report: EvaluationReport,
    ) -> EvaluationReadRecord:
        run = RetrievalBaselineRun.from_report(report)
        with self._sessions.begin() as session:
            existing = session.get(EvaluationRun, run.evaluation_run_id)
            if existing is not None:
                record = _read_row(existing)
                if existing.metrics != run.model_dump(mode="json"):
                    raise EvaluationReadIntegrityError("immutable EvaluationRun drift")
                return record
            now = datetime.now(timezone.utc)
            row = EvaluationRun(
                evaluation_run_id=run.evaluation_run_id,
                release_id=None,
                suite_version=report.suite_version,
                status=run.status,
                metrics=run.model_dump(mode="json"),
                completed_at=now,
            )
            session.add(row)
            session.flush()
            return _read_row(row)

    def list_runs(
        self,
        *,
        suite_id: str | None = None,
        purpose: EvaluationPurpose | None = None,
        outcome: EvaluationOutcome | None = None,
    ) -> tuple[Sequence[EvaluationReadRecord], Sequence[str]]:
        with self._sessions() as session:
            rows = tuple(
                session.scalars(
                    select(EvaluationRun).order_by(
                        EvaluationRun.completed_at.desc().nullslast(),
                        EvaluationRun.started_at.desc(),
                        EvaluationRun.evaluation_run_id,
                    )
                )
            )
        records: list[EvaluationReadRecord] = []
        warnings: list[str] = []
        for row in rows:
            try:
                record = _read_row(row)
            except EvaluationReadIntegrityError:
                warnings.append(f"evaluation_run_invalid:{row.evaluation_run_id}")
                continue
            if purpose is not None and record.purpose != purpose:
                continue
            if suite_id is not None and record.suite_id != suite_id:
                continue
            if outcome is not None and record.outcome != outcome:
                continue
            records.append(record)
        return tuple(records), tuple(warnings)

    def get_run(self, *, evaluation_run_id: str) -> EvaluationReadRecord | None:
        with self._sessions() as session:
            row = session.get(EvaluationRun, evaluation_run_id)
            return _read_row(row) if row is not None else None

    def get_retrieval_baseline(
        self,
        *,
        evaluation_run_id: str,
    ) -> RetrievalBaselineRun | None:
        with self._sessions() as session:
            row = session.get(EvaluationRun, evaluation_run_id)
            if row is None:
                return None
            payload = row.metrics
            if not isinstance(payload, dict) or payload.get("purpose") != "retrieval_baseline":
                return None
            try:
                run = RetrievalBaselineRun.model_validate(payload)
            except ValueError as exc:
                raise EvaluationReadIntegrityError(
                    "immutable EvaluationRun payload drift"
                ) from exc
            _require_row_identity(row, run.evaluation_run_id, run.report.suite_version, run.status)
            return run


def _read_row(row: EvaluationRun) -> EvaluationReadRecord:
    payload = row.metrics
    if payload is None:
        raise EvaluationReadIntegrityError("EvaluationRun metrics are missing")
    try:
        if payload.get("purpose") == "retrieval_baseline":
            return _baseline_record(row, RetrievalBaselineRun.model_validate(payload))
        return _release_gate_record(row, ReleaseEvaluationRun.model_validate(payload))
    except (AttributeError, ValueError) as exc:
        raise EvaluationReadIntegrityError("immutable EvaluationRun payload drift") from exc


def _baseline_record(row: EvaluationRun, run: RetrievalBaselineRun) -> EvaluationReadRecord:
    report = run.report
    _require_row_identity(row, run.evaluation_run_id, report.suite_version, run.status)
    return EvaluationReadRecord(
        evaluation_run_id=run.evaluation_run_id,
        suite_id=report.suite_id,
        suite_version=report.suite_version,
        purpose=run.purpose,
        target_id=report.source_version_id,
        status=run.status,
        outcome=run.outcome,
        case_count=report.case_count,
        recall_at_5=report.metrics.recall_at_5,
        recall_at_10=report.metrics.recall_at_10,
        threshold_checks=(),
        failure_reasons=(),
        case_results=tuple(
            EvaluationCaseReadRecord(
                case_id=case.case_id,
                topic=case.topic,
                question=case.question,
                query_id=case.query_id,
                outcome=case.outcome,
                failure_category=case.failure_category,
                hit_at_5=case.hit_at_5,
                hit_at_10=case.hit_at_10,
                first_relevant_rank=case.first_relevant_rank,
                expected_evidence_ids=case.expected_evidence_ids,
                retrieved_evidence_ids=case.retrieved_evidence_ids,
            )
            for case in report.case_results
        ),
        external_model_requests=report.external_model_requests,
        evaluation_notice=report.evaluation_notice,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _release_gate_record(row: EvaluationRun, run: ReleaseEvaluationRun) -> EvaluationReadRecord:
    _require_row_identity(row, run.evaluation_run_id, run.suite_version, run.status)
    return EvaluationReadRecord(
        evaluation_run_id=run.evaluation_run_id,
        suite_id=run.suite_id,
        suite_version=run.suite_version,
        purpose="release_gate_synthetic",
        target_id=run.target_id,
        status=run.status,
        outcome=run.outcome,
        case_count=len(run.case_results),
        recall_at_5=run.metrics.recall_at_5,
        recall_at_10=run.metrics.recall_at_10,
        threshold_checks=tuple(
            EvaluationThresholdReadRecord(
                metric=check.metric,
                observed=check.observed,
                minimum=check.minimum,
                passed=check.passed,
            )
            for check in run.checks
        ),
        failure_reasons=tuple(run.failure_reasons),
        case_results=tuple(_synthetic_case_record(case) for case in run.case_results),
        external_model_requests=run.external_model_requests,
        evaluation_notice=run.evaluation_notice,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _synthetic_case_record(case) -> EvaluationCaseReadRecord:
    if case.hit_at_5:
        outcome, failure_category = "hit_top_5", "none"
    elif case.hit_at_10:
        outcome, failure_category = "hit_top_10_only", "ranked_below_5"
    else:
        outcome, failure_category = "expected_not_in_top_10", "expected_not_retrieved"
    return EvaluationCaseReadRecord(
        case_id=case.case_id,
        topic=None,
        question=None,
        query_id=None,
        outcome=outcome,
        failure_category=failure_category,
        hit_at_5=case.hit_at_5,
        hit_at_10=case.hit_at_10,
        first_relevant_rank=None,
        expected_evidence_ids=(),
        retrieved_evidence_ids=(),
    )


def _require_row_identity(
    row: EvaluationRun,
    evaluation_run_id: str,
    suite_version: str,
    status: str,
) -> None:
    if (
        row.evaluation_run_id != evaluation_run_id
        or row.suite_version != suite_version
        or row.status != status
    ):
        raise EvaluationReadIntegrityError("immutable EvaluationRun column drift")


__all__ = [
    "EvaluationCaseReadRecord",
    "EvaluationOutcome",
    "EvaluationPurpose",
    "EvaluationReadIntegrityError",
    "EvaluationReadPort",
    "EvaluationReadRecord",
    "EvaluationThresholdReadRecord",
    "RetrievalBaselineRun",
    "SqlAlchemyEvaluationReadRepository",
]
