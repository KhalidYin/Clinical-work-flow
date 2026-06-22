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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════════════════════════
# Enums — fixed vocabulary, no free text
# ═══════════════════════════════════════════════════════════════════


class ReviewType(StrEnum):
    """Fixed set of review types — each has its own rendering template in Review Panel."""
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


# ═══════════════════════════════════════════════════════════════════
# JSON Schema Definitions — the "format contract"
# ═══════════════════════════════════════════════════════════════════

# These schemas are used at the Agent SDK level (schema parameter)
# to enforce structure. The agent CANNOT produce output that violates
# these schemas — the API layer rejects it before it reaches the file.

REVIEW_FINDING_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://clinical-workflow/schemas/review-finding",
    "title": "ReviewFinding",
    "description": (
        "A single finding that requires human attention. "
        "Every field is required — the agent cannot skip any."
    ),
    "type": "object",
    "required": [
        "id", "category", "severity", "location",
        "title", "current_value", "proposed_value",
        "rationale", "evidence_refs", "auto_approved",
    ],
    "properties": {
        "id": {
            "type": "string",
            "description": "Unique finding identifier, e.g. F-001",
            "pattern": "^F-[0-9]{3,}$",
        },
        "category": {
            "type": "string",
            "enum": [c.value for c in FindingCategory],
            "description": "Fixed category — drives Review Panel filter tabs",
        },
        "severity": {
            "type": "string",
            "enum": [s.value for s in Severity],
            "description": "Critical=red/blocking, Warning=yellow, Info=blue/collapsed",
        },
        "location": {
            "type": "string",
            "description": "Precise location: file:line or dataset.variable",
            "minLength": 3,
        },
        "title": {
            "type": "string",
            "description": "One-line summary — human should understand at a glance",
            "minLength": 5,
            "maxLength": 200,
        },
        "current_value": {
            "type": "string",
            "description": "What's there now (or 'N/A' if new)",
        },
        "proposed_value": {
            "type": "string",
            "description": "What agent recommends",
        },
        "rationale": {
            "type": "string",
            "description": "Agent's reasoning with CDISC/regulatory citation",
            "minLength": 10,
        },
        "evidence_refs": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "At least one reference to a standard/rule (e.g. 'CDISC SDTMIG v3.4 §6.1')",
        },
        "auto_approved": {
            "type": "boolean",
            "default": False,
            "description": "True if agent auto-approved — hidden by default in panel",
        },
    },
    "additionalProperties": False,
}


REVIEW_PACKET_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://clinical-workflow/schemas/review-packet",
    "title": "ReviewPacket",
    "description": (
        "Complete review submission from agent to human. "
        "Contains all findings for one review cycle. "
        "Rendered as a single-page review form in Review Panel."
    ),
    "type": "object",
    "required": [
        "review_id", "review_type", "source_documents",
        "agent_summary", "findings", "urgency",
        "created_at", "generated_by", "auto_approved_count",
    ],
    "properties": {
        "review_id": {
            "type": "string",
            "description": "Unique review identifier, e.g. 'sdtm_ae_review_v2_001'",
            "pattern": "^[a-z]+_[a-z0-9_]+_v[0-9]+_[0-9]{3}$",
        },
        "review_type": {
            "type": "string",
            "enum": [r.value for r in ReviewType],
        },
        "source_documents": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "Files this review depends on (relative to project root)",
        },
        "agent_summary": {
            "type": "string",
            "description": (
                "Natural-language overview of what was done and why review is needed. "
                "Max 500 chars — shown at top of Review Panel as context."
            ),
            "minLength": 10,
            "maxLength": 500,
        },
        "findings": {
            "type": "array",
            "items": {"$ref": "#/$defs/review_finding"},
            "minItems": 1,
            "description": "At least one finding. Agent cannot submit empty review.",
        },
        "urgency": {
            "type": "string",
            "enum": [u.value for u in Urgency],
        },
        "created_at": {
            "type": "string",
            "format": "date-time",
        },
        "generated_by": {
            "type": "string",
            "description": "Agent name + model that generated this",
        },
        "auto_approved_count": {
            "type": "integer",
            "minimum": 0,
            "description": "How many decisions agent made automatically (for transparency)",
        },
    },
    "$defs": {
        "review_finding": REVIEW_FINDING_SCHEMA,
    },
    "additionalProperties": False,
}


DECISION_RECEIPT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://clinical-workflow/schemas/decision-receipt",
    "title": "DecisionReceipt",
    "description": (
        "Human's structured response to a ReviewPacket. "
        "One decision per finding. Generated by Review Panel on Submit."
    ),
    "type": "object",
    "required": ["review_id", "reviewer", "timestamp", "decisions"],
    "properties": {
        "review_id": {
            "type": "string",
            "description": "Matches the review_id of the ReviewPacket being responded to",
        },
        "reviewer": {
            "type": "string",
            "description": "Human reviewer identifier (name/email)",
            "minLength": 2,
        },
        "timestamp": {
            "type": "string",
            "format": "date-time",
        },
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["finding_id", "decision"],
                "properties": {
                    "finding_id": {"type": "string"},
                    "decision": {
                        "type": "string",
                        "enum": [d.value for d in Decision],
                    },
                    "modified_value": {
                        "type": "string",
                        "description": "Required if decision=modified, else null",
                    },
                    "rejection_reason": {
                        "type": "string",
                        "enum": [r.value for r in RejectionReason],
                        "description": "Required if decision=rejected",
                    },
                    "human_correction": {
                        "type": "string",
                        "minLength": 10,
                        "description": (
                            "Human correction or direction. Required for rejected "
                            "decisions unless rejection_reason=insufficient_evidence."
                        ),
                    },
                    "reference": {
                        "type": "string",
                        "description": "Optional authoritative source supplied by the reviewer",
                    },
                    "comment": {
                        "type": "string",
                        "maxLength": 500,
                        "description": "Optional context for agent",
                    },
                },
                "additionalProperties": False,
                "allOf": [
                    {
                        "if": {
                            "properties": {"decision": {"const": "modified"}},
                            "required": ["decision"],
                        },
                        "then": {
                            "required": ["modified_value"],
                            "properties": {
                                "modified_value": {"minLength": 1},
                            },
                        },
                    },
                    {
                        "if": {
                            "properties": {"decision": {"const": "rejected"}},
                            "required": ["decision"],
                        },
                        "then": {
                            "required": ["rejection_reason"],
                            "allOf": [
                                {
                                    "if": {
                                        "properties": {
                                            "rejection_reason": {
                                                "not": {"const": "insufficient_evidence"}
                                            }
                                        },
                                        "required": ["rejection_reason"],
                                    },
                                    "then": {"required": ["human_correction"]},
                                },
                            ],
                        },
                    },
                ],
            },
            "minItems": 1,
        },
        "general_notes": {
            "type": "string",
            "maxLength": 1000,
            "description": "Optional overall feedback",
        },
    },
    "additionalProperties": False,
}


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

    def to_dict(self) -> dict[str, Any]:
        return {
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

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "review_id": self.review_id,
            "reviewer": self.reviewer,
            "timestamp": self.timestamp,
            "decisions": [fd.to_dict() for fd in self.decisions],
        }
        if self.general_notes:
            d["general_notes"] = self.general_notes
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


class ReviewQueue:
    """
    File-system-based message queue for agent↔human review exchange.

    Directory structure:
      .review_queue/
        {review_id}.json          ← Agent writes ReviewPacket
        {review_id}_decision.json ← Human writes DecisionReceipt
        archive/                  ← Completed reviews moved here
    """

    def __init__(self, project_dir: str | Path) -> None:
        self.queue_dir = Path(project_dir) / ".review_queue"
        self.archive_dir = self.queue_dir / "archive"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    # ── Agent-side operations ─────────────────────────────────

    def submit_packet(self, packet: ReviewPacket) -> Path:
        """Agent submits a review packet. Returns path to written file."""
        filepath = self.queue_dir / f"{packet.review_id}.json"
        filepath.write_text(packet.to_json(), encoding="utf-8")
        return filepath

    def has_pending(self) -> bool:
        """Check if there are packets still awaiting human decision."""
        return len(self.pending_packets()) > 0

    def pending_packets(self) -> list[str]:
        """List review_ids that have a packet but no decision yet."""
        pending = []
        for p in sorted(self.queue_dir.glob("*.json")):
            if p.name.endswith("_decision.json"):
                continue
            decision_file = self.queue_dir / f"{p.stem}_decision.json"
            if not decision_file.exists():
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
            except (json.JSONDecodeError, KeyError):
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
        except (json.JSONDecodeError, KeyError):
            return None

    def submit_decision(self, receipt: DecisionReceipt) -> Path:
        """Human submits decision receipt. Returns path to written file."""
        filepath = self.queue_dir / f"{receipt.review_id}_decision.json"
        filepath.write_text(receipt.to_json(), encoding="utf-8")
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
        except (json.JSONDecodeError, KeyError):
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
        """Move completed packet+decision to archive."""
        packet_file = self.queue_dir / f"{review_id}.json"
        decision_file = self.queue_dir / f"{review_id}_decision.json"
        for f in [packet_file, decision_file]:
            if f.exists():
                f.rename(self.archive_dir / f.name)

    def list_archived(self) -> list[str]:
        """List all completed/archived review IDs."""
        return sorted({f.stem.replace("_decision", "")
                       for f in self.archive_dir.glob("*.json")
                       if not f.stem.endswith("_corrupt")})

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
