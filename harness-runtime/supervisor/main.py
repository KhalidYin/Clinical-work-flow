"""Environment-driven entrypoint for the isolated Harness Supervisor service."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from supervisor.container_runtime import (
    ContainerRuntimePort,
    DaemonRootPathMapper,
)
from supervisor.docker_runtime import DockerEngineContainerRuntime
from supervisor.journal import FileAttemptJournal
from supervisor.lifecycle import AttemptCoordinator, FileAttemptResultStore
from supervisor.opencode_executor import OpenCodeAttemptExecutor
from supervisor.service import create_supervisor_app


def _required(values: Mapping[str, str], name: str) -> str:
    value = values.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _sha256(value: str, name: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise RuntimeError(f"{name} must be a lowercase SHA-256")
    return value


def build_supervisor_app(
    environ: Mapping[str, str] | None = None,
    *,
    runtime: ContainerRuntimePort | None = None,
) -> FastAPI:
    values = os.environ if environ is None else environ
    machine_token = _required(values, "HARNESS_SUPERVISOR_MACHINE_TOKEN")
    allowed_spec = _sha256(
        _required(values, "HARNESS_SUPERVISOR_ALLOWED_SPEC_SHA256"),
        "HARNESS_SUPERVISOR_ALLOWED_SPEC_SHA256",
    )
    manifest_path = Path(_required(values, "HARNESS_SUPERVISOR_IMAGE_MANIFEST_PATH"))
    try:
        manifest: Any = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("OpenCode image manifest is unreadable") from exc
    if not isinstance(manifest, dict) or manifest.get("adapter_id") != "opencode@1.18.14":
        raise RuntimeError("OpenCode image manifest has an unsupported adapter_id")
    image_ref = manifest.get("image_ref")
    environment = manifest.get("environment")
    if not isinstance(image_ref, str) or not isinstance(environment, dict):
        raise RuntimeError("OpenCode image manifest is missing image_ref/environment")

    state_root = Path(_required(values, "HARNESS_SUPERVISOR_STATE_ROOT")).resolve()
    mcp_bridge_path = Path(_required(values, "HARNESS_SUPERVISOR_MCP_BRIDGE_PATH"))
    lease_seconds = int(values.get("HARNESS_SUPERVISOR_LEASE_SECONDS", "30"))
    if lease_seconds < 1:
        raise RuntimeError("HARNESS_SUPERVISOR_LEASE_SECONDS must be positive")

    container_runtime = runtime or DockerEngineContainerRuntime()
    discover_daemon_root = values.get(
        "HARNESS_SUPERVISOR_DISCOVER_DAEMON_STATE_ROOT",
        "false",
    ).lower()
    if discover_daemon_root not in {"true", "false"}:
        raise RuntimeError(
            "HARNESS_SUPERVISOR_DISCOVER_DAEMON_STATE_ROOT must be true or false"
        )
    daemon_state_root: str | None = None
    host_path_mapper = None
    if discover_daemon_root == "true":
        discover_mount = getattr(
            container_runtime,
            "current_container_mount_source",
            None,
        )
        if not callable(discover_mount):
            raise RuntimeError("container runtime cannot discover its state mount")
        daemon_state_root = discover_mount(str(state_root))
        host_path_mapper = DaemonRootPathMapper(
            local_root=state_root,
            daemon_root=daemon_state_root,
        )

    def resolve_secret(reference: str) -> str:
        scheme, separator, name = reference.partition("://")
        if separator != "://" or scheme != "env":
            raise ValueError("this deployment supports env:// secret references only")
        value = values.get(name)
        if not value:
            raise ValueError("required model secret reference is not configured")
        return value

    executor = OpenCodeAttemptExecutor(
        runtime=container_runtime,
        image_ref=image_ref,
        mcp_bridge_path=mcp_bridge_path,
        secret_resolver=resolve_secret,
        workspace_root=state_root / "workspaces",
        environment=tuple((str(key), str(value)) for key, value in environment.items()),
        host_path_mapper=host_path_mapper,
    )
    journal = FileAttemptJournal(state_root / "journal")
    result_store = FileAttemptResultStore(state_root / "results")
    pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="harness-attempt")
    coordinator = AttemptCoordinator(
        journal=journal,
        result_store=result_store,
        executor=executor,
        clock=lambda: datetime.now(timezone.utc),
        lease_seconds=lease_seconds,
        submit=pool.submit,
    )
    app = create_supervisor_app(
        machine_token=machine_token,
        allowed_spec_sha256=frozenset({allowed_spec}),
        dispatch=coordinator.dispatch,
        cancel_attempt=executor.cancel,
        recover_orphan=executor.recover_orphan,
        journal=journal,
        result_store=result_store,
        lease_seconds=lease_seconds,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "network_policy": "none",
            "adapter_id": "opencode@1.18.14",
        }

    app.state.attempt_pool = pool
    app.state.daemon_state_root = daemon_state_root
    app.router.add_event_handler(
        "shutdown",
        lambda: pool.shutdown(wait=True, cancel_futures=False),
    )
    return app


def main() -> None:
    import uvicorn

    uvicorn.run(
        build_supervisor_app(),
        host=os.environ.get("HARNESS_SUPERVISOR_HOST", "0.0.0.0"),
        port=int(os.environ.get("HARNESS_SUPERVISOR_PORT", "8790")),
    )


if __name__ == "__main__":
    main()
