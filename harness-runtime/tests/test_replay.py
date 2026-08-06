"""H0-D replay adapter tests.

Replay must be the default test path: no subprocess, no network, fully
deterministic. fake/replay results are distinguishable from a real harness
by adapter identity and must never be able to masquerade as real output.
"""

from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path

import pytest

from adapters.base import HarnessAdapter
from adapters.fake import FakeHarnessAdapter
from adapters.replay import ReplayHarnessAdapter, ReplayMissError
from contracts.request import HarnessExecutionRequest
from contracts.result import HarnessEvent, HarnessStatus


def _request(tmp_path: Path, *, payload: dict | None = None) -> HarnessExecutionRequest:
    request = HarnessExecutionRequest(
        attempt_id="attempt-h0-d-0001",
        adapter_id="replay.cli@0.1.0",
        spec_sha256="a" * 64,
        image_ref=f"clinical-harness:fake@sha256:{'f' * 64}",
        input_path=tmp_path / "input.json",
        scratch_path=tmp_path / "scratch",
        output_path=tmp_path / "output.json",
        timeout_seconds=30,
        payload=payload or {"mode": "ok", "claim": "x"},
    )
    request.input_path.write_text(json.dumps(request.payload), encoding="utf-8")
    return request


def _fixture_records(
    *,
    payload: dict,
    status: HarnessStatus = HarnessStatus.SUCCEEDED,
    exit_code: int | None = 0,
    sha256: str = "b" * 64,
) -> list[dict]:
    import hashlib

    key = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return [
        {
            "input_sha256": key,
            "events": [
                {"type": "started", "payload": {}},
                {"type": "checkpoint", "payload": {"phase": "draft"}},
                {"type": "finished", "payload": {}},
            ],
            "result": {
                "status": status.value,
                "exit_code": exit_code,
                "message": "",
                "output_path": None,
                "output_sha256": sha256,
            },
        }
    ]


def _write_fixture(tmp_path: Path, records: list[dict]) -> Path:
    path = tmp_path / "records.json"
    path.write_text(json.dumps({"records": records}), encoding="utf-8")
    return path


def test_replay_satisfies_harness_adapter_protocol(tmp_path: Path) -> None:
    records_path = _write_fixture(tmp_path, _fixture_records(payload={"mode": "ok"}))
    adapter = ReplayHarnessAdapter(records_path)
    assert isinstance(adapter, HarnessAdapter)


def test_replay_returns_recorded_result_and_events(tmp_path: Path) -> None:
    payload = {"mode": "ok", "claim": "x"}
    records_path = _write_fixture(
        tmp_path,
        _fixture_records(payload=payload, sha256="c" * 64),
    )
    adapter = ReplayHarnessAdapter(records_path)
    events: list[HarnessEvent] = []
    result = adapter.run(_request(tmp_path, payload=payload), events=events.append)

    assert result.status is HarnessStatus.SUCCEEDED
    assert result.output_sha256 == "c" * 64
    assert [event.type for event in events] == ["started", "checkpoint", "finished"]


def test_replay_miss_fails_closed_no_fallback(tmp_path: Path) -> None:
    """Missing record must raise, never silently fall back to live/fake."""
    records_path = _write_fixture(tmp_path, _fixture_records(payload={"mode": "ok"}))
    adapter = ReplayHarnessAdapter(records_path)
    with pytest.raises(ReplayMissError):
        adapter.run(_request(tmp_path, payload={"mode": "different"}))


def test_replay_never_starts_a_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def deny_popen(*args: object, **kwargs: object) -> None:
        raise AssertionError("replay adapter must not start any subprocess")

    monkeypatch.setattr(subprocess, "Popen", deny_popen)
    payload = {"mode": "ok"}
    records_path = _write_fixture(tmp_path, _fixture_records(payload=payload))
    adapter = ReplayHarnessAdapter(records_path)
    result = adapter.run(_request(tmp_path, payload=payload))
    assert result.status is HarnessStatus.SUCCEEDED


def test_replay_zero_outbound_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def deny_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError("replay attempted an outbound network connection")

    monkeypatch.setattr(socket.socket, "connect", deny_connect)
    payload = {"mode": "ok"}
    records_path = _write_fixture(tmp_path, _fixture_records(payload=payload))
    adapter = ReplayHarnessAdapter(records_path)
    assert adapter.run(_request(tmp_path, payload=payload)).status is HarnessStatus.SUCCEEDED


def test_replay_can_replay_failure_and_timeout_states(tmp_path: Path) -> None:
    for status, exit_code in (
        (HarnessStatus.FAILED, 1),
        (HarnessStatus.TIMED_OUT, None),
        (HarnessStatus.CANCELLED, 130),
    ):
        payload = {"case": status.value}
        records_path = _write_fixture(
            tmp_path,
            _fixture_records(payload=payload, status=status, exit_code=exit_code),
        )
        adapter = ReplayHarnessAdapter(records_path)
        result = adapter.run(_request(tmp_path, payload=payload))
        assert result.status is status
        assert result.exit_code == exit_code


def test_fake_and_replay_are_distinguishable(tmp_path: Path) -> None:
    """Adapter identity is the contract-level distinguisher; replay cannot
    masquerade as a real harness."""
    records_path = _write_fixture(
        tmp_path,
        _fixture_records(payload={"mode": "ok"}),
    )
    replay = ReplayHarnessAdapter(records_path)
    assert FakeHarnessAdapter().adapter_id == "fake.cli@0.1.0"
    assert replay.adapter_id.startswith("replay.")
    assert FakeHarnessAdapter().adapter_id != replay.adapter_id


def test_replay_is_deterministic(tmp_path: Path) -> None:
    payload = {"mode": "ok"}
    records_path = _write_fixture(tmp_path, _fixture_records(payload=payload))
    adapter = ReplayHarnessAdapter(records_path)
    first = adapter.run(_request(tmp_path, payload=payload))
    second = adapter.run(_request(tmp_path, payload=payload))
    assert first.output_sha256 == second.output_sha256


def test_fake_run_records_a_replayable_fixture(tmp_path: Path) -> None:
    """The regression baseline is recordable: a fake run can produce a fixture
    that ReplayHarnessAdapter replays with identical results."""
    fake = FakeHarnessAdapter()
    payload = {"mode": "ok", "claim": "y"}
    live_result = fake.run(_request(tmp_path, payload=payload))

    records = [
        {
            "input_sha256": fake.input_sha256(payload),
            "events": [],
            "result": live_result.model_dump(mode="json"),
        }
    ]
    records_path = _write_fixture(tmp_path, records)
    replay = ReplayHarnessAdapter(records_path)
    replayed = replay.run(_request(tmp_path, payload=payload))
    assert replayed.status is live_result.status
    assert replayed.output_sha256 == live_result.output_sha256
