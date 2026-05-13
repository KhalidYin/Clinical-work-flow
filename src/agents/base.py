"""
Agent base classes and shared types for the dual-agent architecture.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable
from datetime import datetime, timezone


# ── Shared Enums ─────────────────────────────────────────────────


class Confidence(StrEnum):
    """置信度标注系统 — 原则3: Agent 不怕说"我不会" """
    HIGH = "high"       # 基于明确的 CDISC 标准条文
    MEDIUM = "medium"   # 基于常规实践推断
    LOW = "low"         # 不确定, 必须停顿请求人类指导


class Severity(StrEnum):
    """问题严重程度"""
    CRITICAL = "critical"  # 数据完整性 / 法规不合规 / 安全影响 → BLOCK
    MAJOR = "major"        # 可能导致分析错误 / P21 Error → FIX
    MINOR = "minor"        # 格式化 / 命名 / 最佳实践 → FLAG


class ReviewLevel(StrEnum):
    """审阅深度级别"""
    HEAVY = "heavy"    # 100% 全覆盖审阅, 逐项核对 CDISC 标准
    MEDIUM = "medium"  # 全覆盖, 抽样检查衍生逻辑
    LIGHT = "light"    # 抽样审阅 20-30%, 发现问题升级


class AgentRole(StrEnum):
    """Agent 角色"""
    MAIN = "main"          # 执行者
    REVIEWER = "reviewer"  # 审阅者


# ── Base Agent ──────────────────────────────────────────────────


@dataclass
class AgentConfig:
    """Agent 配置"""
    name: str
    role: AgentRole
    model: str = "claude-opus-4-7"
    max_retries: int = 2
    system_prompt_template: str = ""


@dataclass
class AgentContext:
    """Agent 运行上下文 (session 级别)"""
    study_id: str
    pipeline_state: dict[str, Any] = field(default_factory=dict)
    tool_registry: dict[str, Callable] = field(default_factory=dict)
    stage_history: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


class BaseAgent:
    """所有 Agent 的基类"""

    def __init__(self, config: AgentConfig, context: AgentContext):
        self.config = config
        self.context = context

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def model(self) -> str:
        return self.config.model

    async def call_tool(self, tool_name: str, **kwargs) -> dict[str, Any]:
        """调用 MCP 工具 (确定性, 可审计)"""
        tool = self.context.tool_registry.get(tool_name)
        if tool is None:
            raise ValueError(f"Tool '{tool_name}' not found in registry")
        return tool(**kwargs)

    def annotate_confidence(self, conclusion: str, evidence: list[str]) -> Confidence:
        """标注置信度"""
        if not evidence:
            return Confidence.LOW
        if len(evidence) >= 2 and all("CDISC" in e or "ICH" in e or "FDA" in e for e in evidence):
            return Confidence.HIGH
        if len(evidence) >= 1:
            return Confidence.MEDIUM
        return Confidence.LOW

    def watermark_output(self, output: dict, stage: str) -> dict:
        """原则4: 每个产品物带 AI Generated 水印"""
        output["_meta"] = {
            "generated_by": f"{self.name} ({self.model})",
            "role": self.config.role.value,
            "stage": stage,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ai_generated": True,
            "human_approved": False,
        }
        return output

    def stop_for_human(self, reason: str, options: list[str] | None = None) -> dict:
        """原则3: 不确定时停止并请求人类指导"""
        return {
            "action": "STOP",
            "agent": self.name,
            "reason": reason,
            "options": options or [],
            "confidence": Confidence.LOW.value,
        }

    async def plan(self, stage: str) -> dict[str, Any]:
        raise NotImplementedError

    async def execute(self, stage: str, plan: dict) -> dict[str, Any]:
        raise NotImplementedError

    async def review(self, stage: str, results: dict) -> dict[str, Any]:
        raise NotImplementedError
