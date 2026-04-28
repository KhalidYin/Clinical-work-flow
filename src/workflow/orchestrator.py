"""
Workflow Orchestrator — the central engine that coordinates AI Agents,
Claude Skills, and MCP Tools across the clinical stat programming pipeline.
"""

from dataclasses import dataclass, field
from typing import Any, Callable
import logging

from .state_machine import (
    WorkflowState,
    Stage,
    TrialPhase,
    TherapeuticArea,
    ApprovalStatus,
    HUMAN_GATES,
    AI_AUTO_STAGES,
)

logger = logging.getLogger(__name__)

# ── Stage → Responsible Component mapping ──────────────────────────

STAGE_ASSIGNMENT: dict[Stage, dict[str, str]] = {
    Stage.PROTOCOL:           {"agent": "ProtocolAnalyzer",  "skill": "protocol-analyze"},
    Stage.SAP:                {"agent": "SAPBuilder",        "skill": "sap-review"},
    Stage.CRF_DESIGN:         {"agent": "CRFMapper",         "skill": "crf-review"},
    Stage.DATA_COLLECTION:    {"agent": "DataMonitor",       "skill": None},
    Stage.SDTM_SPEC:          {"agent": "SDTMSpecBuilder",   "skill": "domain-review"},
    Stage.SDTM_PROGRAMMING:   {"agent": "SDTMProgrammer",    "skill": None},
    Stage.ADAM_SPEC:          {"agent": "ADaMSpecBuilder",   "skill": "domain-review"},
    Stage.ADAM_PROGRAMMING:   {"agent": "ADaMProgrammer",    "skill": None},
    Stage.TFL_SHELL:          {"agent": "TFLShellDesigner",  "skill": "tfl-qc"},
    Stage.TFL_PROGRAMMING:    {"agent": "TFLGenerator",      "skill": None},
    Stage.QC_VALIDATION:      {"agent": "QCValidator",       "skill": "tfl-qc"},
    Stage.SUBMISSION:         {"agent": "SubmissionPackager", "skill": "adrg-draft"},
}


@dataclass
class OrchestratorConfig:
    """Configuration for the workflow orchestrator."""

    trial_phase: TrialPhase = TrialPhase.PHASE_III
    therapeutic_area: TherapeuticArea = TherapeuticArea.NON_ONCOLOGY
    require_human_approval: bool = True
    auto_execute_ai_stages: bool = True
    stop_on_error: bool = True
    output_dir: str = "./output"


@dataclass
class Orchestrator:
    """
    Central orchestrator for the clinical stat programming AI workflow.

    Coordinates three layers:
      - AI Agents:  autonomous multi-step tasks
      - Claude Skills: interactive human-AI review workflows
      - MCP Tools:  deterministic structured operations
    """

    config: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    state: WorkflowState = field(default_factory=WorkflowState)

    agent_registry: dict[str, Callable] = field(default_factory=dict)
    skill_registry: dict[str, Callable] = field(default_factory=dict)
    tool_registry: dict[str, Callable] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.state.trial_phase = self.config.trial_phase
        self.state.therapeutic_area = self.config.therapeutic_area

    # ── Agent / Skill / Tool registration ──────────────────────────

    def register_agent(self, name: str, factory: Callable) -> None:
        self.agent_registry[name] = factory

    def register_skill(self, name: str, skill_fn: Callable) -> None:
        self.skill_registry[name] = skill_fn

    def register_tool(self, name: str, tool_fn: Callable) -> None:
        self.tool_registry[name] = tool_fn

    # ── Stage execution ────────────────────────────────────────────

    async def execute_stage(self, stage: Stage, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Execute one pipeline stage, routing to the correct component.
        """
        assignment = STAGE_ASSIGNMENT.get(stage, {})
        agent_name = assignment.get("agent")
        skill_name = assignment.get("skill")
        results: dict[str, Any] = {"stage": stage.value, "status": "started"}

        ctx = context or {}
        ctx.update({
            "study_id": self.state.study_id,
            "trial_phase": self.state.trial_phase.value,
            "therapeutic_area": self.state.therapeutic_area.value,
            "artifacts": self.state.artifacts,
        })

        # 1. Execute AI agent (autonomous)
        if agent_name and agent_name in self.agent_registry:
            logger.info(f"  Agent: {agent_name}")
            try:
                agent_result = await self._run_agent(agent_name, ctx)
                results["agent"] = agent_result
                results["status"] = "agent_complete"
            except Exception as e:
                results["status"] = "agent_failed"
                results["error"] = str(e)
                if self.config.stop_on_error:
                    raise

        # 2. Launch Claude Skill for human review (interactive)
        if skill_name and skill_name in self.skill_registry:
            logger.info(f"  Skill: {skill_name}")
            try:
                skill_result = await self._run_skill(skill_name, ctx)
                results["skill"] = skill_result
            except Exception as e:
                results["skill_error"] = str(e)

        # 3. Check human gate
        gate = HUMAN_GATES.get(stage)
        if gate and self.config.require_human_approval:
            results["requires_approval"] = True
            results["gate"] = {
                "description": gate.description,
                "checklist": gate.checklist,
                "reviewers": gate.reviewers,
            }

        results["status"] = "complete"
        self.state.stage_history.append({
            "stage": stage.value,
            "result": results,
        })
        return results

    async def run_pipeline(self, start_stage: Stage | None = None) -> dict[str, Any]:
        """
        Execute the full pipeline from the current or specified stage.
        Stops at human gates for approval.
        """
        current = start_stage or self.state.current_stage
        pipeline_results: dict[str, Any] = {}

        for stage in Stage.sequence():
            # Skip stages before our starting point
            seq = Stage.sequence()
            if seq.index(stage) < seq.index(current):
                continue

            logger.info(f"Stage: {stage.value}")

            # Execute stage
            result = await self.execute_stage(stage)
            pipeline_results[stage.value] = result

            # Check if AI-auto stage — proceed immediately
            if stage in AI_AUTO_STAGES and self.config.auto_execute_ai_stages:
                self.state.current_stage = stage.next or stage
                continue

            # Check if blocked by human gate
            if result.get("requires_approval"):
                logger.info(f"  Blocked: awaiting human approval at {stage.value}")
                break

            self.state.current_stage = stage.next or stage

        return pipeline_results

    # ── Internal helpers ───────────────────────────────────────────

    async def _run_agent(self, name: str, context: dict) -> dict:
        agent = self.agent_registry[name](context)
        return await agent.run()

    async def _run_skill(self, name: str, context: dict) -> dict:
        skill = self.skill_registry[name]
        return await skill(context)

    # ── Reporting ──────────────────────────────────────────────────

    def status_report(self) -> dict[str, Any]:
        return {
            **self.state.summary(),
            "pending_human_gates": [
                {"stage": g.stage.value, "description": g.description, "status": g.status.value}
                for g in self.state.get_pending_approvals()
            ],
            "next_stage": self.state.current_stage.next.value
            if self.state.current_stage.next else "complete",
        }
