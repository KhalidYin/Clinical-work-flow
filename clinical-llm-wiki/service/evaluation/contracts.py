"""Machine-readable GoldCase and retrieval evaluation contracts."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from service.retrieval import RetrievalCapabilities


EVALUATION_NOTICE = (
    "single_document_retrieval_baseline_not_clinical_quality_certification"
)


class StrictEvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GoldCase(StrictEvaluationModel):
    case_id: str = Field(min_length=3, max_length=160)
    topic: str = Field(min_length=1, max_length=240)
    question: str = Field(min_length=3, max_length=500)
    expected_evidence_ids: tuple[str, ...] = Field(min_length=1, max_length=10)


class GoldSuite(StrictEvaluationModel):
    suite_id: str = Field(min_length=3, max_length=160)
    version: str = Field(min_length=1, max_length=120)
    document_id: Literal["ICH-E9-1998"]
    source_version_id: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_profile_id: str
    chunk_profile_version: str
    cases: tuple[GoldCase, ...] = Field(min_length=15, max_length=20)
    evaluation_notice: Literal[EVALUATION_NOTICE] = EVALUATION_NOTICE

    @model_validator(mode="after")
    def require_unique_case_ids(self) -> "GoldSuite":
        identifiers = [case.case_id for case in self.cases]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("GoldCase identifiers must be unique")
        return self


class RecallMetrics(StrictEvaluationModel):
    recall_at_5: float = Field(ge=0, le=1)
    recall_at_10: float = Field(ge=0, le=1)


class GoldCaseResult(StrictEvaluationModel):
    case_id: str
    topic: str
    question: str
    query_id: str
    expected_evidence_ids: tuple[str, ...]
    retrieved_chunk_ids: tuple[str, ...]
    retrieved_evidence_ids: tuple[str, ...]
    matched_expected_evidence_ids: tuple[str, ...]
    first_relevant_rank: int | None = Field(default=None, ge=1)
    hit_at_5: bool
    hit_at_10: bool
    outcome: Literal[
        "hit_top_5",
        "hit_top_10_only",
        "expected_not_in_top_10",
    ]
    failure_category: Literal[
        "none",
        "ranked_below_5",
        "expected_not_retrieved",
    ]


class EvaluationReport(StrictEvaluationModel):
    suite_id: str
    suite_version: str
    suite_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    document_id: Literal["ICH-E9-1998"]
    source_version_id: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_profile_id: str
    chunk_profile_version: str
    sandbox_id: str
    fusion_version: Literal["metadata-fts-weighted-v1"]
    case_count: int = Field(ge=15, le=20)
    metrics: RecallMetrics
    capabilities: RetrievalCapabilities
    case_results: tuple[GoldCaseResult, ...]
    external_model_requests: Literal[0] = 0
    evaluation_notice: Literal[EVALUATION_NOTICE] = EVALUATION_NOTICE


def gold_suite_sha256(suite: GoldSuite) -> str:
    payload = json.dumps(
        suite.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(payload).hexdigest()


__all__ = [
    "EVALUATION_NOTICE",
    "EvaluationReport",
    "GoldCase",
    "GoldCaseResult",
    "GoldSuite",
    "RecallMetrics",
    "gold_suite_sha256",
]
