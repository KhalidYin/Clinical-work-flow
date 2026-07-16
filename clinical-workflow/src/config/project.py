"""Study-level project.yaml configuration contract."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


PROJECT_CONFIG_FILE = "project.yaml"

TrialPhase = Literal["phase_i", "phase_ii", "phase_iii", "phase_iv"]
TherapeuticArea = Literal[
    "oncology",
    "cardiovascular",
    "diabetes",
    "respiratory",
    "non_oncology",
    "synthetic_safety",
    "other",
]
ProgrammingLanguage = Literal["sas", "r", "python"]
ConsensusRule = Literal["all_must_approve", "majority", "any_one"]
StaleAction = Literal["continue", "pause"]


class ProjectConfigError(ValueError):
    """Raised when project.yaml cannot be loaded or validated."""


class StrictModel(BaseModel):
    """Base model that rejects undeclared project.yaml keys."""

    model_config = ConfigDict(extra="forbid")


class StandardsConfig(StrictModel):
    sdtm_version: str = Field(min_length=1)
    sdtmig_version: str = Field(min_length=1)
    adam_version: str | None = Field(default=None, min_length=1)
    adamig_version: str | None = Field(default=None, min_length=1)
    ct_version: str = Field(min_length=1)


class ReviewTimeoutConfig(StrictModel):
    reminder_hours: int = Field(ge=1)
    escalation_hours: int = Field(ge=1)
    stale_hours: int = Field(ge=1)
    stale_action: StaleAction

    @model_validator(mode="after")
    def validate_order(self) -> "ReviewTimeoutConfig":
        if self.reminder_hours > self.escalation_hours:
            raise ValueError("reminder_hours must be <= escalation_hours")
        if self.escalation_hours > self.stale_hours:
            raise ValueError("escalation_hours must be <= stale_hours")
        return self


class ReviewAssignment(StrictModel):
    reviewers: list[str] = Field(min_length=1)
    consensus: ConsensusRule


class ReviewAssignments(StrictModel):
    sap_review: ReviewAssignment
    sdtm_spec: ReviewAssignment
    adam_spec: ReviewAssignment
    tfl_shell: ReviewAssignment
    tfl_qc: ReviewAssignment
    submission: ReviewAssignment
    source_intake: ReviewAssignment | None = None
    parser_output: ReviewAssignment | None = None
    sdtm_programming: ReviewAssignment | None = None


class ProjectPaths(StrictModel):
    input_dir: str = Field(min_length=1)
    work_dir: str | None = Field(default=None, min_length=1)
    program_dir: str | None = Field(default=None, min_length=1)
    output_dir: str = Field(min_length=1)
    review_queue_dir: str = Field(min_length=1)
    audit_log: str = Field(min_length=1)


class ProjectConfig(StrictModel):
    study_id: str = Field(min_length=1)
    protocol_id: str = Field(min_length=1)
    trial_phase: TrialPhase
    therapeutic_area: TherapeuticArea
    primary_language: ProgrammingLanguage
    qc_language: ProgrammingLanguage
    sponsor: str = Field(min_length=1)
    created_at: datetime
    standards: StandardsConfig
    synthetic_only: bool | None = None
    scaffold_status: str | None = None
    source_policy: dict[str, Any] | None = None
    programming_chain: dict[str, Any] | None = None
    review_timeout: ReviewTimeoutConfig
    review_assignments: ReviewAssignments
    paths: ProjectPaths

    def to_runtime_context(self) -> dict[str, object]:
        return {
            "study_id": self.study_id,
            "protocol_id": self.protocol_id,
            "trial_phase": self.trial_phase,
            "therapeutic_area": self.therapeutic_area,
            "primary_language": self.primary_language,
            "qc_language": self.qc_language,
            "sponsor": self.sponsor,
            "created_at": self.created_at.isoformat(),
            "standards": self.standards.model_dump(),
            "synthetic_only": self.synthetic_only,
            "scaffold_status": self.scaffold_status,
            "source_policy": self.source_policy,
            "programming_chain": self.programming_chain,
            "review_timeout": self.review_timeout.model_dump(),
            "review_assignments": self.review_assignments.model_dump(),
            "paths": self.paths.model_dump(),
        }


def load_project_config(project_dir: str | Path, required: bool = False) -> ProjectConfig | None:
    """Load and validate project.yaml from a study directory."""
    config_path = Path(project_dir) / PROJECT_CONFIG_FILE
    if not config_path.exists():
        if required:
            raise ProjectConfigError(f"Missing required project config: {config_path}")
        return None

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProjectConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ProjectConfigError(f"{config_path} must contain a YAML mapping")

    try:
        return ProjectConfig.model_validate(raw)
    except ValidationError as exc:
        raise ProjectConfigError(f"Invalid {config_path}: {exc}") from exc


def resolve_project_path(project_dir: str | Path, path_value: str | Path) -> Path:
    """Resolve a configured Study path without permitting directory escape.

    Study configuration is intentionally self-contained.  A Study may refer to
    the Knowledge Service by an explicitly injected endpoint at runtime, but
    its file paths must never infer or traverse to a sibling repository.
    """

    project_root = Path(project_dir).resolve()
    path = Path(path_value)
    if path.is_absolute():
        raise ProjectConfigError("Study paths must be relative to the Study root")

    resolved = (project_root / path).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise ProjectConfigError("Study paths must not escape the Study root") from exc
    return resolved
