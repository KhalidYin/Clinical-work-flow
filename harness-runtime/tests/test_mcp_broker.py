"""H0-E step-scoped MCP broker tests.

The broker is the protocol AND the security boundary: every request is
re-validated server-side (attempt auth, generation/fencing token, spec hash,
capability, parameter schema, path/data boundary, idempotency key) and every
tool call produces an audit event. All bypass attempts fail closed.
"""

from __future__ import annotations

import json
from pathlib import Path


from supervisor.mcp_broker import (
    McpAttemptAuth,
    McpError,
    McpServer,
    ToolHandler,
)


def _auth(*, attempt_id: str = "attempt-1", token: str = "tok-1") -> McpAttemptAuth:
    return McpAttemptAuth(
        attempt_id=attempt_id,
        attempt_token=token,
        generation_token="gen-1",
        spec_sha256="a" * 64,
        allowed_tools=frozenset({"read_input"}),
        input_root=Path("/inputs"),
    )


def _server(tmp_path: Path) -> McpServer:
    auth = _auth()
    real_root = tmp_path / "inputs"
    real_root.mkdir()
    (real_root / "evidence.json").write_text('{"id": "ev-1"}', encoding="utf-8")

    def read_input(path: str) -> dict[str, object]:
        target = (real_root / path).resolve()
        if real_root.resolve() not in target.parents:
            raise McpError(-32000, "path escapes the input root")
        return {"content": target.read_text(encoding="utf-8")}

    server = McpServer(
        authorized_attempts={auth.attempt_id: auth},
        tools={"read_input": ToolHandler(parameter_schema={"path": {"type": "string"}}, handler=read_input)},
    )
    return server


def _call(server: McpServer, *, session: str, method: str, params: dict, msg_id: int = 1) -> dict:
    return json.loads(
        server.handle_line(
            json.dumps(
                {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}
            )
        )
    )


def _initialize(server: McpServer, *, token: str = "tok-1") -> dict:
    return _call(
        server,
        session="",
        method="initialize",
        params={
            "attempt_id": "attempt-1",
            "attempt_token": token,
            "generation_token": "gen-1",
            "spec_sha256": "a" * 64,
        },
    )


# --- authentication / identity --------------------------------------------


def test_initialize_with_valid_credentials_lists_allowed_tools(tmp_path: Path) -> None:
    server = _server(tmp_path)
    response = _initialize(server)
    assert "error" not in response
    assert response["result"]["tools"] == ["read_input"]


def test_initialize_rejects_wrong_attempt_token(tmp_path: Path) -> None:
    server = _server(tmp_path)
    response = _initialize(server, token="wrong-token")
    assert "error" in response
    assert response["error"]["code"] == -32000


def test_initialize_rejects_wrong_generation_token(tmp_path: Path) -> None:
    server = _server(tmp_path)
    response = _call(
        server,
        session="",
        method="initialize",
        params={
            "attempt_id": "attempt-1",
            "attempt_token": "tok-1",
            "generation_token": "stale-gen",
            "spec_sha256": "a" * 64,
        },
    )
    assert "error" in response


def test_initialize_rejects_wrong_spec_sha256(tmp_path: Path) -> None:
    server = _server(tmp_path)
    response = _call(
        server,
        session="",
        method="initialize",
        params={
            "attempt_id": "attempt-1",
            "attempt_token": "tok-1",
            "generation_token": "gen-1",
            "spec_sha256": "b" * 64,
        },
    )
    assert "error" in response


def test_tool_call_requires_initialize_first(tmp_path: Path) -> None:
    server = _server(tmp_path)
    response = _call(
        server,
        session="",
        method="tools/call",
        params={"name": "read_input", "arguments": {"path": "evidence.json"}, "idempotency_key": "k1"},
    )
    assert "error" in response


def test_cross_attempt_credential_rejected(tmp_path: Path) -> None:
    """A credential from another attempt must never authorize this session."""
    server = _server(tmp_path)
    auth = _auth(attempt_id="attempt-1", token="tok-1")
    other = McpAttemptAuth(
        attempt_id="attempt-2",
        attempt_token="tok-2",
        generation_token="gen-1",
        spec_sha256="a" * 64,
        allowed_tools=frozenset({"read_input"}),
        input_root=Path("/inputs"),
    )
    server = McpServer(
        authorized_attempts={auth.attempt_id: auth, other.attempt_id: other},
        tools={"read_input": ToolHandler(parameter_schema={"path": {"type": "string"}}, handler=lambda path: {})},
    )
    response = _call(
        server,
        session="",
        method="initialize",
        params={
            "attempt_id": "attempt-1",
            "attempt_token": "tok-2",  # attempt-2's token
            "generation_token": "gen-1",
            "spec_sha256": "a" * 64,
        },
    )
    assert "error" in response


# --- capability / parameters / path boundary -------------------------------


def test_unknown_tool_rejected(tmp_path: Path) -> None:
    server = _server(tmp_path)
    _initialize(server)
    response = _call(
        server,
        session="",
        method="tools/call",
        params={"name": "not_registered", "arguments": {}, "idempotency_key": "k1"},
    )
    assert "error" in response
    assert response["error"]["code"] == -32601


def test_invalid_arguments_rejected(tmp_path: Path) -> None:
    server = _server(tmp_path)
    _initialize(server)
    response = _call(
        server,
        session="",
        method="tools/call",
        params={"name": "read_input", "arguments": {"path": 123}, "idempotency_key": "k1"},
    )
    assert "error" in response


def test_path_traversal_rejected(tmp_path: Path) -> None:
    server = _server(tmp_path)
    _initialize(server)
    response = _call(
        server,
        session="",
        method="tools/call",
        params={"name": "read_input", "arguments": {"path": "../../etc/passwd"}, "idempotency_key": "k1"},
    )
    assert "error" in response


def test_successful_tool_call_returns_result(tmp_path: Path) -> None:
    server = _server(tmp_path)
    _initialize(server)
    response = _call(
        server,
        session="",
        method="tools/call",
        params={"name": "read_input", "arguments": {"path": "evidence.json"}, "idempotency_key": "k1"},
    )
    assert "error" not in response
    assert response["result"]["content"] == '{"id": "ev-1"}'


# --- idempotency -----------------------------------------------------------


def test_idempotency_key_returns_cached_result(tmp_path: Path) -> None:
    server = _server(tmp_path)
    _initialize(server)
    calls: list[str] = []

    def read_input(path: str) -> dict[str, object]:
        calls.append(path)
        return {"content": "value"}

    server = McpServer(
        authorized_attempts={_auth().attempt_id: _auth()},
        tools={"read_input": ToolHandler(parameter_schema={"path": {"type": "string"}}, handler=read_input)},
    )
    _initialize(server)
    first = _call(
        server,
        session="",
        method="tools/call",
        params={"name": "read_input", "arguments": {"path": "a.json"}, "idempotency_key": "dup-1"},
    )
    second = _call(
        server,
        session="",
        method="tools/call",
        params={"name": "read_input", "arguments": {"path": "a.json"}, "idempotency_key": "dup-1"},
    )
    assert first["result"] == second["result"]
    assert calls == ["a.json"]  # handler executed exactly once


# --- audit -----------------------------------------------------------------


def test_every_tool_call_produces_audit_event(tmp_path: Path) -> None:
    server = _server(tmp_path)
    _initialize(server)
    _call(
        server,
        session="",
        method="tools/call",
        params={"name": "read_input", "arguments": {"path": "evidence.json"}, "idempotency_key": "k-audit"},
    )
    _call(
        server,
        session="",
        method="tools/call",
        params={"name": "read_input", "arguments": {"path": "../escape"}, "idempotency_key": "k-bad"},
    )
    audit = server.audit_events()
    assert len(audit) == 2
    assert audit[0]["tool"] == "read_input"
    assert audit[0]["result"] == "succeeded"
    assert audit[1]["result"] == "failed"
    assert all(event["attempt_id"] == "attempt-1" for event in audit)


def test_audit_never_exposes_attempt_token(tmp_path: Path) -> None:
    server = _server(tmp_path)
    _initialize(server)
    _call(
        server,
        session="",
        method="tools/call",
        params={"name": "read_input", "arguments": {"path": "evidence.json"}, "idempotency_key": "k1"},
    )
    serialized = json.dumps(server.audit_events())
    assert "tok-1" not in serialized
    assert "attempt_token" not in serialized
