"""Fixed OpenCode executor compiled entirely inside the Supervisor boundary."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import re
import tempfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contracts.manifest import ArtifactManifest
from contracts.receipt import ExecutionReceipt, ExitClassification, ToolCallSummary
from contracts.request import HarnessExecutionRequest, McpConfig
from contracts.result import HarnessStatus
from supervisor.container_runtime import ContainerRuntimePort, ReadOnlyMount
from supervisor.lifecycle import AttemptExecutionOutcome
from supervisor.pack_compiler import (
    CompiledHarnessPack,
    HarnessPackCompiler,
    HarnessPackResolver,
)
from supervisor.service_contracts import SupervisorAttemptRequest
from supervisor.supervisor import HarnessSupervisor


SecretResolver = Callable[[str], str]
WorkspaceObserver = Callable[[Path], None]

_PROVIDER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")


class OpenCodeAttemptExecutor:
    """Materialize and run one digest-locked, zero-network OpenCode Attempt."""

    def __init__(
        self,
        *,
        runtime: ContainerRuntimePort,
        image_ref: str,
        mcp_bridge_path: Path,
        secret_resolver: SecretResolver,
        workspace_root: Path,
        environment: tuple[tuple[str, str], ...] = (),
        pack_resolver: HarnessPackResolver | None = None,
        pack_compiler: HarnessPackCompiler | None = None,
        trusted_internal_network_id: str | None = None,
        host_path_mapper: Callable[[str | Path], str] | None = None,
        workspace_observer: WorkspaceObserver | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._runtime = runtime
        self._image_ref = image_ref
        self._mcp_bridge_path = mcp_bridge_path
        self._secret_resolver = secret_resolver
        self._workspace_root = workspace_root
        self._environment = environment
        if (pack_resolver is None) != (pack_compiler is None):
            raise ValueError("pack_resolver and pack_compiler must be configured together")
        self._pack_resolver = pack_resolver
        self._pack_compiler = pack_compiler
        self._trusted_internal_network_id = trusted_internal_network_id
        self._host_path_mapper = host_path_mapper
        self._workspace_observer = workspace_observer
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def execute(self, attempt: SupervisorAttemptRequest) -> AttemptExecutionOutcome:
        if len(attempt.secret_refs) != 1:
            raise ValueError("OpenCode Attempt requires exactly one secret reference")
        provider = attempt.input_bundle.get("provider")
        model = attempt.input_bundle.get("model")
        if not isinstance(provider, str) or _PROVIDER.fullmatch(provider) is None:
            raise ValueError("OpenCode provider identifier is invalid")
        if not isinstance(model, str) or _MODEL.fullmatch(model) is None:
            raise ValueError("OpenCode model identifier is invalid")
        if not self._mcp_bridge_path.is_file():
            raise RuntimeError("OpenCode MCP stdio bridge is not available")
        if self._pack_resolver is not None and attempt.instruction_ref is None:
            raise ValueError("instruction_ref is required for Pack execution")

        self._workspace_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="supervisor-opencode-",
            dir=self._workspace_root,
        ) as directory:
            workdir = Path(directory)
            input_dir = workdir / "inputs"
            secret_dir = workdir / "secrets"
            scratch_path = workdir / "scratch"
            input_dir.mkdir()
            secret_dir.mkdir()
            compiled_pack = self._compile_pack(attempt, workdir)
            (scratch_path / "data" / "opencode").mkdir(parents=True, exist_ok=True)
            (scratch_path / "data" / "opencode" / "auth.json").touch()

            input_path = input_dir / "input.json"
            input_path.write_text(
                json.dumps(attempt.input_bundle, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            evidence_ids = self._materialize_evidence(attempt, input_dir)
            mcp_bundle_path = (
                compiled_pack.mcp_bundle_path
                if compiled_pack is not None
                else secret_dir / "mcp-bundle.json"
            )
            mcp_bundle = (
                json.loads(mcp_bundle_path.read_text(encoding="utf-8"))
                if compiled_pack is not None
                else {"allowed_tools": ["read_input"]}
            )
            mcp_bundle.update(
                {
                    "attempt_id": attempt.attempt_id,
                    "generation_token_sha256": hashlib.sha256(
                        attempt.generation_token.encode("utf-8")
                    ).hexdigest(),
                    "fencing_token_sha256": hashlib.sha256(
                        attempt.fencing_token.encode("utf-8")
                    ).hexdigest(),
                    "spec_sha256": attempt.spec_sha256,
                    "pack_sha256": (
                        compiled_pack.pack_identity.sha256
                        if compiled_pack is not None
                        else None
                    ),
                    "allowed_evidence_ids": list(evidence_ids),
                    "input_root": "/inputs",
                }
            )
            mcp_bundle_path.write_text(
                json.dumps(mcp_bundle, sort_keys=True),
                encoding="utf-8",
            )
            mcp_bundle_path.chmod(0o444)
            mcp_bridge_runtime_path = secret_dir / "mcp_stdio_bridge.sh"
            mcp_bridge_runtime_path.write_bytes(self._mcp_bridge_path.read_bytes())
            mcp_bridge_runtime_path.chmod(0o444)

            if compiled_pack is None:
                config_path = scratch_path / "config" / "opencode" / "opencode.json"
                config_path.parent.mkdir(parents=True)
                config_path.write_text(
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
                        },
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
            elif compiled_pack.model_ref != f"{provider}/{model}":
                raise ValueError("Attempt model does not match the trusted Pack binding")

            secret = self._secret_resolver(attempt.secret_refs[0])
            auth_path = secret_dir / "opencode-auth.json"
            auth_path.write_text(
                json.dumps({provider: {"type": "api", "key": secret}}),
                encoding="utf-8",
            )
            auth_path.chmod(0o444)

            harness_request = HarnessExecutionRequest(
                attempt_id=attempt.attempt_id,
                adapter_id=attempt.adapter_id,
                spec_sha256=attempt.spec_sha256,
                image_ref=self._image_ref,
                input_path=input_path,
                scratch_path=scratch_path,
                output_path=scratch_path / "staging" / "events.jsonl",
                timeout_seconds=attempt.timeout_seconds,
                payload={"control_request_sha256": attempt.request_sha256()},
                mcp_config=McpConfig(
                    transport="stdio",
                    tools=(
                        frozenset({"read_evidence"})
                        if compiled_pack is not None
                        else frozenset({"read_input"})
                    ),
                ),
                secret_refs=attempt.secret_refs,
            )
            environment = dict(self._environment)
            environment["XDG_DATA_HOME"] = "/scratch/data"
            environment["XDG_CONFIG_HOME"] = "/scratch/config"
            if compiled_pack is not None:
                environment.update(
                    {
                        "HOME": "/scratch/home",
                        "XDG_CACHE_HOME": "/scratch/cache",
                        "XDG_STATE_HOME": "/scratch/state",
                        "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
                        "OPENCODE_DISABLE_CLAUDE_CODE_SKILLS": "1",
                    }
                )
                command = (
                    "cd /workspace && exec opencode run "
                    "'Load the evidence-candidate skill, call read_evidence for the "
                    "authorized Evidence, and return exactly one JSON object matching "
                    "/workspace/output.schema.json.' "
                    '--model "$1" --format json --pure > /staging/events.jsonl',
                    "opencode-harness",
                    compiled_pack.model_ref or f"{provider}/{model}",
                )
            else:
                command = (
                    "exec opencode run 'Produce one JSON object matching the attached schema.' "
                    '--file /inputs/input.json --model "$1" --format json --pure '
                    "> /staging/events.jsonl",
                    "opencode-harness",
                    f"{provider}/{model}",
                )
            if self._workspace_observer is not None:
                self._workspace_observer(workdir)
            receipt = HarnessSupervisor(
                runtime=self._runtime,
                host_path_mapper=self._host_path_mapper,
            ).execute(
                harness_request,
                entrypoint=("/bin/sh", "-c"),
                command=command,
                extra_read_only_mounts=(
                    *(
                        (
                            ReadOnlyMount(
                                host_path=str(compiled_pack.workspace_root),
                                container_path="/workspace",
                            ),
                        )
                        if compiled_pack is not None
                        else ()
                    ),
                    ReadOnlyMount(
                        host_path=str(auth_path),
                        container_path="/scratch/data/opencode/auth.json",
                    ),
                    ReadOnlyMount(
                        host_path=str(mcp_bridge_runtime_path),
                        container_path="/harness/mcp_stdio_bridge.sh",
                    ),
                    ReadOnlyMount(
                        host_path=str(mcp_bundle_path),
                        container_path="/harness/mcp-bundle.json",
                    ),
                ),
                environment=tuple(environment.items()),
                control_request_sha256=attempt.request_sha256(),
                trusted_internal_network_id=(
                    self._trusted_internal_network_id
                    if compiled_pack is not None
                    else None
                ),
            )
            if compiled_pack is not None:
                tool_call_summary = self._read_mcp_summary(
                    scratch_path / "staging"
                )
                receipt = receipt.model_copy(
                    update={
                        "pack_identity": compiled_pack.pack_identity,
                        "compiled_config_sha256": compiled_pack.compiled_config_sha256,
                        "advertised_skills": compiled_pack.advertised_skills,
                        "allowed_mcp_capabilities": (
                            compiled_pack.allowed_mcp_capabilities
                        ),
                        "tool_call_summary": tool_call_summary,
                        # Product policy owns any later Attempt; the harness never
                        # advertises an automatic retry for this completed run.
                        "retryable": False,
                    }
                )
            output = None
            if receipt.status == HarnessStatus.SUCCEEDED:
                try:
                    output = self._read_jsonl_output(scratch_path / "staging")
                except (OSError, UnicodeError, ValueError):
                    receipt = receipt.model_copy(
                        update={
                            "status": HarnessStatus.FAILED,
                            "exit_classification": ExitClassification.FAILED,
                            "message": "OpenCode output validation failed",
                            "retryable": False,
                        }
                    )
            return AttemptExecutionOutcome(receipt=receipt, output_bundle=output)

    @staticmethod
    def _read_mcp_summary(staging_root: Path) -> tuple[ToolCallSummary, ...]:
        candidates = tuple(staging_root.rglob("mcp-audit.jsonl"))
        if not candidates:
            return ()
        if len(candidates) != 1:
            raise ValueError("OpenCode staging must contain at most one MCP audit")
        counts: Counter[str] = Counter()
        for line in candidates[0].read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            tool = row.get("tool") if isinstance(row, dict) else None
            if not isinstance(tool, str) or not tool:
                raise ValueError("OpenCode MCP audit row is invalid")
            counts[tool] += 1
        return tuple(
            ToolCallSummary(tool=tool, calls=calls)
            for tool, calls in sorted(counts.items())
        )

    def _compile_pack(
        self,
        attempt: SupervisorAttemptRequest,
        workdir: Path,
    ) -> CompiledHarnessPack | None:
        if self._pack_resolver is None or self._pack_compiler is None:
            return None
        if attempt.instruction_ref is None:
            raise ValueError("instruction_ref is required for Pack execution")
        resolved = self._pack_resolver.resolve(
            attempt.instruction_ref,
            adapter_id=attempt.adapter_id,
            image_ref=self._image_ref,
        )
        return self._pack_compiler.compile(resolved, workdir)

    @staticmethod
    def _materialize_evidence(
        attempt: SupervisorAttemptRequest,
        input_dir: Path,
    ) -> tuple[str, ...]:
        raw_evidence = attempt.input_bundle.get("evidence", [])
        if not isinstance(raw_evidence, list):
            raise ValueError("Attempt evidence must be a list")
        evidence_dir = input_dir / "evidence"
        evidence_ids: list[str] = []
        for item in raw_evidence:
            if not isinstance(item, dict):
                raise ValueError("Attempt evidence item must be an object")
            evidence_id = item.get("evidence_id")
            if not isinstance(evidence_id, str) or _MODEL.fullmatch(evidence_id) is None:
                raise ValueError("Attempt evidence_id is invalid")
            if evidence_id in evidence_ids:
                raise ValueError("Attempt evidence_id values must be unique")
            evidence_dir.mkdir(parents=True, exist_ok=True)
            (evidence_dir / f"{evidence_id}.json").write_text(
                json.dumps(item, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            evidence_ids.append(evidence_id)
        return tuple(evidence_ids)

    def cancel(self, attempt_id: str, request_sha256: str) -> ExecutionReceipt:
        managed = self._terminate_managed(attempt_id, request_sha256)
        now = self._clock()
        spec_sha256 = managed[0].spec_sha256 if managed else "0" * 64
        return ExecutionReceipt(
            execution_id=f"exec-{attempt_id}",
            spec_sha256=spec_sha256,
            request_sha256=request_sha256,
            harness_id="opencode@1.18.14",
            image_ref=self._image_ref,
            adapter_id="opencode@1.18.14",
            status=HarnessStatus.CANCELLED,
            exit_classification=ExitClassification.CANCELLED,
            message=(
                "managed OpenCode container cancelled"
                if managed
                else "no matching managed OpenCode container remained"
            ),
            started_at=now,
            ended_at=now,
            artifact_manifest=ArtifactManifest(),
        )

    def recover_orphan(self, attempt_id: str, request_sha256: str) -> ExecutionReceipt:
        managed = self._terminate_managed(attempt_id, request_sha256)
        now = self._clock()
        spec_sha256 = managed[0].spec_sha256 if managed else "0" * 64
        return ExecutionReceipt(
            execution_id=f"exec-{attempt_id}",
            spec_sha256=spec_sha256,
            request_sha256=request_sha256,
            harness_id="opencode@1.18.14",
            image_ref=self._image_ref,
            adapter_id="opencode@1.18.14",
            status=HarnessStatus.FAILED,
            exit_classification=ExitClassification.ORPHANED,
            message=(
                "orphaned OpenCode container terminated"
                if managed
                else "orphaned Attempt had no matching managed container"
            ),
            started_at=now,
            ended_at=now,
            artifact_manifest=ArtifactManifest(),
        )

    def _terminate_managed(self, attempt_id: str, request_sha256: str):
        managed = tuple(
            container
            for container in self._runtime.list_managed()
            if container.attempt_id == attempt_id
            and container.request_sha256 == request_sha256
        )
        for container in managed:
            self._runtime.terminate(container.container_id)
            self._runtime.remove(container.container_id)
        return managed

    @staticmethod
    def _read_jsonl_output(staging_root: Path) -> dict[str, Any]:
        candidates = tuple(staging_root.rglob("events.jsonl"))
        if len(candidates) != 1:
            raise ValueError("OpenCode staging must contain exactly one events.jsonl")
        text_parts: list[str] = []
        for line in candidates[0].read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict) or event.get("type") != "text":
                continue
            payload = event.get("part", event.get("data"))
            if isinstance(payload, dict) and isinstance(payload.get("text"), str):
                text_parts.append(payload["text"])
        if not text_parts:
            raise ValueError("OpenCode output contains no text event")
        raw = "".join(text_parts).strip()
        if raw.startswith("```json") and raw.endswith("```"):
            raw = raw[7:-3].strip()
        output = json.loads(raw)
        if not isinstance(output, dict):
            raise ValueError("OpenCode structured output must be a JSON object")
        return output
