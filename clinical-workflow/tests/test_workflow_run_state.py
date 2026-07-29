from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.runtime.pipeline_contract import CANONICAL_PIPELINE, PipelineStage
from src.runtime.workflow_run_state import (
    GateAcceptanceStatus,
    KnowledgeLockProjection,
    ModelPolicyProjection,
    RunBlocker,
    RunBlockerKind,
    StageExecutionStatus,
    StageState,
    WorkflowActionName,
    WorkflowNextAction,
    WorkflowRunState,
    WorkflowRunStatus,
)


def _stage(
    stage_id: PipelineStage,
    *,
    state: StageExecutionStatus = StageExecutionStatus.PENDING,
    gate: GateAcceptanceStatus = GateAcceptanceStatus.NOT_READY,
) -> StageState:
    contract = CANONICAL_PIPELINE.get_stage(stage_id)
    completed = state is StageExecutionStatus.COMPLETED
    return StageState(
        ordinal=contract.ordinal,
        stage_id=stage_id,
        display_name=contract.display_name,
        state=state,
        gate_acceptance=gate,
        gate_evidence_report_ref=(
            f"docs/reviews/P11-G{contract.ordinal:02d}-{stage_id.value.replace('_', '-')}.md"
            if completed
            else None
        ),
        input_refs=("input.synthetic.001",) if state is not StageExecutionStatus.PENDING else (),
        evidence_refs=(
            ("evidence.synthetic.001",)
            if state is not StageExecutionStatus.PENDING
            else ()
        ),
        artifact_refs=("artifact.synthetic.001",) if completed else (),
        completion_evidence_refs=(
            contract.completion_evidence if completed else ()
        ),
    )


def _state(
    stages: tuple[StageState, ...],
    *,
    run_state: WorkflowRunStatus,
    active_stage_id: PipelineStage | None,
    blocker: RunBlocker | None = None,
    next_actions: tuple[WorkflowNextAction, ...] | None = None,
) -> WorkflowRunState:
    return WorkflowRunState(
        study_id="SYNTH-E2E-001",
        run_id="run.synthetic.001",
        knowledge_lock=KnowledgeLockProjection(
            snapshot_id="snapshot-p11-s0",
            snapshot_sha256="a" * 64,
        ),
        model_policy=ModelPolicyProjection(
            registry_version="1.0.0",
            production_profile_id="producer.synthetic",
            validation_profile_id="validator.synthetic",
            policy_sha256="b" * 64,
        ),
        run_state=run_state,
        active_stage_id=active_stage_id,
        stages=stages,
        next_actions=next_actions
        or (
            WorkflowNextAction(
                action=WorkflowActionName.REFRESH,
                enabled=True,
            ),
        ),
        blocker=blocker,
    )


def _pending_stages() -> tuple[StageState, ...]:
    return tuple(_stage(stage_id) for stage_id in PipelineStage)


def test_initial_projection_has_exact_canonical_ten_stage_order() -> None:
    state = _state(
        _pending_stages(),
        run_state=WorkflowRunStatus.IDLE,
        active_stage_id=PipelineStage.PROTOCOL_ANALYSIS,
        next_actions=(
            WorkflowNextAction(
                action=WorkflowActionName.RUN,
                stage_id=PipelineStage.PROTOCOL_ANALYSIS,
                enabled=True,
            ),
            WorkflowNextAction(
                action=WorkflowActionName.REFRESH,
                enabled=True,
            ),
        ),
    )

    assert tuple(item.stage_id for item in state.stages) == tuple(PipelineStage)
    assert len(state.stages) == 10


def test_completed_stage_awaits_delivery_acceptance_outside_review_queue() -> None:
    stages = list(_pending_stages())
    stages[0] = _stage(
        PipelineStage.PROTOCOL_ANALYSIS,
        state=StageExecutionStatus.COMPLETED,
        gate=GateAcceptanceStatus.AWAITING_USER_ACCEPTANCE,
    )
    blocker = RunBlocker(
        kind=RunBlockerKind.GATE_ACCEPTANCE,
        stage_id=PipelineStage.PROTOCOL_ANALYSIS,
        code="gate.acceptance.pending",
        summary="P11-G01 requires explicit user acceptance.",
        evidence_refs=("docs/reviews/P11-G01-protocol-analysis.md",),
    )
    state = _state(
        tuple(stages),
        run_state=WorkflowRunStatus.BLOCKED,
        active_stage_id=PipelineStage.PROTOCOL_ANALYSIS,
        blocker=blocker,
        next_actions=(
            WorkflowNextAction(
                action=WorkflowActionName.RUN,
                stage_id=PipelineStage.SAP_GENERATION,
                enabled=False,
                reason="G1 is awaiting user acceptance.",
            ),
            WorkflowNextAction(
                action=WorkflowActionName.REFRESH,
                enabled=True,
            ),
        ),
    )

    assert (
        state.stages[0].gate_acceptance
        is GateAcceptanceStatus.AWAITING_USER_ACCEPTANCE
    )
    assert state.stages[1].state is StageExecutionStatus.PENDING

    payload = state.stages[0].model_dump(mode="json")
    payload["gate_evidence_report_ref"] = (
        ".review_queue/P11-G01-protocol-analysis.json"
    )
    with pytest.raises(ValidationError, match="outside .review_queue"):
        StageState.model_validate(payload)


def test_next_stage_cannot_run_before_prior_gate_is_accepted() -> None:
    stages = list(_pending_stages())
    stages[0] = _stage(
        PipelineStage.PROTOCOL_ANALYSIS,
        state=StageExecutionStatus.COMPLETED,
        gate=GateAcceptanceStatus.AWAITING_USER_ACCEPTANCE,
    )
    stages[1] = _stage(
        PipelineStage.SAP_GENERATION,
        state=StageExecutionStatus.RUNNING,
    )

    with pytest.raises(
        ValidationError,
        match="later stages must remain pending while a gate awaits acceptance",
    ):
        _state(
            tuple(stages),
            run_state=WorkflowRunStatus.RUNNING,
            active_stage_id=PipelineStage.SAP_GENERATION,
        )


def test_accepted_prior_gate_allows_next_stage_to_run() -> None:
    stages = list(_pending_stages())
    stages[0] = _stage(
        PipelineStage.PROTOCOL_ANALYSIS,
        state=StageExecutionStatus.COMPLETED,
        gate=GateAcceptanceStatus.ACCEPTED,
    )
    stages[1] = _stage(
        PipelineStage.SAP_GENERATION,
        state=StageExecutionStatus.RUNNING,
    )
    state = _state(
        tuple(stages),
        run_state=WorkflowRunStatus.RUNNING,
        active_stage_id=PipelineStage.SAP_GENERATION,
    )
    assert state.active_stage_id is PipelineStage.SAP_GENERATION


def test_awaiting_gate_enables_only_refresh() -> None:
    stages = list(_pending_stages())
    stages[0] = _stage(
        PipelineStage.PROTOCOL_ANALYSIS,
        state=StageExecutionStatus.COMPLETED,
        gate=GateAcceptanceStatus.AWAITING_USER_ACCEPTANCE,
    )
    blocker = RunBlocker(
        kind=RunBlockerKind.GATE_ACCEPTANCE,
        stage_id=PipelineStage.PROTOCOL_ANALYSIS,
        code="gate.acceptance.pending",
        summary="P11-G01 requires explicit user acceptance.",
        evidence_refs=("docs/reviews/P11-G01-protocol-analysis.md",),
    )
    with pytest.raises(ValidationError, match="only refresh"):
        _state(
            tuple(stages),
            run_state=WorkflowRunStatus.BLOCKED,
            active_stage_id=PipelineStage.PROTOCOL_ANALYSIS,
            blocker=blocker,
            next_actions=(
                WorkflowNextAction(
                    action=WorkflowActionName.RUN,
                    stage_id=PipelineStage.SAP_GENERATION,
                    enabled=True,
                ),
            ),
        )


def test_completed_run_requires_all_ten_accepted_gates() -> None:
    accepted = tuple(
        _stage(
            stage_id,
            state=StageExecutionStatus.COMPLETED,
            gate=GateAcceptanceStatus.ACCEPTED,
        )
        for stage_id in PipelineStage
    )
    state = _state(
        accepted,
        run_state=WorkflowRunStatus.COMPLETED,
        active_stage_id=PipelineStage.SUBMISSION_PACKAGING,
    )
    assert state.run_state is WorkflowRunStatus.COMPLETED

    incomplete = list(accepted)
    incomplete[-1] = _stage(PipelineStage.SUBMISSION_PACKAGING)
    with pytest.raises(ValidationError, match="all ten accepted"):
        _state(
            tuple(incomplete),
            run_state=WorkflowRunStatus.COMPLETED,
            active_stage_id=PipelineStage.SUBMISSION_PACKAGING,
        )
