"""
独立强制审核清单层。

设计理由:
  Skills 不内化到 Agent prompt 中。
  审核清单是独立文件, 在 REVIEW 阶段被强制加载。
  Agent 必须逐项标记 [PASS/FAIL/FLAGGED] 才能提交 Human Gate。

这是对"移除 Skills 是否导致 AI 执行不够精准"的回答:
  · Skills 的审核灵魂 (清单 + 强制检查) 在这里保留
  · Skills 的交互界面由 Orchestrator 的 Human Gate flow 替代
  · Agent 不能跳过清单项 ← 这是强制约束, 不是建议
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
import yaml


class ChecklistItemStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    FLAGGED = "FLAGGED"
    NOT_APPLICABLE = "N/A"


@dataclass
class ChecklistItem:
    """审核清单中的一项"""
    id: str
    item: str
    category: str = ""           # 如 "Endpoint Definition", "CDISC Compliance"
    required_evidence: str = ""   # Agent 必须提供什么证据
    status: str = ChecklistItemStatus.PASS
    agent_finding: str = ""      # Agent 的发现
    agent_evidence: str = ""     # Agent 提供的证据
    agent_confidence: str = "HIGH"
    human_decision: str = ""     # 审核人的决定


@dataclass
class StageChecklist:
    """
    一个阶段的独立审核清单。

    这个清单在代码中作为数据结构存在,
    在部署时可以从 YAML 文件加载。
    """
    stage: str
    gate_reviewers: list[str]
    description: str
    items: list[ChecklistItem] = field(default_factory=list)

    def all_passed(self) -> bool:
        """清单全部通过?"""
        return all(
            i.status in (ChecklistItemStatus.PASS, ChecklistItemStatus.NOT_APPLICABLE)
            for i in self.items
        )

    def failed_items(self) -> list[ChecklistItem]:
        """未通过的清单项"""
        return [i for i in self.items if i.status == ChecklistItemStatus.FAIL]

    def flagged_items(self) -> list[ChecklistItem]:
        """被标记的清单项"""
        return [i for i in self.items if i.status == ChecklistItemStatus.FLAGGED]

    def validate_agent_completion(self) -> dict[str, Any]:
        """
        验证 Agent 是否真的逐项检查了 (不能跳过)。
        返回: {valid: bool, violations: [...]}
        """
        violations = []
        for item in self.items:
            if item.status == ChecklistItemStatus.PASS and not item.agent_evidence:
                violations.append({
                    "item_id": item.id,
                    "item": item.item,
                    "violation": "Agent claimed PASS but provided no evidence",
                    "required": f"Must provide evidence for: {item.required_evidence}",
                })
            if item.status == ChecklistItemStatus.FAIL and not item.agent_finding:
                violations.append({
                    "item_id": item.id,
                    "item": item.item,
                    "violation": "Agent marked FAIL but provided no finding description",
                })
        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "message": "All items properly evidenced" if len(violations) == 0
                       else f"{len(violations)} items lack proper evidence",
        }

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "reviewers": self.gate_reviewers,
            "description": self.description,
            "total_items": len(self.items),
            "passed": sum(1 for i in self.items if i.status == ChecklistItemStatus.PASS),
            "failed": len(self.failed_items()),
            "flagged": len(self.flagged_items()),
        }


# ── 6 个 Human Gate 的完整审核清单 ───────────────────────────


GATE_CHECKLISTS: dict[str, StageChecklist] = {
    "sap": StageChecklist(
        stage="sap",
        gate_reviewers=["Lead Biostatistician", "Lead Programmer"],
        description="Statistical Analysis Plan — 完整性 / 与 Protocol 一致性审核",
        items=[
            ChecklistItem("SAP-01", "Primary endpoint matches Protocol Section X.X exactly",
                         category="Endpoint Definition",
                         required_evidence="Protocol section ref + SAP section ref + endpoint text comparison"),
            ChecklistItem("SAP-02", "Key secondary endpoints match Protocol (all listed)",
                         category="Endpoint Definition",
                         required_evidence="Side-by-side comparison of Protocol vs SAP endpoints"),
            ChecklistItem("SAP-03", "Analysis populations fully defined (ITT, FAS, Safety, PP)",
                         category="Population Definition",
                         required_evidence="Exact population criteria text from SAP with Protocol reference"),
            ChecklistItem("SAP-04", "Multiplicity adjustment strategy specified",
                         category="Statistical Methods",
                         required_evidence="Hierarchical testing order or other multiplicity method documented"),
            ChecklistItem("SAP-05", "Handling of missing data with justification",
                         category="Statistical Methods",
                         required_evidence="Primary + sensitivity approaches stated with ICH E9(R1) reference"),
            ChecklistItem("SAP-06", "Estimands framework per ICH E9(R1) for each endpoint",
                         category="Estimands",
                         required_evidence="Five estimand attributes documented per endpoint"),
            ChecklistItem("SAP-07", "Sample size calculation with all assumptions listed",
                         category="Sample Size",
                         required_evidence="Power, alpha, effect size, SD, dropout rate all documented"),
            ChecklistItem("SAP-08", "Interim analysis plan with stopping boundaries",
                         category="Interim Analysis",
                         required_evidence="Timing, OBF/Pocock boundaries, alpha spending function"),
            ChecklistItem("SAP-09", "Subgroup analyses pre-specified with rationale",
                         category="Subgroup Analysis",
                         required_evidence="Each subgroup variable + rationale documented"),
            ChecklistItem("SAP-10", "Sensitivity analyses cover plausible departures",
                         category="Sensitivity",
                         required_evidence="At least 2 sensitivity analyses for primary endpoint"),
            ChecklistItem("SAP-11", "All TFL mock shells complete and numbered",
                         category="TFL Planning",
                         required_evidence="TFL shell catalog with IDs, titles, populations, source datasets"),
        ],
    ),

    "sdtm_spec": StageChecklist(
        stage="sdtm_spec",
        gate_reviewers=["Lead Programmer", "Data Manager"],
        description="SDTM 映射规范 — CDISC 合规 / 控制术语一致性",
        items=[
            ChecklistItem("SDTM-01", "All CRF pages annotated (aCRF complete)",
                         category="CRF Coverage",
                         required_evidence="aCRF page count matches EDC form count"),
            ChecklistItem("SDTM-02", "Domain assignments correct per SDTM IG classification",
                         category="CDISC Compliance",
                         required_evidence="Each assigned domain justified per SDTMIG Section 2"),
            ChecklistItem("SDTM-03", "Controlled terminology aligned with NCI/CDISC CT (latest version)",
                         category="Terminology",
                         required_evidence="CDISC CT version referenced + all coded variables checked"),
            ChecklistItem("SDTM-04", "SUPPQUAL variables justified — not masking missing standard vars",
                         category="CDISC Compliance",
                         required_evidence="Each QNAM has documented justification for non-standard inclusion"),
            ChecklistItem("SDTM-05", "Cross-domain relationships (RELREC) documented",
                         category="Data Integrity",
                         required_evidence="RELREC records for AE↔LB, CM↔AE, etc. documented"),
        ],
    ),

    "adam_spec": StageChecklist(
        stage="adam_spec",
        gate_reviewers=["Lead Biostatistician", "Lead Programmer"],
        description="ADaM 规范 — 衍生逻辑 / SAP 一致性",
        items=[
            ChecklistItem("ADAM-01", "ADSL population flags (FASFL, SAFFL, PPSFL) match SAP populations",
                         category="Population Flags",
                         required_evidence="Flag derivation logic with SAP section reference"),
            ChecklistItem("ADAM-02", "Endpoint derivations match SAP definitions for each endpoint",
                         category="Endpoint Derivation",
                         required_evidence="Per-endpoint derivation traceability to SAP"),
            ChecklistItem("ADAM-03", "Imputation methods specified (LOCF, WOCF, MI, etc.)",
                         category="Missing Data",
                         required_evidence="Imputation method per endpoint with SAP reference"),
            ChecklistItem("ADAM-04", "Analysis time windows defined (visit windows, analysis periods)",
                         category="Timing",
                         required_evidence="Visit window ranges documented per protocol SoA"),
            ChecklistItem("ADAM-05", "All TFL shells traceable to specific ADaM variables",
                         category="Traceability",
                         required_evidence="TFL column → ADaM variable mapping for each TFL"),
        ],
    ),

    "tfl_shell": StageChecklist(
        stage="tfl_shell",
        gate_reviewers=["Lead Biostatistician", "Medical Writer"],
        description="TFL Shell — Mock Shell 一致性 / 格式规范",
        items=[
            ChecklistItem("TFL-01", "Table/figure titles match SAP mock shells exactly",
                         category="Title Alignment",
                         required_evidence="Side-by-side title comparison per TFL"),
            ChecklistItem("TFL-02", "Column headers match ADaM variable labels",
                         category="Header Alignment",
                         required_evidence="Column header → ADaM variable label mapping"),
            ChecklistItem("TFL-03", "Footnotes complete with all abbreviations expanded",
                         category="Footnotes",
                         required_evidence="Footnote list completeness check per TFL"),
            ChecklistItem("TFL-04", "Population/subgroup headers correct per SAP",
                         category="Population Header",
                         required_evidence="Population column header matches SAP population definition"),
        ],
    ),

    "qc_validation": StageChecklist(
        stage="qc_validation",
        gate_reviewers=["QC Programmer", "Lead Programmer"],
        description="QC 验证 — 双编程 / P21 合规",
        items=[
            ChecklistItem("QC-01", "All pivotal TFLs double-programmed with independent code",
                         category="Double Programming",
                         required_evidence="Independent QC program per pivotal TFL + comparison result"),
            ChecklistItem("QC-02", "Discrepancies resolved or documented with justification",
                         category="Discrepancy Resolution",
                         required_evidence="Discrepancy log with resolution status per item"),
            ChecklistItem("QC-03", "Pinnacle 21 errors triaged (0 open ERROR-level findings)",
                         category="P21 Validation",
                         required_evidence="P21 output summary + triage report showing 0 errors"),
            ChecklistItem("QC-04", "All program logs clean (no unhandled exceptions, warnings reviewed)",
                         category="Program Logs",
                         required_evidence="Log file summary per program"),
        ],
    ),

    "submission": StageChecklist(
        stage="submission",
        gate_reviewers=["Lead Programmer", "Regulatory Affairs"],
        description="递交包 — define.xml / eCTD / 完整性",
        items=[
            ChecklistItem("SUB-01", "define.xml validates against CDISC XML Schema (define-xml-2.0.xsd)",
                         category="define.xml",
                         required_evidence="Schema validation result + error count = 0"),
            ChecklistItem("SUB-02", "ADRG/SDRG narrative complete with all required sections",
                         category="Reviewer's Guide",
                         required_evidence="ADRG/SDRG section completeness checklist"),
            ChecklistItem("SUB-03", "All XPT files conform to SAS Transport v5 specification",
                         category="XPT Compliance",
                         required_evidence="XPT header check + record count per dataset"),
            ChecklistItem("SUB-04", "eCTD folder structure follows FDA/NMPA specification",
                         category="eCTD Structure",
                         required_evidence="Folder structure validation against eCTD spec"),
        ],
    ),
}


def get_checklist(stage: str) -> StageChecklist | None:
    """获取阶段的审核清单"""
    return GATE_CHECKLISTS.get(stage)


def validate_checklist_completion(stage: str,
                                   agent_results: list[dict]) -> dict[str, Any]:
    """
    验证 Agent 是否完成了清单中的每一项 (强制执行)。

    如果 Agent 跳过了任何一项 → 审核包无法提交。
    这是对"Skills 移除是否导致不够精准"的直接回答:
      Skills 的强制审核在这里以程序化方式执行。
    """
    checklist = get_checklist(stage)
    if checklist is None:
        return {"valid": True, "message": "No checklist for this stage"}
    return checklist.validate_agent_completion()
