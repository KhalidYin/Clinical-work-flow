from __future__ import annotations

from pydantic import ValidationError
import pytest

from service.processing.model_profiles import (
    LiveModelAuthorizationError,
    authorized_live_provider_from_environment,
    live_model_authorization_from_environment,
)
from service.processing.model_provider import (
    ModelMessage,
    ModelProfile,
    ModelRequest,
    PromptProfile,
    StepAttemptContext,
)
from service.processing import worker


def _profile(
    *,
    profile_id: str = "live-extractor",
    version: str = "1.0.0",
    deployment_class: str = "external_api",
) -> ModelProfile:
    return ModelProfile(
        profile_id=profile_id,
        version=version,
        provider="test-provider",
        model="structured-model",
        deployment_class=deployment_class,
        secret_ref="env://KNOWLEDGE_MODEL_API_KEY",
        endpoint_ref="env://KNOWLEDGE_MODEL_ENDPOINT",
        allowed_data_boundaries=["external_allowed"],
        capabilities=["structured_generation"],
    )


def _environment(**overrides: str) -> dict[str, str]:
    values = {
        "KNOWLEDGE_LIVE_MODEL_ENABLED": "true",
        "KNOWLEDGE_LIVE_MODEL_PROFILE_ID": "live-extractor",
        "KNOWLEDGE_LIVE_MODEL_PROFILE_VERSION": "1.0.0",
        "KNOWLEDGE_LIVE_MODEL_ALLOWED_DATA_BOUNDARIES": "external_allowed",
    }
    values.update(overrides)
    return values


def _request(profile: ModelProfile, *, boundary: str = "external_allowed") -> ModelRequest:
    return ModelRequest(
        attempt=StepAttemptContext(
            run_id="run-live",
            step_id="step-live",
            attempt_id="attempt-live-1",
            attempt_number=1,
        ),
        model_profile=profile,
        prompt_profile=PromptProfile(
            profile_id="atomic-candidate",
            version="1.0.0",
            system_template="Return one evidence-grounded claim.",
            output_schema_id="knowledge-candidate.v1",
            output_schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["claim"],
                "properties": {"claim": {"type": "string"}},
            },
        ),
        data_boundary=boundary,
        messages=(ModelMessage(role="user", content="Synthetic outbound-safe evidence."),),
    )


def test_live_mode_requires_exact_explicit_opt_in_and_profile_version() -> None:
    with pytest.raises(LiveModelAuthorizationError, match="=true"):
        live_model_authorization_from_environment({})

    authorization = live_model_authorization_from_environment(_environment())

    assert authorization.profile_id == "live-extractor"
    assert authorization.profile_version == "1.0.0"
    assert {item.value for item in authorization.allowed_data_boundaries} == {
        "external_allowed"
    }

    with pytest.raises(LiveModelAuthorizationError, match="does not match"):
        authorized_live_provider_from_environment(
            model_profile=_profile(version="2.0.0"),
            environ=_environment(),
            completion_fn=lambda **_kwargs: None,
            secret_resolver=lambda _ref: "unused",
        )


@pytest.mark.parametrize("boundary", ["local_processing_only", "prohibited"])
def test_live_authorization_rejects_non_exportable_boundaries(boundary: str) -> None:
    with pytest.raises(ValidationError, match="non-exportable"):
        live_model_authorization_from_environment(
            _environment(KNOWLEDGE_LIVE_MODEL_ALLOWED_DATA_BOUNDARIES=boundary)
        )


def test_unauthorized_boundary_fails_before_secret_resolution_or_provider_call() -> None:
    calls: list[str] = []
    profile = _profile()
    provider = authorized_live_provider_from_environment(
        model_profile=profile,
        environ=_environment(),
        completion_fn=lambda **_kwargs: calls.append("provider"),
        secret_resolver=lambda _ref: calls.append("secret") or "resolved",
    )

    with pytest.raises(LiveModelAuthorizationError, match="does not allow"):
        provider.invoke(_request(profile, boundary="enterprise_provider_only"))

    assert calls == []


def test_live_provider_is_bound_to_the_canonical_profile_object() -> None:
    calls: list[str] = []
    profile = _profile()
    provider = authorized_live_provider_from_environment(
        model_profile=profile,
        environ=_environment(),
        completion_fn=lambda **_kwargs: calls.append("provider"),
        secret_resolver=lambda _ref: calls.append("secret") or "resolved",
    )
    drifted = profile.model_copy(update={"model": "different-model"})

    with pytest.raises(LiveModelAuthorizationError, match="differs"):
        provider.invoke(_request(drifted))

    assert calls == []


def test_authorized_live_request_performs_one_structured_call_without_retry() -> None:
    calls: list[dict] = []
    resolved_references: list[str] = []
    profile = _profile()

    def completion(**kwargs):
        calls.append(kwargs)
        return {
            "id": "live-request-001",
            "choices": [{"message": {"content": '{"claim":"Grounded synthetic claim."}'}}],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 5,
                "total_tokens": 17,
            },
        }

    provider = authorized_live_provider_from_environment(
        model_profile=profile,
        environ=_environment(),
        completion_fn=completion,
        secret_resolver=lambda ref: resolved_references.append(ref) or "resolved",
    )
    invocation = provider.invoke(_request(profile))

    assert len(calls) == 1
    assert calls[0]["stream"] is False
    assert calls[0]["num_retries"] == 0
    assert calls[0]["response_format"]["type"] == "json_schema"
    assert resolved_references == [
        "env://KNOWLEDGE_MODEL_API_KEY",
        "env://KNOWLEDGE_MODEL_ENDPOINT",
    ]
    assert invocation.provider_request_id == "live-request-001"
    assert invocation.token_usage.total_tokens == 17
    assert "resolved" not in invocation.model_dump_json()


def test_enrichment_worker_live_mode_does_not_require_offline_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    captured: dict[str, object] = {}

    def build_live_provider(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        worker,
        "authorized_live_provider_from_environment",
        build_live_provider,
    )
    profile = _profile()

    result = worker.enrichment_provider_from_environment(
        profile,
        _environment(KNOWLEDGE_ENRICHMENT_PROVIDER_MODE="live"),
    )

    assert result is sentinel
    assert captured["model_profile"] == profile
    assert "KNOWLEDGE_ENRICHMENT_RECORDS_PATH" not in captured["environ"]


def test_enrichment_worker_never_falls_back_when_offline_records_are_missing() -> None:
    with pytest.raises(RuntimeError, match="fake/replay"):
        worker.enrichment_provider_from_environment(
            _profile(),
            {"KNOWLEDGE_ENRICHMENT_PROVIDER_MODE": "replay"},
        )
