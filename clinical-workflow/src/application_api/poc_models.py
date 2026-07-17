"""P9.1 single-study POC runner API contracts.

These models are the only contract the React Workbench may use.  The browser
must not infer workflow state from filenames, local paths, or console text.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Base class for POC API payloads."""

    model_config = ConfigDict(extra="forbid")


class PocRunState(StrEnum):
    """Top-level state exposed to the Workbench."""

    IDLE = "idle"
    RUNNING = "running"
    BLOCKED_REVIEW = "blocked_review"
    BLOCKED_ERROR = "blocked_error"
    DONE = "done"


class PocStepState(StrEnum):
    """Per-step state exposed to the timeline."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    BLOCKED_REVIEW = "blocked_review"
    BLOCKED_ERROR = "blocked_error"
    SKIPPED = "skipped"


class PocStepKind(StrEnum):
    """Workbench rendering hint for the active step."""

    INSTRUCTION = "instruction"
    REVIEW = "review"
    ARTIFACT = "artifact"
    ERROR = "error"
    COMPLETE = "complete"


class PocActionType(StrEnum):
    """Action IDs recognized by the Workbench."""

    RUN_POC = "run_poc"
    RESUME = "resume"
    REFRESH = "refresh"
    OPEN_OUTPUT_FOLDER = "open_output_folder"


class PocHealthSeverity(StrEnum):
    """Health severity for preflight and runtime diagnostics."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class PocArtifactKind(StrEnum):
    """Safe preview kinds for Study artifacts."""

    JSON = "json"
    CSV = "csv"
    TEXT = "text"
    YAML = "yaml"
    DIRECTORY = "directory"
    UNKNOWN = "unknown"


class PocArtifactRef(StrictModel):
    """Relative artifact reference; absolute paths are intentionally absent."""

    artifact_id: str = Field(min_length=3)
    label: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    kind: PocArtifactKind
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    preview_available: bool = False


class PocStep(StrictModel):
    """A single timeline step for the SDTM AE POC."""

    step_id: str = Field(min_length=3)
    ordinal: int = Field(ge=1)
    title: str = Field(min_length=1)
    state: PocStepState
    kind: PocStepKind = PocStepKind.INSTRUCTION
    summary: str = ""
    blocking_reason: str | None = None
    review_id: str | None = None
    artifact_refs: list[PocArtifactRef] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class PocActiveStep(StrictModel):
    """Current focus panel payload."""

    step_id: str
    kind: PocStepKind
    title: str
    summary: str = ""
    blocking_reason: str | None = None
    next_instruction: str | None = None
    review_id: str | None = None
    artifact_refs: list[PocArtifactRef] = Field(default_factory=list)


class PocNextAction(StrictModel):
    """Button-level action contract."""

    action_id: PocActionType
    label: str = Field(min_length=1)
    enabled: bool
    reason: str | None = None
    method: Literal["GET", "POST"] = "POST"
    endpoint: str = Field(min_length=1)


class PocHealthItem(StrictModel):
    """One preflight/runtime health check."""

    check_id: str = Field(min_length=2)
    severity: PocHealthSeverity
    summary: str = Field(min_length=1)
    detail: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class PocEvent(StrictModel):
    """Visible runner event for the Workbench log."""

    event_id: str = Field(min_length=3)
    event_type: str = Field(min_length=1)
    occurred_at: str = Field(min_length=10)
    step_id: str | None = None
    summary: str = Field(min_length=1)
    severity: PocHealthSeverity = PocHealthSeverity.OK
    related_refs: list[dict[str, Any]] = Field(default_factory=list)


class PocState(StrictModel):
    """Complete state consumed by the React Workbench."""

    study_id: str = Field(min_length=2)
    target_artifact: Literal["sdtm_ae_dataset"] = "sdtm_ae_dataset"
    run_id: str | None = None
    run_state: PocRunState
    source: dict[str, Any] = Field(default_factory=dict)
    knowledge: dict[str, Any] = Field(default_factory=dict)
    blocking_reason: str | None = None
    active_step: PocActiveStep | None = None
    steps: list[PocStep]
    next_actions: list[PocNextAction]
    health: list[PocHealthItem] = Field(default_factory=list)
    events: list[PocEvent] = Field(default_factory=list)
    partial_errors: list[dict[str, Any]] = Field(default_factory=list)


class PocRunRequest(StrictModel):
    """Start request for the bounded SDTM AE POC."""

    target_artifact: Literal["sdtm_ae_dataset"] = "sdtm_ae_dataset"
    intent: str = Field(default="生成 SAMPLE-AE-001 SDTM AE 最小 POC", min_length=3)
    force_restart: bool = False


class PocRunResponse(StrictModel):
    """Response after starting or resuming a POC run."""

    accepted: bool
    run_id: str
    run_state: PocRunState
    state_endpoint: str
    message: str


class PocResumeReason(StrEnum):
    """Allowed resume reasons for the bounded POC runner."""

    REVIEW_DECISION_AVAILABLE = "review_decision_available"
    OPERATOR_RESUME = "operator_resume"
    RETRY_AFTER_FAILURE = "retry_after_failure"


class PocResumeRequest(StrictModel):
    """Resume request after a Review Gate or recoverable failure."""

    reason: PocResumeReason = PocResumeReason.REVIEW_DECISION_AVAILABLE
    review_id: str | None = None
    last_seen_event_id: str | None = None

