"""Strict P17 contracts for candidate build and immutable Release publication."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from service.evaluation import ReleaseEvaluationRun
from service.object_store import ObjectDescriptor


class StrictReleaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IndexCapabilities(StrictReleaseModel):
    metadata: Literal["available"]
    full_text: Literal["available"]
    vector: Literal["available", "degraded", "disabled"]
    relation: Literal["available", "degraded", "disabled"]


class ReleaseBuildCommand(StrictReleaseModel):
    release_candidate_id: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=120)
    base_release_id: str | None = Field(default=None, max_length=160)
    evaluation_run_id: str = Field(min_length=1, max_length=160)
    chunk_profile_id: str = Field(min_length=1, max_length=160)
    rotation_case_ids: tuple[str, ...]
    additional_revision_ids: tuple[str, ...]
    index_capabilities: IndexCapabilities
    embedding_profile_id: str | None = Field(default=None, max_length=160)
    relation_index_version: str | None = Field(default=None, max_length=120)
    db_schema_revision: str = Field(min_length=1, max_length=120)
    knowledge_contract_version: str = Field(min_length=1, max_length=120)
    parser_profile_version: str = Field(min_length=1, max_length=120)
    model_profile_version: str = Field(min_length=1, max_length=120)
    prompt_profile_version: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_build_scope(self) -> "ReleaseBuildCommand":
        if len(self.rotation_case_ids) != len(set(self.rotation_case_ids)):
            raise ValueError("rotation_case_ids must be unique")
        if len(self.additional_revision_ids) != len(set(self.additional_revision_ids)):
            raise ValueError("additional_revision_ids must be unique")
        if (
            self.base_release_id is None
            and not self.rotation_case_ids
            and not self.additional_revision_ids
        ):
            raise ValueError("initial Release requires explicit membership")
        if (
            self.index_capabilities.vector == "available"
            and self.embedding_profile_id is None
        ):
            raise ValueError("available vector capability requires embedding_profile_id")
        if (
            self.index_capabilities.relation == "available"
            and self.relation_index_version is None
        ):
            raise ValueError("available relation capability requires relation_index_version")
        return self


class ReleasePublishCommand(StrictReleaseModel):
    release_id: str = Field(min_length=1, max_length=160)
    base_release_id: str | None = Field(default=None, max_length=160)


class ReleaseItemSnapshot(StrictReleaseModel):
    knowledge_revision_id: str = Field(min_length=1, max_length=160)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    disposition: Literal["carry_forward", "replace", "retire", "no_action", "add"]
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    chunk_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_item_identity(self) -> "ReleaseItemSnapshot":
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("evidence_ids must be unique")
        if len(self.chunk_ids) != len(set(self.chunk_ids)):
            raise ValueError("chunk_ids must be unique")
        return self


class ReleaseBuildSnapshot(StrictReleaseModel):
    current_release_id: str | None = Field(default=None, max_length=160)
    evaluation: ReleaseEvaluationRun
    chunk_profile_version: str = Field(min_length=1, max_length=120)
    items: tuple[ReleaseItemSnapshot, ...] = Field(min_length=1)
    rotation_case_ids: tuple[str, ...]


class IndexManifestPayload(StrictReleaseModel):
    version: Literal["p17-index-v1"] = "p17-index-v1"
    release_id: str
    release_version: str
    capabilities: IndexCapabilities
    embedding_profile_id: str | None = None
    relation_index_version: str | None = None
    revision_ids: tuple[str, ...]
    chunk_ids: tuple[str, ...]


class ReleaseManifestItem(StrictReleaseModel):
    knowledge_revision_id: str
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    disposition: str
    evidence_ids: tuple[str, ...]
    chunk_ids: tuple[str, ...]


class ReleaseManifestPayload(StrictReleaseModel):
    schema_version: Literal["p17-release-v1"] = "p17-release-v1"
    release_id: str
    release_version: str
    base_release_id: str | None
    evaluation_run_id: str
    chunk_profile_id: str
    chunk_profile_version: str
    rotation_case_ids: tuple[str, ...]
    db_schema_revision: str
    knowledge_contract_version: str
    parser_profile_version: str
    model_profile_version: str
    prompt_profile_version: str
    index_descriptor: ObjectDescriptor
    items: tuple[ReleaseManifestItem, ...]


class PreparedRelease(StrictReleaseModel):
    release_id: str
    version: str
    base_release_id: str | None
    evaluation_run_id: str
    index_manifest: IndexManifestPayload
    index_descriptor: ObjectDescriptor
    manifest: ReleaseManifestPayload
    manifest_descriptor: ObjectDescriptor


class PublishedReleaseRecord(StrictReleaseModel):
    release_id: str
    version: str
    previous_release_id: str | None
    manifest_object_key: str
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    index_manifest_version: str
    published_at: datetime
