"""H0-A harness adapter interface.

The product/supervisor side depends only on this Protocol — never on a
concrete Harness product. A specific candidate (e.g. a real CLI) is adapted
by implementing this interface; contracts, supervisor, MCP broker and
enrichment wiring stay unchanged (H0-A conclusion).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from contracts.request import HarnessExecutionRequest
from contracts.result import HarnessEvent, HarnessResult


class HarnessAdapterError(RuntimeError):
    """Adapter-level failure that is not a harness result (e.g. missing input)."""


class HarnessEventSink(Protocol):
    def __call__(self, event: HarnessEvent) -> None: ...


@runtime_checkable
class HarnessAdapter(Protocol):
    """Encapsulates one concrete harness executable shape."""

    adapter_id: str

    def run(
        self,
        request: HarnessExecutionRequest,
        events: HarnessEventSink | None = None,
    ) -> HarnessResult:
        """Run one attempt and return the untrusted result."""
        ...

    def terminate(self) -> None:
        """Best-effort cancellation; must not raise if nothing is running."""
        ...
