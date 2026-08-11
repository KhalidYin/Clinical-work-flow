from __future__ import annotations

import json
import hashlib
from datetime import datetime, timedelta, timezone
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
GATEWAY_IMAGE = (
    "ubuntu/squid:6.6-24.04_edge@sha256:"
    "8a3baed477e2c282ab8aa5edad442f69873246964f225c5c2ae8364b6610963c"
)
POLICY_ROOT = ROOT / "egress" / "model-deepseek-v1"


def _write_local_deepseek_certificate(root: Path) -> tuple[Path, Path]:
    x509 = pytest.importorskip("cryptography.x509")
    hashes = pytest.importorskip("cryptography.hazmat.primitives.hashes")
    serialization = pytest.importorskip(
        "cryptography.hazmat.primitives.serialization"
    )
    rsa = pytest.importorskip(
        "cryptography.hazmat.primitives.asymmetric.rsa"
    )
    name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "api.deepseek.com")])
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("api.deepseek.com")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path = root / "local-deepseek-cert.pem"
    key_path = root / "local-deepseek-key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


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
            secret_workspace_root=tmp_path / "attempt-secrets",
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
            secret_workspace_root=tmp_path / "denied-attempt-secrets",
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


@pytest.mark.integration
def test_real_opencode_preserves_pack_skill_and_mcp_through_model_gateway(
    tmp_path: Path,
) -> None:
    from supervisor.network_policy import (
        NetworkRuntimeBinding,
        p16_network_policy_registry,
    )

    client, manifest = _docker_and_manifest()
    try:
        client.images.get(GATEWAY_IMAGE)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"pinned gateway image unavailable: {exc}")

    suffix = uuid.uuid4().hex[:12]
    labels = {"clinical.p16.test": suffix}
    client_network = client.networks.create(
        f"p16-opencode-client-{suffix}",
        internal=True,
        labels=labels,
    )
    uplink_network = client.networks.create(
        f"p16-opencode-uplink-{suffix}",
        internal=False,
        labels=labels,
    )
    containers: list[object] = []
    mock = None
    gateway = None
    try:
        cert_path, key_path = _write_local_deepseek_certificate(tmp_path)
        secret_file = tmp_path / "synthetic-model-key"
        secret_file.write_text(SYNTHETIC_SECRET + "\n", encoding="utf-8")
        audit_dir = tmp_path / "gateway-mock-audit"
        audit_dir.mkdir()
        tls_server = """
import os
import ssl
from http.server import ThreadingHTTPServer
from pathlib import Path
from poc.openai_mock.server import ScriptedOpenAIMock, _handler, load_api_key

mock = ScriptedOpenAIMock(
    api_key=load_api_key(os.environ),
    audit_path=Path(os.environ['P15_MOCK_AUDIT_PATH']),
)
server = ThreadingHTTPServer(('0.0.0.0', 443), _handler(mock))
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain('/tls/cert.pem', '/tls/key.pem')
server.socket = context.wrap_socket(server.socket, server_side=True)
server.serve_forever()
"""
        mock = client.containers.create(
            MOCK_IMAGE,
            command=["python", "-c", tls_server],
            network_mode=uplink_network.name,
            labels=labels,
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            environment={
                "P15_MOCK_API_KEY_FILE": "/run/secrets/model-key",
                "P15_MOCK_AUDIT_PATH": "/audit/requests.jsonl",
            },
            volumes={
                str(secret_file): {
                    "bind": "/run/secrets/model-key",
                    "mode": "ro",
                },
                str(cert_path): {"bind": "/tls/cert.pem", "mode": "ro"},
                str(key_path): {"bind": "/tls/key.pem", "mode": "ro"},
                str(audit_dir): {"bind": "/audit", "mode": "rw"},
            },
            tmpfs={"/tmp": "rw,noexec,nosuid,size=16m"},
        )
        containers.append(mock)
        uplink_network.disconnect(mock)
        uplink_network.connect(mock, aliases=["api.deepseek.com"])
        mock.start()
        _wait_running(mock)

        production_config = (POLICY_ROOT / "squid.conf").read_text(
            encoding="utf-8"
        )
        test_config = production_config.replace(
            "http_access deny blocked_destination",
            "# test-only local TLS target: production keeps this deny",
        )
        config_path = tmp_path / "squid.conf"
        config_path.write_text(test_config, encoding="utf-8")
        config_sha256 = hashlib.sha256(config_path.read_bytes()).hexdigest()
        gateway = client.containers.create(
            GATEWAY_IMAGE,
            command=["-f", "/etc/squid/squid.conf", "-NYC"],
            entrypoint=["/usr/sbin/squid"],
            user="13:13",
            network_mode=client_network.name,
            labels=labels,
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            tmpfs={
                "/tmp": "rw,noexec,nosuid,size=16m",
                "/run": "rw,noexec,nosuid,size=4m",
                "/var/log/squid": "rw,noexec,nosuid,size=16m",
                "/var/spool/squid": "rw,noexec,nosuid,size=16m",
            },
            volumes={
                str(config_path): {
                    "bind": "/etc/squid/squid.conf",
                    "mode": "ro",
                }
            },
        )
        containers.append(gateway)
        client_network.disconnect(gateway)
        client_network.connect(gateway, aliases=["harness-egress-deepseek"])
        uplink_network.connect(gateway)
        gateway.start()
        _wait_running(gateway)

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
                provider_id="deepseek",
                model_id="deepseek-v4-flash",
                base_url="https://api.deepseek.com/v1",
            ),
        )
        input_bundle = {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "data_boundary": "external_allowed",
            "messages": [{"role": "user", "content": "Use authorized Evidence."}],
            "evidence": [
                {
                    "evidence_id": "evidence-poc-001",
                    "content": "Synthetic evidence for the P16 gateway integration.",
                }
            ],
        }
        attempt = SupervisorAttemptRequest(
            attempt_id=f"attempt-p16-{suffix}",
            run_id=f"run-p16-{suffix}",
            step_id="enrichment.extract_candidate",
            generation_token=f"generation-p16-{suffix}",
            fencing_token=f"fencing-p16-{suffix}",
            adapter_id="opencode@1.18.14",
            spec_sha256="a" * 64,
            input_sha256=canonical_sha256(input_bundle),
            input_bundle=input_bundle,
            instruction_ref=InstructionRef(
                pack_id="knowledge-candidate-v1",
                version="1.0.0",
                sha256=pack_sha256,
            ),
            secret_refs=("secret://deepseek-api-key",),
            network_policy_id="model-deepseek-v1",
            model_egress={
                "profile_id": "deepseek-v4-flash-extractor",
                "profile_version": "1.0.0",
                "provider": "deepseek",
                "model": "deepseek-v4-flash",
                "endpoint": "https://api.deepseek.com:443",
                "data_boundary": "external_allowed",
            },
            capabilities=frozenset(
                {"knowledge.read-evidence", "harness.browser"}
            ),
            timeout_seconds=30,
            network_mode="none",
        )
        runtime = RecordingDockerRuntime(client)
        binding = NetworkRuntimeBinding(
            policy_id="model-deepseek-v1",
            internal_network_id=client_network.id,
            proxy_url="http://harness-egress-deepseek:3128",
            gateway_identity="test-only-local-squid",
            gateway_config_sha256=config_sha256,
        )
        environment = {
            str(key): str(value)
            for key, value in dict(manifest["environment"]).items()
        }
        # The local fixture uses a one-hour self-signed certificate. Production
        # keeps normal public CA validation and Squid never terminates TLS.
        environment["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
        executor = OpenCodeAttemptExecutor(
            runtime=runtime,
            image_ref=str(manifest["image_ref"]),
            mcp_bridge_path=ROOT / "supervisor" / "mcp_stdio_bridge.sh",
            secret_resolver=lambda _reference: SYNTHETIC_SECRET,
            workspace_root=tmp_path / "gateway-attempts",
            secret_workspace_root=tmp_path / "gateway-attempt-secrets",
            environment=tuple(environment.items()),
            pack_resolver=resolver,
            pack_compiler=compiler,
            network_policy_registry=p16_network_policy_registry(
                available_policy_ids=frozenset({"none", "model-deepseek-v1"})
            ),
            network_runtime_bindings=(binding,),
        )

        outcome = executor.execute(attempt)

        debug = {
            "receipt": outcome.receipt.model_dump(mode="json"),
            "opencode_logs": runtime.logs_before_removal,
            "staged_files": runtime.staged_files,
            "gateway_logs": gateway.logs().decode("utf-8", errors="replace"),
            "mock_logs": mock.logs().decode("utf-8", errors="replace"),
            "mock_audit": (
                audit_dir.joinpath("requests.jsonl").read_text(encoding="utf-8")
                if audit_dir.joinpath("requests.jsonl").exists()
                else ""
            ),
        }
        assert outcome.receipt.exit_classification is ExitClassification.SUCCEEDED, (
            json.dumps(debug, ensure_ascii=False, default=str)
        )
        assert outcome.output_bundle is not None
        assert outcome.output_bundle["candidate_group_id"] == "candidate-poc-001"
        assert runtime.network_names == {client_network.name}
        assert outcome.receipt.network_policy is not None
        assert outcome.receipt.network_policy.policy_id == "model-deepseek-v1"
        assert outcome.receipt.network_policy.gateway_config_sha256 == config_sha256
        audits = [
            json.loads(line)
            for line in audit_dir.joinpath("requests.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        assert {audit["model"] for audit in audits} == {"deepseek-v4-flash"}
        assert "skill" in audits[1]["tool_names"]
        assert "clinical_attempt_read_evidence" in audits[1]["tool_names"]
        staged = "\n".join(runtime.staged_files.values())
        assert "read_evidence" in staged
        assert SYNTHETIC_SECRET not in staged
        gateway_logs = debug["gateway_logs"]
        assert "api.deepseek.com:443" in gateway_logs
        assert SYNTHETIC_SECRET not in gateway_logs
        assert client.containers.list(
            all=True,
            filters={"label": f"clinical.harness.attempt_id={attempt.attempt_id}"},
        ) == []
    finally:
        for container in reversed(containers):
            try:
                container.remove(force=True)  # type: ignore[attr-defined]
            except Exception:
                pass
        for network in (client_network, uplink_network):
            try:
                network.remove()
            except Exception:
                pass
