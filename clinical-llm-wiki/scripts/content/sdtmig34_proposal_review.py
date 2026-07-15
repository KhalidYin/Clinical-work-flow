"""P6-P3-D SDTMIG 3.4 proposal review gate.

The gate combines the P3-C Core proposal batch and the Events/AE batch proven
by P3-B Gold calibration.  It opens a blocking human ReviewPacket with Chinese
human-facing text and deliberately does not write a DecisionReceipt or apply
any approval.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
from typing import Any

from jsonschema import Draft202012Validator

from scripts.content.sdtmig34_core_proposals import (
    DEFAULT_REPORT as CORE_REPORT,
    canonical_json_bytes,
    run_core_proposals,
    sha256_payload,
    write_json,
)
from scripts.content.sdtmig34_gold_calibration import (
    DEFAULT_REPORT as GOLD_REPORT,
    run_gold_calibration,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGE = ROOT / "sources" / "packages" / "src-cdisc-sdtmig-3-4"
DEFAULT_REVIEW_REPORT = DEFAULT_PACKAGE / "proposal-review-gate-report.json"
DEFAULT_REVIEW_QUEUE = ROOT / ".review_queue"

REVIEW_ID = "sdtm_spec_sdtmig34_proposals_v1_001"
PACKET_NAME = f"{REVIEW_ID}.json"
PACKET_CREATED_AT = "2026-07-15T16:30:00+08:00"
GENERATED_BY = "P6-P3-D SDTMIG 3.4 知识候选审核门生成器"

SOURCE_DOCUMENTS = [
    "sources/packages/src-cdisc-sdtmig-3-4/core-proposal-quality-report.json",
    "sources/packages/src-cdisc-sdtmig-3-4/gold-proposal-calibration-report.json",
    "sources/packages/src-cdisc-sdtmig-3-4/proposal-review-gate-report.json",
    "sources/packages/src-cdisc-sdtmig-3-4/source-manifest.json",
    "vault/60_Sources/Registry/CDISC SDTMIG 3.4.md",
    "vault/98_Inbox/SDTMIG 3.4 Core Proposal Batch.md",
]

_HAN_RE = re.compile(r"[\u4e00-\u9fff]")


class ProposalReviewError(ValueError):
    """Raised when the proposal review gate cannot be trusted."""


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def schema_definition(root: str | Path, name: str) -> dict[str, Any]:
    schema_path = Path(root) / "schemas" / "engine" / "review" / "review-protocol.schema.json"
    schema = load_json(schema_path)
    definition = deepcopy(schema["$defs"][name])
    definition.pop("$id", None)
    definition["$schema"] = schema["$schema"]
    definition["$defs"] = schema["$defs"]
    return definition


def build_proposal_review_artifacts(
    *,
    wiki_root: str | Path = ROOT,
    created_at: str = PACKET_CREATED_AT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build the compact quality report and blocking ReviewPacket."""

    root = Path(wiki_root).resolve()
    _validate_created_at(created_at)
    core = run_core_proposals(include_source_text=False)
    events = run_gold_calibration(include_source_text=False)
    core_report = load_json(root / CORE_REPORT.relative_to(ROOT))
    gold_report = load_json(root / GOLD_REPORT.relative_to(ROOT))
    if core["report"]["batch_sha256"] != core_report["batch_sha256"]:
        raise ProposalReviewError("Core report does not match rebuilt Core batch")
    if events["report"]["batch_sha256"] != gold_report["batch_sha256"]:
        raise ProposalReviewError("Events/AE report does not match rebuilt Gold batch")

    sources = [
        _batch_source("core", core["batch"], core_report),
        _batch_source("events_ae", events["batch"], gold_report),
    ]
    statements = _combined_statements(sources)
    checks = _quality_checks(root=root, sources=sources, statements=statements)
    packet = build_review_packet(
        statements=statements,
        checks=checks,
        created_at=created_at,
    )
    Draft202012Validator(schema_definition(root, "review_packet")).validate(packet)
    report = {
        "schema_version": "1.0.0",
        "review_id": REVIEW_ID,
        "gate_status": "pending_human_review",
        "created_at": created_at,
        "source_id": "src-cdisc-sdtmig-3-4",
        "source_sha256": core["batch"]["source_sha256"],
        "structure_map_sha256": core["batch"]["structure_map_sha256"],
        "batch_sources": [
            {
                "label": source["label"],
                "batch_id": source["batch"]["batch_id"],
                "package_id": source["batch"]["extraction_package"]["package_id"],
                "proposal_total": len(source["batch"]["extraction_package"]["statements"]),
                "source_unit_total": len(source["batch"]["extraction_package"]["units"]),
                "report_sha256": sha256_payload(source["report"]),
                "batch_sha256": sha256_payload(source["batch"]),
            }
            for source in sources
        ],
        "summary": {
            "checks_total": len(checks),
            "checks_passed": sum(item["status"] == "passed" for item in checks),
            "checks_failed": sum(item["status"] != "passed" for item in checks),
            "proposal_total": len(statements),
            "human_findings_pending": len(packet["findings"]),
            "auto_approved_count": packet["auto_approved_count"],
        },
        "semantic_quality": {
            "review_required_count": len(statements),
            "duplicate_evidence_key_count": _duplicate_evidence_count(statements),
            "statement_status_counts": dict(
                sorted(Counter(s["review_status"] for s in statements).items())
            ),
            "knowledge_type_counts": dict(
                sorted(Counter(s["knowledge_type"] for s in statements).items())
            ),
            "modality_counts": dict(sorted(Counter(s["modality"] for s in statements).items())),
            "multi_source_proposal_count": sum(len(s["evidence"]) > 1 for s in statements),
            "variable_rule_count": sum(
                s["knowledge_type"] == "variable_rule" for s in statements
            ),
        },
        "checks": checks,
        "packet": {
            "review_id": packet["review_id"],
            "packet_sha256": sha256_payload(packet),
            "finding_count": len(packet["findings"]),
            "source_documents": packet["source_documents"],
            "language": "zh-CN",
        },
    }
    if report["summary"]["checks_failed"]:
        raise ProposalReviewError("proposal review checks did not all pass")
    return report, packet


def _batch_source(
    label: str, batch: dict[str, Any], report: dict[str, Any]
) -> dict[str, Any]:
    return {"label": label, "batch": batch, "report": report}


def _combined_statements(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    combined = []
    seen: set[str] = set()
    for source in sources:
        for statement in source["batch"]["extraction_package"]["statements"]:
            if statement["statement_id"] in seen:
                raise ProposalReviewError(
                    f"duplicate statement id: {statement['statement_id']}"
                )
            seen.add(statement["statement_id"])
            enriched = deepcopy(statement)
            enriched["batch_label"] = source["label"]
            combined.append(enriched)
    return combined


def _quality_checks(
    *, root: Path, sources: list[dict[str, Any]], statements: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    core_batch = next(source for source in sources if source["label"] == "core")["batch"]
    events_batch = next(source for source in sources if source["label"] == "events_ae")[
        "batch"
    ]
    source_docs_valid = _source_documents_are_committed_review_inputs(root)
    proposed_only = all(
        statement["review_status"] == "proposed"
        and statement["review_receipt_id"] is None
        for statement in statements
    )
    duplicate_evidence = _duplicate_evidence_count(statements)
    variable_scope_valid = _variable_rule_scope_is_reviewable(statements)
    return [
        {
            "check_id": "CHK-001",
            "name": "Core proposal batch gate",
            "status": "passed"
            if core_batch["quality_summary"]["gate_status"] == "pass"
            else "failed",
            "evidence_refs": [CORE_REPORT.relative_to(ROOT).as_posix()],
            "detail": "P3-C Core proposal batch quality gate is pass.",
        },
        {
            "check_id": "CHK-002",
            "name": "Events/AE proposal batch gate",
            "status": "passed"
            if events_batch["gold_evaluation"]["gate_status"] == "pass"
            else "failed",
            "evidence_refs": [GOLD_REPORT.relative_to(ROOT).as_posix()],
            "detail": "P3-B Events/AE Gold-calibrated batch remains structurally pass.",
        },
        {
            "check_id": "CHK-003",
            "name": "Proposed-only review boundary",
            "status": "passed" if proposed_only else "failed",
            "evidence_refs": ["proposal-review:combined-statements"],
            "detail": "No statement carries approved status or a review receipt.",
        },
        {
            "check_id": "CHK-004",
            "name": "Duplicate evidence identity check",
            "status": "passed" if duplicate_evidence == 0 else "failed",
            "evidence_refs": ["proposal-review:evidence-identity"],
            "detail": f"Duplicate evidence identities: {duplicate_evidence}.",
        },
        {
            "check_id": "CHK-005",
            "name": "Variable rule reviewability check",
            "status": "passed" if variable_scope_valid else "failed",
            "evidence_refs": ["proposal-review:variable-rules"],
            "detail": "Variable rules have explicit subjects, scopes, and locator evidence.",
        },
        {
            "check_id": "CHK-006",
            "name": "ReviewPacket source boundary",
            "status": "passed" if source_docs_valid else "failed",
            "evidence_refs": SOURCE_DOCUMENTS,
            "detail": "Source documents are committed metadata/reports, not original or derived source text.",
        },
    ]


def _source_documents_are_committed_review_inputs(root: Path) -> bool:
    generated_report = DEFAULT_REVIEW_REPORT.relative_to(ROOT).as_posix()
    for declared in SOURCE_DOCUMENTS:
        path = root / declared
        normalized = path.relative_to(root).as_posix() if path.exists() else declared
        if not path.is_file() and normalized != generated_report:
            return False
        if "/original/" in normalized or "/derived/" in normalized:
            return False
        if path.suffix.lower() in {".pdf", ".xlsx"}:
            return False
    return True


def _variable_rule_scope_is_reviewable(statements: list[dict[str, Any]]) -> bool:
    for statement in statements:
        if statement["knowledge_type"] != "variable_rule":
            continue
        if not statement["subject"].strip():
            return False
        if not statement["scope"]["model"] or not statement["scope"]["implementation_guide"]:
            return False
        if not statement["evidence"]:
            return False
    return True


def build_review_packet(
    *,
    statements: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    findings = [
        _finding_for_statement(index, statement)
        for index, statement in enumerate(statements, start=1)
    ]
    return {
        "review_id": REVIEW_ID,
        "review_type": "sdtm_spec",
        "source_documents": SOURCE_DOCUMENTS,
        "agent_summary": (
            "P6-P3-D 人工审核门：请逐条确认 SDTMIG 3.4 Core 与 Events/AE "
            "proposed knowledge 的语义、适用范围、条件、例外和 locator。"
        ),
        "findings": findings,
        "urgency": "blocking",
        "created_at": created_at,
        "generated_by": GENERATED_BY,
        "auto_approved_count": 0,
    }


def _finding_for_statement(index: int, statement: dict[str, Any]) -> dict[str, Any]:
    locator_ids = [item["locator_id"] for item in statement["evidence"]]
    scope = statement["scope"]
    conditions = statement["conditions"] or ["无显式条件"]
    exceptions = statement["exceptions"] or ["无显式例外"]
    title = f"确认 {statement['subject']} 的 {statement['knowledge_type']} 候选"
    current_value = (
        f"当前状态：{statement['statement_id']} 仍为 proposed；"
        f"批次={statement['batch_label']}；modality={statement['modality']}。"
    )
    proposed_value = (
        f"建议审阅：statement=\"{statement['statement']}\"；"
        f"scope=model {scope['model']}, IG {scope['implementation_guide']}, "
        f"domains {scope['domains']}, variables {scope['variables']}；"
        f"conditions {conditions}；exceptions {exceptions}；locators {locator_ids}。"
    )
    rationale = (
        "该候选由 ProposalBatch 生成器注入证据并保持 proposed 状态；"
        "需要人工确认语义是否忠实、范围是否过宽或过窄、条件/例外是否完整。"
    )
    for value in (title, current_value, proposed_value, rationale):
        if _HAN_RE.search(value) is None:
            raise ProposalReviewError("human-facing ReviewPacket field is not Chinese")
    return {
        "id": f"F-{index:03d}",
        "category": _finding_category(statement),
        "severity": _finding_severity(statement),
        "location": f"proposal-review#{statement['statement_id']}",
        "title": title,
        "current_value": current_value,
        "proposed_value": proposed_value,
        "rationale": rationale,
        "evidence_refs": [
            f"proposal:{statement['statement_id']}",
            *[f"locator:{locator_id}" for locator_id in locator_ids],
        ],
        "auto_approved": False,
    }


def _finding_category(statement: dict[str, Any]) -> str:
    if statement["knowledge_type"] == "cross_reference":
        return "terminology"
    if statement["knowledge_type"] in {"variable_rule", "example"}:
        return "mapping"
    return "compliance"


def _finding_severity(statement: dict[str, Any]) -> str:
    if statement["modality"] in {"must", "must_not"}:
        return "warning"
    if statement["knowledge_type"] in {"variable_rule", "exception"}:
        return "warning"
    return "info"


def _duplicate_evidence_count(statements: list[dict[str, Any]]) -> int:
    keys = [_evidence_key(statement) for statement in statements]
    return sum(count - 1 for count in Counter(keys).values() if count > 1)


def _evidence_key(statement: dict[str, Any]) -> str:
    return "|".join(
        sorted(
            f"{item['source_id']}::{item['artifact_id']}::{item['locator_id']}"
            for item in statement["evidence"]
        )
    )


def _validate_created_at(value: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})", value):
        raise ProposalReviewError(f"created_at must be ISO-8601 with timezone: {value}")


def write_packet(path: str | Path, packet: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_json_bytes(packet))


def run_proposal_review_gate(
    *,
    wiki_root: str | Path = ROOT,
    created_at: str = PACKET_CREATED_AT,
) -> dict[str, Any]:
    report, packet = build_proposal_review_artifacts(
        wiki_root=wiki_root,
        created_at=created_at,
    )
    return {"report": report, "packet": packet}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-root", type=Path, default=ROOT)
    parser.add_argument("--created-at", default=PACKET_CREATED_AT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REVIEW_REPORT)
    parser.add_argument(
        "--packet",
        type=Path,
        default=DEFAULT_REVIEW_QUEUE / PACKET_NAME,
    )
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    result = run_proposal_review_gate(
        wiki_root=args.wiki_root,
        created_at=args.created_at,
    )
    if not args.no_write:
        decision = args.packet.with_name(f"{REVIEW_ID}_decision.json")
        confirmation = args.packet.with_name(f"{REVIEW_ID}_confirmation.json")
        if decision.exists() or confirmation.exists():
            raise ProposalReviewError(
                "cannot overwrite a review gate that already has a decision or confirmation"
            )
        write_json(args.report, result["report"])
        write_packet(args.packet, result["packet"])
    print(
        "Proposal review gate pending_human_review: "
        f"{len(result['packet']['findings'])} findings"
    )


if __name__ == "__main__":
    try:
        main()
    except ProposalReviewError as error:
        raise SystemExit(f"Proposal review gate failed: {error}") from error
