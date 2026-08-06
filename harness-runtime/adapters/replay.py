"""H0-D replay harness adapter: deterministic zero-outbound default path.

Replays a recorded fixture (input hash → events + untrusted HarnessResult)
without starting any subprocess or touching the network. A missing record
fails closed — never falls back to fake or live execution. The adapter
identity ``replay.cli@0.1.0`` keeps replayed output distinguishable from a
real harness result.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from pydantic import Field

from contracts.request import StrictContractModel
from contracts.result import HarnessEvent, HarnessResult, HarnessStatus

from .base import HarnessEventSink


class ReplayMissError(LookupError):
    """No recorded output exists for the exact versioned input hash."""


class ReplayRecord(StrictContractModel):
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    events: tuple[HarnessEvent, ...] = ()
    result: HarnessResult
    output: dict[str, object] | None = None


class ReplayFixture(StrictContractModel):
    records: tuple[ReplayRecord, ...] = ()


def _input_sha256(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def load_replay_fixture(records_path: Path) -> Mapping[str, ReplayRecord]:
    fixture = ReplayFixture.model_validate_json(records_path.read_text(encoding="utf-8"))
    return {record.input_sha256: record for record in fixture.records}


class ReplayHarnessAdapter:
    """Adapter over a recorded fixture; never executes anything."""

    adapter_id = "replay.cli@0.1.0"

    def __init__(self, records_path: Path) -> None:
        self._records = load_replay_fixture(records_path)

    @staticmethod
    def input_sha256(payload: dict[str, object]) -> str:
        return _input_sha256(payload)

    def run(
        self,
        request,
        events: HarnessEventSink | None = None,
    ) -> HarnessResult:
        key = _input_sha256(request.payload)
        record = self._records.get(key)
        if record is None:
            raise ReplayMissError(f"no replay record for input sha256 {key}")
        for event in record.events:
            if events is not None:
                events(event)
        result = record.result
        if (
            result.status is HarnessStatus.SUCCEEDED
            and record.output is not None
        ):
            # Materialize the recorded output artifact into the request
            # staging path so downstream validators read a real artifact
            # with a supervisor-recomputable hash.
            request.output_path.parent.mkdir(parents=True, exist_ok=True)
            request.output_path.write_text(
                json.dumps(record.output, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            digest = hashlib.sha256(request.output_path.read_bytes()).hexdigest()
            result = result.model_copy(
                update={
                    "output_path": request.output_path,
                    "output_sha256": digest,
                }
            )
        return result

    def terminate(self) -> None:
        return None
