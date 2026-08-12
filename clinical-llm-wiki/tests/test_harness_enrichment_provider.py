"""H0-F harness enrichment provider contract tests.

Proves that ``executor_kind=harness`` attempts run through the harness
runtime adapter (replay, zero outbound) and land in the product's
``ModelInvocation`` audit shape without changing the frozen Candidate /
Review / Release semantics.
"""

# ruff: noqa: E402 -- harness-runtime imports require sys.path setup first
from __future__ import annotations

import hashlib
import builtins
import json
import sys
from pathlib import Path

import pytest

# The harness-runtime packages live outside the knowledge product; tests add
# the repository-level harness-runtime/ directory to sys.path (the worker
# environment must do the same via PYTHONPATH).
_HARNESS_RUNTIME_ROOT = Path(__file__).resolve().parents[2] / "harness-runtime"
sys.path.insert(0, str(_HARNESS_RUNTIME_ROOT))

from adapters.replay import ReplayFixture, ReplayHarnessAdapter, ReplayRecord
from contracts.manifest import ArtifactManifest
from contracts.receipt import ExecutionReceipt, ExitClassification
from contracts.result import HarnessResult, HarnessStatus
from supervisor.fake_container_runtime import FakeContainerRuntime
from supervisor.supervisor import HarnessSupervisor

from service.auth import (
    ActorContext,
    Permission,
    PrincipalType,
    ProductRole,
    WorkerPool,
)
from service.governance import (
    InMemoryGovernanceRepository,
    KnowledgeGovernanceService,
)
from service.knowledge import EvidenceReference
from service.processing import enrichment as enrichment_mod
from service.processing.contracts import ClaimedStepAttempt, ExecutorKind
from service.processing.harness_enrichment_provider import (
    HarnessEnrichmentProvider,
    RemoteSupervisorEnrichmentProvider,
    SupervisedOpenCodeEnrichmentProvider,
)
from service.processing.worker import harness_enrichment_provider_from_environment
from service.processing.model_provider import (
    DataBoundary,
    DeploymentClass,
    FakeModelProvider,
    InvocationErrorType,
    InvocationStatus,
    ModelMessage,
    ModelProfile,
    ModelProviderError,
    ModelRequest,
    PromptProfile,
    StepAttemptContext,
)
from service.sources import RightsClassification


def _profile() -> ModelProfile:
    return ModelProfile(
        profile_id="demo-extractor",
        version="1.0.0",
        provider="harness",
        model="fake.cli@0.1.0",
        deployment_class="external_api",
        secret_ref="env://KNOWLEDGE_DEMO_SECRET",
        allowed_data_boundaries={DataBoundary.ENTERPRISE_PROVIDER_ONLY},
        capabilities={"structured_generation"},
        timeout_seconds=30,
    )


def _prompt() -> PromptProfile:
    return PromptProfile(
        profile_id="atomic-candidate",
        version="1.0.0",
        system_template="Extract one evidence-grounded knowledge candidate.",
        output_schema_id="knowledge-candidate.v1",
        output_schema=enrichment_mod.ENRICHMENT_OUTPUT_SCHEMA,
    )


def _attempt() -> StepAttemptContext:
    return StepAttemptContext(
        run_id="run-sdtm-demo",
        step_id="step-enrichment",
        attempt_id="attempt-enrichment-1",
        attempt_number=1,
        previous_attempt_id=None,
    )


def _request() -> ModelRequest:
    return ModelRequest(
        attempt=_attempt(),
        model_profile=_profile(),
        prompt_profile=_prompt(),
        data_boundary=DataBoundary.ENTERPRISE_PROVIDER_ONLY,
        messages=(
            ModelMessage(role="user", content='{"evidence": [{"id": "ev-1"}]}'),
        ),
    )


_CANDIDATE_OUTPUT = {
    "candidate_group_id": "sdtm.ae.aeseq.definition",
    "knowledge_type": "definition",
    "claim": "AESEQ is the sequence identifier within the AE domain.",
    "scope": {"domain": "AE"},
    "applicability": {"population": "all"},
    "conditions": [],
    "exceptions": [],
    "evidence_ids": ["evidence-aeseq"],
    "relation_proposals": [],
    "advisory_signals": [],
    "confidence": 0.9,
}


def _service_payload() -> dict:
    """Exact payload HarnessEnrichmentProvider builds for the request that
    EnrichmentWorkerService constructs via build_enrichment_model_request."""
    content = json.dumps(
        {
            "source_version_id": "srcv-sdtm-demo",
            "evidence": [
                {
                    "evidence_id": "evidence-aeseq",
                    "locator": {"section": "AE"},
                    "content_sha256": "a" * 64,
                    "content": "AESEQ is the sequence identifier.",
                }
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "messages": [{"role": "user", "content": content}],
        "evidence_boundary": "enterprise_provider_only",
    }


def _replay_adapter(
    tmp_path: Path,
    *,
    status: HarnessStatus = HarnessStatus.SUCCEEDED,
    payload: dict | None = None,
) -> ReplayHarnessAdapter:
    payload = payload if payload is not None else {
        "messages": [
            {"role": "user", "content": '{"evidence": [{"id": "ev-1"}]}'}
        ],
        "evidence_boundary": "enterprise_provider_only",
    }
    key = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    result = HarnessResult(
        status=status,
        exit_code=0 if status is HarnessStatus.SUCCEEDED else 1,
        message="" if status is HarnessStatus.SUCCEEDED else f"{status.value} from fixture",
        output_path=None,
        output_sha256=(
            None
            if status is not HarnessStatus.SUCCEEDED
            else hashlib.sha256(
                json.dumps(_CANDIDATE_OUTPUT, sort_keys=True).encode("utf-8")
            ).hexdigest()
        ),
    )
    records_path = tmp_path / "records.json"
    records_path.write_text(
        json.dumps(
            ReplayFixture(
                records=(
                    ReplayRecord(
                        input_sha256=key,
                        events=(),
                        result=result,
                        output=(
                            _CANDIDATE_OUTPUT
                            if status is HarnessStatus.SUCCEEDED
                            else None
                        ),
                    ),
                )
            ).model_dump(mode="json")
        ),
        encoding="utf-8",
    )
    return ReplayHarnessAdapter(records_path)


def test_replay_invoke_returns_succeeded_invocation(tmp_path: Path) -> None:
    provider = HarnessEnrichmentProvider(adapter=_replay_adapter(tmp_path))
    invocation = provider.invoke(_request())
    assert invocation.status is InvocationStatus.REPLAYED
    assert invocation.provider == "harness"
    assert invocation.model == "replay.cli@0.1.0"
    assert invocation.output == _CANDIDATE_OUTPUT
    assert invocation.output_sha256 == hashlib.sha256(
        json.dumps(_CANDIDATE_OUTPUT, sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert invocation.latency_ms >= 0


def test_failed_fixture_returns_failed_invocation(tmp_path: Path) -> None:
    provider = HarnessEnrichmentProvider(
        adapter=_replay_adapter(tmp_path, status=HarnessStatus.FAILED)
    )
    invocation = provider.invoke(_request())
    assert invocation.status is InvocationStatus.FAILED
    assert invocation.error_type is InvocationErrorType.PROVIDER_ERROR
    assert "fixture" in (invocation.error_message or "")
    assert invocation.output is None


def test_timed_out_fixture_maps_to_timeout_error(tmp_path: Path) -> None:
    provider = HarnessEnrichmentProvider(
        adapter=_replay_adapter(tmp_path, status=HarnessStatus.TIMED_OUT)
    )
    invocation = provider.invoke(_request())
    assert invocation.status is InvocationStatus.FAILED
    assert invocation.error_type is InvocationErrorType.TIMEOUT


def _opencode_provider(tmp_path: Path, *, output: dict | None = None):
    events = ""
    if output is not None:
        events = json.dumps(
            {"type": "text", "data": {"text": json.dumps(output)}}
        ) + "\n"
    runtime = FakeContainerRuntime(
        exit_code=0,
        staged_outputs={tmp_path / "events.jsonl": events.encode("utf-8")},
    )
    workspaces: list[Path] = []

    def observe_workspace(path: Path) -> None:
        workspaces.append(path)

    provider = SupervisedOpenCodeEnrichmentProvider(
        supervisor=HarnessSupervisor(runtime=runtime),
        image_ref=(
            "ghcr.io/anomalyco/opencode:1.18.14@sha256:"
            + "f" * 64
        ),
        spec_sha256="a" * 64,
        secret_resolver=lambda reference: "synthetic-test-secret",
        environment=(("OPENCODE_DISABLE_MODELS_FETCH", "1"),),
        workspace_observer=observe_workspace,
    )
    return provider, runtime, workspaces


def test_checked_in_pack_schema_matches_enrichment_product_contract() -> None:
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "harness-packs"
        / "knowledge-candidate-v1"
        / "schemas"
        / "candidate.schema.json"
    )
    pack_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    pack_schema.pop("$schema")

    assert pack_schema == enrichment_mod.ENRICHMENT_OUTPUT_SCHEMA


def _supervised_request() -> ModelRequest:
    request = _request()
    profile = request.model_profile.model_copy(
        update={
            "provider": "openai",
            "model": "gpt-test",
            "deployment_class": DeploymentClass.ENTERPRISE_MANAGED,
        }
    )
    canonical_content = _service_payload()["messages"][0]["content"]
    return request.model_copy(
        update={
            "model_profile": profile,
            "messages": (ModelMessage(role="user", content=canonical_content),),
        }
    )


def test_supervised_opencode_invocation_validates_and_attaches_receipts(tmp_path: Path) -> None:
    provider, runtime, workspaces = _opencode_provider(
        tmp_path,
        output=_CANDIDATE_OUTPUT,
    )

    request = _supervised_request()
    invocation = provider.invoke(request)

    assert invocation.status is InvocationStatus.SUCCEEDED
    assert invocation.output == _CANDIDATE_OUTPUT
    assert invocation.execution_receipt is not None
    assert invocation.execution_receipt["status"] == "succeeded"
    assert invocation.validation_receipt is not None
    assert invocation.validation_receipt["result"] == "passed"
    assert runtime.last_config is not None
    assert runtime.last_config.entrypoint == ("/bin/sh", "-c")
    assert dict(runtime.last_config.environment)["XDG_CONFIG_HOME"] == "/scratch/config"
    assert any(
        mount.container_path == "/harness/mcp_stdio_bridge.sh"
        for mount in runtime.last_config.read_only_inputs
    )
    assert any(
        mount.container_path == "/harness/mcp-bundle.json"
        for mount in runtime.last_config.read_only_inputs
    )
    command = " ".join(runtime.last_config.command)
    assert "synthetic-test-secret" not in command
    assert request.messages[0].content not in command
    assert workspaces and not workspaces[0].exists()


def test_supervised_opencode_invalid_output_fails_with_validation_receipt(tmp_path: Path) -> None:
    invalid_output = {"claim": "missing required fields"}
    provider, _, workspaces = _opencode_provider(
        tmp_path,
        output=invalid_output,
    )

    with pytest.raises(ModelProviderError) as caught:
        provider.invoke(_supervised_request())

    invocation = caught.value.invocation
    assert invocation.status is InvocationStatus.FAILED
    assert invocation.error_type is InvocationErrorType.STRUCTURED_OUTPUT_INVALID
    assert invocation.execution_receipt is not None
    assert invocation.validation_receipt is not None
    assert invocation.validation_receipt["result"] == "failed"
    assert invocation.validation_receipt["input_sha256"] == hashlib.sha256(
        json.dumps(
            invalid_output,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert workspaces and not workspaces[0].exists()


class SuccessfulSupervisorTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object] | None, dict[str, str]]] = []
        self.request_sha256 = ""

    def __call__(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, object]]:
        self.calls.append((method, path, payload, headers))
        if path == "/v1/attempts":
            assert payload is not None
            self.request_sha256 = hashlib.sha256(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            return 202, {
                "contract_version": "1.0.0",
                "attempt_id": "attempt-enrichment-1",
                "request_sha256": self.request_sha256,
                "state": "accepted",
                "receipt": None,
            }
        if path.endswith("/heartbeat"):
            return 200, {
                "contract_version": "1.0.0",
                "attempt_id": "attempt-enrichment-1",
                "request_sha256": self.request_sha256,
                "state": "running",
                "receipt": None,
            }
        if path.endswith("/result"):
            receipt = ExecutionReceipt(
                execution_id="exec-attempt-enrichment-1",
                spec_sha256="a" * 64,
                request_sha256=self.request_sha256,
                harness_id="opencode@1.18.14",
                adapter_id="opencode@1.18.14",
                status=HarnessStatus.SUCCEEDED,
                exit_classification=ExitClassification.SUCCEEDED,
                exit_code=0,
                started_at="2026-08-09T12:00:00Z",
                ended_at="2026-08-09T12:00:01Z",
                artifact_manifest=ArtifactManifest(),
            ).model_dump(mode="json")
            return 200, {
                "contract_version": "1.0.0",
                "attempt_id": "attempt-enrichment-1",
                "request_sha256": self.request_sha256,
                "receipt": receipt,
                "output_sha256": hashlib.sha256(
                    json.dumps(
                        _CANDIDATE_OUTPUT,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
                "output_bundle": _CANDIDATE_OUTPUT,
            }
        return 200, {
            "contract_version": "1.0.0",
            "attempt_id": "attempt-enrichment-1",
            "request_sha256": self.request_sha256,
            "state": "succeeded",
            "receipt": None,
        }


def test_remote_supervisor_provider_sends_only_product_attempt_and_validates_output() -> None:
    transport = SuccessfulSupervisorTransport()
    provider = RemoteSupervisorEnrichmentProvider(
        supervisor_url="http://harness-supervisor:8790",
        machine_token="internal-supervisor-token",
        spec_sha256="a" * 64,
        transport=transport,
        sleep=lambda _seconds: None,
    )

    invocation = provider.invoke(_supervised_request())

    assert invocation.status is InvocationStatus.SUCCEEDED
    assert invocation.output == _CANDIDATE_OUTPUT
    assert invocation.execution_receipt is not None
    assert invocation.validation_receipt is not None
    submitted = transport.calls[0][2]
    assert submitted is not None
    assert submitted["contract_version"] == "1.0.0"
    assert submitted["adapter_id"] == "opencode@1.18.14"
    assert submitted["network_mode"] == "none"
    assert submitted["network_policy_id"] == "none"
    assert submitted["secret_refs"] == ["env://KNOWLEDGE_DEMO_SECRET"]
    assert submitted["input_bundle"]["provider"] == "openai"
    assert submitted["input_bundle"]["model"] == "gpt-test"
    assert submitted["input_bundle"]["evidence"] == [
        {
            "evidence_id": "evidence-aeseq",
            "locator": {"section": "AE"},
            "content_sha256": "a" * 64,
            "content": "AESEQ is the sequence identifier.",
        }
    ]
    assert not ({"image_ref", "command", "mounts", "environment"} & submitted.keys())
    assert "internal-supervisor-token" not in json.dumps(submitted)
    assert transport.calls[0][3]["Authorization"] == "Bearer internal-supervisor-token"
    assert [call[1] for call in transport.calls] == [
        "/v1/attempts",
        "/v1/attempts/attempt-enrichment-1/heartbeat",
        "/v1/attempts/attempt-enrichment-1",
        "/v1/attempts/attempt-enrichment-1/result",
    ]


def test_remote_supervisor_provider_sends_hash_locked_pack_ref_only() -> None:
    transport = SuccessfulSupervisorTransport()
    provider = RemoteSupervisorEnrichmentProvider(
        supervisor_url="http://harness-supervisor:8790",
        machine_token="internal-supervisor-token",
        spec_sha256="a" * 64,
        instruction_ref={
            "pack_id": "knowledge-candidate-v1",
            "version": "1.0.0",
            "sha256": "c" * 64,
        },
        transport=transport,
        sleep=lambda _seconds: None,
    )

    provider.invoke(_supervised_request())

    submitted = transport.calls[0][2]
    assert submitted is not None
    assert submitted["instruction_ref"] == {
        "pack_id": "knowledge-candidate-v1",
        "version": "1.0.0",
        "sha256": "c" * 64,
    }
    serialized = json.dumps(submitted, sort_keys=True)
    assert '"skills"' not in serialized
    assert '"opencode_config"' not in serialized
    assert '"mcp_command"' not in serialized


def test_remote_provider_validates_pack_ref_without_harness_runtime_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = builtins.__import__

    def isolated_import(name, *args, **kwargs):  # type: ignore[no-untyped-def]
        if name == "contracts.spec":
            raise ModuleNotFoundError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", isolated_import)
    provider = RemoteSupervisorEnrichmentProvider(
        supervisor_url="http://harness-supervisor:8790",
        machine_token="internal-supervisor-token",
        spec_sha256="a" * 64,
        instruction_ref={
            "pack_id": "knowledge-candidate-v1",
            "version": "1.0.0",
            "sha256": "c" * 64,
        },
        transport=SuccessfulSupervisorTransport(),
        sleep=lambda _seconds: None,
    )

    assert provider._instruction_ref["pack_id"] == "knowledge-candidate-v1"


class InvalidOutputSupervisorTransport(SuccessfulSupervisorTransport):
    def __call__(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, object]]:
        status_code, response = super().__call__(method, path, payload, headers)
        if path.endswith("/result"):
            invalid_output = {"claim": "missing required fields"}
            response["output_bundle"] = invalid_output
            response["output_sha256"] = hashlib.sha256(
                json.dumps(
                    invalid_output,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
        return status_code, response


def test_remote_supervisor_provider_revalidates_untrusted_output() -> None:
    provider = RemoteSupervisorEnrichmentProvider(
        supervisor_url="http://harness-supervisor:8790",
        machine_token="internal-supervisor-token",
        spec_sha256="a" * 64,
        transport=InvalidOutputSupervisorTransport(),
        sleep=lambda _seconds: None,
    )

    with pytest.raises(ModelProviderError) as caught:
        provider.invoke(_supervised_request())

    invocation = caught.value.invocation
    assert invocation.error_type is InvocationErrorType.STRUCTURED_OUTPUT_INVALID
    assert invocation.execution_receipt is not None
    assert invocation.validation_receipt is not None
    assert invocation.validation_receipt["result"] == "failed"


def test_worker_builds_remote_supervisor_provider_without_image_or_model_secret() -> None:
    provider = harness_enrichment_provider_from_environment(
        {
            "KNOWLEDGE_ENRICHMENT_PROVIDER_MODE": "harness",
            "KNOWLEDGE_HARNESS_EXECUTION_MODE": "opencode-remote",
            "KNOWLEDGE_HARNESS_SUPERVISOR_URL": "http://harness-supervisor:8790",
            "KNOWLEDGE_HARNESS_SUPERVISOR_TOKEN_REF": "env://SUPERVISOR_MACHINE_TOKEN",
            "SUPERVISOR_MACHINE_TOKEN": "internal-supervisor-token",
            "KNOWLEDGE_HARNESS_SPEC_SHA256": "a" * 64,
            "KNOWLEDGE_HARNESS_PACK_ID": "knowledge-candidate-v1",
            "KNOWLEDGE_HARNESS_PACK_VERSION": "1.0.0",
            "KNOWLEDGE_HARNESS_PACK_SHA256": "c" * 64,
        }
    )

    assert isinstance(provider, RemoteSupervisorEnrichmentProvider)
    assert provider._instruction_ref == {
        "pack_id": "knowledge-candidate-v1",
        "version": "1.0.0",
        "sha256": "c" * 64,
    }


def test_worker_supervised_mode_rejects_partial_pack_identity() -> None:
    with pytest.raises(RuntimeError, match="must be configured together"):
        harness_enrichment_provider_from_environment(
            {
                "KNOWLEDGE_ENRICHMENT_PROVIDER_MODE": "harness",
                "KNOWLEDGE_HARNESS_EXECUTION_MODE": "opencode-supervised",
                "KNOWLEDGE_HARNESS_SUPERVISOR_URL": "http://harness-supervisor:8790",
                "KNOWLEDGE_HARNESS_SUPERVISOR_TOKEN_REF": (
                    "env://SUPERVISOR_MACHINE_TOKEN"
                ),
                "SUPERVISOR_MACHINE_TOKEN": "internal-supervisor-token",
                "KNOWLEDGE_HARNESS_SPEC_SHA256": "a" * 64,
                "KNOWLEDGE_HARNESS_PACK_ID": "knowledge-candidate-v1",
            }
        )


class NeverCompletesSupervisorTransport(SuccessfulSupervisorTransport):
    def __call__(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, object]]:
        if path == "/v1/attempts":
            return super().__call__(method, path, payload, headers)
        self.calls.append((method, path, payload, headers))
        projection: dict[str, object] = {
            "contract_version": "1.0.0",
            "attempt_id": "attempt-enrichment-1",
            "request_sha256": self.request_sha256,
            "state": "running",
            "receipt": None,
        }
        if path.endswith("/cancel"):
            projection["state"] = "cancelled"
        if path.endswith("/result"):
            receipt = ExecutionReceipt(
                execution_id="exec-attempt-enrichment-1",
                spec_sha256="a" * 64,
                request_sha256=self.request_sha256,
                harness_id="opencode@1.18.14",
                adapter_id="opencode@1.18.14",
                status=HarnessStatus.CANCELLED,
                exit_classification=ExitClassification.CANCELLED,
                started_at="2026-08-09T12:00:00Z",
                ended_at="2026-08-09T12:00:01Z",
                artifact_manifest=ArtifactManifest(),
            ).model_dump(mode="json")
            return 200, {
                "contract_version": "1.0.0",
                "attempt_id": "attempt-enrichment-1",
                "request_sha256": self.request_sha256,
                "receipt": receipt,
                "output_sha256": None,
                "output_bundle": None,
            }
        return 200, projection


class CompletesDuringTimeoutReceiptGraceTransport(SuccessfulSupervisorTransport):
    def __init__(self) -> None:
        super().__init__()
        self.status_polls = 0

    def __call__(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, object]]:
        if path == "/v1/attempts":
            return super().__call__(method, path, payload, headers)
        self.calls.append((method, path, payload, headers))
        if method == "GET" and path.endswith("attempt-enrichment-1"):
            self.status_polls += 1
        state = "timed_out" if self.status_polls >= 3 else "running"
        if path.endswith("/result"):
            receipt = ExecutionReceipt(
                execution_id="exec-attempt-enrichment-1",
                spec_sha256="a" * 64,
                request_sha256=self.request_sha256,
                harness_id="opencode@1.18.14",
                adapter_id="opencode@1.18.14",
                status=HarnessStatus.TIMED_OUT,
                exit_classification=ExitClassification.TIMED_OUT,
                started_at="2026-08-09T12:00:00Z",
                ended_at="2026-08-09T12:00:01Z",
                artifact_manifest=ArtifactManifest(),
                retryable=False,
            ).model_dump(mode="json")
            return 200, {
                "contract_version": "1.0.0",
                "attempt_id": "attempt-enrichment-1",
                "request_sha256": self.request_sha256,
                "receipt": receipt,
                "output_sha256": None,
                "output_bundle": None,
            }
        return 200, {
            "contract_version": "1.0.0",
            "attempt_id": "attempt-enrichment-1",
            "request_sha256": self.request_sha256,
            "state": state,
            "receipt": None,
        }


def test_remote_supervisor_provider_cancels_when_poll_budget_expires() -> None:
    transport = NeverCompletesSupervisorTransport()
    provider = RemoteSupervisorEnrichmentProvider(
        supervisor_url="http://harness-supervisor:8790",
        machine_token="internal-supervisor-token",
        spec_sha256="a" * 64,
        transport=transport,
        poll_interval_seconds=1,
        sleep=lambda _seconds: None,
    )
    request = _supervised_request()
    profile = request.model_profile.model_copy(update={"timeout_seconds": 1})

    with pytest.raises(ModelProviderError) as caught:
        provider.invoke(request.model_copy(update={"model_profile": profile}))

    assert caught.value.invocation.error_type is InvocationErrorType.TIMEOUT
    assert any(path.endswith("/cancel") for _, path, _, _ in transport.calls)


def test_remote_supervisor_provider_waits_for_terminal_timeout_receipt_before_cancel() -> None:
    transport = CompletesDuringTimeoutReceiptGraceTransport()
    provider = RemoteSupervisorEnrichmentProvider(
        supervisor_url="http://harness-supervisor:8790",
        machine_token="internal-supervisor-token",
        spec_sha256="a" * 64,
        transport=transport,
        poll_interval_seconds=1,
        sleep=lambda _seconds: None,
    )
    request = _supervised_request()
    profile = request.model_profile.model_copy(update={"timeout_seconds": 1})

    with pytest.raises(ModelProviderError) as caught:
        provider.invoke(request.model_copy(update={"model_profile": profile}))

    assert caught.value.invocation.error_type is InvocationErrorType.TIMEOUT
    assert caught.value.invocation.execution_receipt["status"] == "timed_out"
    assert not any(path.endswith("/cancel") for _, path, _, _ in transport.calls)


def test_worker_supervised_mode_uses_remote_supervisor_without_docker_inputs() -> None:
    provider = harness_enrichment_provider_from_environment(
        {
            "KNOWLEDGE_ENRICHMENT_PROVIDER_MODE": "harness",
            "KNOWLEDGE_HARNESS_EXECUTION_MODE": "opencode-supervised",
            "KNOWLEDGE_HARNESS_SUPERVISOR_URL": "http://harness-supervisor:8790",
            "KNOWLEDGE_HARNESS_SUPERVISOR_TOKEN_REF": "env://SUPERVISOR_MACHINE_TOKEN",
            "SUPERVISOR_MACHINE_TOKEN": "internal-supervisor-token",
            "KNOWLEDGE_HARNESS_SPEC_SHA256": "a" * 64,
        }
    )

    assert isinstance(provider, RemoteSupervisorEnrichmentProvider)


def test_worker_supervised_mode_requires_supervisor_endpoint_and_spec_hash() -> None:
    with pytest.raises(RuntimeError, match="KNOWLEDGE_HARNESS_SUPERVISOR_URL"):
        harness_enrichment_provider_from_environment(
            {
                "KNOWLEDGE_ENRICHMENT_PROVIDER_MODE": "harness",
                "KNOWLEDGE_HARNESS_EXECUTION_MODE": "opencode-supervised",
            }
        )


def test_real_opencode_container_attempt_fails_closed_offline(tmp_path: Path) -> None:
    docker = pytest.importorskip("docker")
    manifest = json.loads(
        (_HARNESS_RUNTIME_ROOT / "images" / "opencode-1.18.14.json").read_text(
            encoding="utf-8"
        )
    )
    try:
        client = docker.from_env()
        client.ping()
        client.images.get(manifest["image_ref"])
    except Exception as exc:
        pytest.skip(f"Docker/OpenCode image unavailable: {exc}")
    from supervisor.docker_runtime import DockerEngineContainerRuntime

    workspaces: list[Path] = []
    provider = SupervisedOpenCodeEnrichmentProvider(
        supervisor=HarnessSupervisor(
            runtime=DockerEngineContainerRuntime(client=client)
        ),
        image_ref=manifest["image_ref"],
        spec_sha256="a" * 64,
        secret_resolver=lambda reference: "synthetic-offline-secret",
        environment=tuple(manifest["environment"].items()),
        workspace_observer=workspaces.append,
    )
    request = _supervised_request()
    profile = request.model_profile.model_copy(
        update={"provider": "admission", "model": "invalid"}
    )

    with pytest.raises(ModelProviderError) as caught:
        provider.invoke(request.model_copy(update={"model_profile": profile}))

    invocation = caught.value.invocation
    assert invocation.status is InvocationStatus.FAILED
    assert invocation.execution_receipt is not None
    assert invocation.execution_receipt["image_ref"] == manifest["image_ref"]
    assert "synthetic-offline-secret" not in json.dumps(invocation.execution_receipt)
    assert workspaces and not workspaces[0].exists()


def test_harness_claim_dispatches_to_harness_provider(tmp_path: Path) -> None:
    """executor_kind=harness claim must use the harness provider; the default
    provider stays untouched (direct_model / replay)."""
    harness_provider = HarnessEnrichmentProvider(
        adapter=_replay_adapter(tmp_path, payload=_service_payload())
    )
    governance = KnowledgeGovernanceService(
        repository=InMemoryGovernanceRepository(
            runs={"run-sdtm-demo": "processing"},
            evidence_ids={"evidence-aeseq"},
            knowledge_unit_ids={"ku-sdtm-ae"},
        )
    )
    repository = enrichment_mod.InMemoryEnrichmentRepository(
        contexts={
            "run-sdtm-demo": enrichment_mod.EnrichmentContext(
                run_id="run-sdtm-demo",
                source_version_id="srcv-sdtm-demo",
                data_boundary=DataBoundary.ENTERPRISE_PROVIDER_ONLY,
                evidence=(
                    enrichment_mod.EnrichmentEvidence(
                        reference=EvidenceReference(
                            evidence_id="evidence-aeseq",
                            source_version_id="srcv-sdtm-demo",
                            locator={"section": "AE"},
                            content_sha256="a" * 64,
                            rights={
                                "classification": RightsClassification.LICENSED,
                                "storage_allowed": True,
                                "citation_required": True,
                            },
                        ),
                        content="AESEQ is the sequence identifier.",
                    ),
                ),
            )
        }
    )
    default_provider = FakeModelProvider(output={**_CANDIDATE_OUTPUT, "claim": "default"})
    service = enrichment_mod.EnrichmentWorkerService(
        repository=repository,
        governance=governance,
        provider=default_provider,
        model_profile=_profile(),
        prompt_profile=_prompt(),
        actor=_enrichment_actor(),
        harness_provider=harness_provider,
    )
    claim = ClaimedStepAttempt(
        run_id="run-sdtm-demo",
        step_id="step-enrichment",
        step_key="enrichment.extract_candidate",
        pool=WorkerPool.ENRICHMENT,
        attempt_id="attempt-enrichment-1",
        attempt_number=1,
        previous_attempt_id=None,
        input_sha256="f" * 64,
        executor_kind=ExecutorKind.HARNESS.value,
    )
    outcome = service.extract_candidate(claim)
    assert outcome.output_sha256
    assert repository.invocations[0].provider == "harness"
    assert repository.invocations[0].output == _CANDIDATE_OUTPUT


def _enrichment_actor() -> ActorContext:
    return ActorContext(
        actor_id="svc-enrichment",
        display_name="Enrichment Worker",
        principal_type=PrincipalType.SERVICE_ACCOUNT,
        roles=frozenset({ProductRole.SERVICE_ACCOUNT}),
        permissions=frozenset(
            {
                Permission.EVIDENCE_READ,
                Permission.MODEL_INVOKE,
                Permission.CANDIDATE_WRITE,
                Permission.RELATION_PROPOSE,
                Permission.PROCESSING_EXECUTE,
            }
        ),
        worker_pool=WorkerPool.ENRICHMENT,
    )
