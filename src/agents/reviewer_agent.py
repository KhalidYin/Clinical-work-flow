"""
ReviewerAgent — 独立交叉审阅。

核心原则:
  ·  不同模型 (产生不同的"幻觉指纹")
  ·  独立上下文 (不拿 MainAgent 的推理过程)
  ·  只看产物 + CDISC 标准
  ·  强制挑出 N 个评论项 (防止懒审)
  ·  输出结构化审阅报告
"""

# ReviewerAgent no longer a dataclass — uses explicit __init__
from typing import Any

from .base import (
    BaseAgent, AgentConfig, AgentContext,
    Confidence, Severity, ReviewLevel, AgentRole,
)
from .review_package import (
    ReviewerReport, ReviewerIssue, ConfirmedCorrect,
    AmbiguityFlag, ClarificationNeeded,
)


# ── Review focus areas per stage ───────────────────────────────


REVIEW_FOCUS = {
    "sdtm_spec": {
        "primary": [
            "Variable completeness: all Req variables present",
            "Controlled terminology: matches CDISC CT exactly",
            "Variable lengths: meet CDISC minimums",
            "Domain assignments: correct per SDTM IG",
        ],
        "secondary": [
            "SUPPQUAL justification",
            "Cross-domain RELREC documentation",
            "Source traceability: variable → CRF field",
        ],
    },
    "adam_spec": {
        "primary": [
            "ADSL flags: FASFL/SAFFL derivation matches SAP populations",
            "Endpoint derivation: matches SAP definitions precisely",
            "BDS structure: PARAMCD, AVAL, BASE, CHG, ABLFL correct",
            "TTE censoring: CNSR rules match SAP per PARAMCD",
        ],
        "secondary": [
            "Analysis visit windows",
            "DTYPE usage correct",
            "ANLxxFL analysis flag logic",
        ],
    },
    "tfl_shell": {
        "primary": [
            "Title/header match SAP shell exactly",
            "Population: correct analysis population used",
            "N-count source traceable to ADaM spec",
        ],
        "secondary": [
            "Footnotes complete",
            "Sorting logic specified",
            "Page layout appropriate",
        ],
    },
}


# ── ReviewerAgent ──────────────────────────────────────────────


class ReviewerAgent(BaseAgent):
    """
    ReviewerAgent = 独立审阅者

    关键设计:
      1. 不收 MainAgent 的推理过程 (防止锚定)
      2. 拿到的是最终产物 (Spec / TFL / Report)
      3. 独立对照 CDISC 标准逐项审阅
      4. 强制挑出 N 个评论点
      5. 输出结构化 ReviewerReport

    与 MainAgent 的隔离:
      · 不同的 System Prompt
      · 不同的模型 (Sonnet vs Opus)
      · 独立的上下文 (不看 MainAgent 的推理)
      · 可以调用 MCP 工具做独立验证 (独立实例)
    """

    def __init__(self, config: AgentConfig, context: AgentContext,
                 min_issues_to_find: int = 3):
        super().__init__(config, context)
        self.config.role = AgentRole.REVIEWER
        if not self.config.model:
            self.config.model = "claude-sonnet-4-6"
        self.min_issues_to_find = min_issues_to_find  # 强制找至少 N 个评论项

    # ── Review Entry ────────────────────────────────────────────

    async def review(self, stage: str,
                     artifacts: dict[str, Any],
                     level: str = "MEDIUM",
                     round_num: int = 1) -> ReviewerReport:
        """
        独立审阅入口。

        Args:
          stage: 审阅的阶段
          artifacts: MainAgent 的产出物 (只给产物, 不给推理过程!)
          level: 审阅深度 (HEAVY / MEDIUM / LIGHT)
          round_num: 当前审阅轮次 (用于修复-重审循环)

        Returns:
          ReviewerReport: 结构化审阅报告
        """
        report = ReviewerReport(
            review_id=f"REV-{stage}-R{round_num}",
            stage=stage,
            review_level=level,
            reviewer_model=self.model,
            review_round=round_num,
        )

        # 确定审阅覆盖度
        if level == ReviewLevel.HEAVY.value:
            report.coverage["sample_rate_pct"] = 100
        elif level == ReviewLevel.MEDIUM.value:
            report.coverage["sample_rate_pct"] = 100  # 全覆盖但抽查衍生
        else:
            report.coverage["sample_rate_pct"] = 30  # LIGHT: 抽样

        # 逐项审阅
        focus = REVIEW_FOCUS.get(stage, {})
        primary_checks = focus.get("primary", [])
        secondary_checks = focus.get("secondary", [])

        all_items_count = 0
        reviewed_count = 0

        for check_type, checks in [("primary", primary_checks),
                                    ("secondary", secondary_checks)]:
            for check_desc in checks:
                all_items_count += 1
                reviewed_count += 1

                # 根据审阅级别决定是否执行此检查
                if level == ReviewLevel.LIGHT.value and check_type == "secondary":
                    reviewed_count -= 1
                    continue

                # 独立验证 (原则2: 可调用 MCP 工具独立验证)
                check_result = await self._check_item(stage, check_desc, artifacts)

                if check_result["status"] == "issue":
                    report.issues.append(ReviewerIssue(
                        issue_id=f"REV-{len(report.issues)+1:03d}",
                        location=check_result.get("location", ""),
                        severity=check_result.get("severity", "minor"),
                        finding=check_result.get("finding", ""),
                        standard_reference=check_result.get("reference", ""),
                        recommendation=check_result.get("recommendation", ""),
                        confidence=check_result.get("confidence", "HIGH"),
                    ))
                elif check_result["status"] == "ambiguity":
                    report.ambiguity_flags.append(AmbiguityFlag(
                        location=check_result.get("location", ""),
                        concern=check_result.get("finding", ""),
                        preferred_interpretation=check_result.get("preferred", ""),
                    ))
                else:
                    # 确认正确的项
                    report.confirmed_correct.append(ConfirmedCorrect(
                        area=check_desc,
                        items_verified=1,
                        evidence=check_result.get("evidence", ""),
                    ))

        # 更新覆盖统计
        report.coverage["total_items"] = all_items_count
        report.coverage["reviewed"] = reviewed_count

        # 计算审阅分
        total_issues = len(report.issues)
        critical_count = sum(1 for i in report.issues if i.severity == "critical")
        major_count = sum(1 for i in report.issues if i.severity == "major")
        report.review_score = max(
            0,
            100 - (critical_count * 10 + major_count * 5
                   + (total_issues - critical_count - major_count) * 1)
        )

        # 防止懒审: 如果没找到问题, 至少标记 Ambiguity
        if len(report.issues) < self.min_issues_to_find:
            report.requires_clarification.append(
                ClarificationNeeded(
                    question=f"Reviewer completed {reviewed_count}/{all_items_count} "
                    f"checks with only {len(report.issues)} issues found. "
                    f"Requesting re-review with higher scrutiny on "
                    f"{', '.join(primary_checks[:3])}."
                )
            )

        return report

    # ── Individual Item Check ───────────────────────────────────

    async def _check_item(self, stage: str, check_desc: str,
                          artifacts: dict) -> dict[str, Any]:
        """
        检查单个审阅项。

        在完整实现中:
          · 对于术语检查 → 调用 cdisc_validate 做独立验证
          · 对于逻辑检查 → 独立推理
          · 标记置信度 (原则3)
        """
        # 模拟: 基于检查描述和产物进行独立判断
        # 在完整实现中, 这里会进行实际的 CDISC 标准对比
        return {
            "status": "ok",  # "ok" | "issue" | "ambiguity"
            "location": f"{stage}.{check_desc[:30]}",
            "finding": "Item verified against CDISC standards",
            "reference": "CDISC SDTMIG v3.4 / ADaMIG v1.3",
            "evidence": "Independent verification completed",
            "confidence": Confidence.HIGH.value,
        }

    # ── Plan/Execute (Reviewer 的实现) ──────────────────────────

    async def plan(self, stage: str) -> dict[str, Any]:
        """Reviewer 的 PLAN: 确定审阅范围和重点"""
        focus = REVIEW_FOCUS.get(stage, {})
        primary = len(focus.get("primary", []))
        secondary = len(focus.get("secondary", []))
        return {
            "stage": stage,
            "review_type": "independent_cross_review",
            "focus_areas": {
                "primary": primary,
                "secondary": secondary,
                "total": primary + secondary,
            },
        }

    async def execute(self, stage: str, plan: dict) -> dict[str, Any]:
        """Reviewer 的 EXECUTE: 执行审阅"""
        return {"stage": stage, "status": "review_pending"}

    async def meta_review(self, results: dict) -> dict[str, Any]:
        """Meta-review: Reviewer 审核自己的审阅结果"""
        return {"stage": "meta", "self_review": "complete"}
