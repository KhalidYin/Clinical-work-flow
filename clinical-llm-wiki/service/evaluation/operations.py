"""Server-owned Evaluation start, replay, and regression operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, Sequence

from pydantic import Field

from service.auth import ActorContext, Permission, require_permission
from service.retrieval import ReleaseCandidateScope, RetrievalQuery, RetrievalResult

from .contracts import EvaluationReport, GoldSuite, StrictEvaluationModel
from .read_model import EvaluationCaseReadRecord, EvaluationReadRecord, RetrievalBaselineRun
from .service import EvaluationService, RetrievalQueryPort


class EvaluationSuiteNotFoundError(LookupError):
    """The requested server-registered evaluation suite does not exist."""


class EvaluationSuiteVersionConflictError(RuntimeError):
    """The caller selected a stale version of a registered suite."""


class EvaluationRunNotFoundError(LookupError):
    """The requested immutable EvaluationRun does not exist."""


class EvaluationCaseNotFoundError(LookupError):
    """The requested case is not present in the immutable EvaluationRun."""


class EvaluationComparisonError(RuntimeError):
    """Two immutable runs cannot be compared without inventing semantics."""


EvaluationCaseChange = Literal[
    "improved",
    "regressed",
    "unchanged",
    "added",
    "removed",
]


class EvaluationStartCommand(StrictEvaluationModel):
    suite_id: str = Field(min_length=3, max_length=160)
    suite_version: str = Field(min_length=1, max_length=120)


@dataclass(frozen=True, slots=True)
class RegisteredEvaluationSuite:
    suite: GoldSuite
    sandbox_id: str

    def __post_init__(self) -> None:
        if not self.sandbox_id.strip():
            raise ValueError("registered evaluation sandbox ID is required")


@dataclass(frozen=True, slots=True)
class EvaluationSuiteRecord:
    suite_id: str
    suite_version: str
    document_id: str
    source_version_id: str
    chunk_profile_id: str
    case_count: int
    sandbox_kind: Literal["release_candidate"] = "release_candidate"
    external_model_requests: Literal[0] = 0


@dataclass(frozen=True, slots=True)
class EvaluationMetricDeltas:
    recall_at_5: float
    recall_at_10: float


@dataclass(frozen=True, slots=True)
class EvaluationRegressionCounts:
    improved: int
    regressed: int
    unchanged: int
    added: int
    removed: int


@dataclass(frozen=True, slots=True)
class EvaluationCaseDiffRecord:
    case_id: str
    change: EvaluationCaseChange
    baseline_outcome: str | None
    current_outcome: str | None
    baseline_rank: int | None
    current_rank: int | None


@dataclass(frozen=True, slots=True)
class EvaluationRegressionRecord:
    evaluation_run_id: str
    baseline_run_id: str
    suite_id: str
    current_suite_version: str
    baseline_suite_version: str
    metric_deltas: EvaluationMetricDeltas
    counts: EvaluationRegressionCounts
    case_diffs: tuple[EvaluationCaseDiffRecord, ...]


class EvaluationOperationsRepositoryPort(Protocol):
    def record_retrieval_baseline(
        self,
        report: EvaluationReport,
    ) -> EvaluationReadRecord: ...

    def get_retrieval_baseline(
        self,
        *,
        evaluation_run_id: str,
    ) -> RetrievalBaselineRun | None: ...

    def get_run(self, *, evaluation_run_id: str) -> EvaluationReadRecord | None: ...


class EvaluationOperationsService:
    """Keep candidate scope and comparison semantics on the server."""

    def __init__(
        self,
        *,
        suites: Sequence[RegisteredEvaluationSuite],
        retrieval: RetrievalQueryPort,
        repository: EvaluationOperationsRepositoryPort,
    ) -> None:
        registered = {item.suite.suite_id: item for item in suites}
        if len(registered) != len(suites):
            raise ValueError("registered evaluation suite IDs must be unique")
        self._suites = registered
        self._retrieval = retrieval
        self._repository = repository

    def list_suites(self) -> tuple[EvaluationSuiteRecord, ...]:
        return tuple(
            EvaluationSuiteRecord(
                suite_id=registered.suite.suite_id,
                suite_version=registered.suite.version,
                document_id=registered.suite.document_id,
                source_version_id=registered.suite.source_version_id,
                chunk_profile_id=registered.suite.chunk_profile_id,
                case_count=len(registered.suite.cases),
            )
            for registered in sorted(
                self._suites.values(),
                key=lambda item: (item.suite.suite_id, item.suite.version),
            )
        )

    def start(
        self,
        *,
        actor: ActorContext,
        command: EvaluationStartCommand,
    ) -> EvaluationReadRecord:
        require_permission(actor, Permission.EVALUATION_RUN)
        registered = self._registered_suite(command.suite_id)
        if registered.suite.version != command.suite_version:
            raise EvaluationSuiteVersionConflictError(
                "registered evaluation suite version changed"
            )
        report = EvaluationService(retrieval=self._retrieval).run(
            suite=registered.suite,
            scope=_scope(registered),
        )
        return self._repository.record_retrieval_baseline(report)

    def replay_case(
        self,
        *,
        actor: ActorContext,
        evaluation_run_id: str,
        case_id: str,
    ) -> RetrievalResult:
        require_permission(actor, Permission.CANDIDATE_READ)
        run = self._repository.get_retrieval_baseline(
            evaluation_run_id=evaluation_run_id
        )
        if run is None:
            raise EvaluationRunNotFoundError(evaluation_run_id)
        case = next(
            (item for item in run.report.case_results if item.case_id == case_id),
            None,
        )
        if case is None:
            raise EvaluationCaseNotFoundError(case_id)
        return self._retrieval.query(
            RetrievalQuery(
                query=case.question,
                top_k=10,
                scope=ReleaseCandidateScope(
                    sandbox_id=run.report.sandbox_id,
                    source_version_ids=(run.report.source_version_id,),
                    chunk_profile_id=run.report.chunk_profile_id,
                ),
            )
        )

    def compare_runs(
        self,
        *,
        actor: ActorContext,
        evaluation_run_id: str,
        baseline_run_id: str,
    ) -> EvaluationRegressionRecord:
        require_permission(actor, Permission.QUERY_RELEASED)
        current = self._repository.get_run(evaluation_run_id=evaluation_run_id)
        baseline = self._repository.get_run(evaluation_run_id=baseline_run_id)
        if current is None:
            raise EvaluationRunNotFoundError(evaluation_run_id)
        if baseline is None:
            raise EvaluationRunNotFoundError(baseline_run_id)
        if (
            current.suite_id != baseline.suite_id
            or current.purpose != baseline.purpose
        ):
            raise EvaluationComparisonError(
                "Evaluation regression requires the same suite and purpose"
            )
        case_diffs = _case_diffs(current=current, baseline=baseline)
        return EvaluationRegressionRecord(
            evaluation_run_id=current.evaluation_run_id,
            baseline_run_id=baseline.evaluation_run_id,
            suite_id=current.suite_id,
            current_suite_version=current.suite_version,
            baseline_suite_version=baseline.suite_version,
            metric_deltas=EvaluationMetricDeltas(
                recall_at_5=round(current.recall_at_5 - baseline.recall_at_5, 6),
                recall_at_10=round(current.recall_at_10 - baseline.recall_at_10, 6),
            ),
            counts=EvaluationRegressionCounts(
                improved=sum(item.change == "improved" for item in case_diffs),
                regressed=sum(item.change == "regressed" for item in case_diffs),
                unchanged=sum(item.change == "unchanged" for item in case_diffs),
                added=sum(item.change == "added" for item in case_diffs),
                removed=sum(item.change == "removed" for item in case_diffs),
            ),
            case_diffs=case_diffs,
        )

    def _registered_suite(self, suite_id: str) -> RegisteredEvaluationSuite:
        try:
            return self._suites[suite_id]
        except KeyError as exc:
            raise EvaluationSuiteNotFoundError(suite_id) from exc


def _scope(registered: RegisteredEvaluationSuite) -> ReleaseCandidateScope:
    return ReleaseCandidateScope(
        sandbox_id=registered.sandbox_id,
        source_version_ids=(registered.suite.source_version_id,),
        chunk_profile_id=registered.suite.chunk_profile_id,
    )


def _case_diffs(
    *,
    current: EvaluationReadRecord,
    baseline: EvaluationReadRecord,
) -> tuple[EvaluationCaseDiffRecord, ...]:
    current_by_id = {item.case_id: item for item in current.case_results}
    baseline_by_id = {item.case_id: item for item in baseline.case_results}
    ordered_ids = tuple(baseline_by_id) + tuple(
        case_id for case_id in current_by_id if case_id not in baseline_by_id
    )
    results: list[EvaluationCaseDiffRecord] = []
    for case_id in ordered_ids:
        current_case = current_by_id.get(case_id)
        baseline_case = baseline_by_id.get(case_id)
        results.append(
            EvaluationCaseDiffRecord(
                case_id=case_id,
                change=_case_change(current_case=current_case, baseline_case=baseline_case),
                baseline_outcome=(
                    baseline_case.outcome if baseline_case is not None else None
                ),
                current_outcome=current_case.outcome if current_case is not None else None,
                baseline_rank=(
                    baseline_case.first_relevant_rank
                    if baseline_case is not None
                    else None
                ),
                current_rank=(
                    current_case.first_relevant_rank
                    if current_case is not None
                    else None
                ),
            )
        )
    return tuple(results)


def _case_change(
    *,
    current_case: EvaluationCaseReadRecord | None,
    baseline_case: EvaluationCaseReadRecord | None,
) -> EvaluationCaseChange:
    if baseline_case is None:
        return "added"
    if current_case is None:
        return "removed"
    current_score = _outcome_score(current_case.outcome)
    baseline_score = _outcome_score(baseline_case.outcome)
    if current_score > baseline_score:
        return "improved"
    if current_score < baseline_score:
        return "regressed"
    return "unchanged"


def _outcome_score(outcome: str) -> int:
    return {
        "expected_not_in_top_10": 0,
        "hit_top_10_only": 1,
        "hit_top_5": 2,
    }[outcome]


__all__ = [
    "EvaluationCaseDiffRecord",
    "EvaluationCaseNotFoundError",
    "EvaluationComparisonError",
    "EvaluationMetricDeltas",
    "EvaluationOperationsRepositoryPort",
    "EvaluationOperationsService",
    "EvaluationRegressionCounts",
    "EvaluationRegressionRecord",
    "EvaluationRunNotFoundError",
    "EvaluationStartCommand",
    "EvaluationSuiteNotFoundError",
    "EvaluationSuiteRecord",
    "EvaluationSuiteVersionConflictError",
    "RegisteredEvaluationSuite",
]
