"""Deterministic OpenAI Chat Completions mock for the P15 local POC."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from collections.abc import Mapping
from typing import Any


@dataclass(frozen=True, slots=True)
class MockResponse:
    status: int
    content_type: str
    body: str


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_api_key(environ: Mapping[str, str]) -> str:
    """Load the synthetic POC credential only from a mounted secret file."""

    key_file = environ.get("P15_MOCK_API_KEY_FILE")
    if not key_file:
        raise RuntimeError("P15_MOCK_API_KEY_FILE secret file is required")
    try:
        api_key = Path(key_file).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError("P15 mock key secret file is unavailable") from exc
    if not api_key:
        raise RuntimeError("P15 mock key secret file is empty")
    return api_key


def _candidate() -> dict[str, object]:
    return {
        "candidate_group_id": "candidate-poc-001",
        "knowledge_type": "poc_claim",
        "claim": "Synthetic evidence supports the P15 POC claim.",
        "scope": {"source": "synthetic-p15"},
        "applicability": {"data_boundary": "external_allowed"},
        "conditions": [],
        "exceptions": [],
        "evidence_ids": ["evidence-poc-001"],
        "relation_proposals": [],
        "advisory_signals": [],
        "confidence": 1.0,
    }


class ScriptedOpenAIMock:
    """Require one Evidence tool result before emitting the fixed Candidate."""

    def __init__(
        self,
        *,
        api_key: str,
        audit_path: Path | None = None,
        scenario: str = "success",
    ) -> None:
        if not api_key:
            raise ValueError("mock api_key must not be empty")
        if scenario not in {"success", "unauthorized_tool"}:
            raise ValueError("unsupported P15 mock scenario")
        self._api_key = api_key
        self._audit_path = audit_path
        self._scenario = scenario
        self._unauthorized_issued = False
        self.audits: list[dict[str, object]] = []

    def respond(
        self,
        *,
        path: str,
        authorization: str | None,
        payload: object,
    ) -> MockResponse:
        if path not in {"/v1/chat/completions", "/v1/responses"}:
            audit = {
                "path": path,
                "rejected": True,
                "request_sha256": _canonical_sha256(payload),
                "payload_keys": (
                    sorted(str(key) for key in payload)
                    if isinstance(payload, dict)
                    else []
                ),
            }
            self.audits.append(audit)
            self._write_audit(audit)
            return self._error(404, "not_found")
        if authorization != f"Bearer {self._api_key}":
            return self._error(401, "unauthorized")
        if not isinstance(payload, dict):
            return self._error(400, "invalid_request")
        if path == "/v1/responses":
            return self._respond_responses(payload)
        model = payload.get("model")
        messages = payload.get("messages")
        tools = payload.get("tools")
        stream = payload.get("stream", False)
        if (
            not isinstance(model, str)
            or not isinstance(messages, list)
            or not isinstance(tools, list)
            or not isinstance(stream, bool)
        ):
            return self._error(400, "invalid_request")
        tool_names = self._tool_names(tools)
        evidence_tools = [name for name in tool_names if name.endswith("read_evidence")]
        if len(evidence_tools) != 1:
            return self._error(400, "read_evidence_tool_required")
        has_tool_result = any(
            isinstance(message, dict)
            and message.get("role") == "tool"
            and "evidence-poc-001" in str(message.get("content", ""))
            for message in messages
        )
        audit = {
            "path": path,
            "model": model,
            "request_sha256": _canonical_sha256(payload),
            "tool_names": tool_names,
            "has_tool_result": has_tool_result,
            "stream": stream,
        }
        self.audits.append(audit)
        self._write_audit(audit)
        response = (
            self._candidate_response(model)
            if has_tool_result
            else self._tool_call_response(model, evidence_tools[0])
        )
        if stream:
            return MockResponse(
                status=200,
                content_type="text/event-stream",
                body=self._as_sse(response),
            )
        return MockResponse(
            status=200,
            content_type="application/json",
            body=json.dumps(response, ensure_ascii=False, separators=(",", ":")),
        )

    def _respond_responses(self, payload: dict[str, object]) -> MockResponse:
        model = payload.get("model")
        input_items = payload.get("input")
        tools = payload.get("tools", [])
        stream = payload.get("stream", False)
        if (
            not isinstance(model, str)
            or not isinstance(input_items, list)
            or not isinstance(tools, list)
            or stream is not True
        ):
            return self._error(400, "invalid_request")
        tool_names = self._tool_names(tools)
        output_count = self._count_typed_items(input_items, "function_call_output")
        audit = {
            "path": "/v1/responses",
            "model": model,
            "request_sha256": _canonical_sha256(payload),
            "tool_names": tool_names,
            "function_call_output_count": output_count,
            "stream": True,
        }
        self.audits.append(audit)
        self._write_audit(audit)
        if not tool_names:
            body = self._responses_text_sse(model, "P15 Candidate")
        elif self._scenario == "unauthorized_tool" and not self._unauthorized_issued:
            self._unauthorized_issued = True
            body = self._responses_function_sse(
                model,
                call_id="call-unauthorized-p15",
                name="bash",
                arguments={
                    "command": "touch /staging/unauthorized-marker",
                    "description": "P15 denied-tool probe",
                },
            )
        elif self._scenario == "unauthorized_tool":
            body = self._responses_text_sse(model, "not-json-after-denied-tool")
        elif output_count == 0 and "skill" in tool_names:
            body = self._responses_function_sse(
                model,
                call_id="call-skill-p15",
                name="skill",
                arguments={"name": "evidence-candidate"},
            )
        elif output_count <= 1:
            evidence_tools = [name for name in tool_names if name.endswith("read_evidence")]
            if len(evidence_tools) != 1:
                return self._error(400, "read_evidence_tool_required")
            body = self._responses_function_sse(
                model,
                call_id="call-evidence-p15",
                name=evidence_tools[0],
                arguments={"evidence_id": "evidence-poc-001"},
            )
        else:
            body = self._responses_text_sse(
                model,
                json.dumps(_candidate(), ensure_ascii=False, separators=(",", ":")),
            )
        return MockResponse(
            status=200,
            content_type="text/event-stream",
            body=body,
        )

    @staticmethod
    def _tool_names(tools: list[object]) -> list[str]:
        names: list[str] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            function = tool.get("function")
            if isinstance(function, dict) and isinstance(function.get("name"), str):
                names.append(str(function["name"]))
            elif tool.get("type") == "function" and isinstance(tool.get("name"), str):
                names.append(str(tool["name"]))
        return names

    @classmethod
    def _count_typed_items(cls, value: object, item_type: str) -> int:
        if isinstance(value, list):
            return sum(cls._count_typed_items(item, item_type) for item in value)
        if isinstance(value, dict):
            return int(value.get("type") == item_type) + sum(
                cls._count_typed_items(item, item_type) for item in value.values()
            )
        return 0

    @staticmethod
    def _response_shell(
        model: str,
        *,
        status: str,
        output: list[dict[str, object]],
    ) -> dict[str, object]:
        return {
            "id": "resp_p15",
            "object": "response",
            "created_at": 0,
            "status": status,
            "error": None,
            "incomplete_details": None,
            "instructions": None,
            "max_output_tokens": None,
            "model": model,
            "output": output,
            "parallel_tool_calls": False,
            "previous_response_id": None,
            "reasoning": {"effort": None, "summary": None},
            "store": False,
            "temperature": 0,
            "text": {"format": {"type": "text"}},
            "tool_choice": "auto",
            "tools": [],
            "top_p": 1,
            "truncation": "disabled",
            "usage": (
                None
                if status != "completed"
                else {
                    "input_tokens": 1,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens": 1,
                    "output_tokens_details": {"reasoning_tokens": 0},
                    "total_tokens": 2,
                }
            ),
            "metadata": {},
        }

    @classmethod
    def _responses_function_sse(
        cls,
        model: str,
        *,
        call_id: str,
        name: str,
        arguments: dict[str, str],
    ) -> str:
        encoded_arguments = json.dumps(arguments, separators=(",", ":"))
        item = {
            "id": f"fc_{call_id}",
            "type": "function_call",
            "call_id": call_id,
            "name": name,
            "arguments": encoded_arguments,
            "status": "completed",
        }
        events = [
            {
                "type": "response.created",
                "response": cls._response_shell(model, status="in_progress", output=[]),
            },
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {**item, "arguments": "", "status": "in_progress"},
            },
            {
                "type": "response.function_call_arguments.delta",
                "item_id": item["id"],
                "output_index": 0,
                "delta": encoded_arguments,
            },
            {
                "type": "response.function_call_arguments.done",
                "item_id": item["id"],
                "output_index": 0,
                "arguments": encoded_arguments,
            },
            {"type": "response.output_item.done", "output_index": 0, "item": item},
            {
                "type": "response.completed",
                "response": cls._response_shell(
                    model,
                    status="completed",
                    output=[item],
                ),
            },
        ]
        return cls._responses_events(events)

    @classmethod
    def _responses_text_sse(cls, model: str, text: str) -> str:
        content = {"type": "output_text", "text": text, "annotations": []}
        item = {
            "id": "msg_p15",
            "type": "message",
            "role": "assistant",
            "status": "completed",
            "content": [content],
        }
        events = [
            {
                "type": "response.created",
                "response": cls._response_shell(model, status="in_progress", output=[]),
            },
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {**item, "status": "in_progress", "content": []},
            },
            {
                "type": "response.content_part.added",
                "item_id": item["id"],
                "output_index": 0,
                "content_index": 0,
                "part": {**content, "text": ""},
            },
            {
                "type": "response.output_text.delta",
                "item_id": item["id"],
                "output_index": 0,
                "content_index": 0,
                "delta": text,
            },
            {
                "type": "response.output_text.done",
                "item_id": item["id"],
                "output_index": 0,
                "content_index": 0,
                "text": text,
            },
            {
                "type": "response.content_part.done",
                "item_id": item["id"],
                "output_index": 0,
                "content_index": 0,
                "part": content,
            },
            {"type": "response.output_item.done", "output_index": 0, "item": item},
            {
                "type": "response.completed",
                "response": cls._response_shell(
                    model,
                    status="completed",
                    output=[item],
                ),
            },
        ]
        return cls._responses_events(events)

    @staticmethod
    def _responses_events(events: list[dict[str, object]]) -> str:
        chunks: list[str] = []
        for sequence_number, event in enumerate(events):
            value = {**event, "sequence_number": sequence_number}
            chunks.append(
                f"event: {event['type']}\n"
                f"data: {json.dumps(value, ensure_ascii=False, separators=(',', ':'))}\n\n"
            )
        chunks.append("data: [DONE]\n\n")
        return "".join(chunks)

    @staticmethod
    def _tool_call_response(model: str, tool_name: str) -> dict[str, object]:
        return {
            "id": "chatcmpl-p15-tool",
            "object": "chat.completion",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call-evidence-p15",
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": json.dumps(
                                        {"evidence_id": "evidence-poc-001"},
                                        separators=(",", ":"),
                                    ),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    @staticmethod
    def _candidate_response(model: str) -> dict[str, object]:
        return {
            "id": "chatcmpl-p15-candidate",
            "object": "chat.completion",
            "created": 0,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            _candidate(),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    @staticmethod
    def _as_sse(response: dict[str, object]) -> str:
        choice = dict(response["choices"][0])  # type: ignore[index]
        message = dict(choice["message"])
        chunk = {
            "id": response["id"],
            "object": "chat.completion.chunk",
            "created": response["created"],
            "model": response["model"],
            "choices": [
                {
                    "index": 0,
                    "delta": message,
                    "finish_reason": choice["finish_reason"],
                }
            ],
        }
        return f"data: {json.dumps(chunk, separators=(',', ':'))}\n\ndata: [DONE]\n\n"

    @staticmethod
    def _error(status: int, code: str) -> MockResponse:
        return MockResponse(
            status=status,
            content_type="application/json",
            body=json.dumps({"error": {"code": code}}, separators=(",", ":")),
        )

    def _write_audit(self, audit: dict[str, object]) -> None:
        if self._audit_path is None:
            return
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(audit, sort_keys=True) + "\n")


def _handler(mock: ScriptedOpenAIMock):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            if self.path != "/health":
                self.send_error(404)
                return
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length < 1 or length > 1024 * 1024:
                response = ScriptedOpenAIMock._error(400, "invalid_content_length")
            else:
                try:
                    payload: Any = json.loads(self.rfile.read(length))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    payload = None
                response = mock.respond(
                    path=self.path,
                    authorization=self.headers.get("Authorization"),
                    payload=payload,
                )
            encoded = response.body.encode("utf-8")
            self.send_response(response.status)
            self.send_header("Content-Type", response.content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    return Handler


def main() -> None:
    api_key = load_api_key(os.environ)
    audit_path_value = os.environ.get("P15_MOCK_AUDIT_PATH")
    mock = ScriptedOpenAIMock(
        api_key=api_key,
        audit_path=Path(audit_path_value) if audit_path_value else None,
        scenario=os.environ.get("P15_MOCK_SCENARIO", "success"),
    )
    server = ThreadingHTTPServer(
        (os.environ.get("P15_MOCK_HOST", "0.0.0.0"), int(os.environ.get("P15_MOCK_PORT", "8080"))),
        _handler(mock),
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
