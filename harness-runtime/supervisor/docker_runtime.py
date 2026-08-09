"""H0-C Docker Engine runtime implementation (docker-py, lazily imported).

docker-py is NOT installed in the default dev environment: import happens on
first use, and the integration tests are skipped via importorskip. The
security baseline (digest-locked image, network none, read-only root,
non-root user, dropped capabilities, resource limits, stop timeout) is enforced here and in
``ContainerConfig`` validation.
"""

from __future__ import annotations

import json
import os
import tarfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from contracts.result import HarnessEvent
from supervisor.container_runtime import ContainerConfig, ManagedContainer
from supervisor.staging import StagingScanError


class DockerEngineContainerRuntime:
    """ContainerRuntimePort over the Docker Engine API."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client
        self._stop_timeouts: dict[str, int] = {}

    def _docker(self) -> Any:
        if self._client is not None:
            return self._client
        import docker  # delayed: docker-py is optional in the skeleton

        self._client = docker.from_env()
        return self._client

    # -- lifecycle ----------------------------------------------------------

    def create(self, config: ContainerConfig) -> str:
        client = self._docker()
        volumes: dict[str, dict[str, str]] = {}
        for mount in config.read_only_inputs:
            volumes[mount.host_path] = {"bind": mount.container_path, "mode": "ro"}
        if config.host_scratch_dir:
            volumes[config.host_scratch_dir] = {"bind": config.scratch_dir, "mode": "rw"}
        if config.host_staging_dir:
            volumes[config.host_staging_dir] = {"bind": config.staging_dir, "mode": "rw"}
        create_kwargs: dict[str, Any] = dict(
            image=config.image_ref,
            command=list(config.command),
            network_mode=config.network_mode,
            user=config.user,
            read_only=True,
            mem_limit=config.memory_bytes,
            pids_limit=config.pids_limit,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            init=True,
            tmpfs=dict(config.tmpfs),
            volumes=volumes,
            environment=dict(config.environment),
            labels={
                **dict(config.labels),
                "clinical.harness.attempt": "managed",
            },
        )
        if config.entrypoint:
            create_kwargs["entrypoint"] = list(config.entrypoint)
        container = client.containers.create(**create_kwargs)
        self._stop_timeouts[container.id] = config.stop_timeout_seconds
        return container.id

    def start(self, container_id: str) -> None:
        self._docker().containers.get(container_id).start()

    def wait(self, container_id: str, timeout_seconds: int) -> int | None:
        container = self._docker().containers.get(container_id)
        try:
            result = container.wait(timeout=timeout_seconds)
        except Exception:
            return None  # timed out; caller decides to terminate
        return int(result.get("StatusCode", -1))

    def events(self, container_id: str) -> Iterator[HarnessEvent]:
        container = self._docker().containers.get(container_id)
        try:
            logs = container.logs(stdout=True, stderr=True).decode(
                "utf-8", errors="replace"
            )
        except Exception:
            logs = ""
        for line in logs.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and "type" in data:
                yield HarnessEvent(
                    type=data["type"],
                    payload=data.get("payload", {}),
                )

    def logs(self, container_id: str, tail: int = 200) -> str:
        container = self._docker().containers.get(container_id)
        try:
            return container.logs(tail=tail).decode("utf-8", errors="replace")
        except Exception:
            return ""

    def copy_from(self, container_id: str, container_path: str, host_path: str) -> None:
        container = self._docker().containers.get(container_id)
        stream, _ = container.get_archive(container_path)
        destination_root = Path(host_path).resolve()
        with tarfile.open(fileobj=_ChunkIteratorReader(stream), mode="r|") as archive:
            for member in archive:
                target = (destination_root / member.name).resolve()
                if destination_root not in target.parents and target != destination_root:
                    raise StagingScanError(
                        f"archive path escapes staging root: {member.name}"
                    )
                archive.extract(member, destination_root)

    def terminate(self, container_id: str) -> None:
        try:
            container = self._docker().containers.get(container_id)
            container.stop(timeout=self._stop_timeouts.get(container_id, 10))
        except Exception:
            try:
                self._docker().containers.get(container_id).kill()
            except Exception:
                pass

    def remove(self, container_id: str) -> None:
        try:
            self._docker().containers.get(container_id).remove(force=True)
        except Exception:
            pass
        finally:
            self._stop_timeouts.pop(container_id, None)

    def list_managed(self) -> tuple[ManagedContainer, ...]:
        containers = self._docker().containers.list(
            all=True,
            filters={"label": "clinical.harness.attempt=managed"},
        )
        managed: list[ManagedContainer] = []
        for container in containers:
            labels = container.attrs.get("Config", {}).get("Labels", {}) or {}
            try:
                managed.append(
                    ManagedContainer(
                        container_id=container.id,
                        attempt_id=labels["clinical.harness.attempt_id"],
                        request_sha256=labels["clinical.harness.request_sha256"],
                        spec_sha256=labels["clinical.harness.spec_sha256"],
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return tuple(sorted(managed, key=lambda item: item.attempt_id))

    def current_container_mount_source(
        self,
        destination: str,
        *,
        container_id: str | None = None,
    ) -> str:
        """Return the daemon-visible source for this container's exact mount."""

        identity = container_id or os.environ.get("HOSTNAME")
        if not identity:
            raise RuntimeError("Supervisor container identity is not available")
        container = self._docker().containers.get(identity)
        mounts = container.attrs.get("Mounts", [])
        matches = [
            mount
            for mount in mounts
            if isinstance(mount, dict)
            and mount.get("Destination") == destination
            and mount.get("Type") in {"bind", "volume"}
            and isinstance(mount.get("Source"), str)
        ]
        if len(matches) != 1:
            raise RuntimeError("Supervisor state mount is not available")
        source = str(matches[0]["Source"]).rstrip("/")
        if not source.startswith("/"):
            raise RuntimeError("Supervisor state mount source is not absolute")
        return source


class _ChunkIteratorReader:
    """Expose docker-py's archive chunk iterator as tarfile's read surface."""

    def __init__(self, chunks: Any) -> None:
        self._chunks = iter(chunks)
        self._buffer = bytearray()
        self._exhausted = False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            for chunk in self._chunks:
                self._buffer.extend(chunk)
            result = bytes(self._buffer)
            self._buffer.clear()
            self._exhausted = True
            return result
        while len(self._buffer) < size and not self._exhausted:
            try:
                self._buffer.extend(next(self._chunks))
            except StopIteration:
                self._exhausted = True
        result = bytes(self._buffer[:size])
        del self._buffer[:size]
        return result
