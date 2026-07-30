from __future__ import annotations

from collections import deque
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
import pytest

from service.auth import (
    ActorContext,
    AuthorizationError,
    GrantStatus,
    PrincipalType,
    ServiceAccountGrant,
    WORKER_POOL_PERMISSIONS,
    WorkerPool,
    resolve_service_account_actor,
)
from service.processing.contracts import (
    ArtifactManifest,
    ClaimedStepAttempt,
    StepDefinition,
    StepOutcome,
    processing_runtime_contract_json_schema,
    validate_step_graph,
)
from service.processing.worker import MultiPoolWorkerRuntime, WorkerRuntime


ROOT = Path(__file__).resolve().parents[1]


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _actor(pool: WorkerPool) -> ActorContext:
    return resolve_service_account_actor(
        ServiceAccountGrant(
            service_account_id=f"svc-{pool.value}",
            display_name=f"{pool.value.title()} Worker",
            worker_pool=pool,
            scopes=WORKER_POOL_PERMISSIONS[pool],
            secret_ref=f"env://P12_{pool.value.upper()}_WORKER_TOKEN",
            status=GrantStatus.ACTIVE,
        )
    )


class FakeLedger:
    def __init__(self, claims: list[ClaimedStepAttempt]) -> None:
        self.claims = deque(claims)
        self.completed: list[tuple[str, str]] = []
        self.failed: list[tuple[str, str, str]] = []
        self.checkpoints: list[tuple[str, dict[str, Any]]] = []
        self.claim_calls = 0
        self.recovery_calls = 0

    def recover_expired_leases(self, **_: object) -> int:
        self.recovery_calls += 1
        return 0

    def claim_next(
        self,
        *,
        actor: ActorContext,
        worker_id: str,
        supported_step_keys: frozenset[str],
        lease_seconds: int,
    ) -> ClaimedStepAttempt | None:
        del actor, worker_id, lease_seconds
        self.claim_calls += 1
        for claim in list(self.claims):
            if claim.step_key in supported_step_keys:
                self.claims.remove(claim)
                return claim
        return None

    def heartbeat(self, **_: object) -> None:
        return None

    def save_checkpoint(
        self,
        *,
        attempt_id: str,
        checkpoint: dict[str, Any],
        **_: object,
    ) -> None:
        self.checkpoints.append((attempt_id, checkpoint))

    def complete_attempt(
        self,
        *,
        attempt_id: str,
        outcome: StepOutcome,
        **_: object,
    ) -> None:
        self.completed.append((attempt_id, outcome.output_sha256))

    def fail_attempt(
        self,
        *,
        attempt_id: str,
        error_type: str,
        error_message: str,
        **_: object,
    ) -> None:
        self.failed.append((attempt_id, error_type, error_message))


def _claim(pool: WorkerPool, step_key: str, ordinal: int) -> ClaimedStepAttempt:
    return ClaimedStepAttempt(
        run_id="run-contract",
        step_id=f"step-{ordinal}",
        step_key=step_key,
        pool=pool,
        attempt_id=f"attempt-{ordinal}",
        attempt_number=1,
        previous_attempt_id=None,
        input_sha256=_hash(f"input-{ordinal}"),
        checkpoint=None,
    )


def _handler(context) -> StepOutcome:
    context.checkpoint({"phase": "done"})
    return StepOutcome(
        output_sha256=_hash(context.claim.step_key),
        artifact_manifest=ArtifactManifest(artifacts=[]),
    )


def test_step_graph_requires_known_acyclic_dependencies() -> None:
    valid = [
        StepDefinition(
            step_key="parse",
            pool=WorkerPool.DOCUMENT,
            input_sha256=_hash("source"),
        ),
        StepDefinition(
            step_key="extract",
            pool=WorkerPool.ENRICHMENT,
            input_sha256=_hash("evidence"),
            depends_on=["parse"],
        ),
    ]
    assert validate_step_graph(valid) == tuple(valid)

    with pytest.raises(ValueError, match="unknown dependency"):
        validate_step_graph(
            [
                StepDefinition(
                    step_key="extract",
                    pool=WorkerPool.ENRICHMENT,
                    input_sha256=_hash("evidence"),
                    depends_on=["missing"],
                )
            ]
        )

    with pytest.raises(ValueError, match="cycle"):
        validate_step_graph(
            [
                StepDefinition(
                    step_key="a",
                    pool=WorkerPool.DOCUMENT,
                    input_sha256=_hash("a"),
                    depends_on=["b"],
                ),
                StepDefinition(
                    step_key="b",
                    pool=WorkerPool.DOCUMENT,
                    input_sha256=_hash("b"),
                    depends_on=["a"],
                ),
            ]
        )


def test_single_process_multi_pool_and_separate_runtimes_share_semantics() -> None:
    claims = [
        _claim(WorkerPool.DOCUMENT, "parse", 1),
        _claim(WorkerPool.ENRICHMENT, "extract", 2),
        _claim(WorkerPool.RELEASE, "build", 3),
    ]

    def execute(multi_process: bool) -> list[tuple[str, str]]:
        ledger = FakeLedger(claims.copy())
        runtimes = [
            WorkerRuntime(
                ledger=ledger,
                actor=_actor(claim.pool),
                worker_id=f"{claim.pool.value}-1",
                handlers={claim.step_key: _handler},
            )
            for claim in claims
        ]
        if multi_process:
            for runtime in runtimes:
                assert runtime.run_once() is True
        else:
            coordinator = MultiPoolWorkerRuntime(runtimes)
            assert coordinator.run_once() == 3
        assert len(ledger.checkpoints) == 3
        assert ledger.recovery_calls == 3
        return sorted(ledger.completed)

    assert execute(multi_process=False) == execute(multi_process=True)


def test_worker_refuses_human_or_cross_pool_actor_before_claim() -> None:
    ledger = FakeLedger([_claim(WorkerPool.DOCUMENT, "parse", 1)])
    human = ActorContext(
        actor_id="usr-curator",
        display_name="Curator",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({"knowledge_curator"}),
        permissions=frozenset({"processing:execute"}),
        identity_source="local_test",
    )

    with pytest.raises(AuthorizationError, match="service account"):
        WorkerRuntime(
            ledger=ledger,
            actor=human,
            worker_id="human-worker",
            handlers={"parse": _handler},
        )

    with pytest.raises(AuthorizationError, match="pool"):
        WorkerRuntime(
            ledger=ledger,
            actor=_actor(WorkerPool.ENRICHMENT),
            worker_id="wrong-pool",
            handlers={"parse": _handler},
            pool=WorkerPool.DOCUMENT,
        )
    assert ledger.claim_calls == 0


def test_worker_does_not_claim_when_no_p1_handler_is_registered() -> None:
    ledger = FakeLedger([_claim(WorkerPool.DOCUMENT, "future-p2-step", 1)])
    runtime = WorkerRuntime(
        ledger=ledger,
        actor=_actor(WorkerPool.DOCUMENT),
        worker_id="document-idle",
        handlers={},
    )

    assert runtime.run_once() is False
    assert ledger.claim_calls == 0
    assert ledger.recovery_calls == 0


def test_handler_failure_is_recorded_without_exception_content() -> None:
    ledger = FakeLedger([_claim(WorkerPool.DOCUMENT, "parse", 1)])

    def fail_handler(_context) -> StepOutcome:
        raise RuntimeError("credential=do-not-log")

    runtime = WorkerRuntime(
        ledger=ledger,
        actor=_actor(WorkerPool.DOCUMENT),
        worker_id="document-1",
        handlers={"parse": fail_handler},
    )

    assert runtime.run_once() is True
    assert ledger.failed == [
        ("attempt-1", "handler_error", "handler_error: RuntimeError")
    ]


def test_checked_in_processing_runtime_schema_matches_runtime_contract() -> None:
    checked_in = json.loads(
        (
            ROOT
            / "schemas"
            / "application"
            / "processing-runtime.prerelease.schema.json"
        ).read_text(encoding="utf-8")
    )
    runtime = processing_runtime_contract_json_schema()

    Draft202012Validator.check_schema(checked_in)
    assert checked_in == runtime
    serialized = json.dumps(checked_in)
    assert set(checked_in["$defs"]["RunStatus"]["enum"]) == {
        "queued",
        "processing",
        "author_confirmation_required",
        "review_required",
        "approved",
        "release_blocked",
        "released",
        "failed",
        "cancelled",
    }
    assert "metadata" not in checked_in["$defs"]["ArtifactManifest"]["properties"]
    assert all(
        forbidden not in serialized
        for forbidden in ("absolute_path", "provider_url", "study_id", "workflow_id")
    )
