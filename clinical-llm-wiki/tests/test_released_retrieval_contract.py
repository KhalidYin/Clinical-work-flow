from __future__ import annotations

from types import SimpleNamespace

import pytest

from service.retrieval import (
    CandidateSearchRecord,
    EvidenceCitation,
    ImmutableReleaseRetrievalService,
    ReleasedRetrievalRequest,
)


def _citation(evidence_id: str = "evidence-e9") -> EvidenceCitation:
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


def _record(chunk_id: str) -> CandidateSearchRecord:
    return CandidateSearchRecord(
        chunk_id=chunk_id,
        chunk_profile_id="chunk-profile-e9-v1",
        source_version_id="srcv-e9",
        source_title="ICH E9 Statistical Principles for Clinical Trials",
        source_version="1998",
        ordinal=1,
        evidence_type="text",
        content="Randomisation protects against selection bias.",
        content_sha256="b" * 64,
        token_count=7,
        locator={"kind": "page", "page": 8},
        metadata_score=0.2,
        full_text_score=0.8,
        citations=(_citation(),),
    )


class FakeReleaseResolver:
    def __init__(self) -> None:
        self.requested_ids: list[str | None] = []

    def resolve(self, *, release_id: str | None = None):
        self.requested_ids.append(release_id)
        resolved_id = release_id or "release-current"
        return SimpleNamespace(
            release_id=resolved_id,
            version="2026.08.16",
            manifest=SimpleNamespace(
                chunk_profile_id="chunk-profile-e9-v1",
                items=(
                    SimpleNamespace(chunk_ids=("chunk-e9-001", "chunk-e9-002")),
                ),
            ),
        )


class FakeReleasedSearchRepository:
    def __init__(self, records: list[CandidateSearchRecord]) -> None:
        self.records = records
        self.calls: list[tuple[str, tuple[str, ...], str, int]] = []

    def search_released_metadata_fts(
        self,
        *,
        query: str,
        chunk_ids: tuple[str, ...],
        chunk_profile_id: str,
        limit: int,
    ) -> list[CandidateSearchRecord]:
        self.calls.append((query, chunk_ids, chunk_profile_id, limit))
        return self.records


def test_released_query_uses_only_frozen_manifest_membership_and_supports_replay() -> None:
    resolver = FakeReleaseResolver()
    repository = FakeReleasedSearchRepository([_record("chunk-e9-001")])
    service = ImmutableReleaseRetrievalService(
        resolver=resolver,
        repository=repository,
    )

    result = service.query(
        ReleasedRetrievalRequest(
            query="randomisation selection bias",
            top_k=5,
            release_id="release-historical",
        )
    )

    assert resolver.requested_ids == ["release-historical"]
    assert repository.calls[0][1] == ("chunk-e9-001", "chunk-e9-002")
    assert repository.calls[0][2] == "chunk-profile-e9-v1"
    assert result.release_id == "release-historical"
    assert result.release_version == "2026.08.16"
    assert result.context_package.scope_kind == "immutable_release"
    assert result.context_package.release_id == "release-historical"
    assert [hit.chunk_id for hit in result.hits] == ["chunk-e9-001"]
    assert result.capabilities.vector.status == "degraded"
    assert result.capabilities.relation.status == "degraded"
    assert result.external_model_requests == 0


def test_released_query_fails_closed_for_chunk_outside_manifest() -> None:
    service = ImmutableReleaseRetrievalService(
        resolver=FakeReleaseResolver(),
        repository=FakeReleasedSearchRepository([_record("chunk-unpublished")]),
    )

    with pytest.raises(ValueError, match="immutable Release"):
        service.query(ReleasedRetrievalRequest(query="randomisation", top_k=5))
