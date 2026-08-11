"""Versioned product-level contracts for the Supervisor control plane."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from contracts.receipt import ExecutionReceipt
from contracts.request import StrictContractModel
from contracts.spec import InstructionRef


def canonical_sha256(value: object) -> str:
    """Hash a JSON value using the wire contract's canonical encoding."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SupervisorAttemptRequest(BaseModel):
    """Product-level Attempt request; no container configuration is accepted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["1.0.0"] = "1.0.0"
    attempt_id: str = Field(min_length=1, max_length=160)
    run_id: str = Field(min_length=1, max_length=160)
    step_id: str = Field(min_length=1, max_length=160)
    generation_token: str = Field(min_length=1, max_length=256)
    fencing_token: str = Field(min_length=1, max_length=256)
    adapter_id: Literal["opencode@1.18.14"]
    spec_sha256: str
    input_sha256: str
    input_bundle: dict[str, object]
    instruction_ref: InstructionRef | None = None
    secret_refs: tuple[str, ...] = ()
    network_policy_id: str = Field(
        default="none",
        pattern=r"^[a-z0-9][a-z0-9.-]{0,99}$",
    )
    model_egress: "ModelEgressBinding | None" = None
    capabilities: frozenset[str] = frozenset()
    timeout_seconds: int = Field(default=60, ge=1, le=3600)
    network_mode: Literal["none"] = "none"

    @field_validator("secret_refs")
    @classmethod
    def validate_secret_refs(cls, refs: tuple[str, ...]) -> tuple[str, ...]:
        import re

        pattern = re.compile(
            r"^(?:env|secret)://[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"
        )
        if any(pattern.fullmatch(ref) is None for ref in refs):
            raise ValueError("secret references must use an approved scheme and safe name")
        return refs

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities(cls, values: frozenset[str]) -> frozenset[str]:
        import re

        pattern = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
        if any(pattern.fullmatch(value) is None for value in values):
            raise ValueError("capability identifiers must use the canonical safe form")
        return values

    def request_sha256(self) -> str:
        # Hash the actual wire fields so additive optional contract fields do
        # not silently invalidate already-supported clients.
        payload = self.model_dump(mode="json", exclude_unset=True)
        return canonical_sha256(payload)


class ModelEgressBinding(BaseModel):
    """Requested model identity and data boundary, never a routing decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str = Field(min_length=1, max_length=160)
    profile_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    provider: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,99}$")
    model: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
    endpoint: str = Field(
        min_length=1,
        max_length=500,
        pattern=r"^https://[^/?#]+(?::[0-9]{1,5})?(?:/[^?#]*)?$",
    )
    data_boundary: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,99}$")


class SupervisorAttemptStatus(StrictContractModel):
    """Credential-free status projection returned to the product worker."""

    contract_version: Literal["1.0.0"] = "1.0.0"
    attempt_id: str = Field(min_length=1, max_length=160)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: Literal[
        "accepted",
        "running",
        "succeeded",
        "failed",
        "cancelled",
        "timed_out",
        "orphaned",
    ]
    receipt: ExecutionReceipt | None = None


class SupervisorAttemptResult(StrictContractModel):
    """Terminal Receipt plus the separately stored untrusted output bundle."""

    contract_version: Literal["1.0.0"] = "1.0.0"
    attempt_id: str = Field(min_length=1, max_length=160)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    receipt: ExecutionReceipt
    output_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    output_bundle: dict[str, object] | None = None
