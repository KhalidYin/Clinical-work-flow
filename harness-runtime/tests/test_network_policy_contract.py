"""P16/P1 contract tests for capability-preserving controlled egress."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from contracts.manifest import ArtifactManifest
from contracts.receipt import ExecutionReceipt, ExitClassification, ValidationReceipt
from contracts.result import HarnessStatus
from contracts.spec import NetworkPolicy
from supervisor.service_contracts import SupervisorAttemptRequest, canonical_sha256


def _attempt_payload() -> dict[str, object]:
    input_bundle = {"document_id": "doc-p16"}
    return {
        "attempt_id": "attempt-p16",
        "run_id": "run-p16",
        "step_id": "step-p16",
        "generation_token": "generation-p16",
        "fencing_token": "fence-p16",
        "adapter_id": "opencode@1.18.14",
        "spec_sha256": "a" * 64,
        "input_sha256": canonical_sha256(input_bundle),
        "input_bundle": input_bundle,
        "secret_refs": ["secret://deepseek-api-key"],
        "network_policy_id": "model-deepseek-v1",
        "model_egress": {
            "profile_id": "deepseek-extractor",
            "profile_version": "1.0.0",
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "endpoint": "https://api.deepseek.com:443",
            "data_boundary": "external_allowed",
        },
        "capabilities": ["harness.browser", "knowledge.read-evidence"],
    }


def _receipt_payload() -> dict[str, object]:
    return {
        "execution_id": "exec-p16",
        "spec_sha256": "a" * 64,
        "request_sha256": "b" * 64,
        "harness_id": "opencode@1.18.14",
        "status": HarnessStatus.SUCCEEDED,
        "exit_classification": ExitClassification.SUCCEEDED,
        "started_at": datetime(2026, 8, 11, tzinfo=timezone.utc),
        "ended_at": datetime(2026, 8, 11, 0, 0, 1, tzinfo=timezone.utc),
        "artifact_manifest": ArtifactManifest(items=()),
        "network_policy": {
            "policy_id": "model-deepseek-v1",
            "policy_sha256": "c" * 64,
            "kind": "model_endpoint",
            "allowed_endpoints": ["api.deepseek.com:443"],
            "gateway_identity": "egress-gateway@p16",
            "gateway_config_sha256": "e" * 64,
        },
    }


def test_attempt_contract_preserves_agent_capabilities_beside_model_policy() -> None:
    request = SupervisorAttemptRequest.model_validate(_attempt_payload())

    assert request.network_policy_id == "model-deepseek-v1"
    assert request.model_egress.provider == "deepseek"
    assert request.model_egress.model == "deepseek-v4-flash"
    assert request.capabilities == frozenset(
        {"harness.browser", "knowledge.read-evidence"}
    )
    assert "harness.browser" in request.model_dump(mode="json")["capabilities"]


@pytest.mark.parametrize(
    "secret_ref",
    ["DEEPSEEK_API_KEY", "vault://deepseek-api-key", "secret://../deepseek-api-key"],
)
def test_attempt_contract_rejects_untrusted_secret_reference_syntax(
    secret_ref: str,
) -> None:
    payload = _attempt_payload()
    payload["secret_refs"] = [secret_ref]

    with pytest.raises(ValidationError):
        SupervisorAttemptRequest.model_validate(payload)


def test_step_network_contract_selects_policy_without_accepting_targets() -> None:
    policy = NetworkPolicy(policy_id="model-deepseek-v1")
    assert policy.policy_id == "model-deepseek-v1"

    with pytest.raises(ValidationError):
        NetworkPolicy(
            policy_id="research-public-web-v1",
            mode="allowlist",
            allowlist=("unreviewed.example:443",),
        )


def test_receipts_record_non_sensitive_network_policy_evidence() -> None:
    execution = ExecutionReceipt.model_validate(_receipt_payload())
    validation = ValidationReceipt(
        validator_id="candidate-schema-v1",
        validator_version="1.0.0",
        validator_sha256="d" * 64,
        input_sha256="a" * 64,
        result="passed",
        network_policy=execution.network_policy,
    )

    evidence = execution.network_policy.model_dump(mode="json")
    assert evidence == validation.network_policy.model_dump(mode="json")
    assert evidence["policy_id"] == "model-deepseek-v1"
    assert evidence["gateway_identity"] == "egress-gateway@p16"
    assert "secret" not in str(evidence).lower()
