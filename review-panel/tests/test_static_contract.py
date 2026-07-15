from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from review_panel.app import create_app
from test_review_api import make_repo


STATIC_ROOT = Path(__file__).resolve().parents[1] / "src" / "review_panel" / "static"


def read_static(name: str) -> str:
    return (STATIC_ROOT / name).read_text(encoding="utf-8")


def test_static_files_are_served_by_fastapi(tmp_path: Path):
    repo = make_repo(tmp_path)
    client = TestClient(create_app(repo))

    assert client.get("/").status_code == 200
    assert "Clinical Review Panel" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/review-client.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200


def test_html_contains_required_review_workflow_regions():
    html = read_static("index.html")

    assert '<section class="review-list-panel"' in html
    assert '<section class="review-detail-panel"' in html
    assert 'id="service-state"' in html
    assert 'id="global-alerts"' in html
    assert 'id="finding-template"' in html
    assert 'value="approved"' in html
    assert 'value="modified"' in html
    assert 'value="rejected"' in html
    assert "checked" not in html
    assert "reviewer_role" not in html


def test_frontend_uses_review_client_and_not_disk_paths_or_frameworks():
    app_js = read_static("app.js")
    client_js = read_static("review-client.js")
    html = read_static("index.html")

    combined = "\n".join([app_js, client_js, html])
    assert "new ReviewClient" in app_js
    assert "/api/v1/reviews" in client_js
    assert "file://" not in combined
    assert "C:\\" not in combined
    assert "React" not in combined
    assert "Vue" not in combined
    assert "localStorage" not in combined


def test_frontend_contract_covers_batch_submit_url_restore_and_states():
    app_js = read_static("app.js")

    assert "URLSearchParams(window.location.search)" in app_js
    assert "history.pushState" in app_js
    assert "confirm(`Approve" in app_js
    assert "confirm(`Submit decisions" in app_js
    assert "decided_waiting_confirmation" in app_js
    assert "source_availability" in app_js
    assert "required_reviewers" in app_js
    assert "aria-selected" in app_js


def test_css_covers_accessibility_and_narrow_layout():
    css = read_static("styles.css")

    assert "@media (max-width: 900px)" in css
    assert "grid-template-columns: 1fr" in css
    assert "button:focus-visible" in css
    assert "min-height: 44px" in css
    assert "[hidden]" in css
    assert ".button.primary:disabled" in css
    assert "fieldset:disabled" in css
    assert "oklch(" in css
    assert "border-radius: var(--radius)" in css
