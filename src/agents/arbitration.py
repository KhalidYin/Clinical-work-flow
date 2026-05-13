"""
Arbitration — 当 MainAgent 和 ReviewerAgent 无法达成一致时的
人类仲裁流程 (原则3 和 原则6 的实现)
"""

from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

from .review_package import ArbitrationItem


# ── Arbitration Case ────────────────────────────────────────────


@dataclass
class ArbitrationCase:
    """
    需要人类裁决的争议。

    展示:
      · MainAgent 的主张 + 理由 + 引用的标准
      · ReviewerAgent 的主张 + 理由 + 引用的标准
      · 权威标准参考
      · AI 建议的裁决方向
    """
    arbitration_id: str = ""
    stage: str = ""
    severity: str = ""
    rounds_attempted: int = 0

    # 争议的内容
    contested_item: str = ""

    # 双方的立场 (不暴露推理过程)
    main_agent_position: dict = field(default_factory=dict)
    # { "value": ..., "rationale": ..., "standard_ref": ..., "confidence": ... }

    reviewer_position: dict = field(default_factory=dict)
    # { "value": ..., "rationale": ..., "standard_ref": ..., "confidence": ... }

    # 帮助人类裁决的上下文
    authoritative_reference: str = ""   # 最权威的标准来源
    impact_assessment: str = ""         # 不同裁决方向的影响
    ai_recommendation: str = ""         # AI 的推荐方向

    # 裁决结果
    human_decision: str = ""            # "main" | "reviewer" | "custom"
    custom_value: Any = None
    decided_by: str = ""
    decided_at: str = ""
    rationale: str = ""

    @property
    def is_resolved(self) -> bool:
        return self.human_decision != "" and self.decided_by != ""

    def resolve(self, decision: str, decided_by: str,
                rationale: str = "", custom_value: Any = None) -> None:
        self.human_decision = decision
        self.decided_by = decided_by
        self.decided_at = datetime.now(timezone.utc).isoformat()
        self.rationale = rationale
        if custom_value is not None:
            self.custom_value = custom_value

    def display_for_human(self) -> dict[str, Any]:
        """生成人类仲裁界面所需的数据"""
        return {
            "arbitration_id": self.arbitration_id,
            "stage": self.stage,
            "severity": self.severity,
            "contested_item": self.contested_item,
            "main_agent": {
                "model": "claude-opus-4-7",
                "position": self.main_agent_position.get("value"),
                "rationale": self.main_agent_position.get("rationale"),
                "standard_reference": self.main_agent_position.get("standard_ref"),
            },
            "reviewer_agent": {
                "model": "claude-sonnet-4-6",
                "position": self.reviewer_position.get("value"),
                "rationale": self.reviewer_position.get("rationale"),
                "standard_reference": self.reviewer_position.get("standard_ref"),
            },
            "authoritative_reference": self.authoritative_reference,
            "impact_assessment": self.impact_assessment,
            "ai_recommendation": self.ai_recommendation,
            "decision_options": ["main", "reviewer", "custom"],
        }


# ── Arbitration History ─────────────────────────────────────────


@dataclass
class ArbitrationHistory:
    """
    仲裁历史知识库。
    用于防止重复争议 — 下次遇到类似情况可以引用历史裁决。
    但不自动应用 (每个案例仍然需要人类判断)。
    """
    cases: list[ArbitrationCase] = field(default_factory=list)

    def add(self, case: ArbitrationCase) -> None:
        self.cases.append(case)

    def search(self, query: str) -> list[ArbitrationCase]:
        """搜索相关历史裁决"""
        return [c for c in self.cases
                if query.lower() in c.contested_item.lower()
                or query.lower() in c.stage.lower()]

    def get_stats(self) -> dict[str, Any]:
        resolved = [c for c in self.cases if c.is_resolved]
        return {
            "total_cases": len(self.cases),
            "resolved": len(resolved),
            "pending": len(self.cases) - len(resolved),
            "main_agent_wins": sum(1 for c in resolved if c.human_decision == "main"),
            "reviewer_wins": sum(1 for c in resolved if c.human_decision == "reviewer"),
            "custom_decisions": sum(1 for c in resolved if c.human_decision == "custom"),
        }


# ── 跨审阅轮次管理 ──────────────────────────────────────────────


MAX_REVIEW_ROUNDS = 2


@dataclass
class CrossReviewCycle:
    """
    管理 MainAgent ↔ ReviewerAgent 的审阅循环。

    流程:
      MainAgent 产物 → Reviewer 审阅
      → 有 Critical/Major → MainAgent 修复 → Reviewer 重审
      → 最多 2 轮
      → 2 轮后仍有未解决 → 触发 Arbitration
    """
    stage: str
    max_rounds: int = MAX_REVIEW_ROUNDS
    rounds_completed: int = 0
    issues_resolved: int = 0
    issues_remaining: int = 0

    def can_continue(self) -> bool:
        return self.rounds_completed < self.max_rounds and self.issues_remaining > 0

    def needs_arbitration(self) -> bool:
        return (self.rounds_completed >= self.max_rounds
                and self.issues_remaining > 0)

    def status_summary(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "rounds": self.rounds_completed,
            "max_rounds": self.max_rounds,
            "issues_resolved": self.issues_resolved,
            "issues_remaining": self.issues_remaining,
            "needs_arbitration": self.needs_arbitration(),
            "status": ("passed" if not self.needs_arbitration() and self.issues_remaining == 0
                       else "arbitration_needed" if self.needs_arbitration()
                       else "in_progress"),
        }
