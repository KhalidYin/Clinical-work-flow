"""Strict contracts for the P17 release-candidate retrieval sandbox."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictRetrievalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReleaseCandidateScope(StrictRetrievalModel):
    """Explicitly prevents POC content from being mistaken for a published Release."""

    sandbox_kind: Literal["release_candidate"] = "release_candidate"
    sandbox_id: str = Field(min_length=3, max_length=160)
    source_version_ids: tuple[str, ...] = Field(min_length=1, max_length=50)
    chunk_profile_id: str = Field(min_length=3, max_length=160)

    @field_validator("source_version_ids")
    @classmethod
    def normalize_source_versions(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted(set(value)))
        if not normalized or any(not item.strip() for item in normalized):
            raise ValueError("source_version_ids must contain non-empty identifiers")
        return normalized


class RetrievalQuery(StrictRetrievalModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=50)
    scope: ReleaseCandidateScope

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("query must contain searchable text")
        return normalized


class EvidenceCitation(StrictRetrievalModel):
    evidence_id: str
    source_version_id: str
    source_artifact_id: str
    locator: dict[str, object]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    span_role: Literal["primary", "overlap"]


class CandidateSearchRecord(StrictRetrievalModel):
    """Repository result before deterministic fusion and rank assignment."""

    chunk_id: str
    chunk_profile_id: str
    source_version_id: str
    source_title: str
    source_version: str
    ordinal: int = Field(ge=0)
    evidence_type: str
    content: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    token_count: int = Field(gt=0)
    locator: dict[str, object]
    metadata_score: float = Field(ge=0)
    full_text_score: float = Field(ge=0)
    citations: tuple[EvidenceCitation, ...]


class CapabilityState(StrictRetrievalModel):
    status: Literal["available", "degraded", "disabled"]
    reason: str | None = None


class RetrievalCapabilities(StrictRetrievalModel):
    metadata: CapabilityState
    full_text: CapabilityState
    vector: CapabilityState
    relation: CapabilityState
    generation: CapabilityState


class RouteContributions(StrictRetrievalModel):
    metadata: float = Field(ge=0)
    full_text: float = Field(ge=0)
    vector: None = None
    relation: None = None


class ChunkExplanation(StrictRetrievalModel):
    source_version_id: str
    source_title: str
    source_version: str
    chunk_profile_id: str
    ordinal: int = Field(ge=0)
    evidence_type: str
    locator: dict[str, object]
    token_count: int = Field(gt=0)


class RetrievalHit(StrictRetrievalModel):
    rank: int = Field(gt=0)
    chunk_id: str
    content: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fusion_score: float = Field(ge=0)
    route_contributions: RouteContributions
    explanation: ChunkExplanation
    citations: tuple[EvidenceCitation, ...] = Field(min_length=1)


class ContextPackage(StrictRetrievalModel):
    sandbox_kind: Literal["release_candidate"] = "release_candidate"
    sandbox_id: str
    chunk_ids: tuple[str, ...]
    citations: tuple[EvidenceCitation, ...]


class RetrievalResult(StrictRetrievalModel):
    query_id: str
    fusion_version: Literal["metadata-fts-weighted-v1"] = "metadata-fts-weighted-v1"
    capabilities: RetrievalCapabilities
    hits: tuple[RetrievalHit, ...]
    context_package: ContextPackage
    external_model_requests: Literal[0] = 0
    evaluation_notice: Literal[
        "single_document_retrieval_baseline_not_clinical_quality_certification"
    ] = "single_document_retrieval_baseline_not_clinical_quality_certification"


def retrieval_query_identity(query: RetrievalQuery) -> str:
    payload = json.dumps(
        query.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"query-{sha256(payload).hexdigest()[:32]}"


__all__ = [
    "CandidateSearchRecord",
    "CapabilityState",
    "ChunkExplanation",
    "ContextPackage",
    "EvidenceCitation",
    "ReleaseCandidateScope",
    "RetrievalCapabilities",
    "RetrievalHit",
    "RetrievalQuery",
    "RetrievalResult",
    "RouteContributions",
    "retrieval_query_identity",
]
