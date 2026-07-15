"""Apply and archive the human-approved P6-P2 structure-map review.

The finalizer fails closed unless the DecisionReceipt covers every actionable
finding exactly once and every decision is approved. It revalidates the local
map hashes and the historical English P2-D packet before it writes the
ConfirmationReceipt, appends one audit event, and archives the immutable
packet/decision/confirmation triplet.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from scripts.pdf.structure_map_review import (
    PACKAGE_RELATIVE_PATH,
    PACKET_NAME,
    REPORT_NAME,
    REVIEW_ID,
    StructureMapReviewError,
    build_structure_review_artifacts,
)


CONFIRMATION_NAME = f"{REVIEW_ID}_confirmation.json"
DECISION_NAME = f"{REVIEW_ID}_decision.json"
AUDIT_EVENT_ID = "wiki-audit-20260715-sdtmig34-structure-v1-001"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise StructureMapReviewError(f"required review artifact is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StructureMapReviewError(f"review artifact is invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise StructureMapReviewError(f"review artifact must be an object: {path}")
    return payload


def _schema_definition(wiki_root: Path, name: str) -> dict[str, Any]:
    schema = _read_json(
        wiki_root.parent
        / "clinical-workflow"
        / "schemas"
        / "review"
        / "review-protocol.schema.json"
    )
    definition = deepcopy(schema["$defs"][name])
    definition.pop("$id", None)
    definition["$schema"] = schema["$schema"]
    definition["$defs"] = schema["$defs"]
    return definition


def _validate_timestamp(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StructureMapReviewError(f"{field} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise StructureMapReviewError(f"{field} must include a timezone")


def build_confirmation_receipt(
    packet: dict[str, Any],
    decision: dict[str, Any],
    *,
    applied_at: str,
) -> dict[str, Any]:
    """Validate one all-approved human decision and build its confirmation."""

    _validate_timestamp(applied_at, "applied_at")
    if packet.get("review_id") != REVIEW_ID or decision.get("review_id") != REVIEW_ID:
        raise StructureMapReviewError("packet and decision review_id must match the P2 gate")

    finding_by_id = {
        finding["id"]: finding
        for finding in packet.get("findings", [])
        if not finding.get("auto_approved", False)
    }
    decisions = decision.get("decisions", [])
    decision_ids = [item.get("finding_id") for item in decisions]
    if len(decision_ids) != len(set(decision_ids)):
        raise StructureMapReviewError("DecisionReceipt contains duplicate finding decisions")
    if set(decision_ids) != set(finding_by_id):
        missing = sorted(set(finding_by_id) - set(decision_ids))
        unknown = sorted(set(decision_ids) - set(finding_by_id))
        raise StructureMapReviewError(
            f"DecisionReceipt coverage mismatch; missing={missing}, unknown={unknown}"
        )
    non_approved = [
        item["finding_id"] for item in decisions if item.get("decision") != "approved"
    ]
    if non_approved:
        raise StructureMapReviewError(
            "P2 structure baseline requires rework for non-approved findings: "
            + ", ".join(sorted(non_approved))
        )

    ordered = sorted(decisions, key=lambda item: item["finding_id"])
    results = [
        {
            "finding_id": item["finding_id"],
            "original_decision": "approved",
            "application_status": "applied",
            "actual_value": (
                "已批准结构地图基线："
                + str(finding_by_id[item["finding_id"]]["proposed_value"])
            ),
        }
        for item in ordered
    ]
    return {
        "review_id": REVIEW_ID,
        "applied_at": applied_at,
        "generated_by": "P6-P2 结构地图审核应用器",
        "results": results,
        "summary": {
            "total": len(results),
            "applied": len(results),
            "adjusted": 0,
            "failed": 0,
        },
    }


def _audit_event(decision: dict[str, Any], confirmation: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": AUDIT_EVENT_ID,
        "event_type": "structure_map_approval_applied",
        "timestamp": confirmation["applied_at"],
        "record_id": "structure-map-sdtmig34",
        "review_id": REVIEW_ID,
        "approval_receipt_id": "review-sdtmig34-structure-v1-001",
        "decision_file": DECISION_NAME,
        "confirmation_file": CONFIRMATION_NAME,
        "actor": decision["reviewer"],
        "applied_by": confirmation["generated_by"],
        "result": "applied",
        "scope": "P2 navigation structure and Core/Events/AE locator baseline only",
    }


def _audit_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise StructureMapReviewError(
                f"audit trail contains invalid JSON on line {line_number}"
            ) from exc
        if not isinstance(event, dict):
            raise StructureMapReviewError(
                f"audit trail event on line {line_number} is not an object"
            )
        events.append(event)
    return events


def _require_audit_event(path: Path, expected: dict[str, Any]) -> None:
    matches = [event for event in _audit_events(path) if event.get("event_id") == AUDIT_EVENT_ID]
    if len(matches) != 1 or matches[0] != expected:
        raise StructureMapReviewError(
            f"audit event {AUDIT_EVENT_ID} must exist exactly once and match the receipt"
        )


def _validate_triplet(
    root: Path,
    packet: dict[str, Any],
    decision: dict[str, Any],
    confirmation: dict[str, Any],
) -> None:
    for name, payload in (
        ("review_packet", packet),
        ("decision_receipt", decision),
        ("confirmation_receipt", confirmation),
    ):
        Draft202012Validator(_schema_definition(root, name)).validate(payload)
    expected_ids = {finding["id"] for finding in packet["findings"]}
    if {item["finding_id"] for item in decision["decisions"]} != expected_ids:
        raise StructureMapReviewError("archived DecisionReceipt does not cover the packet")
    if {item["finding_id"] for item in confirmation["results"]} != expected_ids:
        raise StructureMapReviewError("archived ConfirmationReceipt does not cover the packet")
    if confirmation["summary"] != {
        "total": len(expected_ids),
        "applied": len(expected_ids),
        "adjusted": 0,
        "failed": 0,
    }:
        raise StructureMapReviewError("archived confirmation summary is inconsistent")


def finalize_structure_review(
    wiki_root: str | Path,
    *,
    applied_at: str | None = None,
    write: bool,
) -> dict[str, Any]:
    """Finalize once, or verify the already-finalized triplet in check mode."""

    root = Path(wiki_root).resolve()
    queue = root / ".review_queue"
    archive = queue / "archive"
    active_paths = {
        "packet": queue / PACKET_NAME,
        "decision": queue / DECISION_NAME,
        "confirmation": queue / CONFIRMATION_NAME,
    }
    archive_paths = {
        name: archive / path.name for name, path in active_paths.items()
    }
    audit_path = root / "audit_trail.jsonl"

    if all(path.is_file() for path in archive_paths.values()) and not any(
        path.exists() for path in active_paths.values()
    ):
        packet = _read_json(archive_paths["packet"])
        decision = _read_json(archive_paths["decision"])
        confirmation = _read_json(archive_paths["confirmation"])
        _validate_triplet(root, packet, decision, confirmation)
        _require_audit_event(audit_path, _audit_event(decision, confirmation))
        return confirmation

    if not write:
        raise StructureMapReviewError("P2 structure review is not fully archived")
    if applied_at is None:
        raise StructureMapReviewError("applied_at is required when finalizing")
    if any(path.exists() for path in archive_paths.values()):
        raise StructureMapReviewError("partial archive exists; refusing to overwrite evidence")
    if active_paths["confirmation"].exists():
        raise StructureMapReviewError("active ConfirmationReceipt already exists")

    packet = _read_json(active_paths["packet"])
    decision = _read_json(active_paths["decision"])
    Draft202012Validator(_schema_definition(root, "review_packet")).validate(packet)
    Draft202012Validator(_schema_definition(root, "decision_receipt")).validate(decision)

    report, expected_packet = build_structure_review_artifacts(
        root,
        created_at=packet["created_at"],
        packet_language="en",
    )
    committed_report = _read_json(root / PACKAGE_RELATIVE_PATH / REPORT_NAME)
    if report != committed_report:
        raise StructureMapReviewError("structure review report drifted after human review")
    if expected_packet != packet:
        raise StructureMapReviewError("ReviewPacket drifted after human review")

    confirmation = build_confirmation_receipt(packet, decision, applied_at=applied_at)
    Draft202012Validator(_schema_definition(root, "confirmation_receipt")).validate(
        confirmation
    )
    audit_event = _audit_event(decision, confirmation)
    if any(event.get("event_id") == AUDIT_EVENT_ID for event in _audit_events(audit_path)):
        raise StructureMapReviewError(f"audit event already exists: {AUDIT_EVENT_ID}")

    temporary = active_paths["confirmation"].with_suffix(".json.tmp")
    if temporary.exists():
        raise StructureMapReviewError(f"temporary confirmation already exists: {temporary}")
    temporary.write_text(
        json.dumps(confirmation, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(active_paths["confirmation"])
    archive.mkdir(parents=True, exist_ok=True)
    for name in ("packet", "decision", "confirmation"):
        active_paths[name].replace(archive_paths[name])
    with audit_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(audit_event, ensure_ascii=False, separators=(",", ":")) + "\n")

    _validate_triplet(
        root,
        _read_json(archive_paths["packet"]),
        _read_json(archive_paths["decision"]),
        _read_json(archive_paths["confirmation"]),
    )
    _require_audit_event(audit_path, audit_event)
    return confirmation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-root", type=Path, default=Path.cwd())
    parser.add_argument("--applied-at")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    confirmation = finalize_structure_review(
        args.wiki_root,
        applied_at=args.applied_at,
        write=not args.check,
    )
    print(json.dumps(confirmation["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
