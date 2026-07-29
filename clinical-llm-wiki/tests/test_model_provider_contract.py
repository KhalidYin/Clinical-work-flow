from __future__ import annotations

import json
import tomllib
from importlib import import_module
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]


def _model_provider_module():
    try:
        return import_module("service.processing.model_provider")
    except ModuleNotFoundError as exc:
        pytest.fail(f"P1-B0 model provider contract is not implemented: {exc}")


def _profile(contract, *, deployment_class: str = "enterprise_managed"):
    return contract.ModelProfile(
        profile_id="extractor-primary",
        version="1.0.0",
        provider="azure",
        model="knowledge-extractor",
        deployment_class=deployment_class,
        secret_ref="env://AZURE_OPENAI_API_KEY",
        endpoint_ref="env://AZURE_OPENAI_ENDPOINT",
        allowed_data_boundaries=["enterprise_provider_only", "external_allowed"],
        capabilities=["structured_generation"],
    )


def _prompt(contract):
    return contract.PromptProfile(
        profile_id="atomic-claim-extraction",
        version="1.0.0",
        system_template="Return only evidence-grounded atomic claims.",
        output_schema_id="knowledge-candidate.v1",
        output_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["claim"],
            "properties": {"claim": {"type": "string"}},
        },
    )


def _request(contract, *, data_boundary: str = "enterprise_provider_only"):
    return contract.ModelRequest(
        attempt=contract.StepAttemptContext(
            run_id="run-001",
            step_id="extract-claims",
            attempt_id="attempt-001",
            attempt_number=1,
        ),
        model_profile=_profile(contract),
        prompt_profile=_prompt(contract),
        data_boundary=data_boundary,
        messages=[
            {
                "role": "user",
                "content": "Evidence E-001 states that AESEQ is a sequence identifier.",
            }
        ],
    )


def test_model_profile_accepts_secret_reference_and_rejects_literal_secret() -> None:
    contract = _model_provider_module()

    profile = contract.ModelProfile(
        profile_id="extractor-primary",
        version="1.0.0",
        provider="azure",
        model="knowledge-extractor",
        deployment_class="enterprise_managed",
        secret_ref="env://AZURE_OPENAI_API_KEY",
        endpoint_ref="env://AZURE_OPENAI_ENDPOINT",
        allowed_data_boundaries=["enterprise_provider_only", "external_allowed"],
        capabilities=["structured_generation"],
    )

    assert profile.secret_ref == "env://AZURE_OPENAI_API_KEY"
    assert "secret_value" not in type(profile).model_fields

    with pytest.raises(ValidationError, match="secret_ref"):
        contract.ModelProfile(
            profile_id="extractor-primary",
            version="1.0.0",
            provider="openai",
            model="knowledge-extractor",
            deployment_class="external_api",
            secret_ref="sk-live-secret",
            allowed_data_boundaries=["external_allowed"],
            capabilities=["structured_generation"],
        )


@pytest.mark.parametrize(
    ("deployment_class", "data_boundary", "allowed"),
    [
        ("enterprise_managed", "enterprise_provider_only", True),
        ("enterprise_managed", "external_allowed", True),
        ("external_api", "external_allowed", True),
        ("external_api", "enterprise_provider_only", False),
        ("enterprise_managed", "local_processing_only", False),
        ("enterprise_managed", "prohibited", False),
    ],
)
def test_data_boundary_policy_fails_closed_before_external_call(
    deployment_class: str,
    data_boundary: str,
    allowed: bool,
) -> None:
    contract = _model_provider_module()
    profile = contract.ModelProfile(
        profile_id="extractor",
        version="1.0.0",
        provider="test",
        model="structured",
        deployment_class=deployment_class,
        secret_ref="env://MODEL_API_KEY",
        allowed_data_boundaries=["enterprise_provider_only", "external_allowed"],
        capabilities=["structured_generation"],
    )

    if allowed:
        contract.enforce_data_boundary(profile, contract.DataBoundary(data_boundary))
    else:
        with pytest.raises(contract.DataBoundaryViolation):
            contract.enforce_data_boundary(profile, contract.DataBoundary(data_boundary))


def test_prompt_schema_is_versioned_and_retry_requires_new_attempt_lineage() -> None:
    contract = _model_provider_module()
    prompt = contract.PromptProfile(
        profile_id="atomic-claim-extraction",
        version="1.0.0",
        system_template="Return only evidence-grounded atomic claims.",
        output_schema_id="knowledge-candidate.v1",
        output_schema={
            "type": "object",
            "additionalProperties": False,
            "required": ["claim"],
            "properties": {"claim": {"type": "string"}},
        },
    )
    first = contract.StepAttemptContext(
        run_id="run-001",
        step_id="extract-claims",
        attempt_id="attempt-001",
        attempt_number=1,
    )
    retry = contract.StepAttemptContext(
        run_id="run-001",
        step_id="extract-claims",
        attempt_id="attempt-002",
        attempt_number=2,
        previous_attempt_id="attempt-001",
    )

    assert len(prompt.output_schema_sha256) == 64
    contract.validate_attempt_transition(first, retry)

    with pytest.raises(contract.AttemptTransitionError):
        contract.validate_attempt_transition(first, first)

    with pytest.raises(ValidationError, match="previous_attempt_id"):
        contract.StepAttemptContext(
            run_id="run-001",
            step_id="extract-claims",
            attempt_id="attempt-003",
            attempt_number=2,
        )


def test_invalid_output_schema_and_inconsistent_invocation_are_rejected() -> None:
    contract = _model_provider_module()

    with pytest.raises(ValidationError, match="output_schema"):
        contract.PromptProfile(
            profile_id="invalid-schema",
            version="1.0.0",
            system_template="Return JSON.",
            output_schema_id="invalid.v1",
            output_schema={"type": "not-a-json-schema-type"},
        )

    request = _request(contract)
    common = {
        "attempt": request.attempt,
        "model_profile_id": request.model_profile.profile_id,
        "model_profile_version": request.model_profile.version,
        "provider": request.model_profile.provider,
        "model": request.model_profile.model,
        "prompt_profile_id": request.prompt_profile.profile_id,
        "prompt_profile_version": request.prompt_profile.version,
        "output_schema_sha256": request.prompt_profile.output_schema_sha256,
        "data_boundary": request.data_boundary,
        "input_sha256": request.input_sha256,
        "latency_ms": 0,
    }
    with pytest.raises(ValidationError, match="successful invocation"):
        contract.ModelInvocation(status="succeeded", **common)
    with pytest.raises(ValidationError, match="failed invocation"):
        contract.ModelInvocation(
            status="failed",
            output={"claim": "must not survive a failed call"},
            output_sha256="f" * 64,
            error_type="provider_error",
            error_message="provider_error: RuntimeError",
            **common,
        )


def test_litellm_adapter_uses_one_non_streaming_structured_call_and_records_provenance() -> None:
    contract = _model_provider_module()
    calls: list[dict] = []

    def completion(**kwargs):
        calls.append(kwargs)
        return {
            "id": "provider-request-001",
            "choices": [{"message": {"content": '{"claim":"AESEQ is a sequence identifier."}'}}],
            "usage": {
                "prompt_tokens": 21,
                "completion_tokens": 9,
                "total_tokens": 30,
            },
            "_hidden_params": {"response_cost": 0.0042},
        }

    provider = contract.LiteLLMModelProvider(
        completion_fn=completion,
        secret_resolver=lambda ref: {
            "env://AZURE_OPENAI_API_KEY": "resolved-secret",
            "env://AZURE_OPENAI_ENDPOINT": "https://enterprise.example.test",
        }[ref],
    )
    invocation = provider.invoke(_request(contract))

    assert len(calls) == 1
    assert calls[0]["stream"] is False
    assert calls[0]["num_retries"] == 0
    assert calls[0]["response_format"]["type"] == "json_schema"
    assert calls[0]["response_format"]["json_schema"]["strict"] is True
    assert invocation.status == contract.InvocationStatus.SUCCEEDED
    assert invocation.provider == "azure"
    assert invocation.model == "knowledge-extractor"
    assert invocation.output == {"claim": "AESEQ is a sequence identifier."}
    assert invocation.provider_request_id == "provider-request-001"
    assert invocation.token_usage.total_tokens == 30
    assert invocation.cost_usd == 0.0042
    assert len(invocation.input_sha256) == len(invocation.output_sha256) == 64
    assert "resolved-secret" not in invocation.model_dump_json()


@pytest.mark.parametrize(
    ("provider_error", "error_type"),
    [
        (TimeoutError("resolved-secret timeout"), "timeout"),
        (type("RateLimitError", (RuntimeError,), {})("resolved-secret throttled"), "rate_limit"),
        (RuntimeError("resolved-secret provider failure"), "provider_error"),
    ],
)
def test_provider_failure_is_one_attempt_with_sanitized_audit_record(
    provider_error: Exception,
    error_type: str,
) -> None:
    contract = _model_provider_module()
    calls = 0

    def completion(**_kwargs):
        nonlocal calls
        calls += 1
        raise provider_error

    provider = contract.LiteLLMModelProvider(
        completion_fn=completion,
        secret_resolver=lambda _ref: "resolved-secret",
    )

    with pytest.raises(contract.ModelProviderError) as captured:
        provider.invoke(_request(contract))

    invocation = captured.value.invocation
    assert calls == 1
    assert invocation.status == contract.InvocationStatus.FAILED
    assert invocation.error_type == contract.InvocationErrorType(error_type)
    assert invocation.output is None
    assert invocation.output_sha256 is None
    assert "resolved-secret" not in invocation.model_dump_json()
    assert captured.value.__cause__ is None
    assert captured.value.__suppress_context__ is True


def test_invalid_structured_output_fails_closed_with_invocation_evidence() -> None:
    contract = _model_provider_module()

    provider = contract.LiteLLMModelProvider(
        completion_fn=lambda **_kwargs: {
            "id": "provider-request-invalid",
            "choices": [{"message": {"content": '{"claim":42}'}}],
        },
        secret_resolver=lambda _ref: "resolved-secret",
    )

    with pytest.raises(contract.ModelProviderError) as captured:
        provider.invoke(_request(contract))

    invocation = captured.value.invocation
    assert invocation.status == contract.InvocationStatus.FAILED
    assert invocation.error_type == "structured_output_invalid"
    assert invocation.provider_request_id == "provider-request-invalid"
    assert invocation.output is None


def test_data_boundary_rejection_happens_before_secret_resolution_or_provider_call() -> None:
    contract = _model_provider_module()
    calls: list[str] = []
    provider = contract.LiteLLMModelProvider(
        completion_fn=lambda **_kwargs: calls.append("provider"),
        secret_resolver=lambda _ref: calls.append("secret") or "resolved",
    )

    with pytest.raises(contract.DataBoundaryViolation):
        provider.invoke(_request(contract, data_boundary="local_processing_only"))

    assert calls == []


def test_fake_and_replay_adapters_validate_output_without_network_fallback() -> None:
    contract = _model_provider_module()
    request = _request(contract)
    fake = contract.FakeModelProvider(
        output={"claim": "AESEQ is a sequence identifier."},
        provider_request_id="fake-request-001",
    )

    original = fake.invoke(request)
    replay = contract.ReplayModelProvider(
        records={request.input_sha256: original.output},
    )
    replayed = replay.invoke(request)

    assert original.status == contract.InvocationStatus.SUCCEEDED
    assert replayed.status == contract.InvocationStatus.REPLAYED
    assert replayed.output == original.output
    assert replayed.output_sha256 == original.output_sha256

    changed_request = request.model_copy(
        update={
            "messages": (
                contract.ModelMessage(role="user", content="Different evidence."),
            )
        }
    )
    with pytest.raises(contract.ReplayMissError):
        replay.invoke(changed_request)


def test_checked_in_model_contract_schema_matches_runtime_models() -> None:
    contract = _model_provider_module()
    checked_in = json.loads(
        (
            ROOT
            / "schemas"
            / "application"
            / "model-provider.prerelease.schema.json"
        ).read_text(encoding="utf-8")
    )

    assert checked_in == contract.model_contract_json_schema()


def test_live_model_adapter_dependency_is_explicit_and_optional() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert "litellm>=1.92,<2" in project["project"]["optional-dependencies"]["models"]
