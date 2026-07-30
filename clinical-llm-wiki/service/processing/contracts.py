"""Stable contracts for durable, non-streaming processing work."""

from __future__ import annotations

from enum import Enum
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

from service.auth import WorkerPool
from service.object_store import ObjectDescriptor


class StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RunStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    AUTHOR_CONFIRMATION_REQUIRED = "author_confirmation_required"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    RELEASE_BLOCKED = "release_blocked"
    RELEASED = "released"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AttemptStatus(str, Enum):
    QUEUED = "queued"
    LEASED = "leased"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class StepDefinition(StrictContractModel):
    step_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    pool: WorkerPool
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    depends_on: tuple[str, ...] = ()

    @field_validator("depends_on")
    @classmethod
    def dependency_names_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("depends_on cannot contain duplicates")
        return value


class ArtifactManifest(StrictContractModel):
    artifacts: tuple[ObjectDescriptor, ...] = ()


class ClaimedStepAttempt(StrictContractModel):
    run_id: str = Field(min_length=1, max_length=160)
    step_id: str = Field(min_length=1, max_length=160)
    step_key: str = Field(min_length=1, max_length=160)
    pool: WorkerPool
    attempt_id: str = Field(min_length=1, max_length=160)
    attempt_number: int = Field(ge=1)
    previous_attempt_id: str | None = Field(default=None, max_length=160)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    checkpoint: dict[str, Any] | None = None


class StepOutcome(StrictContractModel):
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_manifest: ArtifactManifest


def validate_step_graph(steps: Sequence[StepDefinition]) -> tuple[StepDefinition, ...]:
    """Validate a small declared DAG before durable records are created."""

    normalized = tuple(steps)
    by_key = {step.step_key: step for step in normalized}
    if len(by_key) != len(normalized):
        raise ValueError("step_key values must be unique within a run")
    for step in normalized:
        for dependency in step.depends_on:
            if dependency not in by_key:
                raise ValueError(
                    f"unknown dependency {dependency!r} for step {step.step_key!r}"
                )
            if dependency == step.step_key:
                raise ValueError(f"step graph cycle includes {step.step_key!r}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_key: str) -> None:
        if step_key in visiting:
            raise ValueError(f"step graph cycle includes {step_key!r}")
        if step_key in visited:
            return
        visiting.add(step_key)
        for dependency in by_key[step_key].depends_on:
            visit(dependency)
        visiting.remove(step_key)
        visited.add(step_key)

    for key in by_key:
        visit(key)
    return normalized


def processing_runtime_contract_json_schema() -> dict[str, object]:
    schema = TypeAdapter(
        RunStatus
        | StepStatus
        | AttemptStatus
        | StepDefinition
        | ArtifactManifest
        | ClaimedStepAttempt
        | StepOutcome
    ).json_schema(ref_template="#/$defs/{model}")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://clinical.example/schemas/processing-runtime.prerelease.schema.json",
        "title": "P12 Processing Runtime Prerelease Contract",
        **schema,
    }
