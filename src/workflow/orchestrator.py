"""
Workflow Orchestrator v2.1 — 3 Executor + 1 Reviewer + MCP + Checklists.

路由:
  ProtocolSAPAgent       → protocol, sap, crf_design
  DataStandardsAgent     → sdtm_spec, sdtm_prog, adam_spec, adam_prog
  TFLQCSubmissionAgent   → tfl_shell, tfl_prog, qc_validation, submission

变更管理:
  每次修改 → ChangeRecord → 审计日志
  每次 Gate 审核 → 清单强制校验
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
from ..agents.executors import (
    ProtocolSAPAgent, DataStandardsAgent, TFLQCSubmissionAgent,
    STAGE_EXECUTOR_MAP, get_executor_for_stage,
)
from ..agents.reviewer_agent import ReviewerAgent
from ..agents.stage_checklists import (
    StageChecklist, ChecklistItem, ChecklistItemStatus,
    GATE_CHECKLISTS, get_checklist, validate_checklist_completion,
)
from ..agents.review_package import ReviewPackage, ReviewerReport
from ..agents.arbitration import (
    ArbitrationCase, ArbitrationHistory,
    CrossReviewCycle, MAX_REVIEW_ROUNDS,
)
from ..change_management.change_record import (
    ChangeRecord, FileChange, StageImpact,
    ChangeType, ImpactType,
)
from ..change_management.version_manager import VersionManager, VersionBump
from ..change_management.impact_analyzer import ImpactAnalyzer

logger = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────


@dataclass
class OrchestratorConfig:
    trial_phase: str = "phase_iii"
    therapeutic_area: str = "non_oncology"
    require_human_approval: bool = True
    auto_execute_ai_stages: bool = True
    stop_on_error: bool = True
    cross_review_enabled: bool = True
    max_review_rounds: int = MAX_REVIEW_ROUNDS
    enforce_checklists: bool = True       # v2.1: 强制清单校验
    change_tracking_enabled: bool = True   # v2.1: 变更追踪
    output_dir: str = "./output"
    checkpoint_dir: str = ".workflow"


# ── Orchestrator v2.1 ──────────────────────────────────────────


@dataclass
class Orchestrator:
    """v2.1: 3 Executor + 1 Reviewer + MCP + Checklist + Change Management"""

    config: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    state: WorkflowState = field(default_factory=WorkflowState)

    executors: dict[str, Any] = field(default_factory=dict)
    reviewer_agent: ReviewerAgent | None = None

    tool_registry: dict[str, Callable] = field(default_factory=dict)
    version_manager: VersionManager | None = None
    impact_analyzer: ImpactAnalyzer | None = None
    arbitration_history: ArbitrationHistory = field(default_factory=ArbitrationHistory)
    change_log: list[ChangeRecord] = field(default_factory=list)

    def __post_init__(self):
        self.state.trial_phase = TrialPhase(self.config.trial_phase)
        self.state.therapeutic_area = TherapeuticArea(self.config.therapeutic_area)

        context = AgentContext(
            study_id=self.state.study_id,
            tool_registry=self.tool_registry,
        )

        # 初始化 3 个 Executor (深度专注)
        protocol_config = AgentConfig(
            name="ProtocolSAPAgent", role=AgentRole.MAIN, model="claude-opus-4-7",
        )
        data_config = AgentConfig(
            name="DataStandardsAgent", role=AgentRole.MAIN, model="claude-opus-4-7",
        )
        tfl_config = AgentConfig(
            name="TFLQCSubmissionAgent", role=AgentRole.MAIN, model="claude-opus-4-7",
        )

        self.executors = {
            "ProtocolSAPAgent": ProtocolSAPAgent(protocol_config, context),
            "DataStandardsAgent": DataStandardsAgent(data_config, context),
            "TFLQCSubmissionAgent": TFLQCSubmissionAgent(tfl_config, context),
        }

        # ReviewerAgent (独立模型)
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

        # 版本管理 + 影响分析
        if self.config.change_tracking_enabled:
            self.version_manager = VersionManager(study_id=self.state.study_id)
            self.impact_analyzer = ImpactAnalyzer()

    # ── Stage Execution ────────────────────────────────────────

    async def execute_stage(self, stage: Stage) -> dict[str, Any]:
        stage_name = stage.value
        result: dict[str, Any] = {"stage": stage_name, "status": "started"}

        # 获取对应 Executor
        executor = self._get_executor(stage_name)
        result["executor"] = executor.name

        # 加载审核清单 (如果是 Human Gate)
        checklist = None
        if stage not in AI_AUTO_STAGES:
            checklist = get_checklist(stage_name)
            if checklist:
                result["checklist_loaded"] = True
                result["checklist_items"] = len(checklist.items)

        logger.info(f"Stage {stage_name}: Executor={executor.name}, "
                    f"Checklist={'loaded (' + str(len(checklist.items) if checklist else 0) + ' items)' if checklist else 'N/A'}")

        # ── PLAN ──────────────────────────────────────────
        plan = await executor.plan(stage_name)
        if plan.get("status") == "blocked":
            result["status"] = "blocked"
            return result

        # ── EXECUTE ───────────────────────────────────────
        exec_result = await executor.execute(stage_name, plan)
        if exec_result.get("action") == "STOP":
            result["status"] = "stopped_for_human"
            return result

        result["execution"] = exec_result

        # ── SELF-REVIEW ──────────────────────────────────
        self_review = await executor.review(stage_name, exec_result)
        result["self_review"] = self_review

        # ── ReviewerAgent Cross-Review ───────────────────
        reviewer_report = None
        arbitration_items = []

        if (self.config.cross_review_enabled and self.reviewer_agent
                and stage not in AI_AUTO_STAGES
                and stage_name != "protocol"):
            reviewer_report = await self._run_cross_review(
                stage_name, exec_result, result
            )
            if reviewer_report.get("arbitration_needed"):
                arbitration_items = reviewer_report.get("arbitration_items", [])
                result["arbitration_needed"] = True

        # ── Checklist Validation ─────────────────────────
        if checklist and self.config.enforce_checklists:
            checklist_check = validate_checklist_completion(stage_name, [exec_result])
            if not checklist_check["valid"]:
                result["status"] = "checklist_incomplete"
                result["checklist_violations"] = checklist_check["violations"]
                logger.warning(f"Stage {stage_name}: Checklist not properly "
                               f"completed — {len(checklist_check['violations'])} violations")
                return result

        # ── Human Gate ───────────────────────────────────
        if stage not in AI_AUTO_STAGES and self.config.require_human_approval:
            review_pkg = await self._prepare_review_package(
                stage_name, executor, exec_result, checklist, reviewer_report,
                arbitration_items,
            )
            result["review_package"] = review_pkg

            if arbitration_items:
                result["status"] = "arbitration_required"
                return result

            result["status"] = "awaiting_human_approval"
            return result

        # AI Auto → advance
        if stage in AI_AUTO_STAGES and self.config.auto_execute_ai_stages:
            result["status"] = "auto_advanced"
        else:
            result["status"] = "complete"

        return result

    # ── Cross Review Cycle ────────────────────────────────────

    async def _run_cross_review(self, stage_name: str,
                                 exec_result: dict,
                                 result: dict) -> dict[str, Any]:
        """运行双 Agent 交叉审阅循环 (最多 2 轮)"""
        cycle = CrossReviewCycle(stage=stage_name)
        reviewer_report = None

        for round_num in range(1, self.config.max_review_rounds + 1):
            reviewer_report = await self.reviewer_agent.review(
                stage=stage_name,
                artifacts=exec_result.get("artifacts", {}),
                level="HEAVY" if stage_name in ("sap", "sdtm_spec", "adam_spec") else "MEDIUM",
                round_num=round_num,
            )
            cycle.rounds_completed = round_num
            cycle.issues_remaining = len(reviewer_report.get_critical_and_major())

            result[f"review_round_{round_num}"] = reviewer_report.summary()

            if not reviewer_report.has_critical_or_major():
                cycle.issues_remaining = 0
                break

            if round_num < self.config.max_review_rounds:
                # 修复后重审
                logger.info(f"Stage {stage_name}: Fix cycle round {round_num}")
                issues = reviewer_report.get_critical_and_major()
                executor = self._get_executor(stage_name)
                # 记录变更
                if self.config.change_tracking_enabled:
                    ch = ChangeRecord(
                        change_id=f"CHG-REVIEWER-{stage_name}-R{round_num}",
                        change_type=ChangeType.REVIEWER_FEEDBACK,
                        triggered_by="ReviewerAgent",
                        triggered_by_role="AI",
                        description=f"Cross-review round {round_num}: {len(issues)} issues",
                        impact_type=ImpactType.STAGE_LOCAL,
                        requires_re_approval=False,
                    )
                    self.change_log.append(ch)
                cycle.issues_resolved += len(issues)

        if cycle.needs_arbitration():
            cases = self._create_arbitration_cases(stage_name, reviewer_report)
            return {"arbitration_needed": True, "arbitration_items": [
                c.display_for_human() for c in cases
            ]}

        result["review_score"] = reviewer_report.review_score if reviewer_report else 100
        return reviewer_report.summary() if reviewer_report else {}

    # ── Review Package ─────────────────────────────────────────

    async def _prepare_review_package(self, stage_name: str,
                                       executor, exec_result: dict,
                                       checklist: StageChecklist | None,
                                       reviewer_report: dict | None,
                                       arbitration_items: list[dict],
                                       ) -> dict[str, Any]:
        """生成 Human Gate 审核包 (包含增量审核支持)"""
        pkg = {
            "package_id": f"PKG-{stage_name}-{self.state.study_id}",
            "stage": stage_name,
            "executor": executor.name,
            "reviewer": f"ReviewerAgent ({self.reviewer_agent.model})" if self.reviewer_agent else "NONE",
            "review_score": reviewer_report.get("score", 100) if reviewer_report else 100,
            "checklist": checklist.to_dict() if checklist else None,
            "checklist_items": None,
            "arbitrations": arbitration_items,
            "change_summary": "Initial submission" if not self.change_log else
                f"{len(self.change_log)} changes tracked",
            "status": "awaiting_approval",
        }

        # 增量审核: 如果是第 N 次提交, 标注哪些项变了
        if checklist:
            pkg["checklist_items"] = [
                {
                    "id": item.id, "item": item.item,
                    "status": item.status.value,
                    "agent_evidence": item.agent_evidence[:100],
                }
                for item in checklist.items
            ]

        return pkg

    # ── Human Review Feedback (变更追踪入口) ──────────────────

    async def handle_human_review_feedback(self, stage: Stage,
                                            feedback: dict) -> dict[str, Any]:
        """
        处理人工审核返回的修改要求。

        feedback format:
          { "reviewer": "Zhang", "decision": "rejected", "items": [
              {"item_id": "ADAM-01", "action": "fix", "note": "..."}, ...],
            "general_notes": "..." }
        """
        stage_name = stage.value
        executor = self._get_executor(stage_name)

        # 记录变更
        if self.config.change_tracking_enabled:
            ch = ChangeRecord(
                change_id=f"CHG-HUMAN-{stage_name}-{_timestamp()}",
                change_type=ChangeType.HUMAN_REVIEW,
                triggered_by=feedback.get("reviewer", "Unknown"),
                triggered_by_role="Human",
                description=feedback.get("general_notes", "Human review feedback"),
                reason="Human Gate review returned revisions",
                impact_type=ImpactType.STAGE_LOCAL,
                requires_re_approval=True,
            )

            # 记录受影响的文件
            for item in feedback.get("items", []):
                ch.files_changed.append(FileChange(
                    path=f"{stage_name}/{item.get('item_id', 'unknown')}",
                    old_version="current",
                    new_version="pending",
                    diff_summary=item.get("note", ""),
                ))

            self.change_log.append(ch)

            # 版本升级 (MINOR bump for human review changes)
            if self.version_manager:
                for item in feedback.get("items", []):
                    self.version_manager.bump(
                        f"{stage_name}/{item.get('item_id', 'unknown')}",
                        VersionBump.MINOR,
                        ch.change_id,
                        ch.triggered_by,
                    )

        return {
            "status": "feedback_recorded",
            "change_id": ch.change_id if self.config.change_tracking_enabled else "N/A",
            "stage": stage_name,
            "action": "re-execute_stage",
        }

    # ── Protocol Amendment Handler ─────────────────────────────

    async def handle_protocol_amendment(self, amendment_id: str,
                                         description: str,
                                         triggered_by: str) -> dict[str, Any]:
        """
        处理方案修订。
        自动计算全链路影响, 回退到最早受影响阶段, 重新执行。
        """
        if not self.impact_analyzer:
            return {"status": "error", "message": "Impact analyzer not enabled"}

        impact = self.impact_analyzer.analyze("protocol/endpoints.yaml")

        # 记录变更
        ch = ChangeRecord(
            change_id=f"CHG-AMEND-{amendment_id}",
            change_type=ChangeType.PROTOCOL_AMEND,
            triggered_by=triggered_by,
            triggered_by_role="Sponsor",
            reference_id=amendment_id,
            description=description,
            reason=f"Protocol Amendment: {description}",
            impact_type=ImpactType.FULL_PIPELINE,
            requires_re_approval=True,
        )

        ch.impacted_stages = [
            StageImpact(stage=s, impacted=True, requires_re_execution=True,
                        requires_re_approval=(s != "sdtm_programming"
                                               and s != "adam_programming"
                                               and s != "tfl_programming"))
            for s in impact.affected_stages
        ]

        self.change_log.append(ch)

        # 版本升级
        earliest = self.impact_analyzer.earliest_affected_stage("protocol/endpoints.yaml")
        if earliest and self.version_manager:
            for f in impact.direct_impact + impact.cascade_impact:
                self.version_manager.bump(f, VersionBump.MAJOR, ch.change_id, triggered_by)

        return {
            "status": "amendment_analyzed",
            "change_id": ch.change_id,
            "impact": {
                "affected_files": impact.total_affected_files,
                "affected_stages": impact.affected_stages,
                "earliest_stage": earliest,
                "full_restart": impact.requires_full_pipeline_restart,
            },
            "action": f"Re-run pipeline from stage: {earliest}",
        }

    # ── Helpers ────────────────────────────────────────────────

    def _get_executor(self, stage_name: str):
        executor_name = STAGE_EXECUTOR_MAP.get(stage_name)
        if executor_name and executor_name in self.executors:
            return self.executors[executor_name]
        return self.executors.get("ProtocolSAPAgent")  # fallback

    def _create_arbitration_cases(self, stage: str,
                                   reviewer_report) -> list[ArbitrationCase]:
        cases = []
        for issue in reviewer_report.get_critical_and_major():
            case = ArbitrationCase(
                arbitration_id=f"ARB-{stage}-{len(cases)+1:03d}",
                stage=stage, severity=issue.severity,
                rounds_attempted=reviewer_report.review_round,
                contested_item=issue.location,
                reviewer_position={
                    "value": issue.finding, "rationale": issue.recommendation,
                    "standard_ref": issue.standard_reference,
                },
                authoritative_reference=issue.standard_reference,
            )
            self.arbitration_history.add(case)
            cases.append(case)
        return cases

    def status_report(self) -> dict[str, Any]:
        return {
            **self.state.summary(),
            "executors": list(self.executors.keys()),
            "reviewer": f"ReviewerAgent ({self.reviewer_agent.model})" if self.reviewer_agent else "DISABLED",
            "checklists": f"{len(GATE_CHECKLISTS)} gates",
            "changes_tracked": len(self.change_log),
            "arbitrations": self.arbitration_history.get_stats(),
        }

    def register_tool(self, name: str, fn: Callable) -> None:
        self.tool_registry[name] = fn
        for executor in self.executors.values():
            executor.context.tool_registry = self.tool_registry
        if self.reviewer_agent:
            self.reviewer_agent.context.tool_registry = self.tool_registry


def _timestamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
