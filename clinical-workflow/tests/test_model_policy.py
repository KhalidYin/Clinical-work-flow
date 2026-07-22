from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.runtime.model_policy import (
    DataClassification,
    FallbackPolicy,
    ModelCapability,
    ModelDeployment,
    ModelPolicy,
    ModelPolicyError,
    ModelProfile,
    ModelRegistry,
    ModelRole,
)


def _deployment(
    deployment_id: str,
    *,
    provider: str,
    data_classes: tuple[DataClassification, ...] = (
        DataClassification.SYNTHETIC,
        DataClassification.DEIDENTIFIED,
    ),
    enabled: bool = True,
) -> ModelDeployment:
    return ModelDeployment(
        deployment_id=deployment_id,
        provider=provider,
        deployment_alias=f"{deployment_id}.alias",
        model_name="clinical-model",
        model_version="2026-07-15",
        capabilities=(
            ModelCapability.STRUCTURED_OUTPUT,
            ModelCapability.TOOL_PROPOSAL,
        ),
        allowed_data_classes=data_classes,
        enabled=enabled,
    )


def _policy() -> ModelPolicy:
    return ModelPolicy(
        registry=ModelRegistry(
            registry_version="1.0.0",
            deployments=(
                _deployment("foundry.prod.v1", provider="foundry"),
                _deployment("openai.prod.v1", provider="openai"),
                _deployment("foundry.validator.v1", provider="foundry"),
                _deployment(
                    "foundry.sensitive.v1",
                    provider="foundry",
                    data_classes=(DataClassification.REGULATED_SENSITIVE,),
                ),
            ),
            profiles=(
                ModelProfile(
                    profile_id="producer.synthetic",
                    role=ModelRole.PRODUCTION,
                    deployment_ids=("foundry.prod.v1", "openai.prod.v1"),
                    timeout_seconds=120,
                    retry_attempts=1,
                    fallback_policy=FallbackPolicy.APPROVED_ORDER,
                ),
                ModelProfile(
                    profile_id="validator.synthetic",
                    role=ModelRole.VALIDATION,
                    deployment_ids=("foundry.prod.v1", "foundry.validator.v1"),
                    timeout_seconds=120,
                    retry_attempts=0,
                    fallback_policy=FallbackPolicy.APPROVED_ORDER,
                    require_independent_deployment=True,
                ),
                ModelProfile(
                    profile_id="producer.sensitive",
                    role=ModelRole.PRODUCTION,
                    deployment_ids=("foundry.sensitive.v1",),
                    timeout_seconds=120,
                    retry_attempts=0,
                ),
            ),
        )
    )


@pytest.mark.parametrize("version", ["latest", "gpt-latest", "*", "stable"])
def test_model_deployment_rejects_floating_versions(version: str) -> None:
    with pytest.raises(ValidationError, match="immutable provider version"):
        _deployment("foundry.bad.v1", provider="foundry").model_copy(
            update={"model_version": version}
        ).__class__.model_validate(
            {
                **_deployment("foundry.bad.v1", provider="foundry").model_dump(),
                "model_version": version,
            }
        )


@pytest.mark.parametrize(
    "data_classification",
    [DataClassification.SYNTHETIC, DataClassification.DEIDENTIFIED],
)
def test_non_sensitive_profile_uses_only_approved_fallback_order(
    data_classification: DataClassification,
) -> None:
    policy = _policy()
    primary = policy.select(
        profile_id="producer.synthetic",
        role=ModelRole.PRODUCTION,
        data_classification=data_classification,
    )
    fallback = policy.select(
        profile_id="producer.synthetic",
        role=ModelRole.PRODUCTION,
        data_classification=data_classification,
        excluded_deployment_ids=frozenset({primary.deployment_id}),
    )

    assert primary.deployment_id == "foundry.prod.v1"
    assert primary.fallback_used is False
    assert fallback.deployment_id == "openai.prod.v1"
    assert fallback.provider == "openai"
    assert fallback.fallback_used is True


def test_sensitive_data_fails_closed_without_explicit_deployment_authorization() -> None:
    policy = _policy()
    with pytest.raises(ModelPolicyError, match="no approved deployment"):
        policy.select(
            profile_id="producer.synthetic",
            role=ModelRole.PRODUCTION,
            data_classification=DataClassification.REGULATED_SENSITIVE,
        )

    selected = policy.select(
        profile_id="producer.sensitive",
        role=ModelRole.PRODUCTION,
        data_classification=DataClassification.REGULATED_SENSITIVE,
    )
    assert selected.deployment_id == "foundry.sensitive.v1"


def test_validator_selection_can_exclude_producer_deployment() -> None:
    selected = _policy().select(
        profile_id="validator.synthetic",
        role=ModelRole.VALIDATION,
        data_classification=DataClassification.SYNTHETIC,
        producer_deployment_id="foundry.prod.v1",
    )
    assert selected.deployment_id == "foundry.validator.v1"

    with pytest.raises(ModelPolicyError, match="requires producer_deployment_id"):
        _policy().select(
            profile_id="validator.synthetic",
            role=ModelRole.VALIDATION,
            data_classification=DataClassification.SYNTHETIC,
        )


def test_registry_rejects_unknown_deployment_and_profile_role_mismatch() -> None:
    with pytest.raises(ValidationError, match="unknown deployments"):
        ModelRegistry(
            registry_version="1.0.0",
            deployments=(_deployment("foundry.prod.v1", provider="foundry"),),
            profiles=(
                ModelProfile(
                    profile_id="producer.synthetic",
                    role=ModelRole.PRODUCTION,
                    deployment_ids=("missing.deployment",),
                    timeout_seconds=60,
                    retry_attempts=0,
                ),
            ),
        )

    with pytest.raises(ModelPolicyError, match="not validation"):
        _policy().select(
            profile_id="producer.synthetic",
            role=ModelRole.VALIDATION,
            data_classification=DataClassification.SYNTHETIC,
        )


def test_secret_or_endpoint_fields_are_not_part_of_deployment_contract() -> None:
    payload = _deployment("foundry.prod.v1", provider="foundry").model_dump(mode="json")
    payload["api_key"] = "must-not-be-stored"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ModelDeployment.model_validate(payload)
