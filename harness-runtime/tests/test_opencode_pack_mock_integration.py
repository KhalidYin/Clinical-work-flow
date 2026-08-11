from __future__ import annotations

import json
from pathlib import Path
import time
import uuid

import pytest
from jsonschema import Draft202012Validator

from contracts.receipt import ExitClassification
from contracts.spec import InstructionRef
from supervisor.docker_runtime import DockerEngineContainerRuntime
from supervisor.opencode_executor import OpenCodeAttemptExecutor
from supervisor.pack_compiler import (
    HarnessPackCompiler,
    HarnessPackResolver,
    McpCapabilityBinding,
    OpenAICompatibleModelBinding,
)
from supervisor.service_contracts import SupervisorAttemptRequest, canonical_sha256


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
PACK_ROOT = PROJECT_ROOT / "clinical-llm-wiki" / "harness-packs" / (
    "knowledge-candidate-v1"
)
MANIFEST_PATH = ROOT / "images" / "opencode-1.18.14.json"
MOCK_IMAGE = "clinical-harness-supervisor:local"
SYNTHETIC_SECRET = "synthetic-p15-file-secret"


class RecordingDockerRuntime(DockerEngineContainerRuntime):
    def __init__(self, client: object) -> None:
        super().__init__(client=client)
        self.created_config = None
        self.container_environment: list[str] = []
        self.network_names: set[str] = set()
        self.logs_before_removal = ""
        self.staged_files: dict[str, str] = {}
        self.create_count = 0

    def create(self, config):  # type: ignore[no-untyped-def]
        self.create_count += 1
        container_id = super().create(config)
        self.created_config = config
        container = self._docker().containers.get(container_id)
        self.container_environment = list(container.attrs["Config"].get("Env") or [])
        self.network_names = set(
            container.attrs["NetworkSettings"].get("Networks", {}).keys()
        )
        return container_id

    def copy_from(self, container_id: str, container_path: str, host_path: str) -> None:
        super().copy_from(container_id, container_path, host_path)
        staging = Path(host_path)
        self.staged_files = {
            path.relative_to(staging).as_posix(): path.read_text(encoding="utf-8")
            for path in staging.rglob("*")
            if path.is_file()
        }

    def remove(self, container_id: str) -> None:
        self.logs_before_removal = self.logs(container_id, tail=5000)
        if self.created_config is not None and self.created_config.host_staging_dir:
            staging = Path(self.created_config.host_staging_dir)
            self.staged_files = {
                path.relative_to(staging).as_posix(): path.read_text(encoding="utf-8")
                for path in staging.rglob("*")
                if path.is_file()
            }
        super().remove(container_id)


def _docker_and_manifest():
    docker = pytest.importorskip("docker")
    try:
        client = docker.from_env()
        client.ping()
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Docker daemon unavailable: {exc}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    client.images.get(str(manifest["image_ref"]))
    client.images.get(MOCK_IMAGE)
    return client, manifest


def _wait_running(container: object) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        container.reload()  # type: ignore[attr-defined]
        if container.status == "running":  # type: ignore[attr-defined]
            return
        if container.status == "exited":  # type: ignore[attr-defined]
            break
        time.sleep(0.1)
    logs = container.logs().decode("utf-8", errors="replace")  # type: ignore[attr-defined]
    pytest.fail(f"P15 mock did not remain running: {logs}")


def _assert_internal_network_boundary(client: object, network: object, mock_name: str) -> None:
    target = client.containers.run(  # type: ignore[attr-defined]
        MOCK_IMAGE,
        command=["python", "-m", "http.server", "8081", "--bind", "0.0.0.0"],
        detach=True,
        ports={"8081/tcp": None},
    )
    probe = None
    try:
        _wait_running(target)
        target.reload()
        host_port = int(target.attrs["NetworkSettings"]["Ports"]["8081/tcp"][0]["HostPort"])
        script = (
            "import socket,urllib.request;"
            f"urllib.request.urlopen('http://{mock_name}:8080/health',timeout=3).read();"
            "results=[];"
            "\nfor host,port in [('1.1.1.1',443),('host.docker.internal',"
            f"{host_port})]:\n"
            " try:\n  socket.create_connection((host,port),2).close();results.append(False)\n"
            " except OSError:\n  results.append(True)\n"
            "\nraise SystemExit(0 if all(results) else 9)"
        )
        probe = client.containers.run(  # type: ignore[attr-defined]
            MOCK_IMAGE,
            command=["python", "-c", script],
            network=network.name,
            extra_hosts={"host.docker.internal": "host-gateway"},
            detach=True,
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            tmpfs={"/tmp": "rw,noexec,nosuid,size=16m"},
        )
        result = probe.wait(timeout=10)
        logs = probe.logs().decode("utf-8", errors="replace")
        assert result["StatusCode"] == 0, logs
    finally:
        if probe is not None:
            probe.remove(force=True)
        target.remove(force=True)


@pytest.mark.integration
def test_linux_supervisor_image_rejects_pack_symlink() -> None:
    client, _manifest = _docker_and_manifest()
    script = """
from pathlib import Path
import shutil

from supervisor.pack_compiler import HarnessPackResolver, PackResolutionError

source = Path('/source-pack')
target = Path('/tmp/symlink-pack')
shutil.copytree(source, target)
instruction = target / 'instructions' / 'system.md'
real_instruction = target / 'instructions' / 'real-system.md'
instruction.rename(real_instruction)
instruction.symlink_to(real_instruction.name)
try:
    HarnessPackResolver({'knowledge-candidate-v1': target}).measure(
        'knowledge-candidate-v1'
    )
except PackResolutionError as exc:
    raise SystemExit(0 if 'symlink' in str(exc) else 8)
raise SystemExit(9)
"""
    result = client.containers.run(
        MOCK_IMAGE,
        command=["python", "-c", script],
        remove=True,
        read_only=True,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        network_mode="none",
        volumes={str(PACK_ROOT): {"bind": "/source-pack", "mode": "ro"}},
        tmpfs={"/tmp": "rw,noexec,nosuid,size=16m"},
    )
    assert result == b""


@pytest.mark.integration
def test_real_opencode_calls_pack_skill_and_attempt_mcp_over_internal_mock(
    tmp_path: Path,
) -> None:
    client, manifest = _docker_and_manifest()
    suffix = uuid.uuid4().hex[:12]
    network = client.networks.create(f"p15-model-{suffix}", internal=True)
    mock_name = f"p15-openai-mock-{suffix}"
    secret_file = tmp_path / "mock-key"
    secret_file.write_text(SYNTHETIC_SECRET + "\n", encoding="utf-8")
    audit_dir = tmp_path / "mock-audit"
    audit_dir.mkdir()
    mock = None
    try:
        mock = client.containers.run(
            MOCK_IMAGE,
            command=["python", "-m", "poc.openai_mock.server"],
            name=mock_name,
            network=network.name,
            detach=True,
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            environment={
                "P15_MOCK_API_KEY_FILE": "/run/secrets/p15-key",
                "P15_MOCK_AUDIT_PATH": "/audit/requests.jsonl",
            },
            volumes={
                str(secret_file): {"bind": "/run/secrets/p15-key", "mode": "ro"},
                str(audit_dir): {"bind": "/audit", "mode": "rw"},
            },
            tmpfs={"/tmp": "rw,noexec,nosuid,size=16m"},
        )
        _wait_running(mock)
        mock.reload()
        assert SYNTHETIC_SECRET not in json.dumps(mock.attrs["Config"].get("Env"))
        assert set(mock.attrs["NetworkSettings"]["Networks"]) == {network.name}
        _assert_internal_network_boundary(client, network, mock_name)

        resolver = HarnessPackResolver({"knowledge-candidate-v1": PACK_ROOT})
        pack_sha256 = resolver.measure("knowledge-candidate-v1")
        compiler = HarnessPackCompiler(
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
            model_binding=OpenAICompatibleModelBinding(
                provider_id="openai",
                model_id="gpt-4o-mini",
                base_url=f"http://{mock_name}:8080/v1",
            ),
        )
        input_bundle = {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Use authorized Evidence."}],
            "evidence": [
                {
                    "evidence_id": "evidence-poc-001",
                    "content": "Synthetic evidence for the P15 integration POC.",
                }
            ],
        }
        attempt = SupervisorAttemptRequest(
            attempt_id=f"attempt-{suffix}",
            run_id=f"run-{suffix}",
            step_id="enrichment.extract_candidate",
            generation_token=f"generation-{suffix}",
            fencing_token=f"fencing-{suffix}",
            adapter_id="opencode@1.18.14",
            spec_sha256="a" * 64,
            input_sha256=canonical_sha256(input_bundle),
            input_bundle=input_bundle,
            instruction_ref=InstructionRef(
                pack_id="knowledge-candidate-v1",
                version="1.0.0",
                sha256=pack_sha256,
            ),
            secret_refs=("secret://p15-openai-mock",),
            timeout_seconds=15,
            network_mode="none",
        )
        runtime = RecordingDockerRuntime(client)
        executor = OpenCodeAttemptExecutor(
            runtime=runtime,
            image_ref=str(manifest["image_ref"]),
            mcp_bridge_path=ROOT / "supervisor" / "mcp_stdio_bridge.sh",
            secret_resolver=lambda _reference: SYNTHETIC_SECRET,
            workspace_root=tmp_path / "attempts",
            environment=tuple(
                (str(key), str(value))
                for key, value in dict(manifest["environment"]).items()
            ),
            pack_resolver=resolver,
            pack_compiler=compiler,
            trusted_internal_network_id=network.id,
        )

        try:
            outcome = executor.execute(attempt)
        except ValueError as exc:
            pytest.fail(
                json.dumps(
                    {
                        "error": str(exc),
                        "opencode_logs": runtime.logs_before_removal,
                        "staged_files": runtime.staged_files,
                        "mock_audit": (
                            audit_dir.joinpath("requests.jsonl").read_text(
                                encoding="utf-8"
                            )
                            if audit_dir.joinpath("requests.jsonl").exists()
                            else ""
                        ),
                    },
                    ensure_ascii=False,
                )
            )

        debug = {
            "receipt": outcome.receipt.model_dump(mode="json"),
            "opencode_logs": runtime.logs_before_removal,
            "staged_files": runtime.staged_files,
            "mock_logs": mock.logs().decode("utf-8", errors="replace"),
            "mock_audit": (
                audit_dir.joinpath("requests.jsonl").read_text(encoding="utf-8")
                if audit_dir.joinpath("requests.jsonl").exists()
                else ""
            ),
        }
        assert (
            outcome.receipt.exit_classification is ExitClassification.SUCCEEDED
        ), json.dumps(debug, ensure_ascii=False, default=str)
        assert outcome.output_bundle is not None
        assert outcome.output_bundle["candidate_group_id"] == "candidate-poc-001"
        assert outcome.output_bundle["evidence_ids"] == ["evidence-poc-001"]
        schema = json.loads(
            PACK_ROOT.joinpath("schemas", "candidate.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(schema).validate(outcome.output_bundle)
        assert outcome.receipt.pack_identity is not None
        assert outcome.receipt.pack_identity.sha256 == pack_sha256
        assert outcome.receipt.validator_input["network_mode"] == "internal-only"
        assert runtime.network_names == {network.name}
        assert SYNTHETIC_SECRET not in json.dumps(runtime.container_environment)
        staged = "\n".join(runtime.staged_files.values())
        assert "read_evidence" in staged
        assert "evidence-poc-001" in staged
        assert SYNTHETIC_SECRET not in staged
        audits = [
            json.loads(line)
            for line in audit_dir.joinpath("requests.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        assert {audit["model"] for audit in audits} == {"gpt-4o-mini"}
        assert [audit["function_call_output_count"] for audit in audits] == [
            0,
            0,
            1,
            2,
        ]
        assert audits[1]["tool_names"] == sorted(audits[1]["tool_names"])
        assert "skill" in audits[1]["tool_names"]
        assert "clinical_attempt_read_evidence" in audits[1]["tool_names"]
        assert all(SYNTHETIC_SECRET not in json.dumps(audit) for audit in audits)
        assert client.containers.list(
            all=True,
            filters={"label": f"clinical.harness.attempt_id={attempt.attempt_id}"},
        ) == []

        mock.remove(force=True)
        mock = None
        denied_audit_dir = tmp_path / "denied-audit"
        denied_audit_dir.mkdir()
        mock = client.containers.run(
            MOCK_IMAGE,
            command=["python", "-m", "poc.openai_mock.server"],
            name=mock_name,
            network=network.name,
            detach=True,
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            environment={
                "P15_MOCK_API_KEY_FILE": "/run/secrets/p15-key",
                "P15_MOCK_AUDIT_PATH": "/audit/requests.jsonl",
                "P15_MOCK_SCENARIO": "unauthorized_tool",
            },
            volumes={
                str(secret_file): {"bind": "/run/secrets/p15-key", "mode": "ro"},
                str(denied_audit_dir): {"bind": "/audit", "mode": "rw"},
            },
            tmpfs={"/tmp": "rw,noexec,nosuid,size=16m"},
        )
        _wait_running(mock)
        denied_attempt = attempt.model_copy(
            update={
                "attempt_id": f"attempt-denied-{suffix}",
                "generation_token": f"generation-denied-{suffix}",
                "fencing_token": f"fencing-denied-{suffix}",
            }
        )
        denied_runtime = RecordingDockerRuntime(client)
        denied_executor = OpenCodeAttemptExecutor(
            runtime=denied_runtime,
            image_ref=str(manifest["image_ref"]),
            mcp_bridge_path=ROOT / "supervisor" / "mcp_stdio_bridge.sh",
            secret_resolver=lambda _reference: SYNTHETIC_SECRET,
            workspace_root=tmp_path / "denied-attempts",
            environment=tuple(
                (str(key), str(value))
                for key, value in dict(manifest["environment"]).items()
            ),
            pack_resolver=resolver,
            pack_compiler=compiler,
            trusted_internal_network_id=network.id,
        )

        denied_outcome = denied_executor.execute(denied_attempt)

        assert (
            denied_outcome.receipt.exit_classification
            is ExitClassification.FAILED
        )
        assert denied_outcome.receipt.retryable is False
        assert denied_outcome.output_bundle is None
        assert denied_runtime.create_count == 1
        denied_staged = "\n".join(denied_runtime.staged_files.values())
        assert "unauthorized-marker" not in {
            path for path in denied_runtime.staged_files
        }
        assert "tool_use" in denied_staged
        assert '"tool":"bash"' in denied_staged
        assert '"status":"error"' in denied_staged
    finally:
        if mock is not None:
            mock.remove(force=True)
        network.remove()
