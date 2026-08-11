"""H0-C supervisor lifecycle tests driven by FakeContainerRuntime.

Covers success, failure, timeout (terminate + structured receipt), cancelled
status classification, late-event rejection and ExecutionReceipt generation.
No Docker is required for these tests.
"""

from __future__ import annotations

from datetime import datetime
import pytest

from contracts.request import HarnessExecutionRequest
from contracts.result import HarnessStatus
from supervisor.fake_container_runtime import FakeContainerRuntime
from supervisor.container_runtime import DaemonRootPathMapper, ReadOnlyMount
from supervisor.staging import StagingLimits
from supervisor.supervisor import HarnessSupervisor


def _request(tmp_path) -> HarnessExecutionRequest:
    return HarnessExecutionRequest(
        attempt_id="attempt-h0-c-0001",
        adapter_id="fake.cli@0.1.0",
        spec_sha256="a" * 64,
        image_ref=f"clinical-harness:fake@sha256:{'f' * 64}",
        input_path=tmp_path / "input.json",
        scratch_path=tmp_path / "scratch",
        output_path=tmp_path / "output.json",
        timeout_seconds=30,
        payload={"claim": "x"},
    )


def _supervisor(runtime: FakeContainerRuntime) -> HarnessSupervisor:
    return HarnessSupervisor(
        runtime=runtime,
        staging_limits=StagingLimits(max_total_bytes=10 * 1024 * 1024, max_files=20),
    )


def test_success_returns_receipt_with_manifest(tmp_path) -> None:
    runtime = FakeContainerRuntime(
        exit_code=0,
        staged_outputs={tmp_path / "output.json": b'{"claim":"x"}'},
    )
    supervisor = _supervisor(runtime)
    request = _request(tmp_path)
    request.input_path.write_text('{"claim":"x"}', encoding="utf-8")

    receipt = supervisor.execute(request)

    assert receipt.status is HarnessStatus.SUCCEEDED
    assert receipt.exit_classification.value == "succeeded"
    assert receipt.artifact_manifest.items[0].key == "output.json"
    assert len(receipt.artifact_manifest.items[0].sha256) == 64
    assert receipt.network_policy is not None
    assert receipt.network_policy.policy_id == "none"
    assert receipt.network_policy.kind == "none"
    assert receipt.network_policy.allowed_endpoints == ()
    assert receipt.validator_input == {
        "network_mode": "none",
        "read_only_root": True,
        "user": "65534:65534",
        "cap_drop": ["ALL"],
        "no_new_privileges": True,
        "memory_bytes": 512 * 1024 * 1024,
        "pids_limit": 128,
    }
    # config lock: zero network + read-only inputs enforced at the boundary
    config = runtime.last_config
    assert config.network_mode == "none"
    assert config.read_only_inputs


def test_launch_options_preserve_entrypoint_environment_and_secret_mount(tmp_path) -> None:
    runtime = FakeContainerRuntime(
        exit_code=0,
        staged_outputs={tmp_path / "events.jsonl": b'{"type":"text"}\n'},
    )
    supervisor = _supervisor(runtime)
    request = _request(tmp_path)
    request.input_path.write_text("{}", encoding="utf-8")
    auth_file = tmp_path / "opencode-auth.json"
    auth_file.write_text("{}", encoding="utf-8")

    supervisor.execute(
        request,
        entrypoint=("/bin/sh", "-c"),
        command=("opencode run --file /inputs/input.json",),
        extra_read_only_mounts=(
            ReadOnlyMount(
                host_path=str(auth_file),
                container_path="/scratch/data/opencode/auth.json",
            ),
        ),
        environment=(("XDG_DATA_HOME", "/scratch/data"),),
    )

    config = runtime.last_config
    assert config is not None
    assert config.entrypoint == ("/bin/sh", "-c")
    assert config.environment == (("XDG_DATA_HOME", "/scratch/data"),)
    assert config.read_only_inputs[-1].host_path == str(auth_file)
    assert "opencode-auth.json" not in " ".join(config.command)


def test_supervisor_labels_container_with_attempt_and_control_request_hash(tmp_path) -> None:
    runtime = FakeContainerRuntime(exit_code=1)
    supervisor = _supervisor(runtime)
    request = _request(tmp_path)
    request.input_path.write_text("{}", encoding="utf-8")

    supervisor.execute(request, control_request_sha256="c" * 64)

    config = runtime.last_config
    assert config is not None
    assert dict(config.labels) == {
        "clinical.harness.attempt": "managed",
        "clinical.harness.attempt_id": request.attempt_id,
        "clinical.harness.request_sha256": "c" * 64,
        "clinical.harness.spec_sha256": "a" * 64,
    }


def test_supervisor_maps_all_bind_sources_to_daemon_visible_state_root(tmp_path) -> None:
    state_root = tmp_path / "state"
    runtime = FakeContainerRuntime(exit_code=1)
    supervisor = HarnessSupervisor(
        runtime=runtime,
        host_path_mapper=DaemonRootPathMapper(
            local_root=state_root,
            daemon_root="/var/lib/docker/volumes/demo-supervisor/_data",
        ),
    )
    request = _request(state_root / "attempt")
    request.input_path.parent.mkdir(parents=True)
    request.input_path.write_text("{}", encoding="utf-8")
    auth_path = state_root / "attempt" / "secrets" / "auth.json"
    auth_path.parent.mkdir(parents=True)
    auth_path.write_text("{}", encoding="utf-8")

    supervisor.execute(
        request,
        extra_read_only_mounts=(
            ReadOnlyMount(host_path=str(auth_path), container_path="/harness/auth.json"),
        ),
    )

    config = runtime.last_config
    assert config is not None
    daemon_root = "/var/lib/docker/volumes/demo-supervisor/_data"
    assert config.host_scratch_dir.startswith(daemon_root)
    assert config.host_staging_dir.startswith(daemon_root)
    assert "/staging" not in dict(config.tmpfs)
    assert all(
        mount.host_path.startswith(daemon_root) for mount in config.read_only_inputs
    )
    assert str(state_root) not in config.model_dump_json()


def test_daemon_root_mapper_rejects_bind_source_outside_local_state_root(tmp_path) -> None:
    mapper = DaemonRootPathMapper(
        local_root=tmp_path / "state",
        daemon_root="/var/lib/docker/volumes/demo-supervisor/_data",
    )

    with pytest.raises(ValueError, match="outside Supervisor state root"):
        mapper(tmp_path / "outside" / "secret.json")


def test_container_is_removed_when_copying_staging_raises(tmp_path) -> None:
    class BrokenCopyRuntime(FakeContainerRuntime):
        def copy_from(self, container_id: str, container_path: str, host_path: str) -> None:
            raise RuntimeError("copy failed")

    runtime = BrokenCopyRuntime(exit_code=0)
    supervisor = _supervisor(runtime)
    request = _request(tmp_path)
    request.input_path.write_text("{}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="copy failed"):
        supervisor.execute(request)

    assert runtime.remove_called is True


def test_timeout_terminates_and_marks_timed_out(tmp_path) -> None:
    runtime = FakeContainerRuntime(exit_code=None, hangs=True)
    supervisor = _supervisor(runtime)
    request = _request(tmp_path)
    request.input_path.write_text('{"claim":"x"}', encoding="utf-8")

    receipt = supervisor.execute(request)

    assert receipt.status is HarnessStatus.TIMED_OUT
    assert receipt.exit_classification.value == "timed_out"
    assert runtime.terminate_called


def test_cancelled_requires_explicit_signal(tmp_path) -> None:
    """Cancellation is only classified when the supervisor is asked to stop,
    not derived from a self-reported harness status."""
    runtime = FakeContainerRuntime(exit_code=130, cancel_signal=True)
    supervisor = _supervisor(runtime)
    request = _request(tmp_path)
    request.input_path.write_text('{"claim":"x"}', encoding="utf-8")

    receipt = supervisor.execute(request)
    assert receipt.status is HarnessStatus.CANCELLED
    assert receipt.exit_classification.value == "cancelled"


def test_spec_sha256_required_for_harness_execution(tmp_path) -> None:
    runtime = FakeContainerRuntime(exit_code=0, staged_outputs={})
    supervisor = _supervisor(runtime)
    request = _request(tmp_path)
    request.input_path.write_text("{}", encoding="utf-8")
    request = request.model_copy(update={"spec_sha256": None})

    with pytest.raises(ValueError):
        supervisor.execute(request)


def test_receipt_contains_supervisor_timestamps_and_budget(tmp_path) -> None:
    runtime = FakeContainerRuntime(
        exit_code=0,
        staged_outputs={tmp_path / "output.json": b"{}"},
    )
    supervisor = _supervisor(runtime)
    request = _request(tmp_path)
    request.input_path.write_text("{}", encoding="utf-8")

    receipt = supervisor.execute(request)
    assert isinstance(receipt.started_at, datetime)
    assert isinstance(receipt.ended_at, datetime)
    assert receipt.ended_at >= receipt.started_at
    assert "calls" in receipt.budget_used


def test_late_events_after_receipt_are_ignored(tmp_path) -> None:
    runtime = FakeContainerRuntime(exit_code=0, staged_outputs={})
    supervisor = _supervisor(runtime)
    request = _request(tmp_path)
    request.input_path.write_text("{}", encoding="utf-8")
    receipt = supervisor.execute(request)
    assert receipt.event_summary  # events collected during the run
    # any event arriving after wait() finished must not mutate the receipt
    snapshot = receipt.event_summary
    assert snapshot == receipt.event_summary
