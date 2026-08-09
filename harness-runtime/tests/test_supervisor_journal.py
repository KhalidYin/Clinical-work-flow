from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from contracts.manifest import ArtifactManifest
from contracts.receipt import ExecutionReceipt, ExitClassification
from contracts.result import HarnessStatus


REQUEST_SHA256 = "d" * 64


def _failed_receipt(now: datetime) -> ExecutionReceipt:
    return ExecutionReceipt(
        execution_id="exec-attempt-001",
        spec_sha256="a" * 64,
        request_sha256=REQUEST_SHA256,
        harness_id="opencode@1.18.14",
        image_ref=(
            "ghcr.io/anomalyco/opencode:1.18.14@sha256:" + "b" * 64
        ),
        adapter_id="opencode@1.18.14",
        status=HarnessStatus.FAILED,
        exit_classification=ExitClassification.FAILED,
        exit_code=1,
        message="offline provider failure",
        started_at=now,
        ended_at=now,
        artifact_manifest=ArtifactManifest(),
    )


def test_file_journal_recovers_minimal_attempt_state_without_sensitive_request(
    tmp_path: Path,
) -> None:
    from supervisor.journal import FileAttemptJournal

    lease_expires_at = datetime.now(timezone.utc) + timedelta(seconds=30)
    journal = FileAttemptJournal(tmp_path)
    created = journal.create(
        attempt_id="attempt-001",
        request_sha256=REQUEST_SHA256,
        lease_expires_at=lease_expires_at,
    )

    recovered = FileAttemptJournal(tmp_path).get("attempt-001")
    persisted = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.glob("*.json"))

    assert created.state == "accepted"
    assert recovered == created
    assert recovered is not None
    assert recovered.request_sha256 == REQUEST_SHA256
    assert recovered.lease_expires_at == lease_expires_at
    assert "offline synthetic evidence" not in persisted
    assert "generation-001" not in persisted
    assert "fencing-001" not in persisted
    assert "SYNTHETIC_PROVIDER_KEY" not in persisted


def test_file_journal_atomically_persists_terminal_receipt(tmp_path: Path) -> None:
    from supervisor.journal import FileAttemptJournal

    now = datetime.now(timezone.utc)
    journal = FileAttemptJournal(tmp_path)
    journal.create(
        attempt_id="attempt-001",
        request_sha256=REQUEST_SHA256,
        lease_expires_at=now + timedelta(seconds=30),
    )
    receipt = _failed_receipt(now)

    completed = journal.complete(
        "attempt-001",
        state="failed",
        receipt=receipt,
    )
    recovered = FileAttemptJournal(tmp_path).get("attempt-001")

    assert completed.state == "failed"
    assert completed.receipt == receipt
    assert recovered == completed
    assert list(tmp_path.glob("*.tmp")) == []


def test_file_journal_heartbeat_renews_only_active_attempt(tmp_path: Path) -> None:
    from supervisor.journal import FileAttemptJournal

    now = datetime.now(timezone.utc)
    original_expiry = now + timedelta(seconds=5)
    journal = FileAttemptJournal(tmp_path)
    journal.create(
        attempt_id="attempt-001",
        request_sha256=REQUEST_SHA256,
        lease_expires_at=original_expiry,
    )

    renewed = journal.heartbeat("attempt-001", now=now, lease_seconds=30)

    assert renewed.state == "accepted"
    assert renewed.lease_expires_at == now + timedelta(seconds=30)
    assert renewed.lease_expires_at > original_expiry


def test_file_journal_heartbeat_does_not_mutate_terminal_attempt(tmp_path: Path) -> None:
    from supervisor.journal import FileAttemptJournal

    now = datetime.now(timezone.utc)
    original_expiry = now + timedelta(seconds=5)
    journal = FileAttemptJournal(tmp_path)
    journal.create(
        attempt_id="attempt-001",
        request_sha256=REQUEST_SHA256,
        lease_expires_at=original_expiry,
    )
    terminal = journal.complete(
        "attempt-001",
        state="failed",
        receipt=_failed_receipt(now),
    )

    heartbeat = journal.heartbeat("attempt-001", now=now, lease_seconds=30)

    assert heartbeat == terminal
    assert heartbeat.lease_expires_at == original_expiry


def test_file_journal_terminal_receipt_is_write_once(tmp_path: Path) -> None:
    from supervisor.journal import FileAttemptJournal

    now = datetime.now(timezone.utc)
    journal = FileAttemptJournal(tmp_path)
    journal.create(
        attempt_id="attempt-001",
        request_sha256=REQUEST_SHA256,
        lease_expires_at=now + timedelta(seconds=30),
    )
    first_receipt = _failed_receipt(now)
    first = journal.complete(
        "attempt-001",
        state="failed",
        receipt=first_receipt,
    )
    late_receipt = first_receipt.model_copy(
        update={
            "status": HarnessStatus.CANCELLED,
            "exit_classification": ExitClassification.CANCELLED,
            "message": "late cancellation must not overwrite terminal state",
        }
    )

    late = journal.complete(
        "attempt-001",
        state="cancelled",
        receipt=late_receipt,
    )

    assert late == first
    assert FileAttemptJournal(tmp_path).get("attempt-001") == first
