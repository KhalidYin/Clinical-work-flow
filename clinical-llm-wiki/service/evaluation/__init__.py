"""P17 retrieval evaluation public API."""

from .contracts import (
    EVALUATION_NOTICE,
    EvaluationReport,
    GoldCase,
    GoldCaseResult,
    GoldSuite,
    RecallMetrics,
    gold_suite_sha256,
)
from .service import EvaluationService, RetrievalQueryPort
from .release_gate import (
    EvaluationGateFailedError,
    EvaluationThresholdCheck,
    ReleaseEvaluationGateService,
    ReleaseEvaluationRun,
    ReleaseGateThresholds,
    SYNTHETIC_EVALUATION_NOTICE,
    SyntheticEvaluationCase,
    SyntheticEvaluationSuite,
    require_passed_evaluation,
)
from .repository import EvaluationRunImmutableError, SqlAlchemyEvaluationRunRepository
from .read_model import (
    EvaluationCaseReadRecord,
    EvaluationOutcome,
    EvaluationPurpose,
    EvaluationReadIntegrityError,
    EvaluationReadPort,
    EvaluationReadRecord,
    EvaluationThresholdReadRecord,
    RetrievalBaselineRun,
    SqlAlchemyEvaluationReadRepository,
)

__all__ = [
    "EVALUATION_NOTICE",
    "EvaluationReport",
    "EvaluationService",
    "EvaluationGateFailedError",
    "EvaluationCaseReadRecord",
    "EvaluationOutcome",
    "EvaluationPurpose",
    "EvaluationReadIntegrityError",
    "EvaluationReadPort",
    "EvaluationReadRecord",
    "EvaluationRunImmutableError",
    "EvaluationThresholdReadRecord",
    "EvaluationThresholdCheck",
    "GoldCase",
    "GoldCaseResult",
    "GoldSuite",
    "RecallMetrics",
    "ReleaseEvaluationGateService",
    "ReleaseEvaluationRun",
    "ReleaseGateThresholds",
    "RetrievalQueryPort",
    "RetrievalBaselineRun",
    "SYNTHETIC_EVALUATION_NOTICE",
    "SyntheticEvaluationCase",
    "SyntheticEvaluationSuite",
    "SqlAlchemyEvaluationRunRepository",
    "SqlAlchemyEvaluationReadRepository",
    "gold_suite_sha256",
    "require_passed_evaluation",
]
