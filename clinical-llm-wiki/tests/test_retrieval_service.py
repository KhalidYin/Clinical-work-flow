"""P3-A explainable retrieval policy and fusion tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from service.auth import (
    ActorContext,
    AuthorizationError,
    IdentitySource,
    Permission,
    PrincipalType,
    ProductRole,
)
from service.context import ContextPackageBuilder
from service.retrieval import (
    CapabilityState,
    ChannelCandidate,
    Citation,
    HybridRetrievalService,
    ReleaseScope,
    RetrievalChannel,
    RetrievalChannelUnavailable,
    RetrievalFilters,
    RetrievalRequest,
    RetrievalVisibility,
    RevisionDocument,
    VectorProviderStatus,
)


def _actor(*permissions: Permission) -> ActorContext:
    return ActorContext(
        actor_id="actor-retrieval-test",
        display_name="Retrieval test actor",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({ProductRole.RELEASE_MANAGER}),
        permissions=frozenset(permissions),
        identity_source=IdentitySource.LOCAL_TEST,
    )


def _document(
    revision_id: str,
    *,
    stable_key: str,
    claim: str,
    release_ids: tuple[str, ...] = (),
) -> RevisionDocument:
    return RevisionDocument(
        knowledge_unit_id=f"ku-{revision_id}",
        stable_key=stable_key,
        knowledge_type="clinical_rule",
        knowledge_revision_id=revision_id,
        revision_number=1,
        revision_status="released" if release_ids else "approved",
        claim=claim,
        scope={"domain": "AE", "standard": "synthetic"},
        applicability={"fixture": "P3-A"},
        conditions=(),
        exceptions=(),
        content_sha256="a" * 64,
        release_ids=release_ids,
        citations=(
            Citation(
                evidence_id=f"evidence-{revision_id}",
                source_id="source-fixture",
                source_title="Synthetic retrieval fixture",
                source_version_id="source-version-fixture",
                source_version="1.0",
                locator={"kind": "line_range", "start_line": 1, "end_line": 2},
                content_sha256="b" * 64,
                source_sha256="c" * 64,
                rights_classification="internal",
                citation_required=True,
            ),
        ),
    )


@dataclass
class FakeRepository:
    release: ReleaseScope | None = None
    metadata: tuple[ChannelCandidate, ...] = ()
    fts: tuple[ChannelCandidate, ...] = ()
    relations: tuple[ChannelCandidate, ...] = ()
    fts_failure: str | None = None

    def current_release(self):
        return self.release

    def index_version(self, *, visibility, release_scope):
        if release_scope:
            return release_scope.index_version
        return "evaluation-direct@test"

    def metadata_candidates(self, request, *, release_scope):
        return self.metadata

    def fts_candidates(self, request, *, release_scope):
        if self.fts_failure:
            raise RetrievalChannelUnavailable(
                RetrievalChannel.FTS,
                reason=self.fts_failure,
            )
        return self.fts

    def relation_candidates(
        self,
        *,
        seed_revision_ids,
        visibility,
        release_scope,
        depth,
        limit,
    ):
        return self.relations

    def get_revision(self, *, knowledge_revision_id, visibility, release_scope):
        documents = {
            candidate.document.knowledge_revision_id: candidate.document
            for candidate in (*self.metadata, *self.fts, *self.relations)
        }
        return documents.get(knowledge_revision_id)


@dataclass
class FakeVectorProvider:
    vector_candidates: tuple[ChannelCandidate, ...]
    provider_status: VectorProviderStatus = VectorProviderStatus(
        state=CapabilityState.AVAILABLE,
        version="fixture-embedding@1.0.0",
    )

    def status(self):
        return self.provider_status

    def candidates(self, request, *, release_scope):
        return self.vector_candidates


def test_released_query_fails_closed_when_there_is_no_current_release() -> None:
    approved = _document(
        "revision-approved",
        stable_key="AE.TEAE.synthetic",
        claim="Approved but not released.",
    )
    service = HybridRetrievalService(
        repository=FakeRepository(
            metadata=(ChannelCandidate(document=approved, score=1.0),),
        )
    )

    result = service.search(
        actor=_actor(Permission.QUERY_RELEASED),
        request=RetrievalRequest(query="TEAE"),
    )

    assert result.hits == ()
    assert result.partial is True
    assert [gap.code for gap in result.gaps] == ["no_current_release"]
    assert {channel.reason for channel in result.plan.channels} == {
        "no_current_release"
    }


def test_evaluation_visibility_requires_release_manager_permission() -> None:
    service = HybridRetrievalService(repository=FakeRepository())

    with pytest.raises(AuthorizationError):
        service.search(
            actor=_actor(Permission.QUERY_RELEASED),
            request=RetrievalRequest(
                query="TEAE",
                visibility=RetrievalVisibility.EVALUATION,
            ),
        )


def test_exact_vector_and_relation_channels_are_explainably_fused() -> None:
    exact = _document(
        "revision-exact",
        stable_key="AE.TEAE.synthetic",
        claim="Treatment-emergent adverse event rule.",
    )
    paraphrase = _document(
        "revision-paraphrase",
        stable_key="AE.ONSET.synthetic",
        claim="Event onset is bounded by the treatment window.",
    )
    related = _document(
        "revision-related",
        stable_key="AE.TREATMENT-WINDOW.synthetic",
        claim="The treatment window ends after the last dose.",
    )
    service = HybridRetrievalService(
        repository=FakeRepository(
            metadata=(ChannelCandidate(document=exact, score=1.0),),
            fts=(ChannelCandidate(document=exact, score=0.72),),
            relations=(
                ChannelCandidate(
                    document=related,
                    score=1.0,
                    relation_paths=(
                        (
                            exact.stable_key,
                            "depends_on",
                            related.stable_key,
                        ),
                    ),
                ),
            ),
        ),
        vector_provider=FakeVectorProvider(
            vector_candidates=(
                ChannelCandidate(document=paraphrase, score=0.91),
            )
        ),
    )

    result = service.search(
        actor=_actor(Permission.EVALUATION_RUN),
        request=RetrievalRequest(
            query="events beginning during treatment",
            visibility=RetrievalVisibility.EVALUATION,
            filters=RetrievalFilters(scope={"domain": "AE"}),
            relation_depth=1,
        ),
    )

    assert [hit.knowledge_revision_id for hit in result.hits] == [
        "revision-exact",
        "revision-paraphrase",
        "revision-related",
    ]
    assert [item.channel for item in result.hits[0].channel_contributions] == [
        RetrievalChannel.METADATA,
        RetrievalChannel.FTS,
    ]
    assert result.hits[2].relation_paths == (
        (
            "AE.TEAE.synthetic",
            "depends_on",
            "AE.TREATMENT-WINDOW.synthetic",
        ),
    )
    assert result.plan.policy_version == "rrf-neutral@1.0.0"
    assert result.partial is False


def test_missing_vector_and_failed_fts_are_explicit_partial_capabilities() -> None:
    document = _document(
        "revision-metadata",
        stable_key="AE.AESEQ.synthetic",
        claim="AE sequence identifier.",
    )
    service = HybridRetrievalService(
        repository=FakeRepository(
            metadata=(ChannelCandidate(document=document, score=0.9),),
            fts_failure="postgres_fts_unavailable",
        ),
    )

    result = service.search(
        actor=_actor(Permission.EVALUATION_RUN),
        request=RetrievalRequest(
            query="AESEQ",
            visibility=RetrievalVisibility.EVALUATION,
        ),
    )

    assert [hit.knowledge_revision_id for hit in result.hits] == [
        "revision-metadata"
    ]
    assert result.partial is True
    assert {gap.code for gap in result.gaps} == {
        "fts_unavailable",
        "vector_disabled",
    }
    capabilities = {item.channel: item for item in result.plan.channels}
    assert capabilities[RetrievalChannel.FTS].state is CapabilityState.UNAVAILABLE
    assert capabilities[RetrievalChannel.VECTOR].state is CapabilityState.DISABLED


def test_negative_evaluation_query_returns_explicit_gap() -> None:
    service = HybridRetrievalService(repository=FakeRepository())

    result = service.search(
        actor=_actor(Permission.EVALUATION_RUN),
        request=RetrievalRequest(
            query="nonexistent sponsor convention",
            visibility=RetrievalVisibility.EVALUATION,
            include_vector=False,
            relation_depth=0,
        ),
    )

    assert result.hits == ()
    assert [gap.code for gap in result.gaps] == [
        "no_matching_approved_knowledge"
    ]
    assert result.partial is False


def test_context_package_preserves_query_plan_citations_and_truncation() -> None:
    first = _document(
        "revision-first",
        stable_key="AE.FIRST.synthetic",
        claim="First evidence-grounded claim.",
    )
    second = _document(
        "revision-second",
        stable_key="AE.SECOND.synthetic",
        claim="Second evidence-grounded claim.",
    )
    service = HybridRetrievalService(
        repository=FakeRepository(
            metadata=(
                ChannelCandidate(document=first, score=1.0),
                ChannelCandidate(document=second, score=0.9),
            ),
        )
    )
    result = service.search(
        actor=_actor(Permission.EVALUATION_RUN),
        request=RetrievalRequest(
            query="synthetic",
            visibility=RetrievalVisibility.EVALUATION,
            include_vector=False,
            relation_depth=0,
        ),
    )

    package = ContextPackageBuilder().build(
        result,
        max_hits=1,
        max_characters=2_000,
    )

    assert package.query_plan.query_id == result.plan.query_id
    assert package.items[0].citations[0].evidence_id == "evidence-revision-first"
    assert "AE.FIRST.synthetic" in package.rendered_text
    assert "evidence-revision-first" in package.rendered_text
    assert package.truncated is True
    assert package.partial is True
