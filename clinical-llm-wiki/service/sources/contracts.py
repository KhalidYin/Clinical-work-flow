"""Source Registry contracts for governed, non-streaming document intake."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from service.object_store import ObjectDescriptor


class StrictSourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RightsClassification(str, Enum):
    LICENSED = "licensed"
    INTERNAL = "internal"
    RESTRICTED = "restricted"


class DataBoundary(str, Enum):
    LOCAL_PROCESSING_ONLY = "local_processing_only"
    ENTERPRISE_PROVIDER_ONLY = "enterprise_provider_only"
    EXTERNAL_ALLOWED = "external_allowed"
    PROHIBITED = "prohibited"


class RightsPolicy(StrictSourceModel):
    classification: RightsClassification
    storage_allowed: bool
    citation_required: bool = True


class SourceRegistrationCommand(StrictSourceModel):
    source_id: str = Field(
        min_length=5,
        max_length=160,
        pattern=r"^src-[a-z0-9][a-z0-9._-]*$",
    )
    title: str = Field(min_length=1, max_length=500)
    source_type: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[a-z][a-z0-9_-]*$",
    )
    version: str = Field(min_length=1, max_length=120)
    rights: RightsPolicy
    data_boundary: DataBoundary
    media_type: str = Field(min_length=1, max_length=255)
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(
        min_length=8,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )


class RegistrationIntentStatus(str, Enum):
    PENDING = "pending"
    OBJECT_WRITTEN = "object_written"
    COMMITTED = "committed"
    COMPENSATION_REQUIRED = "compensation_required"
    COMPENSATED = "compensated"
    FAILED = "failed"


class RegistrationIntentRecord(StrictSourceModel):
    registration_id: str
    purpose: Literal["raw_source", "parser_output"] = "raw_source"
    source_id: str
    source_version_id: str
    version: str
    object_key: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str
    size_bytes: int = Field(ge=0)
    actor_id: str
    idempotency_key: str
    status: RegistrationIntentStatus
    failure_code: str | None = None


class SourceRegistrationReceipt(StrictSourceModel):
    source_id: str
    source_version_id: str
    run_id: str
    status: Literal["queued"] = "queued"
    original_object: ObjectDescriptor


class OrphanReconcileResult(StrictSourceModel):
    scanned: int = Field(ge=0)
    deleted: int = Field(ge=0)
    missing: int = Field(ge=0)
    failed: int = Field(ge=0)


__all__ = [
    "DataBoundary",
    "OrphanReconcileResult",
    "RegistrationIntentRecord",
    "RegistrationIntentStatus",
    "RightsClassification",
    "RightsPolicy",
    "SourceRegistrationCommand",
    "SourceRegistrationReceipt",
]
