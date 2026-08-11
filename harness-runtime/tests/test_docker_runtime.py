"""H0-C Docker runtime tests.

Unit part (no Docker): image digest lock validation.
Integration part: full create/start/wait/copy/remove round-trip — skipped
unless docker-py AND a reachable Docker daemon are present.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from supervisor.container_runtime import ContainerConfig, ReadOnlyMount


class _FakeContainer:
    id = "container-1"

    def __init__(self) -> None:
        self.attrs: dict[str, object] = {"Config": {"Labels": {}}}
        self.stop_calls: list[int] = []
        self.kill_calls = 0
        self.remove_calls = 0

    def stop(self, *, timeout: int) -> None:
        self.stop_calls.append(timeout)

    def kill(self) -> None:
        self.kill_calls += 1

    def remove(self, *, force: bool) -> None:
        assert force is True
        self.remove_calls += 1


class _FakeContainers:
    def __init__(self, container: _FakeContainer) -> None:
        self.container = container
        self.create_kwargs: dict[str, object] = {}

    def create(self, **kwargs: object) -> _FakeContainer:
        self.create_kwargs = kwargs
        self.container.attrs = {"Config": {"Labels": kwargs.get("labels", {})}}
        return self.container

    def get(self, container_id: str) -> _FakeContainer:
        assert container_id == self.container.id
        return self.container

    def list(self, *, all: bool, filters: dict[str, str]) -> list[_FakeContainer]:
        assert all is True
        assert filters == {"label": "clinical.harness.attempt=managed"}
        return [self.container]


class _FakeNetworks:
    def __init__(self, *, internal: bool) -> None:
        self.internal = internal

    def get(self, name: str):
        assert name == "p15-model-internal"
        return SimpleNamespace(
            id="d" * 64,
            attrs={"Internal": self.internal},
        )


def test_config_requires_digest_locked_image() -> None:
    with pytest.raises(ValidationError):
        ContainerConfig(
            image_ref="clinical-harness:latest",  # no @sha256: digest
            command=(),
            scratch_dir="/scratch",
            staging_dir="/staging",
        )
    ContainerConfig(
        image_ref=f"clinical-harness:fake@sha256:{'f' * 64}",
        command=(),
        scratch_dir="/scratch",
        staging_dir="/staging",
    )


def test_config_rejects_credential_like_environment() -> None:
    with pytest.raises(ValidationError):
        ContainerConfig(
            image_ref=f"clinical-harness:fake@sha256:{'f' * 64}",
            command=(),
            scratch_dir="/scratch",
            staging_dir="/staging",
            environment=(("API_SECRET", "value"),),
        )


def test_create_uses_supported_engine_arguments_and_hardening(tmp_path: Path) -> None:
    from supervisor.docker_runtime import DockerEngineContainerRuntime

    container = _FakeContainer()
    containers = _FakeContainers(container)
    runtime = DockerEngineContainerRuntime(client=SimpleNamespace(containers=containers))
    container_id = runtime.create(
        ContainerConfig(
            image_ref=f"clinical-harness:fake@sha256:{'f' * 64}",
            entrypoint=("/bin/sh", "-c"),
            command=("--version",),
            scratch_dir="/scratch",
            staging_dir="/staging",
            host_scratch_dir=str(tmp_path / "scratch"),
            host_staging_dir=str(tmp_path / "staging"),
            labels=(("clinical.harness.attempt_id", "attempt-1"),),
        )
    )

    assert container_id == container.id
    assert containers.create_kwargs["entrypoint"] == ["/bin/sh", "-c"]
    assert "stop_timeout" not in containers.create_kwargs
    assert containers.create_kwargs["cap_drop"] == ["ALL"]
    assert containers.create_kwargs["security_opt"] == ["no-new-privileges"]
    assert containers.create_kwargs["init"] is True
    assert containers.create_kwargs["tmpfs"] == {
        "/tmp": "rw,noexec,nosuid,size=64m"
    }
    assert containers.create_kwargs["labels"] == {
        "clinical.harness.attempt": "managed",
        "clinical.harness.attempt_id": "attempt-1",
    }


def test_copy_from_is_noop_when_staging_is_already_host_bound(tmp_path: Path) -> None:
    from supervisor.docker_runtime import DockerEngineContainerRuntime

    container = _FakeContainer()
    containers = _FakeContainers(container)
    runtime = DockerEngineContainerRuntime(client=SimpleNamespace(containers=containers))
    container_id = runtime.create(
        ContainerConfig(
            image_ref=f"clinical-harness:fake@sha256:{'f' * 64}",
            scratch_dir="/scratch",
            staging_dir="/staging",
            host_staging_dir=str(tmp_path / "staging"),
        )
    )

    runtime.copy_from(container_id, "/staging", str(tmp_path / "staging"))


def test_runtime_resolves_only_docker_internal_network_and_uses_opaque_id(
    tmp_path: Path,
) -> None:
    from supervisor.docker_runtime import DockerEngineContainerRuntime

    container = _FakeContainer()
    containers = _FakeContainers(container)
    runtime = DockerEngineContainerRuntime(
        client=SimpleNamespace(
            containers=containers,
            networks=_FakeNetworks(internal=True),
        )
    )

    network_id = runtime.require_internal_network("p15-model-internal")
    runtime.create(
        ContainerConfig(
            image_ref=f"clinical-harness:fake@sha256:{'f' * 64}",
            command=("--version",),
            scratch_dir="/scratch",
            staging_dir="/staging",
            host_scratch_dir=str(tmp_path / "scratch"),
            host_staging_dir=str(tmp_path / "staging"),
            internal_network_id=network_id,
        )
    )

    assert network_id == "d" * 64
    assert containers.create_kwargs["network_mode"] == "d" * 64

    external_runtime = DockerEngineContainerRuntime(
        client=SimpleNamespace(
            containers=containers,
            networks=_FakeNetworks(internal=False),
        )
    )
    with pytest.raises(RuntimeError, match="not Docker-internal"):
        external_runtime.require_internal_network("p15-model-internal")


def test_terminate_sends_sigterm_with_attempt_timeout(tmp_path: Path) -> None:
    from supervisor.docker_runtime import DockerEngineContainerRuntime

    container = _FakeContainer()
    containers = _FakeContainers(container)
    runtime = DockerEngineContainerRuntime(client=SimpleNamespace(containers=containers))
    runtime.create(
        ContainerConfig(
            image_ref=f"clinical-harness:fake@sha256:{'f' * 64}",
            command=("--version",),
            scratch_dir="/scratch",
            staging_dir="/staging",
            host_scratch_dir=str(tmp_path / "scratch"),
            host_staging_dir=str(tmp_path / "staging"),
            stop_timeout_seconds=7,
        )
    )

    runtime.terminate(container.id)

    assert container.stop_calls == [7]
    assert container.kill_calls == 0


def test_list_managed_returns_only_supervisor_identity_labels(tmp_path: Path) -> None:
    from supervisor.docker_runtime import DockerEngineContainerRuntime

    container = _FakeContainer()
    containers = _FakeContainers(container)
    runtime = DockerEngineContainerRuntime(client=SimpleNamespace(containers=containers))
    runtime.create(
        ContainerConfig(
            image_ref=f"clinical-harness:fake@sha256:{'f' * 64}",
            command=("--version",),
            scratch_dir="/scratch",
            staging_dir="/staging",
            host_scratch_dir=str(tmp_path / "scratch"),
            host_staging_dir=str(tmp_path / "staging"),
            labels=(
                ("clinical.harness.attempt_id", "attempt-1"),
                ("clinical.harness.request_sha256", "c" * 64),
                ("clinical.harness.spec_sha256", "a" * 64),
            ),
        )
    )

    managed = runtime.list_managed()

    assert len(managed) == 1
    assert managed[0].container_id == container.id
    assert managed[0].attempt_id == "attempt-1"
    assert managed[0].request_sha256 == "c" * 64
    assert managed[0].spec_sha256 == "a" * 64


def test_runtime_discovers_daemon_source_for_its_exact_state_mount() -> None:
    from supervisor.docker_runtime import DockerEngineContainerRuntime

    container = _FakeContainer()
    container.attrs = {
        "Mounts": [
            {
                "Type": "volume",
                "Source": "/var/lib/docker/volumes/demo_state/_data",
                "Destination": "/var/lib/harness-supervisor",
            },
            {
                "Type": "bind",
                "Source": "/var/run/docker.sock",
                "Destination": "/var/run/docker.sock",
            },
        ]
    }
    runtime = DockerEngineContainerRuntime(
        client=SimpleNamespace(containers=_FakeContainers(container))
    )

    source = runtime.current_container_mount_source(
        "/var/lib/harness-supervisor",
        container_id="container-1",
    )

    assert source == "/var/lib/docker/volumes/demo_state/_data"


def test_runtime_fails_closed_when_state_mount_is_not_exactly_identified() -> None:
    from supervisor.docker_runtime import DockerEngineContainerRuntime

    container = _FakeContainer()
    container.attrs = {"Mounts": []}
    runtime = DockerEngineContainerRuntime(
        client=SimpleNamespace(containers=_FakeContainers(container))
    )

    with pytest.raises(RuntimeError, match="state mount is not available"):
        runtime.current_container_mount_source(
            "/var/lib/harness-supervisor",
            container_id="container-1",
        )


@pytest.mark.integration
def test_docker_round_trip(tmp_path: Path) -> None:
    docker = pytest.importorskip("docker")
    try:
        docker.from_env().ping()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Docker daemon unavailable: {exc}")

    from supervisor.docker_runtime import DockerEngineContainerRuntime

    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    staging = tmp_path / "staging"
    staging.mkdir()

    manifest = json.loads(
        (Path(__file__).resolve().parents[1] / "images" / "opencode-1.18.14.json").read_text(
            encoding="utf-8"
        )
    )
    try:
        docker.from_env().images.get(manifest["image_ref"])
    except Exception:  # pragma: no cover - environment dependent
        pytest.skip("pinned OpenCode image is not local")

    runtime = DockerEngineContainerRuntime()
    container_id = runtime.create(
        ContainerConfig(
            image_ref=manifest["image_ref"],
            command=("--version",),
            read_only_inputs=(ReadOnlyMount(host_path=str(input_dir), container_path="/inputs"),),
            scratch_dir="/scratch",
            staging_dir="/staging",
            host_scratch_dir=str(tmp_path / "scratch"),
            host_staging_dir=str(staging),
            environment=tuple(
                (str(key), str(value))
                for key, value in manifest["environment"].items()
            ),
            timeout_seconds=30,
        )
    )
    try:
        runtime.start(container_id)
        exit_code = runtime.wait(container_id, timeout_seconds=30)
        assert exit_code == 0
    finally:
        runtime.remove(container_id)
