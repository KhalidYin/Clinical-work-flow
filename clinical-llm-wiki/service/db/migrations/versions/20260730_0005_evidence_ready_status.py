"""Separate parsed Evidence readiness from Candidate author confirmation.

Revision ID: 20260730_0005
Revises: 20260730_0004
Create Date: 2026-07-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260730_0005"
down_revision: str | None = "20260730_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_STATUS_CONSTRAINT = "ck_processing_runs_status"
_EXPANDED_STATUS_CHECK = (
    "status IN ('queued', 'processing', 'evidence_ready', "
    "'author_confirmation_required', 'review_required', 'approved', "
    "'release_blocked', 'released', 'failed', 'cancelled')"
)
_PREVIOUS_STATUS_CHECK = (
    "status IN ('queued', 'processing', 'author_confirmation_required', "
    "'review_required', 'approved', 'release_blocked', 'released', "
    "'failed', 'cancelled')"
)


def upgrade() -> None:
    op.drop_constraint(op.f(_STATUS_CONSTRAINT), "processing_runs", type_="check")
    op.create_check_constraint(
        op.f(_STATUS_CONSTRAINT),
        "processing_runs",
        _EXPANDED_STATUS_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint(op.f(_STATUS_CONSTRAINT), "processing_runs", type_="check")
    op.create_check_constraint(
        op.f(_STATUS_CONSTRAINT),
        "processing_runs",
        _PREVIOUS_STATUS_CHECK,
    )
