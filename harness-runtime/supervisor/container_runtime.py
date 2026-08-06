"""H0-C container runtime contract and hard-coded security baseline.

The supervisor never lets business code override the baseline: image digest
lock, zero network, read-only root, non-root user, resource limits and
stop-timeout are enforced at this boundary (``ContainerConfig`` validation
and fixed ``network_mode``/``user`` defaults).
"""

from __future__ import annotations

from typing import Iterator, Literal, Protocol

from pydantic import Field, field_validator

from contracts.request import StrictContractModel
from contracts.result import HarnessEvent

_IMAGE_WITH_DIGEST = (
    r"^[a-z0-9][a-z0-9._/:-]*:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}$"
)


class ReadOnlyMount(StrictContractModel):
    """Host input directory mounted read-only into the container."""

    host_path: str = Field(min_length=1)
    container_path: str = Field(min_length=1)


class ContainerConfig(StrictContractModel):
    """Locked execution config derived from a HarnessExecutionRequest."""

    image_ref: str = Field(pattern=_IMAGE_WITH_DIGEST)
    command: tuple[str, ...] = ()
    read_only_inputs: tuple[ReadOnlyMount, ...] = ()
    scratch_dir: str = Field(min_length=1)
    staging_dir: str = Field(min_length=1)
    host_scratch_dir: str | None = None
    host_staging_dir: str | None = None
    network_mode: Literal["none"] = "none"
    user: str = Field(default="65534:65534", pattern=r"^\d+:\d+$")
    memory_bytes: int = Field(default=512 * 1024 * 1024, ge=1)
    pids_limit: int = Field(default=128, ge=1)
    stop_timeout_seconds: int = Field(default=10, ge=1)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    tmpfs: tuple[str, ...] = ()
    environment: tuple[tuple[str, str], ...] = ()

    @field_validator("environment")
    @classmethod
    def no_credentials_in_environment(cls, value: tuple[tuple[str, str], ...]) -> tuple[tuple[str, str], ...]:
        for key, _ in value:
            lowered = key.lower()
            if "secret" in lowered or "token" in lowered or "password" in lowered or "key" in lowered:
                raise ValueError(f"credential-like environment variable is forbidden: {key}")
        return value


class ContainerRuntimePort(Protocol):
    """Abstract Docker Engine (or Podman) lifecycle surface."""

    def create(self, config: ContainerConfig) -> str:
        """Create the container; returns a container_id. Must fail if the
        image cannot be resolved to the exact digest."""
        ...

    def start(self, container_id: str) -> None: ...

    def wait(self, container_id: str, timeout_seconds: int) -> int:
        """Block until the container exits (or timeout); returns exit code.
        On timeout the caller decides to terminate."""
        ...

    def events(self, container_id: str) -> Iterator[HarnessEvent]:
        """Yield structured harness events (sanitized by the implementation)."""
        ...

    def logs(self, container_id: str, tail: int = 200) -> str:
        """Sanitized log tail for the ExecutionReceipt summary."""
        ...

    def copy_from(self, container_id: str, container_path: str, host_path: str) -> None:
        """Copy staging output out of the container for host-side scanning."""
        ...

    def terminate(self, container_id: str) -> None:
        """Kill the container and its child processes; never raises."""
        ...

    def remove(self, container_id: str) -> None:
        """Remove the container; never raises."""
        ...
