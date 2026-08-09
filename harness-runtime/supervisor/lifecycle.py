"""Attempt execution coordination outside product business state."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Protocol

from pydantic import Field

from contracts.manifest import ArtifactManifest
from contracts.receipt import ExecutionReceipt, ExitClassification
from contracts.request import StrictContractModel
from contracts.result import HarnessStatus
from supervisor.journal import FileAttemptJournal, TerminalAttemptState
from supervisor.service_contracts import SupervisorAttemptRequest, canonical_sha256


class AttemptExecutionOutcome(StrictContractModel):
    receipt: ExecutionReceipt
    output_bundle: dict[str, object] | None = None


class StoredAttemptResult(StrictContractModel):
    attempt_id: str = Field(min_length=1, max_length=160)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_bundle: dict[str, object] | None = None


class AttemptExecutorPort(Protocol):
    def execute(self, attempt: SupervisorAttemptRequest) -> AttemptExecutionOutcome: ...


class FileAttemptResultStore:
    """Atomic terminal output store kept separate from the lifecycle journal."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def put(
        self,
        *,
        attempt_id: str,
        request_sha256: str,
        output_bundle: dict[str, object] | None,
    ) -> StoredAttemptResult:
        with self._lock:
            existing = self._read(attempt_id)
            if existing is not None:
                return existing
            result = StoredAttemptResult(
                attempt_id=attempt_id,
                request_sha256=request_sha256,
                output_sha256=(
                    canonical_sha256(output_bundle) if output_bundle is not None else None
                ),
                output_bundle=output_bundle,
            )
            path = self._path(attempt_id)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(result.model_dump_json(), encoding="utf-8")
            temporary.replace(path)
            return result

    def get(self, attempt_id: str) -> StoredAttemptResult | None:
        with self._lock:
            return self._read(attempt_id)

    def _read(self, attempt_id: str) -> StoredAttemptResult | None:
        path = self._path(attempt_id)
        if not path.is_file():
            return None
        return StoredAttemptResult.model_validate_json(path.read_text(encoding="utf-8"))

    def _path(self, attempt_id: str) -> Path:
        filename = hashlib.sha256(attempt_id.encode("utf-8")).hexdigest() + ".json"
        return self._root / filename


_RECEIPT_STATE: dict[ExitClassification, TerminalAttemptState] = {
    ExitClassification.SUCCEEDED: "succeeded",
    ExitClassification.FAILED: "failed",
    ExitClassification.CANCELLED: "cancelled",
    ExitClassification.TIMED_OUT: "timed_out",
    ExitClassification.ORPHANED: "orphaned",
}


class AttemptCoordinator:
    """Run one accepted Attempt and commit output before terminal state."""

    def __init__(
        self,
        *,
        journal: FileAttemptJournal,
        result_store: FileAttemptResultStore,
        executor: AttemptExecutorPort,
        clock: Callable[[], datetime],
        lease_seconds: int,
        submit: Callable[[Callable[[], None]], object],
    ) -> None:
        self._journal = journal
        self._result_store = result_store
        self._executor = executor
        self._clock = clock
        self._lease_seconds = lease_seconds
        self._submit = submit

    def dispatch(self, attempt: SupervisorAttemptRequest) -> None:
        self._journal.heartbeat(
            attempt.attempt_id,
            now=self._clock(),
            lease_seconds=self._lease_seconds,
        )
        self._submit(lambda: self._execute(attempt))

    def _execute(self, attempt: SupervisorAttemptRequest) -> None:
        started_at = self._clock()
        try:
            outcome = self._executor.execute(attempt)
        except Exception:
            ended_at = self._clock()
            outcome = AttemptExecutionOutcome(
                receipt=ExecutionReceipt(
                    execution_id=f"exec-{attempt.attempt_id}",
                    spec_sha256=attempt.spec_sha256,
                    request_sha256=attempt.request_sha256(),
                    harness_id=attempt.adapter_id,
                    adapter_id=attempt.adapter_id,
                    status=HarnessStatus.FAILED,
                    exit_classification=ExitClassification.FAILED,
                    message="executor failed before receipt was produced",
                    started_at=started_at,
                    ended_at=ended_at,
                    artifact_manifest=ArtifactManifest(),
                )
            )
        self._result_store.put(
            attempt_id=attempt.attempt_id,
            request_sha256=attempt.request_sha256(),
            output_bundle=outcome.output_bundle,
        )
        self._journal.complete(
            attempt.attempt_id,
            state=_RECEIPT_STATE[outcome.receipt.exit_classification],
            receipt=outcome.receipt,
        )
