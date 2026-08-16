"""P17: add a singleton current Release pointer.

Revision ID: 20260816_0012
Revises: 20260816_0011
Create Date: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260816_0012"
down_revision: str | None = "20260816_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "release_pointers",
        sa.Column("pointer_key", sa.String(length=40), nullable=False),
        sa.Column("current_release_id", sa.String(length=160), nullable=True),
        sa.Column(
            "pointer_version",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "pointer_key = 'current'",
            name=op.f("ck_release_pointers_singleton_key"),
        ),
        sa.CheckConstraint(
            "pointer_version >= 0",
            name=op.f("ck_release_pointers_pointer_version_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["current_release_id"],
            ["releases.release_id"],
            name=op.f("fk_release_pointers_current_release_id_releases"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("pointer_key", name=op.f("pk_release_pointers")),
    )
    op.execute(
        "INSERT INTO release_pointers "
        "(pointer_key, current_release_id, pointer_version) "
        "VALUES ('current', NULL, 0)"
    )
    op.execute(
        "UPDATE release_pointers SET current_release_id = ("
        "SELECT release_id FROM releases WHERE status = 'released' "
        "ORDER BY published_at DESC NULLS LAST, created_at DESC, release_id DESC "
        "LIMIT 1) WHERE pointer_key = 'current'"
    )


def downgrade() -> None:
    op.drop_table("release_pointers")
