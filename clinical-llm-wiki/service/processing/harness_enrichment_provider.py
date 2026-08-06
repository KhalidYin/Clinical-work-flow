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
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any

from .model_provider import (
    InvocationErrorType,
    InvocationStatus,
    ModelInvocation,
    ModelProviderPort,
    ModelRequest,
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
