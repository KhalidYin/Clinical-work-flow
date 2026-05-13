"""
ReviewPackage, ReviewerReport 等核心数据结构。
"""

from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

from .base import Severity, Confidence, ReviewLevel


# ── Review Package (MainAgent 提交给人类的审核包) ──────────────


@dataclass
class ChecklistItem:
    """审核清单中的单个检查项"""
    item: str
    status: str  # PASS | FAIL | FLAGGED
    evidence: str = ""
    confidence: str = "HIGH"
    agent_note: str = ""


@dataclass
class IssueForAttention:
    """有人类的关注的问题"""
    severity: str  # CRITICAL | MAJOR | MINOR
    location: str  # "{dataset}.{variable}" or "{tfl_id}.{row}/{col}"
    description: str
    recommendation: str = ""
    agent_confidence: str = "HIGH"


@dataclass
class HumanDecision:
    """需要人类裁决的选项"""
    question: str
    options: list[str]
    recommended: str = ""
    context: str = ""


@dataclass
class ArbitrationItem:
    """双 Agent 争议项"""
    arbitration_id: str
    contested_item: str
    severity: str
    main_agent_position: dict
    reviewer_position: dict
    authoritative_reference: str
    recommendation: str = ""


@dataclass
class ReviewPackage:
    """
    准备提交给人类审核的结构化包。
    原则6: 审核清单是 Agent 和人类之间的"合同"。
    """
    package_id: str = ""
    stage: str = ""
    generated_by: str = ""       # "MainAgent (claude-opus-4-7)"
    reviewed_by: str = ""        # "ReviewerAgent (claude-sonnet-4-6)"
    review_score: float = 0.0    # 0-100
    review_rounds: int = 0

    checklist_results: list[ChecklistItem] = field(default_factory=list)
    issues_for_attention: list[IssueForAttention] = field(default_factory=list)
    requires_human_decision: list[HumanDecision] = field(default_factory=list)
    arbitration_items: list[ArbitrationItem] = field(default_factory=list)

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    human_approved: bool = False
    approved_by: str = ""
    approved_at: str = ""

    def approve(self, reviewer: str) -> None:
        self.human_approved = True
        self.approved_by = reviewer
        self.approved_at = datetime.now(timezone.utc).isoformat()

    def has_critical(self) -> bool:
        return any(i.severity == "critical" for i in self.issues_for_attention)

    def has_arbitrations(self) -> bool:
        return len(self.arbitration_items) > 0


# ── Reviewer Report (ReviewerAgent 的独立审阅报告) ─────────────


@dataclass
class ReviewerIssue:
    """Reviewer 发现的问题"""
    issue_id: str
    location: str
    severity: str
    finding: str
    standard_reference: str = ""
    recommendation: str = ""
    confidence: str = "HIGH"


@dataclass
class ConfirmedCorrect:
    """Reviewer 确认正确的项目"""
    area: str
    items_verified: int = 0
    evidence: str = ""


@dataclass
class AmbiguityFlag:
    """Reviewer 标记的歧义"""
    location: str
    concern: str
    preferred_interpretation: str = ""


@dataclass
class ClarificationNeeded:
    """Reviewer 需要澄清的问题"""
    question: str
    context: str = ""


@dataclass
class ReviewerReport:
    """ReviewerAgent 的独立审阅报告"""
    review_id: str = ""
    stage: str = ""
    review_level: str = ReviewLevel.MEDIUM.value
    reviewer_model: str = ""
    review_score: float = 0.0
    review_round: int = 0

    # 审阅覆盖
    coverage: dict = field(default_factory=lambda: {
        "total_items": 0, "reviewed": 0, "sample_rate_pct": 100
    })

    # 审阅结果
    issues: list[ReviewerIssue] = field(default_factory=list)
    confirmed_correct: list[ConfirmedCorrect] = field(default_factory=list)
    ambiguity_flags: list[AmbiguityFlag] = field(default_factory=list)
    requires_clarification: list[ClarificationNeeded] = field(default_factory=list)

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def has_critical(self) -> bool:
        return any(i.severity == "critical" for i in self.issues)

    def has_major(self) -> bool:
        return any(i.severity == "major" for i in self.issues)

    def has_critical_or_major(self) -> bool:
        return self.has_critical() or self.has_major()

    def get_critical_and_major(self) -> list[ReviewerIssue]:
        return [i for i in self.issues if i.severity in ("critical", "major")]

    def summary(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "stage": self.stage,
            "score": self.review_score,
            "critical": sum(1 for i in self.issues if i.severity == "critical"),
            "major": sum(1 for i in self.issues if i.severity == "major"),
            "minor": sum(1 for i in self.issues if i.severity == "minor"),
            "confirmed_areas": len(self.confirmed_correct),
            "ambiguities": len(self.ambiguity_flags),
        }
