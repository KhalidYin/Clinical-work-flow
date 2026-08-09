"""H0-F harness enrichment provider: ModelProviderPort over the harness runtime.

The knowledge product keeps its existing ``ModelProviderPort`` contract and
durable Candidate governance unchanged; this provider is the designed
extension point. For ``executor_kind=harness`` attempts it runs a harness
adapter (fake/replay by default, zero outbound) and maps the untrusted
``HarnessResult`` into the product's ``ModelInvocation`` audit shape.

The harness-runtime packages are imported lazily: the worker environment must
put the ``harness-runtime/`` directory on ``PYTHONPATH`` (compose wiring is a
later deployment step).
"""

from __future__ import annotations

import json
import hashlib
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from .model_provider import (
    InvocationErrorType,
    InvocationStatus,
    ModelInvocation,
    ModelProviderError,
    ModelProviderPort,
    ModelRequest,
    enforce_data_boundary,
)


class HarnessEnrichmentProvider(ModelProviderPort):
    """Run one harness adapter attempt and record a product ModelInvocation."""

    def __init__(self, adapter: Any, spec_sha256: str = "0" * 64) -> None:
        self._adapter = adapter
        self._spec_sha256 = spec_sha256

    def invoke(self, request: ModelRequest) -> ModelInvocation:
        from contracts.request import HarnessExecutionRequest  # lazy harness-runtime

        started = perf_counter()
        workdir = Path(tempfile.mkdtemp(prefix="harness-enrichment-"))
        input_path = workdir / "input.json"
        output_path = workdir / "output.json"
        scratch_path = workdir / "scratch"
        payload = {
            "messages": [
                message.model_dump(mode="json") for message in request.messages
            ],
            "evidence_boundary": request.data_boundary.value,
        }
        input_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        harness_request = HarnessExecutionRequest(
            attempt_id=request.attempt.attempt_id,
            adapter_id=self._adapter.adapter_id,
            spec_sha256=self._spec_sha256,
            image_ref=None,
            input_path=input_path,
            scratch_path=scratch_path,
            output_path=output_path,
            timeout_seconds=request.model_profile.timeout_seconds,
            payload=payload,
        )
        result = self._adapter.run(harness_request)
        latency_ms = int((perf_counter() - started) * 1000)

        common = dict(
            attempt=request.attempt,
            model_profile_id=request.model_profile.profile_id,
            model_profile_version=request.model_profile.version,
            provider="harness",
            model=self._adapter.adapter_id,
            prompt_profile_id=request.prompt_profile.profile_id,
            prompt_profile_version=request.prompt_profile.version,
            output_schema_sha256=request.prompt_profile.output_schema_sha256,
            data_boundary=request.data_boundary,
            input_sha256=request.input_sha256,
            latency_ms=latency_ms,
        )
        if result.status.value == "succeeded":
            output = self._read_output(output_path)
            return ModelInvocation(
                **common,
                status=(
                    InvocationStatus.REPLAYED
                    if self._adapter.adapter_id.startswith("replay.")
                    else InvocationStatus.SUCCEEDED
                ),
                output_sha256=result.output_sha256,
                output=output,
            )
        error_type = (
            InvocationErrorType.TIMEOUT
            if result.status.value == "timed_out"
            else InvocationErrorType.PROVIDER_ERROR
        )
        return ModelInvocation(
            **common,
            status=InvocationStatus.FAILED,
            error_type=error_type,
            error_message=result.message or result.status.value,
        )

    @staticmethod
    def _read_output(output_path: Path) -> dict[str, Any]:
        if not output_path.is_file():
            raise ValueError("succeeded harness result has no staging output artifact")
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("harness output artifact is not a JSON object")
        return payload


WorkspaceObserver = Callable[[Path], None]
SecretResolver = Callable[[str], str]


class SupervisedOpenCodeEnrichmentProvider(ModelProviderPort):
    """Run one digest-locked OpenCode container under the Harness supervisor.

    Request content is materialized as a read-only input artifact. Provider
    credentials are resolved just-in-time into one read-only auth file and the
    whole attempt workspace is removed on every exit path.
    """

    adapter_id = "opencode@1.18.14"
    validator_id = "knowledge.enrichment.output-schema"
    validator_version = "1.0.0"

    def __init__(
        self,
        *,
        supervisor: Any,
        image_ref: str,
        spec_sha256: str,
        secret_resolver: SecretResolver,
        environment: tuple[tuple[str, str], ...] = (),
        mcp_bridge_path: Path | None = None,
        workspace_observer: WorkspaceObserver | None = None,
    ) -> None:
        self._supervisor = supervisor
        self._image_ref = image_ref
        self._spec_sha256 = spec_sha256
        self._secret_resolver = secret_resolver
        self._environment = environment
        self._mcp_bridge_path = mcp_bridge_path or (
            Path(__file__).resolve().parents[3]
            / "harness-runtime"
            / "supervisor"
            / "mcp_stdio_bridge.sh"
        )
        self._workspace_observer = workspace_observer

    def invoke(self, request: ModelRequest) -> ModelInvocation:
        from contracts.receipt import ValidationReceipt
        from contracts.request import HarnessExecutionRequest, McpConfig
        from supervisor.container_runtime import ReadOnlyMount

        enforce_data_boundary(request.model_profile, request.data_boundary)
        Draft202012Validator.check_schema(request.prompt_profile.output_schema)
        started = perf_counter()
        with tempfile.TemporaryDirectory(prefix="harness-opencode-") as directory:
            workdir = Path(directory)
            input_dir = workdir / "inputs"
            secret_dir = workdir / "secrets"
            scratch_path = workdir / "scratch"
            input_dir.mkdir()
            secret_dir.mkdir()
            auth_target = scratch_path / "data" / "opencode" / "auth.json"
            auth_target.parent.mkdir(parents=True)
            auth_target.touch()

            input_path = input_dir / "input.json"
            payload = {
                "system_instruction": request.prompt_profile.system_template,
                "output_schema": request.prompt_profile.output_schema,
                "messages": [
                    message.model_dump(mode="json") for message in request.messages
                ],
                "data_boundary": request.data_boundary.value,
            }
            input_path.write_text(
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            mcp_bundle_path = secret_dir / "mcp-bundle.json"
            mcp_bundle_path.write_text(
                json.dumps(
                    {
                        "attempt_id": request.attempt.attempt_id,
                        "generation_token": f"attempt-{request.attempt.attempt_number}",
                        "spec_sha256": self._spec_sha256,
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

            secret = self._secret_resolver(request.model_profile.secret_ref)
            auth_path = secret_dir / "opencode-auth.json"
            auth_path.write_text(
                json.dumps(
                    {
                        request.model_profile.provider: {
                            "type": "api",
                            "key": secret,
                        }
                    }
                ),
                encoding="utf-8",
            )
            auth_path.chmod(0o444)

            harness_request = HarnessExecutionRequest(
                attempt_id=request.attempt.attempt_id,
                adapter_id=self.adapter_id,
                spec_sha256=self._spec_sha256,
                image_ref=self._image_ref,
                input_path=input_path,
                scratch_path=scratch_path,
                output_path=scratch_path / "staging" / "events.jsonl",
                timeout_seconds=request.model_profile.timeout_seconds,
                payload={"input_sha256": request.input_sha256},
                mcp_config=McpConfig(transport="stdio", tools={"read_input"}),
                secret_refs=(request.model_profile.secret_ref,),
            )
            environment = dict(self._environment)
            environment["XDG_DATA_HOME"] = "/scratch/data"
            environment["XDG_CONFIG_HOME"] = "/scratch/config"
            command = (
                "exec opencode run 'Produce one JSON object matching the attached schema.' "
                "--file /inputs/input.json --model \"$1\" --format json --pure "
                "> /staging/events.jsonl",
                "opencode-harness",
                f"{request.model_profile.provider}/{request.model_profile.model}",
            )
            if not self._mcp_bridge_path.is_file():
                raise RuntimeError("OpenCode MCP stdio bridge is not available")
            if self._workspace_observer is not None:
                self._workspace_observer(workdir)
            receipt = self._supervisor.execute(
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
            )
            common = self._invocation_common(request, started, receipt)
            if receipt.status.value != "succeeded":
                error_type = (
                    InvocationErrorType.TIMEOUT
                    if receipt.status.value == "timed_out"
                    else InvocationErrorType.PROVIDER_ERROR
                )
                invocation = ModelInvocation(
                    **common,
                    status=InvocationStatus.FAILED,
                    error_type=error_type,
                    error_message=receipt.message or receipt.status.value,
                )
                raise ModelProviderError(invocation)

            output: dict[str, Any] | None = None
            try:
                output = self._read_jsonl_output(scratch_path / "staging")
                Draft202012Validator(request.prompt_profile.output_schema).validate(output)
            except (ValueError, json.JSONDecodeError, JsonSchemaValidationError):
                validation = self._validation_receipt(
                    ValidationReceipt,
                    request=request,
                    output=output,
                    result="failed",
                    findings=("structured_output_invalid",),
                )
                invocation = ModelInvocation(
                    **common,
                    status=InvocationStatus.FAILED,
                    error_type=InvocationErrorType.STRUCTURED_OUTPUT_INVALID,
                    error_message="structured_output_invalid: product schema validation failed",
                    validation_receipt=validation,
                )
                raise ModelProviderError(invocation) from None

            validation = self._validation_receipt(
                ValidationReceipt,
                request=request,
                output=output,
                result="passed",
                findings=(),
            )
            return ModelInvocation(
                **common,
                status=InvocationStatus.SUCCEEDED,
                output_sha256=_canonical_sha256(output),
                output=output,
                validation_receipt=validation,
            )

    def _invocation_common(self, request: ModelRequest, started: float, receipt: Any) -> dict[str, Any]:
        return {
            "attempt": request.attempt,
            "model_profile_id": request.model_profile.profile_id,
            "model_profile_version": request.model_profile.version,
            "provider": "harness",
            "model": self.adapter_id,
            "prompt_profile_id": request.prompt_profile.profile_id,
            "prompt_profile_version": request.prompt_profile.version,
            "output_schema_sha256": request.prompt_profile.output_schema_sha256,
            "data_boundary": request.data_boundary,
            "input_sha256": request.input_sha256,
            "provider_request_id": receipt.execution_id,
            "latency_ms": max(0, round((perf_counter() - started) * 1000)),
            "execution_receipt": receipt.model_dump(mode="json"),
        }

    def _validation_receipt(
        self,
        receipt_type: Any,
        *,
        request: ModelRequest,
        output: dict[str, Any] | None,
        result: str,
        findings: tuple[str, ...],
    ) -> dict[str, Any]:
        input_sha256 = _canonical_sha256(output) if output is not None else request.input_sha256
        validator_sha256 = hashlib.sha256(
            (
                self.validator_id
                + ":"
                + self.validator_version
                + ":"
                + request.prompt_profile.output_schema_sha256
            ).encode("utf-8")
        ).hexdigest()
        receipt = receipt_type(
            validator_id=self.validator_id,
            validator_version=self.validator_version,
            validator_sha256=validator_sha256,
            input_sha256=input_sha256,
            result=result,
            findings=findings,
        )
        return receipt.model_dump(mode="json")

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


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
