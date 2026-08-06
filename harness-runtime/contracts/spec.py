"""H0-B StepExecutionSpec: the product-compiled, immutable step contract.

Per PROJECT_GUIDE/PROJECT_SPEC the spec carries full identity, hash-locked
inputs, executor kind, capabilities, budget and gates. It must NEVER carry
fields that alter the outer workflow (``next_stage``, ``skip_stage``,
``publish``) — ``extra="forbid"`` makes those fail closed.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, model_validator

from .request import StrictContractModel


class ExecutorKind(str, Enum):
    DETERMINISTIC_HANDLER = "deterministic_handler"
    DIRECT_MODEL = "direct_model"
    HARNESS = "harness"


class InstructionRef(StrictContractModel):
    """Step/Skill Pack reference, versioned and hash-locked when available."""

    pack_id: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=100)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class InputReference(StrictContractModel):
    """One hash-locked input (artifact / evidence / release)."""

    ref_type: Literal["artifact", "evidence", "release"]
    ref_id: str = Field(min_length=1, max_length=200)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str | None = None


class NetworkPolicy(StrictContractModel):
    """Default zero outbound network; allowlist only when explicitly granted."""

    mode: Literal["none", "allowlist"] = "none"
    allowlist: tuple[str, ...] = ()

    @model_validator(mode="after")
    def allowlist_requires_mode(self) -> "NetworkPolicy":
        if self.mode == "allowlist" and not self.allowlist:
            raise ValueError("allowlist mode requires at least one allowed target")
        if self.mode == "none" and self.allowlist:
            raise ValueError("allowlist must be empty when network mode is none")
        return self


class BudgetPolicy(StrictContractModel):
    """Attempt-level budget; failed calls still consume it."""

    max_calls: int = Field(ge=1)
    max_tokens: int = Field(default=0, ge=0)
    max_time_seconds: int = Field(ge=1)


class GatePolicy(StrictContractModel):
    """Deterministic validators and human-gate requirements for this step."""

    validators: tuple[str, ...] = ()
    review_required: bool = False
    retry_policy: Literal["manual", "none"] = "manual"


class OutputSpec(StrictContractModel):
    """Expected draft output: type, staging path and optional schema lock."""

    artifact_type: str = Field(min_length=1)
    staging_path: str = Field(min_length=1)
    schema_id: str | None = None
    schema_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class StepExecutionSpec(StrictContractModel):
    """Immutable contract compiled by the product control plane."""

    contract_version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    product: str = Field(min_length=1, max_length=100)
    workflow: str = Field(min_length=1, max_length=100)
    run_id: str = Field(min_length=1, max_length=160)
    step_id: str = Field(min_length=1, max_length=160)
    attempt_id: str = Field(min_length=1, max_length=160)
    generation_token: str = Field(min_length=1)
    fencing_token: str = Field(min_length=1)
    instruction_ref: InstructionRef
    inputs: tuple[InputReference, ...] = ()
    executor: ExecutorKind
    model_profile_id: str | None = None
    model_version: str | None = None
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    budget: BudgetPolicy | None = None
    network: NetworkPolicy = Field(default_factory=lambda: NetworkPolicy(mode="none"))
    capabilities: frozenset[str] = frozenset()
    output: OutputSpec
    gates: GatePolicy = Field(default_factory=GatePolicy)
