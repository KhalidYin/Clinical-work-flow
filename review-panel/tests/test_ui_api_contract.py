from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from review_panel.app import create_app
from test_review_api import decision_body, make_repo, packet, write_packet


def test_ui_contract_can_complete_basic_review_flow_through_api(tmp_path: Path):
    repo = make_repo(tmp_path)
    write_packet(repo, packet())
    client = TestClient(create_app(repo))

    list_payload = client.get("/api/v1/reviews").json()
    assert list_payload["reviews"][0]["queue_id"] == "wiki"
    assert list_payload["reviews"][0]["review_id"] == "sdtm_spec_ae_v1_001"

    detail = client.get("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001").json()
    assert detail["packet_sha256"]
    assert detail["source_availability"][0]["available"] is True

    source = client.get("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001/sources/0").json()
    assert "source evidence" in source["content"]

    decision = client.post(
        "/api/v1/reviews/wiki/sdtm_spec_ae_v1_001/decisions",
        json=decision_body(detail["packet_sha256"]),
    )
    assert decision.status_code == 200
    assert decision.json()["receipt_file"] == "sdtm_spec_ae_v1_001_decision.json"
    assert client.get("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001").json()["status"] == (
        "decided_waiting_confirmation"
    )

