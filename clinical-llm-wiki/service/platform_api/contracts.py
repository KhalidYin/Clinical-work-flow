"""Pydantic DTOs owned by the P12 prerelease HTTP boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

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
    must_change_password: bool
    session_expires_at: datetime


class LoginRequest(ApiModel):
    username: str = Field(min_length=1, max_length=160)
    password: SecretStr


class PasswordChangeRequest(ApiModel):
    current_password: SecretStr
    new_password: SecretStr


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


class CandidateAdvisorySignalData(ApiModel):
    signal_type: Literal[
        "possible_duplicate",
        "possible_conflict",
        "explicit_gap",
    ]
    description: str
    target_knowledge_unit_id: str | None
    evidence_ids: list[str] = Field(min_length=1)


class CandidateDetailData(CandidateSummaryData):
    parent_candidate_id: str | None
    conditions: list[dict[str, Any]]
    exceptions: list[dict[str, Any]]
    evidence: list[CandidateEvidenceData]
    relation_proposals: list[CandidateRelationProposalData]
    advisory_signals: list[CandidateAdvisorySignalData]
    origin_model_invocation_id: str | None


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


class RotationProposalRequest(ApiModel):
    expected_case_version: int = Field(ge=1)
    outcome: Literal["carry_forward", "replace", "retire", "no_action"]
    target_knowledge_revision_id: str | None = Field(default=None, max_length=160)
    idempotency_key: str = Field(min_length=8, max_length=160)
    rationale: str | None = Field(default=None, max_length=4000)


class RotationDecisionRequest(RotationProposalRequest):
    pass


class RotationDecisionReceiptData(ApiModel):
    rotation_decision_id: str
    rotation_case_id: str
    outcome: Literal["carry_forward", "replace", "retire", "no_action"]
    expected_case_version: int = Field(ge=1)
    target_knowledge_revision_id: str | None
    actor_id: str
    actor_role: Literal["reviewer"]
    idempotency_key: str
    rationale: str | None
    created_at: datetime


class RotationCaseData(ApiModel):
    rotation_case_id: str
    impact_assessment_id: str
    knowledge_revision_id: str
    status: Literal["open", "in_review", "decided", "included_in_release", "closed"]
    change_types: list[
        Literal[
            "unchanged",
            "moved",
            "modified",
            "added",
            "removed",
            "rights_changed",
            "ambiguous",
        ]
    ]
    eligible_outcomes: list[Literal["carry_forward", "replace", "retire", "no_action"]]
    proposed_outcome: Literal["carry_forward", "replace", "retire", "no_action"] | None
    proposed_target_knowledge_revision_id: str | None
    proposed_by_actor_id: str | None
    proposed_rationale: str | None
    case_version: int = Field(ge=1)
    included_release_id: str | None
    released_in_release_ids: list[str]
    receipts: list[RotationDecisionReceiptData]
    allowed_actions: list[Literal["propose", "decide"]]
    created_at: datetime
    updated_at: datetime


class RotationCaseCollectionData(ApiModel):
    items: list[RotationCaseData]
    total: int = Field(ge=0)
    partial: bool
    warnings: list[str]


class RotationDecisionData(ApiModel):
    case: RotationCaseData
    receipt: RotationDecisionReceiptData


EvidenceChangeKey = Literal[
    "unchanged",
    "moved",
    "modified",
    "added",
    "removed",
    "rights_changed",
    "ambiguous",
]


class EvidenceImpactData(ApiModel):
    evidence_impact_id: str
    change_type: Literal[
        "unchanged",
        "moved",
        "modified",
        "added",
        "removed",
        "rights_changed",
        "ambiguous",
    ]
    from_evidence_id: str | None
    to_evidence_id: str | None
    mapping_basis: Literal[
        "content_exact",
        "locator_exact",
        "ordered_alignment",
        "unmatched",
        "ambiguous",
    ]
    details: dict[str, Any]


class ImpactAssessmentData(ApiModel):
    assessment_id: str
    from_source_version_id: str
    to_source_version_id: str
    comparison_profile_version: str
    change_counts: dict[EvidenceChangeKey, int]
    impacts: list[EvidenceImpactData]
    created_at: datetime


class ChunkProfileData(ApiModel):
    chunk_profile_id: str
    version: str
    tokenizer_id: str
    target_min_tokens: int = Field(gt=0)
    target_max_tokens: int = Field(gt=0)
    hard_max_tokens: int = Field(gt=0)
    overlap_tokens: int = Field(ge=0)
    table_hard_max_tokens: int = Field(gt=0)
    format_rules: dict[str, Any]


class ChunkEvidenceData(ApiModel):
    evidence_id: str
    source_version_id: str
    source_artifact_id: str
    evidence_type: str
    locator: dict[str, Any]
    content: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ChunkSpanData(ApiModel):
    evidence_id: str
    position: int = Field(ge=0)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    span_role: Literal["primary", "overlap"]


class RetrievalChunkData(ApiModel):
    chunk_id: str
    ordinal: int = Field(ge=0)
    evidence_type: str
    content: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    token_count: int = Field(gt=0)
    locator: dict[str, Any]
    data_boundary: Literal[
        "local_processing_only",
        "enterprise_provider_only",
        "external_allowed",
        "prohibited",
    ]
    rights: dict[str, Any]
    spans: list[ChunkSpanData]


class ChunkProjectionFindingData(ApiModel):
    finding_id: str
    evidence_id: str | None
    finding_type: Literal[
        "empty",
        "duplicate",
        "boilerplate",
        "oversize",
        "boundary_violation",
    ]
    details: dict[str, Any]


class ChunkProjectionData(ApiModel):
    run_id: str
    source_version_id: str
    chunk_profile: ChunkProfileData
    evidence: list[ChunkEvidenceData]
    chunks: list[RetrievalChunkData]
    findings: list[ChunkProjectionFindingData]


class QueryLabScopeRequest(ApiModel):
    sandbox_kind: Literal["release_candidate"] = "release_candidate"
    sandbox_id: str = Field(min_length=3, max_length=160)
    source_version_ids: list[str] = Field(min_length=1, max_length=50)
    chunk_profile_id: str = Field(min_length=3, max_length=160)


class QueryLabRequest(ApiModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=50)
    scope: QueryLabScopeRequest


class RetrievalCapabilityData(ApiModel):
    status: Literal["available", "degraded", "disabled"]
    reason: str | None = None


class RetrievalCapabilitiesData(ApiModel):
    metadata: RetrievalCapabilityData
    full_text: RetrievalCapabilityData
    vector: RetrievalCapabilityData
    relation: RetrievalCapabilityData
    generation: RetrievalCapabilityData


class RetrievalRouteContributionsData(ApiModel):
    metadata: float = Field(ge=0)
    full_text: float = Field(ge=0)
    vector: None = None
    relation: None = None


class RetrievalCitationData(ApiModel):
    evidence_id: str
    source_version_id: str
    source_artifact_id: str
    locator: dict[str, Any]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    span_role: Literal["primary", "overlap"]


class RetrievalExplanationData(ApiModel):
    source_version_id: str
    source_title: str
    source_version: str
    chunk_profile_id: str
    ordinal: int = Field(ge=0)
    evidence_type: str
    locator: dict[str, Any]
    token_count: int = Field(gt=0)


class RetrievalHitData(ApiModel):
    rank: int = Field(gt=0)
    chunk_id: str
    content: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fusion_score: float = Field(ge=0)
    route_contributions: RetrievalRouteContributionsData
    explanation: RetrievalExplanationData
    citations: list[RetrievalCitationData] = Field(min_length=1)


class RetrievalContextPackageData(ApiModel):
    sandbox_kind: Literal["release_candidate"] = "release_candidate"
    sandbox_id: str
    chunk_ids: list[str]
    citations: list[RetrievalCitationData]


class QueryLabData(ApiModel):
    query_id: str
    fusion_version: Literal["metadata-fts-weighted-v1"]
    capabilities: RetrievalCapabilitiesData
    hits: list[RetrievalHitData]
    context_package: RetrievalContextPackageData
    external_model_requests: Literal[0]
    evaluation_notice: Literal[
        "single_document_retrieval_baseline_not_clinical_quality_certification"
    ]


class ReleasedQueryLabRequest(ApiModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=50)
    release_id: str | None = Field(default=None, min_length=1, max_length=160)


class ReleasedRetrievalContextPackageData(ApiModel):
    scope_kind: Literal["immutable_release"] = "immutable_release"
    release_id: str
    chunk_ids: list[str]
    citations: list[RetrievalCitationData]


class ReleasedQueryLabData(ApiModel):
    query_id: str
    release_id: str
    release_version: str
    fusion_version: Literal["metadata-fts-weighted-v1"]
    capabilities: RetrievalCapabilitiesData
    hits: list[RetrievalHitData]
    context_package: ReleasedRetrievalContextPackageData
    external_model_requests: Literal[0]
    evaluation_notice: Literal[
        "single_document_retrieval_baseline_not_clinical_quality_certification"
    ]


class EvaluationMetricsData(ApiModel):
    recall_at_5: float = Field(ge=0, le=1)
    recall_at_10: float = Field(ge=0, le=1)


class EvaluationThresholdCheckData(ApiModel):
    metric: Literal["recall_at_5", "recall_at_10"]
    observed: float = Field(ge=0, le=1)
    minimum: float = Field(ge=0, le=1)
    passed: bool


class EvaluationReplayData(ApiModel):
    query_lab_path: Literal["/query-lab"] = "/query-lab"
    query: str | None
    release_id: str | None
    top_k: Literal[10] = 10
    availability: Literal["available", "candidate_scope_required", "query_unavailable"]


class EvaluationCaseData(ApiModel):
    case_id: str
    topic: str | None
    question: str | None
    query_id: str | None
    outcome: Literal["hit_top_5", "hit_top_10_only", "expected_not_in_top_10"]
    failure_category: Literal["none", "ranked_below_5", "expected_not_retrieved"]
    hit_at_5: bool
    hit_at_10: bool
    first_relevant_rank: int | None = Field(default=None, ge=1)
    expected_evidence_ids: list[str]
    retrieved_evidence_ids: list[str]
    replay: EvaluationReplayData


class EvaluationRunSummaryData(ApiModel):
    evaluation_run_id: str
    suite_id: str
    suite_version: str
    purpose: Literal["retrieval_baseline", "release_gate_synthetic"]
    target_id: str
    status: str
    outcome: Literal["informational", "passed", "failed"]
    case_count: int = Field(ge=0)
    metrics: EvaluationMetricsData
    external_model_requests: int = Field(ge=0)
    evaluation_notice: str
    started_at: datetime
    completed_at: datetime | None


class EvaluationRunDetailData(EvaluationRunSummaryData):
    threshold_checks: list[EvaluationThresholdCheckData]
    failure_reasons: list[str]
    case_results: list[EvaluationCaseData]


class EvaluationRunCollectionData(ApiModel):
    items: list[EvaluationRunSummaryData]
    total: int = Field(ge=0)
    partial: bool
    warnings: list[str]


class ReleaseSummaryData(ApiModel):
    release_id: str
    version: str
    status: str
    base_release_id: str | None
    item_count: int = Field(ge=0)
    is_current: bool
    created_at: datetime
    published_at: datetime | None


class ReleaseGateData(ApiModel):
    code: Literal[
        "candidate_integrity",
        "base_release_current",
        "evaluation_passed",
        "publication_snapshot",
    ]
    passed: bool
    reason: str


class ReleaseDiffData(ApiModel):
    included_count: int = Field(ge=0)
    carried_count: int = Field(ge=0)
    replaced_count: int = Field(ge=0)
    added_count: int = Field(ge=0)
    retired_count: int = Field(ge=0)
    included_revision_ids: list[str]
    carried_revision_ids: list[str]
    replaced_revision_ids: list[str]
    added_revision_ids: list[str]
    retired_revision_ids: list[str]


class ReleaseWorkbenchData(ApiModel):
    current: ReleaseSummaryData | None
    candidate: ReleaseSummaryData | None
    history: list[ReleaseSummaryData]
    diff: ReleaseDiffData | None
    gates: list[ReleaseGateData]
    blockers: list[str]
    allowed_actions: list[Literal["publish"]]


class ReleasePublishRequest(ApiModel):
    base_release_id: str | None = Field(max_length=160)


class PublishedReleaseData(ApiModel):
    release_id: str
    version: str
    previous_release_id: str | None
    manifest_object_key: str
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    index_manifest_version: str
    published_at: datetime


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


class UserCreateRequest(ApiModel):
    username: str = Field(min_length=1, max_length=160)
    display_name: str = Field(min_length=1, max_length=240)
    email: str = Field(min_length=3, max_length=320)
    roles: list[ProductRole] = Field(min_length=1)


class UserStatusRequest(ApiModel):
    status: Literal["active", "disabled"]


class AdminTemporaryPasswordData(ApiModel):
    user_id: str
    username: str | None
    temporary_password: str = Field(min_length=12, max_length=128)
    must_change_password: Literal[True] = True


class UserStatusData(ApiModel):
    user_id: str
    status: Literal["active", "disabled"]


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


class ServiceAccountData(ApiModel):
    service_account_id: str
    display_name: str
    worker_pool: Literal["document", "enrichment", "release"]
    scopes: list[Permission]
    status: Literal["active", "disabled"]


class ServiceAccountCollectionData(ApiModel):
    items: list[ServiceAccountData]
    total: int = Field(ge=0)
    partial: bool
    warnings: list[str]


class ModelProfileRegistrationRequest(ApiModel):
    profile_id: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=80)
    provider: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=240)
    deployment_class: Literal["enterprise_managed", "external_api"]
    secret_ref: str = Field(pattern=r"^(env|secret)://[A-Za-z0-9_./-]+$")
    endpoint_ref: str | None = Field(
        default=None,
        pattern=r"^(env|secret)://[A-Za-z0-9_./-]+$",
    )
    allowed_data_boundaries: list[Literal["external_allowed", "enterprise_provider_only"]] = Field(
        min_length=1
    )
    capabilities: list[Literal["structured_generation"]] = Field(min_length=1)
    timeout_seconds: int = Field(ge=1, le=600)
    max_output_tokens: int = Field(ge=1)
    cost_policy: dict[str, Any] | None = None


class ModelProfileData(ModelProfileRegistrationRequest):
    created_at: datetime
    connection_state: Literal["not_verified"] = "not_verified"
    live_enabled: Literal[False] = False


class ModelProfileCollectionData(ApiModel):
    items: list[ModelProfileData]
    total: int = Field(ge=0)
    partial: bool
    warnings: list[str]


class ModelProfileRegistrationData(ApiModel):
    profile: ModelProfileData
    created: bool


class ErrorData(ApiModel):
    code: Literal[
        "authentication_required",
        "invalid_credentials",
        "invalid_identity",
        "account_locked",
        "password_change_required",
        "current_password_invalid",
        "password_policy_failed",
        "csrf_rejected",
        "user_conflict",
        "user_not_found",
        "user_management_invalid",
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
        "rotation_case_not_found",
        "impact_assessment_not_found",
        "chunk_projection_not_found",
        "stale_rotation_case",
        "invalid_rotation_transition",
        "invalid_request",
        "model_profile_conflict",
        "machine_authentication_required",
        "published_knowledge_unavailable",
        "published_knowledge_invalid",
        "released_knowledge_not_found",
        "released_knowledge_invalid",
        "evaluation_run_not_found",
        "evaluation_run_invalid",
        "release_candidate_not_found",
        "release_publish_blocked",
        "release_object_integrity_failed",
        "runtime_knowledge_lock_rejected",
    ]
    message: str
    details: dict[str, Any] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )


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


class RotationCaseResponse(ApiModel):
    data: RotationCaseData
    meta: ResponseMeta


class RotationCaseCollectionResponse(ApiModel):
    data: RotationCaseCollectionData
    meta: ResponseMeta


class RotationDecisionResponse(ApiModel):
    data: RotationDecisionData
    meta: ResponseMeta


class ImpactAssessmentResponse(ApiModel):
    data: ImpactAssessmentData
    meta: ResponseMeta


class ChunkProjectionResponse(ApiModel):
    data: ChunkProjectionData
    meta: ResponseMeta


class QueryLabResponse(ApiModel):
    data: QueryLabData
    meta: ResponseMeta


class ReleasedQueryLabResponse(ApiModel):
    data: ReleasedQueryLabData
    meta: ResponseMeta


class EvaluationRunCollectionResponse(ApiModel):
    data: EvaluationRunCollectionData
    meta: ResponseMeta


class EvaluationRunDetailResponse(ApiModel):
    data: EvaluationRunDetailData
    meta: ResponseMeta


class ReleaseWorkbenchResponse(ApiModel):
    data: ReleaseWorkbenchData
    meta: ResponseMeta


class PublishedReleaseResponse(ApiModel):
    data: PublishedReleaseData
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


class AdminTemporaryPasswordResponse(ApiModel):
    data: AdminTemporaryPasswordData
    meta: ResponseMeta


class UserStatusResponse(ApiModel):
    data: UserStatusData
    meta: ResponseMeta


class ServiceAccountCollectionResponse(ApiModel):
    data: ServiceAccountCollectionData
    meta: ResponseMeta


class ModelProfileCollectionResponse(ApiModel):
    data: ModelProfileCollectionData
    meta: ResponseMeta


class ModelProfileRegistrationResponse(ApiModel):
    data: ModelProfileRegistrationData
    meta: ResponseMeta


class ErrorResponse(ApiModel):
    error: ErrorData
    meta: ResponseMeta
