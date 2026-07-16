"""P8-P4 Study Console static UI contract tests."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from src.agents.ae_workflow import build_sdtm_ae_dataset
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
APP_JS = ROOT / "src" / "study_console" / "static" / "app.js"


def _prepare_container(tmp_path: Path, *, run_ae: bool = False) -> Path:
    container = tmp_path / "clinical-studies"
    shutil.copytree(FIXTURE, container / "ae-pilot")
    if run_ae:
        build_sdtm_ae_dataset(container / "ae-pilot", WIKI_PACKAGE, auto_approve=False)
    return container


def _client(container: Path) -> TestClient:
    app = create_app(ApplicationApiConfig(container_roots={"clinical-studies": container}))
    return TestClient(app)


def test_console_static_shell_and_assets_are_served(tmp_path: Path) -> None:
    client = _client(_prepare_container(tmp_path))

    response = client.get("/console/", follow_redirects=True)

    assert response.status_code == 200
    assert "Clinical Study Console" in response.text
    assert 'id="study-list"' in response.text
    assert 'id="stage-timeline"' in response.text
    assert 'id="run-form"' in response.text
    assert 'id="review-list"' in response.text
    assert "./styles.css" in response.text
    assert "./app.js" in response.text

    assert client.get("/console/styles.css").status_code == 200
    assert client.get("/console/app.js").status_code == 200


def test_console_default_config_can_use_env_studies_root(
    tmp_path: Path,
    monkeypatch,
) -> None:
    container = _prepare_container(tmp_path)
    monkeypatch.setenv("CLINICAL_STUDIES_ROOT", str(container))

    client = TestClient(create_app())
    payload = client.get("/api/v1/studies").json()

    assert [study["study_id"] for study in payload["studies"]] == ["SYNTH-AE-001"]


def test_console_javascript_is_syntax_valid() -> None:
    node = shutil.which("node")
    if node is None:
        raise AssertionError("node is required for Study Console JavaScript syntax validation")

    result = subprocess.run(
        [node, "--check", str(APP_JS)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_review_api_payload_contains_finding_detail_required_by_console(
    tmp_path: Path,
) -> None:
    container = _prepare_container(tmp_path, run_ae=True)
    client = _client(container)

    payload = client.get("/api/v1/studies/SYNTH-AE-001/reviews").json()

    review = payload["reviews"][0]
    assert review["review_id"] == "sdtm_spec_ae_v1_001"
    assert review["decision_state"] == "pending"
    assert review["packet_sha256"]
    assert review["agent_summary"]
    assert review["findings"]
    finding = review["findings"][0]
    assert finding["finding_id"].startswith("F-")
    assert finding["title"]
    assert finding["proposed_value"]
    assert isinstance(finding["auto_approved"], bool)
    assert "G:\\" not in str(finding)
    assert "/" not in review["packet_sha256"]
