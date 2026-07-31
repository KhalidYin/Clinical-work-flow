"""Add advisory eligibility signals and model invocation lineage.

Revision ID: 20260731_0007
Revises: 20260730_0006
Create Date: 2026-07-31
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260731_0007"
down_revision: str | None = "20260730_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_candidates",
        sa.Column(
            "advisory_signals",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_candidates",
        sa.Column("origin_model_invocation_id", sa.String(length=160), nullable=True),
    )
    op.create_foreign_key(
        op.f(
            "fk_knowledge_candidates_origin_model_invocation_id_model_invocations"
        ),
        "knowledge_candidates",
        "model_invocations",
        ["origin_model_invocation_id"],
        ["invocation_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_knowledge_candidates_origin_model_invocation_id",
        "knowledge_candidates",
        ["origin_model_invocation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_candidates_origin_model_invocation_id",
        table_name="knowledge_candidates",
    )
    op.drop_constraint(
        op.f(
            "fk_knowledge_candidates_origin_model_invocation_id_model_invocations"
        ),
        "knowledge_candidates",
        type_="foreignkey",
    )
    op.drop_column("knowledge_candidates", "origin_model_invocation_id")
    op.drop_column("knowledge_candidates", "advisory_signals")
