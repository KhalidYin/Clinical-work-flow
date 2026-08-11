from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from contracts.manifest import ArtifactManifest
from contracts.receipt import ExecutionReceipt, ExitClassification
from contracts.result import HarnessStatus


SPEC_SHA256 = "a" * 64


class RecordingDispatcher:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def __call__(self, attempt: object) -> None:
        self.calls.append(attempt)


class RecordingCanceller:
    def __init__(self, now: datetime) -> None:
        self.now = now
        self.calls: list[tuple[str, str]] = []

    def __call__(self, attempt_id: str, request_sha256: str) -> ExecutionReceipt:
        self.calls.append((attempt_id, request_sha256))
        return ExecutionReceipt(
            execution_id=f"exec-{attempt_id}",
            spec_sha256=SPEC_SHA256,
            request_sha256=request_sha256,
            harness_id="opencode@1.18.14",
            adapter_id="opencode@1.18.14",
            status=HarnessStatus.CANCELLED,
            exit_classification=ExitClassification.CANCELLED,
            message="cancelled by product worker",
            started_at=self.now,
            ended_at=self.now,
            artifact_manifest=ArtifactManifest(),
        )


class RecordingOrphanRecovery:
    def __init__(self, now: datetime) -> None:
        self.now = now
        self.calls: list[str] = []

    def __call__(self, attempt_id: str, request_sha256: str) -> ExecutionReceipt:
        self.calls.append(attempt_id)
        return ExecutionReceipt(
            execution_id=f"exec-{attempt_id}",
            spec_sha256=SPEC_SHA256,
            request_sha256=request_sha256,
            harness_id="opencode@1.18.14",
            adapter_id="opencode@1.18.14",
            status=HarnessStatus.FAILED,
            exit_classification=ExitClassification.ORPHANED,
            message="orphaned container recovered on supervisor startup",
            started_at=self.now,
            ended_at=self.now,
            artifact_manifest=ArtifactManifest(),
        )


def _input_bundle() -> dict[str, object]:
    return {
        "prompt_profile": {
            "profile_id": "atomic-candidate",
            "version": "1.1.0",
        },
        "messages": [{"role": "user", "content": "offline synthetic evidence"}],
    }


def _sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _request_body() -> dict[str, object]:
    bundle = _input_bundle()
    return {
        "contract_version": "1.0.0",
        "attempt_id": "attempt-001",
        "run_id": "run-001",
        "step_id": "enrichment",
        "generation_token": "generation-001",
        "fencing_token": "fencing-001",
        "adapter_id": "opencode@1.18.14",
        "spec_sha256": SPEC_SHA256,
        "input_sha256": _sha256(bundle),
        "input_bundle": bundle,
        "secret_refs": ["env://SYNTHETIC_PROVIDER_KEY"],
        "timeout_seconds": 60,
        "network_mode": "none",
    }


def _deepseek_request_body() -> dict[str, object]:
    body = _request_body()
    body.update(
        {
            "secret_refs": ["secret://deepseek-api-key"],
            "network_policy_id": "model-deepseek-v1",
            "model_egress": {
                "profile_id": "deepseek-v4-flash-extractor",
                "profile_version": "1.0.0",
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "endpoint": "https://api.deepseek.com:443",
                "data_boundary": "external_allowed",
            },
            "capabilities": [
                "harness.browser",
                "knowledge.read-evidence",
                "mcp.knowledge-read",
            ],
        }
    )
    return body


def test_submit_requires_machine_bearer_without_echoing_credentials() -> None:
    from supervisor.service import create_supervisor_app

    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=lambda _attempt: None,
    )
    client = TestClient(app)

    missing = client.post("/v1/attempts", json=_request_body())
    invalid = client.post(
        "/v1/attempts",
        json=_request_body(),
        headers={"Authorization": "Bearer wrong-machine-token"},
    )

    assert missing.status_code == 401
    assert missing.json() == {
        "detail": {
            "code": "machine_authentication_required",
            "message": "valid supervisor machine credential required",
        }
    }
    assert invalid.status_code == 401
    assert "wrong-machine-token" not in invalid.text
    assert "supervisor-machine-token" not in invalid.text


def test_submit_is_idempotent_for_same_attempt_and_canonical_request() -> None:
    from supervisor.service import create_supervisor_app

    dispatcher = RecordingDispatcher()
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=dispatcher,
    )
    client = TestClient(app)
    body = _request_body()
    headers = {"Authorization": "Bearer supervisor-machine-token"}

    first = client.post("/v1/attempts", json=body, headers=headers)
    replay = client.post("/v1/attempts", json=body, headers=headers)

    expected = {
        "contract_version": "1.0.0",
        "attempt_id": "attempt-001",
        "request_sha256": _sha256(body),
        "state": "accepted",
        "receipt": None,
    }
    assert first.status_code == 202
    assert first.json() == expected
    assert replay.status_code == 202
    assert replay.json() == expected
    assert len(dispatcher.calls) == 1
    dispatched = dispatcher.calls[0]
    assert getattr(dispatched, "attempt_id") == "attempt-001"
    assert getattr(dispatched, "network_mode") == "none"
    assert "SYNTHETIC_PROVIDER_KEY" not in first.text


def test_submit_rejects_same_attempt_with_different_request_hash() -> None:
    from supervisor.service import create_supervisor_app

    dispatcher = RecordingDispatcher()
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=dispatcher,
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer supervisor-machine-token"}
    original = _request_body()
    changed = _request_body()
    changed_bundle = _input_bundle()
    changed_bundle["messages"] = [{"role": "user", "content": "different evidence"}]
    changed["input_bundle"] = changed_bundle
    changed["input_sha256"] = _sha256(changed_bundle)

    first = client.post("/v1/attempts", json=original, headers=headers)
    conflict = client.post("/v1/attempts", json=changed, headers=headers)

    assert first.status_code == 202
    assert conflict.status_code == 409
    assert conflict.json() == {
        "detail": {
            "code": "attempt_conflict",
            "message": "attempt_id already has a different request hash",
        }
    }
    assert len(dispatcher.calls) == 1


def test_submit_rejects_spec_hash_outside_supervisor_allowlist() -> None:
    from supervisor.service import create_supervisor_app

    dispatcher = RecordingDispatcher()
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=dispatcher,
    )
    client = TestClient(app)
    body = _request_body()
    body["spec_sha256"] = "b" * 64

    response = client.post(
        "/v1/attempts",
        json=body,
        headers={"Authorization": "Bearer supervisor-machine-token"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": {"code": "spec_not_allowed", "message": "spec hash is not allowed"}
    }
    assert dispatcher.calls == []


def test_submit_rejects_policy_that_is_defined_but_not_runtime_available() -> None:
    from supervisor.service import create_supervisor_app

    dispatcher = RecordingDispatcher()
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=dispatcher,
    )

    response = TestClient(app).post(
        "/v1/attempts",
        json=_deepseek_request_body(),
        headers={"Authorization": "Bearer supervisor-machine-token"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": {
            "code": "network_policy_not_available",
            "message": "requested network policy is not available",
        }
    }
    assert dispatcher.calls == []


def test_submit_rejects_unknown_future_policy_without_disabling_capabilities() -> None:
    from supervisor.service import create_supervisor_app

    dispatcher = RecordingDispatcher()
    body = _request_body()
    body["network_policy_id"] = "research-public-web-v1"
    body["capabilities"] = ["harness.browser"]
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=dispatcher,
    )

    response = TestClient(app).post(
        "/v1/attempts",
        json=body,
        headers={"Authorization": "Bearer supervisor-machine-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "network_policy_not_available"
    assert dispatcher.calls == []


def test_authorized_model_policy_preserves_browser_skill_and_mcp_capabilities() -> None:
    from supervisor.network_policy import p16_network_policy_registry
    from supervisor.service import create_supervisor_app

    dispatcher = RecordingDispatcher()
    registry = p16_network_policy_registry(
        available_policy_ids=frozenset({"none", "model-deepseek-v1"})
    )
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=dispatcher,
        network_policy_registry=registry,
    )

    response = TestClient(app).post(
        "/v1/attempts",
        json=_deepseek_request_body(),
        headers={"Authorization": "Bearer supervisor-machine-token"},
    )

    assert response.status_code == 202
    assert len(dispatcher.calls) == 1
    dispatched = dispatcher.calls[0]
    assert getattr(dispatched, "capabilities") == frozenset(
        {"harness.browser", "knowledge.read-evidence", "mcp.knowledge-read"}
    )
    evidence = registry.authorize(dispatched)
    assert evidence.policy_id == "model-deepseek-v1"
    assert evidence.allowed_endpoints == ("api.deepseek.com:443",)
    assert "secret" not in evidence.model_dump_json().lower()


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ({"profile_id": "unreviewed-profile"}, "network_policy_binding_mismatch"),
        ({"model": "deepseek-chat"}, "network_policy_binding_mismatch"),
        ({"endpoint": "https://api.deepseek.example:443"}, "network_policy_binding_mismatch"),
        ({"data_boundary": "prohibited"}, "network_policy_binding_mismatch"),
    ],
)
def test_model_policy_rejects_binding_drift_before_dispatch(
    mutation: dict[str, str],
    expected_code: str,
) -> None:
    from supervisor.network_policy import p16_network_policy_registry
    from supervisor.service import create_supervisor_app

    dispatcher = RecordingDispatcher()
    body = _deepseek_request_body()
    model_egress = dict(body["model_egress"])
    model_egress.update(mutation)
    body["model_egress"] = model_egress
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=dispatcher,
        network_policy_registry=p16_network_policy_registry(
            available_policy_ids=frozenset({"none", "model-deepseek-v1"})
        ),
    )

    response = TestClient(app).post(
        "/v1/attempts",
        json=body,
        headers={"Authorization": "Bearer supervisor-machine-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == expected_code
    assert dispatcher.calls == []


def test_model_policy_rejects_unknown_secret_name_before_dispatch() -> None:
    from supervisor.network_policy import p16_network_policy_registry
    from supervisor.service import create_supervisor_app

    dispatcher = RecordingDispatcher()
    body = _deepseek_request_body()
    body["secret_refs"] = ["secret://unknown-provider-key"]
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=dispatcher,
        network_policy_registry=p16_network_policy_registry(
            available_policy_ids=frozenset({"none", "model-deepseek-v1"})
        ),
    )

    response = TestClient(app).post(
        "/v1/attempts",
        json=body,
        headers={"Authorization": "Bearer supervisor-machine-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "secret_reference_not_allowed",
        "message": "secret reference is not allowed by network policy",
    }
    assert dispatcher.calls == []


def test_none_policy_rejects_unknown_secret_name_before_dispatch() -> None:
    from supervisor.service import create_supervisor_app

    dispatcher = RecordingDispatcher()
    body = _request_body()
    body["secret_refs"] = ["secret://unknown-provider-key"]
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=dispatcher,
    )

    response = TestClient(app).post(
        "/v1/attempts",
        json=body,
        headers={"Authorization": "Bearer supervisor-machine-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "secret_reference_not_allowed"
    assert dispatcher.calls == []


def test_submit_rejects_input_hash_mismatch_without_echoing_bundle() -> None:
    from supervisor.service import create_supervisor_app

    dispatcher = RecordingDispatcher()
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=dispatcher,
    )
    client = TestClient(app)
    body = _request_body()
    body["input_sha256"] = "c" * 64

    response = client.post(
        "/v1/attempts",
        json=body,
        headers={"Authorization": "Bearer supervisor-machine-token"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "input_hash_mismatch",
            "message": "input_sha256 does not match input_bundle",
        }
    }
    assert "offline synthetic evidence" not in response.text
    assert "SYNTHETIC_PROVIDER_KEY" not in response.text
    assert dispatcher.calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("image_ref", "attacker.example/image:latest"),
        ("command", ["sh", "-c", "echo injected-command"]),
        ("mounts", [{"source": "/", "target": "/host"}]),
        ("environment", {"INJECTED_SECRET": "credential-marker"}),
        ("network_allowlist", ["attacker.example"]),
        ("network_mode", "bridge"),
        ("adapter_id", "arbitrary-runtime@latest"),
    ],
)
def test_submit_rejects_container_policy_injection(field: str, value: object) -> None:
    from supervisor.service import create_supervisor_app

    dispatcher = RecordingDispatcher()
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=dispatcher,
    )
    client = TestClient(app)
    body = _request_body()
    body[field] = value

    response = client.post(
        "/v1/attempts",
        json=body,
        headers={"Authorization": "Bearer supervisor-machine-token"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "invalid_request_contract",
            "message": "attempt request does not match the supervisor contract",
        }
    }
    assert "credential-marker" not in response.text
    assert "injected-command" not in response.text
    assert dispatcher.calls == []


def test_status_rejects_unknown_attempt_without_dispatching() -> None:
    from supervisor.service import create_supervisor_app

    dispatcher = RecordingDispatcher()
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=dispatcher,
    )
    client = TestClient(app)

    response = client.get(
        "/v1/attempts/missing-attempt",
        headers={"Authorization": "Bearer supervisor-machine-token"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": {"code": "attempt_not_found", "message": "attempt does not exist"}
    }
    assert dispatcher.calls == []


def test_submit_recovers_idempotent_status_from_durable_journal_after_restart(
    tmp_path: Path,
) -> None:
    from supervisor.journal import FileAttemptJournal
    from supervisor.service import create_supervisor_app

    now = datetime.now(timezone.utc)
    journal = FileAttemptJournal(tmp_path)
    first_dispatcher = RecordingDispatcher()
    first_app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=first_dispatcher,
        journal=journal,
        clock=lambda: now,
        lease_seconds=30,
    )
    headers = {"Authorization": "Bearer supervisor-machine-token"}
    first = TestClient(first_app).post("/v1/attempts", json=_request_body(), headers=headers)

    restarted_dispatcher = RecordingDispatcher()
    restarted_app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=restarted_dispatcher,
        journal=FileAttemptJournal(tmp_path),
        clock=lambda: now + timedelta(seconds=1),
        lease_seconds=30,
    )
    recovered = TestClient(restarted_app).post(
        "/v1/attempts",
        json=_request_body(),
        headers=headers,
    )

    assert first.status_code == 202
    assert recovered.status_code == 202
    assert recovered.json() == first.json()
    assert len(first_dispatcher.calls) == 1
    assert restarted_dispatcher.calls == []


def test_heartbeat_renews_durable_attempt_lease(tmp_path: Path) -> None:
    from supervisor.journal import FileAttemptJournal
    from supervisor.service import create_supervisor_app

    now = datetime.now(timezone.utc)
    current_time = [now]
    journal = FileAttemptJournal(tmp_path)
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=RecordingDispatcher(),
        journal=journal,
        clock=lambda: current_time[0],
        lease_seconds=30,
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer supervisor-machine-token"}
    client.post("/v1/attempts", json=_request_body(), headers=headers)
    before = journal.get("attempt-001")
    current_time[0] = now + timedelta(seconds=10)

    heartbeat = client.post("/v1/attempts/attempt-001/heartbeat", headers=headers)
    after = journal.get("attempt-001")

    assert heartbeat.status_code == 200
    assert heartbeat.json()["state"] == "accepted"
    assert before is not None
    assert after is not None
    assert before.lease_expires_at == now + timedelta(seconds=30)
    assert after.lease_expires_at == now + timedelta(seconds=40)


def test_cancel_is_idempotent_and_returns_same_terminal_receipt(tmp_path: Path) -> None:
    from supervisor.journal import FileAttemptJournal
    from supervisor.lifecycle import FileAttemptResultStore
    from supervisor.service import create_supervisor_app

    now = datetime.now(timezone.utc)
    canceller = RecordingCanceller(now)
    result_store = FileAttemptResultStore(tmp_path / "results")
    app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=RecordingDispatcher(),
        cancel_attempt=canceller,
        journal=FileAttemptJournal(tmp_path),
        result_store=result_store,
        clock=lambda: now,
        lease_seconds=30,
    )
    client = TestClient(app)
    headers = {"Authorization": "Bearer supervisor-machine-token"}
    accepted = client.post("/v1/attempts", json=_request_body(), headers=headers)

    first = client.post("/v1/attempts/attempt-001/cancel", headers=headers)
    replay = client.post("/v1/attempts/attempt-001/cancel", headers=headers)
    result = client.get("/v1/attempts/attempt-001/result", headers=headers)

    assert accepted.status_code == 202
    assert first.status_code == 200
    assert first.json()["state"] == "cancelled"
    assert first.json()["receipt"]["exit_classification"] == "cancelled"
    assert replay.json() == first.json()
    assert canceller.calls == [("attempt-001", accepted.json()["request_sha256"])]
    assert result.status_code == 200
    assert result.json()["receipt"] == first.json()["receipt"]
    assert result.json()["output_bundle"] is None


def test_startup_recovers_active_journal_attempt_once_as_orphan(tmp_path: Path) -> None:
    from supervisor.journal import FileAttemptJournal
    from supervisor.service import create_supervisor_app

    now = datetime.now(timezone.utc)
    journal = FileAttemptJournal(tmp_path)
    journal.create(
        attempt_id="attempt-orphan",
        request_sha256="e" * 64,
        lease_expires_at=now + timedelta(seconds=30),
    )
    recovery = RecordingOrphanRecovery(now)

    first_app = create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=RecordingDispatcher(),
        recover_orphan=recovery,
        journal=journal,
        clock=lambda: now,
        lease_seconds=30,
    )
    headers = {"Authorization": "Bearer supervisor-machine-token"}
    first_status = TestClient(first_app).get(
        "/v1/attempts/attempt-orphan",
        headers=headers,
    )
    second_recovery = RecordingOrphanRecovery(now)
    create_supervisor_app(
        machine_token="supervisor-machine-token",
        allowed_spec_sha256=frozenset({SPEC_SHA256}),
        dispatch=RecordingDispatcher(),
        recover_orphan=second_recovery,
        journal=FileAttemptJournal(tmp_path),
        clock=lambda: now,
        lease_seconds=30,
    )

    assert first_status.status_code == 200
    assert first_status.json()["state"] == "orphaned"
    assert first_status.json()["receipt"]["exit_classification"] == "orphaned"
    assert recovery.calls == ["attempt-orphan"]
    assert second_recovery.calls == []
