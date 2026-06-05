"""
v2.1 三 Executor Agent 架构。

设计理由:
  · 恢复 5 Agent 的领域深度优势
  · 每个 Executor 的 system prompt 8-12K tokens (深度专注)
  · vs 单体 MainAgent 的 25K+ (注意分散)

Executor 1: ProtocolSAPAgent      — Protocol + SAP + 方案级别决策
Executor 2: DataStandardsAgent   — SDTM + ADaM (CDISC 精确核心)
Executor 3: TFLQCSubmissionAgent — TFL + QC + Submission (输出+法规)
"""

from typing import Any

from .base import (
    BaseAgent, AgentConfig, AgentContext,
    Confidence, Severity, ReviewLevel, AgentRole,
)
from ..legacy.arbitration import ArbitrationHistory


# ── Executor 1: ProtocolSAPAgent ───────────────────────────────


class ProtocolSAPAgent(BaseAgent):
    """
    专注: Protocol 解析 + SAP 生成 + CRF 设计

    领域深度:
      · ICH E3 (CSR 结构)
      · ICH E9 / E9(R1) (统计原则 + Estimands)
      · Clinical endpoint classification
      · Sample size methodology
      · Analysis population definitions

    对应阶段:
      · protocol (AUTO)
      · sap (HUMAN Gate 1)
      · crf_design (AUTO)
    """

    stages = ["protocol", "sap", "crf_design"]

    def __init__(self, config: AgentConfig, context: AgentContext):
        super().__init__(config, context)
        self.config.role = AgentRole.MAIN
        if not self.config.model:
            self.config.model = "claude-opus-4-7"
        self.arbitration_history = ArbitrationHistory()

    async def plan(self, stage: str) -> dict[str, Any]:
        return {
            "stage": stage,
            "executor": "ProtocolSAPAgent",
            "focus_areas": [
                "Endpoint extraction and classification",
                "SAP section generation per ICH E9/E9(R1)",
                "Estimands framework derivation",
                "Analysis population definition",
                "CRF-to-SDTM pre-mapping",
            ],
        }

    async def execute(self, stage: str, plan: dict) -> dict[str, Any]:
        return {"stage": stage, "executor": self.name, "status": "ready"}

    async def review(self, stage: str, results: dict) -> dict[str, Any]:
        return {"stage": stage, "status": "self_review_complete"}


# ── Executor 2: DataStandardsAgent ─────────────────────────────


class DataStandardsAgent(BaseAgent):
    """
    专注: SDTM + ADaM (CDISC 精确核心)

    领域深度:
      · SDTM v2.0 / SDTMIG v3.4 (所有域 + SUPPQUAL + RELREC)
      · ADaM v2.1 / ADaMIG v1.3 (ADSL + BDS + OCCDS)
      · CDISC Controlled Terminology (NCI Thesaurus)
      · Pinnacle 21 规则引擎
      · define.xml 2.0

    对应阶段:
      · sdtm_spec (HUMAN Gate 2)
      · sdtm_programming (AUTO)
      · adam_spec (HUMAN Gate 3)
      · adam_programming (AUTO)
    """

    stages = ["sdtm_spec", "sdtm_programming", "adam_spec", "adam_programming"]

    def __init__(self, config: AgentConfig, context: AgentContext):
        super().__init__(config, context)
        self.config.role = AgentRole.MAIN
        if not self.config.model:
            self.config.model = "claude-opus-4-7"
        self.arbitration_history = ArbitrationHistory()

    async def plan(self, stage: str) -> dict[str, Any]:
        return {
            "stage": stage,
            "executor": "DataStandardsAgent",
            "focus_areas": [
                "SDTM domain variable mapping per CDISC IG",
                "Controlled terminology alignment (NCI/CDISC CT)",
                "ADaM BDS/OCCDS structure compliance",
                "Derivation logic from SAP endpoint definitions",
                "Cross-domain consistency (RELREC, SUPPQUAL)",
                "Pinnacle 21 pre-validation",
            ],
        }

    async def execute(self, stage: str, plan: dict) -> dict[str, Any]:
        return {"stage": stage, "executor": self.name, "status": "ready"}

    async def review(self, stage: str, results: dict) -> dict[str, Any]:
        return {"stage": stage, "status": "self_review_complete"}


# ── Executor 3: TFLQCSubmissionAgent ───────────────────────────


class TFLQCSubmissionAgent(BaseAgent):
    """
    专注: TFL + QC + Submission (输出 + 法规递交)

    领域深度:
      · TFL Shell design & catalog management
      · SAS/R/Python TFL code generation
      · RTF/PDF output formatting
      · Double programming QC methodology
      · Pinnacle 21 triage & justification
      · define.xml 2.0 + ADRG + SDRG + eCTD structure

    对应阶段:
      · tfl_shell (HUMAN Gate 4)
      · tfl_programming (AUTO)
      · qc_validation (HUMAN Gate 5)
      · submission (HUMAN Gate 6)
    """

    stages = ["tfl_shell", "tfl_programming", "qc_validation", "submission"]

    def __init__(self, config: AgentConfig, context: AgentContext):
        super().__init__(config, context)
        self.config.role = AgentRole.MAIN
        if not self.config.model:
            self.config.model = "claude-opus-4-7"
        self.arbitration_history = ArbitrationHistory()

    async def plan(self, stage: str) -> dict[str, Any]:
        return {
            "stage": stage,
            "executor": "TFLQCSubmissionAgent",
            "focus_areas": [
                "TFL shell to SAP mock shell alignment",
                "Output format compliance (RTF/PDF/XPT)",
                "Double programming discrepancy analysis",
                "P21 finding classification and auto-justification",
                "define.xml schema validation",
                "eCTD Module 5 folder structure",
            ],
        }

    async def execute(self, stage: str, plan: dict) -> dict[str, Any]:
        return {"stage": stage, "executor": self.name, "status": "ready"}

    async def review(self, stage: str, results: dict) -> dict[str, Any]:
        return {"stage": stage, "status": "self_review_complete"}


# ── Stage → Executor mapping ──────────────────────────────────


STAGE_EXECUTOR_MAP: dict[str, str] = {
    "protocol":           "ProtocolSAPAgent",
    "sap":                "ProtocolSAPAgent",
    "crf_design":         "ProtocolSAPAgent",
    "sdtm_spec":          "DataStandardsAgent",
    "sdtm_programming":   "DataStandardsAgent",
    "adam_spec":          "DataStandardsAgent",
    "adam_programming":   "DataStandardsAgent",
    "tfl_shell":          "TFLQCSubmissionAgent",
    "tfl_programming":    "TFLQCSubmissionAgent",
    "qc_validation":      "TFLQCSubmissionAgent",
    "submission":         "TFLQCSubmissionAgent",
}


def get_executor_for_stage(stage: str,
                            config: AgentConfig,
                            context: AgentContext) -> BaseAgent:
    """根据阶段获取对应的 Executor Agent"""
    executor_name = STAGE_EXECUTOR_MAP.get(stage)

    if executor_name == "ProtocolSAPAgent":
        return ProtocolSAPAgent(config, context)
    elif executor_name == "DataStandardsAgent":
        return DataStandardsAgent(config, context)
    elif executor_name == "TFLQCSubmissionAgent":
        return TFLQCSubmissionAgent(config, context)

    raise ValueError(f"No executor mapped for stage: {stage}. "
                     f"Valid stages: {list(STAGE_EXECUTOR_MAP)}")
