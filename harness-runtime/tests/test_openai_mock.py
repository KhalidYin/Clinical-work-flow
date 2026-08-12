from __future__ import annotations

import json
from pathlib import Path

import pytest


def _request(*, messages: list[dict[str, object]], stream: bool = False):
    return {
        "model": "gpt-4o-mini",
        "messages": messages,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "clinical_attempt_read_evidence",
                    "description": "Read one authorized Evidence item.",
                    "parameters": {
                        "type": "object",
                        "required": ["evidence_id"],
                        "properties": {"evidence_id": {"type": "string"}},
                    },
                },
            }
        ],
        "stream": stream,
    }


def _responses_request(
    *,
    output_count: int = 0,
    include_tools: bool = True,
    evidence_id: str = "evidence-poc-001",
):
    input_items: list[dict[str, object]] = [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": f"Authorized Evidence IDs: [\"{evidence_id}\"]",
                }
            ],
        }
    ]
    for index in range(output_count):
        input_items.append(
            {
                "type": "function_call_output",
                "call_id": f"call-{index}",
                "output": "synthetic tool result",
            }
        )
    tools = (
        [
            {
                "type": "function",
                "name": "skill",
                "description": "Load a skill",
                "parameters": {"type": "object"},
            },
            {
                "type": "function",
                "name": "clinical_attempt_read_evidence",
                "description": "Read Evidence",
                "parameters": {"type": "object"},
            },
        ]
        if include_tools
        else []
    )
    return {
        "model": "gpt-4o-mini",
        "input": input_items,
        "tools": tools,
        "stream": True,
    }


def test_mock_requires_tool_call_before_returning_candidate() -> None:
    from poc.openai_mock.server import ScriptedOpenAIMock

    mock = ScriptedOpenAIMock(api_key="synthetic-p15-key")
    first = mock.respond(
        path="/v1/chat/completions",
        authorization="Bearer synthetic-p15-key",
        payload=_request(
            messages=[{"role": "user", "content": "Create one Candidate."}]
        ),
    )

    assert first.status == 200
    first_body = json.loads(first.body)
    tool_call = first_body["choices"][0]["message"]["tool_calls"][0]
    assert tool_call["function"]["name"] == "clinical_attempt_read_evidence"
    assert json.loads(tool_call["function"]["arguments"]) == {
        "evidence_id": "evidence-poc-001"
    }

    second = mock.respond(
        path="/v1/chat/completions",
        authorization="Bearer synthetic-p15-key",
        payload=_request(
            messages=[
                {"role": "user", "content": "Create one Candidate."},
                {
                    "role": "assistant",
                    "tool_calls": [tool_call],
                },
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(
                        {
                            "evidence_id": "evidence-poc-001",
                            "content": "Synthetic evidence.",
                        }
                    ),
                },
            ]
        ),
    )

    assert second.status == 200
    candidate = json.loads(json.loads(second.body)["choices"][0]["message"]["content"])
    assert candidate["candidate_group_id"] == "candidate-poc-001"
    assert candidate["evidence_ids"] == ["evidence-poc-001"]
    assert candidate["claim"] == "Synthetic evidence supports the P15 POC claim."


def test_mock_streams_openai_chunks_and_audits_only_safe_metadata() -> None:
    from poc.openai_mock.server import ScriptedOpenAIMock

    secret = "synthetic-p15-key"
    mock = ScriptedOpenAIMock(api_key=secret)
    response = mock.respond(
        path="/v1/chat/completions",
        authorization=f"Bearer {secret}",
        payload=_request(
            messages=[{"role": "user", "content": "private prompt marker"}],
            stream=True,
        ),
    )

    assert response.status == 200
    assert response.content_type == "text/event-stream"
    assert response.body.endswith("data: [DONE]\n\n")
    assert "clinical_attempt_read_evidence" in response.body
    serialized_audit = json.dumps(mock.audits, sort_keys=True)
    assert secret not in serialized_audit
    assert "private prompt marker" not in serialized_audit
    assert mock.audits == [
        {
            "path": "/v1/chat/completions",
            "model": "gpt-4o-mini",
            "request_sha256": mock.audits[0]["request_sha256"],
            "tool_names": ["clinical_attempt_read_evidence"],
            "has_tool_result": False,
            "stream": True,
        }
    ]


def test_mock_rejects_wrong_key_missing_tool_and_unexpected_path() -> None:
    from poc.openai_mock.server import ScriptedOpenAIMock

    mock = ScriptedOpenAIMock(api_key="synthetic-p15-key")
    valid = _request(messages=[{"role": "user", "content": "candidate"}])

    assert mock.respond(
        path="/v1/chat/completions",
        authorization="Bearer wrong",
        payload=valid,
    ).status == 401
    assert mock.respond(
        path="/v1/chat/completions",
        authorization="Bearer synthetic-p15-key",
        payload={**valid, "tools": []},
    ).status == 400
    assert mock.respond(
        path="/v1/models",
        authorization="Bearer synthetic-p15-key",
        payload=valid,
    ).status == 404
    assert mock.audits[-1]["path"] == "/v1/models"
    assert mock.audits[-1]["payload_keys"] == sorted(valid)
    assert "wrong" not in json.dumps(mock.audits)


def test_mock_loads_key_from_secret_file_without_key_environment(tmp_path: Path) -> None:
    from poc.openai_mock.server import load_api_key

    secret_file = tmp_path / "mock-key"
    secret_file.write_text("synthetic-file-secret\n", encoding="utf-8")

    assert load_api_key({"P15_MOCK_API_KEY_FILE": str(secret_file)}) == (
        "synthetic-file-secret"
    )

    with pytest.raises(RuntimeError, match="file"):
        load_api_key({"P15_MOCK_API_KEY": "forbidden-environment-secret"})


def test_responses_api_sequences_skill_evidence_and_candidate() -> None:
    from poc.openai_mock.server import ScriptedOpenAIMock

    mock = ScriptedOpenAIMock(api_key="synthetic-p15-key")

    skill = mock.respond(
        path="/v1/responses",
        authorization="Bearer synthetic-p15-key",
        payload=_responses_request(),
    )
    evidence = mock.respond(
        path="/v1/responses",
        authorization="Bearer synthetic-p15-key",
        payload=_responses_request(output_count=1),
    )
    candidate = mock.respond(
        path="/v1/responses",
        authorization="Bearer synthetic-p15-key",
        payload=_responses_request(output_count=2),
    )
    title = mock.respond(
        path="/v1/responses",
        authorization="Bearer synthetic-p15-key",
        payload=_responses_request(include_tools=False),
    )

    assert '"name":"skill"' in skill.body
    assert '"name":"clinical_attempt_read_evidence"' in evidence.body
    assert "candidate-poc-001" in candidate.body
    assert "P15 Candidate" in title.body
    assert all(response.content_type == "text/event-stream" for response in (
        skill,
        evidence,
        candidate,
        title,
    ))


def test_responses_api_uses_attempt_authorized_evidence_identity() -> None:
    from poc.openai_mock.server import ScriptedOpenAIMock

    mock = ScriptedOpenAIMock(api_key="synthetic-p15-key")
    evidence = mock.respond(
        path="/v1/responses",
        authorization="Bearer synthetic-p15-key",
        payload=_responses_request(output_count=1, evidence_id="evidence-db-001"),
    )
    candidate = mock.respond(
        path="/v1/responses",
        authorization="Bearer synthetic-p15-key",
        payload=_responses_request(output_count=2, evidence_id="evidence-db-001"),
    )

    assert "evidence-db-001" in evidence.body
    assert "evidence-db-001" in candidate.body
    assert "evidence-poc-001" not in evidence.body + candidate.body


def test_schema_invalid_scenario_preserves_tools_then_returns_invalid_candidate() -> None:
    from poc.openai_mock.server import ScriptedOpenAIMock

    mock = ScriptedOpenAIMock(
        api_key="synthetic-p15-key",
        scenario="schema_invalid",
    )

    candidate = mock.respond(
        path="/v1/responses",
        authorization="Bearer synthetic-p15-key",
        payload=_responses_request(output_count=2, evidence_id="evidence-db-001"),
    )

    assert "candidate-poc-001" in candidate.body
    assert '"claim"' not in candidate.body


def test_timeout_scenario_delays_model_post_after_writing_safe_audit() -> None:
    from poc.openai_mock.server import ScriptedOpenAIMock

    sleeps: list[float] = []
    mock = ScriptedOpenAIMock(
        api_key="synthetic-p15-key",
        scenario="timeout",
        delay_seconds=2.0,
        sleep=sleeps.append,
    )

    response = mock.respond(
        path="/v1/responses",
        authorization="Bearer synthetic-p15-key",
        payload=_responses_request(),
    )

    assert response.status == 200
    assert sleeps == [2.0]
    assert len(mock.audits) == 1


def test_responses_api_recovers_identity_from_opencode_transformed_text() -> None:
    from poc.openai_mock.server import ScriptedOpenAIMock

    payload = _responses_request(output_count=2)
    payload["input"][0]["content"][0]["text"] = (
        "Load evidence-candidate, then use evidence-db-transformed-001."
    )
    response = ScriptedOpenAIMock(api_key="synthetic-p15-key").respond(
        path="/v1/responses",
        authorization="Bearer synthetic-p15-key",
        payload=payload,
    )

    assert "evidence-db-transformed-001" in response.body
    assert "evidence-poc-001" not in response.body


def test_responses_fault_scenario_requests_unauthorized_bash() -> None:
    from poc.openai_mock.server import ScriptedOpenAIMock

    mock = ScriptedOpenAIMock(
        api_key="synthetic-p15-key",
        scenario="unauthorized_tool",
    )

    response = mock.respond(
        path="/v1/responses",
        authorization="Bearer synthetic-p15-key",
        payload=_responses_request(),
    )

    assert '"name":"bash"' in response.body
    assert "unauthorized-marker" in response.body
