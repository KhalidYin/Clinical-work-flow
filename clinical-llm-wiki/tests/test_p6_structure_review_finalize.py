"""P6-P2-E human-decision application and archive gates."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from scripts.pdf.structure_map_review import PACKET_NAME, REVIEW_ID, StructureMapReviewError
from scripts.pdf.structure_review_finalize import (
    AUDIT_EVENT_ID,
    CONFIRMATION_NAME,
    DECISION_NAME,
    build_confirmation_receipt,
    finalize_structure_review,
)


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / ".review_queue" / "archive"
PACKET = ARCHIVE / PACKET_NAME
DECISION = ARCHIVE / DECISION_NAME
CONFIRMATION = ARCHIVE / CONFIRMATION_NAME


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_definition(name: str) -> dict[str, object]:
    schema = _read(
        ROOT.parent
        / "clinical-workflow"
        / "schemas"
        / "review"
        / "review-protocol.schema.json"
    )
    definition = deepcopy(schema["$defs"][name])  # type: ignore[index]
    definition.pop("$id", None)
    definition["$schema"] = schema["$schema"]
    definition["$defs"] = schema["$defs"]
    return definition


def test_archived_structure_review_triplet_is_schema_valid_and_complete() -> None:
    packet = _read(PACKET)
    decision = _read(DECISION)
    confirmation = _read(CONFIRMATION)
    Draft202012Validator(_schema_definition("review_packet")).validate(packet)
    Draft202012Validator(_schema_definition("decision_receipt")).validate(decision)
    Draft202012Validator(_schema_definition("confirmation_receipt")).validate(
        confirmation
    )

    finding_ids = {item["id"] for item in packet["findings"]}  # type: ignore[index]
    assert {item["finding_id"] for item in decision["decisions"]} == finding_ids  # type: ignore[index]
    assert {item["finding_id"] for item in confirmation["results"]} == finding_ids  # type: ignore[index]
    assert {item["decision"] for item in decision["decisions"]} == {"approved"}  # type: ignore[index]
    assert {item["application_status"] for item in confirmation["results"]} == {  # type: ignore[index]
        "applied"
    }
    assert confirmation["summary"] == {
        "total": 8,
        "applied": 8,
        "adjusted": 0,
        "failed": 0,
    }


def test_structure_review_audit_event_is_unique_and_bound_to_reviewer() -> None:
    events = [
        json.loads(line)
        for line in (ROOT / "audit_trail.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matches = [event for event in events if event.get("event_id") == AUDIT_EVENT_ID]
    assert len(matches) == 1
    assert matches[0]["review_id"] == REVIEW_ID
    assert matches[0]["actor"] == "KK"
    assert matches[0]["result"] == "applied"


def test_finalizer_check_is_idempotent() -> None:
    confirmation = finalize_structure_review(ROOT, write=False)
    assert confirmation == _read(CONFIRMATION)


def test_confirmation_builder_rejects_incomplete_or_nonapproved_decisions() -> None:
    packet = _read(PACKET)
    decision = _read(DECISION)
    incomplete = deepcopy(decision)
    incomplete["decisions"].pop()  # type: ignore[index]
    with pytest.raises(StructureMapReviewError, match="coverage mismatch"):
        build_confirmation_receipt(
            packet,
            incomplete,
            applied_at="2026-07-15T13:40:00+08:00",
        )

    rejected = deepcopy(decision)
    rejected["decisions"][0]["decision"] = "rejected"  # type: ignore[index]
    with pytest.raises(StructureMapReviewError, match="requires rework"):
        build_confirmation_receipt(
            packet,
            rejected,
            applied_at="2026-07-15T13:40:00+08:00",
        )
