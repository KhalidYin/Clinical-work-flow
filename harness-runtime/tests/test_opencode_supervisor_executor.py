from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from supervisor.container_runtime import DaemonRootPathMapper, ManagedContainer
from contracts.receipt import ExitClassification
from contracts.result import HarnessStatus
from supervisor.fake_container_runtime import FakeContainerRuntime
from supervisor.service_contracts import SupervisorAttemptRequest, canonical_sha256


IMAGE_REF = "ghcr.io/anomalyco/opencode:1.18.14@sha256:" + "b" * 64
SPEC_SHA256 = "a" * 64
SYNTHETIC_SECRET = "synthetic-offline-secret-marker"


class ManagedFakeRuntime(FakeContainerRuntime):
    def __init__(self) -> None:
        super().__init__(exit_code=None, hangs=True)
        self.managed = (
            ManagedContainer(
                container_id="managed-container-1",
                attempt_id="attempt-001",
                request_sha256=_attempt().request_sha256(),
                spec_sha256=SPEC_SHA256,
            ),
        )
        self.terminated_ids: list[str] = []
        self.removed_ids: list[str] = []

    def list_managed(self) -> tuple[ManagedContainer, ...]:
        return self.managed

    def terminate(self, container_id: str) -> None:
        self.terminated_ids.append(container_id)

    def remove(self, container_id: str) -> None:
        self.removed_ids.append(container_id)


def _attempt() -> SupervisorAttemptRequest:
    input_bundle = {
        "system_instruction": "Return one JSON object.",
        "output_schema": {"type": "object"},
        "messages": [{"role": "user", "content": "offline synthetic evidence"}],
        "data_boundary": "provider_approved",
        "provider": "synthetic",
        "model": "invalid-offline-model",
    }
    return SupervisorAttemptRequest(
        attempt_id="attempt-001",
        run_id="run-001",
        step_id="enrichment",
        generation_token="generation-001",
        fencing_token="fencing-001",
        adapter_id="opencode@1.18.14",
        spec_sha256=SPEC_SHA256,
        input_sha256=canonical_sha256(input_bundle),
        input_bundle=input_bundle,
        secret_refs=("env://SYNTHETIC_PROVIDER_KEY",),
        timeout_seconds=60,
        network_mode="none",
    )


def test_executor_compiles_fixed_offline_opencode_attempt_and_cleans_workspace(
    tmp_path: Path,
) -> None:
    from supervisor.opencode_executor import OpenCodeAttemptExecutor

    output = {"claims": [], "advisory_signals": []}
    event = json.dumps({"type": "text", "data": {"text": json.dumps(output)}})
    runtime = FakeContainerRuntime(
        exit_code=0,
        staged_outputs={Path("events.jsonl"): event.encode("utf-8")},
    )
    observed_workspaces: list[Path] = []
    executor = OpenCodeAttemptExecutor(
        runtime=runtime,
        image_ref=IMAGE_REF,
        mcp_bridge_path=(
            Path(__file__).resolve().parents[1] / "supervisor" / "mcp_stdio_bridge.sh"
        ),
        secret_resolver=lambda reference: (
            SYNTHETIC_SECRET
            if reference == "env://SYNTHETIC_PROVIDER_KEY"
            else (_ for _ in ()).throw(KeyError(reference))
        ),
        workspace_root=tmp_path,
        host_path_mapper=DaemonRootPathMapper(
            local_root=tmp_path,
            daemon_root="/var/lib/docker/volumes/demo-supervisor/_data",
        ),
        workspace_observer=observed_workspaces.append,
    )

    outcome = executor.execute(_attempt())

    assert outcome.receipt.exit_classification == ExitClassification.SUCCEEDED
    assert outcome.receipt.request_sha256 == _attempt().request_sha256()
    assert outcome.output_bundle == output
    assert runtime.last_config is not None
    assert runtime.last_config.image_ref == IMAGE_REF
    assert runtime.last_config.network_mode == "none"
    assert runtime.last_config.user == "65534:65534"
    assert runtime.last_config.entrypoint == ("/bin/sh", "-c")
    assert len(runtime.last_config.read_only_inputs) == 4
    assert all(
        mount.host_path.startswith("/var/lib/docker/volumes/demo-supervisor/_data")
        for mount in runtime.last_config.read_only_inputs
    )
    assert runtime.last_config.host_scratch_dir.startswith(
        "/var/lib/docker/volumes/demo-supervisor/_data"
    )
    serialized_config = runtime.last_config.model_dump_json()
    assert SYNTHETIC_SECRET not in serialized_config
    assert "generation-001" not in serialized_config
    assert "fencing-001" not in serialized_config
    assert len(observed_workspaces) == 1
    assert not observed_workspaces[0].exists()


def test_executor_cancel_terminates_only_exact_managed_attempt(tmp_path: Path) -> None:
    from supervisor.opencode_executor import OpenCodeAttemptExecutor

    now = datetime.now(timezone.utc)
    runtime = ManagedFakeRuntime()
    executor = OpenCodeAttemptExecutor(
        runtime=runtime,
        image_ref=IMAGE_REF,
        mcp_bridge_path=(
            Path(__file__).resolve().parents[1] / "supervisor" / "mcp_stdio_bridge.sh"
        ),
        secret_resolver=lambda _reference: SYNTHETIC_SECRET,
        workspace_root=tmp_path,
        clock=lambda: now,
    )

    receipt = executor.cancel("attempt-001", _attempt().request_sha256())

    assert receipt.exit_classification == ExitClassification.CANCELLED
    assert receipt.request_sha256 == _attempt().request_sha256()
    assert runtime.terminated_ids == ["managed-container-1"]
    assert runtime.removed_ids == ["managed-container-1"]


def test_executor_orphan_recovery_terminates_exact_labeled_container(tmp_path: Path) -> None:
    from supervisor.opencode_executor import OpenCodeAttemptExecutor

    now = datetime.now(timezone.utc)
    runtime = ManagedFakeRuntime()
    executor = OpenCodeAttemptExecutor(
        runtime=runtime,
        image_ref=IMAGE_REF,
        mcp_bridge_path=(
            Path(__file__).resolve().parents[1] / "supervisor" / "mcp_stdio_bridge.sh"
        ),
        secret_resolver=lambda _reference: SYNTHETIC_SECRET,
        workspace_root=tmp_path,
        clock=lambda: now,
    )

    receipt = executor.recover_orphan("attempt-001", _attempt().request_sha256())

    assert receipt.status is HarnessStatus.FAILED
    assert receipt.exit_classification == ExitClassification.ORPHANED
    assert runtime.terminated_ids == ["managed-container-1"]
    assert runtime.removed_ids == ["managed-container-1"]
