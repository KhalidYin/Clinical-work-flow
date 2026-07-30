"""Add product identity, RBAC, and service-account records.

Revision ID: 20260730_0002
Revises: 20260730_0001
Create Date: 2026-07-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0002"
down_revision: str | None = "20260730_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "platform_users",
        sa.Column("user_id", sa.String(length=160), nullable=False),
        sa.Column("identity_source", sa.String(length=40), nullable=False),
        sa.Column("issuer", sa.String(length=500), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("display_name", sa.String(length=240), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column(
            "last_authenticated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        _created_at(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "identity_source IN ('local_test', 'oidc')",
            name=op.f("ck_platform_users_identity_source"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name=op.f("ck_platform_users_user_status"),
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_platform_users")),
        sa.UniqueConstraint("issuer", "subject", name="identity_subject"),
    )
    op.create_index(
        "ix_platform_users_status_updated_at",
        "platform_users",
        ["status", "updated_at"],
        unique=False,
    )

    op.create_table(
        "role_bindings",
        sa.Column("user_id", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=False),
        sa.Column("granted_by_actor_id", sa.String(length=160), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "role IN ('platform_admin', 'knowledge_curator', 'reviewer', "
            "'release_manager', 'consumer')",
            name=op.f("ck_role_bindings_product_role"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["platform_users.user_id"],
            name=op.f("fk_role_bindings_user_id_platform_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "role", name=op.f("pk_role_bindings")),
    )

    op.create_table(
        "service_accounts",
        sa.Column("service_account_id", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=240), nullable=False),
        sa.Column("worker_pool", sa.String(length=40), nullable=False),
        sa.Column(
            "scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("secret_ref", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_by_actor_id", sa.String(length=160), nullable=False),
        _created_at(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "worker_pool IN ('document', 'enrichment', 'release')",
            name=op.f("ck_service_accounts_worker_pool"),
        ),
        sa.CheckConstraint(
            "secret_ref ~ '^(env|secret)://[A-Za-z0-9_./-]+$'",
            name=op.f("ck_service_accounts_secret_ref"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name=op.f("ck_service_accounts_account_status"),
        ),
        sa.PrimaryKeyConstraint(
            "service_account_id",
            name=op.f("pk_service_accounts"),
        ),
    )
    op.create_index(
        "ix_service_accounts_pool_status",
        "service_accounts",
        ["worker_pool", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("service_accounts")
    op.drop_table("role_bindings")
    op.drop_table("platform_users")
