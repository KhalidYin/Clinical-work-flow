"""Contract, policy, drift, negative, and security tests for the fixed pipeline."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError

from src.mcp_tools.server import (
    AUXILIARY_TOOL_NAMES as SERVER_AUXILIARY_TOOL_NAMES,
    CORE_TOOL_NAMES as SERVER_CORE_TOOL_NAMES,
)
from src.runtime.action_policy import (
    AUXILIARY_TOOL_NAMES,
    CORE_TOOL_NAMES,
    DEFAULT_ACTION_POLICY,
    ActionRequest,
    PolicyReason,
    ToolClassification,
    authorize_action,
)
from src.runtime.pipeline_contract import (
    CANONICAL_PIPELINE,
    CONTRACT_VERSION,
    ExecutableName,
    PipelineContract,
    PipelineContractError,
    PipelineStage,
    ToolName,
    assert_compatible_contract_version,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "pipeline"


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _action(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "contract_version": CONTRACT_VERSION,
        "origin": "runtime",
        "stage_id": "sdtm_spec",
        "capability": "sdtm_spec_generation",
        "tool_name": "sdtm_spec_build",
        "arguments": {"domain_code": "AE"},
    }
    data.update(overrides)
    return data


def test_canonical_pipeline_has_exact_ten_stage_order_and_dependencies():
    assert [stage.stage_id for stage in CANONICAL_PIPELINE.stages] == list(PipelineStage)
    assert [stage.ordinal for stage in CANONICAL_PIPELINE.stages] == list(range(1, 11))
    assert CANONICAL_PIPELINE.stages[0].depends_on == ()
    assert [stage.depends_on[0] for stage in CANONICAL_PIPELINE.stages[1:]] == list(
        PipelineStage
    )[:-1]


def test_each_stage_has_specific_inputs_outputs_and_completion_evidence():
    for stage in CANONICAL_PIPELINE.stages:
        assert stage.required_inputs
        assert stage.canonical_outputs
        assert stage.completion_evidence
        assert all(path.startswith("output/") for path in stage.completion_evidence)
        assert "output/programs" not in stage.completion_evidence
        assert "output/programs/" not in stage.completion_evidence

    assert CANONICAL_PIPELINE.get_stage("sdtm_programming").completion_evidence == (
        "output/sdtm/programs/",
        "output/sdtm/datasets/",
    )
    assert CANONICAL_PIPELINE.get_stage("adam_programming").completion_evidence == (
        "output/adam/programs/",
        "output/adam/datasets/",
    )
    assert CANONICAL_PIPELINE.get_stage("tfl_programming").completion_evidence == (
        "output/tfl/programs/",
        "output/tfl/outputs/",
    )


def test_pipeline_model_rejects_unknown_fields_stage_and_capability():
    payload = CANONICAL_PIPELINE.model_dump(mode="json")
    payload["workflow_playbook"] = {"next_stage": "submission_packaging"}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PipelineContract.model_validate(payload)

    payload = CANONICAL_PIPELINE.model_dump(mode="json")
    payload["stages"][0]["stage_id"] = "crf_design"
    with pytest.raises(ValidationError):
        PipelineContract.model_validate(payload)

    payload = CANONICAL_PIPELINE.model_dump(mode="json")
    payload["stages"][0]["allowed_capabilities"] = ["skip_pipeline"]
    with pytest.raises(ValidationError):
        PipelineContract.model_validate(payload)


def test_pipeline_model_rejects_reordered_or_rewired_stages():
    payload = CANONICAL_PIPELINE.model_dump(mode="json")
    payload["stages"][0], payload["stages"][1] = payload["stages"][1], payload["stages"][0]
    with pytest.raises(ValidationError, match="canonical ten-stage order"):
        PipelineContract.model_validate(payload)

    payload = CANONICAL_PIPELINE.model_dump(mode="json")
    payload["stages"][6]["depends_on"] = ["protocol_analysis"]
    with pytest.raises(ValidationError, match="must depend on"):
        PipelineContract.model_validate(payload)


def test_pipeline_json_schema_enforces_exact_order_and_strict_fields():
    schema = _schema("pipeline-contract.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    payload = CANONICAL_PIPELINE.model_dump(mode="json")
    validator.validate(payload)

    reordered = copy.deepcopy(payload)
    reordered["stages"][0], reordered["stages"][1] = (
        reordered["stages"][1],
        reordered["stages"][0],
    )
    with pytest.raises(JsonSchemaValidationError):
        validator.validate(reordered)

    injected = copy.deepcopy(payload)
    injected["stages"][0]["next_stage"] = "submission_packaging"
    with pytest.raises(JsonSchemaValidationError):
        validator.validate(injected)


def test_action_policy_lists_all_server_tools_without_classification_drift():
    policy_core = {
        item.name.value
        for item in DEFAULT_ACTION_POLICY.tools
        if item.classification == ToolClassification.CORE
    }
    policy_auxiliary = {
        item.name.value
        for item in DEFAULT_ACTION_POLICY.tools
        if item.classification == ToolClassification.AUXILIARY
    }
    assert policy_core == set(SERVER_CORE_TOOL_NAMES) == {item.value for item in CORE_TOOL_NAMES}
    assert policy_auxiliary == set(SERVER_AUXILIARY_TOOL_NAMES) == {
        item.value for item in AUXILIARY_TOOL_NAMES
    }
    assert len(policy_core) == 6
    assert len(policy_auxiliary) == 5


def test_action_policy_schema_validates_registry_and_rejects_classification_drift():
    schema = _schema("action-policy.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    payload = DEFAULT_ACTION_POLICY.model_dump(mode="json")
    validator.validate(payload)

    drifted = copy.deepcopy(payload)
    drifted["tools"][0]["classification"] = "auxiliary"
    with pytest.raises(JsonSchemaValidationError):
        validator.validate(drifted)


def test_authorization_allows_only_stage_capability_resource_mapping():
    allowed = authorize_action(ActionRequest.model_validate(_action()))
    assert allowed.allowed is True
    assert allowed.reason == PolicyReason.ALLOWED

    wrong_stage = authorize_action(
        ActionRequest.model_validate(_action(stage_id="sap_generation", capability="sap_generation"))
    )
    assert wrong_stage.allowed is False
    assert wrong_stage.reason == PolicyReason.TOOL_NOT_ALLOWED

    wrong_capability = authorize_action(
        ActionRequest.model_validate(_action(capability="cdisc_validation"))
    )
    assert wrong_capability.allowed is False
    assert wrong_capability.reason == PolicyReason.TOOL_CAPABILITY_MISMATCH

    stage_capability_denied = authorize_action(
        ActionRequest.model_validate(
            _action(stage_id="sap_generation", capability="cdisc_validation", tool_name=None)
        )
    )
    assert stage_capability_denied.allowed is False
    assert stage_capability_denied.reason == PolicyReason.CAPABILITY_NOT_ALLOWED


def test_tfl_render_and_code_execution_are_controlled_executables_not_mcp_tools():
    assert "tfl_renderer" not in {tool.value for tool in ToolName}
    assert ExecutableName.TFL_RENDERER in {
        item.name for item in DEFAULT_ACTION_POLICY.executables
    }
    tfl_stage = CANONICAL_PIPELINE.get_stage(PipelineStage.TFL_PROGRAMMING)
    assert tfl_stage.allowed_tools == ()
    assert tfl_stage.allowed_executables == (ExecutableName.TFL_RENDERER,)

    decision = authorize_action(
        ActionRequest.model_validate(
            _action(
                stage_id="tfl_programming",
                capability="tfl_programming",
                tool_name=None,
                executable_name="tfl_renderer",
            )
        )
    )
    assert decision.allowed is True


@pytest.mark.parametrize("field", ["next_stage", "skip_stage", "command", "script_path"])
def test_action_request_rejects_workflow_control_and_command_injection(field: str):
    payload = _action()
    payload[field] = "submission_packaging" if "stage" in field else "rm -rf project"
    with pytest.raises(ValidationError):
        ActionRequest.model_validate(payload)


def test_action_request_rejects_nested_command_injection_and_workflow_origin():
    with pytest.raises(ValidationError, match="arbitrary command/control field"):
        ActionRequest.model_validate(_action(arguments={"nested": {"command": "danger"}}))
    with pytest.raises(ValidationError):
        ActionRequest.model_validate(_action(origin="workflow_knowledge"))


def test_action_request_json_schema_rejects_unknowns_control_fields_and_dual_resources():
    schema = _schema("action-request.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    validator.validate(_action())

    with pytest.raises(JsonSchemaValidationError):
        validator.validate(_action(next_stage="submission_packaging"))
    with pytest.raises(JsonSchemaValidationError):
        validator.validate(_action(arguments={"command": "danger"}))
    with pytest.raises(JsonSchemaValidationError):
        validator.validate(_action(executable_name="sdtm_program_runner"))


def test_semver_contract_compatibility_fails_closed():
    assert_compatible_contract_version("1.0.0", "1.4.2")
    with pytest.raises(PipelineContractError, match="Incompatible"):
        assert_compatible_contract_version("1.0.0", "2.0.0")
    with pytest.raises(PipelineContractError, match="Incompatible"):
        assert_compatible_contract_version("1.2.0", "1.1.9")
    with pytest.raises(PipelineContractError, match="Invalid SemVer"):
        assert_compatible_contract_version("1.0", "1.0.0")

    with pytest.raises(ValidationError):
        ActionRequest.model_validate(_action(contract_version="1.0"))
