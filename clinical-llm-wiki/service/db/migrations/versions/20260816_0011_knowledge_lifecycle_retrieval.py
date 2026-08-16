"""P17: add retrieval projection and knowledge rotation contracts.

Revision ID: 20260816_0011
Revises: 20260809_0010
Create Date: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260816_0011"
down_revision: str | None = "20260809_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chunk_profiles",
        sa.Column("chunk_profile_id", sa.String(length=160), nullable=False),
        sa.Column("version", sa.String(length=120), nullable=False),
        sa.Column("tokenizer_id", sa.String(length=240), nullable=False),
        sa.Column("target_min_tokens", sa.Integer(), nullable=False),
        sa.Column("target_max_tokens", sa.Integer(), nullable=False),
        sa.Column("hard_max_tokens", sa.Integer(), nullable=False),
        sa.Column("overlap_tokens", sa.Integer(), nullable=False),
        sa.Column("table_hard_max_tokens", sa.Integer(), nullable=False),
        sa.Column(
            "format_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "target_min_tokens > 0 AND target_min_tokens <= target_max_tokens "
            "AND target_max_tokens <= hard_max_tokens",
            name=op.f("ck_chunk_profiles_token_targets"),
        ),
        sa.CheckConstraint(
            "overlap_tokens >= 0 AND overlap_tokens < target_min_tokens",
            name=op.f("ck_chunk_profiles_overlap_tokens"),
        ),
        sa.CheckConstraint(
            "table_hard_max_tokens >= hard_max_tokens",
            name=op.f("ck_chunk_profiles_table_token_limit"),
        ),
        sa.PrimaryKeyConstraint("chunk_profile_id", name=op.f("pk_chunk_profiles")),
        sa.UniqueConstraint("version", name="chunk_profile_version"),
    )

    op.create_table(
        "retrieval_chunks",
        sa.Column("chunk_id", sa.String(length=160), nullable=False),
        sa.Column("chunk_profile_id", sa.String(length=160), nullable=False),
        sa.Column("source_version_id", sa.String(length=160), nullable=False),
        sa.Column("evidence_type", sa.String(length=80), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("locator", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("data_boundary", sa.String(length=40), nullable=False),
        sa.Column("rights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("ordinal >= 0", name=op.f("ck_retrieval_chunks_ordinal_nonnegative")),
        sa.CheckConstraint(
            "token_count > 0",
            name=op.f("ck_retrieval_chunks_token_count_positive"),
        ),
        sa.CheckConstraint(
            "data_boundary IN "
            "('local_processing_only', 'enterprise_provider_only', "
            "'external_allowed', 'prohibited')",
            name=op.f("ck_retrieval_chunks_data_boundary"),
        ),
        sa.ForeignKeyConstraint(
            ["chunk_profile_id"],
            ["chunk_profiles.chunk_profile_id"],
            name=op.f("fk_retrieval_chunks_chunk_profile_id_chunk_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["source_versions.source_version_id"],
            name=op.f("fk_retrieval_chunks_source_version_id_source_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("chunk_id", name=op.f("pk_retrieval_chunks")),
        sa.UniqueConstraint(
            "chunk_profile_id",
            "source_version_id",
            "ordinal",
            name="chunk_projection_ordinal",
        ),
    )
    op.create_index(
        "ix_retrieval_chunks_source_profile_ordinal",
        "retrieval_chunks",
        ["source_version_id", "chunk_profile_id", "ordinal"],
        unique=False,
    )

    op.create_table(
        "retrieval_chunk_evidence",
        sa.Column("chunk_id", sa.String(length=160), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.String(length=160), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("span_role", sa.String(length=40), nullable=False),
        sa.CheckConstraint(
            "position >= 0",
            name=op.f("ck_retrieval_chunk_evidence_position_nonnegative"),
        ),
        sa.CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset",
            name=op.f("ck_retrieval_chunk_evidence_span_offsets"),
        ),
        sa.CheckConstraint(
            "span_role IN ('primary', 'overlap')",
            name=op.f("ck_retrieval_chunk_evidence_span_role"),
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["retrieval_chunks.chunk_id"],
            name=op.f("fk_retrieval_chunk_evidence_chunk_id_retrieval_chunks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence.evidence_id"],
            name=op.f("fk_retrieval_chunk_evidence_evidence_id_evidence"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "chunk_id",
            "position",
            name=op.f("pk_retrieval_chunk_evidence"),
        ),
        sa.UniqueConstraint(
            "chunk_id",
            "evidence_id",
            "start_offset",
            "end_offset",
            "span_role",
            name="chunk_evidence_span",
        ),
    )

    op.create_table(
        "chunk_projection_findings",
        sa.Column("finding_id", sa.String(length=160), nullable=False),
        sa.Column("chunk_profile_id", sa.String(length=160), nullable=False),
        sa.Column("source_version_id", sa.String(length=160), nullable=False),
        sa.Column("evidence_id", sa.String(length=160), nullable=True),
        sa.Column("finding_type", sa.String(length=60), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "finding_type IN ('empty', 'duplicate', 'boilerplate', "
            "'oversize', 'boundary_violation')",
            name=op.f("ck_chunk_projection_findings_finding_type"),
        ),
        sa.ForeignKeyConstraint(
            ["chunk_profile_id"],
            ["chunk_profiles.chunk_profile_id"],
            name=op.f("fk_chunk_projection_findings_chunk_profile_id_chunk_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["source_versions.source_version_id"],
            name=op.f("fk_chunk_projection_findings_source_version_id_source_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence.evidence_id"],
            name=op.f("fk_chunk_projection_findings_evidence_id_evidence"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "finding_id",
            name=op.f("pk_chunk_projection_findings"),
        ),
    )
    op.create_index(
        "ix_chunk_projection_findings_source_profile",
        "chunk_projection_findings",
        ["source_version_id", "chunk_profile_id"],
        unique=False,
    )

    op.create_table(
        "impact_assessments",
        sa.Column("assessment_id", sa.String(length=160), nullable=False),
        sa.Column("from_source_version_id", sa.String(length=160), nullable=False),
        sa.Column("to_source_version_id", sa.String(length=160), nullable=False),
        sa.Column("comparison_profile_version", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_source_version_id <> to_source_version_id",
            name=op.f("ck_impact_assessments_distinct_source_versions"),
        ),
        sa.ForeignKeyConstraint(
            ["from_source_version_id"],
            ["source_versions.source_version_id"],
            name=op.f("fk_impact_assessments_from_source_version_id_source_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_source_version_id"],
            ["source_versions.source_version_id"],
            name=op.f("fk_impact_assessments_to_source_version_id_source_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("assessment_id", name=op.f("pk_impact_assessments")),
        sa.UniqueConstraint(
            "from_source_version_id",
            "to_source_version_id",
            "comparison_profile_version",
            name="source_version_comparison",
        ),
    )
    op.create_index(
        "ix_impact_assessments_to_version_created_at",
        "impact_assessments",
        ["to_source_version_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "evidence_impacts",
        sa.Column("evidence_impact_id", sa.String(length=160), nullable=False),
        sa.Column("assessment_id", sa.String(length=160), nullable=False),
        sa.Column("change_type", sa.String(length=40), nullable=False),
        sa.Column("from_evidence_id", sa.String(length=160), nullable=True),
        sa.Column("to_evidence_id", sa.String(length=160), nullable=True),
        sa.Column("mapping_basis", sa.String(length=60), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "change_type IN ('unchanged', 'moved', 'modified', 'added', "
            "'removed', 'rights_changed', 'ambiguous')",
            name=op.f("ck_evidence_impacts_change_type"),
        ),
        sa.CheckConstraint(
            "mapping_basis IN ('content_exact', 'locator_exact', "
            "'ordered_alignment', 'unmatched', 'ambiguous')",
            name=op.f("ck_evidence_impacts_mapping_basis"),
        ),
        sa.CheckConstraint(
            "(change_type = 'added' AND from_evidence_id IS NULL "
            "AND to_evidence_id IS NOT NULL) OR "
            "(change_type = 'removed' AND from_evidence_id IS NOT NULL "
            "AND to_evidence_id IS NULL) OR "
            "(change_type IN ('unchanged', 'moved', 'modified', 'rights_changed') "
            "AND from_evidence_id IS NOT NULL AND to_evidence_id IS NOT NULL) OR "
            "(change_type = 'ambiguous' "
            "AND (from_evidence_id IS NOT NULL OR to_evidence_id IS NOT NULL))",
            name=op.f("ck_evidence_impacts_evidence_mapping_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["impact_assessments.assessment_id"],
            name=op.f("fk_evidence_impacts_assessment_id_impact_assessments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["from_evidence_id"],
            ["evidence.evidence_id"],
            name=op.f("fk_evidence_impacts_from_evidence_id_evidence"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["to_evidence_id"],
            ["evidence.evidence_id"],
            name=op.f("fk_evidence_impacts_to_evidence_id_evidence"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("evidence_impact_id", name=op.f("pk_evidence_impacts")),
    )
    op.create_index(
        "ix_evidence_impacts_assessment_change",
        "evidence_impacts",
        ["assessment_id", "change_type"],
        unique=False,
    )

    op.create_table(
        "rotation_cases",
        sa.Column("rotation_case_id", sa.String(length=160), nullable=False),
        sa.Column("impact_assessment_id", sa.String(length=160), nullable=False),
        sa.Column("knowledge_revision_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("proposed_outcome", sa.String(length=40), nullable=True),
        sa.Column(
            "proposed_target_knowledge_revision_id",
            sa.String(length=160),
            nullable=True,
        ),
        sa.Column("proposed_by_actor_id", sa.String(length=160), nullable=True),
        sa.Column("proposal_idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("proposed_rationale", sa.Text(), nullable=True),
        sa.Column(
            "case_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column("included_release_id", sa.String(length=160), nullable=True),
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
            "status IN ('open', 'in_review', 'decided', 'included_in_release', 'closed')",
            name=op.f("ck_rotation_cases_status"),
        ),
        sa.CheckConstraint(
            "proposed_outcome IS NULL OR proposed_outcome IN "
            "('carry_forward', 'replace', 'retire', 'no_action')",
            name=op.f("ck_rotation_cases_proposed_outcome"),
        ),
        sa.CheckConstraint(
            "(proposed_outcome IS NULL AND "
            "proposed_target_knowledge_revision_id IS NULL AND "
            "proposed_by_actor_id IS NULL AND proposal_idempotency_key IS NULL) OR "
            "(proposed_outcome IN ('carry_forward', 'replace') AND "
            "proposed_target_knowledge_revision_id IS NOT NULL AND "
            "proposed_by_actor_id IS NOT NULL AND proposal_idempotency_key IS NOT NULL) OR "
            "(proposed_outcome IN ('retire', 'no_action') AND "
            "proposed_target_knowledge_revision_id IS NULL AND "
            "proposed_by_actor_id IS NOT NULL AND proposal_idempotency_key IS NOT NULL)",
            name=op.f("ck_rotation_cases_proposal_shape"),
        ),
        sa.CheckConstraint(
            "case_version >= 1",
            name=op.f("ck_rotation_cases_case_version_positive"),
        ),
        sa.CheckConstraint(
            "(status IN ('open', 'in_review') AND included_release_id IS NULL) OR "
            "(status = 'included_in_release' AND included_release_id IS NOT NULL) OR "
            "(status IN ('decided', 'closed'))",
            name=op.f("ck_rotation_cases_included_release_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["impact_assessment_id"],
            ["impact_assessments.assessment_id"],
            name=op.f("fk_rotation_cases_impact_assessment_id_impact_assessments"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_revision_id"],
            ["knowledge_revisions.knowledge_revision_id"],
            name=op.f("fk_rotation_cases_knowledge_revision_id_knowledge_revisions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["proposed_target_knowledge_revision_id"],
            ["knowledge_revisions.knowledge_revision_id"],
            name=op.f(
                "fk_rotation_cases_proposed_target_knowledge_revision_id_knowledge_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["included_release_id"],
            ["releases.release_id"],
            name=op.f("fk_rotation_cases_included_release_id_releases"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("rotation_case_id", name=op.f("pk_rotation_cases")),
        sa.UniqueConstraint(
            "impact_assessment_id",
            "knowledge_revision_id",
            name="assessment_revision_case",
        ),
        sa.UniqueConstraint(
            "proposed_by_actor_id",
            "proposal_idempotency_key",
            name="rotation_proposal_actor_idempotency",
        ),
    )
    op.create_index(
        "ix_rotation_cases_status_updated_at",
        "rotation_cases",
        ["status", "updated_at"],
        unique=False,
    )

    op.create_table(
        "rotation_decision_receipts",
        sa.Column("rotation_decision_id", sa.String(length=160), nullable=False),
        sa.Column("rotation_case_id", sa.String(length=160), nullable=False),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("expected_case_version", sa.Integer(), nullable=False),
        sa.Column("target_knowledge_revision_id", sa.String(length=160), nullable=True),
        sa.Column("actor_id", sa.String(length=160), nullable=False),
        sa.Column("actor_role", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome IN ('carry_forward', 'replace', 'retire', 'no_action')",
            name=op.f("ck_rotation_decision_receipts_outcome"),
        ),
        sa.CheckConstraint(
            "expected_case_version >= 1",
            name=op.f("ck_rotation_decision_receipts_case_version_positive"),
        ),
        sa.CheckConstraint(
            "actor_role = 'reviewer'",
            name=op.f("ck_rotation_decision_receipts_reviewer_role"),
        ),
        sa.CheckConstraint(
            "(outcome IN ('carry_forward', 'replace') "
            "AND target_knowledge_revision_id IS NOT NULL) OR "
            "(outcome IN ('retire', 'no_action') "
            "AND target_knowledge_revision_id IS NULL)",
            name=op.f("ck_rotation_decision_receipts_target_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["rotation_case_id"],
            ["rotation_cases.rotation_case_id"],
            name=op.f("fk_rotation_decision_receipts_rotation_case_id_rotation_cases"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_knowledge_revision_id"],
            ["knowledge_revisions.knowledge_revision_id"],
            name=op.f(
                "fk_rotation_decision_receipts_target_knowledge_revision_id_knowledge_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "rotation_decision_id",
            name=op.f("pk_rotation_decision_receipts"),
        ),
        sa.UniqueConstraint("rotation_case_id", name="case_decision"),
        sa.UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="rotation_actor_idempotency",
        ),
    )


def downgrade() -> None:
    op.drop_table("rotation_decision_receipts")
    op.drop_index("ix_rotation_cases_status_updated_at", table_name="rotation_cases")
    op.drop_table("rotation_cases")
    op.drop_index("ix_evidence_impacts_assessment_change", table_name="evidence_impacts")
    op.drop_table("evidence_impacts")
    op.drop_index(
        "ix_impact_assessments_to_version_created_at",
        table_name="impact_assessments",
    )
    op.drop_table("impact_assessments")
    op.drop_index(
        "ix_chunk_projection_findings_source_profile",
        table_name="chunk_projection_findings",
    )
    op.drop_table("chunk_projection_findings")
    op.drop_table("retrieval_chunk_evidence")
    op.drop_index(
        "ix_retrieval_chunks_source_profile_ordinal",
        table_name="retrieval_chunks",
    )
    op.drop_table("retrieval_chunks")
    op.drop_table("chunk_profiles")
