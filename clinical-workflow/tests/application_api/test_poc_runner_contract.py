"""P0/P1 POC runner v2 API contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.application_api import ApplicationApiConfig, create_app
from src.application_api.poc_models import (
    PocActionType,
    PocActiveStep,
    PocBlocker,
    PocBlockerKind,
    PocHealthItem,
    PocHealthSeverity,
    PocInputCheck,
    PocInputCheckState,
    PocInputCheckSummary,
    PocNextAction,
    PocRecoveryAction,
    PocRunState,
    PocState,
    PocStep,
    PocStepKind,
    PocStepState,
    normalize_poc_run_state,
)


ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = ROOT.parent
STUDIES_ROOT = PLATFORM_ROOT / "clinical-studies"
KNOWLEDGE_FIXTURE = ROOT / "tests" / "fixtures" / "knowledge" / "sdtmig34-poc"
STUDY_ID = "SAMPLE-AE-001"
STEP_IDS = (
    "input-check",
    "minimum-information",
    "wiki-context",
    "mapping-spec",
    "program-execution",
    "validation-review",
    "canonical-ae",
)


def _client(container: Path = STUDIES_ROOT) -> TestClient:
    return TestClient(
        create_app(
            ApplicationApiConfig(
                container_roots={"clinical-studies": container},
                poc_knowledge_package_root=KNOWLEDGE_FIXTURE,
            )
        )
    )


def _minimal_container(tmp_path: Path) -> Path:
    container = tmp_path / "clinical-studies"
    study = container / STUDY_ID
    study.mkdir(parents=True)
    (study / "project.yaml").write_text('study_id: "SAMPLE-AE-001"\n', encoding="utf-8")
    return container


def _input_check(state: PocInputCheckState = PocInputCheckState.NOT_RUN) -> PocInputCheck:
    return PocInputCheck(
        summary=PocInputCheckSummary(
            status=state,
            required_total=1,
            required_ready=0,
            blocking_count=0,
            warning_count=0,
            message="Input Check contract fixture",
        )
    )


def _steps(
    *,
    active_step_id: str = "input-check",
    active_state: PocStepState = PocStepState.PENDING,
) -> list[PocStep]:
    return [
        PocStep(
            step_id=step_id,
            ordinal=ordinal,
            title=step_id,
            state=active_state if step_id == active_step_id else PocStepState.PENDING,
        )
        for ordinal, step_id in enumerate(STEP_IDS, start=1)
    ]


def _blocker(kind: PocBlockerKind, *, stage_id: str = "input-check") -> PocBlocker:
    recovery = {
        PocBlockerKind.INPUT: PocRecoveryAction.PROVIDE_INPUT,
        PocBlockerKind.VALIDATION: PocRecoveryAction.SUBMIT_REVIEW_DECISION,
        PocBlockerKind.REVIEW: PocRecoveryAction.SUBMIT_REVIEW_DECISION,
        PocBlockerKind.SYSTEM: PocRecoveryAction.RETRY_CURRENT_STEP,
    }[kind]
    return PocBlocker(
        kind=kind,
        stage_id=stage_id,
        code=f"{kind.value}_fixture",
        summary=f"{kind.value} blocker",
        detail="合同测试使用的结构化阻断详情。",
        affected_variables=["AETERM"] if kind is PocBlockerKind.VALIDATION else [],
        evidence_refs=["work/evidence.json"],
        recovery_action=recovery,
        review_id="review-fixture-001"
        if kind in {PocBlockerKind.REVIEW, PocBlockerKind.VALIDATION}
        else None,
        retryable=kind is PocBlockerKind.SYSTEM,
    )


def _minimal_state(
    run_state: PocRunState,
    *,
    blocker_kind: PocBlockerKind | None = None,
) -> PocState:
    blocker = _blocker(blocker_kind) if blocker_kind else None
    step_state = {
        PocRunState.IDLE: PocStepState.PENDING,
        PocRunState.RUNNING: PocStepState.RUNNING,
        PocRunState.BLOCKED: PocStepState.BLOCKED,
        PocRunState.DONE: PocStepState.DONE,
    }[run_state]
    active_step_id = "canonical-ae" if run_state is PocRunState.DONE else "input-check"
    steps = _steps(active_step_id=active_step_id, active_state=step_state)
    if run_state is PocRunState.DONE:
        for step in steps[:-1]:
            step.state = PocStepState.SKIPPED
    active_kind = (
        PocStepKind.REVIEW
        if blocker_kind is PocBlockerKind.REVIEW
        else PocStepKind.ERROR
        if blocker
        else PocStepKind.COMPLETE
        if run_state is PocRunState.DONE
        else PocStepKind.INSTRUCTION
    )
    return PocState(
        study_id=STUDY_ID,
        run_state=run_state,
        input_check=_input_check(),
        blocker=blocker,
        blocking_reason=blocker.summary if blocker else None,
        active_step=PocActiveStep(
            step_id=active_step_id,
            kind=active_kind,
            title="合同状态",
        ),
        steps=steps,
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
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("idle", PocRunState.IDLE),
        ("queued", PocRunState.RUNNING),
        ("running", PocRunState.RUNNING),
        ("blocked", PocRunState.BLOCKED),
        ("blocked_review", PocRunState.BLOCKED),
        ("blocked_error", PocRunState.BLOCKED),
        ("failed", PocRunState.BLOCKED),
        ("done", PocRunState.DONE),
        ("completed", PocRunState.DONE),
    ],
)
def test_legacy_run_states_normalize_to_v2(raw: str, expected: PocRunState) -> None:
    assert normalize_poc_run_state(raw) is expected


@pytest.mark.parametrize(
    ("run_state", "blocker_kind"),
    [
        (PocRunState.IDLE, None),
        (PocRunState.RUNNING, None),
        (PocRunState.BLOCKED, PocBlockerKind.INPUT),
        (PocRunState.BLOCKED, PocBlockerKind.VALIDATION),
        (PocRunState.BLOCKED, PocBlockerKind.REVIEW),
        (PocRunState.BLOCKED, PocBlockerKind.SYSTEM),
        (PocRunState.DONE, None),
    ],
)
def test_poc_state_contract_covers_v2_run_and_blocker_states(
    run_state: PocRunState,
    blocker_kind: PocBlockerKind | None,
) -> None:
    payload = _minimal_state(run_state, blocker_kind=blocker_kind).model_dump(mode="json")

    validated = PocState.model_validate(payload)

    assert validated.schema_version == "2.0"
    assert validated.run_state is run_state
    assert {step.state for step in validated.steps}.issubset(set(PocStepState))
    if blocker_kind:
        assert validated.blocker is not None
        assert validated.blocker.kind is blocker_kind
        assert validated.blocker.stage_id == validated.active_step.step_id


def test_poc_state_contract_rejects_blocker_ledger_mismatch() -> None:
    payload = _minimal_state(
        PocRunState.BLOCKED,
        blocker_kind=PocBlockerKind.VALIDATION,
    ).model_dump(mode="json")
    payload["blocker"]["stage_id"] = "validation-review"

    with pytest.raises(ValidationError, match="active_step must match"):
        PocState.model_validate(payload)


def test_poc_state_contract_rejects_undeclared_ui_fields() -> None:
    payload = _minimal_state(PocRunState.IDLE).model_dump(mode="json")
    payload["absolute_path"] = str(STUDIES_ROOT)

    with pytest.raises(ValidationError):
        PocState.model_validate(payload)


def test_poc_state_route_exposes_workbench_v2_payload_without_absolute_paths() -> None:
    response = _client().get(f"/api/v1/studies/{STUDY_ID}/poc-state")

    assert response.status_code == 200
    payload = response.json()
    validated = PocState.model_validate(payload)
    assert validated.study_id == STUDY_ID
    assert validated.target_artifact == "sdtm_ae_dataset"
    assert tuple(step.step_id for step in validated.steps) == STEP_IDS
    assert {action.action_id for action in validated.next_actions} == {
        PocActionType.RUN_POC,
        PocActionType.RETRY_CURRENT_STEP,
        PocActionType.OPEN_REVIEW,
        PocActionType.RESUME,
        PocActionType.REFRESH,
        PocActionType.OPEN_OUTPUT_FOLDER,
    }
    assert validated.source["format"] == "sas7bdat"
    assert validated.knowledge["scope"] == "p9-poc-test-only"
    assert {item.input_id: item.status.value for item in validated.input_check.dependencies}[
        "protocol"
    ] == "not_required"
    assert str(PLATFORM_ROOT) not in response.text


def test_artifacts_only_supplement_refs_and_do_not_mark_steps_done(tmp_path: Path) -> None:
    container = _minimal_container(tmp_path)
    study = container / STUDY_ID
    artifact = study / "output" / "sdtm" / "drafts" / "ae.csv"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("STUDYID,DOMAIN\nSAMPLE-AE-001,AE\n", encoding="utf-8")

    payload = _client(container).get(f"/api/v1/studies/{STUDY_ID}/poc-state").json()
    state = PocState.model_validate(payload)
    program_step = next(step for step in state.steps if step.step_id == "program-execution")

    assert state.run_state is PocRunState.IDLE
    assert program_step.state is PocStepState.PENDING
    assert program_step.artifact_refs


@pytest.mark.parametrize(
    ("legacy_state", "current_step", "expected_kind", "expected_stage"),
    [
        ("blocked_review", "mapping-spec", PocBlockerKind.REVIEW, "mapping-spec"),
        ("blocked_error", "codegen", PocBlockerKind.SYSTEM, "program-execution"),
    ],
)
def test_legacy_blocked_run_is_read_as_v2_ledger(
    tmp_path: Path,
    legacy_state: str,
    current_step: str,
    expected_kind: PocBlockerKind,
    expected_stage: str,
) -> None:
    container = _minimal_container(tmp_path)
    study = container / STUDY_ID
    runs = study / ".application_api" / "poc_runs"
    runs.mkdir(parents=True)
    run_id = "run-legacy1234"
    (runs / f"{run_id}.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "run_state": legacy_state,
                "current_step": current_step,
                "blocking_reason": "legacy blocker",
                "blocking_review_id": "review-fixture-001"
                if legacy_state == "blocked_review"
                else None,
                "updated_at": "2026-07-17T20:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    state = PocState.model_validate(
        _client(container).get(f"/api/v1/studies/{STUDY_ID}/poc-state").json()
    )

    assert state.run_state is PocRunState.BLOCKED
    assert state.legacy_run_state == legacy_state
    assert state.blocker is not None
    assert state.blocker.kind is expected_kind
    assert state.blocker.stage_id == expected_stage
    assert next(step for step in state.steps if step.state is PocStepState.BLOCKED).step_id == expected_stage


def test_poc_run_routes_normalize_legacy_runner_response(tmp_path: Path) -> None:
    client = _client(_minimal_container(tmp_path))
    start = client.post(
        f"/api/v1/studies/{STUDY_ID}/poc-runs",
        json={"target_artifact": "sdtm_ae_dataset", "intent": "生成 AE POC"},
    )

    assert start.status_code == 202
    start_payload = start.json()
    assert start_payload["accepted"] is True
    assert start_payload["run_state"] == "blocked"
    assert start_payload["state_endpoint"].endswith("/poc-state")

    run = client.get(f"/api/v1/studies/{STUDY_ID}/poc-runs/{start_payload['run_id']}")
    assert run.status_code == 200
    assert run.json()["run_state"] == "blocked"
    assert run.json()["legacy_run_state"] is None
    assert run.json()["blocker"]["kind"] == "input"


def test_completed_review_projects_legacy_aeterm_fail_as_deferred_warning(
    tmp_path: Path,
) -> None:
    container = _minimal_container(tmp_path)
    study = container / STUDY_ID
    runs = study / ".application_api" / "poc_runs"
    runs.mkdir(parents=True)
    payload = _minimal_state(PocRunState.DONE).model_dump(mode="json")
    payload.update(
        {
            "run_id": "run-poc-completed-review",
            "schema_version": "2.0",
            "updated_at": "2026-07-20T08:00:00Z",
            "current_step": "canonical-ae",
        }
    )
    validation_step = next(
        step for step in payload["steps"] if step["step_id"] == "validation-review"
    )
    validation_step["state"] = "done"
    validation_step["checks"] = [
        {
            "check_id": "required_value_empty",
            "state": "fail",
            "summary": "AETERM: 128/1066 条记录",
            "affected_variables": ["AETERM"],
            "evidence_refs": ["output/sdtm/validation/ae-reference-validation.json"],
        }
    ]
    (runs / "run-poc-completed-review.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    state = _client(container).get(f"/api/v1/studies/{STUDY_ID}/poc-state").json()
    projected = next(
        step for step in state["steps"] if step["step_id"] == "validation-review"
    )

    assert projected["state"] == "done"
    assert projected["checks"][0]["state"] == "warning"
    assert "后审处置" in projected["checks"][0]["summary"]
