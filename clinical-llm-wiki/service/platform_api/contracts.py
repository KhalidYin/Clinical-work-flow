"""Pydantic DTOs owned by the P12 prerelease HTTP boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from service.auth import IdentitySource, Permission, PrincipalType, ProductRole


CONTRACT_VERSION = "knowledge-api.prerelease.v1"


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        extra="forbid",
        populate_by_name=True,
    )


class ResponseMeta(ApiModel):
    contract_version: Literal[CONTRACT_VERSION] = CONTRACT_VERSION
    fixture: Literal[False] = False
    generated_at: datetime


class SessionData(ApiModel):
    actor_id: str
    display_name: str
    principal_type: Literal[PrincipalType.HUMAN] = PrincipalType.HUMAN
    roles: list[ProductRole]
    organization: str
    permissions: list[Permission]


class PlatformHealthData(ApiModel):
    status: Literal["healthy", "degraded"]
    api: Literal["available", "degraded", "disabled"]
    database: Literal["available", "degraded", "disabled"]
    object_store: Literal["available", "degraded", "disabled"]
    semantic_index: Literal["available", "degraded", "disabled"]
    checked_at: datetime


class CurrentReleaseData(ApiModel):
    release_id: str | None
    version: str | None
    status: Literal["released", "not_released"]
    index_version: str | None
    released_at: datetime | None


class SourceSummaryData(ApiModel):
    source_id: str
    title: str
    version: str
    media_type: Literal["PDF", "DOCX", "XLSX", "Markdown"]
    rights: Literal["licensed", "internal", "restricted"]
    status: Literal[
        "registered",
        "processing",
        "candidate",
        "approved",
        "released",
        "restricted",
        "disabled",
    ]
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    updated_at: datetime


class ObjectReferenceData(ApiModel):
    object_key: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str
    size_bytes: int = Field(ge=0)
    artifact_role: Literal["original", "derived"]


class SourceRegistrationData(ApiModel):
    source_id: str
    source_version_id: str
    run_id: str
    status: Literal["queued"]
    original_object: ObjectReferenceData


class ProcessingAttemptData(ApiModel):
    attempt_id: str
    attempt_number: int = Field(ge=1)
    status: Literal["queued", "leased", "succeeded", "failed", "expired", "cancelled"]
    error_type: str | None
    checkpoint: dict[str, Any] | None
    artifact_count: int = Field(ge=0)


class ProcessingStepData(ApiModel):
    step_id: str
    step_key: str
    pool: Literal["document", "enrichment", "release"]
    status: Literal["queued", "processing", "succeeded", "failed", "cancelled"]
    depends_on: list[str]
    latest_attempt: ProcessingAttemptData


class ProcessingRunData(ApiModel):
    run_id: str
    source_version_id: str
    status: Literal[
        "queued",
        "processing",
        "evidence_ready",
        "author_confirmation_required",
        "review_required",
        "approved",
        "release_blocked",
        "released",
        "failed",
        "cancelled",
    ]
    created_at: datetime
    updated_at: datetime
    original_artifact_count: int = Field(ge=0)
    derived_artifact_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    steps: list[ProcessingStepData]


class ProcessingRunCollectionData(ApiModel):
    items: list[ProcessingRunData]
    total: int = Field(ge=0)
    partial: bool
    warnings: list[str]


class CandidateSummaryData(ApiModel):
    candidate_id: str
    candidate_group_id: str
    run_id: str
    revision_number: int = Field(ge=1)
    status: Literal[
        "author_confirmation_required",
        "author_confirmed",
        "superseded",
    ]
    knowledge_type: str
    claim: str
    scope: dict[str, Any]
    applicability: dict[str, Any]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_count: int = Field(ge=1)
    relation_proposal_count: int = Field(ge=0)
    author_actor_id: str | None
    knowledge_revision_id: str | None
    review_status: (
        Literal[
            "review_required",
            "approved",
            "rejected",
            "changes_requested",
            "released",
            "superseded",
            "retired",
        ]
        | None
    )


class CandidateEvidenceData(ApiModel):
    evidence_id: str
    source_version_id: str
    locator: dict[str, Any]
    content: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    rights: dict[str, Any]


class CandidateRelationProposalData(ApiModel):
    relation_type: Literal[
        "applies_to",
        "conflicts_with",
        "depends_on",
        "derived_from",
        "supersedes",
        "supports",
        "used_by",
    ]
    target_knowledge_unit_id: str
    evidence_ids: list[str]
    status: Literal["proposed", "accepted", "rejected", "superseded"]


class CandidateDetailData(CandidateSummaryData):
    parent_candidate_id: str | None
    conditions: list[dict[str, Any]]
    exceptions: list[dict[str, Any]]
    evidence: list[CandidateEvidenceData]
    relation_proposals: list[CandidateRelationProposalData]


class RelationEvidenceData(ApiModel):
    evidence_id: str
    source_version_id: str
    locator: dict[str, Any]
    content: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RelationNodeData(ApiModel):
    knowledge_unit_id: str
    stable_key: str
    knowledge_type: str
    knowledge_revision_id: str | None
    revision_number: int | None
    status: Literal[
        "unversioned",
        "review_required",
        "approved",
        "rejected",
        "changes_requested",
        "released",
        "superseded",
        "retired",
    ]
    claim: str | None
    release_ids: list[str]


class RelationEdgeData(ApiModel):
    relation_id: str
    source_knowledge_unit_id: str
    target_knowledge_unit_id: str
    relation_type: Literal[
        "applies_to",
        "conflicts_with",
        "depends_on",
        "derived_from",
        "supersedes",
        "supports",
        "used_by",
    ]
    status: str
    evidence: list[RelationEvidenceData] = Field(min_length=1)


class RelationQueryData(ApiModel):
    root_node_id: str | None
    requested_depth: int = Field(ge=0)
    applied_depth: int = Field(ge=0, le=2)
    nodes: list[RelationNodeData]
    edges: list[RelationEdgeData]
    total_nodes: int = Field(ge=0)
    truncated: bool
    partial: bool
    warnings: list[str]


class AuditVersionData(ApiModel):
    revision_number: int | None
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class AuditEventData(ApiModel):
    audit_event_id: str
    actor_id: str
    action: str
    object_type: str
    object_id: str
    run_id: str | None
    before_version: AuditVersionData | None
    after_version: AuditVersionData | None
    result: str | None
    correlation_id: str | None
    created_at: datetime


class AuditEventCollectionData(ApiModel):
    items: list[AuditEventData]
    total: int = Field(ge=0)
    next_cursor: str | None
    partial: bool
    warnings: list[str]


class CandidateCollectionData(ApiModel):
    items: list[CandidateSummaryData]
    total: int = Field(ge=0)
    partial: bool
    warnings: list[str]


class CandidateRevisionRequest(ApiModel):
    expected_revision_number: int = Field(ge=1)
    expected_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    claim: str = Field(min_length=1)
    scope: dict[str, Any] = Field(min_length=1)
    applicability: dict[str, Any] = Field(min_length=1)
    conditions: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    idempotency_key: str = Field(min_length=8, max_length=160)


class CandidateRevisionData(ApiModel):
    candidate_id: str
    parent_candidate_id: str
    revision_number: int = Field(ge=2)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["author_confirmation_required"]


class AuthorConfirmationRequest(ApiModel):
    expected_revision_number: int = Field(ge=1)
    expected_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=8, max_length=160)


class AuthorConfirmationData(ApiModel):
    candidate_id: str
    candidate_status: Literal["author_confirmed"]
    knowledge_revision_id: str
    revision_status: Literal["review_required"]
    decision_id: str


class ReviewDecisionRequest(ApiModel):
    candidate_id: str
    expected_revision_number: int = Field(ge=1)
    expected_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: Literal["approved", "rejected", "changes_requested"]
    idempotency_key: str = Field(min_length=8, max_length=160)
    rationale: str | None = Field(default=None, max_length=4000)


class ReviewDecisionData(ApiModel):
    candidate_id: str
    knowledge_revision_id: str
    revision_status: Literal["approved", "rejected", "changes_requested"]
    decision_id: str


class RetryData(ApiModel):
    run_id: str
    step_id: str
    attempt_id: str
    status: Literal["queued"] = "queued"


class CancelData(ApiModel):
    run_id: str
    status: Literal["cancelled"] = "cancelled"


class PlatformUserData(ApiModel):
    user_id: str
    display_name: str
    email: str
    identity_source: IdentitySource
    roles: list[ProductRole]
    status: Literal["active", "disabled"]
    last_active_at: datetime | None


class SourceCollectionData(ApiModel):
    items: list[SourceSummaryData]
    total: int = Field(ge=0)
    partial: bool
    warnings: list[str]


class UserCollectionData(ApiModel):
    items: list[PlatformUserData]
    total: int = Field(ge=0)
    partial: bool
    warnings: list[str]


class ErrorData(ApiModel):
    code: Literal[
        "authentication_required",
        "invalid_identity",
        "permission_denied",
        "service_unavailable",
        "registration_conflict",
        "invalid_source",
        "unsupported_media",
        "run_not_found",
        "retry_not_allowed",
        "candidate_not_found",
        "invalid_governance_transition",
        "stale_revision",
        "duplicate_decision",
    ]
    message: str


class SessionResponse(ApiModel):
    data: SessionData
    meta: ResponseMeta


class HealthResponse(ApiModel):
    data: PlatformHealthData
    meta: ResponseMeta


class CurrentReleaseResponse(ApiModel):
    data: CurrentReleaseData
    meta: ResponseMeta


class SourceCollectionResponse(ApiModel):
    data: SourceCollectionData
    meta: ResponseMeta


class SourceRegistrationResponse(ApiModel):
    data: SourceRegistrationData
    meta: ResponseMeta


class ProcessingRunResponse(ApiModel):
    data: ProcessingRunData
    meta: ResponseMeta


class ProcessingRunCollectionResponse(ApiModel):
    data: ProcessingRunCollectionData
    meta: ResponseMeta


class CandidateCollectionResponse(ApiModel):
    data: CandidateCollectionData
    meta: ResponseMeta


class CandidateDetailResponse(ApiModel):
    data: CandidateDetailData
    meta: ResponseMeta


class RelationQueryResponse(ApiModel):
    data: RelationQueryData
    meta: ResponseMeta


class AuditEventCollectionResponse(ApiModel):
    data: AuditEventCollectionData
    meta: ResponseMeta


class CandidateRevisionResponse(ApiModel):
    data: CandidateRevisionData
    meta: ResponseMeta


class AuthorConfirmationResponse(ApiModel):
    data: AuthorConfirmationData
    meta: ResponseMeta


class ReviewDecisionResponse(ApiModel):
    data: ReviewDecisionData
    meta: ResponseMeta


class RetryResponse(ApiModel):
    data: RetryData
    meta: ResponseMeta


class CancelResponse(ApiModel):
    data: CancelData
    meta: ResponseMeta


class UserCollectionResponse(ApiModel):
    data: UserCollectionData
    meta: ResponseMeta


class ErrorResponse(ApiModel):
    error: ErrorData
    meta: ResponseMeta
