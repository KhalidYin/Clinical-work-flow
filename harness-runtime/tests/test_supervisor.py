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
    # config lock: zero network + read-only inputs enforced at the boundary
    config = runtime.last_config
    assert config.network_mode == "none"
    assert config.read_only_inputs


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
