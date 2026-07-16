"""Study-local governance for reusable P9 AE mapping rules.

The module classifies what can be generalized from a Study MappingSpec without
publishing anything into the Wiki.  A separate Wiki-side release script consumes
only an approved, de-identified candidate.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from src.knowledge.compatibility import sha256_canonical_json
from src.runtime.review_protocol import (
    Decision,
    FindingCategory,
    ReviewFinding,
    ReviewPacket,
    ReviewQueue,
    ReviewType,
    Severity,
    Urgency,
)


RULE_GOVERNANCE_REVIEW_ID = "sap_review_p9_ae_rule_governance_v1_001"
RULE_GOVERNANCE_REPORT_PATH = (
    "knowledge/promotion_candidates/ae-rule-governance-report.json"
)
RULE_GOVERNANCE_APPROVED_PATH = (
    "knowledge/promotion_candidates/ae-rule-governance-approved.json"
)
TARGET_KNOWLEDGE_ID = "pattern-p9-sdtm-ae-metadata-mapping-evidence-gate"
TARGET_RULE_ID = "rule-p9-sdtm-ae-metadata-mapping-evidence-gate"


class AERuleGovernanceError(ValueError):
    """The Study-local rule governance package is incomplete or unsafe."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AERuleGovernanceError(f"Cannot read JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise AERuleGovernanceError(f"JSON artifact must be an object: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _content_hash(payload: Mapping[str, Any], field: str) -> str:
    body = dict(payload)
    body.pop(field, None)
    return sha256_canonical_json(body)


def _mapping_paths(study: Path) -> tuple[Path, Path]:
    return (
        study / "work/mapping/ae-mapping-context.json",
        study / "work/mapping/ae-mapping-spec-candidate.json",
    )


def _deidentified_study_hash(study_id: str, spec_sha256: str) -> str:
    return sha256_canonical_json(
        {"study_id": study_id, "source_mapping_spec_sha256": spec_sha256}
    )


def _assert_public_candidate_is_deidentified(
    candidate: Mapping[str, Any], *, forbidden_values: list[str]
) -> None:
    serialized = json.dumps(candidate, ensure_ascii=False, sort_keys=True)
    for value in forbidden_values:
        if value and value in serialized:
            raise AERuleGovernanceError(
                f"general rule candidate contains raw Study-specific value: {value}"
            )


def build_ae_rule_governance_report(
    study_dir: str | Path,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Classify P4 mapping evidence into reusable, local, and unresolved parts."""

    study = Path(study_dir).resolve()
    context_path, spec_path = _mapping_paths(study)
    context = _read_json(context_path)
    spec = _read_json(spec_path)
    if spec.get("status") != "candidate":
        raise AERuleGovernanceError("P5 starts from the candidate MappingSpec, not an approved artifact")
    if spec.get("spec_sha256") != _content_hash(spec, "spec_sha256"):
        raise AERuleGovernanceError("MappingSpec hash drifted")
    if context.get("context_sha256") != _content_hash(context, "context_sha256"):
        raise AERuleGovernanceError("Mapping context hash drifted")
    if spec["source"]["sha256"] != context["source"]["sha256"]:
        raise AERuleGovernanceError("MappingSpec and context source hash differ")

    used_rule_ids = sorted(
        {rule["rule_id"] for rule in spec.get("knowledge", {}).get("rules", [])}
    )
    if not used_rule_ids:
        raise AERuleGovernanceError("general rule candidate requires approved rule evidence")
    operations = sorted({mapping["operation"] for mapping in spec.get("mappings", [])})
    if not operations:
        raise AERuleGovernanceError("general rule candidate requires at least one mapping operation")

    source_study_hash = _deidentified_study_hash(spec["study_id"], spec["spec_sha256"])
    general_candidate = {
        "candidate_id": "candidate-p9-ae-mapping-evidence-gate-v1",
        "classification": "general_rule_candidate",
        "target_knowledge_id": TARGET_KNOWLEDGE_ID,
        "target_rule_id": TARGET_RULE_ID,
        "title": "P9 SDTM AE metadata mapping evidence gate",
        "review_status": "pending",
        "deidentified": True,
        "source_study_sha256": source_study_hash,
        "source_mapping_spec_sha256": spec["spec_sha256"],
        "source_context_sha256": context["context_sha256"],
        "source_decision_sha256": None,
        "source_version": {
            "standard": context["target_standard"]["name"],
            "version": context["target_standard"]["version"],
            "snapshot_id": context["knowledge"]["snapshot_id"],
            "snapshot_sha256": context["knowledge"]["snapshot_sha256"],
        },
        "applicability": {
            "domains": ["sdtm", "ae"],
            "workflow_stages": ["sdtm_spec", "sdtm_programming"],
            "conditions": [
                "source metadata is hash-locked",
                "MappingSpec uses only allowlisted operations",
                "each mapping cites approved Wiki rules",
                "insufficient source evidence remains an explicit gap",
            ],
        },
        "non_applicability": [
            "does not approve Study-specific constants or identifier prefixes",
            "does not approve controlled terminology value mapping without catalog evidence",
            "does not approve study-day derivation without a joinable reference date",
            "does not claim full SDTMIG conformance",
        ],
        "evidence": {
            "operation_allowlist": context["allowed_operations"],
            "operations_used": operations,
            "approved_rule_refs": used_rule_ids,
            "gap_ids": sorted(gap["gap_id"] for gap in spec["explicit_gaps"]),
            "source_rows": context["source"]["row_count"],
        },
    }
    _assert_public_candidate_is_deidentified(
        general_candidate, forbidden_values=[spec["study_id"]]
    )

    study_specific = []
    for mapping in spec["mappings"]:
        if mapping["operation"] in {"constant", "concat"}:
            study_specific.append({
                "mapping_id": mapping["mapping_id"],
                "target_variable": mapping["target_variable"],
                "classification": "study_specific_rule",
                "reason": (
                    "该映射是当前 POC/目标数据集上下文中的具体填充值或标识逻辑，"
                    "只能保留在 Study-local MappingSpec，不得自动写入 Wiki。"
                ),
            })

    unresolved = [
        {
            "gap_id": gap["gap_id"],
            "classification": "unresolved_gap",
            "category": gap["category"],
            "affects_variables": gap["affects_variables"],
            "reason": gap["description"],
        }
        for gap in spec["explicit_gaps"]
    ]
    report = {
        "schema_version": "1.0.0",
        "report_id": "ae-rule-governance-report-sample-ae-001-v1",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "mapping_context_path": "work/mapping/ae-mapping-context.json",
            "mapping_context_sha256": _sha256_file(context_path),
            "mapping_spec_path": "work/mapping/ae-mapping-spec-candidate.json",
            "mapping_spec_file_sha256": _sha256_file(spec_path),
            "mapping_spec_content_sha256": spec["spec_sha256"],
        },
        "classification_counts": {
            "general_rule_candidate": 1,
            "study_specific_rule": len(study_specific),
            "unresolved_gap": len(unresolved),
        },
        "general_rule_candidates": [general_candidate],
        "study_specific_rules": study_specific,
        "unresolved_gaps": unresolved,
    }
    report["report_sha256"] = sha256_canonical_json(report)
    return report


def validate_ae_rule_governance_report(report: Mapping[str, Any]) -> list[str]:
    violations: list[str] = []
    if report.get("report_sha256") != _content_hash(report, "report_sha256"):
        violations.append("report_sha256: content hash mismatch")
    if report.get("classification_counts", {}).get("general_rule_candidate") != len(
        report.get("general_rule_candidates", [])
    ):
        violations.append("classification_counts.general_rule_candidate mismatch")
    for candidate in report.get("general_rule_candidates", []):
        if not candidate.get("deidentified"):
            violations.append(f"{candidate.get('candidate_id')}: deidentified must be true")
        if candidate.get("review_status") != "pending":
            violations.append(f"{candidate.get('candidate_id')}: review_status must start pending")
        if candidate.get("source_decision_sha256") is not None:
            violations.append(f"{candidate.get('candidate_id')}: source_decision_sha256 must start null")
    return violations


def _rule_governance_review_packet(report: Mapping[str, Any]) -> ReviewPacket:
    candidate = report["general_rule_candidates"][0]
    return ReviewPacket(
        review_id=RULE_GOVERNANCE_REVIEW_ID,
        review_type=ReviewType.SAP_REVIEW,
        source_documents=[
            RULE_GOVERNANCE_REPORT_PATH,
            report["source_artifacts"]["mapping_context_path"],
            report["source_artifacts"]["mapping_spec_path"],
        ],
        agent_summary=(
            "请审核 P9 AE Mapping 中可复用的治理规则候选。批准后仅允许写入去标识、"
            "一般化的 evidence gate，不批准当前 Study 的具体映射值。"
        ),
        findings=[
            ReviewFinding(
                id="F-001",
                category=FindingCategory.COMPLIANCE,
                severity=Severity.WARNING,
                location=candidate["target_knowledge_id"],
                title="批准去标识的一般化 Mapping evidence gate 候选",
                current_value="候选仍为 Study-local pending，不进入 Wiki approved index",
                proposed_value=(
                    "批准通用规则：MappingSpec 必须使用 allowlist operation、引用 approved "
                    "Wiki rule，且证据不足字段必须保留 explicit gap。"
                ),
                rationale=(
                    "该候选不含 Study ID、受试者数据、源数据样例或 Sponsor 特定规则；它只沉淀"
                    "治理边界，不沉淀本 Study 的变量值。"
                ),
                evidence_refs=[RULE_GOVERNANCE_REPORT_PATH, candidate["candidate_id"]],
            ),
            ReviewFinding(
                id="F-002",
                category=FindingCategory.MAPPING,
                severity=Severity.INFO,
                location="study_specific_rules",
                title="确认 Study-specific 映射不进入通用知识",
                current_value=json.dumps(
                    report["study_specific_rules"], ensure_ascii=False, sort_keys=True
                ),
                proposed_value="这些内容继续留在当前 Study-local MappingSpec",
                rationale="常量、标识前缀和当前源系统身份不能因一次运行成功变成通用规则。",
                evidence_refs=[RULE_GOVERNANCE_REPORT_PATH],
            ),
            ReviewFinding(
                id="F-003",
                category=FindingCategory.COMPLIANCE,
                severity=Severity.INFO,
                location="unresolved_gaps",
                title="确认未解决缺口继续保持显式 gap",
                current_value=json.dumps(
                    report["unresolved_gaps"], ensure_ascii=False, sort_keys=True
                ),
                proposed_value="不将 gap 补写为已批准规则",
                rationale="P5 只沉淀 evidence gate，不补齐 CT、reference-date 或完整 conformity 缺口。",
                evidence_refs=[RULE_GOVERNANCE_REPORT_PATH],
            ),
        ],
        urgency=Urgency.BLOCKING,
        created_at=str(report["generated_at"]),
        generated_by="P9 AE Rule Governance Classifier",
    )


def prepare_ae_rule_governance_review(
    study_dir: str | Path,
    *,
    generated_at: str | None = None,
) -> dict[str, str]:
    """Persist classification report and submit the reusable-rule ReviewPacket."""

    study = Path(study_dir).resolve()
    report = build_ae_rule_governance_report(study, generated_at=generated_at)
    violations = validate_ae_rule_governance_report(report)
    if violations:
        raise AERuleGovernanceError(f"Rule governance report invalid: {violations[0]}")
    report_path = _write_json(study / RULE_GOVERNANCE_REPORT_PATH, report)
    packet_path = ReviewQueue(study).submit_packet(_rule_governance_review_packet(report))
    return {
        "status": "rule_governance_review_required",
        "report": report_path.relative_to(study).as_posix(),
        "review_packet": packet_path.relative_to(study).as_posix(),
    }


def approve_ae_rule_governance_from_receipt(study_dir: str | Path) -> dict[str, Any]:
    """Create an approved, de-identified Wiki import candidate from a full receipt."""

    study = Path(study_dir).resolve()
    queue = ReviewQueue(study)
    packet = queue.load_packet(RULE_GOVERNANCE_REVIEW_ID)
    receipt = queue.check_decision(RULE_GOVERNANCE_REVIEW_ID)
    if packet is None or receipt is None:
        raise AERuleGovernanceError("Rule governance ReviewPacket or DecisionReceipt is missing")
    if receipt.rejected_count() or receipt.modified_count():
        raise AERuleGovernanceError("Rule governance receipt requires rework")
    required = {finding.id for finding in packet.findings_needing_decision()}
    approved = {
        decision.finding_id for decision in receipt.decisions
        if decision.decision == Decision.APPROVED
    }
    if approved != required:
        raise AERuleGovernanceError("Every rule governance finding must be approved")

    report = _read_json(study / RULE_GOVERNANCE_REPORT_PATH)
    violations = validate_ae_rule_governance_report(report)
    if violations:
        raise AERuleGovernanceError(f"Rule governance report drifted: {violations[0]}")
    decision_path = study / f".review_queue/{RULE_GOVERNANCE_REVIEW_ID}_decision.json"
    decision_sha = _sha256_file(decision_path)
    candidate = dict(report["general_rule_candidates"][0])
    candidate["review_status"] = "approved"
    candidate["source_decision_sha256"] = decision_sha
    candidate["approval"] = {
        "review_id": RULE_GOVERNANCE_REVIEW_ID,
        "approval_receipt_id": "review-sap-review-p9-ae-rule-governance-v1-001",
        "decision_receipt_sha256": decision_sha,
        "review_packet_sha256": _sha256_file(study / f".review_queue/{RULE_GOVERNANCE_REVIEW_ID}.json"),
        "reviewer": receipt.reviewer,
        "reviewer_role": receipt.reviewer_role or "knowledge_governance",
        "approved_at": receipt.timestamp,
    }
    _assert_public_candidate_is_deidentified(candidate, forbidden_values=[report["report_id"]])
    approved_candidate = {
        "schema_version": "1.0.0",
        "approved_candidate_id": "approved-p9-ae-rule-governance-v1",
        "report_sha256": report["report_sha256"],
        "candidate": candidate,
    }
    approved_candidate["approved_candidate_sha256"] = sha256_canonical_json(
        approved_candidate
    )
    return _read_json(_write_json(study / RULE_GOVERNANCE_APPROVED_PATH, approved_candidate))


def build_clean_ae_rule_reuse_context(query_result: Mapping[str, Any]) -> dict[str, Any]:
    """Build the P5 reuse context from a Wiki snapshot query result only."""

    if query_result.get("knowledge_id") != TARGET_KNOWLEDGE_ID:
        raise AERuleGovernanceError("clean query did not resolve the expected P9 rule")
    rule_ids = query_result.get("rule_ids")
    if not isinstance(rule_ids, list) or TARGET_RULE_ID not in rule_ids:
        raise AERuleGovernanceError("clean query result does not include the reusable rule id")
    context = {
        "schema_version": "1.0.0",
        "context_id": "ae-rule-reuse-context-p9-v1",
        "source": "clean_room_wiki_snapshot_query",
        "source_study_artifacts_read": False,
        "knowledge": {
            "snapshot_id": query_result["snapshot_id"],
            "snapshot_sha256": query_result["snapshot_sha256"],
            "rules": [{
                "knowledge_id": query_result["knowledge_id"],
                "knowledge_version": query_result["knowledge_version"],
                "rule_id": TARGET_RULE_ID,
            }],
        },
        "mapping_context_rule_refs": [TARGET_RULE_ID],
    }
    context["context_sha256"] = sha256_canonical_json(context)
    return context
