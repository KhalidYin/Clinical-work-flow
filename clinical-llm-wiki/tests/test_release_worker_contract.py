from __future__ import annotations

from hashlib import sha256
import json

from service.auth import (
    ActorContext,
    Permission,
    PrincipalType,
    ProductRole,
    WorkerPool,
)
from service.evaluation import ReleaseEvaluationGateService, SyntheticEvaluationSuite
from service.object_store import InMemoryObjectStore
from service.processing.contracts import ClaimedStepAttempt


class _EvaluationRepository:
    def record(self, run):
        return run


class _ReleaseRepository:
    def __init__(self, module) -> None:
        self.module = module
        self.prepared = None

    def resolve_build(self, command):
        evaluation = ReleaseEvaluationGateService(
            repository=_EvaluationRepository()
        ).evaluate(
            suite=SyntheticEvaluationSuite(
                suite_id="synthetic-release-worker",
                version="v1",
                purpose="release_gate_synthetic",
                thresholds={"recall_at_5_min": 0.5, "recall_at_10_min": 1.0},
                cases=(
                    {"case_id": "worker-1", "hit_at_5": True, "hit_at_10": True},
                    {"case_id": "worker-2", "hit_at_5": False, "hit_at_10": True},
                ),
            ),
            target_id=command.release_candidate_id,
        )
        assert evaluation.evaluation_run_id == command.evaluation_run_id
        return self.module.ReleaseBuildSnapshot(
            current_release_id=None,
            evaluation=evaluation,
            chunk_profile_version="worker-v1",
            items=(
                self.module.ReleaseItemSnapshot(
                    knowledge_revision_id="revision-worker-1",
                    content_sha256="a" * 64,
                    disposition="add",
                    evidence_ids=("evidence-worker-1",),
                    chunk_ids=("chunk-worker-1",),
                ),
            ),
            rotation_case_ids=(),
        )

    def record_candidate(self, *, command, prepared, actor_id: str):
        self.prepared = prepared
        return prepared


def test_release_worker_reads_hash_addressed_command_and_builds_candidate() -> None:
    from service import releases
    from service.processing.release_worker import (
        RELEASE_BUILD_STEP_KEY,
        ReleaseWorkerService,
        release_step_handlers,
    )

    objects = InMemoryObjectStore()
    repository = _ReleaseRepository(releases)
    evaluation = ReleaseEvaluationGateService(repository=_EvaluationRepository()).evaluate(
        suite=SyntheticEvaluationSuite(
            suite_id="synthetic-release-worker",
            version="v1",
            purpose="release_gate_synthetic",
            thresholds={"recall_at_5_min": 0.5, "recall_at_10_min": 1.0},
            cases=(
                {"case_id": "worker-1", "hit_at_5": True, "hit_at_10": True},
                {"case_id": "worker-2", "hit_at_5": False, "hit_at_10": True},
            ),
        ),
        target_id="release-worker-1",
    )
    command = releases.ReleaseBuildCommand(
        release_candidate_id="release-worker-1",
        version="worker.1",
        base_release_id=None,
        evaluation_run_id=evaluation.evaluation_run_id,
        chunk_profile_id="chunk-profile-worker-v1",
        rotation_case_ids=(),
        additional_revision_ids=("revision-worker-1",),
        index_capabilities={
            "metadata": "available",
            "full_text": "available",
            "vector": "degraded",
            "relation": "degraded",
        },
        db_schema_revision="20260816_0012",
        knowledge_contract_version="p17-v1",
        parser_profile_version="parser-v1",
        model_profile_version="replay-v1",
        prompt_profile_version="prompt-v1",
    )
    content = json.dumps(
        command.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = sha256(content).hexdigest()
    objects.put_bytes(
        f"release-requests/{digest}.json",
        content,
        media_type="application/json",
        expected_sha256=digest,
    )
    actor = ActorContext(
        actor_id="svc-release-worker",
        display_name="Release worker",
        principal_type=PrincipalType.SERVICE_ACCOUNT,
        roles=frozenset({ProductRole.SERVICE_ACCOUNT}),
        permissions=frozenset(
            {
                Permission.PROCESSING_EXECUTE,
                Permission.RELEASE_BUILD,
                Permission.INDEX_BUILD,
                Permission.OBJECT_WRITE_DERIVED,
            }
        ),
        worker_pool=WorkerPool.RELEASE,
    )
    service = ReleaseWorkerService(
        actor=actor,
        repository=repository,
        object_store=objects,
    )
    claim = ClaimedStepAttempt(
        run_id="run-release-worker",
        step_id="step-release-worker",
        step_key=RELEASE_BUILD_STEP_KEY,
        pool=WorkerPool.RELEASE,
        attempt_id="attempt-release-worker",
        attempt_number=1,
        input_sha256=digest,
    )

    outcome = release_step_handlers(service)[RELEASE_BUILD_STEP_KEY](
        type("Context", (), {"claim": claim})()
    )

    assert repository.prepared is not None
    assert outcome.output_sha256 == repository.prepared.manifest_descriptor.sha256
    assert outcome.artifact_manifest.artifacts == (
        repository.prepared.index_descriptor,
        repository.prepared.manifest_descriptor,
    )
