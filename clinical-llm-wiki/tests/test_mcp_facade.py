"""P3-A read-only MCP facade tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from service.auth import (
    ActorContext,
    IdentitySource,
    Permission,
    PrincipalType,
    ProductRole,
)
from service.mcp import ReadOnlyKnowledgeFacade
from service.mcp.server import build_mcp_server
from service.retrieval import (
    ChannelCandidate,
    Citation,
    HybridRetrievalService,
    ReleaseScope,
    RetrievalVisibility,
    RevisionDocument,
)


def _actor() -> ActorContext:
    return ActorContext(
        actor_id="mcp-consumer",
        display_name="MCP consumer",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({ProductRole.CONSUMER}),
        permissions=frozenset({Permission.QUERY_RELEASED}),
        identity_source=IdentitySource.LOCAL_TEST,
    )


def _document() -> RevisionDocument:
    return RevisionDocument(
        knowledge_unit_id="ku-released",
        stable_key="AE.TEAE.synthetic",
        knowledge_type="clinical_rule",
        knowledge_revision_id="revision-released",
        revision_number=1,
        revision_status="released",
        claim="Synthetic released TEAE claim.",
        scope={"domain": "AE"},
        applicability={"fixture": "P3-A"},
        conditions=(),
        exceptions=(),
        content_sha256="a" * 64,
        release_ids=("release-1",),
        citations=(
            Citation(
                evidence_id="evidence-1",
                source_id="source-1",
                source_title="Synthetic source",
                source_version_id="source-version-1",
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
class Repository:
    document: RevisionDocument

    def current_release(self):
        return ReleaseScope(
            release_id="release-1",
            version="1.0.0",
            index_version="index-1",
        )

    def index_version(self, *, visibility, release_scope):
        return release_scope.index_version if release_scope else "evaluation"

    def metadata_candidates(self, request, *, release_scope):
        return (ChannelCandidate(document=self.document, score=1.0),)

    def fts_candidates(self, request, *, release_scope):
        return ()

    def relation_candidates(
        self,
        *,
        seed_revision_ids,
        visibility,
        release_scope,
        depth,
        limit,
    ):
        return ()

    def get_revision(self, *, knowledge_revision_id, visibility, release_scope):
        if (
            knowledge_revision_id == self.document.knowledge_revision_id
            and visibility is RetrievalVisibility.RELEASED
        ):
            return self.document
        return None


def test_read_only_facade_search_get_trace_and_release_info() -> None:
    repository = Repository(document=_document())
    facade = ReadOnlyKnowledgeFacade(
        retrieval=HybridRetrievalService(repository=repository),
        release_repository=repository,
        actor=_actor(),
    )

    search = facade.search(query="TEAE", include_vector=False)
    detail = facade.get(knowledge_revision_id="revision-released")
    trace = facade.trace(knowledge_revision_id="revision-released")
    release = facade.release_info()

    assert search["hits"][0]["rank"] == 1
    assert search["hits"][0]["citations"][0]["evidence_id"] == "evidence-1"
    assert detail["knowledge_revision_id"] == "revision-released"
    assert trace["document"]["citations"][0]["source_id"] == "source-1"
    assert release == {
        "status": "released",
        "release_id": "release-1",
        "version": "1.0.0",
        "index_version": "index-1",
    }


def test_facade_has_no_mutation_tools() -> None:
    public_methods = {
        name
        for name in dir(ReadOnlyKnowledgeFacade)
        if not name.startswith("_") and callable(getattr(ReadOnlyKnowledgeFacade, name))
    }

    assert public_methods == {"get", "release_info", "search", "trace"}


def test_fastmcp_registry_exposes_only_four_read_tools() -> None:
    pytest.importorskip("mcp")
    repository = Repository(document=_document())
    facade = ReadOnlyKnowledgeFacade(
        retrieval=HybridRetrievalService(repository=repository),
        release_repository=repository,
        actor=_actor(),
    )
    server = build_mcp_server(facade)

    tools = asyncio.run(server.list_tools())

    assert {tool.name for tool in tools} == {
        "knowledge_get",
        "knowledge_release_info",
        "knowledge_search",
        "knowledge_trace",
    }
