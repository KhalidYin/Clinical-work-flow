"""H0-C HarnessSupervisor: orchestrates one containerized harness attempt.

Pipeline: validate identity/image lock → materialize workspace → create/
start container (security baseline from ContainerConfig) → collect events →
wait (timeout/cancel handling) → copy staging out → host-side scan with
recomputed hashes → supervisor-owned ExecutionReceipt. Never trusts the
harness's self-reported status/hash/budget as completion evidence.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from contracts.manifest import ArtifactManifest
from contracts.receipt import ExecutionReceipt, ExitClassification
from contracts.request import HarnessExecutionRequest
from contracts.result import HarnessStatus
from supervisor.container_runtime import (
    ContainerConfig,
    ContainerRuntimePort,
    ReadOnlyMount,
)
from supervisor.staging import StagingLimits, StagingScanError, scan_staging

_SIGNAL_EXIT_CODES = (130, 137, 143)  # SIGINT / SIGKILL / SIGTERM


def _request_sha256(request: HarnessExecutionRequest) -> str:
    return hashlib.sha256(
        json.dumps(request.model_dump(mode="json"), sort_keys=True).encode("utf-8")
    ).hexdigest()


class HarnessSupervisor:
    """Product-side execution face; carries no business state."""

    def __init__(
        self,
        *,
        runtime: ContainerRuntimePort,
        staging_limits: StagingLimits | None = None,
    ) -> None:
        self._runtime = runtime
        self._staging_limits = staging_limits or StagingLimits()
        self._cancel_requested = False

    def cancel(self) -> None:
        """Explicit cancellation signal for the running attempt."""
        self._cancel_requested = True

    def execute(
        self,
        request: HarnessExecutionRequest,
        *,
        command: tuple[str, ...] = (),
    ) -> ExecutionReceipt:
        if request.spec_sha256 is None:
            raise ValueError("spec_sha256 is required for harness execution")
        if request.image_ref is None:
            raise ValueError("image_ref (with digest lock) is required for harness execution")

        started_at = datetime.now(timezone.utc)
        host_scratch = Path(request.scratch_path)
        host_staging = host_scratch / "staging"
        host_scratch.mkdir(parents=True, exist_ok=True)
        host_staging.mkdir(parents=True, exist_ok=True)

        config = ContainerConfig(
            image_ref=request.image_ref,
            command=command,
            read_only_inputs=(
                ReadOnlyMount(
                    host_path=str(Path(request.input_path).parent),
                    container_path="/inputs",
                ),
            ),
            scratch_dir="/scratch",
            staging_dir="/staging",
            host_scratch_dir=str(host_scratch),
            host_staging_dir=str(host_staging),
            timeout_seconds=request.timeout_seconds,
        )
        container_id = self._runtime.create(config)
        self._runtime.start(container_id)
        events = list(self._runtime.events(container_id))

        exit_code = self._runtime.wait(container_id, request.timeout_seconds)
        classification: ExitClassification
        status: HarnessStatus
        message = ""
        if exit_code is None:
            self._runtime.terminate(container_id)
            status = (
                HarnessStatus.CANCELLED
                if self._cancel_requested
                else HarnessStatus.TIMED_OUT
            )
            classification = (
                ExitClassification.CANCELLED
                if self._cancel_requested
                else ExitClassification.TIMED_OUT
            )
            message = "harness timed out and was terminated"
        elif exit_code == 0:
            status = HarnessStatus.SUCCEEDED
            classification = ExitClassification.SUCCEEDED
        elif exit_code in _SIGNAL_EXIT_CODES or self._cancel_requested:
            status = HarnessStatus.CANCELLED
            classification = ExitClassification.CANCELLED
            message = f"harness cancelled (exit {exit_code})"
        else:
            status = HarnessStatus.FAILED
            classification = ExitClassification.FAILED
            message = f"harness failed (exit {exit_code})"

        manifest = ArtifactManifest()
        if exit_code is not None:
            try:
                self._runtime.copy_from(container_id, "/staging", str(host_staging))
                manifest = scan_staging(host_staging, self._staging_limits)
            except StagingScanError as exc:
                status = HarnessStatus.FAILED
                classification = ExitClassification.FAILED
                message = f"staging scan rejected output: {exc}"

        ended_at = datetime.now(timezone.utc)
        self._runtime.remove(container_id)

        return ExecutionReceipt(
            execution_id=f"exec-{request.attempt_id}",
            spec_sha256=request.spec_sha256,
            request_sha256=_request_sha256(request),
            harness_id=request.adapter_id,
            image_ref=request.image_ref,
            adapter_id=request.adapter_id,
            status=status,
            exit_classification=classification,
            exit_code=exit_code,
            message=message,
            started_at=started_at,
            ended_at=ended_at,
            budget_used={"calls": len(events)},
            event_summary=tuple(event.type for event in events),
            tool_call_summary=(),
            artifact_manifest=manifest,
            retryable=classification in {
                ExitClassification.FAILED,
                ExitClassification.TIMED_OUT,
            },
            validator_input={},
        )
