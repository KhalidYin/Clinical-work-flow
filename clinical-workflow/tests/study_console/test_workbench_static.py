"""P0 React Workbench static UI contract tests."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from src.application_api import ApplicationApiConfig, create_app


ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = ROOT.parent
WORKBENCH_STATIC = ROOT / "src" / "study_console_workbench_static"


def _client(tmp_path: Path) -> TestClient:
    container = tmp_path / "clinical-studies"
    container.mkdir()
    app = create_app(ApplicationApiConfig(container_roots={"clinical-studies": container}))
    return TestClient(app)


def test_workbench_static_shell_and_assets_are_served(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/workbench/", follow_redirects=True)

    assert response.status_code == 200
    assert "Clinical POC Workbench" in response.text
    assert '<div id="root"></div>' in response.text
    asset_paths = re.findall(r'/(workbench/assets/[^"]+)', response.text)
    assert asset_paths
    for asset_path in asset_paths:
        assert client.get(f"/{asset_path}").status_code == 200


def test_workbench_redirect_points_to_static_shell(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/workbench", follow_redirects=False)

    assert response.status_code in {307, 308}
    assert response.headers["location"] == "/workbench/"


def test_workbench_build_artifact_is_committed() -> None:
    assert (WORKBENCH_STATIC / "index.html").exists()
    assert any((WORKBENCH_STATIC / "assets").glob("index-*.js"))


def test_browser_e2e_is_distinct_from_api_preflight() -> None:
    preflight = (REPO_ROOT / "scripts/smoke-sample-ae-workbench.ps1").read_text(
        encoding="utf-8"
    )
    browser_e2e = (REPO_ROOT / "scripts/e2e-sample-ae-workbench.ps1").read_text(
        encoding="utf-8"
    )

    assert "API preflight OK (no browser actions were executed)" in preflight
    assert "agent-browser" not in preflight
    assert "agent-browser" in browser_e2e
    assert "SAMPLE-AE-E2E" in browser_e2e
    assert "SAMPLE-AE-INPUT-E2E" in browser_e2e
    assert 'Name "Run POC"' in browser_e2e
    assert 'Name "Retry current step"' in browser_e2e
    assert 'Name "Submit DecisionReceipt"' in browser_e2e
    assert 'Name "Resume"' in browser_e2e
    assert 'workspace-tab:nth-child(4)' in browser_e2e
    assert "CLINICAL_STUDIES_ROOT" in browser_e2e
