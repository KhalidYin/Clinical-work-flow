from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from supervisor.fake_container_runtime import FakeContainerRuntime


class EmptyManagedRuntime(FakeContainerRuntime):
    def __init__(self) -> None:
        super().__init__(exit_code=1)

    def list_managed(self):
        return ()


class MountAwareRuntime(EmptyManagedRuntime):
    def __init__(self) -> None:
        super().__init__()
        self.mount_destinations: list[str] = []

    def current_container_mount_source(self, destination: str) -> str:
        self.mount_destinations.append(destination)
        return "/var/lib/docker/volumes/demo-supervisor/_data"


class DistinctMountAwareRuntime(EmptyManagedRuntime):
    def __init__(self) -> None:
        super().__init__()
        self.mount_destinations: list[str] = []

    def current_container_mount_source(self, destination: str) -> str:
        self.mount_destinations.append(destination)
        if destination.endswith("secrets"):
            return "/var/lib/docker/volumes/demo-secrets/_data"
        return "/var/lib/docker/volumes/demo-state/_data"


class InternalNetworkRuntime(EmptyManagedRuntime):
    def __init__(self) -> None:
        super().__init__()
        self.network_names: list[str] = []

    def require_internal_network(self, name: str) -> str:
        self.network_names.append(name)
        return "d" * 64


def test_environment_factory_enables_deepseek_only_with_verified_gateway_binding(
    tmp_path: Path,
) -> None:
    from supervisor.main import build_supervisor_app

    manifest_path = tmp_path / "opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "adapter_id": "opencode@1.18.14",
                "image_ref": (
                    "ghcr.io/anomalyco/opencode:1.18.14@sha256:"
                    + "b" * 64
                ),
                "environment": {"OPENCODE_DISABLE_MODELS_FETCH": "1"},
            }
        ),
        encoding="utf-8",
    )
    gateway_manifest = (
        Path(__file__).resolve().parents[1]
        / "egress"
        / "model-deepseek-v1"
        / "manifest.json"
    )
    runtime = InternalNetworkRuntime()

    app = build_supervisor_app(
        {
            "HARNESS_SUPERVISOR_MACHINE_TOKEN": "synthetic-supervisor-machine-token",
            "HARNESS_SUPERVISOR_ALLOWED_SPEC_SHA256": "a" * 64,
            "HARNESS_SUPERVISOR_IMAGE_MANIFEST_PATH": str(manifest_path),
            "HARNESS_SUPERVISOR_STATE_ROOT": str(tmp_path / "state"),
            "HARNESS_SUPERVISOR_SECRET_ROOT": str(tmp_path / "secrets"),
            "HARNESS_SUPERVISOR_MCP_BRIDGE_PATH": str(
                Path(__file__).resolve().parents[1]
                / "supervisor"
                / "mcp_stdio_bridge.sh"
            ),
            "HARNESS_SUPERVISOR_DEEPSEEK_EGRESS_MANIFEST_PATH": str(
                gateway_manifest
            ),
            "HARNESS_SUPERVISOR_DEEPSEEK_NETWORK_NAME": (
                "clinical-harness-deepseek-client"
            ),
        },
        runtime=runtime,
    )

    assert runtime.network_names == ["clinical-harness-deepseek-client"]
    assert len(app.state.network_runtime_bindings) == 1
    binding = app.state.network_runtime_bindings[0]
    assert binding.policy_id == "model-deepseek-v1"
    assert binding.internal_network_id == "d" * 64


def test_secret_reference_prefers_mounted_file_over_container_environment(
    tmp_path: Path,
) -> None:
    from supervisor.main import resolve_secret_reference

    secret_file = tmp_path / "p15-key"
    secret_file.write_text("synthetic-file-value\n", encoding="utf-8")

    assert resolve_secret_reference(
        "env://SYNTHETIC_PROVIDER_KEY",
        {"SYNTHETIC_PROVIDER_KEY_FILE": str(secret_file)},
    ) == "synthetic-file-value"


def test_secret_reference_resolves_only_through_ephemeral_store(tmp_path: Path) -> None:
    from supervisor.main import resolve_secret_reference
    from supervisor.secret_store import TmpfsSecretStore

    store = TmpfsSecretStore(
        root=tmp_path,
        allowed_names=frozenset({"deepseek-api-key"}),
        clear_on_start=True,
    )
    store.inject("deepseek-api-key", "synthetic-opaque-value")

    assert resolve_secret_reference(
        "secret://deepseek-api-key",
        {},
        secret_store=store,
    ) == "synthetic-opaque-value"


def test_environment_factory_builds_private_supervisor_service(tmp_path: Path) -> None:
    from supervisor.main import build_supervisor_app

    manifest_path = tmp_path / "opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "adapter_id": "opencode@1.18.14",
                "image_ref": "ghcr.io/anomalyco/opencode:1.18.14@sha256:" + "b" * 64,
                "environment": {
                    "OPENCODE_DISABLE_MODELS_FETCH": "1",
                    "OPENCODE_DISABLE_AUTOUPDATE": "true",
                },
            }
        ),
        encoding="utf-8",
    )
    values = {
        "HARNESS_SUPERVISOR_MACHINE_TOKEN": "synthetic-supervisor-machine-token",
        "HARNESS_SUPERVISOR_ALLOWED_SPEC_SHA256": "a" * 64,
        "HARNESS_SUPERVISOR_IMAGE_MANIFEST_PATH": str(manifest_path),
        "HARNESS_SUPERVISOR_STATE_ROOT": str(tmp_path / "state"),
        "HARNESS_SUPERVISOR_SECRET_ROOT": str(tmp_path / "secrets"),
        "HARNESS_SUPERVISOR_MCP_BRIDGE_PATH": str(
            Path(__file__).resolve().parents[1] / "supervisor" / "mcp_stdio_bridge.sh"
        ),
        "SYNTHETIC_PROVIDER_KEY": "synthetic-offline-provider-key",
    }

    app = build_supervisor_app(values, runtime=EmptyManagedRuntime())

    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "network_policy": "none",
        "adapter_id": "opencode@1.18.14",
    }


def test_environment_factory_requires_ephemeral_secret_root(tmp_path: Path) -> None:
    from supervisor.main import build_supervisor_app

    manifest_path = tmp_path / "opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "adapter_id": "opencode@1.18.14",
                "image_ref": "ghcr.io/anomalyco/opencode:1.18.14@sha256:" + "b" * 64,
                "environment": {"OPENCODE_DISABLE_MODELS_FETCH": "1"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="HARNESS_SUPERVISOR_SECRET_ROOT is required",
    ):
        build_supervisor_app(
            {
                "HARNESS_SUPERVISOR_MACHINE_TOKEN": "synthetic-supervisor-machine-token",
                "HARNESS_SUPERVISOR_ALLOWED_SPEC_SHA256": "a" * 64,
                "HARNESS_SUPERVISOR_IMAGE_MANIFEST_PATH": str(manifest_path),
                "HARNESS_SUPERVISOR_STATE_ROOT": str(tmp_path / "state"),
                "HARNESS_SUPERVISOR_MCP_BRIDGE_PATH": str(
                    Path(__file__).resolve().parents[1]
                    / "supervisor"
                    / "mcp_stdio_bridge.sh"
                ),
            },
            runtime=EmptyManagedRuntime(),
        )


def test_container_factory_discovers_daemon_visible_state_mount(tmp_path: Path) -> None:
    from supervisor.main import build_supervisor_app

    manifest_path = tmp_path / "opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "adapter_id": "opencode@1.18.14",
                "image_ref": "ghcr.io/anomalyco/opencode:1.18.14@sha256:" + "b" * 64,
                "environment": {"OPENCODE_DISABLE_MODELS_FETCH": "1"},
            }
        ),
        encoding="utf-8",
    )
    state_root = tmp_path / "state"
    runtime = MountAwareRuntime()
    app = build_supervisor_app(
        {
            "HARNESS_SUPERVISOR_MACHINE_TOKEN": "synthetic-supervisor-machine-token",
            "HARNESS_SUPERVISOR_ALLOWED_SPEC_SHA256": "a" * 64,
            "HARNESS_SUPERVISOR_IMAGE_MANIFEST_PATH": str(manifest_path),
            "HARNESS_SUPERVISOR_STATE_ROOT": str(state_root),
            "HARNESS_SUPERVISOR_SECRET_ROOT": str(tmp_path / "secrets"),
            "HARNESS_SUPERVISOR_MCP_BRIDGE_PATH": str(
                Path(__file__).resolve().parents[1]
                / "supervisor"
                / "mcp_stdio_bridge.sh"
            ),
            "HARNESS_SUPERVISOR_DISCOVER_DAEMON_STATE_ROOT": "true",
        },
        runtime=runtime,
    )

    assert runtime.mount_destinations == [str(state_root), str(tmp_path / "secrets")]
    assert app.state.daemon_state_root == (
        "/var/lib/docker/volumes/demo-supervisor/_data"
    )
    assert app.state.daemon_secret_root == (
        "/var/lib/docker/volumes/demo-supervisor/_data"
    )


def test_container_factory_discovers_distinct_ephemeral_secret_mount(
    tmp_path: Path,
) -> None:
    from supervisor.main import build_supervisor_app

    manifest_path = tmp_path / "opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "adapter_id": "opencode@1.18.14",
                "image_ref": "ghcr.io/anomalyco/opencode:1.18.14@sha256:" + "b" * 64,
                "environment": {"OPENCODE_DISABLE_MODELS_FETCH": "1"},
            }
        ),
        encoding="utf-8",
    )
    state_root = tmp_path / "state"
    secret_root = tmp_path / "secrets"
    secret_root.mkdir()
    (secret_root / "orphan-marker").write_text(
        "synthetic-marker",
        encoding="utf-8",
    )
    runtime = DistinctMountAwareRuntime()

    app = build_supervisor_app(
        {
            "HARNESS_SUPERVISOR_MACHINE_TOKEN": "synthetic-supervisor-machine-token",
            "HARNESS_SUPERVISOR_ALLOWED_SPEC_SHA256": "a" * 64,
            "HARNESS_SUPERVISOR_IMAGE_MANIFEST_PATH": str(manifest_path),
            "HARNESS_SUPERVISOR_STATE_ROOT": str(state_root),
            "HARNESS_SUPERVISOR_SECRET_ROOT": str(secret_root),
            "HARNESS_SUPERVISOR_MCP_BRIDGE_PATH": str(
                Path(__file__).resolve().parents[1]
                / "supervisor"
                / "mcp_stdio_bridge.sh"
            ),
            "HARNESS_SUPERVISOR_DISCOVER_DAEMON_STATE_ROOT": "true",
        },
        runtime=runtime,
    )

    assert runtime.mount_destinations == [str(state_root), str(secret_root)]
    assert app.state.daemon_state_root == "/var/lib/docker/volumes/demo-state/_data"
    assert app.state.daemon_secret_root == "/var/lib/docker/volumes/demo-secrets/_data"
    assert tuple(secret_root.iterdir()) == ()


def test_environment_factory_configures_pack_and_verified_internal_mock(
    tmp_path: Path,
) -> None:
    from supervisor.main import build_supervisor_app
    from supervisor.pack_compiler import HarnessPackResolver

    project_root = Path(__file__).resolve().parents[2]
    pack_root = (
        project_root
        / "clinical-llm-wiki"
        / "harness-packs"
        / "knowledge-candidate-v1"
    )
    image_ref = (
        "ghcr.io/anomalyco/opencode:1.18.14@sha256:"
        "16a66f622a0bb0b4bb2a05242749907704a4149ef25805932c067d5afb340f6a"
    )
    manifest_path = tmp_path / "opencode.json"
    manifest_path.write_text(
        json.dumps(
            {
                "adapter_id": "opencode@1.18.14",
                "image_ref": image_ref,
                "environment": {"OPENCODE_DISABLE_MODELS_FETCH": "1"},
            }
        ),
        encoding="utf-8",
    )
    pack_sha256 = HarnessPackResolver(
        {"knowledge-candidate-v1": pack_root}
    ).measure("knowledge-candidate-v1")
    runtime = InternalNetworkRuntime()

    app = build_supervisor_app(
        {
            "HARNESS_SUPERVISOR_MACHINE_TOKEN": "synthetic-supervisor-machine-token",
            "HARNESS_SUPERVISOR_ALLOWED_SPEC_SHA256": "a" * 64,
            "HARNESS_SUPERVISOR_IMAGE_MANIFEST_PATH": str(manifest_path),
            "HARNESS_SUPERVISOR_STATE_ROOT": str(tmp_path / "state"),
            "HARNESS_SUPERVISOR_SECRET_ROOT": str(tmp_path / "secrets"),
            "HARNESS_SUPERVISOR_MCP_BRIDGE_PATH": str(
                Path(__file__).resolve().parents[1]
                / "supervisor"
                / "mcp_stdio_bridge.sh"
            ),
            "HARNESS_SUPERVISOR_PACK_ID": "knowledge-candidate-v1",
            "HARNESS_SUPERVISOR_PACK_ROOT": str(pack_root),
            "HARNESS_SUPERVISOR_MODEL_PROVIDER": "openai",
            "HARNESS_SUPERVISOR_MODEL_ID": "gpt-4o-mini",
            "HARNESS_SUPERVISOR_MODEL_BASE_URL": (
                "http://p15-openai-mock:8080/v1"
            ),
            "HARNESS_SUPERVISOR_INTERNAL_NETWORK_NAME": "p15-model-internal",
            "SYNTHETIC_PROVIDER_KEY": "synthetic-offline-provider-key",
        },
        runtime=runtime,
    )

    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "network_policy": "internal-only",
        "adapter_id": "opencode@1.18.14",
        "pack_id": "knowledge-candidate-v1",
        "pack_sha256": pack_sha256,
        "model_ref": "openai/gpt-4o-mini",
    }
    assert runtime.network_names == ["p15-model-internal"]
