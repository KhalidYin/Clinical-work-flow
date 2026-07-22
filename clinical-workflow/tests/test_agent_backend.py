from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from src.runtime.action_policy import ActionOrigin, ActionPolicyError, ActionRequest
from src.runtime.agent_backend import (
    ActionProposal,
    AgentBackendError,
    AgentExecutionBackend,
    ArtifactInput,
    BackendFailureReason,
    FakeAgentExecutionBackend,
    ProductionRequest,
    ProductionResult,
    ValidationRequest,
    ValidationResult,
    authorize_action_proposals,
)
from src.runtime.model_policy import (
    DataClassification,
    ModelRole,
    ModelSelection,
)


def _selection(role: ModelRole, deployment_id: str) -> ModelSelection:
    return ModelSelection(
        profile_id=f"{role.value}.synthetic",
        role=role,
        deployment_id=deployment_id,
        provider="foundry",
        deployment_alias=f"{deployment_id}.alias",
        model_name="clinical-model",
        model_version="2026-07-15",
        data_classification=DataClassification.SYNTHETIC,
        fallback_used=False,
    )


def _artifact(artifact_id: str = "artifact.protocol.input") -> ArtifactInput:
    return ArtifactInput(
        artifact_id=artifact_id,
        sha256="a" * 64,
        media_type="application/json",
    )


def _production_request() -> ProductionRequest:
    return ProductionRequest(
        request_id="request.production.001",
        run_id="run.synthetic.001",
        stage_id="sdtm_spec",
        capability="sdtm_spec_generation",
        model=_selection(ModelRole.PRODUCTION, "foundry.prod.v1"),
        data_classification=DataClassification.SYNTHETIC,
        input_artifacts=(_artifact(),),
        task_payload={"target": "DM"},
    )


def _production_result(*, proposals: tuple[ActionProposal, ...] = ()) -> ProductionResult:
    return ProductionResult(
        request_id="request.production.001",
        backend_id="fake.agent.backend",
        deployment_id="foundry.prod.v1",
        structured_output={"spec_id": "spec-dm-001"},
        proposed_artifacts=("artifact.spec.dm.candidate",),
        action_proposals=proposals,
        trace_id="b" * 32,
    )


def _validation_request() -> ValidationRequest:
    return ValidationRequest(
        request_id="request.validation.001",
        run_id="run.synthetic.001",
        stage_id="sdtm_spec",
        model=_selection(ModelRole.VALIDATION, "foundry.validator.v1"),
        data_classification=DataClassification.SYNTHETIC,
        producer_deployment_id="foundry.prod.v1",
        producer_result_ref="result.production.001",
        candidate_artifacts=(_artifact("artifact.spec.dm.candidate"),),
        evidence_refs=("evidence.protocol.001",),
        validation_payload={"checks": ["schema", "traceability"]},
    )


def _validation_result() -> ValidationResult:
    return ValidationResult(
        request_id="request.validation.001",
        backend_id="fake.agent.backend",
        deployment_id="foundry.validator.v1",
        findings=(),
        coverage_refs=("coverage.sdtm-spec.001",),
        trace_id="c" * 32,
    )


def test_fake_backend_is_async_replaceable_and_returns_registered_results() -> None:
    backend = FakeAgentExecutionBackend(
        production_results={"request.production.001": _production_result()},
        validation_results={"request.validation.001": _validation_result()},
    )

    assert isinstance(backend, AgentExecutionBackend)
    assert asyncio.run(backend.produce(_production_request())) == _production_result()
    assert asyncio.run(backend.validate(_validation_request())) == _validation_result()
    assert not hasattr(backend, "tool_registry")
    assert not hasattr(backend, "review_queue")


@pytest.mark.parametrize(
    "reason",
    [
        BackendFailureReason.CANCELLED,
        BackendFailureReason.TIMEOUT,
        BackendFailureReason.PROVIDER_FAILURE,
        BackendFailureReason.INVALID_STRUCTURED_OUTPUT,
    ],
)
def test_fake_backend_normalizes_provider_failures(reason: BackendFailureReason) -> None:
    backend = FakeAgentExecutionBackend(
        failures={"request.production.001": reason},
    )
    with pytest.raises(AgentBackendError) as captured:
        asyncio.run(backend.produce(_production_request()))
    assert captured.value.reason == reason
    assert "prompt" not in captured.value.detail


def test_validation_request_rejects_same_deployment_and_hidden_producer_fields() -> None:
    request = _validation_request().model_dump(mode="json")
    request["model"]["deployment_id"] = request["producer_deployment_id"]
    with pytest.raises(ValidationError, match="must differ"):
        ValidationRequest.model_validate(request)

    request = _validation_request().model_dump(mode="json")
    request["producer_reasoning"] = "hidden chain of thought"
    request["producer_confidence"] = 0.99
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ValidationRequest.model_validate(request)


def test_runtime_authorizes_allowed_action_proposal() -> None:
    proposal = ActionProposal(
        proposal_id="proposal.sdtm-spec.001",
        action=ActionRequest(
            contract_version="1.0.0",
            origin=ActionOrigin.AGENT,
            stage_id="sdtm_spec",
            capability="sdtm_spec_generation",
            tool_name="sdtm_spec_build",
            arguments={"study_id": "SYNTH-E2E-001"},
        ),
        rationale_ref="rationale.sdtm-spec.001",
    )
    authorized = authorize_action_proposals(_production_result(proposals=(proposal,)))
    assert authorized == (proposal.action,)


def test_runtime_denies_out_of_stage_action_proposal() -> None:
    proposal = ActionProposal(
        proposal_id="proposal.define.001",
        action=ActionRequest(
            contract_version="1.0.0",
            origin=ActionOrigin.AGENT,
            stage_id="sdtm_spec",
            capability="define_xml_generation",
            tool_name="define_xml_build",
            arguments={},
        ),
        rationale_ref="rationale.define.001",
    )
    with pytest.raises(ActionPolicyError, match="denied"):
        authorize_action_proposals(_production_result(proposals=(proposal,)))


def test_action_proposal_requires_agent_origin_and_results_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="origin=agent"):
        ActionProposal(
            proposal_id="proposal.runtime.001",
            action=ActionRequest(
                contract_version="1.0.0",
                origin=ActionOrigin.RUNTIME,
                stage_id="sdtm_spec",
                capability="sdtm_spec_generation",
                tool_name="sdtm_spec_build",
                arguments={},
            ),
            rationale_ref="rationale.runtime.001",
        )

    payload = _production_result().model_dump(mode="json")
    payload["canonical_artifact_path"] = "output/sdtm/dm.xpt"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ProductionResult.model_validate(payload)
