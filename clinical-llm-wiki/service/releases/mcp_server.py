"""Official MCP transport adapter for immutable Release resolution."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .resolver import ReleaseMcpApplication


def create_release_mcp_server(application: ReleaseMcpApplication) -> FastMCP:
    server = FastMCP("clinical-knowledge-releases")

    @server.tool(
        name="resolve_released_knowledge",
        description="Resolve one immutable published Knowledge Release by ID, or current.",
    )
    def resolve_released_knowledge(release_id: str | None = None) -> dict[str, object]:
        return application.resolve_released_knowledge(release_id=release_id)

    return server


__all__ = ["create_release_mcp_server"]
