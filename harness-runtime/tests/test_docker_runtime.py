"""H0-C Docker runtime tests.

Unit part (no Docker): image digest lock validation.
Integration part: full create/start/wait/copy/remove round-trip — skipped
unless docker-py AND a reachable Docker daemon are present.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from supervisor.container_runtime import ContainerConfig, ReadOnlyMount


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

    runtime = DockerEngineContainerRuntime()
    container_id = runtime.create(
        ContainerConfig(
            image_ref="alpine:3.20@sha256:beefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef0000",
            command=("true",),
            read_only_inputs=(ReadOnlyMount(host_path=str(input_dir), container_path="/inputs"),),
            scratch_dir="/scratch",
            staging_dir="/staging",
            host_scratch_dir=str(tmp_path / "scratch"),
            host_staging_dir=str(staging),
            timeout_seconds=30,
        )
    )
    try:
        runtime.start(container_id)
        exit_code = runtime.wait(container_id, timeout_seconds=30)
        assert exit_code == 0
    finally:
        runtime.remove(container_id)
