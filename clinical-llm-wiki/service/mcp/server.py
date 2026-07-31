"""Local stdio MCP server backed by the same governed retrieval service."""

from __future__ import annotations

import os

from service.auth import resolve_human_actor
from service.db.session import (
    create_database_engine,
    create_session_factory,
    database_url_from_environment,
)
from service.platform_api.main import _local_identity_provider
from service.platform_api.repository import SqlAlchemyPlatformRepository
from service.retrieval import HybridRetrievalService, SqlAlchemyRetrievalRepository

from .facade import ReadOnlyKnowledgeFacade


def build_mcp_server(facade: ReadOnlyKnowledgeFacade):
    """Build the stable MCP v1 FastMCP server without adding write-capable tools."""

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised by optional install boundary
        raise RuntimeError(
            "MCP support is optional; install the project with the 'mcp' extra"
        ) from exc

    mcp = FastMCP("Clinical LLM Wiki")

    @mcp.tool()
    def knowledge_search(
        query: str,
        visibility: str = "released",
        knowledge_types: list[str] | None = None,
        scope: dict[str, str] | None = None,
        source_version_ids: list[str] | None = None,
        rights_classifications: list[str] | None = None,
        limit: int = 10,
        relation_depth: int = 1,
        include_vector: bool = True,
    ) -> dict:
        """Search governed knowledge with explainable backend-provided ranking."""

        return facade.search(
            query=query,
            visibility=visibility,
            knowledge_types=knowledge_types,
            scope=scope,
            source_version_ids=source_version_ids,
            rights_classifications=rights_classifications,
            limit=limit,
            relation_depth=relation_depth,
            include_vector=include_vector,
        )

    @mcp.tool()
    def knowledge_get(
        knowledge_revision_id: str,
        visibility: str = "released",
    ) -> dict:
        """Get one governed revision within the requested visibility boundary."""

        return facade.get(
            knowledge_revision_id=knowledge_revision_id,
            visibility=visibility,
        )

    @mcp.tool()
    def knowledge_trace(
        knowledge_revision_id: str,
        visibility: str = "released",
    ) -> dict:
        """Trace a visible revision to canonical Evidence and source locators."""

        return facade.trace(
            knowledge_revision_id=knowledge_revision_id,
            visibility=visibility,
        )

    @mcp.tool()
    def knowledge_release_info() -> dict:
        """Report the immutable Release currently visible to production consumers."""

        return facade.release_info()

    return mcp


def create_environment_facade() -> ReadOnlyKnowledgeFacade:
    """Resolve one local MCP session identity from an opaque environment token."""

    token = os.environ.get("KNOWLEDGE_MCP_BEARER_TOKEN")
    if not token:
        raise RuntimeError("KNOWLEDGE_MCP_BEARER_TOKEN is required")
    engine = create_database_engine(database_url_from_environment())
    sessions = create_session_factory(engine)
    platform_repository = SqlAlchemyPlatformRepository(sessions)
    assertion = _local_identity_provider().verify_bearer_token(token)
    actor = resolve_human_actor(assertion, platform_repository)
    retrieval_repository = SqlAlchemyRetrievalRepository(sessions)
    return ReadOnlyKnowledgeFacade(
        retrieval=HybridRetrievalService(repository=retrieval_repository),
        release_repository=retrieval_repository,
        actor=actor,
    )


def main() -> None:
    server = build_mcp_server(create_environment_facade())
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
