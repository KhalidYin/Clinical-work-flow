from __future__ import annotations

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
