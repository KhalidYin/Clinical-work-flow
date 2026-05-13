"""
Workflow Orchestrator v2.0 — Dual-Agent + MCP + Human Gates.

Coordinates:
  - MainAgent:     PLAN → EXECUTE → REVIEW 循环
  - ReviewerAgent: 独立交叉审阅 (不同模型)
  - MCP Tools:     确定性操作
  - Human Gates:   人工审核 + 双 Agent 争议仲裁
"""

from dataclasses import dataclass, field
from typing import Any, Callable
import logging

from .state_machine import (
    WorkflowState, Stage, TrialPhase, TherapeuticArea,
    ApprovalStatus, HUMAN_GATES, AI_AUTO_STAGES,
)
from ..agents.base import (
    AgentConfig, AgentContext, AgentRole,
    Confidence, Severity, ReviewLevel,
)
from ..agents.main_agent import MainAgent, STAGE_CONFIGS
from ..agents.reviewer_agent import ReviewerAgent
from ..agents.review_package import ReviewPackage, ReviewerReport
from ..agents.arbitration import (
    ArbitrationCase, ArbitrationHistory,
    CrossReviewCycle, MAX_REVIEW_ROUNDS,
)

logger = logging.getLogger(__name__)


# ── Orchestrator Config ────────────────────────────────────────


@dataclass
class OrchestratorConfig:
    trial_phase: str = "phase_iii"
    therapeutic_area: str = "non_oncology"
    require_human_approval: bool = True
    auto_execute_ai_stages: bool = True
    stop_on_error: bool = True
    cross_review_enabled: bool = True       # 启用 ReviewerAgent
    max_review_rounds: int = MAX_REVIEW_ROUNDS
    output_dir: str = "./output"
    checkpoint_dir: str = ".workflow"


# ── Orchestrator ────────────────────────────────────────────────


@dataclass
class Orchestrator:
    """
    Central orchestrator v2.0.

    Dual-Agent architecture:
      1. MainAgent:     PLAN → calls MCP tools → self-check → prepares review package
      2. ReviewerAgent: Independent cross-review on MainAgent outputs
      3. Human Gates:   Approval + Arbitration when agents disagree
    """

    config: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    state: WorkflowState = field(default_factory=WorkflowState)

    main_agent: MainAgent | None = None
    reviewer_agent: ReviewerAgent | None = None

    tool_registry: dict[str, Callable] = field(default_factory=dict)
    arbitration_history: ArbitrationHistory = field(default_factory=ArbitrationHistory)

    def __post_init__(self):
        self.state.trial_phase = TrialPhase(self.config.trial_phase)
        self.state.therapeutic_area = TherapeuticArea(self.config.therapeutic_area)

        # Initialize Agent context
        context = AgentContext(
            study_id=self.state.study_id,
            pipeline_state=self.state.__dict__ if hasattr(self.state, '__dict__') else {},
            tool_registry=self.tool_registry,
        )

        # MainAgent (Opus — deep reasoning)
        self.main_agent = MainAgent(
            config=AgentConfig(
                name="ClinicalProgrammingMainAgent",
                role=AgentRole.MAIN,
                model="claude-opus-4-7",
            ),
            context=context,
        )

        # ReviewerAgent (Sonnet — different model, different blind spots)
        if self.config.cross_review_enabled:
            self.reviewer_agent = ReviewerAgent(
                config=AgentConfig(
                    name="ClinicalProgrammingReviewerAgent",
                    role=AgentRole.REVIEWER,
                    model="claude-sonnet-4-6",
                ),
                context=AgentContext(
                    study_id=self.state.study_id,
                    tool_registry=self.tool_registry,
                ),
            )

    # ── Tool Registration ───────────────────────────────────────

    def register_tool(self, name: str, tool_fn: Callable) -> None:
        self.tool_registry[name] = tool_fn
        if self.main_agent:
            self.main_agent.context.tool_registry = self.tool_registry
        if self.reviewer_agent:
            self.reviewer_agent.context.tool_registry = self.tool_registry

    # ── Stage Execution (with Cross-Review) ─────────────────────

    async def execute_stage(self, stage: Stage) -> dict[str, Any]:
        """
        Execute one pipeline stage with the full dual-agent cycle:

        1. MainAgent.PLAN   — Build execution plan
        2. MainAgent.EXECUTE — Call MCP tools
        3. MainAgent.REVIEW  — Self-check
        4. ReviewerAgent     — Independent cross-review (if enabled)
        5. Fix cycle         — Resolve issues (max 2 rounds)
        6. Arbitration       — Human decides if agents disagree
        7. Human Gate        — Package for human approval (if applicable)
        """
        stage_name = stage.value
        stage_config = STAGE_CONFIGS.get(stage_name)
        result: dict[str, Any] = {
            "stage": stage_name,
            "status": "started",
            "main_agent": self.main_agent.name if self.main_agent else "N/A",
        }

        ctx = self._build_stage_context(stage)

        # ── Step 1: MainAgent PLAN ──────────────────────────
        logger.info(f"Stage {stage_name}: MainAgent PLAN")
        plan = await self.main_agent.plan(stage_name)
        if plan["status"] == "blocked":
            result["status"] = "blocked"
            result["blockers"] = plan.get("blockers", [])
            return result

        # ── Step 2: MainAgent EXECUTE ───────────────────────
        logger.info(f"Stage {stage_name}: MainAgent EXECUTE")
        exec_results = await self.main_agent.execute(stage_name, plan["plan"])
        if exec_results.get("action") == "STOP":
            result["status"] = "stopped_for_human"
            result["reason"] = exec_results.get("reason")
            return result

        result["execution"] = exec_results

        # ── Step 3: MainAgent SELF-REVIEW ───────────────────
        logger.info(f"Stage {stage_name}: MainAgent REVIEW")
        self_review = await self.main_agent.review(stage_name, exec_results)
        result["self_review"] = self_review

        # ── Step 4: ReviewerAgent CROSS-REVIEW ──────────────
        reviewer_report = None
        arbitration_items = []

        if (self.config.cross_review_enabled
                and self.reviewer_agent
                and stage_config
                and stage_config.reviewer_level != "NONE"):

            logger.info(f"Stage {stage_name}: ReviewerAgent cross-review "
                        f"(level={stage_config.reviewer_level})")

            cross_cycle = CrossReviewCycle(stage=stage_name)

            for round_num in range(1, self.config.max_review_rounds + 1):
                # Reviewer 独立审阅 (不拿 MainAgent 推理过程!)
                reviewer_report = await self.reviewer_agent.review(
                    stage=stage_name,
                    artifacts=exec_results.get("artifacts", {}),
                    level=stage_config.reviewer_level,
                    round_num=round_num,
                )
                cross_cycle.rounds_completed = round_num
                cross_cycle.issues_remaining = len(
                    reviewer_report.get_critical_and_major()
                )

                result[f"review_round_{round_num}"] = reviewer_report.summary()

                if not reviewer_report.has_critical_or_major():
                    # All good — pass!
                    cross_cycle.issues_resolved = cross_cycle.issues_remaining
                    cross_cycle.issues_remaining = 0
                    break

                if round_num < self.config.max_review_rounds:
                    # Fix and re-review
                    logger.info(f"Stage {stage_name}: Fixing "
                                f"{cross_cycle.issues_remaining} issues, round {round_num}")
                    issues = reviewer_report.get_critical_and_major()
                    exec_results = await self.main_agent.fix_issues(
                        stage_name, issues, exec_results.get("artifacts", {})
                    )
                    cross_cycle.issues_resolved += len(issues)

            # Check if we need arbitration
            if cross_cycle.needs_arbitration():
                logger.warning(f"Stage {stage_name}: ARBITRATION NEEDED "
                               f"after {cross_cycle.rounds_completed} rounds")
                arbitration_items = await self._create_arbitration_cases(
                    stage_name, reviewer_report
                )
                result["arbitration_needed"] = True
                result["arbitration_items_count"] = len(arbitration_items)

        # ── Step 5: Human Gate ─────────────────────────────
        if stage_config and stage_config.gate == "HUMAN" and self.config.require_human_approval:
            logger.info(f"Stage {stage_name}: Preparing Human Gate review package")

            package = await self.main_agent.prepare_review_package(
                stage=stage_name,
                results=exec_results,
                reviewer_report=reviewer_report.summary() if reviewer_report else None,
                arbitration_items=[
                    a.display_for_human() for a in arbitration_items
                ] if arbitration_items else None,
            )

            result["review_package"] = {
                "package_id": package.package_id,
                "checklist_count": len(package.checklist_results),
                "issues_count": len(package.issues_for_attention),
                "arbitrations_count": len(package.arbitration_items),
                "review_score": package.review_score,
                "status": "awaiting_approval",
            }

            # 如果有仲裁项 → 阻塞, 等待人类裁决
            if arbitration_items:
                result["status"] = "arbitration_required"
                return result

            result["status"] = "awaiting_human_approval"
            return result

        # ── Step 6: AI Auto — Advance ──────────────────────
        if stage in AI_AUTO_STAGES and self.config.auto_execute_ai_stages:
            next_stage = stage.next
            if next_stage:
                self.state.current_stage = next_stage
            result["status"] = "auto_advanced"
            result["next_stage"] = next_stage.value if next_stage else None
            return result

        result["status"] = "complete"
        return result

    # ── Arbitration ────────────────────────────────────────────

    async def _create_arbitration_cases(self, stage: str,
                                         reviewer_report: ReviewerReport,
                                         ) -> list[ArbitrationCase]:
        """从审阅报告中创建仲裁案例"""
        cases = []
        for issue in reviewer_report.get_critical_and_major():
            case = ArbitrationCase(
                arbitration_id=f"ARB-{stage}-{len(cases)+1:03d}",
                stage=stage,
                severity=issue.severity,
                rounds_attempted=reviewer_report.review_round,
                contested_item=issue.location,
                main_agent_position={
                    "value": "As generated (see artifact)",
                    "rationale": "MainAgent generated per CDISC standard",
                    "standard_ref": "CDISC IG standard",
                    "confidence": "HIGH",
                },
                reviewer_position={
                    "value": issue.finding,
                    "rationale": issue.recommendation,
                    "standard_ref": issue.standard_reference,
                    "confidence": issue.confidence,
                },
                authoritative_reference=issue.standard_reference,
                impact_assessment=f"This {issue.severity} issue affects {issue.location}",
                ai_recommendation=f"Review {issue.standard_reference} and decide",
            )
            self.arbitration_history.add(case)
            cases.append(case)
        return cases

    async def resolve_arbitration(self, arbitration_id: str,
                                   decision: str, decided_by: str,
                                   rationale: str = "") -> dict[str, Any]:
        """人类裁决争议"""
        for case in self.arbitration_history.cases:
            if case.arbitration_id == arbitration_id and not case.is_resolved:
                case.resolve(decision, decided_by, rationale)
                return {"status": "resolved", "case": case.display_for_human()}
        return {"status": "not_found", "arbitration_id": arbitration_id}

    # ── Full Pipeline ──────────────────────────────────────────

    async def run_pipeline(self, start_stage: Stage | None = None) -> dict[str, Any]:
        """Execute the full pipeline"""
        current = start_stage or self.state.current_stage
        pipeline_results: dict[str, Any] = {}

        seq = Stage.sequence()
        start_idx = seq.index(current) if current in seq else 0

        for stage in seq[start_idx:]:
            logger.info(f"Pipeline Stage: {stage.value}")

            result = await self.execute_stage(stage)
            pipeline_results[stage.value] = result

            # Stop if human approval or arbitration needed
            if result["status"] in ("awaiting_human_approval",
                                     "arbitration_required",
                                     "stopped_for_human",
                                     "blocked"):
                logger.info(f"Pipeline paused at {stage.value}: {result['status']}")
                break

        return pipeline_results

    # ── Helpers ────────────────────────────────────────────────

    def _build_stage_context(self, stage: Stage) -> dict[str, Any]:
        return {
            "study_id": self.state.study_id,
            "trial_phase": self.state.trial_phase.value,
            "therapeutic_area": self.state.therapeutic_area.value,
            "current_stage": stage.value,
            "artifacts": self.state.artifacts,
        }

    def status_report(self) -> dict[str, Any]:
        report = self.state.summary()
        report["agents"] = {
            "main": "MainAgent (claude-opus-4-7)",
            "reviewer": "ReviewerAgent (claude-sonnet-4-6)"
            if self.reviewer_agent else "DISABLED",
        }
        report["arbitrations"] = self.arbitration_history.get_stats()
        return report
