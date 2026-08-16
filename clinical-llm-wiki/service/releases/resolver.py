"""Shared read-only application service for REST and MCP Release consumers."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from .contracts import ReleaseManifestPayload


class ReleasedKnowledgeUnavailableError(RuntimeError):
    """A requested immutable Release is absent or not published."""


class ReleasedManifestResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: str
    version: str
    manifest_sha256: str
    manifest: ReleaseManifestPayload


class ReleasedReleaseRepository(Protocol):
    def get_released(self, release_id: str | None = None): ...


class ImmutableReleaseResolver:
    def __init__(self, *, repository: ReleasedReleaseRepository) -> None:
        self._repository = repository

    def resolve(self, *, release_id: str | None = None) -> ReleasedManifestResult:
        prepared = self._repository.get_released(release_id)
        if prepared is None:
            target = release_id or "current"
            raise ReleasedKnowledgeUnavailableError(
                f"released knowledge is unavailable: {target}"
            )
        return ReleasedManifestResult(
            release_id=prepared.release_id,
            version=prepared.version,
            manifest_sha256=prepared.manifest_descriptor.sha256,
            manifest=prepared.manifest,
        )


class ReleaseMcpApplication:
    """Transport-neutral MCP tool adapter over the same immutable resolver."""

    def __init__(self, *, resolver: ImmutableReleaseResolver) -> None:
        self._resolver = resolver

    def resolve_released_knowledge(
        self,
        *,
        release_id: str | None = None,
    ) -> dict[str, object]:
        return self._resolver.resolve(release_id=release_id).model_dump(mode="json")


__all__ = [
    "ImmutableReleaseResolver",
    "ReleaseMcpApplication",
    "ReleasedKnowledgeUnavailableError",
    "ReleasedManifestResult",
]
