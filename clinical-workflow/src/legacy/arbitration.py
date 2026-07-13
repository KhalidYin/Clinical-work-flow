"""
Arbitration — archived from src/agents/arbitration.py (v2.1).

When MainAgent and ReviewerAgent cannot reach consensus, this module
provides the human arbitration flow (Principles 3 and 6).

NOTE: ArbitrationItem was originally imported from review_package.py.
      It is inlined here since review_package.py has been retired.
"""

from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone


# ── ArbitrationItem (inlined from review_package.py) ──────────


@dataclass
class ArbitrationItem:
    """Dual-agent dispute item."""
    arbitration_id: str
    contested_item: str
    severity: str
    main_agent_position: dict
    reviewer_position: dict
    authoritative_reference: str
    recommendation: str = ""


# ── Arbitration Case ────────────────────────────────────────────


@dataclass
class ArbitrationCase:
    """
    Dispute requiring human adjudication.

    Displays:
      · MainAgent position + rationale + standard reference
      · ReviewerAgent position + rationale + standard reference
      · Authoritative standard reference
      · AI recommended direction
    """
    arbitration_id: str = ""
    stage: str = ""
    severity: str = ""
    rounds_attempted: int = 0

    # Contested content
    contested_item: str = ""

    # Positions of both parties (no reasoning process exposed)
    main_agent_position: dict = field(default_factory=dict)
    # { "value": ..., "rationale": ..., "standard_ref": ..., "confidence": ... }

    reviewer_position: dict = field(default_factory=dict)
    # { "value": ..., "rationale": ..., "standard_ref": ..., "confidence": ... }

    # Context to help humans decide
    authoritative_reference: str = ""   # Most authoritative standard source
    impact_assessment: str = ""         # Impact of different decisions
    ai_recommendation: str = ""         # AI's recommended direction

    # Decision result
    human_decision: str = ""            # "main" | "reviewer" | "custom"
    custom_value: Any = None
    decided_by: str = ""
    decided_at: str = ""
    rationale: str = ""

    @property
    def is_resolved(self) -> bool:
        return self.human_decision != "" and self.decided_by != ""

    def resolve(self, decision: str, decided_by: str,
                rationale: str = "", custom_value: Any = None) -> None:
        self.human_decision = decision
        self.decided_by = decided_by
        self.decided_at = datetime.now(timezone.utc).isoformat()
        self.rationale = rationale
        if custom_value is not None:
            self.custom_value = custom_value

    def display_for_human(self) -> dict[str, Any]:
        """Generate data for the human arbitration interface."""
        return {
            "arbitration_id": self.arbitration_id,
            "stage": self.stage,
            "severity": self.severity,
            "contested_item": self.contested_item,
            "main_agent": {
                "model": "claude-opus-4-7",
                "position": self.main_agent_position.get("value"),
                "rationale": self.main_agent_position.get("rationale"),
                "standard_reference": self.main_agent_position.get("standard_ref"),
            },
            "reviewer_agent": {
                "model": "claude-sonnet-4-6",
                "position": self.reviewer_position.get("value"),
                "rationale": self.reviewer_position.get("rationale"),
                "standard_reference": self.reviewer_position.get("standard_ref"),
            },
            "authoritative_reference": self.authoritative_reference,
            "impact_assessment": self.impact_assessment,
            "ai_recommendation": self.ai_recommendation,
            "decision_options": ["main", "reviewer", "custom"],
        }


# ── Arbitration History ─────────────────────────────────────────


@dataclass
class ArbitrationHistory:
    """
    Arbitration history knowledge base.
    Used to prevent duplicate disputes — similar cases can reference
    past decisions. But never auto-applied (each case still needs human judgment).
    """
    cases: list[ArbitrationCase] = field(default_factory=list)

    def add(self, case: ArbitrationCase) -> None:
        self.cases.append(case)

    def search(self, query: str) -> list[ArbitrationCase]:
        """Search related historical decisions."""
        return [c for c in self.cases
                if query.lower() in c.contested_item.lower()
                or query.lower() in c.stage.lower()]

    def get_stats(self) -> dict[str, Any]:
        resolved = [c for c in self.cases if c.is_resolved]
        return {
            "total_cases": len(self.cases),
            "resolved": len(resolved),
            "pending": len(self.cases) - len(resolved),
            "main_agent_wins": sum(1 for c in resolved if c.human_decision == "main"),
            "reviewer_wins": sum(1 for c in resolved if c.human_decision == "reviewer"),
            "custom_decisions": sum(1 for c in resolved if c.human_decision == "custom"),
        }


# ── Cross-Review Cycle Management ────────────────────────────────


MAX_REVIEW_ROUNDS = 2


@dataclass
class CrossReviewCycle:
    """
    Manages the MainAgent <-> ReviewerAgent review cycle.

    Flow:
      MainAgent output -> Reviewer review
      -> has Critical/Major -> MainAgent fix -> Reviewer re-review
      -> max 2 rounds
      -> after 2 rounds still unresolved -> trigger Arbitration
    """
    stage: str
    max_rounds: int = MAX_REVIEW_ROUNDS
    rounds_completed: int = 0
    issues_resolved: int = 0
    issues_remaining: int = 0

    def can_continue(self) -> bool:
        return self.rounds_completed < self.max_rounds and self.issues_remaining > 0

    def needs_arbitration(self) -> bool:
        return (self.rounds_completed >= self.max_rounds
                and self.issues_remaining > 0)

    def status_summary(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "rounds": self.rounds_completed,
            "max_rounds": self.max_rounds,
            "issues_resolved": self.issues_resolved,
            "issues_remaining": self.issues_remaining,
            "needs_arbitration": self.needs_arbitration(),
            "status": ("passed" if not self.needs_arbitration() and self.issues_remaining == 0
                       else "arbitration_needed" if self.needs_arbitration()
                       else "in_progress"),
        }
