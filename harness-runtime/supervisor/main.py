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
from supervisor.egress_gateway import load_network_runtime_binding
from supervisor.journal import FileAttemptJournal
from supervisor.lifecycle import AttemptCoordinator, FileAttemptResultStore
from supervisor.network_policy import p16_network_policy_registry
from supervisor.opencode_executor import OpenCodeAttemptExecutor
from supervisor.pack_compiler import (
    HarnessPackCompiler,
    HarnessPackResolver,
    McpCapabilityBinding,
    OpenAICompatibleModelBinding,
)
from supervisor.service import create_supervisor_app
from supervisor.secret_store import P16_EPHEMERAL_SECRET_NAMES, TmpfsSecretStore


def _required(values: Mapping[str, str], name: str) -> str:
    value = values.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def resolve_secret_reference(
    reference: str,
    values: Mapping[str, str],
    *,
    secret_store: TmpfsSecretStore | None = None,
) -> str:
    """Resolve a legacy env reference or an opaque ephemeral-store reference."""

    scheme, separator, name = reference.partition("://")
    if separator != "://":
        raise ValueError("secret reference scheme is invalid")
    if scheme == "secret":
        if secret_store is None:
            raise ValueError("ephemeral secret store is unavailable")
        return secret_store.resolve(reference)
    if scheme != "env":
        raise ValueError("secret reference scheme is not supported")
    file_path = values.get(f"{name}_FILE")
    if file_path:
        try:
            value = Path(file_path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ValueError("required model secret file is unavailable") from exc
    else:
        value = values.get(name, "")
    if not value:
        raise ValueError("required model secret reference is not configured")
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
    secret_root = Path(_required(values, "HARNESS_SUPERVISOR_SECRET_ROOT")).resolve()
    secret_store = TmpfsSecretStore(
        root=secret_root,
        allowed_names=P16_EPHEMERAL_SECRET_NAMES,
        clear_on_start=True,
    )
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
    daemon_secret_root: str | None = None
    host_path_mapper = None
    secret_path_mapper = None
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
        daemon_secret_root = discover_mount(str(secret_root))
        secret_path_mapper = DaemonRootPathMapper(
            local_root=secret_root,
            daemon_root=daemon_secret_root,
        )

    def resolve_secret(reference: str) -> str:
        return resolve_secret_reference(
            reference,
            values,
            secret_store=secret_store,
        )

    pack_environment_names = (
        "HARNESS_SUPERVISOR_PACK_ID",
        "HARNESS_SUPERVISOR_PACK_ROOT",
        "HARNESS_SUPERVISOR_MODEL_PROVIDER",
        "HARNESS_SUPERVISOR_MODEL_ID",
        "HARNESS_SUPERVISOR_MODEL_BASE_URL",
        "HARNESS_SUPERVISOR_INTERNAL_NETWORK_NAME",
    )
    configured_pack_values = [values.get(name) for name in pack_environment_names]
    if any(configured_pack_values) and not all(configured_pack_values):
        raise RuntimeError("all Harness Pack POC settings must be configured together")
    pack_resolver = None
    pack_compiler = None
    internal_network_id = None
    pack_sha256 = None
    model_ref = None
    pack_id = None
    if all(configured_pack_values):
        pack_id = _required(values, "HARNESS_SUPERVISOR_PACK_ID")
        pack_root = Path(_required(values, "HARNESS_SUPERVISOR_PACK_ROOT"))
        pack_resolver = HarnessPackResolver({pack_id: pack_root})
        pack_sha256 = pack_resolver.measure(pack_id)
        model_binding = OpenAICompatibleModelBinding(
            provider_id=_required(values, "HARNESS_SUPERVISOR_MODEL_PROVIDER"),
            model_id=_required(values, "HARNESS_SUPERVISOR_MODEL_ID"),
            base_url=_required(values, "HARNESS_SUPERVISOR_MODEL_BASE_URL"),
        )
        model_ref = model_binding.model_ref
        pack_compiler = HarnessPackCompiler(
            {
                "knowledge.read-evidence": McpCapabilityBinding(
                    capability_id="knowledge.read-evidence",
                    server_name="clinical_attempt",
                    tools=frozenset({"read_evidence"}),
                    command=(
                        "/bin/sh",
                        "/harness/mcp_stdio_bridge.sh",
                        "/harness/mcp-bundle.json",
                        "/staging/mcp-audit.jsonl",
                    ),
                )
            },
            model_binding=model_binding,
        )
        require_internal_network = getattr(
            container_runtime,
            "require_internal_network",
            None,
        )
        if not callable(require_internal_network):
            raise RuntimeError("container runtime cannot verify the POC model network")
        internal_network_id = require_internal_network(
            _required(values, "HARNESS_SUPERVISOR_INTERNAL_NETWORK_NAME")
        )

    gateway_manifest_path = values.get(
        "HARNESS_SUPERVISOR_DEEPSEEK_EGRESS_MANIFEST_PATH",
        "",
    )
    gateway_network_name = values.get(
        "HARNESS_SUPERVISOR_DEEPSEEK_NETWORK_NAME",
        "",
    )
    if bool(gateway_manifest_path) != bool(gateway_network_name):
        raise RuntimeError("DeepSeek gateway deployment configuration is incomplete")
    network_runtime_bindings = ()
    available_policy_ids = frozenset({"none"})
    if gateway_manifest_path:
        network_runtime_bindings = (
            load_network_runtime_binding(
                manifest_path=Path(gateway_manifest_path),
                network_name=gateway_network_name,
                runtime=container_runtime,
            ),
        )
        available_policy_ids = frozenset({"none", "model-deepseek-v1"})

    network_policy_registry = p16_network_policy_registry(
        available_policy_ids=available_policy_ids
    )
    executor = OpenCodeAttemptExecutor(
        runtime=container_runtime,
        image_ref=image_ref,
        mcp_bridge_path=mcp_bridge_path,
        secret_resolver=resolve_secret,
        workspace_root=state_root / "workspaces",
        secret_workspace_root=secret_root,
        environment=tuple((str(key), str(value)) for key, value in environment.items()),
        pack_resolver=pack_resolver,
        pack_compiler=pack_compiler,
        trusted_internal_network_id=internal_network_id,
        host_path_mapper=host_path_mapper,
        secret_path_mapper=secret_path_mapper,
        network_runtime_bindings=network_runtime_bindings,
        network_policy_registry=network_policy_registry,
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
        network_policy_registry=network_policy_registry,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        projection = {
            "status": "ok",
            "network_policy": (
                "internal-only" if internal_network_id is not None else "none"
            ),
            "adapter_id": "opencode@1.18.14",
        }
        if pack_id is not None and pack_sha256 is not None and model_ref is not None:
            projection.update(
                {
                    "pack_id": pack_id,
                    "pack_sha256": pack_sha256,
                    "model_ref": model_ref,
                }
            )
        return projection

    app.state.attempt_pool = pool
    app.state.daemon_state_root = daemon_state_root
    app.state.daemon_secret_root = daemon_secret_root
    app.state.network_runtime_bindings = network_runtime_bindings
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
