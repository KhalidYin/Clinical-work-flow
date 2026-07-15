"""P6-P3-E SDTMIG 3.4 proposal approval application gates."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from scripts.content.extraction_contract import validate_extraction_package
from scripts.content.sdtmig34_proposal_finalize import (
    APPROVAL_RECEIPT_ID,
    AUDIT_EVENT_ID,
    CONFIRMATION_NAME,
    DECISION_NAME,
    DEFAULT_RELEASE,
    PACKET_NAME,
    REVIEW_ID,
    ProposalFinalizeError,
    build_confirmation_receipt,
    finalize_proposal_review,
)


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / ".review_queue" / "archive"
PACKET = ARCHIVE / PACKET_NAME
DECISION = ARCHIVE / DECISION_NAME
CONFIRMATION = ARCHIVE / CONFIRMATION_NAME


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_definition(name: str) -> dict[str, object]:
    schema = _read(ROOT / "schemas" / "engine" / "review" / "review-protocol.schema.json")
    definition = deepcopy(schema["$defs"][name])  # type: ignore[index]
    definition.pop("$id", None)
    definition["$schema"] = schema["$schema"]
    definition["$defs"] = schema["$defs"]
    return definition


def test_archived_proposal_review_triplet_is_schema_valid_and_complete() -> None:
    packet = _read(PACKET)
    decision = _read(DECISION)
    confirmation = _read(CONFIRMATION)
    Draft202012Validator(_schema_definition("review_packet")).validate(packet)
    Draft202012Validator(_schema_definition("decision_receipt")).validate(decision)
    Draft202012Validator(_schema_definition("confirmation_receipt")).validate(
        confirmation
    )

    finding_ids = {item["id"] for item in packet["findings"]}  # type: ignore[index]
    assert len(finding_ids) == 28
    assert {item["finding_id"] for item in decision["decisions"]} == finding_ids  # type: ignore[index]
    assert {item["finding_id"] for item in confirmation["results"]} == finding_ids  # type: ignore[index]
    assert {item["decision"] for item in decision["decisions"]} == {"approved"}  # type: ignore[index]
    assert {item["application_status"] for item in confirmation["results"]} == {  # type: ignore[index]
        "applied"
    }
    assert confirmation["summary"] == {
        "total": 28,
        "applied": 28,
        "adjusted": 0,
        "failed": 0,
    }


def test_approved_proposal_release_is_bound_to_review_receipt() -> None:
    release = _read(DEFAULT_RELEASE)
    package = release["extraction_package"]  # type: ignore[index]
    validate_extraction_package(package)  # type: ignore[arg-type]

    statements = package["statements"]  # type: ignore[index]
    assert len(statements) == 28
    assert {statement["review_status"] for statement in statements} == {"approved"}
    assert {statement["review_receipt_id"] for statement in statements} == {
        APPROVAL_RECEIPT_ID
    }
    assert release["review_id"] == REVIEW_ID
    assert release["approval_receipt_id"] == APPROVAL_RECEIPT_ID
    assert release["approved_statement_count"] == 28


def test_proposal_review_audit_event_and_obsidian_release_card_exist() -> None:
    events = [
        json.loads(line)
        for line in (ROOT / "audit_trail.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matches = [event for event in events if event.get("event_id") == AUDIT_EVENT_ID]
    assert len(matches) == 1
    assert matches[0]["review_id"] == REVIEW_ID
    assert matches[0]["approval_receipt_id"] == APPROVAL_RECEIPT_ID
    assert matches[0]["result"] == "applied"

    release_card = (
        ROOT
        / "vault"
        / "60_Sources"
        / "Registry"
        / "SDTMIG 3.4 Approved Proposal Release.md"
    )
    assert release_card.is_file()
    assert "P4 才会把 release 拆成可复用知识卡" in release_card.read_text(
        encoding="utf-8"
    )


def test_proposal_finalizer_check_is_idempotent() -> None:
    confirmation = finalize_proposal_review(ROOT, write=False)
    assert confirmation == _read(CONFIRMATION)


def test_confirmation_builder_rejects_incomplete_or_nonapproved_decisions() -> None:
    packet = _read(PACKET)
    decision = _read(DECISION)
    release = _read(DEFAULT_RELEASE)
    package = release["extraction_package"]  # type: ignore[index]

    incomplete = deepcopy(decision)
    incomplete["decisions"].pop()  # type: ignore[index]
    with pytest.raises(ProposalFinalizeError, match="coverage mismatch"):
        build_confirmation_receipt(
            packet,
            incomplete,
            package,  # type: ignore[arg-type]
            applied_at="2026-07-15T17:30:00+08:00",
        )

    rejected = deepcopy(decision)
    rejected["decisions"][0]["decision"] = "rejected"  # type: ignore[index]
    with pytest.raises(ProposalFinalizeError, match="requires rework"):
        build_confirmation_receipt(
            packet,
            rejected,
            package,  # type: ignore[arg-type]
            applied_at="2026-07-15T17:30:00+08:00",
        )
