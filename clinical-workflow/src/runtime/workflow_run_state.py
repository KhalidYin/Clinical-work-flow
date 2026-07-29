"""Prerelease ten-stage WorkflowRunState projection for P11.

The projection never scans artifacts to infer progress.  Callers must supply
Runtime-owned stage facts.  P11 delivery-gate acceptance is kept distinct from
clinical ReviewPacket/DecisionReceipt evidence and can only pause the next
canonical stage; it cannot reorder or skip the pipeline.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from .pipeline_contract import (
    CANONICAL_PIPELINE,
    CONTRACT_VERSION,
    ContractVersion,
    PipelineStage,
    StrictContractModel,
)


IDENTIFIER_PATTERN = r"^[a-z][a-z0-9._-]{2,127}$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class WorkflowRunStateError(ValueError):
    """A run projection contradicts the fixed pipeline or gate evidence."""


class WorkflowRunStatus(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class StageExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class GateAcceptanceStatus(StrEnum):
    NOT_READY = "not_ready"
    AWAITING_USER_ACCEPTANCE = "awaiting_user_acceptance"
    ACCEPTED = "accepted"


class WorkflowActionName(StrEnum):
    RUN = "run"
    RESUME = "resume"
    RETRY = "retry"
    REFRESH = "refresh"


class RunBlockerKind(StrEnum):
    INPUT = "input"
    VALIDATION = "validation"
    REVIEW = "review"
    SYSTEM = "system"
    GATE_ACCEPTANCE = "gate_acceptance"


class KnowledgeLockProjection(StrictContractModel):
    snapshot_id: str = Field(pattern=IDENTIFIER_PATTERN)
    snapshot_sha256: str = Field(pattern=SHA256_PATTERN)
    status: Literal["locked"] = "locked"


class ModelPolicyProjection(StrictContractModel):
    registry_version: str = Field(
        pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"
    )
    production_profile_id: str = Field(pattern=IDENTIFIER_PATTERN)
    validation_profile_id: str = Field(pattern=IDENTIFIER_PATTERN)
    policy_sha256: str = Field(pattern=SHA256_PATTERN)


class WorkflowNextAction(StrictContractModel):
    action: WorkflowActionName
    stage_id: PipelineStage | None = None
    enabled: bool
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def require_reason_for_disabled_action(self) -> Self:
        if not self.enabled and not self.reason:
            raise ValueError("disabled workflow actions require a reason")
        return self


class RunBlocker(StrictContractModel):
    kind: RunBlockerKind
    stage_id: PipelineStage
    code: str = Field(pattern=IDENTIFIER_PATTERN)
    summary: str = Field(min_length=1, max_length=1000)
    evidence_refs: tuple[str, ...] = Field(min_length=1)

    @field_validator("evidence_refs")
    @classmethod
    def reject_duplicate_evidence(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("blocker evidence_refs must not contain duplicates")
        return value


class StageState(StrictContractModel):
    ordinal: int = Field(ge=1, le=10)
    stage_id: PipelineStage
    display_name: str = Field(min_length=1)
    state: StageExecutionStatus
    gate_acceptance: GateAcceptanceStatus = GateAcceptanceStatus.NOT_READY
    gate_evidence_report_ref: str | None = Field(default=None, min_length=1)
    input_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()
    production_run_ref: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    validation_run_refs: tuple[str, ...] = ()
    knowledge_usage_ref: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    clinical_review_ref: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)
    completion_evidence_refs: tuple[str, ...] = ()

    @field_validator(
        "input_refs",
        "evidence_refs",
        "artifact_refs",
        "validation_run_refs",
        "completion_evidence_refs",
    )
    @classmethod
    def reject_duplicates(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("stage projection lists must not contain duplicates")
        return value

    @field_validator("gate_evidence_report_ref")
    @classmethod
    def keep_delivery_gate_outside_review_queue(
        cls, value: str | None
    ) -> str | None:
        if value is not None and (
            not value.startswith("docs/reviews/P11-G")
            or ".review_queue" in value
            or ".." in value
        ):
            raise ValueError(
                "gate evidence report must use docs/reviews/P11-G* outside .review_queue"
            )
        return value

    @model_validator(mode="after")
    def validate_execution_and_acceptance_shape(self) -> Self:
        if self.state is StageExecutionStatus.COMPLETED:
            if not self.completion_evidence_refs:
                raise ValueError("completed stages require completion evidence")
            if self.gate_acceptance is GateAcceptanceStatus.NOT_READY:
                raise ValueError(
                    "completed stages must await or have user gate acceptance"
                )
            if not self.gate_evidence_report_ref:
                raise ValueError(
                    "completed stages require a gate evidence report reference"
                )
        else:
            if self.gate_acceptance is not GateAcceptanceStatus.NOT_READY:
                raise ValueError(
                    "incomplete stages cannot await or receive gate acceptance"
                )
            if self.gate_evidence_report_ref is not None:
                raise ValueError(
                    "incomplete stages cannot reference a gate evidence report"
                )
            if self.completion_evidence_refs:
                raise ValueError(
                    "incomplete stages cannot claim completion evidence"
                )
        return self


class WorkflowRunState(StrictContractModel):
    schema_version: Literal["0.1.0"] = "0.1.0"
    study_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(pattern=IDENTIFIER_PATTERN)
    pipeline_contract_version: ContractVersion = CONTRACT_VERSION
    knowledge_lock: KnowledgeLockProjection
    model_policy: ModelPolicyProjection
    run_state: WorkflowRunStatus
    active_stage_id: PipelineStage | None
    stages: tuple[StageState, ...] = Field(min_length=10, max_length=10)
    next_actions: tuple[WorkflowNextAction, ...] = Field(min_length=1)
    blocker: RunBlocker | None = None

    @model_validator(mode="after")
    def validate_canonical_projection(self) -> Self:
        expected = tuple(PipelineStage)
        actual = tuple(item.stage_id for item in self.stages)
        if actual != expected:
            raise ValueError("stages must use the canonical ten-stage order")
        for ordinal, stage in enumerate(self.stages, start=1):
            contract = CANONICAL_PIPELINE.get_stage(stage.stage_id)
            if stage.ordinal != ordinal or stage.display_name != contract.display_name:
                raise ValueError(
                    f"stage {stage.stage_id.value} ordinal/display name drifted"
                )

        running = tuple(
            item for item in self.stages if item.state is StageExecutionStatus.RUNNING
        )
        blocked = tuple(
            item for item in self.stages if item.state is StageExecutionStatus.BLOCKED
        )
        awaiting = tuple(
            item
            for item in self.stages
            if item.gate_acceptance
            is GateAcceptanceStatus.AWAITING_USER_ACCEPTANCE
        )
        if len(running) > 1 or len(blocked) > 1 or len(awaiting) > 1:
            raise ValueError(
                "only one stage may be running, blocked, or awaiting acceptance"
            )

        for index, stage in enumerate(self.stages):
            if stage.state is not StageExecutionStatus.PENDING:
                prior = self.stages[:index]
                if any(
                    item.gate_acceptance is not GateAcceptanceStatus.ACCEPTED
                    for item in prior
                ):
                    raise ValueError(
                        "a stage cannot start before every prior gate is accepted"
                    )
            if (
                stage.gate_acceptance
                is GateAcceptanceStatus.AWAITING_USER_ACCEPTANCE
                and any(
                    later.state is not StageExecutionStatus.PENDING
                    for later in self.stages[index + 1 :]
                )
            ):
                raise ValueError(
                    "later stages must remain pending while a gate awaits acceptance"
                )

        self._validate_run_state(running=running, blocked=blocked, awaiting=awaiting)
        self._validate_next_actions(awaiting=awaiting)
        return self

    def _validate_run_state(
        self,
        *,
        running: tuple[StageState, ...],
        blocked: tuple[StageState, ...],
        awaiting: tuple[StageState, ...],
    ) -> None:
        active_candidates = running or blocked or awaiting
        if active_candidates:
            if self.active_stage_id != active_candidates[0].stage_id:
                raise ValueError("active_stage_id must match the active stage")

        if self.run_state is WorkflowRunStatus.RUNNING:
            if len(running) != 1 or self.blocker is not None:
                raise ValueError("running state requires one running stage and no blocker")
        elif self.run_state is WorkflowRunStatus.BLOCKED:
            if len(blocked) + len(awaiting) != 1 or self.blocker is None:
                raise ValueError(
                    "blocked state requires one blocked/awaiting stage and a blocker"
                )
            if self.blocker.stage_id != self.active_stage_id:
                raise ValueError("blocker stage must match active_stage_id")
            if awaiting and self.blocker.kind is not RunBlockerKind.GATE_ACCEPTANCE:
                raise ValueError(
                    "awaiting user acceptance requires a gate_acceptance blocker"
                )
        elif self.run_state is WorkflowRunStatus.COMPLETED:
            if self.active_stage_id is not PipelineStage.SUBMISSION_PACKAGING:
                raise ValueError("completed run must select submission_packaging")
            if self.blocker is not None:
                raise ValueError("completed run cannot have a blocker")
            if any(
                item.state is not StageExecutionStatus.COMPLETED
                or item.gate_acceptance is not GateAcceptanceStatus.ACCEPTED
                for item in self.stages
            ):
                raise ValueError("completed run requires all ten accepted stages")
        elif running or blocked or awaiting or self.blocker is not None:
            raise ValueError("idle state cannot contain active or blocked stages")

    def _validate_next_actions(
        self,
        *,
        awaiting: tuple[StageState, ...],
    ) -> None:
        action_names = tuple(item.action for item in self.next_actions)
        if len(action_names) != len(set(action_names)):
            raise ValueError("next_actions must not contain duplicate actions")
        if awaiting and any(
            item.enabled and item.action is not WorkflowActionName.REFRESH
            for item in self.next_actions
        ):
            raise ValueError(
                "only refresh may be enabled while user gate acceptance is pending"
            )
