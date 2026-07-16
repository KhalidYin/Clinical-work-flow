"""
Structured Review Protocol v3.0 — Agent↔Human interaction layer.

Core insight: replace chat-based review with a protocol exchange.
Agent writes a ReviewPacket → Human batch-approves in Review Panel →
DecisionReceipt returned → Agent continues.

ALL formats are enforced by JSON Schema at the Agent SDK level —
not by prompt suggestion. This is the "contract" between agent and human.

Design principles:
  1. Fixed schema per review_type — same structure every time
  2. Human never types free text unless choosing "Modified" with custom value
  3. File system is the message queue (.review_queue/)
  4. Every packet and receipt is git-versioned (audit trail)
"""

from __future__ import annotations

import json
import hashlib
import re
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


REVIEW_PROTOCOL_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "schemas"
    / "review"
    / "review-protocol.schema.json"
)


def load_review_protocol_schema() -> dict[str, Any]:
    """Load the authoritative Review Protocol JSON Schema bundle."""
    return json.loads(REVIEW_PROTOCOL_SCHEMA_PATH.read_text(encoding="utf-8"))


def _schema_definition(schema_bundle: dict[str, Any], name: str) -> dict[str, Any]:
    """Return a standalone schema definition with shared $defs available."""
    schema = deepcopy(schema_bundle["$defs"][name])
    schema.setdefault("$schema", schema_bundle["$schema"])
    schema["$defs"] = deepcopy(schema_bundle["$defs"])
    return schema


# ═══════════════════════════════════════════════════════════════════
# Enums — fixed vocabulary, no free text
# ═══════════════════════════════════════════════════════════════════


class ReviewType(StrEnum):
    """Fixed set of review types — each has its own rendering template in Review Panel."""
    SOURCE_INTAKE = "source_intake"
    SDTM_SPEC = "sdtm_spec"
    ADAM_SPEC = "adam_spec"
    TFL_SHELL = "tfl_shell"
    TFL_QC = "tfl_qc"
    SAP_REVIEW = "sap_review"
    SUBMISSION = "submission"


class FindingCategory(StrEnum):
    """What kind of finding — drives filter tabs in Review Panel."""
    MAPPING = "mapping"           # CRF → SDTM variable mapping
    DERIVATION = "derivation"     # ADaM derivation logic
    POPULATION = "population"     # Analysis population flags
    TERMINOLOGY = "terminology"   # CDISC CT alignment
    COMPLIANCE = "compliance"     # Regulatory/standard compliance
    FORMATTING = "formatting"     # Output format/layout


class Severity(StrEnum):
    """How critical — drives color coding and default visibility."""
    CRITICAL = "critical"   # Red — blocks progress
    WARNING = "warning"      # Yellow — should fix
    INFO = "info"            # Blue — FYI, auto-collapsed


class Decision(StrEnum):
    """Human decision on a single finding."""
    APPROVED = "approved"     # Accept agent's proposed value as-is
    REJECTED = "rejected"     # Reject — agent must re-think
    MODIFIED = "modified"     # Accept with human edit


class RejectionReason(StrEnum):
    """Structured reason for rejected findings."""
    WRONG_DOMAIN_ASSIGNMENT = "wrong_domain_assignment"
    INCORRECT_VARIABLE_MAPPING = "incorrect_variable_mapping"
    INCORRECT_DERIVATION = "incorrect_derivation"
    WRONG_CT_VALUE = "wrong_ct_value"
    MISSING_VARIABLE = "missing_variable"
    INCORRECT_POPULATION = "incorrect_population"
    INCORRECT_METHOD = "incorrect_method"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    OTHER = "other"


class Urgency(StrEnum):
    """Does this review block the agent from continuing?"""
    NORMAL = "normal"         # Agent can continue on other work
    BLOCKING = "blocking"     # Agent must wait for this before proceeding


class ConsensusRule(StrEnum):
    """How assigned reviewers close a packet when more than one is required."""

    ALL_MUST_APPROVE = "all_must_approve"
    MAJORITY = "majority"
    ANY_ONE = "any_one"


class QueueScope(StrEnum):
    """Ownership boundary for a physical review queue."""

    STUDY = "study"
    WIKI = "wiki"


class ReviewPolicyState(StrEnum):
    """Effective state derived from assignments, receipts, and timeout policy."""

    READY = "ready"
    PENDING = "pending"
    REJECTED = "rejected"
    REMINDER_DUE = "reminder_due"
    ESCALATION_DUE = "escalation_due"
    STALE = "stale"


@dataclass(frozen=True)
class ReviewerAssignment:
    """A role assignment carried by the shared ReviewPacket contract."""

    role: str
    name: str | None = None
    decision: Decision | None = None
    decided_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "name": self.name,
            "decision": self.decision.value if self.decision else None,
            "decided_at": self.decided_at,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ReviewerAssignment":
        decision = value.get("decision")
        return cls(
            role=value["role"],
            name=value.get("name"),
            decision=Decision(decision) if decision is not None else None,
            decided_at=value.get("decided_at"),
        )


@dataclass(frozen=True)
class TimeoutConfig:
    """Non-executing review reminder/escalation metadata in hours."""

    reminder_hours: int | None = None
    escalation_hours: int | None = None
    stale_hours: int | None = None
    escalation_contacts: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name in ("reminder_hours", "escalation_hours", "stale_hours"):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        if self.escalation_contacts:
            result["escalation_contacts"] = self.escalation_contacts
        return result

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TimeoutConfig":
        return cls(
            reminder_hours=value.get("reminder_hours"),
            escalation_hours=value.get("escalation_hours"),
            stale_hours=value.get("stale_hours"),
            escalation_contacts=list(value.get("escalation_contacts", [])),
        )


@dataclass(frozen=True)
class ReviewPolicyEvaluation:
    """Pure evaluation result; callers decide how to notify or block."""

    state: ReviewPolicyState
    can_close: bool
    pending_roles: list[str] = field(default_factory=list)
    decided_roles: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# JSON Schema Definitions — loaded from the repository schema bundle
# ═══════════════════════════════════════════════════════════════════

# The exported schema constants below are intentionally loaded from the
# repository-level JSON Schema bundle. Keep the JSON file authoritative and use
# tests to catch any drift in Python enums or TypeScript review-panel types.
REVIEW_PROTOCOL_SCHEMA = load_review_protocol_schema()
REVIEW_FINDING_SCHEMA = _schema_definition(REVIEW_PROTOCOL_SCHEMA, "review_finding")
REVIEW_PACKET_SCHEMA = _schema_definition(REVIEW_PROTOCOL_SCHEMA, "review_packet")
FINDING_DECISION_SCHEMA = _schema_definition(REVIEW_PROTOCOL_SCHEMA, "finding_decision")
DECISION_RECEIPT_SCHEMA = _schema_definition(REVIEW_PROTOCOL_SCHEMA, "decision_receipt")
CONFIRMATION_RECEIPT_SCHEMA = _schema_definition(
    REVIEW_PROTOCOL_SCHEMA, "confirmation_receipt"
)


def _jsonschema_violations(schema: dict[str, Any], data: dict[str, Any]) -> list[str]:
    """Return deterministic JSON Schema violations for protocol boundaries."""

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [
        error.message
        for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
    ]


def validate_review_packet_schema(data: dict[str, Any]) -> list[str]:
    """Validate a packet against the repository JSON Schema authority."""

    return _jsonschema_violations(REVIEW_PACKET_SCHEMA, data)


def validate_decision_receipt_schema(data: dict[str, Any]) -> list[str]:
    """Validate a decision receipt against the repository JSON Schema authority."""

    return _jsonschema_violations(DECISION_RECEIPT_SCHEMA, data)


def evaluate_review_policy(
    packet: "ReviewPacket",
    receipts: list["DecisionReceipt"],
    *,
    now: datetime | None = None,
) -> ReviewPolicyEvaluation:
    """Evaluate review assignments and timeout policy without mutating a packet.

    A rejected receipt is terminal and conservative.  A packet without explicit
    assignments retains the legacy one-receipt behavior.  Timeouts never approve
    work; they only expose reminder/escalation/stale states for the Runtime/audit.
    """

    now = now or datetime.now(timezone.utc)
    assignments = packet.required_reviewers
    if not assignments:
        if any(_receipt_is_rejected(receipt) for receipt in receipts):
            return ReviewPolicyEvaluation(ReviewPolicyState.REJECTED, can_close=True)
        return ReviewPolicyEvaluation(
            ReviewPolicyState.READY if receipts else _timeout_state(packet, now),
            can_close=bool(receipts),
        )

    assigned_roles = {assignment.role for assignment in assignments}
    receipt_by_role = {
        receipt.reviewer_role: receipt
        for receipt in receipts
        if receipt.reviewer_role in assigned_roles
    }
    rejected_roles = [
        role for role, receipt in receipt_by_role.items() if _receipt_is_rejected(receipt)
    ]
    if rejected_roles:
        return ReviewPolicyEvaluation(
            ReviewPolicyState.REJECTED,
            can_close=True,
            pending_roles=sorted(assigned_roles - set(receipt_by_role)),
            decided_roles=sorted(receipt_by_role),
        )

    required_count = len(assignments)
    approved_count = len(receipt_by_role)
    rule = packet.consensus_rule or ConsensusRule.ALL_MUST_APPROVE
    if rule == ConsensusRule.ANY_ONE:
        can_close = approved_count >= 1
    elif rule == ConsensusRule.MAJORITY:
        can_close = approved_count >= (required_count // 2 + 1)
    else:
        can_close = approved_count == required_count
    if can_close:
        return ReviewPolicyEvaluation(
            ReviewPolicyState.READY,
            can_close=True,
            pending_roles=sorted(assigned_roles - set(receipt_by_role)),
            decided_roles=sorted(receipt_by_role),
        )
    return ReviewPolicyEvaluation(
        _timeout_state(packet, now),
        can_close=False,
        pending_roles=sorted(assigned_roles - set(receipt_by_role)),
        decided_roles=sorted(receipt_by_role),
    )


def _receipt_is_rejected(receipt: "DecisionReceipt") -> bool:
    return any(item.decision == Decision.REJECTED for item in receipt.decisions)


def _timeout_state(packet: "ReviewPacket", now: datetime) -> ReviewPolicyState:
    config = packet.timeout_config
    if config is None:
        return ReviewPolicyState.PENDING
    try:
        created_at = datetime.fromisoformat(packet.created_at.replace("Z", "+00:00"))
    except ValueError:
        return ReviewPolicyState.PENDING
    elapsed_hours = (now - created_at).total_seconds() / 3600
    if config.stale_hours is not None and elapsed_hours >= config.stale_hours:
        return ReviewPolicyState.STALE
    if config.escalation_hours is not None and elapsed_hours >= config.escalation_hours:
        return ReviewPolicyState.ESCALATION_DUE
    if config.reminder_hours is not None and elapsed_hours >= config.reminder_hours:
        return ReviewPolicyState.REMINDER_DUE
    return ReviewPolicyState.PENDING


# ═══════════════════════════════════════════════════════════════════
# Output Format Specifications — for document generation outputs
# ═══════════════════════════════════════════════════════════════════

# Every stage that produces documents MUST conform to these format specs.
# These are referenced by the agent when generating outputs and by the
# Review Panel when rendering review forms.

OUTPUT_FORMAT_SPECS: dict[str, dict[str, Any]] = {
    "sdtm_spec": {
        "description": "SDTM domain variable mapping specification",
        "file_pattern": "sdtm_{domain}_spec.xlsx",
        "required_columns": [
            "Variable", "Label", "Type", "Length", "Core", "Role",
            "Mandatory", "Derivation", "Source CRF", "Controlled Terms",
            "CT Codelist", "Value Constraints",
        ],
        "required_metadata": [
            "domain_code", "domain_name", "domain_class", "structure",
            "keys", "sdtm_version", "sdtmig_version", "ct_version",
            "generated_by", "generated_at",
        ],
    },
    "adam_spec": {
        "description": "ADaM dataset derivation specification",
        "file_pattern": "adam_{dataset}_spec.xlsx",
        "required_columns": [
            "Variable", "Label", "Type", "Length", "Core", "Source",
            "Derivation", "Significant Digits", "Codelist",
        ],
        "required_metadata": [
            "dataset_name", "dataset_label", "structure", "predecessors",
            "population_flags", "adam_version", "adamig_version",
            "generated_by", "generated_at",
        ],
    },
    "tfl_shell": {
        "description": "TFL shell definition",
        "file_pattern": "tfl_{tfl_id}.yaml",
        "required_fields": [
            "tfl_id", "type", "title", "population", "source_dataset",
            "section", "analysis_method", "columns", "footnotes",
        ],
        "required_metadata": [
            "page_layout", "is_pivotal", "requires_double_programming",
            "generated_by", "generated_at",
        ],
    },
    "program_code": {
        "description": "Generated SAS/R/Python program",
        "file_pattern": "{stage}/{name}.{ext}",
        "required_header": [
            "# PROGRAM: <name>",
            "# PURPOSE: <description>",
            "# INPUT: <source datasets>",
            "# OUTPUT: <output dataset/file>",
            "# GENERATED BY: <agent_name> (<model>)",
            "# GENERATED AT: <ISO 8601 timestamp>",
            "# AI GENERATED: YES — HUMAN APPROVAL: PENDING",
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════
# Data Classes — Python representation of the protocol
# ═══════════════════════════════════════════════════════════════════


@dataclass
class ReviewFinding:
    """
    Single finding for human review.

    Every field is REQUIRED by JSON Schema. The agent cannot skip fields.
    The Review Panel renders each finding as a row in a fixed-layout table.
    """
    id: str
    category: FindingCategory
    severity: Severity
    location: str
    title: str
    current_value: str
    proposed_value: str
    rationale: str
    evidence_refs: list[str]
    auto_approved: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "severity": self.severity.value,
            "location": self.location,
            "title": self.title,
            "current_value": self.current_value,
            "proposed_value": self.proposed_value,
            "rationale": self.rationale,
            "evidence_refs": self.evidence_refs,
            "auto_approved": self.auto_approved,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ReviewFinding":
        return cls(
            id=d["id"],
            category=FindingCategory(d["category"]),
            severity=Severity(d["severity"]),
            location=d["location"],
            title=d["title"],
            current_value=d["current_value"],
            proposed_value=d["proposed_value"],
            rationale=d["rationale"],
            evidence_refs=d["evidence_refs"],
            auto_approved=d.get("auto_approved", False),
        )


@dataclass
class ReviewPacket:
    """
    Agent submits this to .review_queue/ when human input is needed.

    One packet = one review cycle. Contains all findings.
    Review Panel renders the entire packet as a single-page form.
    """
    review_id: str
    review_type: ReviewType
    source_documents: list[str]
    agent_summary: str
    findings: list[ReviewFinding]
    urgency: Urgency = Urgency.NORMAL
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    generated_by: str = ""
    auto_approved_count: int = 0
    required_reviewers: list[ReviewerAssignment] = field(default_factory=list)
    consensus_rule: ConsensusRule | None = None
    timeout_config: TimeoutConfig | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "review_id": self.review_id,
            "review_type": self.review_type.value,
            "source_documents": self.source_documents,
            "agent_summary": self.agent_summary,
            "findings": [f.to_dict() for f in self.findings],
            "urgency": self.urgency.value,
            "created_at": self.created_at,
            "generated_by": self.generated_by,
            "auto_approved_count": self.auto_approved_count,
        }
        if self.required_reviewers:
            data["required_reviewers"] = [item.to_dict() for item in self.required_reviewers]
        if self.consensus_rule is not None:
            data["consensus_rule"] = self.consensus_rule.value
        if self.timeout_config is not None:
            data["timeout_config"] = self.timeout_config.to_dict()
        return data

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ReviewPacket":
        return cls(
            review_id=d["review_id"],
            review_type=ReviewType(d["review_type"]),
            source_documents=d["source_documents"],
            agent_summary=d["agent_summary"],
            findings=[ReviewFinding.from_dict(f) for f in d["findings"]],
            urgency=Urgency(d.get("urgency", "normal")),
            created_at=d.get("created_at", datetime.now(timezone.utc).isoformat()),
            generated_by=d.get("generated_by", ""),
            auto_approved_count=d.get("auto_approved_count", 0),
            required_reviewers=[
                ReviewerAssignment.from_dict(item) for item in d.get("required_reviewers", [])
            ],
            consensus_rule=(
                ConsensusRule(d["consensus_rule"])
                if d.get("consensus_rule") is not None else None
            ),
            timeout_config=(
                TimeoutConfig.from_dict(d["timeout_config"])
                if d.get("timeout_config") is not None else None
            ),
        )

    def findings_by_severity(self, severity: Severity) -> list[ReviewFinding]:
        return [f for f in self.findings if f.severity == severity]

    def findings_needing_decision(self) -> list[ReviewFinding]:
        """Findings that are NOT auto-approved — human must decide."""
        return [f for f in self.findings if not f.auto_approved]

    def has_critical(self) -> bool:
        return any(f.severity == Severity.CRITICAL for f in self.findings)


@dataclass
class FindingDecision:
    """Human decision on a single finding."""
    finding_id: str
    decision: Decision
    modified_value: str | None = None
    rejection_reason: RejectionReason | None = None
    human_correction: str | None = None
    reference: str | None = None
    comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "finding_id": self.finding_id,
            "decision": self.decision.value,
        }
        if self.modified_value is not None:
            d["modified_value"] = self.modified_value
        if self.rejection_reason is not None:
            d["rejection_reason"] = self.rejection_reason.value
        if self.human_correction is not None:
            d["human_correction"] = self.human_correction
        if self.reference is not None:
            d["reference"] = self.reference
        if self.comment is not None:
            d["comment"] = self.comment
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FindingDecision":
        return cls(
            finding_id=d["finding_id"],
            decision=Decision(d["decision"]),
            modified_value=d.get("modified_value"),
            rejection_reason=(
                RejectionReason(d["rejection_reason"])
                if d.get("rejection_reason") else None
            ),
            human_correction=d.get("human_correction"),
            reference=d.get("reference"),
            comment=d.get("comment"),
        )


@dataclass
class DecisionReceipt:
    """
    Human returns this after reviewing a ReviewPacket.

    Generated by Review Panel on "Submit All Decisions".
    Agent reads this from .review_queue/ and applies decisions.
    """
    review_id: str
    reviewer: str
    decisions: list[FindingDecision]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    general_notes: str = ""
    reviewer_role: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "review_id": self.review_id,
            "reviewer": self.reviewer,
            "timestamp": self.timestamp,
            "decisions": [fd.to_dict() for fd in self.decisions],
        }
        if self.general_notes:
            d["general_notes"] = self.general_notes
        if self.reviewer_role:
            d["reviewer_role"] = self.reviewer_role
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DecisionReceipt":
        return cls(
            review_id=d["review_id"],
            reviewer=d["reviewer"],
            decisions=[FindingDecision.from_dict(fd) for fd in d["decisions"]],
            timestamp=d.get("timestamp", datetime.now(timezone.utc).isoformat()),
            general_notes=d.get("general_notes", ""),
            reviewer_role=d.get("reviewer_role"),
        )

    def approved_count(self) -> int:
        return sum(1 for d in self.decisions if d.decision == Decision.APPROVED)

    def rejected_count(self) -> int:
        return sum(1 for d in self.decisions if d.decision == Decision.REJECTED)

    def modified_count(self) -> int:
        return sum(1 for d in self.decisions if d.decision == Decision.MODIFIED)

    def summary(self) -> dict[str, Any]:
        total = len(self.decisions)
        return {
            "review_id": self.review_id,
            "reviewer": self.reviewer,
            "total_decisions": total,
            "approved": self.approved_count(),
            "rejected": self.rejected_count(),
            "modified": self.modified_count(),
            "approval_rate_pct": round(self.approved_count() / total * 100, 1) if total else 0,
        }


# ═══════════════════════════════════════════════════════════════════
# Review Queue — file-system-based message passing
# ═══════════════════════════════════════════════════════════════════


class ReviewQueueScopeError(ValueError):
    """Raised when one physical queue is incorrectly reused across boundaries."""


class ReviewQueue:
    """
    File-system-based message queue for agent↔human review exchange.

    Directory structure:
      .review_queue/
        {review_id}.json          ← Agent writes ReviewPacket
        {review_id}_decision.json ← Human writes DecisionReceipt
        {review_id}_confirmation.json ← Agent writes application result
        {review_id}_rework.json   ← Agent writes rejected-finding rework directives
        archive/                  ← Completed reviews moved here
    """

    def __init__(
        self,
        project_dir: str | Path,
        queue_dir: str | Path | None = None,
        *,
        scope: QueueScope | str = QueueScope.STUDY,
    ) -> None:
        project_path = Path(project_dir)
        self.project_dir = project_path.resolve()
        self.scope = QueueScope(scope)
        if queue_dir is None:
            self.queue_dir = project_path / ".review_queue"
        else:
            queue_path = Path(queue_dir)
            self.queue_dir = queue_path if queue_path.is_absolute() else project_path / queue_path
        self.archive_dir = self.queue_dir / "archive"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_scope_marker()

    # ── Agent-side operations ─────────────────────────────────

    def submit_packet(self, packet: ReviewPacket) -> Path:
        """Agent submits a review packet. Returns path to written file."""
        violations = validate_review_packet_schema(packet.to_dict())
        if violations:
            raise ValueError(f"ReviewPacket does not satisfy schema: {violations}")
        filepath = self.queue_dir / f"{packet.review_id}.json"
        filepath.write_text(packet.to_json(), encoding="utf-8")
        self._write_audit_event("packet_submitted", packet.review_id, filepath)
        return filepath

    def has_pending(self) -> bool:
        """Check if there are packets still awaiting human decision."""
        return len(self.pending_packets()) > 0

    def pending_packets(self) -> list[str]:
        """List review_ids that have a packet but no decision yet."""
        pending = []
        for p in sorted(self.queue_dir.glob("*.json")):
            if not self._is_packet_file(p):
                continue
            try:
                packet = ReviewPacket.from_dict(json.loads(p.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, KeyError, ValueError):
                pending.append(p.stem)
                continue
            if not evaluate_review_policy(packet, self._load_receipts(p.stem)).can_close:
                pending.append(p.stem)
        return pending

    # ── Human-side operations ─────────────────────────────────

    def load_pending_packets(self) -> list[ReviewPacket]:
        """Load all pending review packets for display in Review Panel."""
        packets = []
        for review_id in self.pending_packets():
            filepath = self.queue_dir / f"{review_id}.json"
            try:
                data = json.loads(filepath.read_text(encoding="utf-8"))
                packets.append(ReviewPacket.from_dict(data))
            except (json.JSONDecodeError, KeyError, ValueError):
                # Corrupt packet — log and skip
                filepath.rename(self.archive_dir / f"{review_id}_corrupt.json")
        return packets

    def load_packet(self, review_id: str) -> ReviewPacket | None:
        """Load a specific review packet."""
        filepath = self.queue_dir / f"{review_id}.json"
        if not filepath.exists():
            return None
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return ReviewPacket.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def submit_decision(self, receipt: DecisionReceipt) -> Path:
        """Human submits decision receipt. Returns path to written file."""
        violations = validate_decision_receipt_schema(receipt.to_dict())
        if violations:
            raise ValueError(f"DecisionReceipt does not satisfy schema: {violations}")
        suffix = ""
        if receipt.reviewer_role:
            safe_role = re.sub(r"[^a-z0-9_]+", "_", receipt.reviewer_role.lower()).strip("_")
            if not safe_role:
                raise ValueError("DecisionReceipt.reviewer_role must contain a file-safe role")
            suffix = f"_{safe_role}"
        filepath = self.queue_dir / f"{receipt.review_id}_decision{suffix}.json"
        filepath.write_text(receipt.to_json(), encoding="utf-8")
        self._write_audit_event("decision_submitted", receipt.review_id, filepath)
        return filepath

    # ── Agent-side: check for decisions ───────────────────────

    def check_decision(self, review_id: str) -> DecisionReceipt | None:
        """Agent checks if human has responded to a review packet."""
        filepath = self.queue_dir / f"{review_id}_decision.json"
        if not filepath.exists():
            return None
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return DecisionReceipt.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def wait_for_decision(self, review_id: str,
                          poll_interval_s: float = 2.0,
                          timeout_s: float | None = None) -> DecisionReceipt | None:
        """
        Blocking wait for human decision.
        In practice, the agent loop polls this — not a tight spin loop.
        timeout_s=None means wait forever.
        """
        import time
        elapsed = 0.0
        while timeout_s is None or elapsed < timeout_s:
            receipt = self.check_decision(review_id)
            if receipt is not None:
                return receipt
            time.sleep(poll_interval_s)
            elapsed += poll_interval_s
        return None

    # ── Lifecycle ────────────────────────────────────────────

    def archive_completed(self, review_id: str) -> None:
        """Move completed packet, decision, confirmation, and rework files to archive."""
        files = [
            self.queue_dir / f"{review_id}.json",
            self.queue_dir / f"{review_id}_confirmation.json",
            self.queue_dir / f"{review_id}_rework.json",
        ]
        files.extend(sorted(self.queue_dir.glob(f"{review_id}_decision*.json")))
        for review_file in files:
            if review_file.exists():
                review_file.rename(self.archive_dir / review_file.name)
        self._write_audit_event("review_archived", review_id, self.archive_dir)

    def list_archived(self) -> list[str]:
        """List all completed/archived review IDs."""
        return sorted(
            f.stem
            for f in self.archive_dir.glob("*.json")
            if self._is_packet_file(f)
        )

    def _is_packet_file(self, path: Path) -> bool:
        """Return true only for ReviewPacket JSON files."""
        name = path.name
        return not (
            name == ".queue_scope.json"
            or name.endswith("_decision.json")
            or "_decision_" in name
            or name.endswith("_confirmation.json")
            or name.endswith("_rework.json")
            or name.endswith("_conflict.json")
            or name.endswith("_corrupt.json")
            or "_clarification_" in name
        )

    def effective_policy(self, review_id: str, *, now: datetime | None = None) -> ReviewPolicyEvaluation:
        """Return effective assignment/timeout state from files in this queue."""

        packet = self.load_packet(review_id)
        if packet is None:
            raise FileNotFoundError(f"ReviewPacket not found: {review_id}")
        receipts = self._load_receipts(review_id)
        evaluation = evaluate_review_policy(packet, receipts, now=now)
        self._write_audit_event(
            "review_policy_evaluated",
            review_id,
            self.queue_dir,
            policy_state=evaluation.state.value,
            can_close=evaluation.can_close,
            pending_roles=evaluation.pending_roles,
        )
        return evaluation

    def _load_receipts(self, review_id: str) -> list[DecisionReceipt]:
        receipts: list[DecisionReceipt] = []
        for path in sorted(self.queue_dir.glob(f"{review_id}_decision*.json")):
            try:
                receipts.append(DecisionReceipt.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return receipts

    def _ensure_scope_marker(self) -> None:
        marker = self.queue_dir / ".queue_scope.json"
        expected = {"scope": self.scope.value, "owner_root": str(self.project_dir)}
        if marker.exists():
            try:
                existing = json.loads(marker.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ReviewQueueScopeError(f"Invalid queue scope marker: {marker}") from exc
            if existing.get("scope") != self.scope.value or existing.get("owner_root") != str(self.project_dir):
                raise ReviewQueueScopeError(
                    "Review queue belongs to a different scope or owner root; "
                    "Study and Wiki queues must remain physically separate."
                )
            return
        marker.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")

    def _write_audit_event(
        self,
        event: str,
        review_id: str,
        artifact_path: Path,
        **details: Any,
    ) -> None:
        digest = ""
        if artifact_path.is_file():
            digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        audit_line = {
            "event": event,
            "review_id": review_id,
            "queue_scope": self.scope.value,
            "queue_path": str(self.queue_dir),
            "artifact": str(artifact_path),
            "artifact_sha256": digest,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        with (self.project_dir / "audit_trail.jsonl").open("a", encoding="utf-8") as audit:
            audit.write(json.dumps(audit_line, ensure_ascii=False, sort_keys=True) + "\n")

    def queue_stats(self) -> dict[str, Any]:
        return {
            "pending_reviews": self.pending_packets(),
            "pending_count": len(self.pending_packets()),
            "archived_count": len(self.list_archived()),
            "blocking_present": any(
                self.load_packet(rid) and self.load_packet(rid).urgency == Urgency.BLOCKING
                for rid in self.pending_packets()
            ),
        }


# ═══════════════════════════════════════════════════════════════════
# Validation — ensure packets/decisions conform to schema
# ═══════════════════════════════════════════════════════════════════


def validate_review_packet(data: dict[str, Any]) -> list[str]:
    """
    Validate a review packet against the schema.
    Returns list of violation messages (empty = valid).

    This is a lightweight Python-level check for use when JSON Schema
    validation isn't available. In production, use jsonschema.validate()
    against REVIEW_PACKET_SCHEMA.
    """
    violations: list[str] = []

    required_fields = [
        "review_id", "review_type", "source_documents",
        "agent_summary", "findings", "urgency",
        "created_at", "generated_by", "auto_approved_count",
    ]
    for field_name in required_fields:
        if field_name not in data:
            violations.append(f"Missing required field: {field_name}")

    if "review_type" in data:
        valid_types = {r.value for r in ReviewType}
        if data["review_type"] not in valid_types:
            violations.append(f"Invalid review_type '{data['review_type']}'. "
                              f"Valid: {sorted(valid_types)}")

    if "urgency" in data:
        valid_urg = {u.value for u in Urgency}
        if data["urgency"] not in valid_urg:
            violations.append(f"Invalid urgency '{data['urgency']}'")

    if "findings" in data:
        if not isinstance(data["findings"], list):
            violations.append("findings must be a list")
        elif len(data["findings"]) == 0:
            violations.append("findings must contain at least one finding")
        else:
            for i, f in enumerate(data["findings"]):
                _validate_finding(f, i, violations)

    return violations


def _validate_finding(finding: dict[str, Any], index: int,
                      violations: list[str]) -> None:
    """Validate a single finding."""
    required = [
        "id", "category", "severity", "location",
        "title", "current_value", "proposed_value",
        "rationale", "evidence_refs", "auto_approved",
    ]
    for field_name in required:
        if field_name not in finding:
            violations.append(f"Finding[{index}]: missing required field '{field_name}'")

    if "category" in finding:
        valid_cats = {c.value for c in FindingCategory}
        if finding["category"] not in valid_cats:
            violations.append(f"Finding[{index}]: invalid category '{finding['category']}'")

    if "severity" in finding:
        valid_sev = {s.value for s in Severity}
        if finding["severity"] not in valid_sev:
            violations.append(f"Finding[{index}]: invalid severity '{finding['severity']}'")

    if "evidence_refs" in finding:
        refs = finding["evidence_refs"]
        if not isinstance(refs, list) or len(refs) == 0:
            violations.append(f"Finding[{index}]: evidence_refs must be non-empty list")


def validate_decision_receipt(data: dict[str, Any]) -> list[str]:
    """Validate a decision receipt against the schema."""
    violations: list[str] = []

    for field_name in ["review_id", "reviewer", "timestamp", "decisions"]:
        if field_name not in data:
            violations.append(f"Missing required field: {field_name}")

    if "decisions" in data:
        if not isinstance(data["decisions"], list):
            violations.append("decisions must be a list")
        elif len(data["decisions"]) == 0:
            violations.append("decisions must contain at least one decision")
        else:
            valid_dec = {d.value for d in Decision}
            valid_reasons = {r.value for r in RejectionReason}
            for i, d in enumerate(data["decisions"]):
                if "finding_id" not in d:
                    violations.append(f"Decision[{i}]: missing finding_id")
                if "decision" not in d:
                    violations.append(f"Decision[{i}]: missing decision")
                elif d["decision"] not in valid_dec:
                    violations.append(f"Decision[{i}]: invalid decision '{d['decision']}'")
                if d.get("decision") == "modified" and not d.get("modified_value"):
                    violations.append(
                        f"Decision[{i}]: decision=modified requires modified_value"
                    )
                if d.get("decision") == "rejected":
                    reason = d.get("rejection_reason")
                    if not reason:
                        violations.append(
                            f"Decision[{i}]: decision=rejected requires rejection_reason"
                        )
                    elif reason not in valid_reasons:
                        violations.append(
                            f"Decision[{i}]: invalid rejection_reason '{reason}'"
                        )
                    elif reason != RejectionReason.INSUFFICIENT_EVIDENCE.value:
                        correction = d.get("human_correction", "")
                        if len(correction) < 10:
                            violations.append(
                                f"Decision[{i}]: rejected decision requires "
                                "human_correction with at least 10 characters"
                            )

    return violations


# ═══════════════════════════════════════════════════════════════════
# Helpers — packet/receipt creation
# ═══════════════════════════════════════════════════════════════════


def make_review_id(review_type: ReviewType, domain_or_dataset: str,
                   version: int = 1, sequence: int = 1) -> str:
    """Generate a standardized review_id."""
    return f"{review_type.value}_{domain_or_dataset.lower()}_v{version}_{sequence:03d}"


def make_finding_id(index: int) -> str:
    """Generate a standardized finding ID."""
    return f"F-{index + 1:03d}"


def new_review_packet(
    review_type: ReviewType,
    source_documents: list[str],
    agent_summary: str,
    generated_by: str,
    findings: list[ReviewFinding] | None = None,
    urgency: Urgency = Urgency.NORMAL,
    domain_or_dataset: str = "review",
    version: int = 1,
) -> ReviewPacket:
    """Create a new ReviewPacket with standardized IDs."""
    packet = ReviewPacket(
        review_id=make_review_id(review_type, domain_or_dataset, version),
        review_type=review_type,
        source_documents=source_documents,
        agent_summary=agent_summary,
        findings=findings or [],
        urgency=urgency,
        generated_by=generated_by,
        auto_approved_count=sum(1 for f in (findings or []) if f.auto_approved),
    )
    return packet
