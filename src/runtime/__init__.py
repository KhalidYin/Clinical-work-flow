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
from .router import Router, RouteResult, CAPABILITY_REGISTRY, parse_intent
from .review_protocol import (
    ReviewPacket, ReviewFinding,
    DecisionReceipt, FindingDecision,
    ReviewType, FindingCategory, Severity, Decision, Urgency,
    ReviewQueue,
    REVIEW_PACKET_SCHEMA, REVIEW_FINDING_SCHEMA, DECISION_RECEIPT_SCHEMA,
    OUTPUT_FORMAT_SPECS,
    validate_review_packet, validate_decision_receipt,
    new_review_packet, make_review_id, make_finding_id,
)

__all__ = [
    # Agent Runtime
    "AgentRuntime",
    "LoopState",
    "AgentAction",
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
    "Urgency",
    # Review Protocol — Queue
    "ReviewQueue",
    # Review Protocol — Schemas
    "REVIEW_PACKET_SCHEMA",
    "REVIEW_FINDING_SCHEMA",
    "DECISION_RECEIPT_SCHEMA",
    "OUTPUT_FORMAT_SPECS",
    # Review Protocol — Validation
    "validate_review_packet",
    "validate_decision_receipt",
    # Review Protocol — Helpers
    "new_review_packet",
    "make_review_id",
    "make_finding_id",
]
