from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from importlib import import_module

import pytest

from service.auth import (
    ActorContext,
    AuthorizationError,
    IdentitySource,
    Permission,
    PrincipalType,
    ProductRole,
    WorkerPool,
)
from service.evaluation import ReleaseEvaluationGateService, SyntheticEvaluationSuite
from service.object_store import InMemoryObjectStore, ObjectIntegrityError


class _EvaluationRepository:
    def record(self, run):
        return run


def _passed_evaluation():
    suite = SyntheticEvaluationSuite(
        suite_id="synthetic-release-service",
        version="v1",
        purpose="release_gate_synthetic",
        thresholds={"recall_at_5_min": 0.5, "recall_at_10_min": 1.0},
        cases=(
            {"case_id": "release-1", "hit_at_5": True, "hit_at_10": True},
            {"case_id": "release-2", "hit_at_5": False, "hit_at_10": True},
        ),
    )
    return ReleaseEvaluationGateService(repository=_EvaluationRepository()).evaluate(
        suite=suite,
        target_id="release-candidate-synthetic-v2",
    )


def _failed_evaluation():
    suite = SyntheticEvaluationSuite(
        suite_id="synthetic-release-service-failed",
        version="v1",
        purpose="release_gate_synthetic",
        thresholds={"recall_at_5_min": 1.0, "recall_at_10_min": 1.0},
        cases=(
            {"case_id": "failed-1", "hit_at_5": True, "hit_at_10": True},
            {"case_id": "failed-2", "hit_at_5": False, "hit_at_10": True},
        ),
    )
    return ReleaseEvaluationGateService(repository=_EvaluationRepository()).evaluate(
        suite=suite,
        target_id="release-candidate-synthetic-v2",
    )


class FakeReleaseRepository:
    def __init__(self, module) -> None:
        self.module = module
        self.candidate = None
        self.build_actor_id = None
        self.publish_actor_id = None
        self.published = False

    def resolve_build(self, command):
        return self.module.ReleaseBuildSnapshot(
            current_release_id="release-synthetic-v1",
            evaluation=_passed_evaluation(),
            chunk_profile_version="synthetic-v1",
            items=(
                self.module.ReleaseItemSnapshot(
                    knowledge_revision_id="revision-synthetic-1",
                    content_sha256="a" * 64,
                    disposition="carry_forward",
                    evidence_ids=("evidence-synthetic-1",),
                    chunk_ids=("chunk-synthetic-1",),
                ),
            ),
            rotation_case_ids=("rotation-synthetic-safe",),
        )

    def record_candidate(self, *, command, prepared, actor_id: str):
        assert command.release_candidate_id == prepared.release_id
        self.build_actor_id = actor_id
        self.candidate = prepared
        return prepared

    def get_candidate(self, release_id: str):
        if self.candidate is not None and self.candidate.release_id == release_id:
            return self.candidate
        return None

    def publish_candidate(self, *, command, actor_id: str):
        assert self.candidate is not None
        assert command.release_id == self.candidate.release_id
        self.publish_actor_id = actor_id
        self.published = True
        return self.module.PublishedReleaseRecord(
            release_id=command.release_id,
            version=self.candidate.version,
            previous_release_id=command.base_release_id,
            manifest_object_key=self.candidate.manifest_descriptor.object_key,
            manifest_sha256=self.candidate.manifest_descriptor.sha256,
            index_manifest_version=self.candidate.index_manifest.version,
            published_at=datetime(2026, 8, 16, 6, 0, tzinfo=timezone.utc),
        )

    def get_released(self, release_id=None):
        if not self.published or self.candidate is None:
            return None
        if release_id is None or release_id == self.candidate.release_id:
            return self.candidate
        return None


class _TamperingObjectStore(InMemoryObjectStore):
    def __init__(self) -> None:
        super().__init__()
        self.tampered_keys: set[str] = set()

    def get_bytes(self, object_key: str) -> bytes:
        content = super().get_bytes(object_key)
        return content + b"tampered" if object_key in self.tampered_keys else content


class _FailedEvaluationReleaseRepository(FakeReleaseRepository):
    def resolve_build(self, command):
        return super().resolve_build(command).model_copy(
            update={"evaluation": _failed_evaluation()}
        )


def _worker() -> ActorContext:
    return ActorContext(
        actor_id="svc-release-test",
        display_name="Release worker",
        principal_type=PrincipalType.SERVICE_ACCOUNT,
        roles=frozenset({ProductRole.SERVICE_ACCOUNT}),
        permissions=frozenset(
            {
                Permission.RELEASE_BUILD,
                Permission.INDEX_BUILD,
                Permission.OBJECT_WRITE_DERIVED,
            }
        ),
        worker_pool=WorkerPool.RELEASE,
    )


def _manager() -> ActorContext:
    return ActorContext(
        actor_id="usr-release-manager",
        display_name="Release manager",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({ProductRole.RELEASE_MANAGER}),
        permissions=frozenset({Permission.RELEASE_PUBLISH}),
        identity_source=IdentitySource.LOCAL_TEST,
    )


def _command(module):
    return module.ReleaseBuildCommand(
        release_candidate_id="release-candidate-synthetic-v2",
        version="synthetic.2",
        base_release_id="release-synthetic-v1",
        evaluation_run_id=_passed_evaluation().evaluation_run_id,
        chunk_profile_id="chunk-profile-synthetic-v1",
        rotation_case_ids=("rotation-synthetic-safe",),
        additional_revision_ids=(),
        index_capabilities={
            "metadata": "available",
            "full_text": "available",
            "vector": "degraded",
            "relation": "degraded",
        },
        db_schema_revision="20260816_0012",
        knowledge_contract_version="p17-v1",
        parser_profile_version="parser-synthetic-v1",
        model_profile_version="replay-v1",
        prompt_profile_version="prompt-v1",
    )


def test_release_worker_builds_hash_verified_candidate_and_manager_publishes() -> None:
    module = import_module("service.releases")
    repository = FakeReleaseRepository(module)
    objects = InMemoryObjectStore()
    builder = module.ReleaseBuilder(repository=repository, object_store=objects)
    publisher = module.ReleasePublisher(repository=repository, object_store=objects)

    prepared = builder.build(actor=_worker(), command=_command(module))
    published = publisher.publish(
        actor=_manager(),
        command=module.ReleasePublishCommand(
            release_id=prepared.release_id,
            base_release_id="release-synthetic-v1",
        ),
    )

    assert repository.build_actor_id == "svc-release-test"
    assert repository.publish_actor_id == "usr-release-manager"
    assert objects.head(prepared.manifest_descriptor.object_key) == (
        prepared.manifest_descriptor
    )
    assert objects.head(prepared.index_descriptor.object_key) == prepared.index_descriptor
    assert prepared.manifest.evaluation_run_id == _passed_evaluation().evaluation_run_id
    assert prepared.manifest.items[0].evidence_ids == ("evidence-synthetic-1",)
    assert prepared.manifest.items[0].chunk_ids == ("chunk-synthetic-1",)
    assert published.release_id == prepared.release_id


def test_build_and_publish_keep_machine_and_human_authority_separate() -> None:
    module = import_module("service.releases")
    repository = FakeReleaseRepository(module)
    objects = InMemoryObjectStore()
    builder = module.ReleaseBuilder(repository=repository, object_store=objects)
    publisher = module.ReleasePublisher(repository=repository, object_store=objects)

    with pytest.raises(AuthorizationError, match="Release worker"):
        builder.build(actor=_manager(), command=_command(module))
    prepared = builder.build(actor=_worker(), command=_command(module))
    with pytest.raises(AuthorizationError, match="Release Manager"):
        publisher.publish(
            actor=_worker(),
            command=module.ReleasePublishCommand(
                release_id=prepared.release_id,
                base_release_id="release-synthetic-v1",
            ),
        )


def test_publish_rejects_object_bytes_changed_after_candidate_build() -> None:
    module = import_module("service.releases")
    repository = FakeReleaseRepository(module)
    objects = _TamperingObjectStore()
    builder = module.ReleaseBuilder(repository=repository, object_store=objects)
    publisher = module.ReleasePublisher(repository=repository, object_store=objects)

    prepared = builder.build(actor=_worker(), command=_command(module))
    objects.tampered_keys.add(prepared.manifest_descriptor.object_key)

    with pytest.raises(ObjectIntegrityError, match="object bytes mismatch"):
        publisher.publish(
            actor=_manager(),
            command=module.ReleasePublishCommand(
                release_id=prepared.release_id,
                base_release_id=prepared.base_release_id,
            ),
        )


def test_failed_evaluation_blocks_candidate_before_objects_are_written() -> None:
    module = import_module("service.releases")
    repository = _FailedEvaluationReleaseRepository(module)
    objects = InMemoryObjectStore()
    builder = module.ReleaseBuilder(repository=repository, object_store=objects)
    command = _command(module).model_copy(
        update={"evaluation_run_id": _failed_evaluation().evaluation_run_id}
    )

    with pytest.raises(module.EvaluationGateFailedError, match="evaluation Gate failed"):
        builder.build(actor=_worker(), command=command)
    assert repository.candidate is None


def test_rest_and_mcp_application_resolve_only_published_immutable_release() -> None:
    module = import_module("service.releases")
    repository = FakeReleaseRepository(module)
    objects = InMemoryObjectStore()
    builder = module.ReleaseBuilder(repository=repository, object_store=objects)
    publisher = module.ReleasePublisher(repository=repository, object_store=objects)
    resolver = module.ImmutableReleaseResolver(repository=repository)

    prepared = builder.build(actor=_worker(), command=_command(module))
    with pytest.raises(module.ReleasedKnowledgeUnavailableError):
        resolver.resolve(release_id=prepared.release_id)
    publisher.publish(
        actor=_manager(),
        command=module.ReleasePublishCommand(
            release_id=prepared.release_id,
            base_release_id=prepared.base_release_id,
        ),
    )

    rest_result = resolver.resolve(release_id=prepared.release_id)
    mcp_application = module.ReleaseMcpApplication(resolver=resolver)
    mcp_result = mcp_application.resolve_released_knowledge(
        release_id=prepared.release_id
    )
    assert mcp_result == rest_result.model_dump(mode="json")

    from service.releases.mcp_server import create_release_mcp_server

    server = create_release_mcp_server(mcp_application)
    tools = asyncio.run(server.list_tools())
    assert [tool.name for tool in tools] == ["resolve_released_knowledge"]
