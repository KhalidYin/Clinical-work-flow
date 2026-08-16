from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from service.auth import (
    ActorContext,
    AuthorizationError,
    IdentitySource,
    PrincipalType,
    ProductRole,
    ROLE_PERMISSIONS,
)
from service.evaluation import (
    EvaluationCaseReadRecord,
    EvaluationOperationsService,
    EvaluationReadRecord,
    EvaluationStartCommand,
    GoldSuite,
    RegisteredEvaluationSuite,
    RetrievalBaselineRun,
)
from service.retrieval import (
    CapabilityState,
    ContextPackage,
    RetrievalCapabilities,
    RetrievalResult,
    retrieval_query_identity,
)
from service.platform_api.main import _registered_evaluation_suites


ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "service/evaluation/suites/ich-e9-retrieval-gold-v1.json"


def _actor(role: ProductRole) -> ActorContext:
    return ActorContext(
        actor_id=f"usr-{role.value}",
        display_name=role.value,
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({role}),
        permissions=ROLE_PERMISSIONS[role],
        identity_source=IdentitySource.LOCAL_TEST,
    )


def _suite() -> GoldSuite:
    return GoldSuite.model_validate_json(SUITE_PATH.read_text(encoding="utf-8"))


class RecordingRetrieval:
    def __init__(self) -> None:
        self.requests = []

    def query(self, request):
        self.requests.append(request)
        return RetrievalResult(
            query_id=retrieval_query_identity(request),
            capabilities=RetrievalCapabilities(
                metadata=CapabilityState(status="available"),
                full_text=CapabilityState(status="available"),
                vector=CapabilityState(status="degraded", reason="not_configured"),
                relation=CapabilityState(status="degraded", reason="not_enabled"),
                generation=CapabilityState(status="disabled", reason="zero_model_requests"),
            ),
            hits=(),
            context_package=ContextPackage(
                sandbox_id=request.scope.sandbox_id,
                chunk_ids=(),
                citations=(),
            ),
        )


class MemoryEvaluationOperationsRepository:
    def __init__(self) -> None:
        self.runs: dict[str, RetrievalBaselineRun] = {}
        self.records: dict[str, EvaluationReadRecord] = {}
        self.insertions = 0

    def record_retrieval_baseline(self, report):
        run = RetrievalBaselineRun.from_report(report)
        if run.evaluation_run_id not in self.runs:
            self.runs[run.evaluation_run_id] = run
            self.records[run.evaluation_run_id] = self._record(run)
            self.insertions += 1
        return self.get_run(evaluation_run_id=run.evaluation_run_id)

    def get_retrieval_baseline(self, *, evaluation_run_id):
        return self.runs.get(evaluation_run_id)

    def get_run(self, *, evaluation_run_id):
        return self.records.get(evaluation_run_id)

    @staticmethod
    def _record(run):
        report = run.report
        now = datetime.now(timezone.utc)
        return EvaluationReadRecord(
            evaluation_run_id=run.evaluation_run_id,
            suite_id=report.suite_id,
            suite_version=report.suite_version,
            purpose="retrieval_baseline",
            target_id=report.source_version_id,
            status="completed",
            outcome="informational",
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
            external_model_requests=0,
            evaluation_notice=report.evaluation_notice,
            started_at=now,
            completed_at=now,
        )


def _service():
    suite = _suite()
    retrieval = RecordingRetrieval()
    repository = MemoryEvaluationOperationsRepository()
    service = EvaluationOperationsService(
        suites=(
            RegisteredEvaluationSuite(
                suite=suite,
                sandbox_id="sandbox-ich-e9-poc-v1",
            ),
        ),
        retrieval=retrieval,
        repository=repository,
    )
    return service, retrieval, repository, suite


def test_start_uses_server_registered_suite_scope_and_records_one_immutable_run() -> None:
    service, retrieval, repository, suite = _service()
    command = EvaluationStartCommand(
        suite_id=suite.suite_id,
        suite_version=suite.version,
    )

    first = service.start(actor=_actor(ProductRole.RELEASE_MANAGER), command=command)
    repeated = service.start(actor=_actor(ProductRole.RELEASE_MANAGER), command=command)

    assert first == repeated
    assert first.purpose == "retrieval_baseline"
    assert first.outcome == "informational"
    assert first.external_model_requests == 0
    assert repository.insertions == 1
    assert len(retrieval.requests) == 36
    assert all(
        request.scope.source_version_ids == (suite.source_version_id,)
        and request.scope.chunk_profile_id == suite.chunk_profile_id
        and request.scope.sandbox_id == "sandbox-ich-e9-poc-v1"
        for request in retrieval.requests
    )

    with pytest.raises(AuthorizationError, match="evaluation:run"):
        service.start(actor=_actor(ProductRole.CONSUMER), command=command)


def test_case_replay_recovers_candidate_scope_from_immutable_run() -> None:
    service, retrieval, _, suite = _service()
    run = service.start(
        actor=_actor(ProductRole.RELEASE_MANAGER),
        command=EvaluationStartCommand(
            suite_id=suite.suite_id,
            suite_version=suite.version,
        ),
    )
    case = suite.cases[0]

    replay = service.replay_case(
        actor=_actor(ProductRole.RELEASE_MANAGER),
        evaluation_run_id=run.evaluation_run_id,
        case_id=case.case_id,
    )

    assert replay.query_id == retrieval_query_identity(retrieval.requests[-1])
    request = retrieval.requests[-1]
    assert request.query == case.question
    assert request.top_k == 10
    assert request.scope.source_version_ids == (suite.source_version_id,)
    assert request.scope.chunk_profile_id == suite.chunk_profile_id
    assert request.scope.sandbox_id == "sandbox-ich-e9-poc-v1"

    with pytest.raises(AuthorizationError, match="candidate:read"):
        service.replay_case(
            actor=_actor(ProductRole.CONSUMER),
            evaluation_run_id=run.evaluation_run_id,
            case_id=case.case_id,
        )


def test_regression_diff_is_server_classified_for_same_suite_runs() -> None:
    service, _, repository, suite = _service()
    baseline = service.start(
        actor=_actor(ProductRole.RELEASE_MANAGER),
        command=EvaluationStartCommand(
            suite_id=suite.suite_id,
            suite_version=suite.version,
        ),
    )
    baseline_envelope = repository.runs[baseline.evaluation_run_id]
    first_case = baseline_envelope.report.case_results[0]
    improved_case = first_case.model_copy(
        update={
            "first_relevant_rank": 1,
            "hit_at_5": True,
            "hit_at_10": True,
            "outcome": "hit_top_5",
            "failure_category": "none",
            "retrieved_evidence_ids": first_case.expected_evidence_ids,
            "matched_expected_evidence_ids": first_case.expected_evidence_ids,
        }
    )
    current_report = baseline_envelope.report.model_copy(
        update={
            "suite_version": "1.0.1",
            "metrics": baseline_envelope.report.metrics.model_copy(
                update={"recall_at_5": 0.055556, "recall_at_10": 0.055556}
            ),
            "case_results": (improved_case, *baseline_envelope.report.case_results[1:]),
        }
    )
    current = repository.record_retrieval_baseline(current_report)

    regression = service.compare_runs(
        actor=_actor(ProductRole.RELEASE_MANAGER),
        evaluation_run_id=current.evaluation_run_id,
        baseline_run_id=baseline.evaluation_run_id,
    )

    assert regression.metric_deltas.recall_at_5 == 0.055556
    assert regression.metric_deltas.recall_at_10 == 0.055556
    assert regression.counts.improved == 1
    assert regression.counts.regressed == 0
    assert regression.counts.unchanged == 17
    assert regression.case_diffs[0].change == "improved"
    assert regression.case_diffs[0].baseline_outcome == "expected_not_in_top_10"
    assert regression.case_diffs[0].current_outcome == "hit_top_5"


def test_environment_wiring_loads_the_packaged_ich_e9_suite() -> None:
    registered = _registered_evaluation_suites()

    assert len(registered) == 1
    assert registered[0].suite.suite_id == "ich-e9-retrieval-gold"
    assert registered[0].suite.version == "1.0.0"
    assert len(registered[0].suite.cases) == 18
    assert registered[0].sandbox_id == "sandbox-ich-e9-poc-v1"
