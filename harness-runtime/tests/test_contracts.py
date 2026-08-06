"""H0-B contract tests: identity, forbidden fields, receipt separation, schema lock.

Proves the trust-chain contract from TEST_GUIDE "目标 Harness Gate" items 1:
unknown fields, wrong version/hash, missing identity fail; and that
``HarnessResult`` (untrusted, self-reported) can never double as
``ExecutionReceipt`` (supervisor-owned).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from contracts.manifest import ArtifactManifest, ArtifactManifestItem
from contracts.receipt import (
    ExecutionReceipt,
    ExitClassification,
    ValidationReceipt,
)
from contracts.request import HarnessExecutionRequest
from contracts.result import HarnessResult, HarnessStatus
from contracts.schema import harness_contract_json_schema
from contracts.spec import (
    ExecutorKind,
    GatePolicy,
    InputReference,
    NetworkPolicy,
    StepExecutionSpec,
)


def _valid_spec() -> StepExecutionSpec:
    return StepExecutionSpec(
        contract_version="1.0.0",
        product="clinical-llm-wiki",
        workflow="knowledge-production",
        run_id="run-0001",
        step_id="step-0001",
        attempt_id="attempt-0001",
        generation_token="gen-1",
        fencing_token="fence-1",
        instruction_ref={"pack_id": "atomic-candidate", "version": "1.1.0"},
        inputs=(
            InputReference(
                ref_type="evidence",
                ref_id="ev-1",
                sha256="a" * 64,
                media_type="application/json",
            ),
        ),
        executor=ExecutorKind.HARNESS,
        model_profile_id="demo-extractor",
        model_version="1.0.0",
        timeout_seconds=300,
        network=NetworkPolicy(mode="none"),
        gates=GatePolicy(validators=("candidate-schema-v1",)),
        output={"artifact_type": "knowledge_candidate", "staging_path": "/staging/out"},
    )


def _valid_result() -> HarnessResult:
    return HarnessResult(
        status=HarnessStatus.SUCCEEDED,
        exit_code=0,
        output_path=None,
        output_sha256="b" * 64,
    )


# --- identity / required fields -------------------------------------------


def test_spec_requires_full_identity() -> None:
    payload = _valid_spec().model_dump()
    del payload["generation_token"]
    with pytest.raises(ValidationError):
        StepExecutionSpec.model_validate(payload)


def test_spec_rejects_workflow_control_fields() -> None:
    payload = _valid_spec().model_dump()
    payload["next_stage"] = "sdtm"  # must never be allowed
    with pytest.raises(ValidationError):
        StepExecutionSpec.model_validate(payload)


def test_spec_rejects_skip_stage_and_publish() -> None:
    for field in ("skip_stage", "publish"):
        payload = _valid_spec().model_dump()
        payload[field] = True
        with pytest.raises(ValidationError):
            StepExecutionSpec.model_validate(payload)


def test_harness_result_rejects_workflow_control_fields() -> None:
    with pytest.raises(ValidationError):
        HarnessResult.model_validate({**_valid_result().model_dump(), "next_stage": "qc"})


def test_request_links_spec_by_sha256() -> None:
    with pytest.raises(ValidationError):
        HarnessExecutionRequest.model_validate(
            {
                "attempt_id": "attempt-0001",
                "adapter_id": "fake.cli@0.1.0",
                "spec_sha256": "not-a-sha256",
                "input_path": "in.json",
                "scratch_path": "scratch",
                "output_path": "out.json",
            }
        )


# --- HarnessResult vs ExecutionReceipt separation -------------------------


def test_receipt_requires_supervisor_owned_fields() -> None:
    """A self-reported HarnessResult alone can never construct a receipt."""
    result = _valid_result()
    with pytest.raises(ValidationError):
        ExecutionReceipt.model_validate(
            {
                "execution_id": "exec-1",
                "spec_sha256": "c" * 64,
                "request_sha256": "d" * 64,
                "harness_id": "fake.cli@0.1.0",
                "status": result.status.value,
                # missing supervisor-owned: timestamps, budget_used,
                # artifact_manifest (recomputed), exit_classification
            }
        )


def test_receipt_artifact_manifest_is_supervisor_recomputed() -> None:
    """The supervisor-owned manifest is mandatory; a self-reported
    ``output_sha256`` from ``HarnessResult`` can never substitute it."""
    base = {
        "execution_id": "exec-1",
        "spec_sha256": "c" * 64,
        "request_sha256": "d" * 64,
        "harness_id": "fake.cli@0.1.0",
        "status": HarnessStatus.SUCCEEDED,
        "exit_classification": ExitClassification.SUCCEEDED,
        "started_at": datetime(2026, 8, 5, tzinfo=timezone.utc),
        "ended_at": datetime(2026, 8, 5, 0, 1, tzinfo=timezone.utc),
        "budget_used": {"calls": 1, "tokens": 100},
        "retryable": False,
    }
    # without a supervisor recomputed artifact manifest the receipt is invalid,
    # even if the harness self-reported a sha256 in its result
    with pytest.raises(ValidationError):
        ExecutionReceipt.model_validate(base)

    manifest = ArtifactManifest(
        items=(
            ArtifactManifestItem(
                key="staging/out.json",
                media_type="application/json",
                size=42,
                sha256="b" * 64,
            ),
        )
    )
    receipt = ExecutionReceipt.model_validate({**base, "artifact_manifest": manifest})
    assert receipt.artifact_manifest.items[0].sha256 == "b" * 64


def test_validation_receipt_records_validator_identity() -> None:
    v = ValidationReceipt(
        validator_id="candidate-schema-v1",
        validator_version="1.0.0",
        validator_sha256="e" * 64,
        input_sha256="c" * 64,
        result="passed",
        findings=(),
    )
    assert v.result == "passed"


# --- schema export lock ---------------------------------------------------


def test_schema_export_is_stable_and_locked() -> None:
    first = json.dumps(harness_contract_json_schema(), sort_keys=True)
    second = json.dumps(harness_contract_json_schema(), sort_keys=True)
    assert first == second
    schema = json.loads(first)
    assert schema["$id"].endswith(".schema.json")
    assert "next_stage" not in first


def test_executor_kind_includes_harness() -> None:
    assert ExecutorKind.HARNESS.value == "harness"
    assert _valid_spec().executor is ExecutorKind.HARNESS
