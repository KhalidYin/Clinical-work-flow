"""
AI Agents for Clinical Statistical Programming — v2.0

Architecture:
  MainAgent    (main_agent.py)     — Executor + Coordinator
  ReviewerAgent (reviewer_agent.py) — Independent Cross-Reviewer

Shared:
  base.py              — BaseAgent, Confidence, Severity, ReviewLevel
  review_package.py    — ReviewPackage, ReviewerReport 数据结构
  arbitration.py       — ArbitrationCase, CrossReviewCycle
"""

from .base import (
    BaseAgent, AgentConfig, AgentContext,
    Confidence, Severity, ReviewLevel, AgentRole,
)
from .main_agent import MainAgent, StageConfig, STAGE_CONFIGS
from .reviewer_agent import ReviewerAgent
from .review_package import (
    ReviewPackage, ReviewerReport,
    ChecklistItem, IssueForAttention, HumanDecision, ArbitrationItem,
    ReviewerIssue, ConfirmedCorrect, AmbiguityFlag, ClarificationNeeded,
)
from .arbitration import (
    ArbitrationCase, ArbitrationHistory, CrossReviewCycle,
    MAX_REVIEW_ROUNDS,
)

__all__ = [
    # Base
    "BaseAgent", "AgentConfig", "AgentContext",
    "Confidence", "Severity", "ReviewLevel", "AgentRole",
    # Main
    "MainAgent", "StageConfig", "STAGE_CONFIGS",
    # Reviewer
    "ReviewerAgent",
    # Packages
    "ReviewPackage", "ReviewerReport",
    "ChecklistItem", "IssueForAttention", "HumanDecision", "ArbitrationItem",
    "ReviewerIssue", "ConfirmedCorrect", "AmbiguityFlag", "ClarificationNeeded",
    # Arbitration
    "ArbitrationCase", "ArbitrationHistory", "CrossReviewCycle",
    "MAX_REVIEW_ROUNDS",
]
