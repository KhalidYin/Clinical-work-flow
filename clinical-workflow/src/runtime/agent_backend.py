"""Stage-local Agent execution boundary owned by the Clinical Runtime.

Backends may call an LLM provider and return structured proposals.  They cannot
execute MCP tools, write canonical artifacts, mutate ReviewQueue, or choose the
next pipeline stage.  The Runtime authorizes every returned ``ActionProposal``.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import Field, JsonValue, field_validator, model_validator

from .action_policy import (
    ActionOrigin,
    ActionPolicy,
    ActionPolicyError,
    ActionRequest,
    DEFAULT_ACTION_POLICY,
    require_authorized_action,
)
from .model_policy import DataClassification, ModelRole, ModelSelection
from .pipeline_contract import (
    CONTRACT_VERSION,
    CapabilityName,
    ContractVersion,
    PipelineStage,
    StrictContractModel,
)


IDENTIFIER_PATTERN = r"^[a-z][a-z0-9._-]{2,127}$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class BackendFailureReason(StrEnum):
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    PROVIDER_FAILURE = "provider_failure"
    INVALID_STRUCTURED_OUTPUT = "invalid_structured_output"


class AgentBackendError(RuntimeError):
    """Normalized backend failure that contains no provider secret or raw prompt."""

    def __init__(self, reason: BackendFailureReason, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


class ArtifactInput(StrictContractModel):
    artifact_id: str = Field(pattern=IDENTIFIER_PATTERN)
    sha256: str = Field(pattern=SHA256_PATTERN)
    media_type: str = Field(min_length=1, max_length=128)


class ActionProposal(StrictContractModel):
    proposal_id: str = Field(pattern=IDENTIFIER_PATTERN)
    action: ActionRequest
    rationale_ref: str = Field(pattern=IDENTIFIER_PATTERN)

    @model_validator(mode="after")
    def require_agent_origin(self) -> "ActionProposal":
        if self.action.origin != ActionOrigin.AGENT:
            raise ValueError("backend action proposals must use origin=agent")
        return self


class ProductionRequest(StrictContractModel):
    contract_version: ContractVersion = CONTRACT_VERSION
    request_id: str = Field(pattern=IDENTIFIER_PATTERN)
    run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    stage_id: PipelineStage
    capability: CapabilityName
    model: ModelSelection
    data_classification: DataClassification
    input_artifacts: tuple[ArtifactInput, ...] = Field(min_length=1)
    knowledge_usage_ref: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    task_payload: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_model_role_and_data_class(self) -> "ProductionRequest":
        if self.model.role != ModelRole.PRODUCTION:
            raise ValueError("production requests require a production model selection")
        if self.model.data_classification != self.data_classification:
            raise ValueError("request and model data classifications must match")
        return self


class ProductionResult(StrictContractModel):
    contract_version: ContractVersion = CONTRACT_VERSION
    request_id: str = Field(pattern=IDENTIFIER_PATTERN)
    backend_id: str = Field(pattern=IDENTIFIER_PATTERN)
    deployment_id: str = Field(pattern=IDENTIFIER_PATTERN)
    structured_output: dict[str, JsonValue]
    proposed_artifacts: tuple[str, ...] = ()
    action_proposals: tuple[ActionProposal, ...] = ()
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")

    @field_validator("proposed_artifacts")
    @classmethod
    def reject_duplicate_artifacts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("proposed_artifacts must not contain duplicates")
        return value


class ValidationRequest(StrictContractModel):
    contract_version: ContractVersion = CONTRACT_VERSION
    request_id: str = Field(pattern=IDENTIFIER_PATTERN)
    run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    stage_id: PipelineStage
    model: ModelSelection
    data_classification: DataClassification
    producer_deployment_id: str = Field(pattern=IDENTIFIER_PATTERN)
    producer_result_ref: str = Field(pattern=IDENTIFIER_PATTERN)
    candidate_artifacts: tuple[ArtifactInput, ...] = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    validation_payload: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_independent_model(self) -> "ValidationRequest":
        if self.model.role != ModelRole.VALIDATION:
            raise ValueError("validation requests require a validation model selection")
        if self.model.data_classification != self.data_classification:
            raise ValueError("request and model data classifications must match")
        if self.model.deployment_id == self.producer_deployment_id:
            raise ValueError("validator deployment must differ from producer deployment")
        return self


class FindingSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


class ValidationFinding(StrictContractModel):
    finding_id: str = Field(pattern=IDENTIFIER_PATTERN)
    severity: FindingSeverity
    category: str = Field(pattern=IDENTIFIER_PATTERN)
    statement: str = Field(min_length=1, max_length=1000)
    artifact_id: str = Field(pattern=IDENTIFIER_PATTERN)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    proposed_correction: str | None = Field(default=None, max_length=1000)


class ValidationResult(StrictContractModel):
    contract_version: ContractVersion = CONTRACT_VERSION
    request_id: str = Field(pattern=IDENTIFIER_PATTERN)
    backend_id: str = Field(pattern=IDENTIFIER_PATTERN)
    deployment_id: str = Field(pattern=IDENTIFIER_PATTERN)
    findings: tuple[ValidationFinding, ...] = ()
    coverage_refs: tuple[str, ...] = Field(min_length=1)
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")


@runtime_checkable
class AgentExecutionBackend(Protocol):
    """Provider-neutral async boundary implemented by fake and MAF adapters."""

    backend_id: str

    async def produce(self, request: ProductionRequest) -> ProductionResult: ...

    async def validate(self, request: ValidationRequest) -> ValidationResult: ...


class FakeAgentExecutionBackend:
    """Deterministic test backend with no file, ReviewQueue, tool, or network access."""

    def __init__(
        self,
        *,
        backend_id: str = "fake.agent.backend",
        production_results: Mapping[str, ProductionResult] | None = None,
        validation_results: Mapping[str, ValidationResult] | None = None,
        failures: Mapping[str, BackendFailureReason] | None = None,
    ) -> None:
        self.backend_id = backend_id
        self._production_results = dict(production_results or {})
        self._validation_results = dict(validation_results or {})
        self._failures = dict(failures or {})

    def _raise_configured_failure(self, request_id: str) -> None:
        reason = self._failures.get(request_id)
        if reason is not None:
            raise AgentBackendError(reason, f"fake backend failed: {reason.value}")

    async def produce(self, request: ProductionRequest) -> ProductionResult:
        self._raise_configured_failure(request.request_id)
        try:
            result = self._production_results[request.request_id]
        except KeyError as exc:
            raise AgentBackendError(
                BackendFailureReason.INVALID_STRUCTURED_OUTPUT,
                "fake backend has no registered production result",
            ) from exc
        if (
            result.request_id != request.request_id
            or result.deployment_id != request.model.deployment_id
        ):
            raise AgentBackendError(
                BackendFailureReason.INVALID_STRUCTURED_OUTPUT,
                "production result request or deployment mismatch",
            )
        return result

    async def validate(self, request: ValidationRequest) -> ValidationResult:
        self._raise_configured_failure(request.request_id)
        try:
            result = self._validation_results[request.request_id]
        except KeyError as exc:
            raise AgentBackendError(
                BackendFailureReason.INVALID_STRUCTURED_OUTPUT,
                "fake backend has no registered validation result",
            ) from exc
        if (
            result.request_id != request.request_id
            or result.deployment_id != request.model.deployment_id
        ):
            raise AgentBackendError(
                BackendFailureReason.INVALID_STRUCTURED_OUTPUT,
                "validation result request or deployment mismatch",
            )
        return result


def authorize_action_proposals(
    result: ProductionResult,
    *,
    policy: ActionPolicy = DEFAULT_ACTION_POLICY,
) -> tuple[ActionRequest, ...]:
    """Runtime-owned authorization step; a backend cannot call this implicitly."""
    authorized: list[ActionRequest] = []
    for proposal in result.action_proposals:
        try:
            require_authorized_action(proposal.action, policy=policy)
        except ActionPolicyError as exc:
            raise ActionPolicyError(
                f"backend proposal {proposal.proposal_id} denied: {exc}"
            ) from exc
        authorized.append(proposal.action)
    return tuple(authorized)
