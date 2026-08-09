"""Versioned product-level contracts for the Supervisor control plane."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.receipt import ExecutionReceipt
from contracts.request import StrictContractModel


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
    secret_refs: tuple[str, ...] = ()
    timeout_seconds: int = Field(default=60, ge=1, le=3600)
    network_mode: Literal["none"] = "none"

    def request_sha256(self) -> str:
        return canonical_sha256(self.model_dump(mode="json"))


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
