"""
Clinical Statistical Programming Workflow State Machine.
Defines the full pipeline: Protocol → SAP → SDTM → ADaM → TFL → Submission.
"""

from enum import StrEnum
from dataclasses import dataclass, field
from typing import Any
import uuid
from datetime import datetime, timezone


class Stage(StrEnum):
    """The 12-stage clinical stat programming pipeline."""

    PROTOCOL = "protocol"
    SAP = "sap"
    CRF_DESIGN = "crf_design"
    DATA_COLLECTION = "data_collection"
    SDTM_SPEC = "sdtm_spec"
    SDTM_PROGRAMMING = "sdtm_programming"
    ADAM_SPEC = "adam_spec"
    ADAM_PROGRAMMING = "adam_programming"
    TFL_SHELL = "tfl_shell"
    TFL_PROGRAMMING = "tfl_programming"
    QC_VALIDATION = "qc_validation"
    SUBMISSION = "submission"

    @classmethod
    def sequence(cls) -> list["Stage"]:
        return list(cls)

    @property
    def next(self) -> "Stage | None":
        seq = self.sequence()
        idx = seq.index(self)
        return seq[idx + 1] if idx + 1 < len(seq) else None


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CONDITIONAL = "conditional"


class TrialPhase(StrEnum):
    PHASE_I = "phase_i"
    PHASE_II = "phase_ii"
    PHASE_III = "phase_iii"


class TherapeuticArea(StrEnum):
    ONCOLOGY = "oncology"
    NON_ONCOLOGY = "non_oncology"


@dataclass
class HumanGate:
    """A mandatory human review checkpoint before proceeding."""

    stage: Stage
    description: str
    reviewers: list[str]
    checklist: list[str]
    status: ApprovalStatus = ApprovalStatus.PENDING
    comments: str = ""
    signed_by: str = ""
    signed_at: datetime | None = None

    def approve(self, reviewer: str, comments: str = "") -> None:
        self.status = ApprovalStatus.APPROVED
        self.signed_by = reviewer
        self.signed_at = datetime.now(timezone.utc)
        self.comments = comments

    def reject(self, reviewer: str, comments: str) -> None:
        self.status = ApprovalStatus.REJECTED
        self.signed_by = reviewer
        self.comments = comments


# Each stage's human gate configuration
HUMAN_GATES: dict[Stage, HumanGate] = {
    Stage.SAP: HumanGate(
        stage=Stage.SAP,
        description="Statistical Analysis Plan review — verify endpoints, populations, methods",
        reviewers=["Lead Biostatistician", "Lead Programmer"],
        checklist=[
            "Primary/secondary endpoints match protocol",
            "Analysis populations defined (ITT, PP, Safety)",
            "Multiplicity adjustments specified",
            "SAP mock shells complete",
            "Sensitivity analyses specified",
        ],
    ),
    Stage.SDTM_SPEC: HumanGate(
        stage=Stage.SDTM_SPEC,
        description="SDTM mapping specification review — verify domain coverage, variable mappings",
        reviewers=["Lead Programmer", "Data Manager"],
        checklist=[
            "All CRF pages annotated (aCRF complete)",
            "Domain assignments correct per SDTM IG",
            "Controlled terminology aligned",
            "Supplemental qualifiers justified",
            "Cross-domain relationships documented",
        ],
    ),
    Stage.ADAM_SPEC: HumanGate(
        stage=Stage.ADAM_SPEC,
        description="ADaM specification review — verify derivations match SAP",
        reviewers=["Lead Biostatistician", "Lead Programmer"],
        checklist=[
            "ADSL population flags match SAP populations",
            "Endpoint derivations match SAP definitions",
            "Imputation methods specified",
            "Analysis time windows defined",
            "All TFL shells traceable to ADaM variables",
        ],
    ),
    Stage.TFL_SHELL: HumanGate(
        stage=Stage.TFL_SHELL,
        description="TFL shell review — verify mock-ups match SAP and ADaM",
        reviewers=["Lead Biostatistician", "Medical Writer"],
        checklist=[
            "Table/figure titles match SAP",
            "Column headers match ADaM variable labels",
            "Footnotes complete",
            "Population/subgroup headers correct",
        ],
    ),
    Stage.QC_VALIDATION: HumanGate(
        stage=Stage.QC_VALIDATION,
        description="QC validation review — verify double programming results",
        reviewers=["QC Programmer", "Lead Programmer"],
        checklist=[
            "All pivotal TFLs double-programmed",
            "Discrepancies resolved or documented",
            "Pinnacle 21 errors triaged",
            "Log files clean",
        ],
    ),
    Stage.SUBMISSION: HumanGate(
        stage=Stage.SUBMISSION,
        description="Submission package review — verify define.xml, ADRG, eCTD compliance",
        reviewers=["Lead Programmer", "Regulatory Affairs"],
        checklist=[
            "define.xml validates against CDISC schema",
            "ADRG/SDRG narrative complete",
            "XPT files conform to v5 transport spec",
            "eCTD folder structure correct",
        ],
    ),
}

# AI-auto stages (no human gate required)
AI_AUTO_STAGES = {
    Stage.SDTM_PROGRAMMING,
    Stage.ADAM_PROGRAMMING,
    Stage.TFL_PROGRAMMING,
}


@dataclass
class WorkflowState:
    """Tracks the state of one clinical study through the full pipeline."""

    study_id: str = field(default_factory=lambda: f"STUDY-{uuid.uuid4().hex[:8].upper()}")
    protocol_id: str = ""
    trial_phase: TrialPhase = TrialPhase.PHASE_III
    therapeutic_area: TherapeuticArea = TherapeuticArea.NON_ONCOLOGY
    current_stage: Stage = Stage.PROTOCOL
    stage_history: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, list[str]] = field(default_factory=dict)
    human_gates: dict[str, HumanGate] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def advance(self) -> Stage | None:
        """Move to next stage. Returns None if blocked by a human gate."""
        next_stage = self.current_stage.next
        if next_stage is None:
            return None

        # Check if a human gate is needed at the current or next stage
        gate = HUMAN_GATES.get(next_stage)
        if gate and gate.status != ApprovalStatus.APPROVED:
            self.human_gates[next_stage.value] = gate
            self.current_stage = next_stage
            return None  # Blocked: requires human approval

        self.stage_history.append({
            "stage": self.current_stage.value,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        self.current_stage = next_stage
        return next_stage

    def get_pending_approvals(self) -> list[HumanGate]:
        return [g for g in self.human_gates.values() if g.status == ApprovalStatus.PENDING]

    def add_artifact(self, stage: Stage, path: str) -> None:
        self.artifacts.setdefault(stage.value, []).append(path)

    def summary(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "protocol_id": self.protocol_id,
            "trial_phase": self.trial_phase.value,
            "therapeutic_area": self.therapeutic_area.value,
            "current_stage": self.current_stage.value,
            "pending_approvals": len(self.get_pending_approvals()),
            "total_artifacts": sum(len(v) for v in self.artifacts.values()),
            "errors": len(self.errors),
        }
