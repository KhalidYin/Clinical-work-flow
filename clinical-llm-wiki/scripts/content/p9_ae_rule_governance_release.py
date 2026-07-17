"""Release an approved P9 AE mapping governance candidate into the Wiki.

The input is a de-identified, Study-local approved candidate.  This script
creates governed Markdown knowledge, local review evidence, a release artifact,
and a locked snapshot that can be queried without reading the original Study.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service.contracts import SchemaBundle, canonical_json_sha256  # noqa: E402
from service.repository import VaultRepository  # noqa: E402
from service.snapshot import load_locked_snapshot  # noqa: E402


REVIEW_ID = "sap_review_p9_ae_rule_governance_v1_001"
RECEIPT_ID = "review-sap-review-p9-ae-rule-governance-v1-001"
AUDIT_REFERENCE = "wiki-audit-p9-ae-rule-governance-v1-001"
RELEASE_ID = "release-p9-ae-rule-governance-v1"
SNAPSHOT_ID = "snapshot-p9-ae-rule-governance-v1"
TARGET_CARD_PATH = (
    "vault/20_Knowledge/Programming/P9 SDTM AE Metadata Mapping Evidence Gate.md"
)
RELEASE_PATH = "sources/packages/p9-ae-rule-governance/release.json"
SNAPSHOT_PATH = f"snapshots/{SNAPSHOT_ID}.json"
FORBIDDEN_PUBLIC_VALUES = ("SAMPLE-AE-001", "Subject", "RecordPosition", "AETERM_PT")
TEST_USE_SCOPE = "p9-poc-test-only"
TEST_USE_NOTICE = (
    "测试用途声明：本卡和本 snapshot 仅用于 P9.1 单机 POC / 测试验证，"
    "不是生产正式知识，不得作为真实 Study 自动化的独立执行依据。"
)


class P9RuleGovernanceReleaseError(ValueError):
    """The P9 rule candidate cannot enter governed Wiki release."""


def _read_json(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise P9RuleGovernanceReleaseError(f"cannot read JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise P9RuleGovernanceReleaseError(f"JSON artifact must be an object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _repository(root: Path) -> VaultRepository:
    repository = VaultRepository(root, SchemaBundle.load(root / "schemas" / "engine"))
    repository.refresh()
    return repository


def _approved_candidate(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != "1.0.0":
        raise P9RuleGovernanceReleaseError("approved candidate schema_version mismatch")
    expected_hash = payload.get("approved_candidate_sha256")
    body = dict(payload)
    body.pop("approved_candidate_sha256", None)
    if expected_hash != canonical_json_sha256(body):
        raise P9RuleGovernanceReleaseError("approved candidate content hash mismatch")
    candidate = payload.get("candidate")
    if not isinstance(candidate, dict):
        raise P9RuleGovernanceReleaseError("approved candidate payload is missing candidate")
    if candidate.get("review_status") != "approved":
        raise P9RuleGovernanceReleaseError("candidate must be approved before Wiki release")
    if candidate.get("deidentified") is not True:
        raise P9RuleGovernanceReleaseError("candidate must be explicitly deidentified")
    approval = candidate.get("approval")
    if not isinstance(approval, dict):
        raise P9RuleGovernanceReleaseError("candidate approval evidence is missing")
    if approval.get("approval_receipt_id") != RECEIPT_ID:
        raise P9RuleGovernanceReleaseError("candidate approval receipt does not match P9 gate")
    if candidate.get("source_decision_sha256") != approval.get("decision_receipt_sha256"):
        raise P9RuleGovernanceReleaseError("candidate source decision hash is not approval-bound")
    serialized = json.dumps(candidate, ensure_ascii=False, sort_keys=True)
    leaked = [value for value in FORBIDDEN_PUBLIC_VALUES if value in serialized]
    if leaked:
        raise P9RuleGovernanceReleaseError(
            "candidate contains non-public Study/source value: " + ", ".join(leaked)
        )
    if not candidate.get("evidence", {}).get("approved_rule_refs"):
        raise P9RuleGovernanceReleaseError("candidate lacks approved rule evidence")
    return candidate


def _knowledge_body(candidate: Mapping[str, Any]) -> str:
    rule_refs = "\n".join(
        f"- `{rule_id}`" for rule_id in candidate["evidence"]["approved_rule_refs"]
    )
    gaps = "\n".join(f"- `{gap_id}`" for gap_id in candidate["evidence"]["gap_ids"])
    return f"""# P9 SDTM AE Metadata Mapping Evidence Gate（测试用）

验证等级：**tested**。

> {TEST_USE_NOTICE}

本卡沉淀的是 P9.1 从真实 SAS7BDAT metadata POC 中抽取出的通用治理边界，不沉淀当前 Study 的常量、受试者、源变量取值、Sponsor 特例或完整 SDTMIG 符合性声明。

## 适用

- 目标为 SDTM AE 的 metadata-driven MappingSpec。
- 原始来源与 Source Metadata 已 hash-lock。
- MappingSpec 只能使用 allowlist operation。
- 每条 mapping 必须引用 approved Wiki rule。
- 证据不足字段必须保留 explicit gap。

## 不适用

{chr(10).join(f"- {item}" for item in candidate["non_applicability"])}

## 已引用的 approved rule

{rule_refs}

## 必须保留的缺口类别

{gaps}

## 边界

本规则不批准 controlled terminology 映射、不批准 study-day 派生、不批准当前 Study 标识规则，也不替代 Mapping Review、Program Review 或 canonical promotion。
"""


def _knowledge_record(candidate: Mapping[str, Any], body: str) -> dict[str, Any]:
    record = {
        "id": candidate["target_knowledge_id"],
        "type": "programming_pattern",
        "title": "P9 SDTM AE Metadata Mapping Evidence Gate（测试用）",
        "version": "1.0.0",
        "schema_version": "1.0.0",
        "content_status": "verified",
        "approval_status": "approved",
        "domains": ["sdtm", "ae"],
        "workflow_stages": ["sdtm_spec", "sdtm_programming"],
        "topics": ["metadata-driven-mapping", "evidence-gate", "explicit-gap", TEST_USE_SCOPE],
        "aliases": ["P9 AE mapping evidence gate", "P9 AE mapping evidence gate test-only"],
        "authority": "approved_precedent",
        "applicability": {
            "therapeutic_areas": [],
            "trial_phases": [],
            "sponsor_ids": [],
            "study_ids": [],
            "conditions": [
                "metadata-driven-mapping",
                "hash-locked-source-metadata",
                "approved-rule-references-required",
            ],
        },
        "sources": ["src-cdisc-sdtmig-3-4"],
        "owner": "clinical-knowledge-governance",
        "created": candidate["approval"]["approved_at"],
        "last_reviewed": candidate["approval"]["approved_at"][:10],
        "review_due": "2027-07-17",
        "supersedes": [],
        "superseded_by": None,
        "content_hash": "",
        "rights_status": "restricted",
        "allowed_uses": ["runtime", "reference", TEST_USE_SCOPE],
        "storage_mode": "committed",
        "contract_compatibility": {
            "minimum": "1.0.0",
            "maximum_exclusive": "2.0.0",
        },
        "approval_receipt_id": RECEIPT_ID,
        "audit_reference": AUDIT_REFERENCE,
        "summary": (
            "测试用 P9.1 POC 知识。SDTM AE metadata-driven MappingSpec 的通用证据门：allowlist operation、"
            "approved rule refs 和 explicit gap preservation。"
        ),
        "statements": [{
            "rule_id": candidate["target_rule_id"],
            "statement": (
                "Metadata-driven SDTM AE MappingSpec may be reused only when source "
                "metadata is hash-locked, operations are allowlisted, every mapping "
                "cites approved Wiki rules, and unsupported fields remain explicit gaps."
            ),
            "rationale": (
                "P9.1 POC 从真实 SAS7BDAT metadata 中证明该治理边界可复用；"
                "Study-specific constants and unresolved gaps remain excluded. "
                "This record is test-use only and is not a production clinical standard."
            ),
            "evidence_refs": ["src-cdisc-sdtmig-3-4"],
        }],
    }
    record["content_hash"] = canonical_json_sha256({
        "frontmatter": {key: value for key, value in record.items() if key != "content_hash"},
        "body": body.strip(),
    })
    return record


def _governance_packet(record_id: str, candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "review_id": REVIEW_ID,
        "review_type": "sap_review",
        "source_documents": [RELEASE_PATH],
        "agent_summary": "P9 AE 通用 Mapping evidence gate 已由 Study-local 候选批准，现写入 Wiki governance evidence。",
        "findings": [{
            "id": "F-001",
            "category": "compliance",
            "severity": "warning",
            "location": record_id,
            "title": "批准 P9 AE 通用 Mapping evidence gate",
            "current_value": "Wiki 中尚无该 governed rule",
            "proposed_value": candidate["title"],
            "rationale": "该记录只包含去标识的一般化治理边界，并保留不适用范围。",
            "evidence_refs": [candidate["candidate_id"], candidate["source_decision_sha256"]],
            "auto_approved": False,
        }],
        "urgency": "blocking",
        "created_at": candidate["approval"]["approved_at"],
        "generated_by": "P9 AE Rule Governance Release",
        "auto_approved_count": 0,
    }


def _governance_decision(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "review_id": REVIEW_ID,
        "reviewer": candidate["approval"]["reviewer"],
        "reviewer_role": candidate["approval"]["reviewer_role"],
        "timestamp": candidate["approval"]["approved_at"],
        "decisions": [{"finding_id": "F-001", "decision": "approved"}],
        "general_notes": "由已批准的 Study-local P9 reusable-rule ReviewPacket 转写为 Wiki governance evidence。",
    }


def _governance_confirmation(candidate: Mapping[str, Any], record_id: str) -> dict[str, Any]:
    return {
        "review_id": REVIEW_ID,
        "applied_at": candidate["approval"]["approved_at"],
        "generated_by": "P9 AE Rule Governance Release",
        "results": [{
            "finding_id": "F-001",
            "original_decision": "approved",
            "application_status": "applied",
            "actual_value": f"{record_id} written to governed Wiki and included in {SNAPSHOT_ID}",
        }],
        "summary": {"total": 1, "applied": 1, "adjusted": 0, "failed": 0},
    }


def _assert_no_conflict(repository: VaultRepository, record: Mapping[str, Any]) -> None:
    if repository.get(str(record["id"])) is not None:
        raise P9RuleGovernanceReleaseError(f"knowledge item already exists: {record['id']}")
    new_rule_ids = {
        statement["rule_id"] for statement in record.get("statements", [])
    }
    for card in repository.cards.values():
        existing = {
            statement["rule_id"] for statement in card.record.get("statements", [])
        }
        overlap = sorted(new_rule_ids & existing)
        if overlap:
            raise P9RuleGovernanceReleaseError(
                "conflicting existing rule_id: " + ", ".join(overlap)
            )


def _write_card(root: Path, record: Mapping[str, Any], body: str) -> Path:
    path = root / TARGET_CARD_PATH
    if path.exists():
        raise P9RuleGovernanceReleaseError(f"knowledge card already exists: {TARGET_CARD_PATH}")
    path.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = yaml.safe_dump(dict(record), allow_unicode=True, sort_keys=False).strip()
    path.write_text(f"---\n{frontmatter}\n---\n\n{body.strip()}\n", encoding="utf-8", newline="\n")
    return path


def _snapshot(record: Mapping[str, Any], repository: VaultRepository) -> dict[str, Any]:
    content = {
        "schema_bundle": {
            "version": repository.bundle.version,
            "sha256": repository.bundle.sha256,
        },
        "items": [dict(record)],
    }
    return {
        "snapshot_id": SNAPSHOT_ID,
        "version": "1.0.0",
        "created_at": record["created"],
        "sha256": canonical_json_sha256(content),
        **content,
    }


def _release_artifact(
    *,
    candidate_payload: Mapping[str, Any],
    record: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "release_id": RELEASE_ID,
        "usage_scope": TEST_USE_SCOPE,
        "usage_notice": TEST_USE_NOTICE,
        "candidate_sha256": candidate_payload["approved_candidate_sha256"],
        "knowledge_item_id": record["id"],
        "knowledge_card_path": TARGET_CARD_PATH,
        "rule_ids": [statement["rule_id"] for statement in record["statements"]],
        "approval_receipt_id": RECEIPT_ID,
        "audit_reference": AUDIT_REFERENCE,
        "snapshot_lock": {
            "snapshot_id": snapshot["snapshot_id"],
            "version": snapshot["version"],
            "sha256": snapshot["sha256"],
        },
        "clean_room_boundary": (
            "Reuse verification must load this snapshot and query the governed card only; "
            "it must not read the originating Study candidate or DecisionReceipt. "
            "This snapshot is for P9.1 POC testing only."
        ),
    }


def build_release(
    wiki_root: str | Path,
    approved_candidate_path: str | Path,
) -> dict[str, Any]:
    root = Path(wiki_root).resolve()
    candidate_payload = _read_json(approved_candidate_path)
    candidate = _approved_candidate(candidate_payload)
    body = _knowledge_body(candidate)
    record = _knowledge_record(candidate, body)
    repository = _repository(root)
    _assert_no_conflict(repository, record)
    packet = _governance_packet(record["id"], candidate)
    decision = _governance_decision(candidate)
    confirmation = _governance_confirmation(candidate, record["id"])
    for definition, payload in (
        ("review_packet", packet),
        ("decision_receipt", decision),
        ("confirmation_receipt", confirmation),
    ):
        repository.bundle.validate_definition(
            "review/review-protocol.schema.json", definition, payload
        )
    repository.bundle.validate("knowledge/knowledge-item.schema.json", record)
    snapshot = _snapshot(record, repository)
    release = _release_artifact(
        candidate_payload=candidate_payload,
        record=record,
        snapshot=snapshot,
    )
    return {
        "candidate": candidate_payload,
        "record": record,
        "body": body,
        "packet": packet,
        "decision": decision,
        "confirmation": confirmation,
        "snapshot": snapshot,
        "release": release,
    }


def write_release(wiki_root: str | Path, outputs: Mapping[str, Any]) -> dict[str, Any]:
    root = Path(wiki_root).resolve()
    archive = root / ".review_queue" / "archive"
    archive.mkdir(parents=True, exist_ok=True)
    _write_json(archive / f"{REVIEW_ID}.json", outputs["packet"])
    _write_json(archive / f"{REVIEW_ID}_decision.json", outputs["decision"])
    _write_json(archive / f"{REVIEW_ID}_confirmation.json", outputs["confirmation"])
    card_path = _write_card(root, outputs["record"], outputs["body"])
    _write_json(root / RELEASE_PATH, outputs["release"])
    _write_json(root / SNAPSHOT_PATH, outputs["snapshot"])
    with (root / "audit_trail.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(
                {
                    "event_id": AUDIT_REFERENCE,
                    "event_type": "p9_ae_rule_governance_release_applied",
                    "timestamp": outputs["decision"]["timestamp"],
                    "record_id": outputs["record"]["id"],
                    "review_id": REVIEW_ID,
                    "approval_receipt_id": RECEIPT_ID,
                    "audit_reference": AUDIT_REFERENCE,
                    "result": "applied",
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
    repository = _repository(root)
    card = repository.get(outputs["record"]["id"])
    if card is None or not card.production_eligible:
        raise P9RuleGovernanceReleaseError(
            f"released card is not production eligible: {card.eligibility_reasons if card else 'missing'}"
        )
    records = load_locked_snapshot(repository, outputs["release"]["snapshot_lock"])
    if [record["id"] for record in records] != [outputs["record"]["id"]]:
        raise P9RuleGovernanceReleaseError("clean snapshot did not return the released rule")
    return {
        "knowledge_card": card_path.relative_to(root).as_posix(),
        "snapshot": SNAPSHOT_PATH,
        "release": RELEASE_PATH,
        "snapshot_sha256": outputs["snapshot"]["sha256"],
    }


def clean_room_query(wiki_root: str | Path, snapshot_lock: Mapping[str, Any]) -> dict[str, Any]:
    """Prove reuse from the new snapshot without opening the originating Study."""

    root = Path(wiki_root).resolve()
    repository = _repository(root)
    records = load_locked_snapshot(repository, dict(snapshot_lock))
    matches = [
        record for record in records
        if "metadata-driven-mapping" in record.get("topics", [])
        and record.get("approval_status") == "approved"
    ]
    if len(matches) != 1:
        raise P9RuleGovernanceReleaseError("clean-room query did not uniquely resolve the P9 rule")
    record = deepcopy(matches[0])
    return {
        "query_id": "clean-room-p9-ae-rule-governance-v1",
        "usage_scope": TEST_USE_SCOPE,
        "knowledge_id": record["id"],
        "knowledge_version": record["version"],
        "rule_ids": [statement["rule_id"] for statement in record["statements"]],
        "snapshot_id": snapshot_lock["snapshot_id"],
        "snapshot_sha256": snapshot_lock["sha256"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-root", type=Path, default=ROOT)
    parser.add_argument("--approved-candidate", type=Path, required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    outputs = build_release(args.wiki_root, args.approved_candidate)
    if args.write:
        result = write_release(args.wiki_root, outputs)
    else:
        result = {
            "action": "checked",
            "knowledge_item_id": outputs["record"]["id"],
            "snapshot_sha256": outputs["snapshot"]["sha256"],
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except P9RuleGovernanceReleaseError as error:
        raise SystemExit(f"P9 AE rule governance release failed: {error}") from error
