import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PANEL_DIR = ROOT / "src" / "review_panel"


def read_panel_file(*parts: str) -> str:
    return (PANEL_DIR / Path(*parts)).read_text(encoding="utf-8")


def test_review_panel_package_declares_sidebar_view_and_command():
    package = json.loads(read_panel_file("package.json"))

    assert "onView:clinicalReviewPanel.reviewQueue" in package["activationEvents"]
    assert package["contributes"]["commands"][0]["command"] == "clinicalReviewPanel.open"
    assert package["contributes"]["viewsContainers"]["activitybar"][0]["id"] == "clinicalReviewPanel"
    assert package["contributes"]["views"]["clinicalReviewPanel"][0]["id"] == "clinicalReviewPanel.reviewQueue"


def test_review_panel_schema_matches_rejected_feedback_contract():
    schema = read_panel_file("src", "schema.ts")

    for token in [
        "rejection_reason",
        "human_correction",
        "reference",
        "insufficient_evidence",
        "validateDecisionReceiptForPacket",
        "human_correction must be at least 10 characters",
    ]:
        assert token in schema


def test_review_panel_webview_collects_rejected_and_modified_decisions():
    webview = read_panel_file("src", "webview.ts")

    for token in [
        "Rejection reason",
        'data-field="rejection_reason"',
        'data-field="human_correction"',
        'data-field="reference"',
        'data-field="modified_value"',
        "vscode.postMessage({ type: 'submitDecision', receipt })",
        "decision.rejection_reason !== 'insufficient_evidence'",
    ]:
        assert token in webview


def test_review_panel_extension_reads_queue_and_writes_decision_receipt():
    extension = read_panel_file("src", "extension.ts")

    for token in [
        '".review_queue"',
        "registerWebviewViewProvider",
        "validateReviewPacket",
        "validateDecisionReceiptForPacket",
        "fs.writeFile",
        "`${this.current.packet.review_id}_decision.json`",
    ]:
        assert token in extension
