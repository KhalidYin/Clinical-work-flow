"""
ChangeRecord — 每次变更的完整可审计记录。

设计目标:
  1. FDA 检查时可以逐条追溯
  2. 支持变更影响分析
  3. GxP 合规审计追踪
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class ChangeType(StrEnum):
    """变更类型"""
    PROTOCOL_AMEND = "protocol_amendment"    # 方案修订
    SAP_UPDATE = "sap_update"                # SAP 更新
    HUMAN_REVIEW = "human_review"            # 人工审核返回
    DATA_REFRESH = "data_refresh"            # 数据刷新
    REGULATORY_IR = "regulatory_ir"          # 监管机构信息请求
    REVIEWER_FEEDBACK = "reviewer_feedback"  # ReviewerAgent 发现
    STANDARD_UPDATE = "standard_update"      # CDISC 标准更新
    SELF_FIX = "self_fix"                    # MainAgent 自修复
    ROLLBACK = "rollback"                    # 回退
    PIPELINE_RESTART = "pipeline_restart"    # 管线重启


class ImpactType(StrEnum):
    """影响范围"""
    FILE_LOCAL = "file_local"      # 仅当前文件
    STAGE_LOCAL = "stage_local"   # 仅当前阶段
    DOWNSTREAM = "downstream"     # 下游阶段受影响
    FULL_PIPELINE = "full_pipeline"  # 全管线受影响


@dataclass
class FileChange:
    """单个文件的变更详情"""
    path: str
    old_version: str
    new_version: str
    diff_summary: str = ""  # 变更摘要 (人类可读)
    diff_path: str = ""     # 完整 diff 文件路径


@dataclass
class StageImpact:
    """单个阶段的受影响评估"""
    stage: str
    impacted: bool = False
    reason: str = ""
    files_to_update: list[str] = field(default_factory=list)
    requires_re_execution: bool = False
    requires_re_approval: bool = False


@dataclass
class ChangeRecord:
    """一次变更的完整审计记录"""

    change_id: str
    change_type: str  # ChangeType

    # 触发信息
    triggered_by: str           # 触发人/系统
    triggered_by_role: str      # "Sponsor" | "Biostatistician" | "Lead Programmer" | "ReviewerAgent" | "MainAgent" | "FDA"
    reference_id: str = ""      # 外部引用 (如 "Protocol Amendment #3")

    # 变更内容
    description: str = ""
    reason: str = ""

    # 文件变更
    files_changed: list[FileChange] = field(default_factory=list)

    # 影响范围
    impact_type: str = ImpactType.STAGE_LOCAL
    impacted_stages: list[StageImpact] = field(default_factory=list)

    # 状态
    status: str = "pending"     # pending | in_progress | completed | reverted
    resolved_by: str = ""
    resolved_at: str = ""

    # GxP
    gxp_relevant: bool = True
    requires_re_approval: bool = False

    # 审计时间戳
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def resolve(self, resolved_by: str) -> None:
        self.status = "completed"
        self.resolved_by = resolved_by
        self.resolved_at = datetime.now(timezone.utc).isoformat()

    def revert(self, reason: str, triggered_by: str) -> "ChangeRecord":
        """创建一条回滚记录"""
        self.status = "reverted"
        return ChangeRecord(
            change_id=f"CHG-ROLLBACK-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            change_type=ChangeType.ROLLBACK,
            triggered_by=triggered_by,
            description=f"Rollback {self.change_id}: {reason}",
            reason=reason,
            files_changed=[
                FileChange(f.path, f.new_version, f.old_version, f"Rollback: {reason}")
                for f in self.files_changed
            ],
            impact_type=self.impact_type,
            gxp_relevant=True,
            requires_re_approval=True,
        )

    def to_audit_line(self) -> dict[str, Any]:
        """转为 JSONL 审计行"""
        return {
            "change_id": self.change_id,
            "type": self.change_type,
            "triggered_by": self.triggered_by,
            "triggered_by_role": self.triggered_by_role,
            "description": self.description,
            "files_count": len(self.files_changed),
            "impact_type": self.impact_type,
            "stages_impacted": sum(1 for s in self.impacted_stages if s.impacted),
            "status": self.status,
            "requires_re_approval": self.requires_re_approval,
            "gxp_relevant": self.gxp_relevant,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }
