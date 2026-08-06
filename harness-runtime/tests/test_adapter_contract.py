"""H0-A adapter contract tests: fake CLI spawn → events → exit code → Result.

These tests prove the product/supervisor side depends only on the
``HarnessAdapter`` interface, never on a concrete Harness product.
Default path is fully local: no network, no real model, no Docker.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from adapters.base import HarnessAdapter, HarnessAdapterError
from adapters.fake import FakeHarnessAdapter, fake_cli_path
from contracts.request import HarnessExecutionRequest
from contracts.result import HarnessEvent, HarnessStatus


def _request(
    tmp_path: Path,
    *,
    mode: str = "ok",
    timeout_seconds: int = 15,
) -> HarnessExecutionRequest:
    request = HarnessExecutionRequest(
        attempt_id="attempt-h0-a-0001",
        adapter_id="fake.cli@0.1.0",
        input_path=tmp_path / "input.json",
        scratch_path=tmp_path / "scratch",
        output_path=tmp_path / "output.json",
        timeout_seconds=timeout_seconds,
        payload={"mode": mode, "claim": "fake-claim", "evidence_ids": ["ev-1"]},
    )
    # The supervisor (H0-C) materializes the input artifact; the adapter must
    # fail closed when it is missing.
    request.input_path.write_text(json.dumps(request.payload), encoding="utf-8")
    return request


def test_fake_adapter_satisfies_harness_adapter_protocol() -> None:
    adapter = FakeHarnessAdapter()
    assert isinstance(adapter, HarnessAdapter)


def test_success_returns_succeeded_with_sha256_and_event_sequence(
    tmp_path: Path,
) -> None:
    adapter = FakeHarnessAdapter()
    events: list[HarnessEvent] = []
    result = adapter.run(_request(tmp_path), events=events.append)
    assert result.status is HarnessStatus.SUCCEEDED
    assert result.exit_code == 0
    assert result.output_sha256 and len(result.output_sha256) == 64
    # output artifact exists in staging path
    assert (tmp_path / "output.json").exists()
    event_types = [event.type for event in events]
    assert event_types == ["started", "checkpoint", "finished"]


def test_explicit_failure_returns_failed_with_nonzero_exit(
    tmp_path: Path,
) -> None:
    adapter = FakeHarnessAdapter()
    events: list[HarnessEvent] = []
    result = adapter.run(
        _request(tmp_path, mode="fail"),
        events=events.append,
    )
    assert result.status is HarnessStatus.FAILED
    assert result.exit_code not in (None, 0)
    assert "failed" in [event.type for event in events]


def test_timeout_returns_timed_out_and_calls_terminate(
    tmp_path: Path,
) -> None:
    adapter = FakeHarnessAdapter()
    events: list[HarnessEvent] = []
    result = adapter.run(
        _request(tmp_path, mode="hang", timeout_seconds=1),
        events=events.append,
    )
    assert result.status is HarnessStatus.TIMED_OUT
    assert result.exit_code is None
    # terminate must be a no-op after the process is already reaped
    adapter.terminate()


def test_same_input_is_deterministic_and_replayable(
    tmp_path: Path,
) -> None:
    adapter = FakeHarnessAdapter()
    first = adapter.run(_request(tmp_path))
    second = adapter.run(_request(tmp_path))
    assert first.output_sha256 == second.output_sha256
    assert first.status is HarnessStatus.SUCCEEDED
    assert second.status is HarnessStatus.SUCCEEDED


def test_missing_input_fails_closed(tmp_path: Path) -> None:
    adapter = FakeHarnessAdapter()
    request = _request(tmp_path)
    request.input_path.unlink(missing_ok=True)
    with pytest.raises(HarnessAdapterError):
        adapter.run(request)


def test_zero_outbound_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Any outbound socket connect attempt must fail during the fake run."""

    def deny_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError("fake harness attempted an outbound network connection")

    monkeypatch.setattr(socket.socket, "connect", deny_connect)
    adapter = FakeHarnessAdapter()
    result = adapter.run(_request(tmp_path))
    assert result.status is HarnessStatus.SUCCEEDED


def test_fake_cli_path_exists() -> None:
    assert Path(fake_cli_path()).is_file()
