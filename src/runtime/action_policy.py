"""Fail-closed action policy for pipeline capabilities, tools, and executables."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, JsonValue, field_validator, model_validator

from .pipeline_contract import (
    CANONICAL_PIPELINE,
    CONTRACT_VERSION,
    CapabilityName,
    ContractVersion,
    ExecutableName,
    PipelineContract,
    PipelineStage,
    StrictContractModel,
    ToolName,
    assert_compatible_contract_version,
)


class ActionPolicyError(PermissionError):
    """Raised when an action is not authorized by the Engine policy."""


class ToolClassification(StrEnum):
    CORE = "core"
    AUXILIARY = "auxiliary"


class ActionOrigin(StrEnum):
    RUNTIME = "runtime"
    AGENT = "agent"
    HUMAN_APPROVED_DECISION = "human_approved_decision"


class PolicyReason(StrEnum):
    ALLOWED = "allowed"
    CAPABILITY_NOT_ALLOWED = "capability_not_allowed"
    TOOL_NOT_ALLOWED = "tool_not_allowed"
    TOOL_CAPABILITY_MISMATCH = "tool_capability_mismatch"
    EXECUTABLE_NOT_ALLOWED = "executable_not_allowed"
    EXECUTABLE_CAPABILITY_MISMATCH = "executable_capability_mismatch"


CORE_TOOL_NAMES = frozenset(
    {
        ToolName.SDTM_SPEC_BUILD,
        ToolName.ADAM_SPEC_BUILD,
        ToolName.TFL_SHELLS_LIST,
        ToolName.CDISC_VALIDATE,
        ToolName.DEFINE_XML_BUILD,
        ToolName.TRIAGE_P21,
    }
)
AUXILIARY_TOOL_NAMES = frozenset(set(ToolName) - CORE_TOOL_NAMES)


class ToolRegistration(StrictContractModel):
    name: ToolName
    classification: ToolClassification
    capability: CapabilityName
    allowed_stages: tuple[PipelineStage, ...] = Field(min_length=1)

    @field_validator("allowed_stages")
    @classmethod
    def reject_duplicate_stages(
        cls, value: tuple[PipelineStage, ...]
    ) -> tuple[PipelineStage, ...]:
        if len(value) != len(set(value)):
            raise ValueError("allowed_stages must not contain duplicates")
        return value


class ExecutableRegistration(StrictContractModel):
    name: ExecutableName
    capability: CapabilityName
    allowed_stages: tuple[PipelineStage, ...] = Field(min_length=1)
    isolated_runtime_required: bool = True
    arbitrary_command_allowed: bool = False

    @field_validator("allowed_stages")
    @classmethod
    def reject_duplicate_stages(
        cls, value: tuple[PipelineStage, ...]
    ) -> tuple[PipelineStage, ...]:
        if len(value) != len(set(value)):
            raise ValueError("allowed_stages must not contain duplicates")
        return value

    @model_validator(mode="after")
    def reject_arbitrary_commands(self) -> "ExecutableRegistration":
        if self.arbitrary_command_allowed:
            raise ValueError("engine executables cannot accept arbitrary commands")
        return self


class ActionPolicy(StrictContractModel):
    contract_version: ContractVersion
    tools: tuple[ToolRegistration, ...] = Field(min_length=11, max_length=11)
    executables: tuple[ExecutableRegistration, ...] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def validate_complete_registry(self) -> "ActionPolicy":
        assert_compatible_contract_version(CONTRACT_VERSION, self.contract_version)

        tool_names = tuple(item.name for item in self.tools)
        if len(tool_names) != len(set(tool_names)) or set(tool_names) != set(ToolName):
            raise ValueError("tool registry must contain each known MCP tool exactly once")

        executable_names = tuple(item.name for item in self.executables)
        if len(executable_names) != len(set(executable_names)):
            raise ValueError("executable registry must not contain duplicate names")
        if set(executable_names) != set(ExecutableName):
            raise ValueError("executable registry must contain each controlled executable exactly once")

        for registration in self.tools:
            expected_class = (
                ToolClassification.CORE
                if registration.name in CORE_TOOL_NAMES
                else ToolClassification.AUXILIARY
            )
            if registration.classification != expected_class:
                raise ValueError(
                    f"{registration.name} must be classified as {expected_class.value}"
                )
            for stage_id in registration.allowed_stages:
                stage = CANONICAL_PIPELINE.get_stage(stage_id)
                if registration.name not in stage.allowed_tools:
                    raise ValueError(f"{registration.name} is not allowed by stage {stage_id}")
                if registration.capability not in stage.allowed_capabilities:
                    raise ValueError(
                        f"{registration.capability} is not allowed by stage {stage_id}"
                    )

        for registration in self.executables:
            for stage_id in registration.allowed_stages:
                stage = CANONICAL_PIPELINE.get_stage(stage_id)
                if registration.name not in stage.allowed_executables:
                    raise ValueError(f"{registration.name} is not allowed by stage {stage_id}")
                if registration.capability not in stage.allowed_capabilities:
                    raise ValueError(
                        f"{registration.capability} is not allowed by stage {stage_id}"
                    )
        return self

    def tool(self, name: ToolName) -> ToolRegistration:
        return next(item for item in self.tools if item.name == name)

    def executable(self, name: ExecutableName) -> ExecutableRegistration:
        return next(item for item in self.executables if item.name == name)


FORBIDDEN_ARGUMENT_KEYS = frozenset(
    {
        "command",
        "cmd",
        "shell",
        "shell_command",
        "script_path",
        "executable_path",
        "next_stage",
        "skip_stage",
    }
)


def _find_forbidden_argument_key(value: JsonValue, path: str = "arguments") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN_ARGUMENT_KEYS:
                return f"{path}.{key}"
            found = _find_forbidden_argument_key(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_forbidden_argument_key(child, f"{path}[{index}]")
            if found:
                return found
    return None


class ActionRequest(StrictContractModel):
    contract_version: ContractVersion
    origin: ActionOrigin
    stage_id: PipelineStage
    capability: CapabilityName
    tool_name: ToolName | None = None
    executable_name: ExecutableName | None = None
    arguments: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_resource_and_arguments(self) -> "ActionRequest":
        if self.tool_name is not None and self.executable_name is not None:
            raise ValueError("an action may select a tool or executable, not both")
        forbidden_path = _find_forbidden_argument_key(self.arguments)
        if forbidden_path:
            raise ValueError(f"arbitrary command/control field is forbidden: {forbidden_path}")
        return self


class PolicyDecision(StrictContractModel):
    allowed: bool
    reason: PolicyReason
    detail: str = Field(min_length=1)


def authorize_action(
    request: ActionRequest,
    *,
    contract: PipelineContract = CANONICAL_PIPELINE,
    policy: ActionPolicy | None = None,
) -> PolicyDecision:
    """Authorize an action against both the stage contract and resource registry."""
    active_policy = policy or DEFAULT_ACTION_POLICY
    assert_compatible_contract_version(contract.contract_version, request.contract_version)
    assert_compatible_contract_version(contract.contract_version, active_policy.contract_version)
    stage = contract.get_stage(request.stage_id)

    if request.capability not in stage.allowed_capabilities:
        return PolicyDecision(
            allowed=False,
            reason=PolicyReason.CAPABILITY_NOT_ALLOWED,
            detail=f"{request.capability} is not allowed during {request.stage_id}",
        )

    if request.tool_name is not None:
        if request.tool_name not in stage.allowed_tools:
            return PolicyDecision(
                allowed=False,
                reason=PolicyReason.TOOL_NOT_ALLOWED,
                detail=f"{request.tool_name} is not allowed during {request.stage_id}",
            )
        registration = active_policy.tool(request.tool_name)
        if (
            request.stage_id not in registration.allowed_stages
            or request.capability != registration.capability
        ):
            return PolicyDecision(
                allowed=False,
                reason=PolicyReason.TOOL_CAPABILITY_MISMATCH,
                detail=f"{request.tool_name} cannot implement {request.capability}",
            )

    if request.executable_name is not None:
        if request.executable_name not in stage.allowed_executables:
            return PolicyDecision(
                allowed=False,
                reason=PolicyReason.EXECUTABLE_NOT_ALLOWED,
                detail=f"{request.executable_name} is not allowed during {request.stage_id}",
            )
        registration = active_policy.executable(request.executable_name)
        if (
            request.stage_id not in registration.allowed_stages
            or request.capability != registration.capability
        ):
            return PolicyDecision(
                allowed=False,
                reason=PolicyReason.EXECUTABLE_CAPABILITY_MISMATCH,
                detail=f"{request.executable_name} cannot implement {request.capability}",
            )

    return PolicyDecision(
        allowed=True,
        reason=PolicyReason.ALLOWED,
        detail=f"action is allowed during {request.stage_id}",
    )


def require_authorized_action(
    request: ActionRequest,
    *,
    contract: PipelineContract = CANONICAL_PIPELINE,
    policy: ActionPolicy | None = None,
) -> None:
    """Raise rather than return when an action is denied."""
    decision = authorize_action(request, contract=contract, policy=policy)
    if not decision.allowed:
        raise ActionPolicyError(decision.detail)


def _tool(
    name: ToolName,
    classification: ToolClassification,
    capability: CapabilityName,
    *allowed_stages: PipelineStage,
) -> ToolRegistration:
    return ToolRegistration(
        name=name,
        classification=classification,
        capability=capability,
        allowed_stages=allowed_stages,
    )


def _executable(
    name: ExecutableName,
    capability: CapabilityName,
    stage: PipelineStage,
) -> ExecutableRegistration:
    return ExecutableRegistration(name=name, capability=capability, allowed_stages=(stage,))


DEFAULT_ACTION_POLICY = ActionPolicy(
    contract_version=CONTRACT_VERSION,
    tools=(
        _tool(
            ToolName.SDTM_SPEC_BUILD,
            ToolClassification.CORE,
            CapabilityName.SDTM_SPEC_GENERATION,
            PipelineStage.SDTM_SPEC,
        ),
        _tool(
            ToolName.ADAM_SPEC_BUILD,
            ToolClassification.CORE,
            CapabilityName.ADAM_SPEC_GENERATION,
            PipelineStage.ADAM_SPEC,
        ),
        _tool(
            ToolName.TFL_SHELLS_LIST,
            ToolClassification.CORE,
            CapabilityName.TFL_SHELL_GENERATION,
            PipelineStage.TFL_SHELL_DESIGN,
        ),
        _tool(
            ToolName.CDISC_VALIDATE,
            ToolClassification.CORE,
            CapabilityName.CDISC_VALIDATION,
            PipelineStage.SDTM_SPEC,
            PipelineStage.SDTM_PROGRAMMING,
            PipelineStage.ADAM_SPEC,
            PipelineStage.ADAM_PROGRAMMING,
            PipelineStage.QC_VALIDATION,
        ),
        _tool(
            ToolName.DEFINE_XML_BUILD,
            ToolClassification.CORE,
            CapabilityName.DEFINE_XML_GENERATION,
            PipelineStage.SUBMISSION_PACKAGING,
        ),
        _tool(
            ToolName.TRIAGE_P21,
            ToolClassification.CORE,
            CapabilityName.P21_TRIAGE,
            PipelineStage.QC_VALIDATION,
        ),
        _tool(
            ToolName.EDC_IMPORT,
            ToolClassification.AUXILIARY,
            CapabilityName.SOURCE_DATA_IMPORT,
            PipelineStage.SDTM_SPEC,
            PipelineStage.SDTM_PROGRAMMING,
        ),
        _tool(
            ToolName.CTGOV_SEARCH,
            ToolClassification.AUXILIARY,
            CapabilityName.SOURCE_DISCOVERY,
            PipelineStage.PROTOCOL_ANALYSIS,
        ),
        _tool(
            ToolName.CTGOV_STUDY_DETAIL,
            ToolClassification.AUXILIARY,
            CapabilityName.SOURCE_DISCOVERY,
            PipelineStage.PROTOCOL_ANALYSIS,
        ),
        _tool(
            ToolName.CTGOV_DOWNLOAD_DOCS,
            ToolClassification.AUXILIARY,
            CapabilityName.SOURCE_DISCOVERY,
            PipelineStage.PROTOCOL_ANALYSIS,
        ),
        _tool(
            ToolName.CTGOV_CHECK_DOCS,
            ToolClassification.AUXILIARY,
            CapabilityName.SOURCE_DISCOVERY,
            PipelineStage.PROTOCOL_ANALYSIS,
        ),
    ),
    executables=(
        _executable(
            ExecutableName.PROTOCOL_DOCUMENT_PARSER,
            CapabilityName.PROTOCOL_ANALYSIS,
            PipelineStage.PROTOCOL_ANALYSIS,
        ),
        _executable(
            ExecutableName.SAP_DOCUMENT_GENERATOR,
            CapabilityName.SAP_GENERATION,
            PipelineStage.SAP_GENERATION,
        ),
        _executable(
            ExecutableName.SDTM_PROGRAM_RUNNER,
            CapabilityName.SDTM_PROGRAMMING,
            PipelineStage.SDTM_PROGRAMMING,
        ),
        _executable(
            ExecutableName.ADAM_PROGRAM_RUNNER,
            CapabilityName.ADAM_PROGRAMMING,
            PipelineStage.ADAM_PROGRAMMING,
        ),
        _executable(
            ExecutableName.TFL_RENDERER,
            CapabilityName.TFL_PROGRAMMING,
            PipelineStage.TFL_PROGRAMMING,
        ),
        _executable(
            ExecutableName.QC_COMPARATOR,
            CapabilityName.QC_VALIDATION,
            PipelineStage.QC_VALIDATION,
        ),
        _executable(
            ExecutableName.SUBMISSION_PACKAGER,
            CapabilityName.SUBMISSION_PACKAGING,
            PipelineStage.SUBMISSION_PACKAGING,
        ),
    ),
)


def action_request_from_mapping(data: dict[str, Any]) -> ActionRequest:
    """Strict parser used at untrusted Agent/Review boundaries."""
    return ActionRequest.model_validate(data)
