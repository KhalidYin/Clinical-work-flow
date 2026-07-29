"""External model contracts owned by the Knowledge Application Platform."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from time import perf_counter
from typing import Any, Callable, Mapping, Protocol
from uuid import uuid4

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    computed_field,
    model_validator,
)


class StrictContractModel(BaseModel):
    """Reject unknown fields so configuration drift fails closed."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DeploymentClass(str, Enum):
    ENTERPRISE_MANAGED = "enterprise_managed"
    EXTERNAL_API = "external_api"


class DataBoundary(str, Enum):
    LOCAL_PROCESSING_ONLY = "local_processing_only"
    ENTERPRISE_PROVIDER_ONLY = "enterprise_provider_only"
    EXTERNAL_ALLOWED = "external_allowed"
    PROHIBITED = "prohibited"


class ModelCapability(str, Enum):
    STRUCTURED_GENERATION = "structured_generation"
    EMBEDDING = "embedding"


class InvocationStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REPLAYED = "replayed"


class InvocationErrorType(str, Enum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    STRUCTURED_OUTPUT_INVALID = "structured_output_invalid"
    PROVIDER_ERROR = "provider_error"


class DataBoundaryViolation(ValueError):
    """The selected provider is not allowed to receive the source data."""


class AttemptTransitionError(ValueError):
    """A retry or model switch did not create a new ledger attempt."""


class ModelProviderError(RuntimeError):
    """Provider failure with a sanitized invocation record for persistence."""

    def __init__(self, invocation: "ModelInvocation") -> None:
        super().__init__(invocation.error_message or "external model invocation failed")
        self.invocation = invocation


class ReplayMissError(LookupError):
    """No recorded output exists for the exact versioned request hash."""


class ModelProfile(StrictContractModel):
    """Versioned model configuration containing references, never secret values."""

    profile_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    deployment_class: DeploymentClass
    secret_ref: str = Field(pattern=r"^(env|secret)://[A-Za-z0-9_./-]+$")
    endpoint_ref: str | None = Field(
        default=None,
        pattern=r"^(env|secret)://[A-Za-z0-9_./-]+$",
    )
    allowed_data_boundaries: frozenset[DataBoundary] = Field(min_length=1)
    capabilities: frozenset[ModelCapability] = Field(min_length=1)
    timeout_seconds: int = Field(default=60, ge=1, le=600)
    max_output_tokens: int = Field(default=4096, ge=1)


class PromptProfile(StrictContractModel):
    """Versioned prompt and output schema used for one processing capability."""

    profile_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    system_template: str = Field(min_length=1)
    output_schema_id: str = Field(min_length=1)
    output_schema: dict[str, Any]

    @model_validator(mode="after")
    def validate_output_schema(self) -> "PromptProfile":
        try:
            Draft202012Validator.check_schema(self.output_schema)
        except Exception as exc:
            raise ValueError(f"output_schema is not valid Draft 2020-12: {exc}") from exc
        return self

    @computed_field
    @property
    def output_schema_sha256(self) -> str:
        payload = json.dumps(
            self.output_schema,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class StepAttemptContext(StrictContractModel):
    """Ledger identity supplied by the worker; providers never create retries."""

    run_id: str = Field(min_length=1)
    step_id: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    attempt_number: int = Field(ge=1)
    previous_attempt_id: str | None = None

    @model_validator(mode="after")
    def validate_lineage(self) -> "StepAttemptContext":
        if self.attempt_number == 1 and self.previous_attempt_id is not None:
            raise ValueError("first attempt must not set previous_attempt_id")
        if self.attempt_number > 1 and self.previous_attempt_id is None:
            raise ValueError("retry attempt requires previous_attempt_id")
        return self


class ModelMessage(StrictContractModel):
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1)


class ModelRequest(StrictContractModel):
    """One provider call owned by one durable ledger attempt."""

    attempt: StepAttemptContext
    model_profile: ModelProfile
    prompt_profile: PromptProfile
    data_boundary: DataBoundary
    messages: tuple[ModelMessage, ...] = Field(min_length=1)

    @computed_field
    @property
    def input_sha256(self) -> str:
        return _canonical_sha256(
            {
                "attempt": self.attempt.model_dump(mode="json"),
                "model_profile": {
                    "profile_id": self.model_profile.profile_id,
                    "version": self.model_profile.version,
                },
                "prompt_profile": {
                    "profile_id": self.prompt_profile.profile_id,
                    "version": self.prompt_profile.version,
                    "output_schema_sha256": self.prompt_profile.output_schema_sha256,
                },
                "data_boundary": self.data_boundary.value,
                "messages": [message.model_dump(mode="json") for message in self.messages],
            }
        )


class TokenUsage(StrictContractModel):
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class ModelInvocation(StrictContractModel):
    """Auditable facts for exactly one provider call; no chain-of-thought."""

    invocation_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attempt: StepAttemptContext
    status: InvocationStatus
    model_profile_id: str
    model_profile_version: str
    provider: str
    model: str
    prompt_profile_id: str
    prompt_profile_version: str
    output_schema_sha256: str
    data_boundary: DataBoundary
    input_sha256: str
    output_sha256: str | None = None
    provider_request_id: str | None = None
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    cost_usd: float | None = Field(default=None, ge=0)
    latency_ms: int = Field(ge=0)
    output: dict[str, Any] | None = None
    error_type: InvocationErrorType | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_status_shape(self) -> "ModelInvocation":
        if self.status in {InvocationStatus.SUCCEEDED, InvocationStatus.REPLAYED}:
            if self.output is None or self.output_sha256 is None:
                raise ValueError("successful invocation requires output and output_sha256")
            if self.error_type is not None or self.error_message is not None:
                raise ValueError("successful invocation cannot contain error fields")
        if self.status is InvocationStatus.FAILED:
            if self.output is not None or self.output_sha256 is not None:
                raise ValueError("failed invocation cannot contain output")
            if self.error_type is None or self.error_message is None:
                raise ValueError("failed invocation requires error_type and error_message")
        return self


class ModelProviderPort(Protocol):
    def invoke(self, request: ModelRequest) -> ModelInvocation:
        """Perform exactly one provider call for the supplied ledger attempt."""


CompletionCallable = Callable[..., Any]
SecretResolver = Callable[[str], str]


class LiteLLMModelProvider:
    """Thin in-process LiteLLM adapter with no internal routing or fallback."""

    def __init__(
        self,
        *,
        completion_fn: CompletionCallable | None = None,
        secret_resolver: SecretResolver | None = None,
    ) -> None:
        self._completion_fn = completion_fn or _load_litellm_completion()
        self._secret_resolver = secret_resolver or _resolve_environment_reference

    def invoke(self, request: ModelRequest) -> ModelInvocation:
        enforce_data_boundary(request.model_profile, request.data_boundary)
        if ModelCapability.STRUCTURED_GENERATION not in request.model_profile.capabilities:
            raise ValueError("model profile lacks structured_generation capability")
        Draft202012Validator.check_schema(request.prompt_profile.output_schema)

        profile = request.model_profile
        api_key = self._secret_resolver(profile.secret_ref)
        kwargs: dict[str, Any] = {
            "model": f"{profile.provider}/{profile.model}",
            "messages": [
                {"role": "system", "content": request.prompt_profile.system_template},
                *[message.model_dump(mode="json") for message in request.messages],
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.prompt_profile.output_schema_id.replace(".", "_"),
                    "strict": True,
                    "schema": request.prompt_profile.output_schema,
                },
            },
            "stream": False,
            "num_retries": 0,
            "drop_params": False,
            "timeout": profile.timeout_seconds,
            "max_tokens": profile.max_output_tokens,
            "api_key": api_key,
        }
        if profile.endpoint_ref is not None:
            kwargs["api_base"] = self._secret_resolver(profile.endpoint_ref)

        started = perf_counter()
        response: Any = None
        try:
            response = self._completion_fn(**kwargs)
            output = _structured_output(response)
            Draft202012Validator(request.prompt_profile.output_schema).validate(output)
        except Exception as exc:
            error_type = _classify_provider_error(exc)
            invocation = ModelInvocation(
                attempt=request.attempt,
                status=InvocationStatus.FAILED,
                model_profile_id=profile.profile_id,
                model_profile_version=profile.version,
                provider=profile.provider,
                model=profile.model,
                prompt_profile_id=request.prompt_profile.profile_id,
                prompt_profile_version=request.prompt_profile.version,
                output_schema_sha256=request.prompt_profile.output_schema_sha256,
                data_boundary=request.data_boundary,
                input_sha256=request.input_sha256,
                provider_request_id=(
                    _response_value(response, "id") if response is not None else None
                ),
                latency_ms=max(0, round((perf_counter() - started) * 1000)),
                error_type=error_type,
                error_message=_sanitized_error_message(error_type, exc),
            )
            raise ModelProviderError(invocation) from None

        latency_ms = max(0, round((perf_counter() - started) * 1000))
        usage = _response_value(response, "usage", {}) or {}
        hidden = _response_value(response, "_hidden_params", {}) or {}
        return ModelInvocation(
            attempt=request.attempt,
            status=InvocationStatus.SUCCEEDED,
            model_profile_id=profile.profile_id,
            model_profile_version=profile.version,
            provider=profile.provider,
            model=profile.model,
            prompt_profile_id=request.prompt_profile.profile_id,
            prompt_profile_version=request.prompt_profile.version,
            output_schema_sha256=request.prompt_profile.output_schema_sha256,
            data_boundary=request.data_boundary,
            input_sha256=request.input_sha256,
            output_sha256=_canonical_sha256(output),
            provider_request_id=_response_value(response, "id"),
            token_usage=TokenUsage(
                prompt_tokens=int(_response_value(usage, "prompt_tokens", 0) or 0),
                completion_tokens=int(_response_value(usage, "completion_tokens", 0) or 0),
                total_tokens=int(_response_value(usage, "total_tokens", 0) or 0),
            ),
            cost_usd=_optional_float(_response_value(hidden, "response_cost")),
            latency_ms=latency_ms,
            output=output,
        )


class FakeModelProvider:
    """Deterministic provider for contract tests; never performs network I/O."""

    def __init__(
        self,
        *,
        output: Mapping[str, Any],
        provider_request_id: str = "fake-model-request",
    ) -> None:
        self._output = dict(output)
        self._provider_request_id = provider_request_id

    def invoke(self, request: ModelRequest) -> ModelInvocation:
        enforce_data_boundary(request.model_profile, request.data_boundary)
        Draft202012Validator(request.prompt_profile.output_schema).validate(self._output)
        return _offline_invocation(
            request,
            output=self._output,
            status=InvocationStatus.SUCCEEDED,
            provider_request_id=self._provider_request_id,
        )


class ReplayModelProvider:
    """Replays exact input hashes and refuses nearest-match or live fallback."""

    def __init__(self, *, records: Mapping[str, Mapping[str, Any] | None]) -> None:
        self._records = {
            input_sha256: None if output is None else dict(output)
            for input_sha256, output in records.items()
        }

    def invoke(self, request: ModelRequest) -> ModelInvocation:
        enforce_data_boundary(request.model_profile, request.data_boundary)
        output = self._records.get(request.input_sha256)
        if output is None:
            raise ReplayMissError(
                f"no replay record for input_sha256 {request.input_sha256}"
            )
        Draft202012Validator(request.prompt_profile.output_schema).validate(output)
        return _offline_invocation(
            request,
            output=output,
            status=InvocationStatus.REPLAYED,
            provider_request_id=f"replay:{request.input_sha256[:16]}",
        )


def validate_attempt_transition(
    previous: StepAttemptContext,
    current: StepAttemptContext,
) -> None:
    """Require a new, linked attempt for every retry or profile change."""

    if current.run_id != previous.run_id or current.step_id != previous.step_id:
        raise AttemptTransitionError("attempt transition must stay within one run step")
    if current.attempt_id == previous.attempt_id:
        raise AttemptTransitionError("retry must create a new attempt_id")
    if current.attempt_number != previous.attempt_number + 1:
        raise AttemptTransitionError("retry attempt_number must increment by one")
    if current.previous_attempt_id != previous.attempt_id:
        raise AttemptTransitionError("retry must link previous_attempt_id")


def enforce_data_boundary(profile: ModelProfile, boundary: DataBoundary) -> None:
    """Fail before any provider call when the source cannot leave its boundary."""

    if boundary in {DataBoundary.LOCAL_PROCESSING_ONLY, DataBoundary.PROHIBITED}:
        raise DataBoundaryViolation(f"{boundary.value} data cannot be sent to a model provider")
    if boundary not in profile.allowed_data_boundaries:
        raise DataBoundaryViolation(
            f"profile {profile.profile_id} does not allow {boundary.value} data"
        )
    if (
        boundary is DataBoundary.ENTERPRISE_PROVIDER_ONLY
        and profile.deployment_class is not DeploymentClass.ENTERPRISE_MANAGED
    ):
        raise DataBoundaryViolation(
            "enterprise_provider_only data requires an enterprise-managed deployment"
        )


def _canonical_sha256(payload: Any) -> str:
    data = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def model_contract_json_schema() -> dict[str, Any]:
    """Return the checked-in prerelease schema for request/invocation persistence."""

    schema = TypeAdapter(ModelRequest | ModelInvocation).json_schema(
        ref_template="#/$defs/{model}"
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://clinical.example/schemas/model-provider.prerelease.schema.json",
        "title": "P12 Model Provider Prerelease Contract",
        **schema,
    }


def _load_litellm_completion() -> CompletionCallable:
    try:
        from litellm import completion
    except ImportError as exc:  # pragma: no cover - depends on optional deployment extra
        raise RuntimeError(
            "LiteLLM Python SDK is required for live external model calls"
        ) from exc
    return completion


def _resolve_environment_reference(reference: str) -> str:
    import os

    scheme, name = reference.split("://", 1)
    if scheme != "env":
        raise ValueError(f"unsupported secret reference scheme: {scheme}")
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"required environment reference is not configured: {name}")
    return value


def _response_value(value: Any, field: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(field, default)
    return getattr(value, field, default)


def _structured_output(response: Any) -> dict[str, Any]:
    choices = _response_value(response, "choices")
    if not choices:
        raise ValueError("model response has no choices")
    message = _response_value(choices[0], "message")
    content = _response_value(message, "content")
    if isinstance(content, str):
        parsed = json.loads(content)
    else:
        parsed = content
    if not isinstance(parsed, dict):
        raise ValueError("structured model output must be a JSON object")
    return parsed


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _offline_invocation(
    request: ModelRequest,
    *,
    output: dict[str, Any],
    status: InvocationStatus,
    provider_request_id: str,
) -> ModelInvocation:
    return ModelInvocation(
        attempt=request.attempt,
        status=status,
        model_profile_id=request.model_profile.profile_id,
        model_profile_version=request.model_profile.version,
        provider=request.model_profile.provider,
        model=request.model_profile.model,
        prompt_profile_id=request.prompt_profile.profile_id,
        prompt_profile_version=request.prompt_profile.version,
        output_schema_sha256=request.prompt_profile.output_schema_sha256,
        data_boundary=request.data_boundary,
        input_sha256=request.input_sha256,
        output_sha256=_canonical_sha256(output),
        provider_request_id=provider_request_id,
        latency_ms=0,
        output=output,
    )


def _classify_provider_error(error: Exception) -> InvocationErrorType:
    name = type(error).__name__.lower()
    if isinstance(error, TimeoutError) or "timeout" in name:
        return InvocationErrorType.TIMEOUT
    if "ratelimit" in name or ("rate" in name and "limit" in name):
        return InvocationErrorType.RATE_LIMIT
    if isinstance(error, (json.JSONDecodeError, JsonSchemaValidationError)):
        return InvocationErrorType.STRUCTURED_OUTPUT_INVALID
    if isinstance(error, ValueError) and str(error).startswith(
        ("model response", "structured model output")
    ):
        return InvocationErrorType.STRUCTURED_OUTPUT_INVALID
    return InvocationErrorType.PROVIDER_ERROR


def _sanitized_error_message(error_type: InvocationErrorType, error: Exception) -> str:
    return f"{error_type.value}: {type(error).__name__}"
