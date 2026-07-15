"""Apply and archive the human-approved P6-P3 SDTMIG 3.4 proposal review.

P3-D opens a blocking ReviewPacket over 28 Core/Events/AE proposal statements.
This finalizer closes that gate only after a complete all-approved
DecisionReceipt exists.  It keeps the original proposed batches immutable and
writes a separate approved release artifact for P4 relation/card work.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from scripts.content.extraction_contract import validate_extraction_package
from scripts.content.sdtmig34_core_proposals import (
    DEFAULT_BATCH as CORE_BATCH,
    DEFAULT_REPORT as CORE_REPORT,
    canonical_json_bytes,
    sha256_payload,
    write_json,
)
from scripts.content.sdtmig34_gold_calibration import (
    DEFAULT_BATCH as GOLD_BATCH,
    DEFAULT_REPORT as GOLD_REPORT,
)
from scripts.content.sdtmig34_proposal_review import (
    DEFAULT_PACKAGE,
    DEFAULT_REVIEW_REPORT,
    PACKET_NAME,
    REVIEW_ID,
    ProposalReviewError,
    build_proposal_review_artifacts,
    schema_definition,
)


DECISION_NAME = f"{REVIEW_ID}_decision.json"
CONFIRMATION_NAME = f"{REVIEW_ID}_confirmation.json"
APPROVAL_RECEIPT_ID = "review-sdtm-spec-sdtmig34-proposals-v1-001"
AUDIT_EVENT_ID = "wiki-audit-20260715-sdtmig34-proposals-v1-001"
RELEASE_ID = "release-sdtmig34-proposals-v1"
RELEASE_PACKAGE_ID = "pkg-sdtmig34-approved-proposals-v1"
DEFAULT_RELEASE = DEFAULT_PACKAGE / "approved-proposal-release.json"
DEFAULT_RELEASE_CARD = (
    Path(__file__).resolve().parents[2]
    / "vault"
    / "60_Sources"
    / "Registry"
    / "SDTMIG 3.4 Approved Proposal Release.md"
)
DEFAULT_GOVERNANCE_RECEIPT = (
    Path(__file__).resolve().parents[2]
    / "vault"
    / "80_Governance"
    / "Review-Receipts"
    / "sdtmig34-proposals-v1-001.md"
)
SOURCES_MOC = Path(__file__).resolve().parents[2] / "vault" / "10_MOC" / "Sources-MOC.md"
GENERATED_BY = "P6-P3-E SDTMIG 3.4 知识候选审核应用器"


class ProposalFinalizeError(ProposalReviewError):
    """Raised when the proposal approval gate cannot be safely closed."""


def _wiki_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ProposalFinalizeError(f"required artifact is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ProposalFinalizeError(f"artifact is invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ProposalFinalizeError(f"artifact must be a JSON object: {path}")
    return payload


def _validate_timestamp(value: str, field: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProposalFinalizeError(f"{field} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ProposalFinalizeError(f"{field} must include a timezone")


def _finding_statement_id(finding: dict[str, Any]) -> str:
    location = str(finding.get("location", ""))
    prefix = "proposal-review#"
    if not location.startswith(prefix):
        raise ProposalFinalizeError(f"finding location is not a proposal target: {location}")
    statement_id = location.removeprefix(prefix)
    evidence_refs = finding.get("evidence_refs", [])
    if f"proposal:{statement_id}" not in evidence_refs:
        raise ProposalFinalizeError(
            f"finding {finding.get('id')} does not cite its proposal id"
        )
    return statement_id


def build_all_approved_decision_receipt(
    packet: dict[str, Any],
    *,
    reviewer: str,
    reviewer_role: str,
    timestamp: str,
    general_notes: str,
) -> dict[str, Any]:
    """Create a structured DecisionReceipt from an explicit all-approved review."""

    _validate_timestamp(timestamp, "timestamp")
    if packet.get("review_id") != REVIEW_ID:
        raise ProposalFinalizeError("packet review_id does not match P3 proposal gate")
    decisions = [
        {"finding_id": finding["id"], "decision": "approved"}
        for finding in sorted(packet["findings"], key=lambda item: item["id"])
        if not finding.get("auto_approved", False)
    ]
    receipt = {
        "review_id": REVIEW_ID,
        "reviewer": reviewer,
        "reviewer_role": reviewer_role,
        "timestamp": timestamp,
        "decisions": decisions,
        "general_notes": general_notes,
    }
    Draft202012Validator(schema_definition(_wiki_root(), "decision_receipt")).validate(receipt)
    return receipt


def _decision_coverage(
    packet: dict[str, Any], decision: dict[str, Any]
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if packet.get("review_id") != REVIEW_ID or decision.get("review_id") != REVIEW_ID:
        raise ProposalFinalizeError("packet and decision review_id must match the P3 gate")
    finding_by_id = {
        finding["id"]: finding
        for finding in packet.get("findings", [])
        if not finding.get("auto_approved", False)
    }
    decisions = list(decision.get("decisions", []))
    decision_ids = [item.get("finding_id") for item in decisions]
    if len(decision_ids) != len(set(decision_ids)):
        raise ProposalFinalizeError("DecisionReceipt contains duplicate finding decisions")
    if set(decision_ids) != set(finding_by_id):
        missing = sorted(set(finding_by_id) - set(decision_ids))
        unknown = sorted(set(decision_ids) - set(finding_by_id))
        raise ProposalFinalizeError(
            f"DecisionReceipt coverage mismatch; missing={missing}, unknown={unknown}"
        )
    non_approved = [
        item["finding_id"] for item in decisions if item.get("decision") != "approved"
    ]
    if non_approved:
        raise ProposalFinalizeError(
            "P3 approved release requires rework for non-approved findings: "
            + ", ".join(sorted(non_approved))
        )
    return finding_by_id, sorted(decisions, key=lambda item: item["finding_id"])


def _merge_unique(
    output: list[dict[str, Any]], seen: dict[str, dict[str, Any]], key: str, item: dict[str, Any]
) -> None:
    item_id = item[key]
    existing = seen.get(item_id)
    if existing is not None:
        if existing != item:
            raise ProposalFinalizeError(f"conflicting duplicate {key}: {item_id}")
        return
    copied = deepcopy(item)
    seen[item_id] = copied
    output.append(copied)


def _approved_release_package(
    *,
    packet: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    finding_by_id, decisions = _decision_coverage(packet, decision)
    approved_statement_ids = {
        _finding_statement_id(finding_by_id[item["finding_id"]]) for item in decisions
    }
    batches = [_read_json(CORE_BATCH), _read_json(GOLD_BATCH)]
    source_ids = {batch["source_id"] for batch in batches}
    source_hashes = {batch["source_sha256"] for batch in batches}
    map_ids = {batch["structure_map_id"] for batch in batches}
    map_hashes = {batch["structure_map_sha256"] for batch in batches}
    if len(source_ids) != 1 or len(source_hashes) != 1 or len(map_ids) != 1 or len(map_hashes) != 1:
        raise ProposalFinalizeError("proposal batches do not share source and structure identity")

    artifacts: list[dict[str, Any]] = []
    units: list[dict[str, Any]] = []
    statements: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    seen_artifacts: dict[str, dict[str, Any]] = {}
    seen_units: dict[str, dict[str, Any]] = {}
    seen_statements: dict[str, dict[str, Any]] = {}
    seen_relations: dict[str, dict[str, Any]] = {}

    for batch in batches:
        package = batch["extraction_package"]
        for artifact in package["artifacts"]:
            _merge_unique(artifacts, seen_artifacts, "artifact_id", artifact)
        for unit in package["units"]:
            _merge_unique(units, seen_units, "unit_id", unit)
        for relation in package["relations"]:
            _merge_unique(relations, seen_relations, "relation_id", relation)
        for statement in package["statements"]:
            copied = deepcopy(statement)
            if copied["statement_id"] in approved_statement_ids:
                copied["review_status"] = "approved"
                copied["review_receipt_id"] = APPROVAL_RECEIPT_ID
                _merge_unique(statements, seen_statements, "statement_id", copied)

    if set(seen_statements) != approved_statement_ids:
        missing = sorted(approved_statement_ids - set(seen_statements))
        raise ProposalFinalizeError(f"approved release missed statements: {missing}")

    package = {
        "schema_version": "1.0.0",
        "package_id": RELEASE_PACKAGE_ID,
        "source_id": next(iter(source_ids)),
        "source_sha256": next(iter(source_hashes)),
        "artifacts": artifacts,
        "units": units,
        "statements": statements,
        "relations": relations,
    }
    validate_extraction_package(package)
    return package


def build_confirmation_receipt(
    packet: dict[str, Any],
    decision: dict[str, Any],
    release_package: dict[str, Any],
    *,
    applied_at: str,
) -> dict[str, Any]:
    """Validate the all-approved decision and build an application receipt."""

    _validate_timestamp(applied_at, "applied_at")
    finding_by_id, decisions = _decision_coverage(packet, decision)
    approved = {statement["statement_id"]: statement for statement in release_package["statements"]}
    results = []
    for item in decisions:
        finding = finding_by_id[item["finding_id"]]
        statement_id = _finding_statement_id(finding)
        if statement_id not in approved:
            raise ProposalFinalizeError(f"approved statement missing from release: {statement_id}")
        results.append(
            {
                "finding_id": item["finding_id"],
                "original_decision": "approved",
                "application_status": "applied",
                "actual_value": (
                    f"已批准 {statement_id}；review_status=approved；"
                    f"review_receipt_id={APPROVAL_RECEIPT_ID}"
                ),
            }
        )
    confirmation = {
        "review_id": REVIEW_ID,
        "applied_at": applied_at,
        "generated_by": GENERATED_BY,
        "results": results,
        "summary": {
            "total": len(results),
            "applied": len(results),
            "adjusted": 0,
            "failed": 0,
        },
    }
    Draft202012Validator(schema_definition(_wiki_root(), "confirmation_receipt")).validate(
        confirmation
    )
    return confirmation


def _release_artifact(
    *,
    release_package: dict[str, Any],
    decision: dict[str, Any],
    confirmation: dict[str, Any],
) -> dict[str, Any]:
    core_batch = _read_json(CORE_BATCH)
    gold_batch = _read_json(GOLD_BATCH)
    return {
        "schema_version": "1.0.0",
        "release_id": RELEASE_ID,
        "review_id": REVIEW_ID,
        "approval_receipt_id": APPROVAL_RECEIPT_ID,
        "created_at": confirmation["applied_at"],
        "source_id": release_package["source_id"],
        "source_sha256": release_package["source_sha256"],
        "structure_map_id": core_batch["structure_map_id"],
        "structure_map_sha256": core_batch["structure_map_sha256"],
        "input_batches": [
            {
                "label": "core",
                "batch_id": core_batch["batch_id"],
                "package_id": core_batch["extraction_package"]["package_id"],
                "batch_sha256": sha256_payload(core_batch),
                "report_sha256": sha256_payload(_read_json(CORE_REPORT)),
                "statement_count": len(core_batch["extraction_package"]["statements"]),
            },
            {
                "label": "events_ae",
                "batch_id": gold_batch["batch_id"],
                "package_id": gold_batch["extraction_package"]["package_id"],
                "batch_sha256": sha256_payload(gold_batch),
                "report_sha256": sha256_payload(_read_json(GOLD_REPORT)),
                "statement_count": len(gold_batch["extraction_package"]["statements"]),
            },
        ],
        "decision_receipt": f".review_queue/archive/{DECISION_NAME}",
        "confirmation_receipt": f".review_queue/archive/{CONFIRMATION_NAME}",
        "reviewer": decision["reviewer"],
        "reviewer_role": decision.get("reviewer_role"),
        "approved_package_sha256": sha256_payload(release_package),
        "approved_statement_count": len(release_package["statements"]),
        "approved_status_counts": {"approved": len(release_package["statements"])},
        "runtime_boundary": (
            "Approved extraction release for P4 relation/card work; production "
            "Runtime knowledge cards are created in a later phase."
        ),
        "extraction_package": release_package,
    }


def _audit_event(decision: dict[str, Any], confirmation: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": AUDIT_EVENT_ID,
        "event_type": "sdtmig34_proposal_release_applied",
        "timestamp": confirmation["applied_at"],
        "record_id": RELEASE_ID,
        "review_id": REVIEW_ID,
        "approval_receipt_id": APPROVAL_RECEIPT_ID,
        "decision_file": DECISION_NAME,
        "confirmation_file": CONFIRMATION_NAME,
        "release_file": DEFAULT_RELEASE.relative_to(_wiki_root()).as_posix(),
        "actor": decision["reviewer"],
        "applied_by": confirmation["generated_by"],
        "result": "applied",
        "scope": "P6-P3 Core/Events/AE proposal release; governed runtime cards deferred to P4",
        "audit_reference": AUDIT_EVENT_ID,
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
            raise ProposalFinalizeError(
                f"audit trail contains invalid JSON on line {line_number}"
            ) from exc
        if not isinstance(event, dict):
            raise ProposalFinalizeError(f"audit event on line {line_number} is not an object")
        events.append(event)
    return events


def _require_audit_event(path: Path, expected: dict[str, Any]) -> None:
    matches = [event for event in _audit_events(path) if event.get("event_id") == AUDIT_EVENT_ID]
    if len(matches) != 1 or matches[0] != expected:
        raise ProposalFinalizeError(
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
        Draft202012Validator(schema_definition(root, name)).validate(payload)
    finding_ids = {
        finding["id"] for finding in packet["findings"] if not finding.get("auto_approved", False)
    }
    if {item["finding_id"] for item in decision["decisions"]} != finding_ids:
        raise ProposalFinalizeError("archived DecisionReceipt does not cover the packet")
    if {item["finding_id"] for item in confirmation["results"]} != finding_ids:
        raise ProposalFinalizeError("archived ConfirmationReceipt does not cover the packet")
    if confirmation["summary"] != {
        "total": len(finding_ids),
        "applied": len(finding_ids),
        "adjusted": 0,
        "failed": 0,
    }:
        raise ProposalFinalizeError("archived confirmation summary is inconsistent")


def _validate_release(release: dict[str, Any]) -> None:
    package = release["extraction_package"]
    validate_extraction_package(package)
    if release["approved_package_sha256"] != sha256_payload(package):
        raise ProposalFinalizeError("approved package hash drifted")
    if release["approved_statement_count"] != len(package["statements"]):
        raise ProposalFinalizeError("approved statement count drifted")
    if {statement["review_status"] for statement in package["statements"]} != {"approved"}:
        raise ProposalFinalizeError("release package contains non-approved statements")
    if {
        statement["review_receipt_id"] for statement in package["statements"]
    } != {APPROVAL_RECEIPT_ID}:
        raise ProposalFinalizeError("release package is not bound to the approval receipt")


def _release_card(release: dict[str, Any], confirmation: dict[str, Any]) -> str:
    package = release["extraction_package"]
    rows = "\n".join(
        "| {statement_id} | {subject} | {knowledge_type} | {modality} |".format(**statement)
        for statement in sorted(package["statements"], key=lambda item: item["statement_id"])
    )
    return f"""---
id: {RELEASE_ID}
type: knowledge_proposal_release
title: SDTMIG 3.4 Approved Proposal Release
review_id: {REVIEW_ID}
approval_receipt_id: {APPROVAL_RECEIPT_ID}
approval_status: approved
content_status: reviewed
statement_count: {release["approved_statement_count"]}
created: '{confirmation["applied_at"]}'
---

# SDTMIG 3.4 Approved Proposal Release

本卡是 P6-P3-E 的 Obsidian 审阅入口，记录 Core/Events/AE 的 28 条候选已完成结构化人工批准。机器可验证 release 保存在：

`clinical-llm-wiki/{DEFAULT_RELEASE.relative_to(_wiki_root()).as_posix()}`

## 边界

- 本 release 证明 28 条 proposal 的语义、范围、条件、例外和 locator 已获本地知识治理批准。
- 原始 P3-B/P3-C proposal batch 仍保持 proposed-only，供重建和漂移检查。
- 本卡不是逐条 runtime governed knowledge card；P4 才会把 release 拆成可复用知识卡与 typed relation 图谱。
- 原始 PDF/XLSX 不进入 Vault；引用继续通过 source package locator 与 [[60_Sources/Registry/CDISC SDTMIG 3.4]] 定位。

## 审核证据

- ReviewPacket：`.review_queue/archive/{PACKET_NAME}`
- DecisionReceipt：`.review_queue/archive/{DECISION_NAME}`
- ConfirmationReceipt：`.review_queue/archive/{CONFIRMATION_NAME}`
- Audit event：`{AUDIT_EVENT_ID}`

## 已批准 statement 索引

| Statement | Subject | Type | Modality |
|---|---|---|---|
{rows}
"""


def _governance_receipt_card(decision: dict[str, Any], confirmation: dict[str, Any]) -> str:
    return f"""# SDTMIG 3.4 Proposal Release Approval

本记录对应 P6-P3-E，覆盖 `sdtm_spec_sdtmig34_proposals_v1_001` 的 F-001 至 F-028。

## 批准语义

- 审核人：{decision["reviewer"]}
- 审核角色：{decision.get("reviewer_role", "not_specified")}
- DecisionReceipt 时间：{decision["timestamp"]}
- ConfirmationReceipt 时间：{confirmation["applied_at"]}
- 28 条 finding 全部为 `approved`，应用结果全部为 `applied`。
- 本批准只关闭 SDTMIG 3.4 Core/Events/AE proposal release；P4 前不声明逐条 Runtime governed card 已完成。
- 它不代表 Sponsor、医学、统计、监管或 GxP 项目审批，真实 Study 使用前仍需 Study 级 Review。

## 证据

- ReviewPacket：`.review_queue/archive/{PACKET_NAME}`
- DecisionReceipt：`.review_queue/archive/{DECISION_NAME}`
- ConfirmationReceipt：`.review_queue/archive/{CONFIRMATION_NAME}`
- Release artifact：`{DEFAULT_RELEASE.relative_to(_wiki_root()).as_posix()}`
- Audit event：`{AUDIT_EVENT_ID}`
"""


def _update_sources_moc() -> None:
    text = SOURCES_MOC.read_text(encoding="utf-8")
    old = """## P6 解析候选

- [[98_Inbox/SDTMIG 3.4 Core Proposal Batch|SDTMIG 3.4 Core 小批次候选]]

候选卡只用于治理审阅，不进入 approved-only 索引。
"""
    new = """## P6 SDTMIG 3.4 解析 release

- [[60_Sources/Registry/SDTMIG 3.4 Approved Proposal Release|SDTMIG 3.4 Core/Events/AE 已批准 proposal release]]
- [[98_Inbox/SDTMIG 3.4 Core Proposal Batch|SDTMIG 3.4 Core 小批次候选输入]]

Release 卡是 P6-P3-E 的 Obsidian 审阅入口；逐条 Runtime governed knowledge card 与 typed relation 图谱在 P4 整理。
"""
    if new in text:
        return
    if old not in text:
        raise ProposalFinalizeError("Sources-MOC P6 section did not match expected text")
    SOURCES_MOC.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.strip() + "\n", encoding="utf-8", newline="\n")


def _verify_generated_docs() -> None:
    if not DEFAULT_RELEASE_CARD.is_file():
        raise ProposalFinalizeError("release Obsidian card is missing")
    if not DEFAULT_GOVERNANCE_RECEIPT.is_file():
        raise ProposalFinalizeError("governance receipt card is missing")
    if "SDTMIG 3.4 Approved Proposal Release" not in SOURCES_MOC.read_text(encoding="utf-8"):
        raise ProposalFinalizeError("Sources-MOC does not link the approved release")


def finalize_proposal_review(
    wiki_root: str | Path,
    *,
    applied_at: str | None = None,
    write: bool,
    approve_all: bool = False,
    reviewer: str = "Human Knowledge Owner (Codex task user)",
    reviewer_role: str = "human_knowledge_owner",
    decision_timestamp: str | None = None,
) -> dict[str, Any]:
    """Finalize once, or verify the already-finalized P3 proposal release."""

    root = Path(wiki_root).resolve()
    if root != _wiki_root():
        raise ProposalFinalizeError("P3 proposal finalizer must run against clinical-llm-wiki root")
    queue = root / ".review_queue"
    archive = queue / "archive"
    active_paths = {
        "packet": queue / PACKET_NAME,
        "decision": queue / DECISION_NAME,
        "confirmation": queue / CONFIRMATION_NAME,
    }
    archive_paths = {name: archive / path.name for name, path in active_paths.items()}
    audit_path = root / "audit_trail.jsonl"

    if all(path.is_file() for path in archive_paths.values()) and not any(
        path.exists() for path in active_paths.values()
    ):
        packet = _read_json(archive_paths["packet"])
        decision = _read_json(archive_paths["decision"])
        confirmation = _read_json(archive_paths["confirmation"])
        release = _read_json(DEFAULT_RELEASE)
        _validate_triplet(root, packet, decision, confirmation)
        _validate_release(release)
        _require_audit_event(audit_path, _audit_event(decision, confirmation))
        _verify_generated_docs()
        return confirmation

    if not write:
        raise ProposalFinalizeError("P3 proposal review is not fully archived")
    if applied_at is None:
        raise ProposalFinalizeError("applied_at is required when finalizing")
    _validate_timestamp(applied_at, "applied_at")
    if any(path.exists() for path in archive_paths.values()):
        raise ProposalFinalizeError("partial archive exists; refusing to overwrite evidence")
    if active_paths["confirmation"].exists():
        raise ProposalFinalizeError("active ConfirmationReceipt already exists")
    if DEFAULT_RELEASE.exists():
        raise ProposalFinalizeError("approved release already exists")

    packet = _read_json(active_paths["packet"])
    Draft202012Validator(schema_definition(root, "review_packet")).validate(packet)
    expected_report, expected_packet = build_proposal_review_artifacts(
        wiki_root=root,
        created_at=packet["created_at"],
    )
    if expected_report != _read_json(DEFAULT_REVIEW_REPORT):
        raise ProposalFinalizeError("proposal review report drifted after human review")
    if expected_packet != packet:
        raise ProposalFinalizeError("ReviewPacket drifted after human review")

    if approve_all:
        if active_paths["decision"].exists():
            raise ProposalFinalizeError("DecisionReceipt already exists; refusing approve-all overwrite")
        if decision_timestamp is None:
            raise ProposalFinalizeError("decision_timestamp is required for approve-all")
        decision = build_all_approved_decision_receipt(
            packet,
            reviewer=reviewer,
            reviewer_role=reviewer_role,
            timestamp=decision_timestamp,
            general_notes=(
                "用户在 Codex task 中明确回复“全部同意，继续下一步”，授权 "
                "F-001 至 F-028 全部批准；本批准仅关闭 P6-P3 proposal release，"
                "不代表 Sponsor、监管、GxP 或真实 Study 审批。"
            ),
        )
        write_json(active_paths["decision"], decision)
    else:
        decision = _read_json(active_paths["decision"])
    Draft202012Validator(schema_definition(root, "decision_receipt")).validate(decision)

    release_package = _approved_release_package(packet=packet, decision=decision)
    confirmation = build_confirmation_receipt(
        packet,
        decision,
        release_package,
        applied_at=applied_at,
    )
    release = _release_artifact(
        release_package=release_package,
        decision=decision,
        confirmation=confirmation,
    )
    _validate_release(release)
    audit_event = _audit_event(decision, confirmation)
    if any(event.get("event_id") == AUDIT_EVENT_ID for event in _audit_events(audit_path)):
        raise ProposalFinalizeError(f"audit event already exists: {AUDIT_EVENT_ID}")

    temporary = active_paths["confirmation"].with_suffix(".json.tmp")
    if temporary.exists():
        raise ProposalFinalizeError(f"temporary confirmation already exists: {temporary}")
    temporary.write_bytes(canonical_json_bytes(confirmation))
    temporary.replace(active_paths["confirmation"])
    write_json(DEFAULT_RELEASE, release)
    _write_text(DEFAULT_RELEASE_CARD, _release_card(release, confirmation))
    _write_text(DEFAULT_GOVERNANCE_RECEIPT, _governance_receipt_card(decision, confirmation))
    _update_sources_moc()

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
    _validate_release(_read_json(DEFAULT_RELEASE))
    _require_audit_event(audit_path, audit_event)
    _verify_generated_docs()
    return confirmation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-root", type=Path, default=_wiki_root())
    parser.add_argument("--applied-at")
    parser.add_argument("--decision-timestamp")
    parser.add_argument("--reviewer", default="Human Knowledge Owner (Codex task user)")
    parser.add_argument("--reviewer-role", default="human_knowledge_owner")
    parser.add_argument("--approve-all", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    confirmation = finalize_proposal_review(
        args.wiki_root,
        applied_at=args.applied_at,
        write=not args.check,
        approve_all=args.approve_all,
        reviewer=args.reviewer,
        reviewer_role=args.reviewer_role,
        decision_timestamp=args.decision_timestamp,
    )
    print(json.dumps(confirmation["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProposalFinalizeError as error:
        raise SystemExit(f"Proposal review finalize failed: {error}") from error
