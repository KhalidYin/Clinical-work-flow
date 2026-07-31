"""Provider-neutral read-only tool facade for MCP and other agent runtimes."""

from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from typing import Any, Mapping, Protocol

from service.auth import ActorContext
from service.retrieval import (
    HybridRetrievalService,
    ReleaseScope,
    RetrievalFilters,
    RetrievalRequest,
    RetrievalVisibility,
)


class CurrentReleasePort(Protocol):
    def current_release(self) -> ReleaseScope | None: ...


class ReadOnlyKnowledgeFacade:
    """Expose only governed read paths; it has no mutation or promotion methods."""

    def __init__(
        self,
        *,
        retrieval: HybridRetrievalService,
        release_repository: CurrentReleasePort,
        actor: ActorContext,
    ) -> None:
        self._retrieval = retrieval
        self._release_repository = release_repository
        self._actor = actor

    def search(
        self,
        *,
        query: str,
        visibility: str = "released",
        knowledge_types: list[str] | None = None,
        scope: Mapping[str, str] | None = None,
        source_version_ids: list[str] | None = None,
        rights_classifications: list[str] | None = None,
        limit: int = 10,
        relation_depth: int = 1,
        include_vector: bool = True,
    ) -> dict[str, Any]:
        result = self._retrieval.search(
            actor=self._actor,
            request=RetrievalRequest(
                query=query,
                visibility=RetrievalVisibility(visibility),
                filters=RetrievalFilters(
                    knowledge_types=tuple(knowledge_types or ()),
                    scope=dict(scope or {}),
                    source_version_ids=tuple(source_version_ids or ()),
                    rights_classifications=tuple(rights_classifications or ()),
                ),
                limit=limit,
                relation_depth=relation_depth,
                include_vector=include_vector,
            ),
        )
        return _jsonable(result)

    def get(
        self,
        *,
        knowledge_revision_id: str,
        visibility: str = "released",
    ) -> dict[str, Any]:
        trace = self._retrieval.get_revision(
            actor=self._actor,
            knowledge_revision_id=knowledge_revision_id,
            visibility=RetrievalVisibility(visibility),
        )
        document = trace.document
        return _jsonable(
            {
                "knowledge_revision_id": document.knowledge_revision_id,
                "knowledge_unit_id": document.knowledge_unit_id,
                "stable_key": document.stable_key,
                "knowledge_type": document.knowledge_type,
                "revision_number": document.revision_number,
                "claim": document.claim,
                "scope": document.scope,
                "applicability": document.applicability,
                "conditions": document.conditions,
                "exceptions": document.exceptions,
                "content_sha256": document.content_sha256,
                "visibility": trace.visibility,
                "release_ids": document.release_ids,
            }
        )

    def trace(
        self,
        *,
        knowledge_revision_id: str,
        visibility: str = "released",
    ) -> dict[str, Any]:
        trace = self._retrieval.get_revision(
            actor=self._actor,
            knowledge_revision_id=knowledge_revision_id,
            visibility=RetrievalVisibility(visibility),
        )
        return _jsonable(trace)

    def release_info(self) -> dict[str, Any]:
        release = self._release_repository.current_release()
        if release is None:
            return {
                "status": "not_released",
                "release_id": None,
                "version": None,
                "index_version": None,
            }
        return {
            "status": "released",
            "release_id": release.release_id,
            "version": release.version,
            "index_version": release.index_version,
        }


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value
