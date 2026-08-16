"""Deterministic metadata + FTS retrieval orchestration without model calls."""

from __future__ import annotations

from typing import Protocol

from .contracts import (
    CandidateSearchRecord,
    CapabilityState,
    ChunkExplanation,
    ContextPackage,
    ReleaseCandidateScope,
    RetrievalCapabilities,
    RetrievalHit,
    RetrievalQuery,
    RetrievalResult,
    RouteContributions,
    retrieval_query_identity,
)


FUSION_VERSION = "metadata-fts-weighted-v1"
_CANDIDATE_MULTIPLIER = 5
_CAPABILITIES = RetrievalCapabilities(
    metadata=CapabilityState(status="available"),
    full_text=CapabilityState(status="available"),
    vector=CapabilityState(
        status="degraded",
        reason="embedding_profile_not_configured",
    ),
    relation=CapabilityState(
        status="degraded",
        reason="relation_route_not_enabled_for_e9_poc",
    ),
    generation=CapabilityState(
        status="disabled",
        reason="retrieval_baseline_makes_no_model_requests",
    ),
)


class CandidateSearchRepositoryPort(Protocol):
    def search_metadata_fts(
        self,
        *,
        query: str,
        scope: ReleaseCandidateScope,
        limit: int,
    ) -> list[CandidateSearchRecord]: ...


class RetrievalService:
    def __init__(self, *, repository: CandidateSearchRepositoryPort) -> None:
        self._repository = repository

    def query(self, request: RetrievalQuery) -> RetrievalResult:
        records = self._repository.search_metadata_fts(
            query=request.query,
            scope=request.scope,
            limit=min(250, request.top_k * _CANDIDATE_MULTIPLIER),
        )
        _validate_records(records, request.scope)
        ranked = sorted(
            records,
            key=lambda record: (
                -_fusion_score(record),
                -record.full_text_score,
                -record.metadata_score,
                record.ordinal,
                record.chunk_id,
            ),
        )[: request.top_k]
        hits = tuple(_hit(rank, record) for rank, record in enumerate(ranked, start=1))
        return RetrievalResult(
            query_id=retrieval_query_identity(request),
            capabilities=_CAPABILITIES,
            hits=hits,
            context_package=ContextPackage(
                sandbox_id=request.scope.sandbox_id,
                chunk_ids=tuple(hit.chunk_id for hit in hits),
                citations=tuple(citation for hit in hits for citation in hit.citations),
            ),
        )


def _fusion_score(record: CandidateSearchRecord) -> float:
    return round((0.8 * record.full_text_score) + (0.2 * record.metadata_score), 8)


def _hit(rank: int, record: CandidateSearchRecord) -> RetrievalHit:
    return RetrievalHit(
        rank=rank,
        chunk_id=record.chunk_id,
        content=record.content,
        content_sha256=record.content_sha256,
        fusion_score=_fusion_score(record),
        route_contributions=RouteContributions(
            metadata=record.metadata_score,
            full_text=record.full_text_score,
        ),
        explanation=ChunkExplanation(
            source_version_id=record.source_version_id,
            source_title=record.source_title,
            source_version=record.source_version,
            chunk_profile_id=record.chunk_profile_id,
            ordinal=record.ordinal,
            evidence_type=record.evidence_type,
            locator=record.locator,
            token_count=record.token_count,
        ),
        citations=record.citations,
    )


def _validate_records(
    records: list[CandidateSearchRecord],
    scope: ReleaseCandidateScope,
) -> None:
    seen: set[str] = set()
    allowed_versions = set(scope.source_version_ids)
    for record in records:
        if record.chunk_id in seen:
            raise ValueError("retrieval repository returned a duplicate chunk")
        seen.add(record.chunk_id)
        if (
            record.source_version_id not in allowed_versions
            or record.chunk_profile_id != scope.chunk_profile_id
        ):
            raise ValueError("retrieval repository returned a chunk outside sandbox scope")
        if not record.citations:
            raise ValueError("retrieval hit is missing canonical Evidence citation")
        if any(
            citation.source_version_id != record.source_version_id
            for citation in record.citations
        ):
            raise ValueError("retrieval citation is outside chunk source scope")


__all__ = ["CandidateSearchRepositoryPort", "FUSION_VERSION", "RetrievalService"]
