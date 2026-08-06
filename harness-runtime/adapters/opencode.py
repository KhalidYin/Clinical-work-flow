"""OpenCode adapter: wraps `opencode run --format json` (non-interactive).

Maps OpenCode JSONL events onto the harness event contract, normalizes exit
codes, and enforces zero-outbound defaults (models fetch / autoupdate / LSP
download disabled). The OpenCode binary/image digest is locked by the
supervisor via ``ContainerConfig.image_ref``; this adapter only needs the
binary on PATH or a resolved image entrypoint.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from contracts.request import HarnessExecutionRequest
from contracts.result import HarnessEvent, HarnessResult, HarnessStatus

from .base import HarnessAdapterError, HarnessEventSink

_EVENT_MAP: dict[str, str] = {
    "step_start": "checkpoint",
    "step_finish": "checkpoint",
    "text": "checkpoint",
    "reasoning": "checkpoint",
    "tool_use": "tool_call",
    "error": "failed",
}


def fake_opencode_cli_path() -> str:
    """Path to the bundled fake OpenCode CLI (deterministic test double)."""
    return str(Path(__file__).parent / "fake_opencode_cli.py")


def _sanitize(data: dict[str, Any]) -> dict[str, object]:
    """Keep only safe, small payload fields from untrusted OpenCode events."""
    inner = data.get("data")
    if not isinstance(inner, dict):
        inner = {}
    tool = inner.get("tool")
    if isinstance(tool, dict) and isinstance(tool.get("toolName"), str):
        return {"tool": tool["toolName"]}
    if data.get("type") == "error":
        return {"message": str(inner.get("message", "opencode error"))[:500]}
    return {}


class OpenCodeAdapter:
    """Adapter over the OpenCode CLI (non-interactive ``run`` mode)."""

    adapter_id = "opencode@1.18.14"

    def __init__(
        self,
        binary: str | Path | tuple[str, ...] = "opencode",
        *,
        mcp: dict[str, Any] | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> None:
        if isinstance(binary, tuple):
            self._binary: tuple[str, ...] = binary
        else:
            self._binary = (str(binary),)
        self._mcp = mcp or {}
        self._extra_env = extra_env or {}
        self._process: subprocess.Popen[str] | None = None

    def _environment(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(
            {
                # Zero outbound defaults for OpenCode's optional network steps.
                "OPENCODE_DISABLE_MODELS_FETCH": "1",
                "OPENCODE_DISABLE_AUTOUPDATE": "true",
                "OPENCODE_DISABLE_LSP_DOWNLOAD": "1",
            }
        )
        env.update(self._extra_env)
        return env

    def _write_mcp_config(self, scratch: Path) -> Path:
        config_dir = scratch / ".opencode"
        config_dir.mkdir(parents=True, exist_ok=True)
        config = config_dir / "opencode.json"
        config.write_text(
            json.dumps({"mcp": self._mcp}, indent=2),
            encoding="utf-8",
        )
        return config_dir

    def run(
        self,
        request: HarnessExecutionRequest,
        events: HarnessEventSink | None = None,
    ) -> HarnessResult:
        if not request.input_path.is_file():
            raise HarnessAdapterError(
                f"input artifact not materialized: {request.input_path}"
            )
        prompt = request.input_path.read_text(encoding="utf-8")
        command = [*self._binary, "run", prompt, "--format", "json"]

        scratch = Path(request.scratch_path)
        scratch.mkdir(parents=True, exist_ok=True)
        cwd = self._write_mcp_config(scratch) if self._mcp else scratch

        if events is not None:
            events(HarnessEvent(type="started", payload={}))
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=self._environment(),
            cwd=str(cwd),
        )
        try:
            stdout, stderr = self._process.communicate(
                timeout=request.timeout_seconds
            )
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()
            self._process = None
            return HarnessResult(
                status=HarnessStatus.TIMED_OUT,
                exit_code=None,
                message="opencode timed out",
            )
        exit_code = self._process.returncode
        self._process = None

        message_parts: list[str] = []
        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            event_type = _EVENT_MAP.get(str(data.get("type", "")))
            if event_type is None:
                continue
            if data.get("type") == "text" and isinstance(data.get("data"), dict):
                text = data["data"].get("text")
                if isinstance(text, str) and text:
                    message_parts.append(text)
            if data.get("type") == "error" and isinstance(data.get("data"), dict):
                error_message = data["data"].get("message")
                if isinstance(error_message, str) and error_message:
                    message_parts.append(error_message)
            if events is not None:
                events(HarnessEvent(type=event_type, payload=_sanitize(data)))
        if events is not None:
            events(HarnessEvent(type="finished", payload={}))

        output_sha256: str | None = None
        output_path: Path | None = None
        if request.output_path.is_file():
            output_path = request.output_path
            output_sha256 = hashlib.sha256(
                request.output_path.read_bytes()
            ).hexdigest()
        message = "\n".join(message_parts)[-2000:]

        if exit_code == 0:
            return HarnessResult(
                status=HarnessStatus.SUCCEEDED,
                exit_code=0,
                message=message,
                output_path=output_path,
                output_sha256=output_sha256,
            )
        return HarnessResult(
            status=HarnessStatus.FAILED,
            exit_code=exit_code,
            message=message or (stderr.strip() or "opencode failed"),
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
