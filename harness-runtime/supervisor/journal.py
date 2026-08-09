"""Minimal durable operational journal for Supervisor attempt recovery.

The journal is deliberately not a product state store. It persists only the
request identity/hash, lifecycle state, lease and terminal ExecutionReceipt;
input bundles and credentials never enter this directory.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock
from typing import Literal

from pydantic import Field

from contracts.receipt import ExecutionReceipt
from contracts.request import StrictContractModel


TerminalAttemptState = Literal[
    "succeeded",
    "failed",
    "cancelled",
    "timed_out",
    "orphaned",
]
_TERMINAL_STATES = {"succeeded", "failed", "cancelled", "timed_out", "orphaned"}


class AttemptJournalRecord(StrictContractModel):
    attempt_id: str = Field(min_length=1, max_length=160)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: Literal[
        "accepted",
        "running",
        "succeeded",
        "failed",
        "cancelled",
        "timed_out",
        "orphaned",
    ] = "accepted"
    lease_expires_at: datetime
    receipt: ExecutionReceipt | None = None


class FileAttemptJournal:
    """One atomically replaced JSON record per Attempt."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def create(
        self,
        *,
        attempt_id: str,
        request_sha256: str,
        lease_expires_at: datetime,
    ) -> AttemptJournalRecord:
        record = AttemptJournalRecord(
            attempt_id=attempt_id,
            request_sha256=request_sha256,
            lease_expires_at=lease_expires_at,
        )
        self._write(record)
        return record

    def get(self, attempt_id: str) -> AttemptJournalRecord | None:
        path = self._path(attempt_id)
        if not path.is_file():
            return None
        return AttemptJournalRecord.model_validate_json(path.read_text(encoding="utf-8"))

    def complete(
        self,
        attempt_id: str,
        *,
        state: TerminalAttemptState,
        receipt: ExecutionReceipt,
    ) -> AttemptJournalRecord:
        with self._lock:
            current = self.get(attempt_id)
            if current is None:
                raise KeyError(attempt_id)
            if current.state in _TERMINAL_STATES:
                return current
            completed = current.model_copy(update={"state": state, "receipt": receipt})
            self._write(completed)
            return completed

    def heartbeat(
        self,
        attempt_id: str,
        *,
        now: datetime,
        lease_seconds: int,
    ) -> AttemptJournalRecord:
        with self._lock:
            current = self.get(attempt_id)
            if current is None:
                raise KeyError(attempt_id)
            if current.state in _TERMINAL_STATES:
                return current
            renewed = current.model_copy(
                update={"lease_expires_at": now + timedelta(seconds=lease_seconds)}
            )
            self._write(renewed)
            return renewed

    def list_active(self) -> tuple[AttemptJournalRecord, ...]:
        records = (
            AttemptJournalRecord.model_validate_json(path.read_text(encoding="utf-8"))
            for path in self._root.glob("*.json")
        )
        return tuple(
            sorted(
                (record for record in records if record.state not in _TERMINAL_STATES),
                key=lambda record: record.attempt_id,
            )
        )

    def _write(self, record: AttemptJournalRecord) -> None:
        path = self._path(record.attempt_id)
        temporary = path.with_suffix(".tmp")
        serialized = record.model_dump_json()
        with self._lock:
            temporary.write_text(serialized, encoding="utf-8")
            temporary.replace(path)

    def _path(self, attempt_id: str) -> Path:
        filename = hashlib.sha256(attempt_id.encode("utf-8")).hexdigest() + ".json"
        return self._root / filename
