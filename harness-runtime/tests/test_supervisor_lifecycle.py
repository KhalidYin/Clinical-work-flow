from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from contracts.manifest import ArtifactManifest
from contracts.receipt import ExecutionReceipt, ExitClassification
from contracts.result import HarnessStatus
from supervisor.service_contracts import SupervisorAttemptRequest, canonical_sha256


SPEC_SHA256 = "a" * 64


def _attempt() -> SupervisorAttemptRequest:
    input_bundle = {
        "messages": [{"role": "user", "content": "offline synthetic evidence"}],
        "model": {"provider": "synthetic", "name": "invalid-offline-model"},
    }
    return SupervisorAttemptRequest(
        attempt_id="attempt-001",
        run_id="run-001",
        step_id="enrichment",
        generation_token="generation-001",
        fencing_token="fencing-001",
        adapter_id="opencode@1.18.14",
        spec_sha256=SPEC_SHA256,
        input_sha256=canonical_sha256(input_bundle),
        input_bundle=input_bundle,
        secret_refs=("env://SYNTHETIC_PROVIDER_KEY",),
        timeout_seconds=60,
        network_mode="none",
    )


class SuccessfulExecutor:
    def __init__(self, now: datetime) -> None:
        self.now = now
        self.calls: list[str] = []

    def execute(self, attempt: SupervisorAttemptRequest):
        from supervisor.lifecycle import AttemptExecutionOutcome

        self.calls.append(attempt.attempt_id)
        receipt = ExecutionReceipt(
            execution_id=f"exec-{attempt.attempt_id}",
            spec_sha256=attempt.spec_sha256,
            request_sha256=attempt.request_sha256(),
            harness_id=attempt.adapter_id,
            adapter_id=attempt.adapter_id,
            status=HarnessStatus.SUCCEEDED,
            exit_classification=ExitClassification.SUCCEEDED,
            exit_code=0,
            started_at=self.now,
            ended_at=self.now,
            artifact_manifest=ArtifactManifest(),
        )
        return AttemptExecutionOutcome(
            receipt=receipt,
            output_bundle={"claims": [], "advisory_signals": []},
        )


class FailingExecutor:
    def execute(self, _attempt: SupervisorAttemptRequest):
        raise RuntimeError("provider failed with super-secret-marker")


def test_coordinator_persists_terminal_receipt_and_output_separately(
    tmp_path: Path,
) -> None:
    from supervisor.journal import FileAttemptJournal
    from supervisor.lifecycle import AttemptCoordinator, FileAttemptResultStore

    now = datetime.now(timezone.utc)
    attempt = _attempt()
    journal = FileAttemptJournal(tmp_path / "journal")
    journal.create(
        attempt_id=attempt.attempt_id,
        request_sha256=attempt.request_sha256(),
        lease_expires_at=now + timedelta(seconds=30),
    )
    results = FileAttemptResultStore(tmp_path / "results")
    executor = SuccessfulExecutor(now)
    coordinator = AttemptCoordinator(
        journal=journal,
        result_store=results,
        executor=executor,
        clock=lambda: now,
        lease_seconds=30,
        submit=lambda task: task(),
    )

    coordinator.dispatch(attempt)

    record = journal.get(attempt.attempt_id)
    result = results.get(attempt.attempt_id)
    journal_text = "\n".join(
        path.read_text(encoding="utf-8") for path in (tmp_path / "journal").glob("*.json")
    )
    assert record is not None
    assert record.state == "succeeded"
    assert record.receipt is not None
    assert record.receipt.exit_classification == ExitClassification.SUCCEEDED
    assert result is not None
    assert result.output_bundle == {"claims": [], "advisory_signals": []}
    assert executor.calls == ["attempt-001"]
    assert "offline synthetic evidence" not in journal_text
    assert "SYNTHETIC_PROVIDER_KEY" not in journal_text


def test_coordinator_fail_closes_when_executor_raises_without_receipt(
    tmp_path: Path,
) -> None:
    from supervisor.journal import FileAttemptJournal
    from supervisor.lifecycle import AttemptCoordinator, FileAttemptResultStore

    now = datetime.now(timezone.utc)
    attempt = _attempt()
    journal = FileAttemptJournal(tmp_path / "journal")
    journal.create(
        attempt_id=attempt.attempt_id,
        request_sha256=attempt.request_sha256(),
        lease_expires_at=now + timedelta(seconds=30),
    )
    coordinator = AttemptCoordinator(
        journal=journal,
        result_store=FileAttemptResultStore(tmp_path / "results"),
        executor=FailingExecutor(),
        clock=lambda: now,
        lease_seconds=30,
        submit=lambda task: task(),
    )

    coordinator.dispatch(attempt)

    record = journal.get(attempt.attempt_id)
    assert record is not None
    assert record.state == "failed"
    assert record.receipt is not None
    assert record.receipt.exit_classification == ExitClassification.FAILED
    assert record.receipt.message == "executor failed before receipt was produced"
    assert "super-secret-marker" not in record.model_dump_json()


def test_service_returns_terminal_receipt_and_output_from_separate_store(
    tmp_path: Path,
) -> None:
    from supervisor.journal import FileAttemptJournal
    from supervisor.lifecycle import AttemptCoordinator, FileAttemptResultStore
    from supervisor.service import create_supervisor_app

    now = datetime.now(timezone.utc)
    attempt = _attempt()
    journal = FileAttemptJournal(tmp_path / "journal")
    results = FileAttemptResultStore(tmp_path / "results")
    coordinator = AttemptCoordinator(
        journal=journal,
        result_store=results,
        executor=SuccessfulExecutor(now),
        clock=lambda: now,
        lease_seconds=30,
        submit=lambda task: task(),
    )
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=coordinator.dispatch,
        journal=journal,
        result_store=results,
        clock=lambda: now,
        lease_seconds=30,
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer supervisor-machine-token"}

    accepted = client.post(
        "/v1/attempts",
        json=attempt.model_dump(mode="json"),
        headers=headers,
    )
    status = client.get("/v1/attempts/attempt-001", headers=headers)
    result = client.get("/v1/attempts/attempt-001/result", headers=headers)

    assert accepted.status_code == 202
    assert status.json()["state"] == "succeeded"
    assert result.status_code == 200
    assert result.json()["receipt"]["exit_classification"] == "succeeded"
    assert result.json()["output_bundle"] == {"claims": [], "advisory_signals": []}
    assert result.json()["output_sha256"] == canonical_sha256(
        {"claims": [], "advisory_signals": []}
    )


def test_result_store_keeps_first_terminal_write_when_execution_finishes_after_cancel(
    tmp_path: Path,
) -> None:
    from supervisor.lifecycle import FileAttemptResultStore

    store = FileAttemptResultStore(tmp_path / "results")
    cancelled = store.put(
        attempt_id="attempt-001",
        request_sha256="b" * 64,
        output_bundle=None,
    )
    late_success = store.put(
        attempt_id="attempt-001",
        request_sha256="b" * 64,
        output_bundle={"must_not": "replace cancelled terminal result"},
    )

    assert late_success == cancelled
    assert store.get("attempt-001") == cancelled
