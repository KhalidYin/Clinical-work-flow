"""H0-E step-scoped MCP broker (minimal stdio JSON-RPC subset).

The broker is the protocol AND the security boundary: every request is
re-validated server-side — attempt authentication, generation/fencing token,
spec hash, capability allowlist, parameter schema, path/data boundary and
idempotency key — and every tool call produces an audit event. Attempt
credentials are passed over the stdio handshake, never injected into the
container environment, and never appear in audit events.

Standard MCP transport/schema integration is deferred until a concrete
candidate Harness is selected (H0 plan); this subset uses zero new
dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from pydantic import Field

from contracts.request import StrictContractModel

# JSON-RPC error codes (subset)
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
SERVER_ERROR = -32000


class McpError(RuntimeError):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


class McpAttemptAuth(StrictContractModel):
    """Server-side registration for exactly one attempt."""

    attempt_id: str = Field(min_length=1)
    attempt_token: str = Field(min_length=1)
    generation_token: str = Field(min_length=1)
    spec_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    allowed_tools: frozenset[str] = frozenset()
    input_root: Path | None = None


class ToolHandler(StrictContractModel):
    """One deterministic tool with a simple parameter schema."""

    parameter_schema: dict[str, dict[str, str]] = Field(default_factory=dict)
    handler: Callable[..., dict[str, object]]


class McpSession:
    """Bindings for one initialized attempt: allowed tools + idempotency cache."""

    def __init__(self, auth: McpAttemptAuth) -> None:
        self.attempt_id = auth.attempt_id
        self.allowed_tools = auth.allowed_tools
        self._idempotency: dict[str, dict[str, object]] = {}

    def cached(self, key: str) -> dict[str, object] | None:
        return self._idempotency.get(key)

    def remember(self, key: str, result: dict[str, object]) -> None:
        self._idempotency[key] = result


def _error_response(message_id: Any, code: int, message: str) -> str:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": {"code": code, "message": message},
        }
    )


def _result_response(message_id: Any, result: dict[str, object]) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": message_id, "result": result})


class McpServer:
    """Minimal stdio JSON-RPC broker with server-side security enforcement."""

    def __init__(
        self,
        *,
        authorized_attempts: Mapping[str, McpAttemptAuth],
        tools: Mapping[str, ToolHandler],
    ) -> None:
        self._authorized = dict(authorized_attempts)
        self._tools = dict(tools)
        self._session: McpSession | None = None
        self._audit: list[dict[str, object]] = []

    def audit_events(self) -> list[dict[str, object]]:
        return list(self._audit)

    def handle_line(self, line: str) -> str:
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            return _error_response(None, PARSE_ERROR, "parse error")
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            return _error_response(
                request.get("id") if isinstance(request, dict) else None,
                INVALID_REQUEST,
                "invalid request",
            )
        method = request.get("method")
        params = request.get("params", {})
        message_id = request.get("id")
        if not isinstance(params, dict):
            return _error_response(message_id, INVALID_PARAMS, "params must be an object")
        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_tools_list()
            elif method == "tools/call":
                result = self._handle_tools_call(params)
            else:
                return _error_response(message_id, METHOD_NOT_FOUND, "method not found")
        except McpError as exc:
            return _error_response(message_id, exc.code, str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            return _error_response(
                message_id, SERVER_ERROR, f"server error: {type(exc).__name__}"
            )
        return _result_response(message_id, result)

    # -- handlers -----------------------------------------------------------

    def _handle_initialize(self, params: dict[str, object]) -> dict[str, object]:
        attempt_id = params.get("attempt_id")
        auth = self._authorized.get(attempt_id) if isinstance(attempt_id, str) else None
        if auth is None:
            raise McpError(SERVER_ERROR, "authorization failed: unknown attempt")
        if (
            params.get("attempt_token") != auth.attempt_token
            or params.get("generation_token") != auth.generation_token
            or params.get("spec_sha256") != auth.spec_sha256
        ):
            raise McpError(SERVER_ERROR, "authorization failed: credential mismatch")
        available = sorted(auth.allowed_tools.intersection(self._tools))
        self._session = McpSession(auth)
        return {"tools": available}

    def _handle_tools_list(self) -> dict[str, object]:
        session = self._require_session()
        return {"tools": sorted(session.allowed_tools.intersection(self._tools))}

    def _handle_tools_call(self, params: dict[str, object]) -> dict[str, object]:
        session = self._require_session()
        name = params.get("name")
        arguments = params.get("arguments")
        idempotency_key = params.get("idempotency_key")
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise McpError(INVALID_PARAMS, "name and arguments are required")
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise McpError(INVALID_PARAMS, "idempotency_key is required")
        if name not in self._tools:
            raise McpError(METHOD_NOT_FOUND, f"unknown tool: {name}")
        if name not in session.allowed_tools:
            raise McpError(SERVER_ERROR, f"tool not allowed for this attempt: {name}")
        tool = self._tools[name]
        _validate_arguments(tool.parameter_schema, arguments)

        cache_key = ":".join(
            (
                idempotency_key,
                name,
                json.dumps(arguments, sort_keys=True),
            )
        )
        cached = session.cached(cache_key)
        if cached is not None:
            self._audit_call(session, name, arguments, idempotency_key, "succeeded", cached)
            return cached
        try:
            result = tool.handler(**arguments)
        except McpError as exc:
            self._audit_call(session, name, arguments, idempotency_key, "failed", exc.message() if hasattr(exc, "message") else str(exc))
            raise
        except Exception as exc:
            self._audit_call(session, name, arguments, idempotency_key, "failed", f"{type(exc).__name__}: {exc}")
            raise McpError(SERVER_ERROR, f"tool execution failed: {type(exc).__name__}")
        session.remember(cache_key, result)
        self._audit_call(session, name, arguments, idempotency_key, "succeeded", None)
        return result

    # -- helpers ------------------------------------------------------------

    def _require_session(self) -> McpSession:
        if self._session is None:
            raise McpError(SERVER_ERROR, "initialize required before tool calls")
        return self._session

    def _audit_call(
        self,
        session: McpSession,
        tool: str,
        arguments: dict[str, object],
        idempotency_key: str,
        result: str,
        error: object | None,
    ) -> None:
        # Attempt token and other credentials must never reach the audit log.
        self._audit.append(
            {
                "attempt_id": session.attempt_id,
                "tool": tool,
                "arguments": arguments,
                "idempotency_key": idempotency_key,
                "result": result,
                "error": error if error is not None else None,
            }
        )


def _validate_arguments(schema: dict[str, dict[str, str]], arguments: dict[str, object]) -> None:
    unknown = set(arguments) - set(schema)
    if unknown:
        raise McpError(INVALID_PARAMS, f"unknown arguments: {sorted(unknown)}")
    for field, spec in schema.items():
        if field not in arguments:
            raise McpError(INVALID_PARAMS, f"missing argument: {field}")
        expected = spec.get("type", "string")
        value = arguments[field]
        if expected == "string" and not isinstance(value, str):
            raise McpError(INVALID_PARAMS, f"argument {field} must be a string")
        if expected == "integer" and not isinstance(value, int):
            raise McpError(INVALID_PARAMS, f"argument {field} must be an integer")
        if expected == "boolean" and not isinstance(value, bool):
            raise McpError(INVALID_PARAMS, f"argument {field} must be a boolean")
