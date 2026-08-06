"""Harness execution request contract.

H0-B extends the H0-A minimal request with the full step-scoped execution
bundle: spec hash link, step-scoped MCP config, secret references, network
allowlist and event/receipt targets. All added fields have defaults so the
H0-A adapter contract tests keep passing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictContractModel(BaseModel):
    """Reject unknown fields so configuration drift fails closed."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class McpConfig(StrictContractModel):
    """Step-scoped MCP capability bundle (H0-E broker consumes this)."""

    transport: Literal["stdio", "sse", "http"] = "stdio"
    tools: frozenset[str] = frozenset()


class HarnessExecutionRequest(StrictContractModel):
    """A single step-scoped execution request for one harness attempt.

    ``payload`` is a stand-in for the H0-B hash-locked input/context bundle
    (Evidence refs, Step Pack refs). It is treated as untrusted content.
    """

    attempt_id: str = Field(min_length=1, max_length=160)
    adapter_id: str = Field(min_length=1, max_length=160)
    spec_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    image_ref: str | None = Field(
        default=None,
        pattern=r"^[a-z0-9][a-z0-9._/:-]*:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}$",
        description="Locked OCI image with digest; required for executor_kind=harness",
    )
    input_path: Path
    scratch_path: Path
    output_path: Path
    timeout_seconds: int = Field(default=60, ge=1, le=3600)
    payload: dict[str, object] = Field(default_factory=dict)
    mcp_config: McpConfig | None = None
    secret_refs: tuple[str, ...] = ()
    network_allowlist: frozenset[str] = frozenset()
    events_target: Path | None = None
    receipt_target: Path | None = None
