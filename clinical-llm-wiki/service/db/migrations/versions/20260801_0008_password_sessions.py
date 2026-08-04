"""Add local password credentials and opaque browser sessions.

Revision ID: 20260801_0008
Revises: 20260731_0007
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260801_0008"
down_revision: str | None = "20260731_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_platform_users_identity_source"),
        "platform_users",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_platform_users_identity_source"),
        "platform_users",
        "identity_source IN ('local_password', 'local_test', 'oidc')",
    )
    op.create_table(
        "user_credentials",
        sa.Column("user_id", sa.String(length=160), nullable=False),
        sa.Column("username_normalized", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "failed_attempts",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "password_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "failed_attempts >= 0",
            name=op.f("ck_user_credentials_failed_attempts_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["platform_users.user_id"],
            name=op.f("fk_user_credentials_user_id_platform_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_credentials")),
        sa.UniqueConstraint("username_normalized", name="username_normalized"),
    )
    op.create_table(
        "browser_sessions",
        sa.Column("session_id_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=160), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at > created_at",
            name=op.f("ck_browser_sessions_expires_after_creation"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["platform_users.user_id"],
            name=op.f("fk_browser_sessions_user_id_platform_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("session_id_hash", name=op.f("pk_browser_sessions")),
    )
    op.create_index(
        "ix_browser_sessions_user_active",
        "browser_sessions",
        ["user_id", "expires_at", "revoked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_browser_sessions_user_active", table_name="browser_sessions")
    op.drop_table("browser_sessions")
    op.drop_table("user_credentials")
    op.drop_constraint(
        op.f("ck_platform_users_identity_source"),
        "platform_users",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_platform_users_identity_source"),
        "platform_users",
        "identity_source IN ('local_test', 'oidc')",
    )
