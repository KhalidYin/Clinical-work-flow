from __future__ import annotations

import pytest
from pydantic import ValidationError

from service.retrieval import (
    CandidateSearchRecord,
    EvidenceCitation,
    ReleaseCandidateScope,
    RetrievalQuery,
    RetrievalService,
)


def _citation(evidence_id: str) -> EvidenceCitation:
    return EvidenceCitation(
        evidence_id=evidence_id,
        source_version_id="srcv-e9",
        source_artifact_id="artifact-e9-original",
        locator={"kind": "page", "page": 8},
        content_sha256="a" * 64,
        start_offset=0,
        end_offset=24,
        span_role="primary",
    )


def _record(
    *,
    chunk_id: str,
    ordinal: int,
    metadata_score: float,
    full_text_score: float,
    citations: tuple[EvidenceCitation, ...] | None = None,
) -> CandidateSearchRecord:
    return CandidateSearchRecord(
        chunk_id=chunk_id,
        chunk_profile_id="chunk-profile-e9-v1",
        source_version_id="srcv-e9",
        source_title="ICH E9 Statistical Principles for Clinical Trials",
        source_version="1998",
        ordinal=ordinal,
        evidence_type="text",
        content=f"Deterministic content for {chunk_id}.",
        content_sha256=("b" if chunk_id == "chunk-b" else "c") * 64,
        token_count=8,
        locator={"kind": "page", "page": 8},
        metadata_score=metadata_score,
        full_text_score=full_text_score,
        citations=citations if citations is not None else (_citation(f"evidence-{chunk_id}"),),
    )


class FakeSearchRepository:
    def __init__(self, records: list[CandidateSearchRecord]) -> None:
        self.records = records
        self.calls: list[tuple[str, ReleaseCandidateScope, int]] = []

    def search_metadata_fts(
        self,
        *,
        query: str,
        scope: ReleaseCandidateScope,
        limit: int,
    ) -> list[CandidateSearchRecord]:
        self.calls.append((query, scope, limit))
        return self.records


def _query(*, top_k: int = 5) -> RetrievalQuery:
    return RetrievalQuery(
        query="randomisation bias statistical principles",
        top_k=top_k,
        scope=ReleaseCandidateScope(
            sandbox_id="sandbox-e9-poc",
            source_version_ids=("srcv-e9",),
            chunk_profile_id="chunk-profile-e9-v1",
        ),
    )


def test_scope_only_accepts_release_candidate_sandbox() -> None:
    with pytest.raises(ValidationError):
        ReleaseCandidateScope.model_validate(
            {
                "sandbox_kind": "current_release",
                "sandbox_id": "current",
                "source_version_ids": ["srcv-e9"],
                "chunk_profile_id": "chunk-profile-e9-v1",
            }
        )


def test_metadata_fts_result_is_deterministic_cited_and_explicitly_degraded() -> None:
    repository = FakeSearchRepository(
        [
            _record(
                chunk_id="chunk-b",
                ordinal=2,
                metadata_score=0.2,
                full_text_score=0.5,
            ),
            _record(
                chunk_id="chunk-a",
                ordinal=1,
                metadata_score=0.8,
                full_text_score=0.5,
            ),
        ]
    )
    service = RetrievalService(repository=repository)

    first = service.query(_query(top_k=2))
    repeated = service.query(_query(top_k=2))

    assert first == repeated
    assert [hit.chunk_id for hit in first.hits] == ["chunk-a", "chunk-b"]
    assert [hit.rank for hit in first.hits] == [1, 2]
    assert first.fusion_version == "metadata-fts-weighted-v1"
    assert first.capabilities.metadata.status == "available"
    assert first.capabilities.full_text.status == "available"
    assert first.capabilities.vector.status == "degraded"
    assert first.capabilities.vector.reason == "embedding_profile_not_configured"
    assert first.capabilities.relation.status == "degraded"
    assert all(hit.route_contributions.vector is None for hit in first.hits)
    assert all(hit.route_contributions.relation is None for hit in first.hits)
    assert all(hit.citations for hit in first.hits)
    assert first.context_package.citations == tuple(
        citation for hit in first.hits for citation in hit.citations
    )
    assert first.external_model_requests == 0
    assert repository.calls[0][2] > 2


def test_missing_or_out_of_scope_evidence_citation_fails_closed() -> None:
    uncited = _record(
        chunk_id="chunk-a",
        ordinal=1,
        metadata_score=0.1,
        full_text_score=0.9,
        citations=(),
    )
    with pytest.raises(ValueError, match="citation"):
        RetrievalService(repository=FakeSearchRepository([uncited])).query(_query())

    wrong_scope = uncited.model_copy(
        update={
            "citations": (
                _citation("evidence-wrong").model_copy(
                    update={"source_version_id": "srcv-outside"}
                ),
            )
        }
    )
    with pytest.raises(ValueError, match="scope"):
        RetrievalService(repository=FakeSearchRepository([wrong_scope])).query(_query())
