"""
AI Agents for Clinical Statistical Programming — v3.0

Architecture:
  3 Executor Agents (stage-specialized, deep focus):
    · ProtocolSAPAgent       — Protocol + SAP + CRF Design
    · DataStandardsAgent     — SDTM + ADaM (CDISC precision core)
    · TFLQCSubmissionAgent   — TFL + QC + Submission

Shared:
  base.py              — BaseAgent, Confidence, Severity, ReviewLevel
  executors.py         — Three executor agents + stage mapping

Legacy modules (archived in src/legacy/):
  arbitration.py       — ArbitrationCase, CrossReviewCycle
"""

from .base import (
    BaseAgent, AgentConfig, AgentContext,
    Confidence, Severity, ReviewLevel, AgentRole,
)
from .executors import (
    ProtocolSAPAgent, DataStandardsAgent, TFLQCSubmissionAgent,
    STAGE_EXECUTOR_MAP, get_executor_for_stage,
)

__all__ = [
    # Base
    "BaseAgent", "AgentConfig", "AgentContext",
    "Confidence", "Severity", "ReviewLevel", "AgentRole",
    # Executors
    "ProtocolSAPAgent", "DataStandardsAgent", "TFLQCSubmissionAgent",
    "STAGE_EXECUTOR_MAP", "get_executor_for_stage",
]
