"""Deterministic fake Harness adapter: subprocess wrapper around fake_cli.py.

Proves the H0-A claim that product code can depend only on the
``HarnessAdapter`` interface. Fully local: no network, no real model.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from contracts.request import HarnessExecutionRequest
from contracts.result import HarnessEvent, HarnessResult, HarnessStatus

from .base import HarnessAdapterError, HarnessEventSink


def fake_cli_path() -> str:
    """Path to the bundled fake CLI script (simulated mature Harness CLI)."""
    return str(Path(__file__).parent / "fake_cli.py")


class FakeHarnessAdapter:
    """Adapter over the deterministic fake CLI.

    The supervisor (H0-C) is responsible for materializing inputs; this
    adapter fails closed if the input artifact is not present.
    """

    adapter_id = "fake.cli@0.1.0"

    def __init__(self, cli_path: str | Path | None = None) -> None:
        self._cli_path = Path(cli_path) if cli_path is not None else Path(fake_cli_path())
        self._process: subprocess.Popen[str] | None = None

    @staticmethod
    def input_sha256(payload: dict[str, object]) -> str:
        """Stable key used to record/replay fixtures (H0-D regression baseline)."""
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def run(
        self,
        request: HarnessExecutionRequest,
        events: HarnessEventSink | None = None,
    ) -> HarnessResult:
        if not request.input_path.is_file():
            raise HarnessAdapterError(f"input artifact not materialized: {request.input_path}")
        request.scratch_path.mkdir(parents=True, exist_ok=True)
        request.output_path.parent.mkdir(parents=True, exist_ok=True)

        command = [
            sys.executable,
            str(self._cli_path),
            str(request.input_path),
            str(request.output_path),
        ]
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        try:
            stdout, stderr = self._process.communicate(timeout=request.timeout_seconds)
        except subprocess.TimeoutExpired:
            # Best-effort cleanup; the process is reaped here, so terminate()
            # afterwards must be a no-op.
            self._process.kill()
            self._process.wait()
            self._process = None
            return HarnessResult(
                status=HarnessStatus.TIMED_OUT,
                exit_code=None,
                message="harness timed out",
            )
        returncode = self._process.returncode
        self._process = None

        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and "type" in data:
                event = HarnessEvent(
                    type=data["type"],
                    payload=data.get("payload", {}),
                )
                if events is not None:
                    events(event)

        output_sha256: str | None = None
        output_path: Path | None = None
        if request.output_path.is_file():
            output_path = request.output_path
            output_sha256 = hashlib.sha256(request.output_path.read_bytes()).hexdigest()

        if returncode == 0:
            return HarnessResult(
                status=HarnessStatus.SUCCEEDED,
                exit_code=0,
                output_path=output_path,
                output_sha256=output_sha256,
            )
        return HarnessResult(
            status=HarnessStatus.FAILED,
            exit_code=returncode,
            message=(stderr.strip() or "harness failed"),
            output_path=output_path,
            output_sha256=output_sha256,
        )

    def terminate(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return
        process.kill()
        process.wait()
        self._process = None
