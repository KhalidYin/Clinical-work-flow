"""Synthetic, deterministic EvaluationRun used by the P17 Release Gate."""

from __future__ import annotations

import json
from typing import Literal, Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, model_validator

from .contracts import RecallMetrics, StrictEvaluationModel


SYNTHETIC_EVALUATION_NOTICE = (
    "synthetic_release_gate_not_clinical_quality_certification"
)


class EvaluationGateFailedError(RuntimeError):
    """The selected immutable EvaluationRun did not pass its pinned thresholds."""


class SyntheticEvaluationCase(StrictEvaluationModel):
    case_id: str = Field(min_length=3, max_length=160)
    hit_at_5: bool
    hit_at_10: bool

    @model_validator(mode="after")
    def validate_hit_order(self) -> "SyntheticEvaluationCase":
        if self.hit_at_5 and not self.hit_at_10:
            raise ValueError("a Top-5 hit must also be a Top-10 hit")
        return self


class ReleaseGateThresholds(StrictEvaluationModel):
    recall_at_5_min: float = Field(ge=0, le=1)
    recall_at_10_min: float = Field(ge=0, le=1)


class SyntheticEvaluationSuite(StrictEvaluationModel):
    suite_id: str = Field(min_length=3, max_length=160)
    version: str = Field(min_length=1, max_length=120)
    purpose: Literal["release_gate_synthetic"]
    thresholds: ReleaseGateThresholds
    cases: tuple[SyntheticEvaluationCase, ...] = Field(min_length=2, max_length=50)

    @model_validator(mode="after")
    def validate_synthetic_identity(self) -> "SyntheticEvaluationSuite":
        normalized = self.suite_id.lower()
        if "synthetic" not in normalized or "e9" in normalized:
            raise ValueError("release threshold suite must be explicitly synthetic, not E9")
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("synthetic evaluation case IDs must be unique")
        return self


class EvaluationThresholdCheck(StrictEvaluationModel):
    metric: Literal["recall_at_5", "recall_at_10"]
    observed: float = Field(ge=0, le=1)
    minimum: float = Field(ge=0, le=1)
    passed: bool


class ReleaseEvaluationRun(StrictEvaluationModel):
    evaluation_run_id: str = Field(min_length=1, max_length=160)
    suite_id: str
    suite_version: str
    target_id: str = Field(min_length=1, max_length=160)
    status: Literal["completed"] = "completed"
    outcome: Literal["passed", "failed"]
    thresholds: ReleaseGateThresholds
    metrics: RecallMetrics
    checks: tuple[EvaluationThresholdCheck, ...]
    case_results: tuple[SyntheticEvaluationCase, ...]
    failure_reasons: tuple[
        Literal["recall_at_5_below_threshold", "recall_at_10_below_threshold"],
        ...,
    ]
    external_model_requests: Literal[0] = 0
    evaluation_notice: Literal[SYNTHETIC_EVALUATION_NOTICE] = (
        SYNTHETIC_EVALUATION_NOTICE
    )


class EvaluationRunRepository(Protocol):
    def record(self, run: ReleaseEvaluationRun) -> ReleaseEvaluationRun: ...


class ReleaseEvaluationGateService:
    def __init__(self, *, repository: EvaluationRunRepository) -> None:
        self._repository = repository

    def evaluate(
        self,
        *,
        suite: SyntheticEvaluationSuite,
        target_id: str,
    ) -> ReleaseEvaluationRun:
        if not target_id:
            raise ValueError("evaluation target_id is required")
        count = len(suite.cases)
        metrics = RecallMetrics(
            recall_at_5=round(sum(case.hit_at_5 for case in suite.cases) / count, 6),
            recall_at_10=round(
                sum(case.hit_at_10 for case in suite.cases) / count,
                6,
            ),
        )
        checks = (
            EvaluationThresholdCheck(
                metric="recall_at_5",
                observed=metrics.recall_at_5,
                minimum=suite.thresholds.recall_at_5_min,
                passed=metrics.recall_at_5 >= suite.thresholds.recall_at_5_min,
            ),
            EvaluationThresholdCheck(
                metric="recall_at_10",
                observed=metrics.recall_at_10,
                minimum=suite.thresholds.recall_at_10_min,
                passed=metrics.recall_at_10 >= suite.thresholds.recall_at_10_min,
            ),
        )
        failure_reasons = tuple(
            f"{check.metric}_below_threshold"
            for check in checks
            if not check.passed
        )
        identity = json.dumps(
            {
                "suite": suite.model_dump(mode="json"),
                "target_id": target_id,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        run = ReleaseEvaluationRun(
            evaluation_run_id=f"evaluation-{uuid5(NAMESPACE_URL, identity).hex}",
            suite_id=suite.suite_id,
            suite_version=suite.version,
            target_id=target_id,
            outcome="passed" if not failure_reasons else "failed",
            thresholds=suite.thresholds,
            metrics=metrics,
            checks=checks,
            case_results=suite.cases,
            failure_reasons=failure_reasons,
        )
        return self._repository.record(run)


def require_passed_evaluation(run: ReleaseEvaluationRun) -> None:
    if run.status != "completed" or run.outcome != "passed":
        reasons = ", ".join(run.failure_reasons) or "evaluation_not_completed"
        raise EvaluationGateFailedError(f"evaluation Gate failed: {reasons}")


__all__ = [
    "EvaluationGateFailedError",
    "EvaluationThresholdCheck",
    "ReleaseEvaluationGateService",
    "ReleaseEvaluationRun",
    "ReleaseGateThresholds",
    "SYNTHETIC_EVALUATION_NOTICE",
    "SyntheticEvaluationCase",
    "SyntheticEvaluationSuite",
    "require_passed_evaluation",
]
