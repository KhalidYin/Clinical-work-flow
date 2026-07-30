"""Add Source Registry write intents and parser/evidence lineage.

Revision ID: 20260730_0004
Revises: 20260730_0003
Create Date: 2026-07-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0004"
down_revision: str | None = "20260730_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "object_write_intents",
        sa.Column("write_intent_id", sa.String(length=160), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("owner_type", sa.String(length=60), nullable=False),
        sa.Column("owner_id", sa.String(length=160), nullable=False),
        sa.Column("source_id", sa.String(length=160), nullable=False),
        sa.Column("source_version_id", sa.String(length=160), nullable=False),
        sa.Column("source_version_label", sa.String(length=120), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.String(length=160), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("failure_code", sa.String(length=120), nullable=True),
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
            "purpose IN ('raw_source', 'parser_output')",
            name=op.f("ck_object_write_intents_purpose"),
        ),
        sa.CheckConstraint(
            "size_bytes >= 0",
            name=op.f("ck_object_write_intents_size_bytes_nonnegative"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'object_written', 'committed', "
            "'compensation_required', 'compensated', 'failed')",
            name=op.f("ck_object_write_intents_status"),
        ),
        sa.PrimaryKeyConstraint(
            "write_intent_id",
            name=op.f("pk_object_write_intents"),
        ),
        sa.UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="uq_object_write_intents_actor_idempotency",
        ),
        sa.UniqueConstraint(
            "object_key",
            name="uq_object_write_intents_object_key",
        ),
    )
    op.create_index(
        "ix_object_write_intents_status_updated_at",
        "object_write_intents",
        ["status", "updated_at"],
        unique=False,
    )

    op.create_unique_constraint(
        "uq_source_versions_source_version",
        "source_versions",
        ["source_id", "version"],
    )
    op.add_column(
        "source_artifacts",
        sa.Column("parent_artifact_id", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "source_artifacts",
        sa.Column("parser_profile_version", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "source_artifacts",
        sa.Column(
            "status",
            sa.String(length=40),
            server_default="available",
            nullable=False,
        ),
    )
    op.create_foreign_key(
        op.f("fk_source_artifacts_parent_artifact_id_source_artifacts"),
        "source_artifacts",
        "source_artifacts",
        ["parent_artifact_id"],
        ["artifact_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        op.f("ck_source_artifacts_artifact_kind"),
        "source_artifacts",
        "artifact_kind IN ('original', 'canonical_source', 'parser_output')",
    )
    op.create_check_constraint(
        op.f("ck_source_artifacts_status"),
        "source_artifacts",
        "status IN ('available', 'quarantined', 'missing')",
    )
    op.create_check_constraint(
        op.f("ck_source_artifacts_lineage_shape"),
        "source_artifacts",
        "(artifact_kind IN ('original', 'canonical_source') "
        "AND parent_artifact_id IS NULL "
        "AND parser_profile_version IS NULL) OR "
        "(artifact_kind = 'parser_output' AND parent_artifact_id IS NOT NULL "
        "AND parser_profile_version IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_source_artifacts_object_key",
        "source_artifacts",
        ["object_key"],
    )

    op.add_column(
        "evidence",
        sa.Column("derived_artifact_id", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "evidence",
        sa.Column("source_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "evidence",
        sa.Column("parser_profile_version", sa.String(length=120), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_evidence_derived_artifact_id_source_artifacts"),
        "evidence",
        "source_artifacts",
        ["derived_artifact_id"],
        ["artifact_id"],
        ondelete="RESTRICT",
    )
    # P1 created no canonical Evidence rows. P4 legacy migration remains separate.
    op.alter_column("evidence", "derived_artifact_id", nullable=False)
    op.alter_column("evidence", "source_sha256", nullable=False)
    op.alter_column("evidence", "parser_profile_version", nullable=False)


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_evidence_derived_artifact_id_source_artifacts"),
        "evidence",
        type_="foreignkey",
    )
    op.drop_column("evidence", "parser_profile_version")
    op.drop_column("evidence", "source_sha256")
    op.drop_column("evidence", "derived_artifact_id")

    op.drop_constraint(
        "uq_source_artifacts_object_key",
        "source_artifacts",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_source_artifacts_lineage_shape"),
        "source_artifacts",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_source_artifacts_status"),
        "source_artifacts",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_source_artifacts_artifact_kind"),
        "source_artifacts",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_source_artifacts_parent_artifact_id_source_artifacts"),
        "source_artifacts",
        type_="foreignkey",
    )
    op.drop_column("source_artifacts", "status")
    op.drop_column("source_artifacts", "parser_profile_version")
    op.drop_column("source_artifacts", "parent_artifact_id")
    op.drop_constraint(
        "uq_source_versions_source_version",
        "source_versions",
        type_="unique",
    )
    op.drop_index(
        "ix_object_write_intents_status_updated_at",
        table_name="object_write_intents",
    )
    op.drop_table("object_write_intents")
