from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from review_panel.app import create_app


REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_SCHEMA = REPO_ROOT / "clinical-workflow" / "schemas" / "review" / "review-protocol.schema.json"


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "clinical-workflow" / "schemas" / "review").mkdir(parents=True)
    shutil.copy2(
        REAL_SCHEMA,
        repo / "clinical-workflow" / "schemas" / "review" / "review-protocol.schema.json",
    )
    (repo / "clinical-studies").mkdir()
    (repo / "clinical-llm-wiki" / ".review_queue").mkdir(parents=True)
    (repo / "clinical-llm-wiki" / "sources").mkdir()
    (repo / "clinical-llm-wiki" / "sources" / "source.txt").write_text(
        "source evidence\n",
        encoding="utf-8",
    )
    return repo


def packet(
    review_id: str = "sdtm_spec_ae_v1_001",
    *,
    source_documents: list[str] | None = None,
    required_reviewers: list[dict[str, str | None]] | None = None,
    auto_second: bool = False,
    created_at: str = "2026-07-14T00:00:00Z",
    urgency: str = "blocking",
) -> dict[str, object]:
    findings = [
        {
            "id": "F-001",
            "category": "mapping",
            "severity": "warning",
            "location": "AE.AETERM",
            "title": "Confirm AE term mapping",
            "current_value": "AE_TERM",
            "proposed_value": "AETERM",
            "rationale": "Direct mapping from collected AE term to SDTM variable.",
            "evidence_refs": ["SDTMIG 3.4 AE"],
            "auto_approved": False,
        },
        {
            "id": "F-002",
            "category": "compliance",
            "severity": "info",
            "location": "AE.AEDECOD",
            "title": "Confirm dictionary coding",
            "current_value": "coded term",
            "proposed_value": "AEDECOD",
            "rationale": "Dictionary coding statement requires human traceability check.",
            "evidence_refs": ["SDTMIG 3.4 Findings"],
            "auto_approved": auto_second,
        },
    ]
    payload: dict[str, object] = {
        "review_id": review_id,
        "review_type": "sdtm_spec",
        "source_documents": source_documents or ["sources/source.txt"],
        "agent_summary": "Generated AE findings for structured review.",
        "findings": findings,
        "urgency": urgency,
        "created_at": created_at,
        "generated_by": "DataStandardsAgent",
        "auto_approved_count": 1 if auto_second else 0,
    }
    if required_reviewers:
        payload["required_reviewers"] = required_reviewers
        payload["consensus_rule"] = "all_must_approve"
    return payload


def write_packet(repo: Path, payload: dict[str, object]) -> Path:
    path = repo / "clinical-llm-wiki" / ".review_queue" / f"{payload['review_id']}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def decision_body(packet_sha256: str, *, finding_ids: list[str] | None = None) -> dict[str, object]:
    return {
        "packet_sha256": packet_sha256,
        "reviewer": "Lead Programmer",
        "decisions": [
            {"finding_id": finding_id, "decision": "approved"}
            for finding_id in (finding_ids or ["F-001", "F-002"])
        ],
    }


def test_health_and_list_reviews_with_partial_invalid_packet(tmp_path: Path):
    repo = make_repo(tmp_path)
    write_packet(repo, packet("sdtm_spec_late_v1_001", created_at="2026-07-14T02:00:00Z"))
    write_packet(
        repo,
        packet(
            "sdtm_spec_early_v1_001",
            created_at="2026-07-14T01:00:00Z",
            urgency="blocking",
        ),
    )
    invalid = repo / "clinical-llm-wiki" / ".review_queue" / "sdtm_spec_bad_v1_001.json"
    invalid.write_text("{bad", encoding="utf-8")

    client = TestClient(create_app(repo))

    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["local_only"] is True

    response = client.get("/api/v1/reviews")
    assert response.status_code == 200
    payload = response.json()
    assert payload["partial"] is True
    assert [item["review_id"] for item in payload["reviews"]] == [
        "sdtm_spec_early_v1_001",
        "sdtm_spec_late_v1_001",
    ]
    assert payload["errors"][0]["review_id"] == "sdtm_spec_bad_v1_001"


def test_review_detail_source_preview_and_status_transitions(tmp_path: Path):
    repo = make_repo(tmp_path)
    write_packet(repo, packet())
    client = TestClient(create_app(repo))

    detail = client.get("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["status"] == "pending"
    assert detail_payload["source_availability"][0]["available"] is True

    source = client.get("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001/sources/0")
    assert source.status_code == 200
    assert source.json()["content"].replace("\r\n", "\n") == "source evidence\n"

    body = decision_body(detail_payload["packet_sha256"])
    submitted = client.post("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001/decisions", json=body)
    assert submitted.status_code == 200
    assert submitted.json()["receipt_file"] == "sdtm_spec_ae_v1_001_decision.json"

    after_decision = client.get("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001").json()
    assert after_decision["status"] == "decided_waiting_confirmation"

    confirmation = {
        "review_id": "sdtm_spec_ae_v1_001",
        "applied_at": "2026-07-14T03:00:00Z",
        "results": [
            {
                "finding_id": "F-001",
                "original_decision": "approved",
                "application_status": "applied",
            }
        ],
    }
    (
        repo / "clinical-llm-wiki" / ".review_queue" / "sdtm_spec_ae_v1_001_confirmation.json"
    ).write_text(json.dumps(confirmation), encoding="utf-8")
    assert client.get("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001").json()["status"] == "confirmed"


def test_decision_submit_rejects_hash_drift_and_duplicate_receipt(tmp_path: Path):
    repo = make_repo(tmp_path)
    packet_path = write_packet(repo, packet())
    client = TestClient(create_app(repo))
    detail = client.get("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001").json()

    packet_payload = json.loads(packet_path.read_text(encoding="utf-8"))
    packet_payload["agent_summary"] = "Changed packet content after reviewer loaded it."
    packet_path.write_text(json.dumps(packet_payload), encoding="utf-8")
    drift = client.post(
        "/api/v1/reviews/wiki/sdtm_spec_ae_v1_001/decisions",
        json=decision_body(detail["packet_sha256"]),
    )
    assert drift.status_code == 409
    assert not (repo / "clinical-llm-wiki" / ".review_queue" / "sdtm_spec_ae_v1_001_decision.json").exists()

    current_hash = client.get("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001").json()["packet_sha256"]
    assert client.post(
        "/api/v1/reviews/wiki/sdtm_spec_ae_v1_001/decisions",
        json=decision_body(current_hash),
    ).status_code == 200
    duplicate = client.post(
        "/api/v1/reviews/wiki/sdtm_spec_ae_v1_001/decisions",
        json=decision_body(current_hash),
    )
    assert duplicate.status_code == 409


def test_decision_submit_requires_actionable_finding_coverage_and_role(tmp_path: Path):
    repo = make_repo(tmp_path)
    write_packet(
        repo,
        packet(
            required_reviewers=[{"role": "clinical_lead", "name": None}],
            auto_second=True,
        ),
    )
    client = TestClient(create_app(repo))
    packet_hash = client.get("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001").json()["packet_sha256"]

    missing_role = client.post(
        "/api/v1/reviews/wiki/sdtm_spec_ae_v1_001/decisions",
        json=decision_body(packet_hash, finding_ids=["F-001"]),
    )
    assert missing_role.status_code == 422

    extra_auto = decision_body(packet_hash)
    extra_auto["reviewer_role"] = "clinical_lead"
    rejected = client.post(
        "/api/v1/reviews/wiki/sdtm_spec_ae_v1_001/decisions",
        json=extra_auto,
    )
    assert rejected.status_code == 422

    accepted = decision_body(packet_hash, finding_ids=["F-001"])
    accepted["reviewer_role"] = "clinical_lead"
    response = client.post(
        "/api/v1/reviews/wiki/sdtm_spec_ae_v1_001/decisions",
        json=accepted,
    )
    assert response.status_code == 200
    assert response.json()["receipt_file"] == "sdtm_spec_ae_v1_001_decision_clinical_lead.json"


def test_api_does_not_apply_or_archive_decision(tmp_path: Path):
    repo = make_repo(tmp_path)
    write_packet(repo, packet())
    client = TestClient(create_app(repo))
    packet_hash = client.get("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001").json()["packet_sha256"]

    response = client.post(
        "/api/v1/reviews/wiki/sdtm_spec_ae_v1_001/decisions",
        json=decision_body(packet_hash),
    )

    queue = repo / "clinical-llm-wiki" / ".review_queue"
    assert response.status_code == 200
    assert (queue / "sdtm_spec_ae_v1_001.json").exists()
    assert (queue / "sdtm_spec_ae_v1_001_decision.json").exists()
    assert not (queue / "sdtm_spec_ae_v1_001_confirmation.json").exists()
    assert not (queue / "archive").exists()
