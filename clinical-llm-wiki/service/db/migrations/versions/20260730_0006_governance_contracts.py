"""Expand candidate revision and two-person governance contracts.

Revision ID: 20260730_0006
Revises: 20260730_0005
Create Date: 2026-07-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0006"
down_revision: str | None = "20260730_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_candidates",
        sa.Column("candidate_group_id", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "knowledge_candidates",
        sa.Column("parent_candidate_id", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "knowledge_candidates",
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "knowledge_candidates",
        sa.Column("author_actor_id", sa.String(length=160), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_knowledge_candidates_parent_candidate_id_knowledge_candidates"),
        "knowledge_candidates",
        "knowledge_candidates",
        ["parent_candidate_id"],
        ["candidate_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        op.f("ck_knowledge_candidates_status"),
        "knowledge_candidates",
        "status IN ('author_confirmation_required', 'author_confirmed', 'superseded')",
    )
    op.create_check_constraint(
        op.f("ck_knowledge_candidates_revision_identity_shape"),
        "knowledge_candidates",
        "(candidate_group_id IS NULL AND content_sha256 IS NULL) OR "
        "(candidate_group_id IS NOT NULL AND content_sha256 IS NOT NULL)",
    )
    op.create_unique_constraint(
        "candidate_group_revision",
        "knowledge_candidates",
        ["candidate_group_id", "revision_number"],
    )

    op.add_column(
        "knowledge_revisions",
        sa.Column("author_actor_id", sa.String(length=160), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_knowledge_revisions_status"),
        "knowledge_revisions",
        "status IN ('review_required', 'approved', 'rejected', "
        "'changes_requested', 'released', 'superseded', 'retired')",
    )

    op.add_column(
        "review_decisions",
        sa.Column("candidate_revision_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "review_decisions",
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "review_decisions",
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_review_decisions_target_shape"),
        "review_decisions",
        "(decision = 'author_confirmed' AND knowledge_revision_id IS NULL) OR "
        "(decision IN ('approved', 'rejected', 'changes_requested') "
        "AND knowledge_revision_id IS NOT NULL)",
    )
    op.create_unique_constraint(
        "actor_idempotency",
        "review_decisions",
        ["actor_subject", "idempotency_key"],
    )
    op.create_index(
        "uq_review_decisions_author_confirmation",
        "review_decisions",
        ["candidate_id"],
        unique=True,
        postgresql_where=sa.text("decision = 'author_confirmed'"),
    )
    op.create_index(
        "uq_review_decisions_revision_decision",
        "review_decisions",
        ["knowledge_revision_id"],
        unique=True,
        postgresql_where=sa.text("knowledge_revision_id IS NOT NULL"),
    )

    op.create_table(
        "candidate_relation_proposals",
        sa.Column("proposal_id", sa.String(length=160), nullable=False),
        sa.Column("candidate_id", sa.String(length=160), nullable=False),
        sa.Column("relation_type", sa.String(length=100), nullable=False),
        sa.Column("target_knowledge_unit_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "relation_type IN ('applies_to', 'conflicts_with', 'depends_on', "
            "'derived_from', 'supersedes', 'supports', 'used_by')",
            name=op.f("ck_candidate_relation_proposals_relation_type"),
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'accepted', 'rejected', 'superseded')",
            name=op.f("ck_candidate_relation_proposals_status"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["knowledge_candidates.candidate_id"],
            name=op.f("fk_candidate_relation_proposals_candidate_id_knowledge_candidates"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_knowledge_unit_id"],
            ["knowledge_units.knowledge_unit_id"],
            name=op.f("fk_candidate_relation_proposals_target_knowledge_unit_id_knowledge_units"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "proposal_id",
            name=op.f("pk_candidate_relation_proposals"),
        ),
        sa.UniqueConstraint(
            "candidate_id",
            "relation_type",
            "target_knowledge_unit_id",
            name="candidate_relation_edge",
        ),
    )
    op.create_index(
        "ix_candidate_relation_proposals_candidate_status",
        "candidate_relation_proposals",
        ["candidate_id", "status"],
        unique=False,
    )
    op.create_table(
        "relation_proposal_evidence",
        sa.Column("proposal_id", sa.String(length=160), nullable=False),
        sa.Column("evidence_id", sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["candidate_relation_proposals.proposal_id"],
            name=op.f("fk_relation_proposal_evidence_proposal_id_candidate_relation_proposals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence.evidence_id"],
            name=op.f("fk_relation_proposal_evidence_evidence_id_evidence"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "proposal_id",
            "evidence_id",
            name=op.f("pk_relation_proposal_evidence"),
        ),
    )


def downgrade() -> None:
    op.drop_table("relation_proposal_evidence")
    op.drop_index(
        "ix_candidate_relation_proposals_candidate_status",
        table_name="candidate_relation_proposals",
    )
    op.drop_table("candidate_relation_proposals")

    op.drop_index(
        "uq_review_decisions_revision_decision",
        table_name="review_decisions",
    )
    op.drop_index(
        "uq_review_decisions_author_confirmation",
        table_name="review_decisions",
    )
    op.drop_constraint(
        "actor_idempotency",
        "review_decisions",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_review_decisions_target_shape"),
        "review_decisions",
        type_="check",
    )
    op.drop_column("review_decisions", "idempotency_key")
    op.drop_column("review_decisions", "content_sha256")
    op.drop_column("review_decisions", "candidate_revision_number")

    op.drop_constraint(
        op.f("ck_knowledge_revisions_status"),
        "knowledge_revisions",
        type_="check",
    )
    op.drop_column("knowledge_revisions", "author_actor_id")

    op.drop_constraint(
        "candidate_group_revision",
        "knowledge_candidates",
        type_="unique",
    )
    op.drop_constraint(
        op.f("ck_knowledge_candidates_revision_identity_shape"),
        "knowledge_candidates",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_knowledge_candidates_status"),
        "knowledge_candidates",
        type_="check",
    )
    op.drop_constraint(
        op.f("fk_knowledge_candidates_parent_candidate_id_knowledge_candidates"),
        "knowledge_candidates",
        type_="foreignkey",
    )
    op.drop_column("knowledge_candidates", "author_actor_id")
    op.drop_column("knowledge_candidates", "content_sha256")
    op.drop_column("knowledge_candidates", "parent_candidate_id")
    op.drop_column("knowledge_candidates", "candidate_group_id")
