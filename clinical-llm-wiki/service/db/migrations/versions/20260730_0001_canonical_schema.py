"""Create the canonical knowledge application schema.

Revision ID: 20260730_0001
Revises:
Create Date: 2026-07-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id(name: str) -> sa.Column:
    return sa.Column(name, sa.String(length=160), nullable=False)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def upgrade() -> None:
    # pgvector is a declared baseline capability. A PostgreSQL instance without
    # the extension must fail here instead of silently pretending semantic
    # indexing is available.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sources",
        _id("source_id"),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=False),
        sa.Column("owner_org", sa.String(length=240), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("source_id", name=op.f("pk_sources")),
    )
    op.create_table(
        "source_versions",
        _id("source_version_id"),
        sa.Column("source_id", sa.String(length=160), nullable=False),
        sa.Column("version", sa.String(length=120), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("rights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("data_boundary", sa.String(length=40), nullable=False),
        sa.Column(
            "status",
            sa.String(length=40),
            server_default=sa.text("'registered'"),
            nullable=False,
        ),
        sa.Column("effective_date", sa.Date(), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "data_boundary IN "
            "('local_processing_only', 'enterprise_provider_only', "
            "'external_allowed', 'prohibited')",
            name=op.f("ck_source_versions_data_boundary"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.source_id"],
            name=op.f("fk_source_versions_source_id_sources"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("source_version_id", name=op.f("pk_source_versions")),
        sa.UniqueConstraint(
            "source_id", "version", "sha256", name="source_version_hash"
        ),
    )
    op.create_index(
        "ix_source_versions_source_id_version",
        "source_versions",
        ["source_id", "version"],
        unique=False,
    )
    op.create_table(
        "source_artifacts",
        _id("artifact_id"),
        sa.Column("source_version_id", sa.String(length=160), nullable=False),
        sa.Column("artifact_kind", sa.String(length=60), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "size_bytes >= 0",
            name=op.f("ck_source_artifacts_size_bytes_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["source_versions.source_version_id"],
            name=op.f("fk_source_artifacts_source_version_id_source_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("artifact_id", name=op.f("pk_source_artifacts")),
        sa.UniqueConstraint(
            "source_version_id", "sha256", name="source_artifact_hash"
        ),
    )
    op.create_table(
        "processing_runs",
        _id("run_id"),
        sa.Column("source_version_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("requested_by_subject", sa.String(length=255), nullable=False),
        sa.Column("failure_code", sa.String(length=120), nullable=True),
        _created_at(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'author_confirmation_required', "
            "'review_required', 'approved', 'release_blocked', 'released', "
            "'failed', 'cancelled')",
            name=op.f("ck_processing_runs_status"),
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["source_versions.source_version_id"],
            name=op.f("fk_processing_runs_source_version_id_source_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_processing_runs")),
    )
    op.create_index(
        "ix_processing_runs_status_created_at",
        "processing_runs",
        ["status", "created_at"],
        unique=False,
    )
    op.create_table(
        "job_steps",
        _id("step_id"),
        sa.Column("run_id", sa.String(length=160), nullable=False),
        sa.Column("step_key", sa.String(length=160), nullable=False),
        sa.Column("pool", sa.String(length=40), nullable=False),
        sa.Column(
            "status",
            sa.String(length=40),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column(
            "depends_on",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("input_sha256", sa.String(length=64), nullable=True),
        sa.Column("output_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "checkpoint", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        _created_at(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "pool IN ('document', 'enrichment', 'release')",
            name=op.f("ck_job_steps_pool"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["processing_runs.run_id"],
            name=op.f("fk_job_steps_run_id_processing_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("step_id", name=op.f("pk_job_steps")),
        sa.UniqueConstraint("run_id", "step_key", name="run_step_key"),
        sa.UniqueConstraint("step_id", "run_id", name="step_run_identity"),
    )
    op.create_index(
        "ix_job_steps_run_id_status",
        "job_steps",
        ["run_id", "status"],
        unique=False,
    )
    op.create_table(
        "step_attempts",
        _id("attempt_id"),
        sa.Column("run_id", sa.String(length=160), nullable=False),
        sa.Column("step_id", sa.String(length=160), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("previous_attempt_id", sa.String(length=160), nullable=True),
        sa.Column(
            "status",
            sa.String(length=40),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_sha256", sa.String(length=64), nullable=False),
        sa.Column("output_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "checkpoint", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "artifact_manifest",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error_type", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at(),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "attempt_number >= 1",
            name=op.f("ck_step_attempts_attempt_number_positive"),
        ),
        sa.CheckConstraint(
            "(attempt_number = 1 AND previous_attempt_id IS NULL) OR "
            "(attempt_number > 1 AND previous_attempt_id IS NOT NULL)",
            name=op.f("ck_step_attempts_attempt_lineage"),
        ),
        sa.ForeignKeyConstraint(
            ["previous_attempt_id"],
            ["step_attempts.attempt_id"],
            name=op.f("fk_step_attempts_previous_attempt_id_step_attempts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["step_id", "run_id"],
            ["job_steps.step_id", "job_steps.run_id"],
            name=op.f("fk_step_attempts_step_id_job_steps"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("attempt_id", name=op.f("pk_step_attempts")),
        sa.UniqueConstraint(
            "step_id", "attempt_number", name="step_attempt_number"
        ),
        sa.UniqueConstraint(
            "attempt_id",
            "step_id",
            "run_id",
            "attempt_number",
            name="attempt_context_identity",
        ),
    )
    op.create_index(
        "ix_step_attempts_status_lease",
        "step_attempts",
        ["status", "leased_until"],
        unique=False,
    )
    op.create_table(
        "model_profiles",
        sa.Column("profile_id", sa.String(length=160), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=240), nullable=False),
        sa.Column("deployment_class", sa.String(length=40), nullable=False),
        sa.Column("secret_ref", sa.String(length=500), nullable=False),
        sa.Column("endpoint_ref", sa.String(length=500), nullable=True),
        sa.Column(
            "allowed_data_boundaries",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column(
            "cost_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        _created_at(),
        sa.CheckConstraint(
            "deployment_class IN ('enterprise_managed', 'external_api')",
            name=op.f("ck_model_profiles_deployment_class"),
        ),
        sa.CheckConstraint(
            "secret_ref ~ '^(env|secret)://'",
            name=op.f("ck_model_profiles_secret_reference"),
        ),
        sa.CheckConstraint(
            "endpoint_ref IS NULL OR endpoint_ref ~ '^(env|secret)://'",
            name=op.f("ck_model_profiles_endpoint_reference"),
        ),
        sa.CheckConstraint(
            "timeout_seconds >= 1",
            name=op.f("ck_model_profiles_timeout_positive"),
        ),
        sa.CheckConstraint(
            "max_output_tokens >= 1",
            name=op.f("ck_model_profiles_max_output_tokens_positive"),
        ),
        sa.PrimaryKeyConstraint(
            "profile_id", "version", name=op.f("pk_model_profiles")
        ),
    )
    op.create_table(
        "prompt_profiles",
        sa.Column("profile_id", sa.String(length=160), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("system_template", sa.Text(), nullable=False),
        sa.Column("output_schema_id", sa.String(length=240), nullable=False),
        sa.Column(
            "output_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("output_schema_sha256", sa.String(length=64), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint(
            "profile_id", "version", name=op.f("pk_prompt_profiles")
        ),
    )
    op.create_table(
        "model_invocations",
        _id("invocation_id"),
        sa.Column("run_id", sa.String(length=160), nullable=False),
        sa.Column("step_id", sa.String(length=160), nullable=False),
        sa.Column("attempt_id", sa.String(length=160), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("previous_attempt_id", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("model_profile_id", sa.String(length=160), nullable=False),
        sa.Column("model_profile_version", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=240), nullable=False),
        sa.Column("prompt_profile_id", sa.String(length=160), nullable=False),
        sa.Column("prompt_profile_version", sa.String(length=80), nullable=False),
        sa.Column("output_schema_sha256", sa.String(length=64), nullable=False),
        sa.Column("data_boundary", sa.String(length=40), nullable=False),
        sa.Column("input_sha256", sa.String(length=64), nullable=False),
        sa.Column("output_sha256", sa.String(length=64), nullable=True),
        sa.Column("provider_request_id", sa.String(length=500), nullable=True),
        sa.Column(
            "prompt_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "completion_tokens",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "total_tokens", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("cost_usd", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_type", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "status IN ('succeeded', 'failed', 'replayed')",
            name=op.f("ck_model_invocations_status"),
        ),
        sa.CheckConstraint(
            "prompt_tokens >= 0 AND completion_tokens >= 0 AND total_tokens >= 0",
            name=op.f("ck_model_invocations_token_usage_nonnegative"),
        ),
        sa.CheckConstraint(
            "cost_usd IS NULL OR cost_usd >= 0",
            name=op.f("ck_model_invocations_cost_nonnegative"),
        ),
        sa.CheckConstraint(
            "latency_ms >= 0",
            name=op.f("ck_model_invocations_latency_nonnegative"),
        ),
        sa.CheckConstraint(
            "((status IN ('succeeded', 'replayed')) "
            "AND output IS NOT NULL AND output_sha256 IS NOT NULL "
            "AND error_type IS NULL AND error_message IS NULL) OR "
            "(status = 'failed' AND output IS NULL AND output_sha256 IS NULL "
            "AND error_type IS NOT NULL AND error_message IS NOT NULL)",
            name=op.f("ck_model_invocations_status_shape"),
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id", "step_id", "run_id", "attempt_number"],
            [
                "step_attempts.attempt_id",
                "step_attempts.step_id",
                "step_attempts.run_id",
                "step_attempts.attempt_number",
            ],
            name=op.f("fk_model_invocations_attempt_id_step_attempts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_profile_id", "model_profile_version"],
            ["model_profiles.profile_id", "model_profiles.version"],
            name=op.f("fk_model_invocations_model_profile_id_model_profiles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_profile_id", "prompt_profile_version"],
            ["prompt_profiles.profile_id", "prompt_profiles.version"],
            name=op.f("fk_model_invocations_prompt_profile_id_prompt_profiles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("invocation_id", name=op.f("pk_model_invocations")),
    )
    op.create_index(
        "ix_model_invocations_attempt_id_created_at",
        "model_invocations",
        ["attempt_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "evidence",
        _id("evidence_id"),
        sa.Column("source_version_id", sa.String(length=160), nullable=False),
        sa.Column("source_artifact_id", sa.String(length=160), nullable=True),
        sa.Column("evidence_type", sa.String(length=80), nullable=False),
        sa.Column("locator", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("locator_sha256", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"],
            ["source_artifacts.artifact_id"],
            name=op.f("fk_evidence_source_artifact_id_source_artifacts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"],
            ["source_versions.source_version_id"],
            name=op.f("fk_evidence_source_version_id_source_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("evidence_id", name=op.f("pk_evidence")),
        sa.UniqueConstraint(
            "source_version_id",
            "content_sha256",
            "locator_sha256",
            name="source_locator_hash",
        ),
    )
    op.create_index(
        "ix_evidence_source_version_id_type",
        "evidence",
        ["source_version_id", "evidence_type"],
        unique=False,
    )
    op.create_table(
        "knowledge_candidates",
        _id("candidate_id"),
        sa.Column("run_id", sa.String(length=160), nullable=False),
        sa.Column(
            "revision_number", sa.Integer(), server_default=sa.text("1"), nullable=False
        ),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("knowledge_type", sa.String(length=100), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "applicability", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "exceptions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("author_subject", sa.String(length=255), nullable=True),
        _created_at(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revision_number >= 1",
            name=op.f("ck_knowledge_candidates_revision_number_positive"),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_knowledge_candidates_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["processing_runs.run_id"],
            name=op.f("fk_knowledge_candidates_run_id_processing_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "candidate_id", name=op.f("pk_knowledge_candidates")
        ),
    )
    op.create_index(
        "ix_knowledge_candidates_status_updated_at",
        "knowledge_candidates",
        ["status", "updated_at"],
        unique=False,
    )
    op.create_table(
        "candidate_evidence",
        sa.Column("candidate_id", sa.String(length=160), nullable=False),
        sa.Column("evidence_id", sa.String(length=160), nullable=False),
        sa.Column(
            "evidence_role",
            sa.String(length=60),
            server_default=sa.text("'supports'"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["knowledge_candidates.candidate_id"],
            name=op.f("fk_candidate_evidence_candidate_id_knowledge_candidates"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["evidence.evidence_id"],
            name=op.f("fk_candidate_evidence_evidence_id_evidence"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "candidate_id", "evidence_id", name=op.f("pk_candidate_evidence")
        ),
    )
    op.create_table(
        "knowledge_units",
        _id("knowledge_unit_id"),
        sa.Column("stable_key", sa.String(length=300), nullable=False),
        sa.Column("knowledge_type", sa.String(length=100), nullable=False),
        _created_at(),
        sa.PrimaryKeyConstraint(
            "knowledge_unit_id", name=op.f("pk_knowledge_units")
        ),
        sa.UniqueConstraint(
            "stable_key", name=op.f("uq_knowledge_units_stable_key")
        ),
    )
    op.create_table(
        "knowledge_revisions",
        _id("knowledge_revision_id"),
        sa.Column("knowledge_unit_id", sa.String(length=160), nullable=False),
        sa.Column("candidate_id", sa.String(length=160), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "applicability", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "exceptions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.CheckConstraint(
            "revision_number >= 1",
            name=op.f("ck_knowledge_revisions_revision_number_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["knowledge_candidates.candidate_id"],
            name=op.f("fk_knowledge_revisions_candidate_id_knowledge_candidates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_unit_id"],
            ["knowledge_units.knowledge_unit_id"],
            name=op.f("fk_knowledge_revisions_knowledge_unit_id_knowledge_units"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "knowledge_revision_id", name=op.f("pk_knowledge_revisions")
        ),
        sa.UniqueConstraint(
            "knowledge_unit_id", "revision_number", name="unit_revision"
        ),
    )
    op.create_index(
        "ix_knowledge_revisions_status_created_at",
        "knowledge_revisions",
        ["status", "created_at"],
        unique=False,
    )
    op.create_table(
        "knowledge_relations",
        _id("relation_id"),
        sa.Column("source_revision_id", sa.String(length=160), nullable=False),
        sa.Column("relation_type", sa.String(length=100), nullable=False),
        sa.Column("target_knowledge_unit_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column(
            "provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["source_revision_id"],
            ["knowledge_revisions.knowledge_revision_id"],
            name=op.f(
                "fk_knowledge_relations_source_revision_id_knowledge_revisions"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_knowledge_unit_id"],
            ["knowledge_units.knowledge_unit_id"],
            name=op.f(
                "fk_knowledge_relations_target_knowledge_unit_id_knowledge_units"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "relation_id", name=op.f("pk_knowledge_relations")
        ),
        sa.UniqueConstraint(
            "source_revision_id",
            "relation_type",
            "target_knowledge_unit_id",
            name="knowledge_relation_edge",
        ),
    )
    op.create_index(
        "ix_knowledge_relations_target_type",
        "knowledge_relations",
        ["target_knowledge_unit_id", "relation_type"],
        unique=False,
    )
    op.create_table(
        "review_decisions",
        _id("decision_id"),
        sa.Column("candidate_id", sa.String(length=160), nullable=False),
        sa.Column("knowledge_revision_id", sa.String(length=160), nullable=True),
        sa.Column("decision", sa.String(length=60), nullable=False),
        sa.Column("actor_subject", sa.String(length=255), nullable=False),
        sa.Column("actor_role", sa.String(length=80), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "invalidated_step_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        _created_at(),
        sa.CheckConstraint(
            "decision IN "
            "('author_confirmed', 'approved', 'rejected', 'changes_requested')",
            name=op.f("ck_review_decisions_decision"),
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["knowledge_candidates.candidate_id"],
            name=op.f("fk_review_decisions_candidate_id_knowledge_candidates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_revision_id"],
            ["knowledge_revisions.knowledge_revision_id"],
            name=op.f(
                "fk_review_decisions_knowledge_revision_id_knowledge_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "decision_id", name=op.f("pk_review_decisions")
        ),
    )
    op.create_index(
        "ix_review_decisions_candidate_id_created_at",
        "review_decisions",
        ["candidate_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "releases",
        _id("release_id"),
        sa.Column("version", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("previous_release_id", sa.String(length=160), nullable=True),
        sa.Column("manifest_object_key", sa.String(length=1024), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("db_schema_revision", sa.String(length=120), nullable=False),
        sa.Column(
            "knowledge_contract_version", sa.String(length=120), nullable=False
        ),
        sa.Column("parser_profile_version", sa.String(length=120), nullable=False),
        sa.Column("model_profile_version", sa.String(length=120), nullable=False),
        sa.Column("prompt_profile_version", sa.String(length=120), nullable=False),
        sa.Column("index_manifest_version", sa.String(length=120), nullable=False),
        sa.Column("release_manager_subject", sa.String(length=255), nullable=True),
        _created_at(),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["previous_release_id"],
            ["releases.release_id"],
            name=op.f("fk_releases_previous_release_id_releases"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("release_id", name=op.f("pk_releases")),
        sa.UniqueConstraint("version", name="release_version"),
    )
    op.create_index(
        "ix_releases_status_published_at",
        "releases",
        ["status", "published_at"],
        unique=False,
    )
    op.create_table(
        "evaluation_runs",
        _id("evaluation_run_id"),
        sa.Column("release_id", sa.String(length=160), nullable=True),
        sa.Column("suite_version", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["releases.release_id"],
            name=op.f("fk_evaluation_runs_release_id_releases"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "evaluation_run_id", name=op.f("pk_evaluation_runs")
        ),
    )
    op.create_table(
        "index_manifests",
        _id("index_manifest_id"),
        sa.Column("release_id", sa.String(length=160), nullable=True),
        sa.Column("version", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column(
            "capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["releases.release_id"],
            name=op.f("fk_index_manifests_release_id_releases"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint(
            "index_manifest_id", name=op.f("pk_index_manifests")
        ),
    )
    op.create_table(
        "release_items",
        sa.Column("release_id", sa.String(length=160), nullable=False),
        sa.Column("knowledge_revision_id", sa.String(length=160), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["knowledge_revision_id"],
            ["knowledge_revisions.knowledge_revision_id"],
            name=op.f(
                "fk_release_items_knowledge_revision_id_knowledge_revisions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["release_id"],
            ["releases.release_id"],
            name=op.f("fk_release_items_release_id_releases"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "release_id", "knowledge_revision_id", name=op.f("pk_release_items")
        ),
    )
    op.create_table(
        "audit_events",
        _id("audit_event_id"),
        sa.Column("actor_subject", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=160), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=160), nullable=False),
        sa.Column("run_id", sa.String(length=160), nullable=True),
        sa.Column(
            "details", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["processing_runs.run_id"],
            name=op.f("fk_audit_events_run_id_processing_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("audit_event_id", name=op.f("pk_audit_events")),
    )
    op.create_index(
        "ix_audit_events_entity_created_at",
        "audit_events",
        ["entity_type", "entity_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Keep the shared vector extension installed. Removing a database extension
    # may destroy objects outside this application; the schema downgrade only
    # removes objects owned by this revision.
    for table_name in (
        "audit_events",
        "release_items",
        "index_manifests",
        "evaluation_runs",
        "releases",
        "review_decisions",
        "knowledge_relations",
        "knowledge_revisions",
        "knowledge_units",
        "candidate_evidence",
        "knowledge_candidates",
        "evidence",
        "model_invocations",
        "prompt_profiles",
        "model_profiles",
        "step_attempts",
        "job_steps",
        "processing_runs",
        "source_artifacts",
        "source_versions",
        "sources",
    ):
        op.drop_table(table_name)
