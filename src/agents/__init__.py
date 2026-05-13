"""
AI Agents for Clinical Statistical Programming — v2.1

Architecture:
  3 Executor Agents (stage-specialized, deep focus):
    · ProtocolSAPAgent       — Protocol + SAP + CRF Design
    · DataStandardsAgent     — SDTM + ADaM (CDISC precision core)
    · TFLQCSubmissionAgent   — TFL + QC + Submission

  1 Reviewer Agent (independent cross-review):
    · ReviewerAgent          — Different model, isolated context

  Independent Checklist Layer:
    · stage_checklists.py    — Gate checklists (enforced, not embedded)

Shared:
  base.py              — BaseAgent, Confidence, Severity, ReviewLevel
  review_package.py    — ReviewPackage, ReviewerReport
  arbitration.py       — ArbitrationCase, CrossReviewCycle
"""

from .base import (
    BaseAgent, AgentConfig, AgentContext,
    Confidence, Severity, ReviewLevel, AgentRole,
)
from .main_agent import MainAgent, StageConfig, STAGE_CONFIGS  # kept for backward compat
from .executors import (
    ProtocolSAPAgent, DataStandardsAgent, TFLQCSubmissionAgent,
    STAGE_EXECUTOR_MAP, get_executor_for_stage,
)
from .reviewer_agent import ReviewerAgent
from .stage_checklists import (
    StageChecklist, ChecklistItem, ChecklistItemStatus,
    GATE_CHECKLISTS, get_checklist, validate_checklist_completion,
)
from .review_package import (
    ReviewPackage, ReviewerReport,
    IssueForAttention, HumanDecision, ArbitrationItem,
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
    # Executors (v2.1)
    "ProtocolSAPAgent", "DataStandardsAgent", "TFLQCSubmissionAgent",
    "STAGE_EXECUTOR_MAP", "get_executor_for_stage",
    # Main (backward compat)
    "MainAgent", "StageConfig", "STAGE_CONFIGS",
    # Reviewer
    "ReviewerAgent",
    # Checklists (v2.1)
    "StageChecklist", "ChecklistItem", "ChecklistItemStatus",
    "GATE_CHECKLISTS", "get_checklist", "validate_checklist_completion",
    # Packages
    "ReviewPackage", "ReviewerReport",
    "IssueForAttention", "HumanDecision", "ArbitrationItem",
    "ReviewerIssue", "ConfirmedCorrect", "AmbiguityFlag", "ClarificationNeeded",
    # Arbitration
    "ArbitrationCase", "ArbitrationHistory", "CrossReviewCycle",
    "MAX_REVIEW_ROUNDS",
]
