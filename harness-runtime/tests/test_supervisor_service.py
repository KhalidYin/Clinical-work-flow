from __future__ import annotations

import hashlib
import json

import pytest
from fastapi.testclient import TestClient


SPEC_SHA256 = "a" * 64


class RecordingDispatcher:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def __call__(self, attempt: object) -> None:
        self.calls.append(attempt)


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
