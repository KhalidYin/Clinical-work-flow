"""H0-F: record executor_kind on durable job steps.

Revision ID: 20260805_0009
Revises: 20260801_0008
Create Date: 2026-08-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260805_0009"
down_revision: str | None = "20260801_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job_steps",
        sa.Column(
            "executor_kind",
            sa.String(40),
            nullable=False,
            server_default="deterministic_handler",
        ),
    )
    # Backfill: existing enrichment steps are direct-model execution; document
    # steps stay deterministic_handler.
    op.execute(
        "UPDATE job_steps SET executor_kind = 'direct_model' "
        "WHERE step_key LIKE 'enrichment.%'"
    )
    op.create_check_constraint(
        op.f("ck_job_steps_executor_kind"),
        "job_steps",
        "executor_kind IN ('deterministic_handler', 'direct_model', 'harness')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_job_steps_executor_kind"), "job_steps", type_="check"
    )
    op.drop_column("job_steps", "executor_kind")
