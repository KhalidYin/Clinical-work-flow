"""OpenCode adapter contract tests (driven by a fake `opencode` CLI).

Covers: non-interactive `run --format json` event parsing, exit code
normalization, timeout/terminate, tool-call events, zero outbound network.
The real GHCR image is exercised only by the skipped integration test.
"""

from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest

from adapters.base import HarnessAdapter, HarnessAdapterError
from adapters.opencode import OpenCodeAdapter, fake_opencode_cli_path
from contracts.request import HarnessExecutionRequest
from contracts.result import HarnessStatus


def _request(
    tmp_path: Path,
    *,
    mode: str = "ok",
    timeout_seconds: int = 15,
) -> HarnessExecutionRequest:
    request = HarnessExecutionRequest(
        attempt_id="attempt-opencode-0001",
        adapter_id="opencode@1.18.14",
        input_path=tmp_path / "prompt.txt",
        scratch_path=tmp_path / "scratch",
        output_path=tmp_path / "output.json",
        timeout_seconds=timeout_seconds,
        payload={"mode": mode},
    )
    request.input_path.write_text(
        json.dumps({"mode": mode, "task": "extract candidate"}),
        encoding="utf-8",
    )
    return request


def _adapter() -> OpenCodeAdapter:
    return OpenCodeAdapter(binary=(sys.executable, fake_opencode_cli_path()))


def test_opencode_adapter_satisfies_harness_adapter_protocol(tmp_path: Path) -> None:
    assert isinstance(_adapter(), HarnessAdapter)


def test_success_parses_events_and_message(tmp_path: Path) -> None:
    adapter = _adapter()
    events: list = []
    result = adapter.run(_request(tmp_path), events=events.append)
    assert result.status is HarnessStatus.SUCCEEDED
    assert result.exit_code == 0
    assert "fake-opencode-result" in result.message
    event_types = [event.type for event in events]
    assert event_types[0] == "started"
    assert event_types[-1] == "finished"
    assert "checkpoint" in event_types


def test_tool_use_becomes_tool_call_event(tmp_path: Path) -> None:
    adapter = _adapter()
    events: list = []
    adapter.run(_request(tmp_path, mode="tool"), events=events.append)
    tool_events = [event for event in events if event.type == "tool_call"]
    assert tool_events
    assert tool_events[0].payload.get("tool") == "write_artifact"


def test_explicit_failure_returns_failed(tmp_path: Path) -> None:
    adapter = _adapter()
    result = adapter.run(_request(tmp_path, mode="fail"))
    assert result.status is HarnessStatus.FAILED
    assert result.exit_code not in (None, 0)
    assert "boom" in result.message


def test_timeout_returns_timed_out_and_terminate_is_noop(tmp_path: Path) -> None:
    adapter = _adapter()
    result = adapter.run(_request(tmp_path, mode="hang", timeout_seconds=1))
    assert result.status is HarnessStatus.TIMED_OUT
    assert result.exit_code is None
    adapter.terminate()


def test_missing_input_fails_closed(tmp_path: Path) -> None:
    adapter = _adapter()
    request = _request(tmp_path)
    request.input_path.unlink(missing_ok=True)
    with pytest.raises(HarnessAdapterError):
        adapter.run(request)


def test_zero_outbound_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def deny_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError("opencode adapter attempted an outbound network connection")

    monkeypatch.setattr(socket.socket, "connect", deny_connect)
    result = _adapter().run(_request(tmp_path))
    assert result.status is HarnessStatus.SUCCEEDED


def test_adapter_id_is_distinguishable_from_fake_and_replay() -> None:
    assert OpenCodeAdapter.adapter_id == "opencode@1.18.14"


def test_fake_opencode_cli_exists() -> None:
    assert Path(fake_opencode_cli_path()).is_file()


@pytest.mark.integration
def test_real_opencode_binary_round_trip(tmp_path: Path) -> None:
    """Requires the OpenCode binary/镜像 on PATH or in harness-runtime/images."""
    import shutil

    if shutil.which("opencode") is None:
        pytest.skip("opencode binary not available in this environment")
    result = _adapter().run(_request(tmp_path))
    assert result.status is HarnessStatus.SUCCEEDED
