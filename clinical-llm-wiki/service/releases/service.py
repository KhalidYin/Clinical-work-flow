"""Application services for building and publishing immutable P17 Releases."""

from __future__ import annotations

import json
from typing import Protocol

from service.auth import (
    ActorContext,
    AuthorizationError,
    Permission,
    PrincipalType,
    ProductRole,
    WorkerPool,
    require_permission,
)
from service.evaluation import require_passed_evaluation
from service.object_store import ObjectDescriptor, ObjectIntegrityError, ObjectStorePort

from .contracts import (
    IndexManifestPayload,
    PreparedRelease,
    PublishedReleaseRecord,
    ReleaseBuildCommand,
    ReleaseBuildSnapshot,
    ReleaseManifestItem,
    ReleaseManifestPayload,
    ReleasePublishCommand,
)


class ReleaseBuildRepository(Protocol):
    def resolve_build(self, command: ReleaseBuildCommand) -> ReleaseBuildSnapshot: ...

    def record_candidate(
        self,
        *,
        command: ReleaseBuildCommand,
        prepared: PreparedRelease,
        actor_id: str,
    ) -> PreparedRelease: ...


class ReleasePublishRepository(Protocol):
    def get_candidate(self, release_id: str) -> PreparedRelease | None: ...

    def publish_candidate(
        self,
        *,
        command: ReleasePublishCommand,
        actor_id: str,
    ) -> PublishedReleaseRecord: ...


class ReleaseBuilder:
    def __init__(
        self,
        *,
        repository: ReleaseBuildRepository,
        object_store: ObjectStorePort,
    ) -> None:
        self._repository = repository
        self._object_store = object_store

    def build(
        self,
        *,
        actor: ActorContext,
        command: ReleaseBuildCommand,
    ) -> PreparedRelease:
        _require_release_worker(actor)
        snapshot = self._repository.resolve_build(command)
        if snapshot.current_release_id != command.base_release_id:
            raise ValueError("base Release no longer matches the current pointer")
        if snapshot.evaluation.evaluation_run_id != command.evaluation_run_id:
            raise ValueError("EvaluationRun does not match the build command")
        if snapshot.evaluation.target_id != command.release_candidate_id:
            raise ValueError("EvaluationRun target does not match the Release candidate")
        if snapshot.rotation_case_ids != command.rotation_case_ids:
            raise ValueError("resolved RotationCases do not match the build command")
        require_passed_evaluation(snapshot.evaluation)

        ordered_items = tuple(
            sorted(snapshot.items, key=lambda item: item.knowledge_revision_id)
        )
        index_manifest = IndexManifestPayload(
            release_id=command.release_candidate_id,
            release_version=command.version,
            capabilities=command.index_capabilities,
            embedding_profile_id=command.embedding_profile_id,
            relation_index_version=command.relation_index_version,
            revision_ids=tuple(item.knowledge_revision_id for item in ordered_items),
            chunk_ids=tuple(
                sorted({chunk_id for item in ordered_items for chunk_id in item.chunk_ids})
            ),
        )
        index_descriptor = self._put_json(
            object_key=f"releases/{command.release_candidate_id}/index.json",
            payload=index_manifest,
        )
        manifest = ReleaseManifestPayload(
            release_id=command.release_candidate_id,
            release_version=command.version,
            base_release_id=command.base_release_id,
            evaluation_run_id=command.evaluation_run_id,
            chunk_profile_id=command.chunk_profile_id,
            chunk_profile_version=snapshot.chunk_profile_version,
            rotation_case_ids=snapshot.rotation_case_ids,
            db_schema_revision=command.db_schema_revision,
            knowledge_contract_version=command.knowledge_contract_version,
            parser_profile_version=command.parser_profile_version,
            model_profile_version=command.model_profile_version,
            prompt_profile_version=command.prompt_profile_version,
            index_descriptor=index_descriptor,
            items=tuple(
                ReleaseManifestItem(**item.model_dump(mode="python"))
                for item in ordered_items
            ),
        )
        manifest_descriptor = self._put_json(
            object_key=f"releases/{command.release_candidate_id}/manifest.json",
            payload=manifest,
        )
        prepared = PreparedRelease(
            release_id=command.release_candidate_id,
            version=command.version,
            base_release_id=command.base_release_id,
            evaluation_run_id=command.evaluation_run_id,
            index_manifest=index_manifest,
            index_descriptor=index_descriptor,
            manifest=manifest,
            manifest_descriptor=manifest_descriptor,
        )
        return self._repository.record_candidate(
            command=command,
            prepared=prepared,
            actor_id=actor.actor_id,
        )

    def _put_json(self, *, object_key: str, payload: object) -> ObjectDescriptor:
        content = _canonical_json(payload)
        descriptor = self._object_store.put_bytes(
            object_key,
            content,
            media_type="application/json",
        )
        _verify_object(self._object_store, descriptor, content)
        return descriptor


class ReleasePublisher:
    def __init__(
        self,
        *,
        repository: ReleasePublishRepository,
        object_store: ObjectStorePort,
    ) -> None:
        self._repository = repository
        self._object_store = object_store

    def publish(
        self,
        *,
        actor: ActorContext,
        command: ReleasePublishCommand,
    ) -> PublishedReleaseRecord:
        _require_release_manager(actor)
        candidate = self._repository.get_candidate(command.release_id)
        if candidate is None:
            raise ValueError("Release candidate does not exist")
        if candidate.base_release_id != command.base_release_id:
            raise ValueError("publish base Release does not match the candidate")

        index_content = _canonical_json(candidate.index_manifest)
        _verify_object(self._object_store, candidate.index_descriptor, index_content)
        manifest_content = _canonical_json(candidate.manifest)
        _verify_object(self._object_store, candidate.manifest_descriptor, manifest_content)
        if candidate.manifest.index_descriptor != candidate.index_descriptor:
            raise ObjectIntegrityError("Release manifest index descriptor mismatch")
        return self._repository.publish_candidate(
            command=command,
            actor_id=actor.actor_id,
        )


def _require_release_worker(actor: ActorContext) -> None:
    if (
        actor.principal_type is not PrincipalType.SERVICE_ACCOUNT
        or actor.worker_pool is not WorkerPool.RELEASE
    ):
        raise AuthorizationError("Release worker service account is required")
    for permission in (
        Permission.RELEASE_BUILD,
        Permission.INDEX_BUILD,
        Permission.OBJECT_WRITE_DERIVED,
    ):
        require_permission(actor, permission)


def _require_release_manager(actor: ActorContext) -> None:
    if (
        actor.principal_type is not PrincipalType.HUMAN
        or ProductRole.RELEASE_MANAGER not in actor.roles
    ):
        raise AuthorizationError("human Release Manager is required")
    require_permission(actor, Permission.RELEASE_PUBLISH)


def _canonical_json(payload: object) -> bytes:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")  # type: ignore[union-attr]
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _verify_object(
    store: ObjectStorePort,
    descriptor: ObjectDescriptor,
    expected_content: bytes,
) -> None:
    if store.head(descriptor.object_key) != descriptor:
        raise ObjectIntegrityError(f"object descriptor mismatch: {descriptor.object_key}")
    if store.get_bytes(descriptor.object_key) != expected_content:
        raise ObjectIntegrityError(f"object bytes mismatch: {descriptor.object_key}")


__all__ = ["ReleaseBuilder", "ReleasePublisher"]
