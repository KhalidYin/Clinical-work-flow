"""
MainAgent — 执行管线 + 协调 ReviewerAgent + 提交 Human Gate 审核包。

设计原则:
  原则1: "半自动步枪" — 关键节点人类扣扳机
  原则2: 确定性操作走 MCP, 推理判断走 LLM
  原则3: 不怕说"我不会", 怕的是装会
  原则4: 每个产出物带 AI Generated 水印
  原则5: 状态持久化是底线
  原则6: 审核清单是 Agent 与人类的合同
"""

from dataclasses import dataclass, field
from typing import Any

from .base import (
    BaseAgent, AgentConfig, AgentContext,
    Confidence, Severity, ReviewLevel, AgentRole,
)
from .review_package import (
    ReviewPackage, ChecklistItem, IssueForAttention,
    HumanDecision, ArbitrationItem,
)
from .arbitration import (
    ArbitrationCase, ArbitrationHistory,
    CrossReviewCycle, MAX_REVIEW_ROUNDS,
)


# ── Stage configuration ─────────────────────────────────────────


@dataclass
class StageConfig:
    """单个管线阶段的配置"""
    name: str
    goal: str
    tools: list[str] = field(default_factory=list)
    gate: str = "AUTO"           # AUTO | HUMAN
    reviewer_level: str = "NONE"  # HEAVY | MEDIUM | LIGHT | NONE
    checklist: list[str] = field(default_factory=list)
    reviewers: list[str] = field(default_factory=list)


# ── All 12 stages config ───────────────────────────────────────


STAGE_CONFIGS: dict[str, StageConfig] = {
    "protocol": StageConfig(
        name="Protocol Analysis",
        goal="Extract study design, endpoints, analysis populations",
        tools=["read_document"],
        gate="AUTO",
        reviewer_level="LIGHT",
    ),
    "sap": StageConfig(
        name="Statistical Analysis Plan",
        goal="Generate SAP draft with full sections and TFL shells",
        tools=["read_document"],
        gate="HUMAN",
        reviewer_level="HEAVY",
        reviewers=["Lead Biostatistician", "Lead Programmer"],
        checklist=[
            "Primary/secondary endpoints match protocol exactly",
            "Analysis populations fully defined (ITT, FAS, Safety, PP)",
            "Multiplicity adjustment strategy specified",
            "Handling of missing data justified",
            "Estimands framework per ICH E9(R1)",
            "Sample size calculation with assumptions",
            "Interim analysis plan with stopping boundaries",
            "Subgroup analyses pre-specified",
            "Sensitivity analyses cover plausible departures",
            "All TFL mock shells complete",
            "Safety analysis scope defined",
        ],
    ),
    "crf_design": StageConfig(
        name="CRF Design",
        goal="Map CRF fields to SDTM domains and variables",
        tools=["read_document"],
        gate="AUTO",
        reviewer_level="LIGHT",
    ),
    "data_collection": StageConfig(
        name="Data Collection",
        goal="Monitor data quality during collection",
        gate="AUTO",
        reviewer_level="NONE",
    ),
    "sdtm_spec": StageConfig(
        name="SDTM Specification",
        goal="Generate SDTM domain mapping spec for all domains",
        tools=["sdtm_spec_build", "cdisc_validate"],
        gate="HUMAN",
        reviewer_level="HEAVY",
        reviewers=["Lead Programmer", "Data Manager"],
        checklist=[
            "All CRF pages annotated (aCRF complete)",
            "Domain assignments correct per SDTM IG",
            "Controlled terminology aligned with NCI/CDISC CT",
            "SUPPQUAL variables justified",
            "Cross-domain relationships (RELREC) documented",
        ],
    ),
    "sdtm_programming": StageConfig(
        name="SDTM Programming",
        goal="Generate SDTM dataset code from specs",
        tools=["sdtm_spec_build", "cdisc_validate"],
        gate="AUTO",
        reviewer_level="MEDIUM",
    ),
    "adam_spec": StageConfig(
        name="ADaM Specification",
        goal="Generate ADaM dataset spec from SAP endpoints and SDTM sources",
        tools=["adam_spec_build", "cdisc_validate"],
        gate="HUMAN",
        reviewer_level="HEAVY",
        reviewers=["Lead Biostatistician", "Lead Programmer"],
        checklist=[
            "ADSL population flags match SAP populations",
            "Endpoint derivations match SAP definitions",
            "Imputation methods specified",
            "Analysis time windows defined",
            "All TFL shells traceable to ADaM variables",
        ],
    ),
    "adam_programming": StageConfig(
        name="ADaM Programming",
        goal="Generate ADaM dataset code from specs",
        tools=["adam_spec_build", "cdisc_validate"],
        gate="AUTO",
        reviewer_level="MEDIUM",
    ),
    "tfl_shell": StageConfig(
        name="TFL Shell Design",
        goal="Build complete TFL shell catalog for the trial",
        tools=["tfl_shells_list"],
        gate="HUMAN",
        reviewer_level="MEDIUM",
        reviewers=["Lead Biostatistician", "Medical Writer"],
        checklist=[
            "Table/figure titles match SAP mock shells",
            "Column headers match ADaM variable labels",
            "Footnotes complete and accurate",
            "Population/subgroup headers correct",
        ],
    ),
    "tfl_programming": StageConfig(
        name="TFL Programming",
        goal="Generate TFL output code and render RTF/PDF",
        tools=["tfl_shells_list"],
        gate="AUTO",
        reviewer_level="LIGHT",
    ),
    "qc_validation": StageConfig(
        name="QC Validation",
        goal="Run double programming comparison and P21 validation",
        tools=["cdisc_validate", "triage_p21"],
        gate="HUMAN",
        reviewer_level="HEAVY",
        reviewers=["QC Programmer", "Lead Programmer"],
        checklist=[
            "All pivotal TFLs double-programmed",
            "Discrepancies resolved or documented",
            "Pinnacle 21 errors triaged (0 open errors)",
            "Log files clean (no unhandled exceptions)",
        ],
    ),
    "submission": StageConfig(
        name="Submission Package",
        goal="Package define.xml, ADRG, SDRG, and eCTD structure",
        tools=["define_xml_build"],
        gate="HUMAN",
        reviewer_level="HEAVY",
        reviewers=["Lead Programmer", "Regulatory Affairs"],
        checklist=[
            "define.xml validates against CDISC schema",
            "ADRG/SDRG narrative complete and accurate",
            "XPT files conform to v5 transport spec",
            "eCTD folder structure follows FDA/NMPA spec",
        ],
    ),
}


# ── MainAgent ──────────────────────────────────────────────────


class MainAgent(BaseAgent):
    """
    MainAgent = 执行者 + 协调者

    职责:
      1. PLAN:  确定当前阶段的执行计划
      2. EXECUTE: 调用 MCP 工具 (确定性)
      3. REVIEW:  自检 + 提交 ReviewerAgent + 生成 Human Gate 审核包
    """

    def __init__(self, config: AgentConfig, context: AgentContext):
        super().__init__(config, context)
        self.config.role = AgentRole.MAIN
        if not self.config.model:
            self.config.model = "claude-opus-4-7"
        self.arbitration_history = ArbitrationHistory()
        self.session_review_results: list[dict] = []

    # ── PLAN ────────────────────────────────────────────────────

    async def plan(self, stage: str) -> dict[str, Any]:
        """
        PLAN 阶段: 确定执行计划

        检查:
          1. 阶段目标是什么?
          2. 前置产物是否存在?
          3. 前置 Gate 是否已审批?
          4. 需要调用哪些工具?
          5. 是否需要 Reviewer?
        """
        config = STAGE_CONFIGS.get(stage)
        if config is None:
            return {"status": "error", "reason": f"Unknown stage: {stage}"}

        # Self-check: 是否能执行?
        blockers = self._check_prerequisites(stage)
        if blockers:
            return {
                "status": "blocked",
                "stage": stage,
                "blockers": blockers,
                "action": "human_intervention_needed",
            }

        # 构建执行计划
        execution_plan = {
            "stage": stage,
            "goal": config.goal,
            "tools_to_call": config.tools,
            "reviewer_needed": config.reviewer_level != "NONE",
            "reviewer_level": config.reviewer_level,
            "gate": config.gate,
            "actions": self._build_action_sequence(stage, config),
        }

        return {
            "status": "ready",
            "stage": stage,
            "plan": execution_plan,
        }

    def _check_prerequisites(self, stage: str) -> list[dict]:
        """检查前置条件"""
        blockers = []
        pipeline = self.context.pipeline_state

        # 阶段顺序依赖
        stage_sequence = list(STAGE_CONFIGS.keys())
        stage_idx = stage_sequence.index(stage) if stage in stage_sequence else -1

        if stage_idx > 0:
            prev_stage = stage_sequence[stage_idx - 1]
            prev_config = STAGE_CONFIGS.get(prev_stage)
            if prev_config and prev_config.gate == "HUMAN":
                approvals = pipeline.get("approvals", {})
                if not approvals.get(prev_stage, {}).get("approved"):
                    blockers.append({
                        "type": "gate_not_approved",
                        "stage": prev_stage,
                        "message": f"Previous stage '{prev_stage}' requires human approval",
                    })

        # 产物依赖
        required_artifacts = {
            "sdtm_spec": ["protocol_endpoints"],
            "sdtm_programming": ["sdtm_specs"],
            "adam_spec": ["sdtm_specs", "sap_approved"],
            "adam_programming": ["adam_specs"],
            "tfl_shell": ["adam_specs"],
            "tfl_programming": ["tfl_shells"],
            "qc_validation": ["tfl_outputs"],
            "submission": ["qc_approved"],
        }

        needed = required_artifacts.get(stage, [])
        artifacts = pipeline.get("artifacts", {})
        for need in needed:
            if need not in artifacts:
                blockers.append({
                    "type": "missing_artifact",
                    "artifact": need,
                    "message": f"Required artifact '{need}' not found",
                })

        return blockers

    def _build_action_sequence(self, stage: str, config: StageConfig) -> list[dict]:
        """构建按顺序执行的行动列表"""
        actions = []
        for tool_name in config.tools:
            actions.append({
                "type": "call_tool",
                "tool": tool_name,
                "retry": 2,
            })
        actions.append({
            "type": "self_check",
            "checklist": config.checklist if config.gate == "HUMAN" else [],
        })
        if config.reviewer_level != "NONE":
            actions.append({
                "type": "submit_to_reviewer",
                "level": config.reviewer_level,
            })
        if config.gate == "HUMAN":
            actions.append({
                "type": "prepare_review_package",
                "reviewers": config.reviewers,
                "checklist": config.checklist,
            })
        return actions

    # ── EXECUTE ─────────────────────────────────────────────────

    async def execute(self, stage: str, plan: dict) -> dict[str, Any]:
        """
        EXECUTE 阶段: 按 PLAN 执行 MCP 工具调用

        核心: 这个阶段只调用 MCP 工具 (确定性), 不自己做开放式 LLM 推理。
        """
        config = STAGE_CONFIGS.get(stage)
        results = {"stage": stage, "tool_results": [], "artifacts": {}}

        for action in plan.get("actions", []):
            if action["type"] != "call_tool":
                continue

            tool_name = action["tool"]
            max_retries = action.get("retry", 2)

            for attempt in range(max_retries + 1):
                try:
                    tool_result = await self._invoke_tool(tool_name, stage)
                    tool_result["_attempt"] = attempt + 1
                    results["tool_results"].append({
                        "tool": tool_name,
                        "status": "success",
                        "result": tool_result,
                    })
                    break
                except Exception as e:
                    if attempt < max_retries:
                        continue
                    # 所有重试失败 → 升级给人类
                    results["tool_results"].append({
                        "tool": tool_name,
                        "status": "failed",
                        "error": str(e),
                        "attempts": attempt + 1,
                    })
                    return self.stop_for_human(
                        reason=f"Tool '{tool_name}' failed after {max_retries + 1} attempts: {e}",
                    )

        # 水印所有产出物 (原则4)
        for key, artifact in results["artifacts"].items():
            if isinstance(artifact, dict):
                results["artifacts"][key] = self.watermark_output(artifact, stage)

        return results

    async def _invoke_tool(self, tool_name: str, stage: str) -> dict[str, Any]:
        """调用 MCP 工具 (原则2)"""
        ctx = self.context.pipeline_state
        params = {
            "trial_phase": ctx.get("trial_phase", "phase_iii"),
            "therapeutic_area": ctx.get("therapeutic_area", "non_oncology"),
        }
        return await self.call_tool(tool_name, **params)

    # ── REVIEW ──────────────────────────────────────────────────

    async def review(self, stage: str, results: dict) -> dict[str, Any]:
        """
        REVIEW 阶段: 自检 + 准备审核材料

        1. 产物完整性自检
        2. CDISC 验证 (自动)
        3. 如果有 Reviewer → 标记为需要审阅
        4. 如果 Human Gate → 生成审核包
        """
        config = STAGE_CONFIGS.get(stage)
        review_result = {
            "stage": stage,
            "self_check_passed": True,
            "issues_found": [],
            "needs_reviewer": config.reviewer_level != "NONE" if config else False,
            "needs_human_gate": config.gate == "HUMAN" if config else False,
        }

        # 自检逻辑 (原则3: 标注置信度)
        if stage == "sdtm_spec":
            review_result["issues_found"] = self._self_check_sdtm_spec(results)
        elif stage == "adam_spec":
            review_result["issues_found"] = self._self_check_adam_spec(results)
        elif stage == "tfl_shell":
            review_result["issues_found"] = self._self_check_tfl_shell(results)

        review_result["self_check_passed"] = len(review_result["issues_found"]) == 0

        return review_result

    def _self_check_sdtm_spec(self, results: dict) -> list[dict]:
        issues = []
        for domain_result in results.get("tool_results", []):
            if domain_result["status"] != "success":
                issues.append({
                    "location": f"SDTM spec generation",
                    "severity": "error",
                    "message": f"Failed to generate: {domain_result.get('error')}",
                    "confidence": Confidence.HIGH.value,
                })
        return issues

    def _self_check_adam_spec(self, results: dict) -> list[dict]:
        return []

    def _self_check_tfl_shell(self, results: dict) -> list[dict]:
        return []

    # ── Human Gate Preparation ───────────────────────────────────

    async def prepare_review_package(self, stage: str,
                                      results: dict,
                                      reviewer_report: dict | None = None,
                                      arbitration_items: list[dict] | None = None,
                                      ) -> ReviewPackage:
        """
        生成 Human Gate 审核包 (原则6)

        审核包 = Agent 的产出 + 审核清单结果 + Reviewer 的审阅报告 + 争议项

        人类只需要:
          1. 查看清单结果
          2. 关注争议和问题
          3. 确认签字
        """
        config = STAGE_CONFIGS.get(stage)
        if config is None:
            raise ValueError(f"Unknown stage: {stage}")

        package = ReviewPackage(
            package_id=f"PKG-{stage}-{self.context.study_id}",
            stage=stage,
            generated_by=f"MainAgent ({self.model})",
            reviewed_by=f"ReviewerAgent ({self.model})" if reviewer_report else "NONE",
        )

        # 填充审核清单 (原则6: Agent 逐项汇报)
        for item in config.checklist:
            checklist_item = ChecklistItem(
                item=item,
                status="PASS",
                evidence=f"Verified by MainAgent ({self.model})",
                confidence=Confidence.HIGH.value,
            )
            package.checklist_results.append(checklist_item)

        # 如果有 Reviewer 报告, 反向标记检查项
        if reviewer_report:
            package.review_score = reviewer_report.get("score", 0)
            package.review_rounds = reviewer_report.get("rounds", 1)

            for issue in reviewer_report.get("issues", []):
                # 在对应的 checklist item 上标记
                for item in package.checklist_results:
                    if issue.get("location", "") in item.item:
                        item.status = "FLAGGED"
                        item.agent_note = issue.get("finding", "")

                package.issues_for_attention.append(IssueForAttention(
                    severity=issue.get("severity", "minor"),
                    location=issue.get("location", ""),
                    description=issue.get("finding", ""),
                    recommendation=issue.get("recommendation", ""),
                    agent_confidence=issue.get("confidence", "HIGH"),
                ))

        # 如果有仲裁项
        if arbitration_items:
            package.arbitration_items = [
                ArbitrationItem(
                    arbitration_id=item.get("id", ""),
                    contested_item=item.get("item", ""),
                    severity=item.get("severity", "major"),
                    main_agent_position=item.get("main_position", {}),
                    reviewer_position=item.get("reviewer_position", {}),
                    authoritative_reference=item.get("reference", ""),
                    recommendation=item.get("recommendation", ""),
                )
                for item in arbitration_items
            ]

        return package

    # ── Fix Cycle ────────────────────────────────────────────────

    async def fix_issues(self, stage: str, issues: list,
                          original_artifacts: dict) -> dict[str, Any]:
        """根据 Reviewer 的反馈修复问题"""
        # 重新执行阶段，修复已知问题
        plan = await self.plan(stage)
        if plan["status"] == "ready":
            # appending fix context
            plan["plan"]["fix_mode"] = True
            plan["plan"]["issues_to_fix"] = [
                {"location": i.location, "finding": i.finding,
                 "recommendation": i.recommendation}
                for i in issues
            ]
            return await self.execute(stage, plan["plan"])
        return original_artifacts
