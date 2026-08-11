"""Compose-only zero-network smoke for Worker → Supervisor → OpenCode."""

from __future__ import annotations

import hashlib
import json

from .model_provider import (
    DataBoundary,
    DeploymentClass,
    ModelCapability,
    ModelMessage,
    ModelProfile,
    ModelProviderError,
    ModelRequest,
    PromptProfile,
    StepAttemptContext,
)
from .worker import harness_enrichment_provider_from_environment


def build_smoke_request() -> ModelRequest:
    """Use an impossible provider under network-none; success is not expected."""

    evidence_content = "Synthetic offline harness evidence."
    canonical_message = json.dumps(
        {
            "evidence": [
                {
                    "evidence_id": "evidence-compose-offline-smoke",
                    "locator": {
                        "kind": "synthetic_test",
                        "source_id": "compose-offline-smoke",
                    },
                    "content_sha256": hashlib.sha256(
                        evidence_content.encode("utf-8")
                    ).hexdigest(),
                    "content": evidence_content,
                }
            ]
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    return ModelRequest(
        attempt=StepAttemptContext(
            run_id="compose-offline-smoke",
            step_id="enrichment",
            attempt_id="compose-offline-attempt-001",
            attempt_number=1,
        ),
        model_profile=ModelProfile(
            profile_id="compose-offline-invalid-provider",
            version="1.0.0",
            provider="admission",
            model="invalid-offline-model",
            deployment_class=DeploymentClass.ENTERPRISE_MANAGED,
            secret_ref="env://SYNTHETIC_PROVIDER_KEY",
            allowed_data_boundaries={DataBoundary.ENTERPRISE_PROVIDER_ONLY},
            capabilities={ModelCapability.STRUCTURED_GENERATION},
            timeout_seconds=30,
            max_output_tokens=128,
        ),
        prompt_profile=PromptProfile(
            profile_id="compose-offline-smoke",
            version="1.0.0",
            system_template="Return one JSON object. Do not access any network.",
            output_schema_id="compose-offline-smoke.v1",
            output_schema={
                "type": "object",
                "required": ["result"],
                "properties": {"result": {"const": "offline"}},
                "additionalProperties": False,
            },
        ),
        data_boundary=DataBoundary.ENTERPRISE_PROVIDER_ONLY,
        messages=(
            ModelMessage(role="user", content=canonical_message),
        ),
    )


def main() -> int:
    provider = harness_enrichment_provider_from_environment()
    if provider is None:
        raise RuntimeError("harness provider mode is not configured")
    try:
        provider.invoke(build_smoke_request())
    except ModelProviderError as error:
        invocation = error.invocation
        receipt = invocation.execution_receipt
        if receipt is None:
            raise RuntimeError("offline failure has no ExecutionReceipt") from None
        if receipt.get("exit_classification") not in {"failed", "timed_out"}:
            raise RuntimeError("offline Attempt did not fail closed") from None
        audit = {
            "attempt_id": invocation.attempt.attempt_id,
            "invocation_status": invocation.status.value,
            "error_type": invocation.error_type.value if invocation.error_type else None,
            "execution_receipt": receipt,
        }
        serialized = json.dumps(audit, ensure_ascii=False, sort_keys=True)
        if "synthetic-offline-not-a-real-provider-key" in serialized:
            raise RuntimeError("synthetic secret leaked into audit output") from None
        print(serialized)
        return 0
    raise RuntimeError("invalid zero-network provider unexpectedly succeeded")


if __name__ == "__main__":
    raise SystemExit(main())
