"""P8-P3 write-limited Application API integration tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from src.agents.ae_workflow import apply_ae_review_decision, build_sdtm_ae_dataset
from src.application_api import ApplicationApiConfig, create_app


ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = ROOT.parent
FIXTURE = ROOT / "tests" / "fixtures" / "studies" / "ae-pilot"
WIKI_PACKAGE = (
    PLATFORM_ROOT
    / "clinical-llm-wiki"
    / "sources"
    / "packages"
    / "src-cdisc-sdtmig-3-4"
)
STUDY_ID = "SYNTH-AE-001"
REVIEW_ID = "sdtm_spec_ae_v1_001"


def _prepare_container(tmp_path: Path, *, second_study: bool = False) -> Path:
    container = tmp_path / "clinical-studies"
    study = container / "ae-pilot"
    shutil.copytree(FIXTURE, study)
    if second_study:
        second = container / "ae-pilot-2"
        shutil.copytree(FIXTURE, second)
        project = second / "project.yaml"
        project.write_text(
            project.read_text(encoding="utf-8").replace(
                'study_id: "SYNTH-AE-001"',
                'study_id: "SYNTH-AE-002"',
            ),
            encoding="utf-8",
        )
    return container


def _client(container: Path) -> TestClient:
    app = create_app(ApplicationApiConfig(container_roots={"clinical-studies": container}))
    return TestClient(app)


def _run_intent() -> dict[str, object]:
    return {
        "intent": "生成 AE 数据集",
        "target_stage": "sdtm_programming",
        "dataset": "AE",
        "dry_run": True,
    }


def _headers(key: str) -> dict[str, str]:
    return {"Idempotency-Key": key}


def _review_packet(study: Path) -> dict[str, object]:
    return json.loads((study / ".review_queue" / f"{REVIEW_ID}.json").read_text(encoding="utf-8"))


def _packet_sha256(study: Path) -> str:
    return __import__("hashlib").sha256(
        (study / ".review_queue" / f"{REVIEW_ID}.json").read_bytes()
    ).hexdigest()


def _approval_request(study: Path, reviewer: str = "中文审核人") -> dict[str, object]:
    packet = _review_packet(study)
    decisions = [
        {"finding_id": finding["id"], "decision": "approved"}
        for finding in packet["findings"]
        if not finding.get("auto_approved", False)
    ]
    return {
        "review_id": REVIEW_ID,
        "packet_sha256": _packet_sha256(study),
        "reviewer": reviewer,
        "decisions": decisions,
    }


def _rejection_request(study: Path) -> dict[str, object]:
    packet = _review_packet(study)
    decisions = [
        {
            "finding_id": finding["id"],
            "decision": "rejected",
            "rejection_reason": "insufficient_evidence",
            "comment": "需要补充 SDTM IG 和 study-specific 证据。",
        }
        for finding in packet["findings"]
        if not finding.get("auto_approved", False)
    ]
    return {
        "review_id": REVIEW_ID,
        "packet_sha256": _packet_sha256(study),
        "reviewer": "中文审核人",
        "decisions": decisions,
    }


def test_start_run_is_idempotent_and_blocks_conflicting_same_study_run(
    tmp_path: Path,
) -> None:
    container = _prepare_container(tmp_path)
    client = _client(container)

    first = client.post(
        f"/api/v1/studies/{STUDY_ID}/runs",
        json=_run_intent(),
        headers=_headers("idem-start-000001"),
    )
    assert first.status_code == 202
    payload = first.json()
    assert payload["accepted"] is True
    assert payload["run_state"] == "queued"

    retry = client.post(
        f"/api/v1/studies/{STUDY_ID}/runs",
        json=_run_intent(),
        headers=_headers("idem-start-000001"),
    )
    assert retry.status_code == 202
    assert retry.json() == payload

    changed_body = client.post(
        f"/api/v1/studies/{STUDY_ID}/runs",
        json={**_run_intent(), "dataset": "CM"},
        headers=_headers("idem-start-000001"),
    )
    assert changed_body.status_code == 409
    assert changed_body.json()["code"] == "idempotency_conflict"

    conflict = client.post(
        f"/api/v1/studies/{STUDY_ID}/runs",
        json=_run_intent(),
        headers=_headers("idem-start-000002"),
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "runtime_busy"

    run = client.get(f"/api/v1/studies/{STUDY_ID}/runs/{payload['run_id']}").json()
    assert run["run_state"] == "queued"
    assert run["event_cursor"].startswith("evt-")

    status = client.get(f"/api/v1/studies/{STUDY_ID}/status").json()
    assert status["run_state"] == "queued"


def test_different_studies_can_have_independent_active_runs(tmp_path: Path) -> None:
    container = _prepare_container(tmp_path, second_study=True)
    client = _client(container)

    first = client.post(
        f"/api/v1/studies/{STUDY_ID}/runs",
        json=_run_intent(),
        headers=_headers("idem-start-000011"),
    )
    second = client.post(
        "/api/v1/studies/SYNTH-AE-002/runs",
        json=_run_intent(),
        headers=_headers("idem-start-000012"),
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["run_id"] != second.json()["run_id"]


def test_resume_run_appends_cursor_events_without_duplicate_state(tmp_path: Path) -> None:
    container = _prepare_container(tmp_path)
    client = _client(container)
    start = client.post(
        f"/api/v1/studies/{STUDY_ID}/runs",
        json=_run_intent(),
        headers=_headers("idem-start-000021"),
    ).json()

    before = client.get(f"/api/v1/studies/{STUDY_ID}/events").json()
    cursor = before["next_cursor"]

    resume = client.post(
        f"/api/v1/studies/{STUDY_ID}/runs/{start['run_id']}/resume",
        json={"reason": "operator_resume", "last_seen_event_cursor": cursor},
        headers=_headers("idem-resume-000021"),
    )
    assert resume.status_code == 202
    assert resume.json()["run_state"] == "queued"

    after = client.get(f"/api/v1/studies/{STUDY_ID}/events", params={"cursor": cursor}).json()
    assert [event["event_type"] for event in after["events"]] == ["run_requested"]

    retry = client.post(
        f"/api/v1/studies/{STUDY_ID}/runs/{start['run_id']}/resume",
        json={"reason": "operator_resume", "last_seen_event_cursor": cursor},
        headers=_headers("idem-resume-000021"),
    )
    assert retry.status_code == 202
    assert retry.json() == resume.json()
    all_events = client.get(f"/api/v1/studies/{STUDY_ID}/events").json()["events"]
    assert [event["event_type"] for event in all_events].count("run_requested") == 2


def test_review_decision_api_writes_decision_receipt_and_runtime_can_apply(
    tmp_path: Path,
) -> None:
    container = _prepare_container(tmp_path)
    study = container / "ae-pilot"
    build_sdtm_ae_dataset(study, WIKI_PACKAGE, auto_approve=False)
    client = _client(container)

    review = client.get(f"/api/v1/studies/{STUDY_ID}/reviews").json()["reviews"][0]
    assert review["review_id"] == REVIEW_ID
    assert review["decision_state"] == "pending"
    assert review["packet_sha256"] == _packet_sha256(study)

    response = client.post(
        f"/api/v1/studies/{STUDY_ID}/reviews/{REVIEW_ID}/decisions",
        json=_approval_request(study),
        headers=_headers("idem-review-000001"),
    )
    assert response.status_code == 201
    assert response.json()["decision_receipt_id"] == f"{REVIEW_ID}_decision"
    assert (study / ".review_queue" / f"{REVIEW_ID}_decision.json").exists()

    reviews = client.get(f"/api/v1/studies/{STUDY_ID}/reviews").json()["reviews"]
    assert reviews[0]["decision_state"] == "decided"

    applied = apply_ae_review_decision(study, WIKI_PACKAGE)
    assert applied.status == "canonical_written"
    assert (study / "output" / "sdtm" / "datasets" / "ae.csv").exists()


def test_review_decision_rejects_stale_hash_and_duplicate_non_idempotent_submit(
    tmp_path: Path,
) -> None:
    container = _prepare_container(tmp_path)
    study = container / "ae-pilot"
    build_sdtm_ae_dataset(study, WIKI_PACKAGE, auto_approve=False)
    client = _client(container)

    stale = _approval_request(study)
    stale["packet_sha256"] = "0" * 64
    stale_response = client.post(
        f"/api/v1/studies/{STUDY_ID}/reviews/{REVIEW_ID}/decisions",
        json=stale,
        headers=_headers("idem-review-000011"),
    )
    assert stale_response.status_code == 412
    assert stale_response.json()["code"] == "stale_decision"

    request = _approval_request(study)
    accepted = client.post(
        f"/api/v1/studies/{STUDY_ID}/reviews/{REVIEW_ID}/decisions",
        json=request,
        headers=_headers("idem-review-000012"),
    )
    assert accepted.status_code == 201

    retry = client.post(
        f"/api/v1/studies/{STUDY_ID}/reviews/{REVIEW_ID}/decisions",
        json=request,
        headers=_headers("idem-review-000012"),
    )
    assert retry.status_code == 201
    assert retry.json() == accepted.json()

    duplicate = client.post(
        f"/api/v1/studies/{STUDY_ID}/reviews/{REVIEW_ID}/decisions",
        json=request,
        headers=_headers("idem-review-000013"),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "review_not_pending"


def test_review_decision_rejected_receipt_allows_rework_path(tmp_path: Path) -> None:
    container = _prepare_container(tmp_path)
    study = container / "ae-pilot"
    build_sdtm_ae_dataset(study, WIKI_PACKAGE, auto_approve=False)
    client = _client(container)

    response = client.post(
        f"/api/v1/studies/{STUDY_ID}/reviews/{REVIEW_ID}/decisions",
        json=_rejection_request(study),
        headers=_headers("idem-review-000021"),
    )
    assert response.status_code == 201

    applied = apply_ae_review_decision(study, WIKI_PACKAGE)
    assert applied.status == "rework_required"
    assert not (study / "output" / "sdtm" / "datasets" / "ae.csv").exists()
    assert (study / ".review_queue" / f"{REVIEW_ID}_rework.json").exists()
