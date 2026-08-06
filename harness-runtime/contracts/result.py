"""Harness event/result contracts.

``HarnessResult`` is an UNTRUSTED input from the harness side: the supervisor
must re-compute artifact hashes and generate its own ``ExecutionReceipt``
(H0-C). Nothing in this module may be treated as completion evidence.
``extra="forbid"`` rejects workflow-control fields (``next_stage`` /
``skip_stage`` / ``publish``) fail-closed.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import Field

from .request import StrictContractModel


class HarnessStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class HarnessEvent(StrictContractModel):
    """Structured event emitted by the harness during one attempt.

    Event content is untrusted and must be sanitized before display;
    ``sanitized`` records whether the supervisor already scrubbed it.
    """

    type: Literal["started", "checkpoint", "tool_call", "finished", "failed"]
    payload: dict[str, object] = Field(default_factory=dict)
    attempt_id: str | None = None
    emitted_at: str | None = None
    sanitized: bool = True


class HarnessResult(StrictContractModel):
    """Untrusted result reported by the harness adapter.

    ``output_sha256`` is advisory only — the supervisor recomputes it from
    the staging artifact (H0-C). The contract carries no workflow-control
    fields and refuses unknown ones.
    """

    status: HarnessStatus
    exit_code: int | None = None
    message: str = ""
    output_path: Path | None = None
    output_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
