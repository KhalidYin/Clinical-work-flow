"""P0/P1 POC runner API contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.application_api import ApplicationApiConfig, create_app
from src.application_api.poc_models import (
    PocActionType,
    PocActiveStep,
    PocHealthItem,
    PocHealthSeverity,
    PocNextAction,
    PocRunState,
    PocState,
    PocStep,
    PocStepKind,
    PocStepState,
)


ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = ROOT.parent
STUDIES_ROOT = PLATFORM_ROOT / "clinical-studies"
STUDY_ID = "SAMPLE-AE-001"


def _client() -> TestClient:
    return TestClient(
        create_app(ApplicationApiConfig(container_roots={"clinical-studies": STUDIES_ROOT}))
    )


def _minimal_state(run_state: PocRunState) -> PocState:
    return PocState(
        study_id=STUDY_ID,
        run_state=run_state,
        active_step=PocActiveStep(
            step_id="review-gate" if run_state is PocRunState.BLOCKED_REVIEW else "status",
            kind=PocStepKind.REVIEW
            if run_state is PocRunState.BLOCKED_REVIEW
            else PocStepKind.INSTRUCTION,
            title="合同状态",
        ),
        steps=[
            PocStep(
                step_id="source-intake",
                ordinal=1,
                title="Source Intake",
                state=PocStepState.DONE,
            ),
            PocStep(
                step_id="review-gate",
                ordinal=2,
                title="Review Gate",
                state=PocStepState.BLOCKED_REVIEW
                if run_state is PocRunState.BLOCKED_REVIEW
                else PocStepState.PENDING,
                kind=PocStepKind.REVIEW,
            ),
        ],
        next_actions=[
            PocNextAction(
                action_id=PocActionType.REFRESH,
                label="Refresh",
                enabled=True,
                method="GET",
                endpoint=f"/api/v1/studies/{STUDY_ID}/poc-state",
            )
        ],
        health=[
            PocHealthItem(
                check_id="contract",
                severity=PocHealthSeverity.OK,
                summary="contract payload validates",
            )
        ],
        partial_errors=(
            [{"code": "partial", "message": "partial data"}]
            if run_state is PocRunState.BLOCKED_ERROR
            else []
        ),
    )


@pytest.mark.parametrize(
    "run_state",
    [
        PocRunState.IDLE,
        PocRunState.RUNNING,
        PocRunState.BLOCKED_REVIEW,
        PocRunState.BLOCKED_ERROR,
        PocRunState.DONE,
    ],
)
def test_poc_state_contract_covers_ui_run_states(run_state: PocRunState) -> None:
    payload = _minimal_state(run_state).model_dump(mode="json")

    validated = PocState.model_validate(payload)

    assert validated.run_state is run_state
    assert validated.steps
    assert validated.next_actions[0].endpoint.endswith("/poc-state")
    if run_state is PocRunState.BLOCKED_ERROR:
        assert validated.partial_errors[0]["code"] == "partial"


def test_poc_state_contract_rejects_undeclared_ui_fields() -> None:
    payload = _minimal_state(PocRunState.IDLE).model_dump(mode="json")
    payload["absolute_path"] = str(STUDIES_ROOT)

    with pytest.raises(ValidationError):
        PocState.model_validate(payload)


def test_poc_state_route_exposes_workbench_payload_without_absolute_paths() -> None:
    response = _client().get(f"/api/v1/studies/{STUDY_ID}/poc-state")

    assert response.status_code == 200
    payload = response.json()
    validated = PocState.model_validate(payload)
    assert validated.study_id == STUDY_ID
    assert validated.target_artifact == "sdtm_ae_dataset"
    assert {step.step_id for step in validated.steps} >= {
        "source-intake",
        "sas-metadata",
        "minimum-information",
        "wiki-context",
        "mapping-spec",
        "review-gate",
    }
    assert {action.action_id for action in validated.next_actions} == {
        PocActionType.RUN_POC,
        PocActionType.RESUME,
        PocActionType.REFRESH,
        PocActionType.OPEN_OUTPUT_FOLDER,
    }
    assert validated.source["format"] == "sas7bdat"
    assert validated.knowledge["scope"] == "p9-poc-test-only"
    assert str(PLATFORM_ROOT) not in response.text


def test_poc_run_routes_are_contract_registered_but_not_executors_yet() -> None:
    client = _client()
    start = client.post(
        f"/api/v1/studies/{STUDY_ID}/poc-runs",
        json={"target_artifact": "sdtm_ae_dataset", "intent": "生成 AE POC"},
    )

    assert start.status_code == 202
    start_payload = start.json()
    assert start_payload["accepted"] is False
    assert start_payload["run_state"] == "blocked_error"
    assert start_payload["state_endpoint"].endswith("/poc-state")
    assert "P0/P2" in start_payload["message"]

    run = client.get(f"/api/v1/studies/{STUDY_ID}/poc-runs/{start_payload['run_id']}")
    assert run.status_code == 200
    assert run.json()["run_state"] == "blocked_error"

    resume = client.post(
        f"/api/v1/studies/{STUDY_ID}/poc-runs/{start_payload['run_id']}/resume",
        json={"reason": "operator_resume"},
    )
    assert resume.status_code == 202
    assert resume.json()["accepted"] is False

