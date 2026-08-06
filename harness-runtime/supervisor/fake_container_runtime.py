"""H0-C fake container runtime for lifecycle tests (no Docker required).

Mimics the ``ContainerRuntimePort`` surface with deterministic outcomes:
exit code, hang (timeout), staged outputs to copy out, and recorded config
so tests can assert the security baseline (network none, read-only mounts).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from contracts.result import HarnessEvent
from supervisor.container_runtime import ContainerConfig


class FakeContainerRuntime:
    """Deterministic in-memory ContainerRuntimePort implementation."""

    def __init__(
        self,
        *,
        exit_code: int | None,
        staged_outputs: dict[Path, bytes] | None = None,
        hangs: bool = False,
        cancel_signal: bool = False,
    ) -> None:
        self.exit_code = exit_code
        self.staged_outputs = staged_outputs or {}
        self.hangs = hangs
        self.cancel_signal = cancel_signal
        self.last_config: ContainerConfig | None = None
        self.terminate_called = False
        self.remove_called = False
        self._events = (
            HarnessEvent(type="started", payload={}),
            HarnessEvent(type="checkpoint", payload={"phase": "draft"}),
            HarnessEvent(type="finished", payload={}),
        )

    # -- ContainerRuntimePort surface --------------------------------------

    def create(self, config: ContainerConfig) -> str:
        self.last_config = config
        return "fake-container-0001"

    def start(self, container_id: str) -> None:
        return None

    def wait(self, container_id: str, timeout_seconds: int) -> int | None:
        if self.hangs:
            return None  # timed out, container still running
        return self.exit_code

    def events(self, container_id: str) -> Iterator[HarnessEvent]:
        yield from self._events

    def logs(self, container_id: str, tail: int = 200) -> str:
        return "\n".join(
            f'{{"type": "{event.type}"}}' for event in self._events[-tail:]
        )

    def copy_from(self, container_id: str, container_path: str, host_path: str) -> None:
        destination = Path(host_path)
        destination.mkdir(parents=True, exist_ok=True)
        for source_path, data in self.staged_outputs.items():
            (destination / source_path.name).write_bytes(data)

    def terminate(self, container_id: str) -> None:
        self.terminate_called = True

    def remove(self, container_id: str) -> None:
        self.remove_called = True
