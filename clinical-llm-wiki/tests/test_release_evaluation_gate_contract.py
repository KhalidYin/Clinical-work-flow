from __future__ import annotations

from importlib import import_module

import pytest


class FakeEvaluationRunRepository:
    def __init__(self) -> None:
        self.runs = {}
        self.write_count = 0

    def record(self, run):
        existing = self.runs.get(run.evaluation_run_id)
        if existing is not None:
            if existing != run:
                raise AssertionError("immutable EvaluationRun drift")
            return existing
        self.runs[run.evaluation_run_id] = run
        self.write_count += 1
        return run


def _module():
    return import_module("service.evaluation.release_gate")


def _suite(module, *, recall_5_min: float = 0.75):
    return module.SyntheticEvaluationSuite(
        suite_id="synthetic-release-gate",
        version="v1",
        purpose="release_gate_synthetic",
        thresholds={
            "recall_at_5_min": recall_5_min,
            "recall_at_10_min": 1.0,
        },
        cases=(
            {"case_id": "synthetic-1", "hit_at_5": True, "hit_at_10": True},
            {"case_id": "synthetic-2", "hit_at_5": True, "hit_at_10": True},
            {"case_id": "synthetic-3", "hit_at_5": True, "hit_at_10": True},
            {"case_id": "synthetic-4", "hit_at_5": False, "hit_at_10": True},
        ),
    )


def test_synthetic_threshold_produces_immutable_pass_and_failure_reasons() -> None:
    module = _module()
    repository = FakeEvaluationRunRepository()
    service = module.ReleaseEvaluationGateService(repository=repository)

    passed = service.evaluate(
        suite=_suite(module),
        target_id="release-candidate-synthetic-1",
    )
    failed = service.evaluate(
        suite=_suite(module, recall_5_min=1.0),
        target_id="release-candidate-synthetic-2",
    )

    assert passed.outcome == "passed"
    assert passed.metrics.recall_at_5 == 0.75
    assert passed.metrics.recall_at_10 == 1.0
    assert passed.failure_reasons == ()
    assert failed.outcome == "failed"
    assert failed.failure_reasons == ("recall_at_5_below_threshold",)
    assert passed.external_model_requests == 0
    assert passed.evaluation_notice == (
        "synthetic_release_gate_not_clinical_quality_certification"
    )


def test_evaluation_replay_is_stable_and_gate_fails_closed() -> None:
    module = _module()
    repository = FakeEvaluationRunRepository()
    service = module.ReleaseEvaluationGateService(repository=repository)
    suite = _suite(module)

    first = service.evaluate(suite=suite, target_id="release-candidate-synthetic-1")
    replay = service.evaluate(suite=suite, target_id="release-candidate-synthetic-1")

    assert first == replay
    assert repository.write_count == 1
    module.require_passed_evaluation(first)
    failed = service.evaluate(
        suite=_suite(module, recall_5_min=1.0),
        target_id="release-candidate-synthetic-fail",
    )
    with pytest.raises(module.EvaluationGateFailedError, match="recall_at_5"):
        module.require_passed_evaluation(failed)


def test_synthetic_suite_rejects_e9_or_inconsistent_hits() -> None:
    module = _module()
    payload = _suite(module).model_dump(mode="json")
    payload["suite_id"] = "ich-e9-release-gate"
    with pytest.raises(ValueError, match="synthetic"):
        module.SyntheticEvaluationSuite.model_validate(payload)

    payload = _suite(module).model_dump(mode="json")
    payload["cases"][0]["hit_at_5"] = True
    payload["cases"][0]["hit_at_10"] = False
    with pytest.raises(ValueError, match="Top-5"):
        module.SyntheticEvaluationSuite.model_validate(payload)
