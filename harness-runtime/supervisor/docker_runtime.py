"""H0-C Docker Engine runtime implementation (docker-py, lazily imported).

docker-py is NOT installed in the default dev environment: import happens on
first use, and the integration tests are skipped via importorskip. The
security baseline (digest-locked image, network none, read-only root,
non-root user, resource limits, stop timeout) is enforced here and in
``ContainerConfig`` validation.
"""

from __future__ import annotations

import json
import tarfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from contracts.result import HarnessEvent
from supervisor.container_runtime import ContainerConfig
from supervisor.staging import StagingScanError


class DockerEngineContainerRuntime:
    """ContainerRuntimePort over the Docker Engine API."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

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
        container = client.containers.create(
            image=config.image_ref,
            command=list(config.command),
            network_mode=config.network_mode,
            user=config.user,
            read_only=True,
            mem_limit=config.memory_bytes,
            pids_limit=config.pids_limit,
            stop_timeout=config.stop_timeout_seconds,
            volumes=volumes,
            environment=dict(config.environment),
            labels={"clinical.harness.attempt": "managed"},
        )
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
        with tarfile.open(fileobj=stream, mode="r|") as archive:
            for member in archive:
                target = (destination_root / member.name).resolve()
                if destination_root not in target.parents and target != destination_root:
                    raise StagingScanError(
                        f"archive path escapes staging root: {member.name}"
                    )
                archive.extract(member, destination_root)

    def terminate(self, container_id: str) -> None:
        try:
            self._docker().containers.get(container_id).kill()
        except Exception:
            pass

    def remove(self, container_id: str) -> None:
        try:
            self._docker().containers.get(container_id).remove(force=True)
        except Exception:
            pass
