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
