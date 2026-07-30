"""Enforce durable processing runtime status and checkpoint authority.

Revision ID: 20260730_0003
Revises: 20260730_0002
Create Date: 2026-07-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260730_0003"
down_revision: str | None = "20260730_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        op.f("ck_job_steps_status"),
        "job_steps",
        "status IN ('queued', 'processing', 'succeeded', 'failed', 'cancelled')",
    )
    op.create_check_constraint(
        op.f("ck_job_steps_attempt_checkpoint_authority"),
        "job_steps",
        "checkpoint IS NULL",
    )
    op.create_check_constraint(
        op.f("ck_step_attempts_status"),
        "step_attempts",
        "status IN ('queued', 'leased', 'succeeded', 'failed', 'expired', 'cancelled')",
    )
    op.create_check_constraint(
        op.f("ck_step_attempts_status_shape"),
        "step_attempts",
        "(status = 'queued' AND worker_id IS NULL AND leased_until IS NULL "
        "AND started_at IS NULL AND completed_at IS NULL) OR "
        "(status = 'leased' AND worker_id IS NOT NULL AND leased_until IS NOT NULL "
        "AND started_at IS NOT NULL AND completed_at IS NULL) OR "
        "(status IN ('succeeded', 'failed', 'expired', 'cancelled') "
        "AND leased_until IS NULL AND completed_at IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_step_attempts_status_shape"), "step_attempts", type_="check"
    )
    op.drop_constraint(op.f("ck_step_attempts_status"), "step_attempts", type_="check")
    op.drop_constraint(
        op.f("ck_job_steps_attempt_checkpoint_authority"),
        "job_steps",
        type_="check",
    )
    op.drop_constraint(op.f("ck_job_steps_status"), "job_steps", type_="check")
