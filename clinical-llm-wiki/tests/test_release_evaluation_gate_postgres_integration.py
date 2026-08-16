"""Opt-in PostgreSQL acceptance for immutable synthetic EvaluationRun facts."""

from __future__ import annotations

import json
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import func, select

from service.db.models import EvaluationRun
from service.db.session import create_database_engine, create_session_factory
from service.evaluation.release_gate import (
    ReleaseEvaluationGateService,
    SyntheticEvaluationSuite,
)
from service.evaluation import EvaluationReport, SqlAlchemyEvaluationReadRepository


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="KNOWLEDGE_TEST_DATABASE_URL is required for PostgreSQL integration",
)


def _suite(*, minimum: float) -> SyntheticEvaluationSuite:
    return SyntheticEvaluationSuite(
        suite_id="synthetic-release-gate-db",
        version=f"v1-min-{minimum}",
        purpose="release_gate_synthetic",
        thresholds={"recall_at_5_min": minimum, "recall_at_10_min": 1.0},
        cases=(
            {"case_id": "db-1", "hit_at_5": True, "hit_at_10": True},
            {"case_id": "db-2", "hit_at_5": True, "hit_at_10": True},
            {"case_id": "db-3", "hit_at_5": True, "hit_at_10": True},
            {"case_id": "db-4", "hit_at_5": False, "hit_at_10": True},
        ),
    )


def test_postgres_evaluation_runs_are_replayable_immutable_and_release_neutral() -> None:
    assert TEST_DATABASE_URL is not None
    from service.evaluation.repository import (
        EvaluationRunImmutableError,
        SqlAlchemyEvaluationRunRepository,
    )

    os.environ["KNOWLEDGE_DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(Config(ROOT / "alembic.ini"), "head")
    engine = create_database_engine(TEST_DATABASE_URL)
    sessions = create_session_factory(engine)
    repository = SqlAlchemyEvaluationRunRepository(sessions)
    read_repository = SqlAlchemyEvaluationReadRepository(sessions)
    service = ReleaseEvaluationGateService(repository=repository)
    try:
        passed = service.evaluate(
            suite=_suite(minimum=0.75),
            target_id="candidate-release-db-pass",
        )
        replay = service.evaluate(
            suite=_suite(minimum=0.75),
            target_id="candidate-release-db-pass",
        )
        failed = service.evaluate(
            suite=_suite(minimum=1.0),
            target_id="candidate-release-db-fail",
        )
        report_payload = json.loads(
            (ROOT / "reports/p17/ich-e9-retrieval-baseline.json").read_text(
                encoding="utf-8"
            )
        )
        baseline_report = EvaluationReport.model_validate(
            report_payload["evaluation"]
        )
        baseline = read_repository.record_retrieval_baseline(baseline_report)
        baseline_replay = read_repository.record_retrieval_baseline(baseline_report)

        assert passed == replay
        assert repository.get(passed.evaluation_run_id) == passed
        assert failed.outcome == "failed"
        assert baseline == baseline_replay
        assert baseline.outcome == "informational"
        assert baseline.threshold_checks == ()
        baseline_rows, warnings = read_repository.list_runs(
            suite_id=baseline.suite_id,
            purpose="retrieval_baseline",
            outcome="informational",
        )
        assert baseline_rows == (baseline,)
        assert warnings == ()
        with sessions() as session:
            assert session.scalar(select(func.count()).select_from(EvaluationRun)) == 3
            rows = tuple(session.scalars(select(EvaluationRun)))
            assert all(row.release_id is None for row in rows)
            assert all(row.completed_at is not None for row in rows)
        with sessions.begin() as session:
            row = session.get(EvaluationRun, passed.evaluation_run_id)
            row.metrics = {**row.metrics, "outcome": "failed"}
        with pytest.raises(EvaluationRunImmutableError, match="drift"):
            repository.record(passed)
    finally:
        engine.dispose()
