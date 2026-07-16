"""P8-P2 read-only Application API tests."""

from __future__ import annotations

import json
import shutil
import csv
from pathlib import Path

from fastapi.testclient import TestClient

from src.agents.ae_workflow import build_sdtm_ae_dataset
from src.application_api import ApplicationApiConfig, ApplicationApiService, create_app


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


def _prepare_container(tmp_path: Path, *, run_ae: bool = True) -> Path:
    container = tmp_path / "clinical-studies"
    study = container / "ae-pilot"
    shutil.copytree(FIXTURE, study)
    if run_ae:
        build_sdtm_ae_dataset(study, WIKI_PACKAGE, auto_approve=True)
    return container


def _client(container: Path) -> TestClient:
    app = create_app(
        ApplicationApiConfig(container_roots={"clinical-studies": container})
    )
    return TestClient(app)


def _csv_row_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        return len(list(csv.DictReader(handle)))


def test_readonly_api_lists_study_status_artifacts_context_provenance_and_audit(
    tmp_path: Path,
) -> None:
    container = _prepare_container(tmp_path)
    client = _client(container)

    studies = client.get("/api/v1/studies")
    assert studies.status_code == 200
    studies_payload = studies.json()
    assert [item["study_id"] for item in studies_payload["studies"]] == ["SYNTH-AE-001"]
    assert studies_payload["partial_errors"] == []
    assert str(container) not in studies.text

    status = client.get("/api/v1/studies/SYNTH-AE-001/status").json()
    assert status["run_state"] == "completed"
    assert status["pending_review_count"] == 0
    assert status["stage_order"] == [
        "protocol_analysis",
        "sap_generation",
        "sdtm_spec",
        "sdtm_programming",
        "adam_spec",
        "adam_programming",
        "tfl_shell_design",
        "tfl_programming",
        "qc_validation",
        "submission_packaging",
    ]
    sdtm_programming = next(
        item for item in status["stages"] if item["stage_id"] == "sdtm_programming"
    )
    assert sdtm_programming["status"] == "completed"
    assert sdtm_programming["canonical_artifact_count"] > 0

    artifacts = client.get("/api/v1/studies/SYNTH-AE-001/artifacts").json()
    canonical_ae = next(
        item for item in artifacts["artifacts"] if item["display_name"] == "output/sdtm/datasets/ae.csv"
    )
    assert canonical_ae["artifact_state"] == "canonical"
    assert canonical_ae["artifact_type"] == "dataset"
    assert canonical_ae["sha256"]
    assert "absolute" not in json.dumps(canonical_ae).lower()

    detail = client.get(
        f"/api/v1/studies/SYNTH-AE-001/artifacts/{canonical_ae['artifact_id']}"
    ).json()
    assert detail["registered_ref"]["container_id"] == "clinical-studies"
    assert detail["registered_ref"]["relative_path"].endswith("ae-pilot/output/sdtm/datasets/ae.csv")
    assert not detail["registered_ref"]["relative_path"].startswith("/")
    assert detail["preview"]["kind"] == "csv"
    assert detail["preview"]["row_count"] == _csv_row_count(
        container / "ae-pilot" / "expected" / "sdtm" / "ae.csv"
    )

    context = client.get("/api/v1/studies/SYNTH-AE-001/context").json()
    assert context["bundle_lock"]["version"] == "1.1.0"
    assert {item["ref_type"] for item in context["rule_refs"]} == {"rule"}
    assert "gap-ae-pilot-aedecod" in context["gaps"]
    assert context["source_refs"]
    assert context["study_decision_refs"]

    provenance = client.get("/api/v1/studies/SYNTH-AE-001/provenance").json()
    assert any(ref["ref_type"] == "artifact" for ref in provenance["traceability_refs"])
    assert any(
        item["display_name"] == "output/sdtm/traceability/ae_traceability_report.json"
        for item in provenance["artifacts"]
    )

    audit = client.get("/api/v1/studies/SYNTH-AE-001/audit").json()
    event_types = {event["event_type"] for event in audit["events"]}
    assert {
        "artifact_written",
        "review_packet_written",
        "decision_receipt_written",
        "confirmation_receipt_written",
    }.issubset(event_types)
    assert audit["next_cursor"].startswith("evt-")


def test_readonly_api_reports_partial_study_discovery_errors(tmp_path: Path) -> None:
    container = tmp_path / "clinical-studies"
    bad = container / "bad-study"
    bad.mkdir(parents=True)
    (bad / "project.yaml").write_text("study_id: []\n", encoding="utf-8")

    payload = _client(container).get("/api/v1/studies").json()

    assert payload["studies"] == []
    assert payload["partial_errors"][0]["code"] == "schema_validation_failed"


def test_readonly_api_rejects_unknown_study_and_unregistered_artifact(
    tmp_path: Path,
) -> None:
    container = _prepare_container(tmp_path)
    client = _client(container)

    unknown_study = client.get("/api/v1/studies/UNKNOWN/status")
    assert unknown_study.status_code == 404
    assert unknown_study.json()["code"] == "study_not_found"

    unknown_artifact = client.get("/api/v1/studies/SYNTH-AE-001/artifacts/..--escape")
    assert unknown_artifact.status_code == 404
    assert unknown_artifact.json()["code"] == "artifact_not_found"


def test_readonly_service_rejects_path_escape_without_interpreting_artifact_id_as_path(
    tmp_path: Path,
) -> None:
    container = _prepare_container(tmp_path)
    service = ApplicationApiService(
        ApplicationApiConfig(container_roots={"clinical-studies": container})
    )

    try:
        service.get_artifact("SYNTH-AE-001", "../outside")
    except Exception as exc:  # noqa: BLE001 - assert structured API error below
        assert exc.__class__.__name__ == "ApplicationApiError"
        assert getattr(exc, "code") == "artifact_not_found"
    else:  # pragma: no cover
        raise AssertionError("path-like artifact ID must not resolve to filesystem")


def test_readonly_context_fails_closed_for_damaged_traceability_json(tmp_path: Path) -> None:
    container = _prepare_container(tmp_path)
    traceability = (
        container
        / "ae-pilot"
        / "output"
        / "sdtm"
        / "traceability"
        / "ae_traceability_report.json"
    )
    traceability.write_text("{broken json", encoding="utf-8")

    response = _client(container).get("/api/v1/studies/SYNTH-AE-001/context")

    assert response.status_code == 409
    assert response.json()["code"] == "provenance_unavailable"


def test_readonly_status_for_review_required_study_stays_blocked_and_has_no_canonical(
    tmp_path: Path,
) -> None:
    container = _prepare_container(tmp_path, run_ae=False)
    build_sdtm_ae_dataset(container / "ae-pilot", WIKI_PACKAGE, auto_approve=False)

    client = _client(container)
    status = client.get("/api/v1/studies/SYNTH-AE-001/status").json()
    assert status["run_state"] == "blocked_review"
    assert status["pending_review_count"] == 1

    artifacts = client.get("/api/v1/studies/SYNTH-AE-001/artifacts").json()["artifacts"]
    assert any(item["display_name"] == "output/sdtm/drafts/ae.csv" for item in artifacts)
    assert not any(item["display_name"] == "output/sdtm/datasets/ae.csv" for item in artifacts)
