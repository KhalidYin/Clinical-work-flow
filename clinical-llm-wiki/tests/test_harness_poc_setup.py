from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest


def test_poc_profile_is_internal_mock_only() -> None:
    from service.processing.harness_poc_setup import poc_model_profile_values

    values = poc_model_profile_values()

    assert values["provider"] == "openai"
    assert values["model"] == "gpt-4o-mini"
    assert values["deployment_class"] == "enterprise_managed"
    assert values["secret_ref"] == "env://SYNTHETIC_PROVIDER_KEY"
    assert values["cost_policy"] == {
        "mode": "p15_internal_mock",
        "network": "internal-only",
    }
    assert values["timeout_seconds"] == 30
    assert poc_model_profile_values(timeout_seconds=1)["timeout_seconds"] == 1

    with pytest.raises(ValueError, match="timeout"):
        poc_model_profile_values(timeout_seconds=0)


def test_setup_changes_only_a_queued_unleased_enrichment_step() -> None:
    from service.processing.harness_poc_setup import configure_step_for_harness

    queued = SimpleNamespace(
        step_key="enrichment.extract_candidate",
        status="queued",
        executor_kind="direct_model",
    )
    configure_step_for_harness(queued, attempt_status="queued")
    assert queued.executor_kind == "harness"

    terminal = SimpleNamespace(
        step_key="enrichment.extract_candidate",
        status="succeeded",
        executor_kind="direct_model",
    )
    with pytest.raises(RuntimeError, match="queued"):
        configure_step_for_harness(terminal, attempt_status="succeeded")

    wrong_step = SimpleNamespace(
        step_key="document.persist_evidence",
        status="queued",
        executor_kind="deterministic_handler",
    )
    with pytest.raises(RuntimeError, match="enrichment"):
        configure_step_for_harness(wrong_step, attempt_status="queued")


def test_api_verifier_requires_candidate_evidence_and_invocation_lineage() -> None:
    from service.processing.harness_poc_verify import validate_api_candidate

    summary = {
        "candidateId": "cand-p15-001",
        "candidateGroupId": "candidate-poc-001",
        "status": "author_confirmation_required",
        "evidenceCount": 1,
    }
    detail = {
        **summary,
        "originModelInvocationId": "inv-p15-001",
        "evidence": [{"evidenceId": "evidence-p15-001"}],
    }

    assert validate_api_candidate(summary=summary, detail=detail) == {
        "candidate_id": "cand-p15-001",
        "evidence_id": "evidence-p15-001",
        "origin_model_invocation_id": "inv-p15-001",
        "status": "author_confirmation_required",
    }

    with pytest.raises(RuntimeError, match="author confirmation"):
        validate_api_candidate(
            summary={**summary, "status": "author_confirmed"},
            detail=detail,
        )


def test_loop_verifier_requires_one_canonical_receipted_lineage() -> None:
    from service.processing.harness_poc_verify import validate_loop_snapshot

    pack_sha256 = "d" * 64
    api_candidate = {
        "candidate_id": "cand-p15-001",
        "evidence_id": "evidence-p15-001",
        "origin_model_invocation_id": "inv-p15-001",
        "status": "author_confirmation_required",
    }
    snapshot = {
        "run_id": "run-p15-001",
        "run_status": "author_confirmation_required",
        "step_status": "succeeded",
        "attempt_id": "attempt-p15-001",
        "attempt_status": "succeeded",
        "invocation_id": "inv-p15-001",
        "invocation_status": "succeeded",
        "provider_request_id": "execution-p15-001",
        "candidate_id": "cand-p15-001",
        "candidate_status": "author_confirmation_required",
        "candidate_origin_model_invocation_id": "inv-p15-001",
        "evidence_ids": ["evidence-p15-001"],
        "counts": {
            "attempts": 1,
            "model_invocations": 1,
            "candidates": 1,
            "candidate_evidence": 1,
        },
        "execution_receipt": {
            "execution_id": "execution-p15-001",
            "status": "succeeded",
            "exit_classification": "succeeded",
            "pack_identity": {
                "pack_id": "knowledge-candidate-v1",
                "version": "1.0.0",
                "sha256": pack_sha256,
            },
            "advertised_skills": ["evidence-candidate"],
            "allowed_mcp_capabilities": ["knowledge.read-evidence"],
            "tool_call_summary": [{"tool": "read_evidence", "calls": 1}],
            "network_policy": {
                "policy_id": "none",
                "kind": "none",
                "allowed_endpoints": [],
            },
            "retryable": False,
        },
        "validation_receipt": {
            "result": "passed",
        },
    }

    assert validate_loop_snapshot(
        snapshot=snapshot,
        api_candidate=api_candidate,
        expected_pack_sha256=pack_sha256,
    ) == {
        "attempt_id": "attempt-p15-001",
        "candidate_id": "cand-p15-001",
        "evidence_id": "evidence-p15-001",
        "model_invocation_id": "inv-p15-001",
        "run_id": "run-p15-001",
        "status": "author_confirmation_required",
        "counts": snapshot["counts"],
        "receipt": {
            "network_policy_id": "none",
            "pack_sha256": pack_sha256,
            "skill": "evidence-candidate",
            "mcp_tool": "read_evidence",
            "validation": "passed",
        },
    }

    with pytest.raises(RuntimeError, match="exactly one model invocation"):
        validate_loop_snapshot(
            snapshot={
                **snapshot,
                "counts": {**snapshot["counts"], "model_invocations": 2},
            },
            api_candidate=api_candidate,
            expected_pack_sha256=pack_sha256,
        )

    with pytest.raises(RuntimeError, match="network policy"):
        validate_loop_snapshot(
            snapshot={
                **snapshot,
                "execution_receipt": {
                    **snapshot["execution_receipt"],
                    "network_policy": {
                        "policy_id": "model-deepseek-v1",
                        "kind": "model_endpoint",
                        "allowed_endpoints": ["api.deepseek.com:443"],
                    },
                },
            },
            api_candidate=api_candidate,
            expected_pack_sha256=pack_sha256,
        )


def test_loop_runner_uses_fresh_internal_mock_environment() -> None:
    from scripts.harness_poc_loop import (
        build_poc_environment,
        measure_pack,
        validate_replay_counts,
    )

    root = Path(__file__).resolve().parents[1]
    project_name = "clinical-harness-poc-test1234"
    environment = build_poc_environment(
        project_name=project_name,
        knowledge_root=root,
        secret_factory=lambda: "synthetic-generated-test-secret",
    )

    assert environment["HARNESS_PACK_SHA256"] == measure_pack(
        root / "harness-packs" / "knowledge-candidate-v1"
    )
    assert environment["HARNESS_P15_MODEL_NETWORK_NAME"] == (
        f"{project_name}-model"
    )
    assert environment["HARNESS_DEEPSEEK_CLIENT_NETWORK_NAME"] == (
        f"{project_name}-deepseek-client"
    )
    assert environment["HARNESS_SYNTHETIC_PROVIDER_KEY_FILE"].endswith(
        "p15-synthetic-provider-key.txt"
    )
    assert "DEEPSEEK_API_KEY" not in environment
    assert "KNOWLEDGE_MODEL_API_KEY" not in environment
    assert validate_replay_counts(first=3, second=3) == {
        "first_worker_mock_requests": 3,
        "second_worker_mock_requests": 3,
        "duplicate_mock_requests": 0,
    }
    with pytest.raises(RuntimeError, match="additional model requests"):
        validate_replay_counts(first=3, second=4)


def test_loop_runner_decodes_docker_output_as_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts.harness_poc_loop import PocLoopRunner

    observed: dict[str, object] = {}

    def fake_run(*_args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed.update(kwargs)
        return subprocess.CompletedProcess([], 0, "容器完成", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = PocLoopRunner(
        project_name="clinical-harness-poc-encoding",
        knowledge_root=Path(__file__).resolve().parents[1],
        environment={},
        build=False,
        keep=False,
    )

    result = runner._run(("ps",))

    assert result.stdout == "容器完成"
    assert observed["encoding"] == "utf-8"
    assert observed["errors"] == "replace"


@pytest.mark.parametrize(
    ("scenario", "error_type", "receipt_status", "validation"),
    [
        ("schema_invalid", "structured_output_invalid", "succeeded", "failed"),
        ("timeout", "timeout", "timed_out", None),
    ],
)
def test_failure_verifier_requires_one_failed_lineage_and_zero_candidate(
    scenario: str,
    error_type: str,
    receipt_status: str,
    validation: str | None,
) -> None:
    from service.processing.harness_poc_verify import validate_failure_snapshot

    pack_sha256 = "d" * 64
    snapshot = {
        "run_id": "run-p15-001",
        "run_status": "failed",
        "step_status": "failed",
        "attempt_id": "attempt-p15-001",
        "attempt_status": "failed",
        "attempt_error_type": error_type,
        "invocation_id": "inv-p15-001",
        "invocation_status": "failed",
        "invocation_error_type": error_type,
        "provider_request_id": "execution-p15-001",
        "candidate_id": None,
        "evidence_ids": [],
        "counts": {
            "attempts": 1,
            "model_invocations": 1,
            "candidates": 0,
            "candidate_evidence": 0,
        },
        "execution_receipt": {
            "execution_id": "execution-p15-001",
            "status": receipt_status,
            "exit_classification": receipt_status,
            "pack_identity": {
                "pack_id": "knowledge-candidate-v1",
                "version": "1.0.0",
                "sha256": pack_sha256,
            },
            "advertised_skills": ["evidence-candidate"],
            "allowed_mcp_capabilities": ["knowledge.read-evidence"],
            "tool_call_summary": (
                [{"tool": "read_evidence", "calls": 1}]
                if scenario == "schema_invalid"
                else []
            ),
            "network_policy": {
                "policy_id": "none",
                "kind": "none",
                "allowed_endpoints": [],
            },
            "retryable": False,
        },
        "validation_receipt": (
            {"result": validation, "findings": ["structured_output_invalid"]}
            if validation is not None
            else None
        ),
    }

    result = validate_failure_snapshot(
        snapshot=snapshot,
        expected_scenario=scenario,
        expected_pack_sha256=pack_sha256,
    )

    assert result["scenario"] == scenario
    assert result["error_type"] == error_type
    assert result["candidate_count"] == 0
    assert result["retryable"] is False

    with pytest.raises(RuntimeError, match="zero Candidate"):
        validate_failure_snapshot(
            snapshot={
                **snapshot,
                "counts": {**snapshot["counts"], "candidates": 1},
            },
            expected_scenario=scenario,
            expected_pack_sha256=pack_sha256,
        )


def test_failure_matrix_environment_never_carries_live_keys() -> None:
    from scripts.harness_poc_failure_matrix import build_scenario_environment

    schema = build_scenario_environment(
        base={"HARNESS_PACK_SHA256": "d" * 64},
        scenario="schema_invalid",
    )
    timeout = build_scenario_environment(
        base={"HARNESS_PACK_SHA256": "d" * 64},
        scenario="timeout",
    )

    assert schema["P15_MOCK_SCENARIO"] == "schema_invalid"
    assert schema["KNOWLEDGE_P15_MODEL_TIMEOUT_SECONDS"] == "30"
    assert timeout["P15_MOCK_SCENARIO"] == "timeout"
    assert timeout["P15_MOCK_DELAY_SECONDS"] == "30"
    assert timeout["KNOWLEDGE_P15_MODEL_TIMEOUT_SECONDS"] == "20"
    assert "DEEPSEEK_API_KEY" not in schema | timeout
    assert "KNOWLEDGE_MODEL_API_KEY" not in schema | timeout
