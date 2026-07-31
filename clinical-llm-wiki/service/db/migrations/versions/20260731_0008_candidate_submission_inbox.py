"""Add the de-identified prerelease candidate-submission inbox.

Revision ID: 20260731_0008
Revises: 20260731_0007
Create Date: 2026-07-31
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260731_0008"
down_revision: str | None = "20260731_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candidate_submissions",
        sa.Column("submission_id", sa.String(length=160), nullable=False),
        sa.Column("submitted_by_actor_id", sa.String(length=160), nullable=False),
        sa.Column("submission_type", sa.String(length=60), nullable=False),
        sa.Column("origin_system", sa.String(length=160), nullable=False),
        sa.Column("origin_record_ref", sa.String(length=240), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("payload_sha256", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "submission_type IN ('correction', 'observation', 'rule_gap', 'proposed_rule')",
            name=op.f("ck_candidate_submissions_submission_type"),
        ),
        sa.CheckConstraint(
            "status IN ('received', 'triaged', 'rejected', 'promoted')",
            name=op.f("ck_candidate_submissions_submission_status"),
        ),
        sa.PrimaryKeyConstraint(
            "submission_id",
            name=op.f("pk_candidate_submissions"),
        ),
        sa.UniqueConstraint(
            "submitted_by_actor_id",
            "idempotency_key",
            name="candidate_submission_actor_idempotency",
        ),
    )
    op.create_index(
        "ix_candidate_submissions_status_created_at",
        "candidate_submissions",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_submissions_status_created_at",
        table_name="candidate_submissions",
    )
    op.drop_table("candidate_submissions")
