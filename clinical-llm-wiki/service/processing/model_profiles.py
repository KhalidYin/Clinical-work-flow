"""Explicit runtime authorization for one live enrichment model profile."""

from __future__ import annotations

from collections.abc import Mapping
import os

from pydantic import Field, model_validator

from .model_provider import (
    CompletionCallable,
    DataBoundary,
    LiteLLMModelProvider,
    ModelCapability,
    ModelProfile,
    ModelProviderPort,
    ModelRequest,
    ModelInvocation,
    SecretResolver,
    StrictContractModel,
    enforce_data_boundary,
)


LIVE_MODEL_ENABLED_VARIABLE = "KNOWLEDGE_LIVE_MODEL_ENABLED"
LIVE_MODEL_PROFILE_ID_VARIABLE = "KNOWLEDGE_LIVE_MODEL_PROFILE_ID"
LIVE_MODEL_PROFILE_VERSION_VARIABLE = "KNOWLEDGE_LIVE_MODEL_PROFILE_VERSION"
LIVE_MODEL_BOUNDARIES_VARIABLE = "KNOWLEDGE_LIVE_MODEL_ALLOWED_DATA_BOUNDARIES"


class LiveModelAuthorizationError(RuntimeError):
    """Live model execution was not explicitly authorized for this exact request."""


class LiveModelAuthorization(StrictContractModel):
    """Process-local authorization for exactly one versioned live model profile."""

    profile_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    allowed_data_boundaries: frozenset[DataBoundary] = Field(min_length=1)

    @model_validator(mode="after")
    def reject_non_exportable_boundaries(self) -> "LiveModelAuthorization":
        denied = self.allowed_data_boundaries.intersection(
            {DataBoundary.LOCAL_PROCESSING_ONLY, DataBoundary.PROHIBITED}
        )
        if denied:
            values = ", ".join(sorted(boundary.value for boundary in denied))
            raise ValueError(f"live authorization cannot include non-exportable boundaries: {values}")
        return self


def live_model_authorization_from_environment(
    environ: Mapping[str, str] | None = None,
) -> LiveModelAuthorization:
    """Load an exact live opt-in without resolving or exposing any secret value."""

    values = os.environ if environ is None else environ
    if values.get(LIVE_MODEL_ENABLED_VARIABLE) != "true":
        raise LiveModelAuthorizationError(
            f"{LIVE_MODEL_ENABLED_VARIABLE}=true is required for live model execution"
        )
    profile_id = _required_value(values, LIVE_MODEL_PROFILE_ID_VARIABLE)
    profile_version = _required_value(values, LIVE_MODEL_PROFILE_VERSION_VARIABLE)
    raw_boundaries = _required_value(values, LIVE_MODEL_BOUNDARIES_VARIABLE)
    boundaries = frozenset(
        DataBoundary(value.strip())
        for value in raw_boundaries.split(",")
        if value.strip()
    )
    if not boundaries:
        raise LiveModelAuthorizationError(
            f"{LIVE_MODEL_BOUNDARIES_VARIABLE} must contain at least one data boundary"
        )
    return LiveModelAuthorization(
        profile_id=profile_id,
        profile_version=profile_version,
        allowed_data_boundaries=boundaries,
    )


def validate_live_model_authorization(
    *,
    model_profile: ModelProfile,
    authorization: LiveModelAuthorization,
) -> None:
    """Validate the canonical profile and all authorized boundaries without network I/O."""

    if (
        model_profile.profile_id != authorization.profile_id
        or model_profile.version != authorization.profile_version
    ):
        raise LiveModelAuthorizationError(
            "live authorization does not match the configured model profile and version"
        )
    if ModelCapability.STRUCTURED_GENERATION not in model_profile.capabilities:
        raise LiveModelAuthorizationError(
            "live enrichment profile lacks structured_generation capability"
        )
    for boundary in authorization.allowed_data_boundaries:
        try:
            enforce_data_boundary(model_profile, boundary)
        except ValueError as exc:
            raise LiveModelAuthorizationError(str(exc)) from None


class AuthorizedLiveModelProvider(ModelProviderPort):
    """Bind LiteLLM to one canonical profile and an explicit outbound-data grant."""

    def __init__(
        self,
        *,
        model_profile: ModelProfile,
        authorization: LiveModelAuthorization,
        delegate: ModelProviderPort,
    ) -> None:
        validate_live_model_authorization(
            model_profile=model_profile,
            authorization=authorization,
        )
        self._model_profile = model_profile
        self._authorization = authorization
        self._delegate = delegate

    def invoke(self, request: ModelRequest) -> ModelInvocation:
        if request.model_profile != self._model_profile:
            raise LiveModelAuthorizationError(
                "live request model profile differs from the authorized canonical profile"
            )
        if request.data_boundary not in self._authorization.allowed_data_boundaries:
            raise LiveModelAuthorizationError(
                f"live authorization does not allow {request.data_boundary.value} data"
            )
        try:
            enforce_data_boundary(request.model_profile, request.data_boundary)
        except ValueError as exc:
            raise LiveModelAuthorizationError(str(exc)) from None
        return self._delegate.invoke(request)


def authorized_live_provider_from_environment(
    *,
    model_profile: ModelProfile,
    environ: Mapping[str, str] | None = None,
    completion_fn: CompletionCallable | None = None,
    secret_resolver: SecretResolver | None = None,
) -> AuthorizedLiveModelProvider:
    """Build the live provider only after exact process-local authorization succeeds."""

    authorization = live_model_authorization_from_environment(environ)
    validate_live_model_authorization(
        model_profile=model_profile,
        authorization=authorization,
    )
    return AuthorizedLiveModelProvider(
        model_profile=model_profile,
        authorization=authorization,
        delegate=LiteLLMModelProvider(
            completion_fn=completion_fn,
            secret_resolver=secret_resolver,
        ),
    )


def _required_value(values: Mapping[str, str], name: str) -> str:
    value = values.get(name, "").strip()
    if not value:
        raise LiveModelAuthorizationError(f"{name} is required for live model execution")
    return value


__all__ = [
    "AuthorizedLiveModelProvider",
    "LIVE_MODEL_BOUNDARIES_VARIABLE",
    "LIVE_MODEL_ENABLED_VARIABLE",
    "LIVE_MODEL_PROFILE_ID_VARIABLE",
    "LIVE_MODEL_PROFILE_VERSION_VARIABLE",
    "LiveModelAuthorization",
    "LiveModelAuthorizationError",
    "authorized_live_provider_from_environment",
    "live_model_authorization_from_environment",
    "validate_live_model_authorization",
]
