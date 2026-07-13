"""Finalize hashes and synthetic-pilot governance evidence for P5 content.

This utility does not impersonate a human reviewer.  Its DecisionReceipt is a
deliberately labelled non-human fixture that approves records only for the P5
synthetic pilot and contract/integration testing.  Regulated use still requires
the normal human Review Protocol.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from service.contracts import SchemaBundle, canonical_json_sha256
from service.repository import RepositoryError, parse_markdown_card


ROOT = Path(__file__).resolve().parents[2]
VAULT = ROOT / "vault"
REVIEW_ARCHIVE = ROOT / ".review_queue" / "archive"
OLD_RECEIPT_ID = "review-p5-core-content-v1-001"
RECEIPT_ID = "review-knowledge-p5-core-v1-001"
REVIEW_ID = "knowledge_p5_core_v1_001"
AUDIT_REFERENCE = "vault/80_Governance/Review-Receipts/p5-core-content-approval.md"
SYNTHETIC_STUDY_ID = "SYNTH-ONCO-001"
SYNTHETIC_PILOT_CONDITION = "synthetic-pilot-only"
GOVERNED_TYPES = {
    "concept", "method", "standard_rule", "decision_rule", "programming_pattern",
    "deliverable_pattern", "prior_study_pattern", "workflow_playbook", "source_record",
    "figure_record",
}


def _serialized_card(record: dict[str, Any], body: str) -> str:
    frontmatter = yaml.safe_dump(record, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{frontmatter}\n---\n\n{body.strip()}\n"


def _release_records(*, write: bool) -> list[tuple[Path, dict[str, Any], str]]:
    released: list[tuple[Path, dict[str, Any], str]] = []
    mismatches: list[str] = []
    for path in sorted(VAULT.rglob("*.md")):
        if "90_System" in path.parts and "Templates" in path.parts:
            continue
        try:
            record, body = parse_markdown_card(ROOT, path)
        except RepositoryError:
            continue
        if record.get("type") not in GOVERNED_TYPES:
            continue
        if record.get("approval_receipt_id") == OLD_RECEIPT_ID:
            record["approval_receipt_id"] = RECEIPT_ID
        if record.get("approval_receipt_id") == RECEIPT_ID:
            applicability = record.get("applicability")
            if not isinstance(applicability, dict):
                raise RuntimeError(f"P5 release record has no applicability object: {record['id']}")
            applicability["study_ids"] = [SYNTHETIC_STUDY_ID]
            if not isinstance(applicability.get("conditions"), list):
                raise RuntimeError(f"P5 release record has invalid conditions: {record['id']}")
            applicability["conditions"] = [SYNTHETIC_PILOT_CONDITION]
        expected_hash = canonical_json_sha256({
            "frontmatter": {key: value for key, value in record.items() if key != "content_hash"},
            "body": body,
        })
        record["content_hash"] = expected_hash
        expected = _serialized_card(record, body)
        actual = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if actual != expected:
            if write:
                path.write_text(expected, encoding="utf-8")
            else:
                mismatches.append(path.relative_to(ROOT).as_posix())
        if record.get("approval_receipt_id") == RECEIPT_ID:
            if record.get("approval_status") != "approved" or record.get("content_status") != "verified":
                raise RuntimeError(f"P5 release record is not verified+approved: {record['id']}")
            if record.get("audit_reference") != AUDIT_REFERENCE:
                raise RuntimeError(f"P5 release record has unexpected audit reference: {record['id']}")
            released.append((path, record, body))
    if mismatches:
        raise RuntimeError("P5 generated content is stale: " + ", ".join(mismatches))
    return released


def _governance_payloads(
    released: list[tuple[Path, dict[str, Any], str]], bundle: SchemaBundle
) -> dict[Path, str]:
    ordered = sorted(released, key=lambda item: str(item[1]["id"]))
    findings: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for number, (path, record, _) in enumerate(ordered, start=1):
        finding_id = f"F-{number:03d}"
        record_id = str(record["id"])
        findings.append({
            "id": finding_id,
            "category": "compliance",
            "severity": "info",
            "location": record_id,
            "title": f"Release {record_id} to the P5 synthetic pilot",
            "current_value": "verified candidate",
            "proposed_value": "approved for synthetic pilot and contract testing",
            "rationale": "The P5 plan requires a governed representative baseline with explicit non-production scope.",
            "evidence_refs": list(record.get("sources", [])) or [record_id],
            "auto_approved": False,
        })
        decisions.append({
            "finding_id": finding_id,
            "decision": "approved",
            "comment": "Synthetic-pilot fixture only; human GxP approval is still required for regulated use.",
        })
        results.append({
            "finding_id": finding_id,
            "original_decision": "approved",
            "application_status": "applied",
            "actual_value": record_id,
        })
    packet = {
        "review_id": REVIEW_ID,
        "review_type": "sap_review",
        "source_documents": [path.relative_to(ROOT).as_posix() for path, _, _ in ordered],
        "agent_summary": "P5 representative content release for the synthetic longitudinal pilot; not a regulated human approval.",
        "findings": findings,
        "urgency": "normal",
        "created_at": "2026-07-13T16:50:00+08:00",
        "generated_by": "scripts.content.finalize_p5_content",
        "auto_approved_count": 0,
    }
    decision = {
        "review_id": REVIEW_ID,
        "reviewer": "P5 Synthetic Governance Fixture",
        "reviewer_role": "non_human_test_fixture",
        "timestamp": "2026-07-13T16:55:00+08:00",
        "decisions": decisions,
        "general_notes": "This receipt is intentionally non-human and only closes the P5 synthetic test loop. It cannot satisfy Sponsor, regulatory, or GxP human-review requirements.",
    }
    confirmation = {
        "review_id": REVIEW_ID,
        "applied_at": "2026-07-13T17:00:00+08:00",
        "generated_by": "scripts.content.finalize_p5_content",
        "results": results,
        "summary": {"total": len(results), "applied": len(results), "adjusted": 0, "failed": 0},
    }
    bundle.validate_definition("review/review-protocol.schema.json", "review_packet", packet)
    bundle.validate_definition("review/review-protocol.schema.json", "decision_receipt", decision)
    bundle.validate_definition("review/review-protocol.schema.json", "confirmation_receipt", confirmation)
    governance_note = f"""# P5 核心内容合成试点批准记录

本记录服务于 `SYNTH-ONCO-001` 的 P5 纵向合成试点和合同测试，共覆盖 {len(ordered)} 个 verified 条目。

## 批准语义

- `DecisionReceipt` 的 reviewer 明确为 **non-human test fixture**。
- `approved` 只表示可以进入本地 P5 合成试点的 approved-only 索引。
- 机器范围固定为 `applicability.study_ids: [{SYNTHETIC_STUDY_ID}]`，且 `conditions` 必须包含 `{SYNTHETIC_PILOT_CONDITION}`。
- 它不代表 Sponsor、医学、统计、监管或 GxP 人类审批，真实 Study 使用前必须重新进入 Structured Review Protocol。
- 每个 `F-nnn` 通过 ReviewPacket 的 `location` 精确映射到一个 governed record ID；不存在通配批准。

## 证据

- ReviewPacket：`.review_queue/archive/knowledge_p5_core_v1_001.json`
- DecisionReceipt：`.review_queue/archive/knowledge_p5_core_v1_001_decision.json`
- ConfirmationReceipt：`.review_queue/archive/knowledge_p5_core_v1_001_confirmation.json`
- 生成器：`scripts/content/finalize_p5_content.py`
"""
    return {
        REVIEW_ARCHIVE / f"{REVIEW_ID}.json": json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
        REVIEW_ARCHIVE / f"{REVIEW_ID}_decision.json": json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
        REVIEW_ARCHIVE / f"{REVIEW_ID}_confirmation.json": json.dumps(confirmation, ensure_ascii=False, indent=2) + "\n",
        ROOT / AUDIT_REFERENCE: governance_note,
    }


def finalize(*, write: bool) -> int:
    bundle = SchemaBundle.load(ROOT / "schemas" / "engine")
    released = _release_records(write=write)
    if not released:
        raise RuntimeError("No P5 release records found")
    outputs = _governance_payloads(released, bundle)
    stale: list[str] = []
    for path, expected in outputs.items():
        actual = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else None
        if actual != expected:
            if write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(expected, encoding="utf-8")
            else:
                stale.append(path.relative_to(ROOT).as_posix())
    if stale:
        raise RuntimeError("P5 governance outputs are stale: " + ", ".join(stale))
    return len(released)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if hashes or governance outputs are stale")
    args = parser.parse_args()
    count = finalize(write=not args.check)
    print(f"P5 content finalized: {count} governed records")


if __name__ == "__main__":
    main()
