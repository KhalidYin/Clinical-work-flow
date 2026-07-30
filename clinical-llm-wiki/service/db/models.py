"""Canonical database entities for evidence, governance, and durable processing."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def _text_id() -> Mapped[str]:
    return mapped_column(String(160), primary_key=True)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlatformUser(Base):
    __tablename__ = "platform_users"
    __table_args__ = (
        CheckConstraint(
            "identity_source IN ('local_test', 'oidc')",
            name="identity_source",
        ),
        CheckConstraint("status IN ('active', 'disabled')", name="user_status"),
        UniqueConstraint("issuer", "subject", name="identity_subject"),
        Index("ix_platform_users_status_updated_at", "status", "updated_at"),
    )

    user_id: Mapped[str] = _text_id()
    identity_source: Mapped[str] = mapped_column(String(40), nullable=False)
    issuer: Mapped[str] = mapped_column(String(500), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    display_name: Mapped[str] = mapped_column(String(240), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    last_authenticated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RoleBinding(Base):
    __tablename__ = "role_bindings"
    __table_args__ = (
        CheckConstraint(
            "role IN ('platform_admin', 'knowledge_curator', 'reviewer', "
            "'release_manager', 'consumer')",
            name="product_role",
        ),
        PrimaryKeyConstraint("user_id", "role"),
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("platform_users.user_id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(80), nullable=False)
    granted_by_actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class ServiceAccount(Base):
    __tablename__ = "service_accounts"
    __table_args__ = (
        CheckConstraint(
            "worker_pool IN ('document', 'enrichment', 'release')",
            name="worker_pool",
        ),
        CheckConstraint(
            "secret_ref ~ '^(env|secret)://[A-Za-z0-9_./-]+$'",
            name="secret_ref",
        ),
        CheckConstraint("status IN ('active', 'disabled')", name="account_status"),
        Index("ix_service_accounts_pool_status", "worker_pool", "status"),
    )

    service_account_id: Mapped[str] = _text_id()
    display_name: Mapped[str] = mapped_column(String(240), nullable=False)
    worker_pool: Mapped[str] = mapped_column(String(40), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    secret_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_by_actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Source(Base):
    __tablename__ = "sources"

    source_id: Mapped[str] = _text_id()
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    owner_org: Mapped[str | None] = mapped_column(String(240))
    created_at: Mapped[datetime] = _created_at()


class SourceVersion(Base):
    __tablename__ = "source_versions"
    __table_args__ = (
        CheckConstraint(
            "data_boundary IN "
            "('local_processing_only', 'enterprise_provider_only', "
            "'external_allowed', 'prohibited')",
            name="data_boundary",
        ),
        UniqueConstraint(
            "source_id",
            "version",
            name="uq_source_versions_source_version",
        ),
        UniqueConstraint("source_id", "version", "sha256", name="source_version_hash"),
        Index("ix_source_versions_source_id_version", "source_id", "version"),
    )

    source_version_id: Mapped[str] = _text_id()
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.source_id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    rights: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    data_boundary: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="registered")
    effective_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = _created_at()


class SourceArtifact(Base):
    __tablename__ = "source_artifacts"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="size_bytes_nonnegative"),
        CheckConstraint(
            "artifact_kind IN ('original', 'canonical_source', 'parser_output')",
            name="artifact_kind",
        ),
        CheckConstraint(
            "status IN ('available', 'quarantined', 'missing')",
            name="status",
        ),
        CheckConstraint(
            "(artifact_kind IN ('original', 'canonical_source') "
            "AND parent_artifact_id IS NULL "
            "AND parser_profile_version IS NULL) OR "
            "(artifact_kind = 'parser_output' AND parent_artifact_id IS NOT NULL "
            "AND parser_profile_version IS NOT NULL)",
            name="lineage_shape",
        ),
        UniqueConstraint("source_version_id", "sha256", name="source_artifact_hash"),
        UniqueConstraint(
            "object_key",
            name="uq_source_artifacts_object_key",
        ),
    )

    artifact_id: Mapped[str] = _text_id()
    source_version_id: Mapped[str] = mapped_column(
        ForeignKey("source_versions.source_version_id", ondelete="RESTRICT"), nullable=False
    )
    artifact_kind: Mapped[str] = mapped_column(String(60), nullable=False)
    parent_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_artifacts.artifact_id", ondelete="RESTRICT")
    )
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    parser_profile_version: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="available")
    created_at: Mapped[datetime] = _created_at()


class ObjectWriteIntent(Base):
    __tablename__ = "object_write_intents"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('raw_source', 'parser_output')",
            name="purpose",
        ),
        CheckConstraint("size_bytes >= 0", name="size_bytes_nonnegative"),
        CheckConstraint(
            "status IN ('pending', 'object_written', 'committed', "
            "'compensation_required', 'compensated', 'failed')",
            name="status",
        ),
        UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="uq_object_write_intents_actor_idempotency",
        ),
        UniqueConstraint(
            "object_key",
            name="uq_object_write_intents_object_key",
        ),
        Index("ix_object_write_intents_status_updated_at", "status", "updated_at"),
    )

    write_intent_id: Mapped[str] = _text_id()
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    owner_type: Mapped[str] = mapped_column(String(60), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(160), nullable=False)
    source_id: Mapped[str] = mapped_column(String(160), nullable=False)
    source_version_id: Mapped[str] = mapped_column(String(160), nullable=False)
    source_version_label: Mapped[str] = mapped_column(String(120), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProcessingRun(Base):
    __tablename__ = "processing_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'processing', 'author_confirmation_required', "
            "'review_required', 'approved', 'release_blocked', 'released', "
            "'failed', 'cancelled')",
            name="status",
        ),
        Index("ix_processing_runs_status_created_at", "status", "created_at"),
    )

    run_id: Mapped[str] = _text_id()
    source_version_id: Mapped[str] = mapped_column(
        ForeignKey("source_versions.source_version_id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_by_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobStep(Base):
    __tablename__ = "job_steps"
    __table_args__ = (
        CheckConstraint(
            "pool IN ('document', 'enrichment', 'release')",
            name="pool",
        ),
        CheckConstraint(
            "status IN ('queued', 'processing', 'succeeded', 'failed', 'cancelled')",
            name="status",
        ),
        CheckConstraint("checkpoint IS NULL", name="attempt_checkpoint_authority"),
        UniqueConstraint("run_id", "step_key", name="run_step_key"),
        UniqueConstraint("step_id", "run_id", name="step_run_identity"),
        Index("ix_job_steps_run_id_status", "run_id", "status"),
    )

    step_id: Mapped[str] = _text_id()
    run_id: Mapped[str] = mapped_column(
        ForeignKey("processing_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    step_key: Mapped[str] = mapped_column(String(160), nullable=False)
    pool: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="queued")
    depends_on: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    input_sha256: Mapped[str | None] = mapped_column(String(64))
    output_sha256: Mapped[str | None] = mapped_column(String(64))
    checkpoint: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class StepAttempt(Base):
    __tablename__ = "step_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["step_id", "run_id"],
            ["job_steps.step_id", "job_steps.run_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("attempt_number >= 1", name="attempt_number_positive"),
        CheckConstraint(
            "(attempt_number = 1 AND previous_attempt_id IS NULL) OR "
            "(attempt_number > 1 AND previous_attempt_id IS NOT NULL)",
            name="attempt_lineage",
        ),
        CheckConstraint(
            "status IN ('queued', 'leased', 'succeeded', 'failed', 'expired', 'cancelled')",
            name="status",
        ),
        CheckConstraint(
            "(status = 'queued' AND worker_id IS NULL AND leased_until IS NULL "
            "AND started_at IS NULL AND completed_at IS NULL) OR "
            "(status = 'leased' AND worker_id IS NOT NULL AND leased_until IS NOT NULL "
            "AND started_at IS NOT NULL AND completed_at IS NULL) OR "
            "(status IN ('succeeded', 'failed', 'expired', 'cancelled') "
            "AND leased_until IS NULL AND completed_at IS NOT NULL)",
            name="status_shape",
        ),
        UniqueConstraint("step_id", "attempt_number", name="step_attempt_number"),
        UniqueConstraint(
            "attempt_id",
            "step_id",
            "run_id",
            "attempt_number",
            name="attempt_context_identity",
        ),
        Index("ix_step_attempts_status_lease", "status", "leased_until"),
    )

    attempt_id: Mapped[str] = _text_id()
    run_id: Mapped[str] = mapped_column(String(160), nullable=False)
    step_id: Mapped[str] = mapped_column(String(160), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("step_attempts.attempt_id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="queued")
    worker_id: Mapped[str | None] = mapped_column(String(255))
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    output_sha256: Mapped[str | None] = mapped_column(String(64))
    checkpoint: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    artifact_manifest: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    error_type: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelProfile(Base):
    __tablename__ = "model_profiles"
    __table_args__ = (
        PrimaryKeyConstraint("profile_id", "version"),
        CheckConstraint(
            "deployment_class IN ('enterprise_managed', 'external_api')",
            name="deployment_class",
        ),
        CheckConstraint(
            "secret_ref ~ '^(env|secret)://'",
            name="secret_reference",
        ),
        CheckConstraint(
            "endpoint_ref IS NULL OR endpoint_ref ~ '^(env|secret)://'",
            name="endpoint_reference",
        ),
        CheckConstraint("timeout_seconds >= 1", name="timeout_positive"),
        CheckConstraint("max_output_tokens >= 1", name="max_output_tokens_positive"),
    )

    profile_id: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(240), nullable=False)
    deployment_class: Mapped[str] = mapped_column(String(40), nullable=False)
    secret_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    endpoint_ref: Mapped[str | None] = mapped_column(String(500))
    allowed_data_boundaries: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_policy: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = _created_at()


class PromptProfile(Base):
    __tablename__ = "prompt_profiles"
    __table_args__ = (PrimaryKeyConstraint("profile_id", "version"),)

    profile_id: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    system_template: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema_id: Mapped[str] = mapped_column(String(240), nullable=False)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_schema_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class ModelInvocation(Base):
    __tablename__ = "model_invocations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["attempt_id", "step_id", "run_id", "attempt_number"],
            [
                "step_attempts.attempt_id",
                "step_attempts.step_id",
                "step_attempts.run_id",
                "step_attempts.attempt_number",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["model_profile_id", "model_profile_version"],
            ["model_profiles.profile_id", "model_profiles.version"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["prompt_profile_id", "prompt_profile_version"],
            ["prompt_profiles.profile_id", "prompt_profiles.version"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('succeeded', 'failed', 'replayed')",
            name="status",
        ),
        CheckConstraint(
            "prompt_tokens >= 0 AND completion_tokens >= 0 AND total_tokens >= 0",
            name="token_usage_nonnegative",
        ),
        CheckConstraint(
            "cost_usd IS NULL OR cost_usd >= 0",
            name="cost_nonnegative",
        ),
        CheckConstraint("latency_ms >= 0", name="latency_nonnegative"),
        CheckConstraint(
            "((status IN ('succeeded', 'replayed')) "
            "AND output IS NOT NULL AND output_sha256 IS NOT NULL "
            "AND error_type IS NULL AND error_message IS NULL) OR "
            "(status = 'failed' AND output IS NULL AND output_sha256 IS NULL "
            "AND error_type IS NOT NULL AND error_message IS NOT NULL)",
            name="status_shape",
        ),
        Index("ix_model_invocations_attempt_id_created_at", "attempt_id", "created_at"),
    )

    invocation_id: Mapped[str] = _text_id()
    run_id: Mapped[str] = mapped_column(String(160), nullable=False)
    step_id: Mapped[str] = mapped_column(String(160), nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(160), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_attempt_id: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    model_profile_id: Mapped[str] = mapped_column(String(160), nullable=False)
    model_profile_version: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(240), nullable=False)
    prompt_profile_id: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_profile_version: Mapped[str] = mapped_column(String(80), nullable=False)
    output_schema_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    data_boundary: Mapped[str] = mapped_column(String(40), nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    output_sha256: Mapped[str | None] = mapped_column(String(64))
    provider_request_id: Mapped[str | None] = mapped_column(String(500))
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    error_type: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        UniqueConstraint(
            "source_version_id", "content_sha256", "locator_sha256", name="source_locator_hash"
        ),
        Index("ix_evidence_source_version_id_type", "source_version_id", "evidence_type"),
    )

    evidence_id: Mapped[str] = _text_id()
    source_version_id: Mapped[str] = mapped_column(
        ForeignKey("source_versions.source_version_id", ondelete="RESTRICT"), nullable=False
    )
    source_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_artifacts.artifact_id", ondelete="RESTRICT")
    )
    derived_artifact_id: Mapped[str] = mapped_column(
        ForeignKey("source_artifacts.artifact_id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_profile_version: Mapped[str] = mapped_column(String(120), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(80), nullable=False)
    locator: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    locator_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class KnowledgeCandidate(Base):
    __tablename__ = "knowledge_candidates"
    __table_args__ = (
        CheckConstraint("revision_number >= 1", name="revision_number_positive"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_range",
        ),
        Index("ix_knowledge_candidates_status_updated_at", "status", "updated_at"),
    )

    candidate_id: Mapped[str] = _text_id()
    run_id: Mapped[str] = mapped_column(
        ForeignKey("processing_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    knowledge_type: Mapped[str] = mapped_column(String(100), nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    applicability: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    exceptions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    author_subject: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CandidateEvidence(Base):
    __tablename__ = "candidate_evidence"
    __table_args__ = (PrimaryKeyConstraint("candidate_id", "evidence_id"),)

    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_candidates.candidate_id", ondelete="CASCADE"), nullable=False
    )
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey("evidence.evidence_id", ondelete="RESTRICT"), nullable=False
    )
    evidence_role: Mapped[str] = mapped_column(
        String(60), nullable=False, server_default="supports"
    )


class KnowledgeUnit(Base):
    __tablename__ = "knowledge_units"

    knowledge_unit_id: Mapped[str] = _text_id()
    stable_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    knowledge_type: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class KnowledgeRevision(Base):
    __tablename__ = "knowledge_revisions"
    __table_args__ = (
        CheckConstraint("revision_number >= 1", name="revision_number_positive"),
        UniqueConstraint("knowledge_unit_id", "revision_number", name="unit_revision"),
        Index("ix_knowledge_revisions_status_created_at", "status", "created_at"),
    )

    knowledge_revision_id: Mapped[str] = _text_id()
    knowledge_unit_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_units.knowledge_unit_id", ondelete="RESTRICT"), nullable=False
    )
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_candidates.candidate_id", ondelete="RESTRICT"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    applicability: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    exceptions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()


class KnowledgeRelation(Base):
    __tablename__ = "knowledge_relations"
    __table_args__ = (
        UniqueConstraint(
            "source_revision_id",
            "relation_type",
            "target_knowledge_unit_id",
            name="knowledge_relation_edge",
        ),
        Index("ix_knowledge_relations_target_type", "target_knowledge_unit_id", "relation_type"),
    )

    relation_id: Mapped[str] = _text_id()
    source_revision_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_revisions.knowledge_revision_id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_knowledge_unit_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_units.knowledge_unit_id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created_at()


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('author_confirmed', 'approved', 'rejected', 'changes_requested')",
            name="decision",
        ),
        Index("ix_review_decisions_candidate_id_created_at", "candidate_id", "created_at"),
    )

    decision_id: Mapped[str] = _text_id()
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_candidates.candidate_id", ondelete="RESTRICT"), nullable=False
    )
    knowledge_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_revisions.knowledge_revision_id", ondelete="RESTRICT")
    )
    decision: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(80), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    invalidated_step_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    created_at: Mapped[datetime] = _created_at()


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    evaluation_run_id: Mapped[str] = _text_id()
    release_id: Mapped[str | None] = mapped_column(
        ForeignKey("releases.release_id", ondelete="SET NULL")
    )
    suite_version: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    started_at: Mapped[datetime] = _created_at()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IndexManifest(Base):
    __tablename__ = "index_manifests"

    index_manifest_id: Mapped[str] = _text_id()
    release_id: Mapped[str | None] = mapped_column(
        ForeignKey("releases.release_id", ondelete="SET NULL")
    )
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created_at()


class Release(Base):
    __tablename__ = "releases"
    __table_args__ = (
        UniqueConstraint("version", name="release_version"),
        Index("ix_releases_status_published_at", "status", "published_at"),
    )

    release_id: Mapped[str] = _text_id()
    version: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    previous_release_id: Mapped[str | None] = mapped_column(
        ForeignKey("releases.release_id", ondelete="RESTRICT")
    )
    manifest_object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    db_schema_revision: Mapped[str] = mapped_column(String(120), nullable=False)
    knowledge_contract_version: Mapped[str] = mapped_column(String(120), nullable=False)
    parser_profile_version: Mapped[str] = mapped_column(String(120), nullable=False)
    model_profile_version: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_profile_version: Mapped[str] = mapped_column(String(120), nullable=False)
    index_manifest_version: Mapped[str] = mapped_column(String(120), nullable=False)
    release_manager_subject: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = _created_at()
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReleaseItem(Base):
    __tablename__ = "release_items"
    __table_args__ = (PrimaryKeyConstraint("release_id", "knowledge_revision_id"),)

    release_id: Mapped[str] = mapped_column(
        ForeignKey("releases.release_id", ondelete="CASCADE"), nullable=False
    )
    knowledge_revision_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_revisions.knowledge_revision_id", ondelete="RESTRICT"),
        nullable=False,
    )
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_entity_created_at", "entity_type", "entity_id", "created_at"),
    )

    audit_event_id: Mapped[str] = _text_id()
    actor_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(160), nullable=False)
    run_id: Mapped[str | None] = mapped_column(
        ForeignKey("processing_runs.run_id", ondelete="SET NULL")
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _created_at()
