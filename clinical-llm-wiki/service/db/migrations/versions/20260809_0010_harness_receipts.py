"""P2-B3: persist supervisor and product validation receipts.

Revision ID: 20260809_0010
Revises: 20260805_0009
Create Date: 2026-08-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260809_0010"
down_revision: str | None = "20260805_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_invocations",
        sa.Column(
            "execution_receipt",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "model_invocations",
        sa.Column(
            "validation_receipt",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("model_invocations", "validation_receipt")
    op.drop_column("model_invocations", "execution_receipt")
