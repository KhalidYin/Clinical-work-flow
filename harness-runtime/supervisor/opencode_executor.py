"""Fixed OpenCode executor compiled entirely inside the Supervisor boundary."""

from __future__ import annotations

import json
import re
import tempfile
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from contracts.manifest import ArtifactManifest
from contracts.receipt import ExecutionReceipt, ExitClassification
from contracts.request import HarnessExecutionRequest, McpConfig
from contracts.result import HarnessStatus
from supervisor.container_runtime import ContainerRuntimePort, ReadOnlyMount
from supervisor.lifecycle import AttemptExecutionOutcome
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
        workspace_observer: WorkspaceObserver | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._runtime = runtime
        self._image_ref = image_ref
        self._mcp_bridge_path = mcp_bridge_path
        self._secret_resolver = secret_resolver
        self._workspace_root = workspace_root
        self._environment = environment
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
            (scratch_path / "data" / "opencode").mkdir(parents=True)
            (scratch_path / "data" / "opencode" / "auth.json").touch()

            input_path = input_dir / "input.json"
            input_path.write_text(
                json.dumps(attempt.input_bundle, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            mcp_bundle_path = secret_dir / "mcp-bundle.json"
            mcp_bundle_path.write_text(
                json.dumps(
                    {
                        "attempt_id": attempt.attempt_id,
                        "generation_token": attempt.generation_token,
                        "spec_sha256": attempt.spec_sha256,
                        "allowed_tools": ["read_input"],
                        "input_root": "/inputs",
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            mcp_bundle_path.chmod(0o444)

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
                mcp_config=McpConfig(transport="stdio", tools={"read_input"}),
                secret_refs=attempt.secret_refs,
            )
            environment = dict(self._environment)
            environment["XDG_DATA_HOME"] = "/scratch/data"
            environment["XDG_CONFIG_HOME"] = "/scratch/config"
            command = (
                "exec opencode run 'Produce one JSON object matching the attached schema.' "
                '--file /inputs/input.json --model "$1" --format json --pure '
                "> /staging/events.jsonl",
                "opencode-harness",
                f"{provider}/{model}",
            )
            if self._workspace_observer is not None:
                self._workspace_observer(workdir)
            receipt = HarnessSupervisor(runtime=self._runtime).execute(
                harness_request,
                entrypoint=("/bin/sh", "-c"),
                command=command,
                extra_read_only_mounts=(
                    ReadOnlyMount(
                        host_path=str(auth_path),
                        container_path="/scratch/data/opencode/auth.json",
                    ),
                    ReadOnlyMount(
                        host_path=str(self._mcp_bridge_path),
                        container_path="/harness/mcp_stdio_bridge.sh",
                    ),
                    ReadOnlyMount(
                        host_path=str(mcp_bundle_path),
                        container_path="/harness/mcp-bundle.json",
                    ),
                ),
                environment=tuple(environment.items()),
                control_request_sha256=attempt.request_sha256(),
            )
            output = (
                self._read_jsonl_output(scratch_path / "staging")
                if receipt.status == HarnessStatus.SUCCEEDED
                else None
            )
            return AttemptExecutionOutcome(receipt=receipt, output_bundle=output)

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
            data = event.get("data")
            if isinstance(data, dict) and isinstance(data.get("text"), str):
                text_parts.append(data["text"])
        if not text_parts:
            raise ValueError("OpenCode output contains no text event")
        raw = "".join(text_parts).strip()
        if raw.startswith("```json") and raw.endswith("```"):
            raw = raw[7:-3].strip()
        output = json.loads(raw)
        if not isinstance(output, dict):
            raise ValueError("OpenCode structured output must be a JSON object")
        return output
