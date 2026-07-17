"""P0/P2 bounded POC runner flow tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from src.agents.ae_metadata_poc import MAPPING_REVIEW_ID
from src.agents.ae_metadata_workflow import CANONICAL_DATASET_PATH, PROGRAM_REVIEW_ID
from src.application_api import ApplicationApiConfig, create_app
from src.application_api.poc_models import PocState
from src.runtime.review_protocol import (
    Decision,
    DecisionReceipt,
    FindingDecision,
    RejectionReason,
    ReviewQueue,
)


ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _study_container(tmp_path: Path) -> Path:
    container = tmp_path / "clinical-studies"
    study = container / "SAMPLE-AE-001"
    source = study / "input/edc/ae.csv"
    _write(
        source,
        "STUDYID,Subject,RecordPosition,AETERM,AESTDAT,AEENDAT,AESEV_STD,AESER_STD,"
        "AEREL_STD,AEACN_STD,AEOUT_STD,AETERM_PT,AETERM_SOC,"
        "AETERM_CoderDictName,AETERM_CoderDictVersion\n"
        "SAMPLE-AE-001,S001,1,Headache,01 JAN 2026,02 JAN 2026,MILD,N,NOT RELATED,"
        "NONE,RECOVERED,Headache,Nervous system disorders,MedDRA,27.0\n"
        "SAMPLE-AE-001,S001,2,Nausea,UN FEB 2026,,MODERATE,N,RELATED,"
        "DOSE NOT CHANGED,RECOVERING,Nausea,Gastrointestinal disorders,MedDRA,27.0\n",
    )
    _write(
        study / "project.yaml",
        'study_id: "SAMPLE-AE-001"\n'
        "synthetic_only: true\n"
        "standards:\n"
        '  sdtmig_version: "3.4"\n',
    )
    _write(
        study / "source-inventory.yaml",
        'inventory_id: "test-poc-inventory"\n'
        'status: "test"\n'
        "synthetic_only: true\n"
        "sources:\n"
        '  - path: "input/edc/ae.csv"\n'
        '    source_type: "edc_csv_dataset"\n'
        '    format: "csv"\n'
        '    role: "ae_source_data"\n'
        f'    sha256: "{_sha256(source)}"\n',
    )
    return container


def _client(container: Path) -> TestClient:
    return TestClient(create_app(ApplicationApiConfig(container_roots={"clinical-studies": container})))


def _decide_all(study: Path, review_id: str, decision: Decision = Decision.APPROVED) -> None:
    queue = ReviewQueue(study)
    packet = queue.load_packet(review_id)
    assert packet is not None
    queue.submit_decision(
        DecisionReceipt(
            review_id=review_id,
            reviewer="POC flow reviewer",
            decisions=[
                FindingDecision(
                    finding_id=finding.id,
                    decision=decision,
                    rejection_reason=(
                        RejectionReason.INSUFFICIENT_EVIDENCE
                        if decision is Decision.REJECTED
                        else None
                    ),
                    comment="POC flow decision",
                )
                for finding in packet.findings_needing_decision()
            ],
        )
    )


def test_poc_runner_reaches_mapping_program_review_and_canonical(tmp_path: Path) -> None:
    container = _study_container(tmp_path)
    study = container / "SAMPLE-AE-001"
    client = _client(container)

    started = client.post(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs",
        json={"target_artifact": "sdtm_ae_dataset", "intent": "生成 AE POC"},
    )

    assert started.status_code == 202
    start_payload = started.json()
    assert start_payload["accepted"] is True
    assert start_payload["run_state"] == "blocked"
    assert (study / ".review_queue" / f"{MAPPING_REVIEW_ID}.json").exists()
    assert (study / "work/derived/edc/source-metadata.json").exists()
    assert (study / "work/derived/plans/minimum-information-sdtm-ae.json").exists()

    state = PocState.model_validate(
        client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    )
    assert state.run_id == start_payload["run_id"]
    assert state.active_step is not None
    assert state.active_step.review_id == MAPPING_REVIEW_ID
    assert state.blocker is not None
    assert state.blocker.kind.value == "review"
    assert {event.event_type for event in state.events} >= {
        "run_started",
        "mapping_review_written",
        "run_blocked_review",
    }

    _decide_all(study, MAPPING_REVIEW_ID)
    after_mapping = client.post(
        f"/api/v1/studies/SAMPLE-AE-001/poc-runs/{start_payload['run_id']}/resume",
        json={"reason": "review_decision_available", "review_id": MAPPING_REVIEW_ID},
    )

    assert after_mapping.status_code == 202
    assert after_mapping.json()["run_state"] == "blocked"
    assert (study / ".review_queue" / f"{PROGRAM_REVIEW_ID}.json").exists()
    assert (study / "programs/edc_to_sdtm/program-manifest.json").exists()
    assert (study / "output/sdtm/drafts/ae.csv").exists()

    _decide_all(study, PROGRAM_REVIEW_ID)
    after_program = client.post(
        f"/api/v1/studies/SAMPLE-AE-001/poc-runs/{start_payload['run_id']}/resume",
        json={"reason": "review_decision_available", "review_id": PROGRAM_REVIEW_ID},
    )

    assert after_program.status_code == 202
    assert after_program.json()["run_state"] == "done"
    assert (study / CANONICAL_DATASET_PATH).exists()
    done_state = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    assert done_state["run_state"] == "done"
    assert any(event["event_type"] == "run_done" for event in done_state["events"])


def test_poc_runner_rejected_mapping_review_fails_closed(tmp_path: Path) -> None:
    container = _study_container(tmp_path)
    study = container / "SAMPLE-AE-001"
    client = _client(container)
    started = client.post(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs",
        json={"target_artifact": "sdtm_ae_dataset", "intent": "生成 AE POC"},
    ).json()

    _decide_all(study, MAPPING_REVIEW_ID, Decision.REJECTED)
    resumed = client.post(
        f"/api/v1/studies/SAMPLE-AE-001/poc-runs/{started['run_id']}/resume",
        json={"reason": "review_decision_available", "review_id": MAPPING_REVIEW_ID},
    )

    assert resumed.status_code == 202
    assert resumed.json()["run_state"] == "blocked"
    assert not (study / CANONICAL_DATASET_PATH).exists()
    state = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    assert state["run_state"] == "blocked"
    assert state["blocker"]["kind"] == "system"
    assert "rework" in state["blocking_reason"].lower()
