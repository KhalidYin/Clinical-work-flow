"""Sample study scaffold contract tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.application_api import ApplicationApiConfig, create_app


ROOT = Path(__file__).resolve().parents[2]
PLATFORM_ROOT = ROOT.parent
STUDIES_ROOT = PLATFORM_ROOT / "clinical-studies"
SAMPLE_STUDY = STUDIES_ROOT / "SAMPLE-AE-001"


def test_sample_study_scaffold_keeps_raw_inputs_non_json() -> None:
    assert SAMPLE_STUDY.exists()

    json_inputs = sorted(path.relative_to(SAMPLE_STUDY).as_posix() for path in (SAMPLE_STUDY / "input").rglob("*.json"))

    assert json_inputs == []
    assert (SAMPLE_STUDY / "work" / "derived").exists()
    assert (SAMPLE_STUDY / "work" / "mapping").exists()
    assert (SAMPLE_STUDY / "programs" / "edc_to_sdtm" / "r").exists()
    assert (SAMPLE_STUDY / "programs" / "edc_to_sdtm" / "python").exists()
    assert (SAMPLE_STUDY / "programs" / "edc_to_sdtm" / "sas").exists()
    assert not (SAMPLE_STUDY / "runtime-manifest.yaml").exists()
    assert (SAMPLE_STUDY / "runtime-manifest.draft.yaml").exists()


def test_sample_study_is_visible_to_application_api_without_artifacts() -> None:
    client = TestClient(
        create_app(ApplicationApiConfig(container_roots={"clinical-studies": STUDIES_ROOT}))
    )

    studies = client.get("/api/v1/studies").json()
    study_ids = [study["study_id"] for study in studies["studies"]]
    assert "SAMPLE-AE-001" in study_ids

    status = client.get("/api/v1/studies/SAMPLE-AE-001/status").json()
    assert status["study_id"] == "SAMPLE-AE-001"
    assert status["run_state"] == "idle"
    assert status["knowledge_lock"]["status"] == "missing"

    artifacts = client.get("/api/v1/studies/SAMPLE-AE-001/artifacts").json()
    assert artifacts["artifacts"] == []
