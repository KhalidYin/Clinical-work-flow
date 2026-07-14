from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class QueueKind(StrEnum):
    """Panel-owned queue classification, distinct from Review Protocol scope markers."""

    PLATFORM = "platform"
    WIKI = "wiki"
    STUDY = "study"


class ReviewLifecycleStatus(StrEnum):
    """Status derived from packet, decision receipt, and confirmation files."""

    PENDING = "pending"
    DECIDED_WAITING_CONFIRMATION = "decided_waiting_confirmation"
    CONFIRMED = "confirmed"
    INVALID = "invalid"
    PARTIAL = "partial"


class ReviewPanelErrorCode(StrEnum):
    CONFIG_ERROR = "config_error"
    SCHEMA_ERROR = "schema_error"
    QUEUE_NOT_FOUND = "queue_not_found"
    QUEUE_INVALID = "queue_invalid"
    REVIEW_NOT_FOUND = "review_not_found"
    REVIEW_INVALID = "review_invalid"
    PACKET_CHANGED = "packet_changed"
    RECEIPT_EXISTS = "receipt_exists"
    PATH_FORBIDDEN = "path_forbidden"


@dataclass(frozen=True)
class QueueRegistration:
    """Trusted queue discovered by server-side allowlist."""

    queue_id: str
    queue_kind: QueueKind
    owner_label: str
    owner_root: Path
    queue_path: Path
    protocol_scope: str | None = None
    marker_path: Path | None = None

    def to_public_dict(self) -> dict[str, str | None]:
        return {
            "queue_id": self.queue_id,
            "queue_kind": self.queue_kind.value,
            "owner_label": self.owner_label,
            "protocol_scope": self.protocol_scope,
        }


@dataclass(frozen=True)
class ReviewListItem:
    queue_id: str
    queue_kind: QueueKind
    review_id: str
    review_type: str
    urgency: str
    created_at: str
    status: ReviewLifecycleStatus
    actionable_findings: int
    total_findings: int
    auto_approved_count: int


@dataclass(frozen=True)
class SourceAvailability:
    index: int
    declared_path: str
    available: bool
    reason: str | None = None


@dataclass(frozen=True)
class ReviewDetailContract:
    queue_id: str
    review_id: str
    packet_sha256: str
    status: ReviewLifecycleStatus
    packet: dict[str, Any]
    source_availability: list[SourceAvailability] = field(default_factory=list)
    decision_receipts: list[dict[str, Any]] = field(default_factory=list)
    confirmation_receipt: dict[str, Any] | None = None
    errors: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class DecisionSubmitContract:
    queue_id: str
    review_id: str
    packet_sha256: str
    reviewer: str
    reviewer_role: str | None
    decisions: list[dict[str, Any]]
    general_notes: str | None = None


def derive_review_status(
    *,
    packet_valid: bool,
    partial_errors: bool,
    decision_receipt_count: int,
    confirmation_present: bool,
) -> ReviewLifecycleStatus:
    """Derive display/API status from files without keeping a second state store."""

    if not packet_valid:
        return ReviewLifecycleStatus.INVALID
    if partial_errors:
        return ReviewLifecycleStatus.PARTIAL
    if confirmation_present:
        return ReviewLifecycleStatus.CONFIRMED
    if decision_receipt_count > 0:
        return ReviewLifecycleStatus.DECIDED_WAITING_CONFIRMATION
    return ReviewLifecycleStatus.PENDING

