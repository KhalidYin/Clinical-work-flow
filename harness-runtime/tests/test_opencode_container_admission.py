"""Production-container admission checks for the pinned OpenCode image.

These tests never configure a real provider credential and always use Docker's
``network_mode=none``. They skip when the admitted image is not already local.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from supervisor.container_runtime import ContainerConfig, ReadOnlyMount
from supervisor.docker_runtime import DockerEngineContainerRuntime

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "images" / "opencode-1.18.14.json"
MCP_FIXTURE = Path(__file__).parent / "fixtures" / "fake_mcp_stdio.sh"
MCP_BRIDGE = ROOT / "supervisor" / "mcp_stdio_bridge.sh"


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _docker_and_image() -> tuple[object, dict[str, object]]:
    docker = pytest.importorskip("docker")
    try:
        client = docker.from_env()
        client.ping()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Docker daemon unavailable: {exc}")
    manifest = _manifest()
    try:
        client.images.get(str(manifest["image_ref"]))
    except Exception:
        pytest.skip("pinned OpenCode image is not local")
    return client, manifest


def _config(
    tmp_path: Path,
    manifest: dict[str, object],
    *,
    command: tuple[str, ...],
    read_only_inputs: tuple[ReadOnlyMount, ...] = (),
) -> ContainerConfig:
    scratch = tmp_path / "scratch"
    staging = tmp_path / "staging"
    scratch.mkdir()
    staging.mkdir()
    environment = tuple(
        (str(key), str(value))
        for key, value in dict(manifest["environment"]).items()
    )
    return ContainerConfig(
        image_ref=str(manifest["image_ref"]),
        command=command,
        read_only_inputs=read_only_inputs,
        scratch_dir="/scratch",
        staging_dir="/staging",
        host_scratch_dir=str(scratch),
        host_staging_dir=str(staging),
        environment=environment,
        timeout_seconds=30,
    )


def test_manifest_locks_selected_version_and_digest() -> None:
    manifest = _manifest()
    assert manifest["adapter_id"] == "opencode@1.18.14"
    assert manifest["image_ref"] == (
        "ghcr.io/anomalyco/opencode:1.18.14@sha256:"
        "16a66f622a0bb0b4bb2a05242749907704a4149ef25805932c067d5afb340f6a"
    )


@pytest.mark.integration
def test_offline_container_startup_and_security_baseline(tmp_path: Path) -> None:
    client, manifest = _docker_and_image()
    runtime = DockerEngineContainerRuntime(client=client)
    container_id = runtime.create(_config(tmp_path, manifest, command=("--version",)))
    try:
        container = client.containers.get(container_id)
        attrs = container.attrs
        host = attrs["HostConfig"]
        assert host["NetworkMode"] == "none"
        assert host["ReadonlyRootfs"] is True
        assert attrs["Config"]["User"] == "65534:65534"
        assert host["Memory"] == 512 * 1024 * 1024
        assert host["PidsLimit"] == 128
        assert host["CapDrop"] == ["ALL"]
        assert "no-new-privileges" in host["SecurityOpt"]
        assert host["Init"] is True
        runtime.start(container_id)
        assert runtime.wait(container_id, timeout_seconds=30) == 0
        assert runtime.logs(container_id).strip() == "1.18.14"
    finally:
        runtime.remove(container_id)


@pytest.mark.integration
def test_offline_json_event_and_mcp_stdio_handshake(tmp_path: Path) -> None:
    client, manifest = _docker_and_image()
    runtime = DockerEngineContainerRuntime(client=client)

    event_id = runtime.create(
        _config(
            tmp_path,
            manifest,
            command=(
                "run",
                "offline admission probe",
                "--format",
                "json",
                "--model",
                "admission/invalid",
                "--pure",
            ),
        )
    )
    try:
        runtime.start(event_id)
        assert runtime.wait(event_id, timeout_seconds=30) == 1
        payloads = [json.loads(line) for line in runtime.logs(event_id).splitlines()]
        assert payloads and payloads[-1]["type"] == "error"
    finally:
        runtime.remove(event_id)

    scratch = tmp_path / "mcp-scratch"
    scratch.mkdir()
    config_dir = scratch / "config" / "opencode"
    config_dir.mkdir(parents=True)
    config_dir.joinpath("opencode.json").write_text(
        json.dumps(
            {
                "$schema": "https://opencode.ai/config.json",
                "mcp": {
                    "admission": {
                        "type": "local",
                        "command": ["/bin/sh", "/inputs/fake_mcp_stdio.sh"],
                        "environment": {
                            "MCP_REQUEST_LOG": "/scratch/mcp-requests.jsonl"
                        },
                        "codemode": False,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    staging = tmp_path / "mcp-staging"
    staging.mkdir()
    environment = dict(manifest["environment"])
    environment["XDG_CONFIG_HOME"] = "/scratch/config"
    mcp_config = ContainerConfig(
        image_ref=str(manifest["image_ref"]),
        command=("mcp", "list", "--pure"),
        read_only_inputs=(
            ReadOnlyMount(host_path=str(MCP_FIXTURE.parent), container_path="/inputs"),
        ),
        scratch_dir="/scratch",
        staging_dir="/staging",
        host_scratch_dir=str(scratch),
        host_staging_dir=str(staging),
        environment=tuple((str(key), str(value)) for key, value in environment.items()),
        timeout_seconds=30,
    )
    mcp_id = runtime.create(mcp_config)
    try:
        runtime.start(mcp_id)
        exit_code = runtime.wait(mcp_id, timeout_seconds=30)
        logs = runtime.logs(mcp_id)
        assert exit_code == 0, logs
        assert "connected" in logs.lower()
        requests = scratch.joinpath("mcp-requests.jsonl").read_text(encoding="utf-8")
        assert '"method":"initialize"' in requests
        assert '"method":"tools/list"' in requests
    finally:
        runtime.remove(mcp_id)


@pytest.mark.integration
def test_product_mcp_bridge_connects_inside_opencode_container(tmp_path: Path) -> None:
    client, manifest = _docker_and_image()
    runtime = DockerEngineContainerRuntime(client=client)
    scratch = tmp_path / "bridge-scratch"
    scratch.mkdir()
    config_dir = scratch / "config" / "opencode"
    config_dir.mkdir(parents=True)
    inputs = tmp_path / "bridge-inputs"
    inputs.mkdir()
    inputs.joinpath("evidence.json").write_text('{"id":"ev-1"}', encoding="utf-8")
    bundle = tmp_path / "mcp-bundle.json"
    bundle.write_text(
        json.dumps(
            {
                "attempt_id": "attempt-container-bridge",
                "generation_token": "generation-1",
                "spec_sha256": "a" * 64,
                "allowed_tools": ["read_input"],
                "input_root": "/inputs",
            }
        ),
        encoding="utf-8",
    )
    config_dir.joinpath("opencode.json").write_text(
        json.dumps(
            {
                "$schema": "https://opencode.ai/config.json",
                "mcp": {
                    "clinical_attempt": {
                        "type": "local",
                        "command": [
                            "/bin/sh",
                            "/harness/mcp_stdio_bridge.sh",
                            "/harness/mcp-bundle.json",
                            "/staging/mcp-audit.jsonl",
                        ],
                        "environment": {},
                        "codemode": False,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    staging = tmp_path / "bridge-staging"
    staging.mkdir()
    environment = dict(manifest["environment"])
    environment["XDG_CONFIG_HOME"] = "/scratch/config"
    config = ContainerConfig(
        image_ref=str(manifest["image_ref"]),
        command=("mcp", "list"),
        read_only_inputs=(
            ReadOnlyMount(host_path=str(inputs), container_path="/inputs"),
            ReadOnlyMount(
                host_path=str(MCP_BRIDGE),
                container_path="/harness/mcp_stdio_bridge.sh",
            ),
            ReadOnlyMount(
                host_path=str(bundle),
                container_path="/harness/mcp-bundle.json",
            ),
        ),
        scratch_dir="/scratch",
        staging_dir="/staging",
        host_scratch_dir=str(scratch),
        host_staging_dir=str(staging),
        environment=tuple(environment.items()),
        timeout_seconds=30,
    )
    container_id = runtime.create(config)
    try:
        runtime.start(container_id)
        exit_code = runtime.wait(container_id, timeout_seconds=30)
        logs = runtime.logs(container_id)
        assert exit_code == 0, logs
        assert "clinical_attempt" in logs
        assert "connected" in logs.lower()
        assert "generation-1" not in logs
    finally:
        runtime.remove(container_id)


@pytest.mark.integration
def test_product_mcp_bridge_executes_read_input_and_rejects_escape(tmp_path: Path) -> None:
    client, manifest = _docker_and_image()
    runtime = DockerEngineContainerRuntime(client=client)
    inputs = tmp_path / "tool-inputs"
    inputs.mkdir()
    inputs.joinpath("evidence.json").write_text('{"id":"ev-1"}', encoding="utf-8")
    bundle = tmp_path / "tool-bundle.json"
    bundle.write_text(
        json.dumps(
            {
                "attempt_id": "attempt-tool-call",
                "generation_token": "generation-secret",
                "spec_sha256": "b" * 64,
                "allowed_tools": ["read_input"],
                "input_root": "/inputs",
            }
        ),
        encoding="utf-8",
    )
    scratch = tmp_path / "tool-scratch"
    staging = tmp_path / "tool-staging"
    scratch.mkdir()
    staging.mkdir()
    script = """printf '%s\\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"read_input","arguments":{"path":"evidence.json"}}}' \
'{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"read_input","arguments":{"path":"../secret"}}}' \
| /bin/sh /harness/mcp_stdio_bridge.sh /harness/mcp-bundle.json /staging/mcp-audit.jsonl"""
    config = ContainerConfig(
        image_ref=str(manifest["image_ref"]),
        entrypoint=("/bin/sh", "-c"),
        command=(script,),
        read_only_inputs=(
            ReadOnlyMount(host_path=str(inputs), container_path="/inputs"),
            ReadOnlyMount(
                host_path=str(MCP_BRIDGE),
                container_path="/harness/mcp_stdio_bridge.sh",
            ),
            ReadOnlyMount(
                host_path=str(bundle),
                container_path="/harness/mcp-bundle.json",
            ),
        ),
        scratch_dir="/scratch",
        staging_dir="/staging",
        host_scratch_dir=str(scratch),
        host_staging_dir=str(staging),
        timeout_seconds=30,
    )
    container_id = runtime.create(config)
    try:
        runtime.start(container_id)
        assert runtime.wait(container_id, timeout_seconds=30) == 0
        responses = [json.loads(line) for line in runtime.logs(container_id).splitlines()]
        assert responses[1]["result"]["content"][0]["text"] == '{"id":"ev-1"}'
        assert responses[2]["error"]["code"] == -32602
        audit = staging.joinpath("mcp-audit.jsonl").read_text(encoding="utf-8")
        assert '"result":"succeeded"' in audit
        assert '"result":"failed"' in audit
        assert "generation-secret" not in audit
    finally:
        runtime.remove(container_id)


@pytest.mark.integration
def test_sigterm_stops_the_container_namespace(tmp_path: Path) -> None:
    client, manifest = _docker_and_image()
    runtime = DockerEngineContainerRuntime(client=client)
    container_id = runtime.create(
        _config(
            tmp_path,
            manifest,
            command=(
                "serve",
                "--hostname",
                "127.0.0.1",
                "--port",
                "4096",
                "--pure",
            ),
        )
    )
    try:
        runtime.start(container_id)
        container = client.containers.get(container_id)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            container.reload()
            if container.status == "running":
                break
            time.sleep(0.1)
        assert container.status == "running"

        runtime.terminate(container_id)

        result = container.wait(timeout=30)
        container.reload()
        assert int(result["StatusCode"]) in {0, 143}
        assert container.status == "exited"
        assert container.attrs["State"]["Pid"] == 0
    finally:
        runtime.remove(container_id)


@pytest.mark.integration
def test_synthetic_provider_credential_is_file_mounted_not_exposed(tmp_path: Path) -> None:
    client, manifest = _docker_and_image()
    runtime = DockerEngineContainerRuntime(client=client)
    synthetic_secret = "synthetic-admission-secret-do-not-use"
    auth_file = tmp_path / "opencode-auth.json"
    auth_file.write_text(
        json.dumps({"openai": {"type": "api", "key": synthetic_secret}}),
        encoding="utf-8",
    )
    environment = dict(manifest["environment"])
    environment["XDG_DATA_HOME"] = "/scratch/data"
    config = _config(
        tmp_path,
        {**manifest, "environment": environment},
        command=("providers", "list", "--pure"),
        read_only_inputs=(
            ReadOnlyMount(
                host_path=str(auth_file),
                container_path="/scratch/data/opencode/auth.json",
            ),
        ),
    )
    auth_target = tmp_path / "scratch" / "data" / "opencode" / "auth.json"
    auth_target.parent.mkdir(parents=True)
    auth_target.touch()
    container_id = runtime.create(config)
    try:
        container = client.containers.get(container_id)
        runtime.start(container_id)
        exit_code = runtime.wait(container_id, timeout_seconds=30)
        logs = runtime.logs(container_id)
        container.reload()
        assert exit_code == 0, logs
        assert "openai" in logs.lower()
        assert synthetic_secret not in logs
        assert synthetic_secret not in "\n".join(container.attrs["Config"]["Env"])
        auth_mount = next(
            mount
            for mount in container.attrs["Mounts"]
            if mount["Destination"] == "/scratch/data/opencode/auth.json"
        )
        assert auth_mount["RW"] is False
        scratch_bytes = b"".join(
            path.read_bytes()
            for path in (tmp_path / "scratch").rglob("*")
            if path.is_file()
        )
        assert synthetic_secret.encode() not in scratch_bytes
    finally:
        runtime.remove(container_id)
