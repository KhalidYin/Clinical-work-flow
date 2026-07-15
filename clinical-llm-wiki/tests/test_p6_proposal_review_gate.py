"""P6-P3-D SDTMIG 3.4 proposal review-gate tests."""

from __future__ import annotations

import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator

from scripts.content.sdtmig34_proposal_review import (
    DEFAULT_REVIEW_REPORT,
    PACKET_NAME,
    REVIEW_ID,
    build_proposal_review_artifacts,
    schema_definition,
)


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_PACKET = ROOT / ".review_queue" / PACKET_NAME
ARCHIVED_PACKET = ROOT / ".review_queue" / "archive" / PACKET_NAME


def _packet_path() -> Path:
    return ACTIVE_PACKET if ACTIVE_PACKET.exists() else ARCHIVED_PACKET


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_proposal_review_report_opens_pending_human_gate() -> None:
    report = _read(DEFAULT_REVIEW_REPORT)

    assert report["review_id"] == REVIEW_ID
    assert report["gate_status"] == "pending_human_review"
    assert report["summary"] == {
        "auto_approved_count": 0,
        "checks_failed": 0,
        "checks_passed": 6,
        "checks_total": 6,
        "human_findings_pending": 28,
        "proposal_total": 28,
    }
    assert report["semantic_quality"]["statement_status_counts"] == {"proposed": 28}
    assert report["semantic_quality"]["duplicate_evidence_key_count"] == 0
    assert [item["check_id"] for item in report["checks"]] == [
        f"CHK-{index:03d}" for index in range(1, 7)
    ]
    assert {item["status"] for item in report["checks"]} == {"passed"}


def test_proposal_review_packet_is_blocking_schema_valid_and_chinese() -> None:
    packet = _read(_packet_path())
    Draft202012Validator(schema_definition(ROOT, "review_packet")).validate(packet)

    assert packet["review_id"] == REVIEW_ID
    assert packet["review_type"] == "sdtm_spec"
    assert packet["urgency"] == "blocking"
    assert packet["auto_approved_count"] == 0
    findings = packet["findings"]
    assert len(findings) == 28
    assert [item["id"] for item in findings] == [
        f"F-{index:03d}" for index in range(1, 29)
    ]
    assert all(not item["auto_approved"] for item in findings)
    human_text = [packet["agent_summary"], packet["generated_by"]]
    for finding in findings:
        human_text.extend(
            finding[field]
            for field in ("title", "current_value", "proposed_value", "rationale")
        )
        assert finding["evidence_refs"][0].startswith("proposal:")
        assert any(item.startswith("locator:") for item in finding["evidence_refs"])
    assert all(re.search(r"[\u4e00-\u9fff]", value) for value in human_text)


def test_proposal_review_source_documents_are_committed_review_inputs() -> None:
    packet = _read(_packet_path())

    for declared in packet["source_documents"]:
        path = ROOT / declared
        assert path.is_file(), declared
        normalized = path.relative_to(ROOT).as_posix()
        assert "/original/" not in normalized
        assert "/derived/" not in normalized
        assert path.suffix.lower() not in {".pdf", ".xlsx"}


def test_proposal_review_gate_is_active_without_decision_or_confirmation() -> None:
    if ACTIVE_PACKET.exists():
        assert not ACTIVE_PACKET.with_name(f"{REVIEW_ID}_decision.json").exists()
        assert not ACTIVE_PACKET.with_name(f"{REVIEW_ID}_confirmation.json").exists()
        return

    assert ARCHIVED_PACKET.is_file()
    assert ARCHIVED_PACKET.with_name(f"{REVIEW_ID}_decision.json").is_file()
    assert ARCHIVED_PACKET.with_name(f"{REVIEW_ID}_confirmation.json").is_file()


def test_proposal_review_artifacts_rebuild_exactly() -> None:
    packet = _read(_packet_path())
    report, rebuilt_packet = build_proposal_review_artifacts(
        wiki_root=ROOT,
        created_at=packet["created_at"],
    )

    assert report == _read(DEFAULT_REVIEW_REPORT)
    assert rebuilt_packet == packet
