from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from supervisor.fake_container_runtime import FakeContainerRuntime


class EmptyManagedRuntime(FakeContainerRuntime):
    def __init__(self) -> None:
        super().__init__(exit_code=1)

    def list_managed(self):
        return ()


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
