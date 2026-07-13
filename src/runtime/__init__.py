"""
Clinical Agent Runtime v3.0.

Agent-native architecture:
  - pipeline_contract — Canonical fixed ten-stage machine contract
  - action_policy — Fail-closed capability/tool/executable authorization
  - agent_loop   — Fixed-pipeline runtime with dynamic review strategy
  - router       — Context-aware fixed-stage capability routing
  - review_protocol — Structured Review Packet ↔ Decision Receipt protocol

Usage:
  python -m src.runtime.agent_loop --project-dir ./project \
      "Generate SDTM specs for Phase III NSCLC trial"
"""

from .agent_loop import AgentRuntime, LoopState, AgentAction
from .action_policy import (
    DEFAULT_ACTION_POLICY,
    ActionPolicy,
    ActionPolicyError,
    ActionRequest,
    PolicyDecision,
    authorize_action,
    require_authorized_action,
)
from .decision_application import (
    ApplicationResult,
    ApplicationStatus,
    ConfirmationReceipt,
    DecisionApplicationError,
    ReworkDirective,
    apply_decision_receipt,
)
from .router import Router, RouteResult, CAPABILITY_REGISTRY, parse_intent
from .context_resolver import RuntimeContextError, RuntimeContextResolver
from .pipeline_contract import (
    CANONICAL_PIPELINE,
    CONTRACT_VERSION,
    CapabilityName,
    ExecutableName,
    PipelineContract,
    PipelineContractError,
    PipelineStage,
    ToolName,
)
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
    # Pipeline Contract
    "CANONICAL_PIPELINE",
    "CONTRACT_VERSION",
    "CapabilityName",
    "ExecutableName",
    "PipelineContract",
    "PipelineContractError",
    "PipelineStage",
    "ToolName",
    # Action Policy
    "DEFAULT_ACTION_POLICY",
    "ActionPolicy",
    "ActionPolicyError",
    "ActionRequest",
    "PolicyDecision",
    "authorize_action",
    "require_authorized_action",
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
    "RuntimeContextError",
    "RuntimeContextResolver",
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
