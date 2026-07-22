"""Fail-closed model deployment registry and selection policy for P11.

The registry stores deployment aliases and immutable model versions, never API
keys or provider credentials.  Provider clients are constructed outside this
module after the Runtime has authorized a selection.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from .pipeline_contract import StrictContractModel


IDENTIFIER_PATTERN = r"^[a-z][a-z0-9._-]{2,63}$"
FORBIDDEN_FLOATING_VERSIONS = frozenset({"latest", "current", "stable", "auto", "default"})


class ModelPolicyError(PermissionError):
    """Raised when no explicitly approved deployment can satisfy a request."""


class DataClassification(StrEnum):
    SYNTHETIC = "synthetic"
    DEIDENTIFIED = "deidentified"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    REGULATED_SENSITIVE = "regulated_sensitive"


class ModelCapability(StrEnum):
    STRUCTURED_OUTPUT = "structured_output"
    TOOL_PROPOSAL = "tool_proposal"
    LONG_CONTEXT = "long_context"
    VISION = "vision"


class ModelRole(StrEnum):
    PRODUCTION = "production"
    VALIDATION = "validation"


class FallbackPolicy(StrEnum):
    DISABLED = "disabled"
    APPROVED_ORDER = "approved_order"
    SAME_PROVIDER = "same_provider"


class ModelDeployment(StrictContractModel):
    deployment_id: str = Field(pattern=IDENTIFIER_PATTERN)
    provider: str = Field(pattern=IDENTIFIER_PATTERN)
    deployment_alias: str = Field(pattern=IDENTIFIER_PATTERN)
    model_name: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=128)
    capabilities: tuple[ModelCapability, ...] = Field(min_length=1)
    allowed_data_classes: tuple[DataClassification, ...] = Field(min_length=1)
    region: str | None = Field(default=None, min_length=2, max_length=64)
    enabled: bool = True

    @field_validator("model_version")
    @classmethod
    def reject_floating_version(cls, value: str) -> str:
        normalized = value.strip().lower()
        if (
            normalized in FORBIDDEN_FLOATING_VERSIONS
            or "latest" in normalized
            or "*" in normalized
        ):
            raise ValueError("model_version must be an immutable provider version")
        return value

    @field_validator("capabilities", "allowed_data_classes")
    @classmethod
    def reject_duplicates(cls, value: tuple[object, ...]) -> tuple[object, ...]:
        if len(value) != len(set(value)):
            raise ValueError("model deployment lists must not contain duplicates")
        return value


class ModelProfile(StrictContractModel):
    profile_id: str = Field(pattern=IDENTIFIER_PATTERN)
    role: ModelRole
    deployment_ids: tuple[str, ...] = Field(min_length=1)
    required_capabilities: tuple[ModelCapability, ...] = (
        ModelCapability.STRUCTURED_OUTPUT,
    )
    timeout_seconds: int = Field(ge=1, le=900)
    retry_attempts: int = Field(ge=0, le=3)
    fallback_policy: FallbackPolicy = FallbackPolicy.DISABLED
    require_independent_deployment: bool = False

    @field_validator("deployment_ids", "required_capabilities")
    @classmethod
    def reject_duplicates(cls, value: tuple[object, ...]) -> tuple[object, ...]:
        if len(value) != len(set(value)):
            raise ValueError("model profile lists must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_fallback_shape(self) -> "ModelProfile":
        if self.fallback_policy == FallbackPolicy.DISABLED and len(self.deployment_ids) != 1:
            raise ValueError("disabled fallback profiles must name exactly one deployment")
        if self.require_independent_deployment and self.role != ModelRole.VALIDATION:
            raise ValueError("independent deployment is only meaningful for validation profiles")
        return self


class ModelRegistry(StrictContractModel):
    registry_version: str = Field(pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
    deployments: tuple[ModelDeployment, ...] = Field(min_length=1)
    profiles: tuple[ModelProfile, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references(self) -> "ModelRegistry":
        deployment_ids = tuple(item.deployment_id for item in self.deployments)
        profile_ids = tuple(item.profile_id for item in self.profiles)
        if len(deployment_ids) != len(set(deployment_ids)):
            raise ValueError("deployment_id values must be unique")
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("profile_id values must be unique")
        known = set(deployment_ids)
        for profile in self.profiles:
            missing = set(profile.deployment_ids) - known
            if missing:
                raise ValueError(f"profile references unknown deployments: {sorted(missing)}")
        return self

    def deployment(self, deployment_id: str) -> ModelDeployment:
        try:
            return next(item for item in self.deployments if item.deployment_id == deployment_id)
        except StopIteration as exc:
            raise ModelPolicyError(f"unknown deployment: {deployment_id}") from exc

    def profile(self, profile_id: str) -> ModelProfile:
        try:
            return next(item for item in self.profiles if item.profile_id == profile_id)
        except StopIteration as exc:
            raise ModelPolicyError(f"unknown model profile: {profile_id}") from exc


class ModelSelection(StrictContractModel):
    profile_id: str
    role: ModelRole
    deployment_id: str
    provider: str
    deployment_alias: str
    model_name: str
    model_version: str
    data_classification: DataClassification
    fallback_used: bool


class ModelPolicy(StrictContractModel):
    registry: ModelRegistry

    def select(
        self,
        *,
        profile_id: str,
        role: ModelRole,
        data_classification: DataClassification,
        required_capabilities: tuple[ModelCapability, ...] = (),
        excluded_deployment_ids: frozenset[str] = frozenset(),
        producer_deployment_id: str | None = None,
    ) -> ModelSelection:
        profile = self.registry.profile(profile_id)
        if profile.role != role:
            raise ModelPolicyError(
                f"profile {profile_id} is for {profile.role.value}, not {role.value}"
            )

        exclusions = set(excluded_deployment_ids)
        if profile.require_independent_deployment:
            if not producer_deployment_id:
                raise ModelPolicyError(
                    "independent validation profile requires producer_deployment_id"
                )
            exclusions.add(producer_deployment_id)

        required = set(profile.required_capabilities) | set(required_capabilities)
        candidates = tuple(
            self.registry.deployment(deployment_id)
            for deployment_id in profile.deployment_ids
        )
        if profile.fallback_policy == FallbackPolicy.SAME_PROVIDER:
            primary_provider = candidates[0].provider
            candidates = tuple(item for item in candidates if item.provider == primary_provider)

        for index, deployment in enumerate(candidates):
            if not deployment.enabled or deployment.deployment_id in exclusions:
                continue
            if data_classification not in deployment.allowed_data_classes:
                continue
            if not required.issubset(set(deployment.capabilities)):
                continue
            return ModelSelection(
                profile_id=profile.profile_id,
                role=role,
                deployment_id=deployment.deployment_id,
                provider=deployment.provider,
                deployment_alias=deployment.deployment_alias,
                model_name=deployment.model_name,
                model_version=deployment.model_version,
                data_classification=data_classification,
                fallback_used=index > 0,
            )

        excluded_detail = ", ".join(sorted(exclusions)) or "none"
        raise ModelPolicyError(
            "no approved deployment satisfies profile, capability, data-classification, "
            f"and independence policy; excluded={excluded_detail}"
        )
