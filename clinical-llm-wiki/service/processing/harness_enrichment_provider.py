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
import math
import tempfile
from pathlib import Path
from time import perf_counter, sleep as system_sleep
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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


SupervisorTransport = Callable[
    [str, str, dict[str, object] | None, dict[str, str]],
    tuple[int, dict[str, object]],
]


class _UrllibSupervisorTransport:
    """One-shot JSON transport; it intentionally has no retry policy."""

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def __call__(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, object]]:
        body = None
        request_headers = {"Accept": "application/json", **headers}
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        request = Request(
            self._base_url + path,
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                status_code = response.status
                raw = response.read()
        except HTTPError as error:
            status_code = error.code
            raw = error.read()
        except (OSError, URLError) as error:
            raise RuntimeError("supervisor transport unavailable") from error
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError("supervisor returned invalid JSON") from error
        if not isinstance(decoded, dict):
            raise RuntimeError("supervisor returned a non-object response")
        return status_code, decoded


class RemoteSupervisorEnrichmentProvider(ModelProviderPort):
    """Submit product-level Attempts to the isolated Harness Supervisor."""

    adapter_id = "opencode@1.18.14"
    validator_id = "knowledge.enrichment.output-schema"
    validator_version = "1.0.0"
    _terminal_states = frozenset(
        {"succeeded", "failed", "cancelled", "timed_out", "orphaned"}
    )

    def __init__(
        self,
        *,
        supervisor_url: str,
        machine_token: str,
        spec_sha256: str,
        instruction_ref: Mapping[str, str] | None = None,
        transport: SupervisorTransport | None = None,
        poll_interval_seconds: float = 1.0,
        sleep: Callable[[float], None] = system_sleep,
    ) -> None:
        if not supervisor_url.startswith(("http://", "https://")):
            raise ValueError("supervisor_url must use HTTP or HTTPS")
        if not machine_token:
            raise ValueError("machine_token must not be empty")
        if len(spec_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in spec_sha256
        ):
            raise ValueError("spec_sha256 must be a lowercase SHA-256")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        self._headers = {"Authorization": f"Bearer {machine_token}"}
        self._spec_sha256 = spec_sha256
        self._instruction_ref = None
        if instruction_ref is not None:
            try:
                from contracts.spec import InstructionRef

                self._instruction_ref = InstructionRef.model_validate(
                    dict(instruction_ref)
                ).model_dump(mode="json", exclude_none=True)
            except (ImportError, ValueError, TypeError) as exc:
                raise ValueError("instruction_ref must be a valid Harness Pack reference") from exc
        self._poll_interval_seconds = poll_interval_seconds
        self._sleep = sleep
        self._transport = transport or _UrllibSupervisorTransport(
            supervisor_url,
            timeout_seconds=max(5.0, poll_interval_seconds * 2),
        )

    def invoke(self, request: ModelRequest) -> ModelInvocation:
        enforce_data_boundary(request.model_profile, request.data_boundary)
        Draft202012Validator.check_schema(request.prompt_profile.output_schema)
        started = perf_counter()
        input_bundle: dict[str, object] = {
            "system_instruction": request.prompt_profile.system_template,
            "output_schema": request.prompt_profile.output_schema,
            "messages": [message.model_dump(mode="json") for message in request.messages],
            "data_boundary": request.data_boundary.value,
            "provider": request.model_profile.provider,
            "model": request.model_profile.model,
        }
        attempt_payload: dict[str, object] = {
            "contract_version": "1.0.0",
            "attempt_id": request.attempt.attempt_id,
            "run_id": request.attempt.run_id,
            "step_id": request.attempt.step_id,
            "generation_token": f"attempt-{request.attempt.attempt_number}",
            "fencing_token": (
                f"{request.attempt.attempt_id}:{request.attempt.attempt_number}"
            ),
            "adapter_id": self.adapter_id,
            "spec_sha256": self._spec_sha256,
            "input_sha256": _canonical_sha256(input_bundle),
            "input_bundle": input_bundle,
            "secret_refs": [request.model_profile.secret_ref],
            "timeout_seconds": request.model_profile.timeout_seconds,
            "network_mode": "none",
        }
        if self._instruction_ref is not None:
            attempt_payload["instruction_ref"] = dict(self._instruction_ref)
        request_sha256 = _canonical_sha256(attempt_payload)
        poll_budget_expired = False
        try:
            accepted = self._call("POST", "/v1/attempts", attempt_payload, {200, 202})
            self._validate_projection(accepted, request, request_sha256)
            state = accepted.get("state")
            max_polls = max(
                1,
                math.ceil(
                    request.model_profile.timeout_seconds / self._poll_interval_seconds
                )
                + 1,
            )
            for poll_number in range(max_polls):
                if state in self._terminal_states:
                    break
                heartbeat = self._call(
                    "POST",
                    f"/v1/attempts/{request.attempt.attempt_id}/heartbeat",
                    None,
                    {200},
                )
                self._validate_projection(heartbeat, request, request_sha256)
                status = self._call(
                    "GET",
                    f"/v1/attempts/{request.attempt.attempt_id}",
                    None,
                    {200},
                )
                self._validate_projection(status, request, request_sha256)
                state = status.get("state")
                if state in self._terminal_states:
                    break
                if poll_number + 1 < max_polls:
                    self._sleep(self._poll_interval_seconds)
            else:
                state = None
            if state not in self._terminal_states:
                poll_budget_expired = True
                cancelled = self._call(
                    "POST",
                    f"/v1/attempts/{request.attempt.attempt_id}/cancel",
                    None,
                    {200},
                )
                self._validate_projection(cancelled, request, request_sha256)
                state = cancelled.get("state")
            result = self._call(
                "GET",
                f"/v1/attempts/{request.attempt.attempt_id}/result",
                None,
                {200},
            )
            receipt = self._validate_result(result, request, request_sha256, state)
        except (RuntimeError, ValueError, KeyError, TypeError):
            invocation = self._failure_invocation(
                request=request,
                started=started,
                error_type=InvocationErrorType.PROVIDER_ERROR,
                error_message="supervisor request failed contract validation",
            )
            raise ModelProviderError(invocation) from None

        common = self._invocation_common(request, started, receipt)
        receipt_status = receipt["status"]
        if state != "succeeded" or receipt_status != "succeeded":
            error_type = (
                InvocationErrorType.TIMEOUT
                if (
                    poll_budget_expired
                    or state == "timed_out"
                    or receipt_status == "timed_out"
                )
                else InvocationErrorType.PROVIDER_ERROR
            )
            invocation = ModelInvocation(
                **common,
                status=InvocationStatus.FAILED,
                error_type=error_type,
                error_message=str(receipt.get("message") or state),
            )
            raise ModelProviderError(invocation)

        output = result.get("output_bundle")
        output_sha256 = result.get("output_sha256")
        try:
            if not isinstance(output, dict):
                raise ValueError("terminal success has no object output")
            if output_sha256 != _canonical_sha256(output):
                raise ValueError("terminal output hash mismatch")
            Draft202012Validator(request.prompt_profile.output_schema).validate(output)
        except (ValueError, JsonSchemaValidationError):
            validation = self._validation_receipt(
                request=request,
                output=output if isinstance(output, dict) else None,
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
            request=request,
            output=output,
            result="passed",
            findings=(),
        )
        return ModelInvocation(
            **common,
            status=InvocationStatus.SUCCEEDED,
            output_sha256=output_sha256,
            output=output,
            validation_receipt=validation,
        )

    def _call(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
        expected_statuses: set[int],
    ) -> dict[str, object]:
        status_code, response = self._transport(method, path, payload, dict(self._headers))
        if status_code not in expected_statuses:
            raise RuntimeError("supervisor rejected request")
        return response

    @staticmethod
    def _validate_projection(
        projection: Mapping[str, object],
        request: ModelRequest,
        request_sha256: str,
    ) -> None:
        if projection.get("contract_version") != "1.0.0":
            raise ValueError("unsupported supervisor contract version")
        if projection.get("attempt_id") != request.attempt.attempt_id:
            raise ValueError("supervisor attempt identity mismatch")
        if projection.get("request_sha256") != request_sha256:
            raise ValueError("supervisor request hash mismatch")
        if projection.get("state") not in {
            "accepted",
            "running",
            "succeeded",
            "failed",
            "cancelled",
            "timed_out",
            "orphaned",
        }:
            raise ValueError("supervisor returned invalid state")

    def _validate_result(
        self,
        result: Mapping[str, object],
        request: ModelRequest,
        request_sha256: str,
        state: object,
    ) -> dict[str, object]:
        if result.get("contract_version") != "1.0.0":
            raise ValueError("unsupported supervisor result version")
        if result.get("attempt_id") != request.attempt.attempt_id:
            raise ValueError("supervisor result attempt mismatch")
        if result.get("request_sha256") != request_sha256:
            raise ValueError("supervisor result request hash mismatch")
        receipt = result.get("receipt")
        if not isinstance(receipt, dict):
            raise ValueError("supervisor result receipt is missing")
        if receipt.get("request_sha256") != request_sha256:
            raise ValueError("execution receipt request hash mismatch")
        if receipt.get("spec_sha256") != self._spec_sha256:
            raise ValueError("execution receipt spec hash mismatch")
        if receipt.get("adapter_id") != self.adapter_id:
            raise ValueError("execution receipt adapter mismatch")
        expected_exit = "failed" if state == "failed" else state
        if receipt.get("exit_classification") != expected_exit:
            raise ValueError("execution receipt classification mismatch")
        return receipt

    def _invocation_common(
        self,
        request: ModelRequest,
        started: float,
        receipt: dict[str, object],
    ) -> dict[str, Any]:
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
            "provider_request_id": str(receipt["execution_id"]),
            "latency_ms": max(0, round((perf_counter() - started) * 1000)),
            "execution_receipt": receipt,
        }

    def _validation_receipt(
        self,
        *,
        request: ModelRequest,
        output: dict[str, Any] | None,
        result: str,
        findings: tuple[str, ...],
    ) -> dict[str, Any]:
        return {
            "validator_id": self.validator_id,
            "validator_version": self.validator_version,
            "validator_sha256": hashlib.sha256(
                (
                    self.validator_id
                    + ":"
                    + self.validator_version
                    + ":"
                    + request.prompt_profile.output_schema_sha256
                ).encode("utf-8")
            ).hexdigest(),
            "input_sha256": (
                _canonical_sha256(output) if output is not None else request.input_sha256
            ),
            "result": result,
            "findings": list(findings),
        }

    def _failure_invocation(
        self,
        *,
        request: ModelRequest,
        started: float,
        error_type: InvocationErrorType,
        error_message: str,
    ) -> ModelInvocation:
        return ModelInvocation(
            attempt=request.attempt,
            model_profile_id=request.model_profile.profile_id,
            model_profile_version=request.model_profile.version,
            provider="harness",
            model=self.adapter_id,
            prompt_profile_id=request.prompt_profile.profile_id,
            prompt_profile_version=request.prompt_profile.version,
            output_schema_sha256=request.prompt_profile.output_schema_sha256,
            data_boundary=request.data_boundary,
            input_sha256=request.input_sha256,
            latency_ms=max(0, round((perf_counter() - started) * 1000)),
            status=InvocationStatus.FAILED,
            error_type=error_type,
            error_message=error_message,
        )


def _canonical_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
