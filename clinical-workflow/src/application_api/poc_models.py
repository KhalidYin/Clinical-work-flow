"""P9.1 single-study POC runner API contracts.

These models are the only contract the React Workbench may use. The browser
must not infer workflow state from filenames, local paths, or console text.
Version 2 makes the Runner step ledger authoritative and normalizes legacy
``blocked_review``/``blocked_error`` records at the API boundary.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base class for POC API payloads."""

    model_config = ConfigDict(extra="forbid")


class PocRunState(StrEnum):
    """Version 2 top-level state exposed to the Workbench."""

    IDLE = "idle"
    RUNNING = "running"
    BLOCKED = "blocked"
    DONE = "done"


LEGACY_POC_RUN_STATES = frozenset(
    {"queued", "blocked_review", "blocked_error", "failed", "completed"}
)


def normalize_poc_run_state(value: str | PocRunState) -> PocRunState:
    """Normalize a stored v1/v2 run state to the public v2 state."""

    raw = value.value if isinstance(value, PocRunState) else str(value)
    if raw == PocRunState.IDLE.value:
        return PocRunState.IDLE
    if raw in {PocRunState.RUNNING.value, "queued"}:
        return PocRunState.RUNNING
    if raw in {PocRunState.BLOCKED.value, "blocked_review", "blocked_error", "failed"}:
        return PocRunState.BLOCKED
    if raw in {PocRunState.DONE.value, "completed"}:
        return PocRunState.DONE
    raise ValueError(f"unsupported POC run state: {raw}")


class PocStepState(StrEnum):
    """Version 2 state persisted in the Runner step ledger."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class PocStepKind(StrEnum):
    """Workbench rendering hint for the active step."""

    INSTRUCTION = "instruction"
    REVIEW = "review"
    ARTIFACT = "artifact"
    ERROR = "error"
    COMPLETE = "complete"


POC_STEP_DEFINITIONS = (
    ("input-check", "Input Check"),
    ("minimum-information", "Minimum Information"),
    ("wiki-context", "Wiki Context"),
    ("mapping-spec", "MappingSpec"),
    ("program-execution", "Program / Execution"),
    ("validation-review", "Validation / Review"),
    ("canonical-ae", "Canonical AE"),
)

LEGACY_POC_STEP_ALIASES = {
    "source-intake": "input-check",
    "sas-metadata": "input-check",
    "state-preflight": "input-check",
    "minimum-information": "minimum-information",
    "wiki-context": "wiki-context",
    "mapping-spec": "mapping-spec",
    "review-gate": "mapping-spec",
    "codegen": "program-execution",
    "draft-ae": "program-execution",
    "output-review": "validation-review",
    "canonical-ae": "canonical-ae",
}


class PocActionType(StrEnum):
    """Action IDs recognized by the Workbench."""

    RUN_POC = "run_poc"
    RETRY_CURRENT_STEP = "retry_current_step"
    OPEN_REVIEW = "open_review"
    RESUME = "resume"
    REFRESH = "refresh"
    OPEN_OUTPUT_FOLDER = "open_output_folder"


class PocBlockerKind(StrEnum):
    """Operational class of a POC blocker."""

    INPUT = "input"
    VALIDATION = "validation"
    REVIEW = "review"
    SYSTEM = "system"


class PocRecoveryAction(StrEnum):
    """Bounded recovery route selected by the Runner."""

    PROVIDE_INPUT = "provide_input"
    REPAIR_INPUT = "repair_input"
    INSTALL_DEPENDENCY = "install_dependency"
    RETRY_CURRENT_STEP = "retry_current_step"
    SUBMIT_REVIEW_DECISION = "submit_review_decision"
    RESUME_AFTER_REVIEW = "resume_after_review"
    REFRESH = "refresh"


class PocCheckState(StrEnum):
    """Deterministic result for a step or Input Check."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class PocInputCheckState(StrEnum):
    """Aggregate readiness of the bounded target input."""

    NOT_RUN = "not_run"
    READY = "ready"
    WARNING = "warning"
    BLOCKED = "blocked"
    PARTIAL = "partial"


class PocDependencyRequirement(StrEnum):
    """Requirement level for one target input."""

    REQUIRED = "required"
    CONDITIONAL = "conditional"
    OPTIONAL = "optional"
    NOT_REQUIRED = "not_required"


class PocDependencyStatus(StrEnum):
    """Observed state of one target input dependency."""

    AVAILABLE = "available"
    MISSING = "missing"
    INVALID = "invalid"
    GAP = "gap"
    NOT_REQUIRED = "not_required"


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


class PocStepCheck(StrictModel):
    """One deterministic check owned by a Runner step."""

    check_id: str = Field(min_length=2)
    state: PocCheckState
    summary: str = Field(min_length=1)
    detail: str | None = None
    observed: str | int | float | bool | None = None
    expected: str | int | float | bool | None = None
    affected_variables: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class PocStep(StrictModel):
    """A single authoritative Runner ledger step."""

    step_id: str = Field(min_length=3)
    ordinal: int = Field(ge=1)
    title: str = Field(min_length=1)
    state: PocStepState
    kind: PocStepKind = PocStepKind.INSTRUCTION
    summary: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    checks: list[PocStepCheck] = Field(default_factory=list)
    blocking_reason: str | None = None
    review_id: str | None = None
    input_refs: list[str] = Field(default_factory=list)
    artifact_refs: list[PocArtifactRef] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class PocActiveStep(StrictModel):
    """Current focus panel payload."""

    step_id: str = Field(min_length=3)
    kind: PocStepKind
    title: str = Field(min_length=1)
    summary: str = ""
    blocking_reason: str | None = None
    next_instruction: str | None = None
    review_id: str | None = None
    artifact_refs: list[PocArtifactRef] = Field(default_factory=list)


class PocBlocker(StrictModel):
    """Structured explanation for a blocked run."""

    kind: PocBlockerKind
    stage_id: str = Field(min_length=3)
    code: str = Field(min_length=3)
    summary: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    affected_variables: list[str] = Field(default_factory=list)
    affected_artifacts: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    recovery_action: PocRecoveryAction
    review_id: str | None = None
    retryable: bool = False


class PocInputFile(StrictModel):
    """Input file evidence safe for the Workbench."""

    source_id: str = Field(min_length=2)
    label: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    format: str = Field(min_length=1)
    exists: bool
    sha256: str | None = Field(default=None, min_length=64, max_length=64)
    size_bytes: int | None = Field(default=None, ge=0)
    parser: str | None = None
    parser_available: bool | None = None
    row_count: int | None = Field(default=None, ge=0)
    column_count: int | None = Field(default=None, ge=0)
    labels_available: bool | None = None
    formats_available: bool | None = None
    value_labels_available: bool | None = None
    warnings: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


class PocVariableProfile(StrictModel):
    """Bounded variable profile used before MappingSpec generation."""

    variable: str = Field(min_length=1)
    label: str | None = None
    data_type: str | None = None
    format: str | None = None
    missing_count: int | None = Field(default=None, ge=0)
    non_missing_count: int | None = Field(default=None, ge=0)
    distinct_count: int | None = Field(default=None, ge=0)
    value_labels_available: bool | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class PocInputDependency(StrictModel):
    """One target-scoped input requirement and its observed state."""

    input_id: str = Field(min_length=2)
    label: str = Field(min_length=1)
    requirement: PocDependencyRequirement
    status: PocDependencyStatus
    blocking: bool
    detail: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class PocInputCheckSummary(StrictModel):
    """Compact UI-02 input readiness counters."""

    status: PocInputCheckState
    required_total: int = Field(ge=0)
    required_ready: int = Field(ge=0)
    blocking_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    message: str = Field(min_length=1)


class PocInputCheck(StrictModel):
    """Target-scoped Input Check result."""

    checked_at: str | None = None
    summary: PocInputCheckSummary
    files: list[PocInputFile] = Field(default_factory=list)
    dependencies: list[PocInputDependency] = Field(default_factory=list)
    checks: list[PocStepCheck] = Field(default_factory=list)
    variable_profiles: list[PocVariableProfile] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PocNextAction(StrictModel):
    """Button-level action contract."""

    action_id: PocActionType
    label: str = Field(min_length=1)
    enabled: bool
    primary: bool = False
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
    run_id: str | None = None
    step_id: str | None = None
    summary: str = Field(min_length=1)
    severity: PocHealthSeverity = PocHealthSeverity.OK
    related_refs: list[dict[str, Any]] = Field(default_factory=list)


class PocState(StrictModel):
    """Complete version 2 state consumed by the React Workbench."""

    schema_version: Literal["2.0"] = "2.0"
    study_id: str = Field(min_length=2)
    target_artifact: Literal["sdtm_ae_dataset"] = "sdtm_ae_dataset"
    run_id: str | None = None
    run_state: PocRunState
    legacy_run_state: str | None = None
    source: dict[str, Any] = Field(default_factory=dict)
    knowledge: dict[str, Any] = Field(default_factory=dict)
    input_check: PocInputCheck
    blocker: PocBlocker | None = None
    blocking_reason: str | None = None
    active_step: PocActiveStep | None = None
    steps: list[PocStep]
    next_actions: list[PocNextAction]
    health: list[PocHealthItem] = Field(default_factory=list)
    events: list[PocEvent] = Field(default_factory=list)
    partial_errors: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_state_authority(self) -> "PocState":
        """Keep run, blocker, active step and ledger state mutually consistent."""

        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("step_id values must be unique")
        ordinals = [step.ordinal for step in self.steps]
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("step ordinals must be unique")

        blocked_steps = [step for step in self.steps if step.state is PocStepState.BLOCKED]
        if self.run_state is PocRunState.BLOCKED:
            if self.blocker is None:
                raise ValueError("blocked run requires blocker")
            if self.active_step is None or self.active_step.step_id != self.blocker.stage_id:
                raise ValueError("blocked run active_step must match blocker.stage_id")
            if len(blocked_steps) != 1 or blocked_steps[0].step_id != self.blocker.stage_id:
                raise ValueError("blocked run requires one matching blocked ledger step")
        else:
            if self.blocker is not None:
                raise ValueError("non-blocked run cannot expose blocker")
            if blocked_steps:
                raise ValueError("non-blocked run cannot contain blocked ledger steps")

        primary_actions = [action for action in self.next_actions if action.enabled and action.primary]
        if len(primary_actions) > 1:
            raise ValueError("only one enabled primary action is allowed")
        return self


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
