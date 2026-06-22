"""
Clinical Agent Runtime v3.0.

Agent-native architecture:
  - agent_loop   — Dynamic decision loop (replaces fixed pipeline)
  - router       — Context-aware capability routing
  - review_protocol — Structured Review Packet ↔ Decision Receipt protocol

Usage:
  python -m src.runtime.agent_loop --project-dir ./project \
      "Generate SDTM specs for Phase III NSCLC trial"
"""

from .agent_loop import AgentRuntime, LoopState, AgentAction
from .decision_application import (
    ApplicationResult,
    ApplicationStatus,
    ConfirmationReceipt,
    DecisionApplicationError,
    ReworkDirective,
    apply_decision_receipt,
)
from .router import Router, RouteResult, CAPABILITY_REGISTRY, parse_intent
from .review_protocol import (
    ReviewPacket, ReviewFinding,
    DecisionReceipt, FindingDecision,
    ReviewType, FindingCategory, Severity, Decision, RejectionReason, Urgency,
    ReviewQueue,
    REVIEW_PROTOCOL_SCHEMA, REVIEW_PACKET_SCHEMA, REVIEW_FINDING_SCHEMA,
    FINDING_DECISION_SCHEMA, DECISION_RECEIPT_SCHEMA, CONFIRMATION_RECEIPT_SCHEMA,
    OUTPUT_FORMAT_SPECS,
    validate_review_packet, validate_decision_receipt,
    new_review_packet, make_review_id, make_finding_id,
)

__all__ = [
    # Agent Runtime
    "AgentRuntime",
    "LoopState",
    "AgentAction",
    # Decision Application
    "ApplicationResult",
    "ApplicationStatus",
    "ConfirmationReceipt",
    "DecisionApplicationError",
    "ReworkDirective",
    "apply_decision_receipt",
    # Router
    "Router",
    "RouteResult",
    "CAPABILITY_REGISTRY",
    "parse_intent",
    # Review Protocol — Data Models
    "ReviewPacket",
    "ReviewFinding",
    "DecisionReceipt",
    "FindingDecision",
    # Review Protocol — Enums
    "ReviewType",
    "FindingCategory",
    "Severity",
    "Decision",
    "RejectionReason",
    "Urgency",
    # Review Protocol — Queue
    "ReviewQueue",
    # Review Protocol — Schemas
    "REVIEW_PROTOCOL_SCHEMA",
    "REVIEW_PACKET_SCHEMA",
    "REVIEW_FINDING_SCHEMA",
    "FINDING_DECISION_SCHEMA",
    "DECISION_RECEIPT_SCHEMA",
    "CONFIRMATION_RECEIPT_SCHEMA",
    "OUTPUT_FORMAT_SPECS",
    # Review Protocol — Validation
    "validate_review_packet",
    "validate_decision_receipt",
    # Review Protocol — Helpers
    "new_review_packet",
    "make_review_id",
    "make_finding_id",
]
