from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import stat

import pytest

from supervisor.container_runtime import DaemonRootPathMapper, ManagedContainer
from contracts.receipt import ExitClassification
from contracts.result import HarnessStatus
from supervisor.fake_container_runtime import FakeContainerRuntime
from supervisor.service_contracts import SupervisorAttemptRequest, canonical_sha256


IMAGE_REF = "ghcr.io/anomalyco/opencode:1.18.14@sha256:" + "b" * 64
SPEC_SHA256 = "a" * 64
SYNTHETIC_SECRET = "synthetic-offline-secret-marker"
ADMITTED_IMAGE_REF = (
    "ghcr.io/anomalyco/opencode:1.18.14@sha256:"
    "16a66f622a0bb0b4bb2a05242749907704a4149ef25805932c067d5afb340f6a"
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = (
    PROJECT_ROOT
    / "clinical-llm-wiki"
    / "harness-packs"
    / "knowledge-candidate-v1"
)


class ManagedFakeRuntime(FakeContainerRuntime):
    def __init__(self) -> None:
        super().__init__(exit_code=None, hangs=True)
        self.managed = (
            ManagedContainer(
                container_id="managed-container-1",
                attempt_id="attempt-001",
                request_sha256=_attempt().request_sha256(),
                spec_sha256=SPEC_SHA256,
            ),
        )
        self.terminated_ids: list[str] = []
        self.removed_ids: list[str] = []

    def list_managed(self) -> tuple[ManagedContainer, ...]:
        return self.managed

    def terminate(self, container_id: str) -> None:
        self.terminated_ids.append(container_id)

    def remove(self, container_id: str) -> None:
        self.removed_ids.append(container_id)


class PermissionRecordingFakeRuntime(FakeContainerRuntime):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.writable_modes: dict[str, int] = {}

    def create(self, config):  # type: ignore[no-untyped-def]
        scratch = Path(config.host_scratch_dir)
        staging = Path(config.host_staging_dir)
        for name, path in {
            "home": scratch / "home",
            "cache": scratch / "cache",
            "state": scratch / "state",
            "data": scratch / "data" / "opencode",
            "staging": staging,
        }.items():
            self.writable_modes[name] = stat.S_IMODE(path.stat().st_mode)
        return super().create(config)


def _attempt() -> SupervisorAttemptRequest:
    input_bundle = {
        "system_instruction": "Return one JSON object.",
        "output_schema": {"type": "object"},
        "messages": [{"role": "user", "content": "offline synthetic evidence"}],
        "data_boundary": "provider_approved",
        "provider": "synthetic",
        "model": "invalid-offline-model",
    }
    return SupervisorAttemptRequest(
        attempt_id="attempt-001",
        run_id="run-001",
        step_id="enrichment",
        generation_token="generation-001",
        fencing_token="fencing-001",
        adapter_id="opencode@1.18.14",
        spec_sha256=SPEC_SHA256,
        input_sha256=canonical_sha256(input_bundle),
        input_bundle=input_bundle,
        secret_refs=("env://SYNTHETIC_PROVIDER_KEY",),
        timeout_seconds=60,
        network_mode="none",
    )


def test_executor_compiles_fixed_offline_opencode_attempt_and_cleans_workspace(
    tmp_path: Path,
) -> None:
    from supervisor.opencode_executor import OpenCodeAttemptExecutor

    output = {"claims": [], "advisory_signals": []}
    event = json.dumps({"type": "text", "data": {"text": json.dumps(output)}})
    runtime = FakeContainerRuntime(
        exit_code=0,
        staged_outputs={Path("events.jsonl"): event.encode("utf-8")},
    )
    observed_workspaces: list[Path] = []
    executor = OpenCodeAttemptExecutor(
        runtime=runtime,
        image_ref=IMAGE_REF,
        mcp_bridge_path=(
            Path(__file__).resolve().parents[1] / "supervisor" / "mcp_stdio_bridge.sh"
        ),
        secret_resolver=lambda reference: (
            SYNTHETIC_SECRET
            if reference == "env://SYNTHETIC_PROVIDER_KEY"
            else (_ for _ in ()).throw(KeyError(reference))
        ),
        workspace_root=tmp_path,
        host_path_mapper=DaemonRootPathMapper(
            local_root=tmp_path,
            daemon_root="/var/lib/docker/volumes/demo-supervisor/_data",
        ),
        workspace_observer=observed_workspaces.append,
    )

    outcome = executor.execute(_attempt())

    assert outcome.receipt.exit_classification == ExitClassification.SUCCEEDED
    assert outcome.receipt.request_sha256 == _attempt().request_sha256()
    assert outcome.output_bundle == output
    assert runtime.last_config is not None
    assert runtime.last_config.image_ref == IMAGE_REF
    assert runtime.last_config.network_mode == "none"
    assert runtime.last_config.user == "65534:65534"
    assert runtime.last_config.entrypoint == ("/bin/sh", "-c")
    assert len(runtime.last_config.read_only_inputs) == 4
    assert all(
        mount.host_path.startswith("/var/lib/docker/volumes/demo-supervisor/_data")
        for mount in runtime.last_config.read_only_inputs
    )
    assert runtime.last_config.host_scratch_dir.startswith(
        "/var/lib/docker/volumes/demo-supervisor/_data"
    )
    serialized_config = runtime.last_config.model_dump_json()
    assert SYNTHETIC_SECRET not in serialized_config
    assert "generation-001" not in serialized_config
    assert "fencing-001" not in serialized_config
    assert len(observed_workspaces) == 1
    assert not observed_workspaces[0].exists()


def test_executor_cancel_terminates_only_exact_managed_attempt(tmp_path: Path) -> None:
    from supervisor.opencode_executor import OpenCodeAttemptExecutor

    now = datetime.now(timezone.utc)
    runtime = ManagedFakeRuntime()
    executor = OpenCodeAttemptExecutor(
        runtime=runtime,
        image_ref=IMAGE_REF,
        mcp_bridge_path=(
            Path(__file__).resolve().parents[1] / "supervisor" / "mcp_stdio_bridge.sh"
        ),
        secret_resolver=lambda _reference: SYNTHETIC_SECRET,
        workspace_root=tmp_path,
        clock=lambda: now,
    )

    receipt = executor.cancel("attempt-001", _attempt().request_sha256())

    assert receipt.exit_classification == ExitClassification.CANCELLED
    assert receipt.request_sha256 == _attempt().request_sha256()
    assert runtime.terminated_ids == ["managed-container-1"]
    assert runtime.removed_ids == ["managed-container-1"]


def test_executor_orphan_recovery_terminates_exact_labeled_container(tmp_path: Path) -> None:
    from supervisor.opencode_executor import OpenCodeAttemptExecutor

    now = datetime.now(timezone.utc)
    runtime = ManagedFakeRuntime()
    executor = OpenCodeAttemptExecutor(
        runtime=runtime,
        image_ref=IMAGE_REF,
        mcp_bridge_path=(
            Path(__file__).resolve().parents[1] / "supervisor" / "mcp_stdio_bridge.sh"
        ),
        secret_resolver=lambda _reference: SYNTHETIC_SECRET,
        workspace_root=tmp_path,
        clock=lambda: now,
    )

    receipt = executor.recover_orphan("attempt-001", _attempt().request_sha256())

    assert receipt.status is HarnessStatus.FAILED
    assert receipt.exit_classification == ExitClassification.ORPHANED
    assert runtime.terminated_ids == ["managed-container-1"]
    assert runtime.removed_ids == ["managed-container-1"]


def test_executor_compiles_pack_workspace_internal_mock_and_receipt_identity(
    tmp_path: Path,
) -> None:
    from contracts.spec import InstructionRef
    from supervisor.opencode_executor import OpenCodeAttemptExecutor
    from supervisor.pack_compiler import (
        HarnessPackCompiler,
        HarnessPackResolver,
        McpCapabilityBinding,
        OpenAICompatibleModelBinding,
    )

    resolver = HarnessPackResolver({"knowledge-candidate-v1": PACK_ROOT})
    pack_sha256 = resolver.measure("knowledge-candidate-v1")
    instruction_ref = InstructionRef(
        pack_id="knowledge-candidate-v1",
        version="1.0.0",
        sha256=pack_sha256,
    )
    input_bundle = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Use the authorized Evidence."}],
        "evidence": [
            {
                "evidence_id": "evidence-poc-001",
                "content": "Synthetic evidence for a deterministic POC.",
            }
        ],
    }
    attempt = SupervisorAttemptRequest(
        attempt_id="attempt-pack-001",
        run_id="run-pack-001",
        step_id="enrichment.extract_candidate",
        generation_token="generation-pack-001",
        fencing_token="fencing-pack-001",
        adapter_id="opencode@1.18.14",
        spec_sha256=SPEC_SHA256,
        input_sha256=canonical_sha256(input_bundle),
        input_bundle=input_bundle,
        instruction_ref=instruction_ref,
        secret_refs=("env://SYNTHETIC_PROVIDER_KEY",),
        timeout_seconds=60,
        network_mode="none",
    )
    output = {"candidate_group_id": "candidate-poc-001"}
    event = json.dumps({"type": "text", "data": {"text": json.dumps(output)}})
    runtime = PermissionRecordingFakeRuntime(
        exit_code=0,
        staged_outputs={
            Path("events.jsonl"): event.encode("utf-8"),
            Path("mcp-audit.jsonl"): json.dumps(
                {"tool": "read_evidence", "result": "succeeded"}
            ).encode("utf-8"),
        },
    )
    snapshots: list[dict[str, object]] = []

    def observe(workdir: Path) -> None:
        snapshots.append(
            {
                "skill": (
                    workdir
                    / "workspace"
                    / ".opencode"
                    / "skills"
                    / "evidence-candidate"
                    / "SKILL.md"
                ).is_file(),
                "config": json.loads(
                    (
                        workdir
                        / "scratch"
                        / "config"
                        / "opencode"
                        / "opencode.json"
                    ).read_text(encoding="utf-8")
                ),
                "evidence": json.loads(
                    (
                        workdir
                        / "inputs"
                        / "evidence"
                        / "evidence-poc-001.json"
                    ).read_text(encoding="utf-8")
                ),
                "mcp_bundle": json.loads(
                    (workdir / "scratch" / "mcp-bundle.json").read_text(
                        encoding="utf-8"
                    )
                ),
            }
        )

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
            base_url="http://p15-openai-mock:8080/v1",
        ),
    )
    executor = OpenCodeAttemptExecutor(
        runtime=runtime,
        image_ref=ADMITTED_IMAGE_REF,
        mcp_bridge_path=(
            Path(__file__).resolve().parents[1] / "supervisor" / "mcp_stdio_bridge.sh"
        ),
        secret_resolver=lambda _reference: SYNTHETIC_SECRET,
        workspace_root=tmp_path,
        pack_resolver=resolver,
        pack_compiler=compiler,
        trusted_internal_network_id="d" * 64,
        workspace_observer=observe,
    )

    outcome = executor.execute(attempt)

    assert outcome.output_bundle == output
    assert outcome.receipt.pack_identity is not None
    assert outcome.receipt.pack_identity.sha256 == pack_sha256
    assert outcome.receipt.compiled_config_sha256 is not None
    assert outcome.receipt.advertised_skills == ("evidence-candidate",)
    assert outcome.receipt.allowed_mcp_capabilities == ("knowledge.read-evidence",)
    assert [item.model_dump() for item in outcome.receipt.tool_call_summary] == [
        {"tool": "read_evidence", "calls": 1}
    ]
    assert runtime.last_config is not None
    assert runtime.last_config.internal_network_id == "d" * 64
    assert {mount.container_path for mount in runtime.last_config.read_only_inputs} >= {
        "/workspace",
        "/harness/mcp_stdio_bridge.sh",
        "/harness/mcp-bundle.json",
    }
    assert runtime.last_config.command[0].startswith("cd /workspace && exec opencode run")
    assert 'Authorized Evidence IDs: ["evidence-poc-001"]' in (
        runtime.last_config.command[0]
    )
    assert runtime.writable_modes == {
        "home": 0o777,
        "cache": 0o777,
        "state": 0o777,
        "data": 0o777,
        "staging": 0o777,
    }
    environment = dict(runtime.last_config.environment)
    assert environment["HOME"] == "/scratch/home"
    assert environment["XDG_CONFIG_HOME"] == "/scratch/config"
    assert environment["OPENCODE_DISABLE_EXTERNAL_SKILLS"] == "1"
    assert environment["OPENCODE_DISABLE_CLAUDE_CODE_SKILLS"] == "1"
    assert snapshots[0]["skill"] is True
    assert snapshots[0]["evidence"] == input_bundle["evidence"][0]
    bundle = snapshots[0]["mcp_bundle"]
    assert bundle["allowed_tools"] == ["read_evidence"]
    assert bundle["allowed_evidence_ids"] == ["evidence-poc-001"]
    assert bundle["pack_sha256"] == pack_sha256
    serialized = json.dumps(
        {
            "config": runtime.last_config.model_dump(mode="json"),
            "receipt": outcome.receipt.model_dump(mode="json"),
            "bundle": bundle,
        },
        sort_keys=True,
    )
    assert SYNTHETIC_SECRET not in serialized
    assert attempt.generation_token not in serialized
    assert attempt.fencing_token not in serialized
    assert not snapshots[0]["config"].get("plugin")


def test_pack_executor_rejects_attempt_without_instruction_ref_before_launch(
    tmp_path: Path,
) -> None:
    from supervisor.opencode_executor import OpenCodeAttemptExecutor
    from supervisor.pack_compiler import HarnessPackCompiler, HarnessPackResolver

    runtime = FakeContainerRuntime(exit_code=0)
    executor = OpenCodeAttemptExecutor(
        runtime=runtime,
        image_ref=ADMITTED_IMAGE_REF,
        mcp_bridge_path=(
            Path(__file__).resolve().parents[1] / "supervisor" / "mcp_stdio_bridge.sh"
        ),
        secret_resolver=lambda _reference: SYNTHETIC_SECRET,
        workspace_root=tmp_path,
        pack_resolver=HarnessPackResolver({"knowledge-candidate-v1": PACK_ROOT}),
        pack_compiler=HarnessPackCompiler({}),
    )

    with pytest.raises(ValueError, match="instruction_ref"):
        executor.execute(_attempt())

    assert runtime.last_config is None


def test_output_parser_accepts_fixed_opencode_1_18_14_part_text(tmp_path: Path) -> None:
    from supervisor.opencode_executor import OpenCodeAttemptExecutor

    output = {"candidate_group_id": "candidate-poc-001"}
    event = {
        "type": "text",
        "part": {"type": "text", "text": json.dumps(output)},
    }
    tmp_path.joinpath("events.jsonl").write_text(
        json.dumps(event) + "\n",
        encoding="utf-8",
    )

    assert OpenCodeAttemptExecutor._read_jsonl_output(tmp_path) == output


@pytest.mark.parametrize(
    "events",
    [
        b'{"type":"text","part":{"text":"{bad-json"}}\n',
        b'{"type":"step_finish","part":{}}\n',
    ],
)
def test_executor_classifies_invalid_or_empty_output_as_failed(
    tmp_path: Path,
    events: bytes,
) -> None:
    from supervisor.opencode_executor import OpenCodeAttemptExecutor

    runtime = FakeContainerRuntime(
        exit_code=0,
        staged_outputs={Path("events.jsonl"): events},
    )
    executor = OpenCodeAttemptExecutor(
        runtime=runtime,
        image_ref=IMAGE_REF,
        mcp_bridge_path=(
            Path(__file__).resolve().parents[1] / "supervisor" / "mcp_stdio_bridge.sh"
        ),
        secret_resolver=lambda _reference: SYNTHETIC_SECRET,
        workspace_root=tmp_path,
    )

    outcome = executor.execute(_attempt())

    assert outcome.output_bundle is None
    assert outcome.receipt.status is HarnessStatus.FAILED
    assert outcome.receipt.exit_classification is ExitClassification.FAILED
    assert outcome.receipt.retryable is False
    assert outcome.receipt.message == "OpenCode output validation failed"
