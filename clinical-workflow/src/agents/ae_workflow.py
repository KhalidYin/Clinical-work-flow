"""P7 AE vertical workflow orchestrator.

This module turns the P2/P3 building blocks into one file-protocol workflow:
request → knowledge context → MappingSpec gate → controlled execution →
ReviewPacket → DecisionReceipt → ConfirmationReceipt → canonical AE.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .ae_execution import AEExecutionArtifact, run_controlled_ae_execution
from src.runtime.review_protocol import (
    CONFIRMATION_RECEIPT_SCHEMA,
    Decision,
    DecisionReceipt,
    FindingCategory,
    FindingDecision,
    RejectionReason,
    ReviewFinding,
    ReviewPacket,
    ReviewQueue,
    ReviewType,
    Severity,
    Urgency,
)


AE_REVIEW_ID = "sdtm_spec_ae_v1_001"


class AEWorkflowError(RuntimeError):
    """The P7 AE workflow cannot continue safely."""


@dataclass(frozen=True, slots=True)
class AEWorkflowResult:
    """End-to-end P7 AE workflow status."""

    status: str
    review_id: str
    draft_dataset_path: str | None
    canonical_dataset_path: str | None
    traceability_report_path: str | None
    confirmation_receipt_path: str | None
    review_packet_path: str
    decision_receipt_path: str | None
    canonical_dataset_sha256: str | None


def build_sdtm_ae_dataset(
    study_dir: str | Path,
    wiki_package_dir: str | Path,
    *,
    user_request: str = "生成 AE 数据集",
    auto_approve: bool = False,
    reviewer: str = "P7 synthetic AE reviewer",
) -> AEWorkflowResult:
    """Run the P7 AE vertical chain from a user request.

    With `auto_approve=False`, the function stops after writing the blocking
    ReviewPacket.  With `auto_approve=True`, it writes a fixture approval
    DecisionReceipt and applies it, proving the full synthetic baseline.
    """

    study = Path(study_dir)
    package = Path(wiki_package_dir)
    execution = run_controlled_ae_execution(study, package)
    if execution.status != "draft_written":
        raise AEWorkflowError("controlled AE execution did not produce a draft dataset")
    packet = build_ae_acceptance_packet(study, package, execution, user_request=user_request)
    queue = ReviewQueue(study)
    packet_path = queue.submit_packet(packet)
    if not auto_approve:
        return AEWorkflowResult(
            status="review_required",
            review_id=packet.review_id,
            draft_dataset_path=execution.draft_dataset_path,
            canonical_dataset_path=None,
            traceability_report_path=None,
            confirmation_receipt_path=None,
            review_packet_path=_relative(study, packet_path),
            decision_receipt_path=None,
            canonical_dataset_sha256=None,
        )
    receipt_path = submit_fixture_ae_acceptance(study, packet.review_id, reviewer=reviewer)
    applied = apply_ae_review_decision(study, package, packet.review_id)
    return AEWorkflowResult(
        status=applied.status,
        review_id=packet.review_id,
        draft_dataset_path=execution.draft_dataset_path,
        canonical_dataset_path=applied.canonical_dataset_path,
        traceability_report_path=applied.traceability_report_path,
        confirmation_receipt_path=applied.confirmation_receipt_path,
        review_packet_path=_relative(study, packet_path),
        decision_receipt_path=_relative(study, receipt_path),
        canonical_dataset_sha256=applied.canonical_dataset_sha256,
    )


def build_ae_acceptance_packet(
    study_dir: str | Path,
    wiki_package_dir: str | Path,
    execution: AEExecutionArtifact,
    *,
    user_request: str,
) -> ReviewPacket:
    """Create the blocking Chinese ReviewPacket for P7 AE promotion."""

    study = Path(study_dir)
    package = Path(wiki_package_dir)
    candidate = _read_json(study / "mapping-specs" / "ae-mapping-spec-success.json")
    citation_bundle = _read_json(package / "ae-citation-bundle.json")
    findings = [
        ReviewFinding(
            id="F-001",
            category=FindingCategory.COMPLIANCE,
            severity=Severity.WARNING,
            location="output/sdtm/drafts/ae.csv",
            title="确认 P7 合成 AE draft 可提升为 canonical",
            current_value="draft AE 已通过 P1 expected baseline 验证；canonical 尚未生成",
            proposed_value="批准将 draft AE 提升为 P7 synthetic canonical AE",
            rationale=(
                "该批准仅适用于 P7 synthetic fixture。执行结果、MappingSpec、"
                "validation report 和 provenance 均已锁定；不声明真实 Study 或 GxP 批准。"
            ),
            evidence_refs=[
                execution.draft_dataset_path or "",
                execution.validation_report_path,
                execution.provenance_path or "",
                "expected/sdtm/ae.csv",
            ],
        )
    ]
    for index, gap in enumerate(candidate["gaps"], start=2):
        source_gap = next(
            item for item in citation_bundle["coverage_gaps"] if item["gap_id"] == gap["source_gap_id"]
        )
        findings.append(
            ReviewFinding(
                id=f"F-{index:03d}",
                category=_gap_category(gap),
                severity=Severity.WARNING,
                location=f"AE.{gap['target_variable']}",
                title=f"保留 {gap['target_variable']} 为显式知识缺口",
                current_value="P6/P7 当前没有批准的可执行规则",
                proposed_value="本次 canonical AE 不生成该变量，并在 traceability 中保留 gap",
                rationale=(
                    f"{source_gap['topic']} 仍是 {source_gap['status']}；"
                    "Workflow 必须停在结构化审核或显式范围批准，不能由 LLM 推断补齐。"
                ),
                evidence_refs=[gap["source_gap_id"], gap["gap_id"]],
            )
        )
    return ReviewPacket(
        review_id=AE_REVIEW_ID,
        review_type=ReviewType.SDTM_SPEC,
        source_documents=[
            "mapping-specs/ae-mapping-spec-success.json",
            execution.program_manifest_path,
            execution.validation_report_path,
            execution.provenance_path or "",
            "expected/sdtm/ae.csv",
        ],
        agent_summary=(
            f"用户请求：{user_request}。系统已完成一次 Wiki context 查询、MappingSpec 引用闭合、"
            "受控 adapter 执行和 SDTM AE draft 验证。请批量确认是否将该 synthetic draft 提升为 canonical，"
            "并确认 AEDECOD、AESEV、AEENRF 继续作为显式 gap。"
        ),
        findings=findings,
        urgency=Urgency.BLOCKING,
        generated_by="P7 AE Workflow Orchestrator",
        auto_approved_count=0,
    )


def submit_fixture_ae_acceptance(
    study_dir: str | Path,
    review_id: str = AE_REVIEW_ID,
    *,
    reviewer: str = "P7 synthetic AE reviewer",
) -> Path:
    """Write a fixture approval DecisionReceipt for all findings in the packet."""

    study = Path(study_dir)
    queue = ReviewQueue(study)
    packet = queue.load_packet(review_id)
    if packet is None:
        raise AEWorkflowError(f"ReviewPacket not found: {review_id}")
    receipt = DecisionReceipt(
        review_id=review_id,
        reviewer=reviewer,
        decisions=[
            FindingDecision(
                finding_id=finding.id,
                decision=Decision.APPROVED,
                comment="P7 synthetic baseline approval only; not a real Study approval.",
            )
            for finding in packet.findings_needing_decision()
        ],
        general_notes="批准 P7 合成 AE 基线闭环；3 个 gap 保持显式未解决。",
    )
    return queue.submit_decision(receipt)


def submit_fixture_ae_rejection(
    study_dir: str | Path,
    review_id: str = AE_REVIEW_ID,
    *,
    reviewer: str = "P7 synthetic AE reviewer",
) -> Path:
    """Write a fixture rejection receipt for rework-path regression tests."""

    study = Path(study_dir)
    queue = ReviewQueue(study)
    packet = queue.load_packet(review_id)
    if packet is None:
        raise AEWorkflowError(f"ReviewPacket not found: {review_id}")
    receipt = DecisionReceipt(
        review_id=review_id,
        reviewer=reviewer,
        decisions=[
            FindingDecision(
                finding_id=finding.id,
                decision=Decision.REJECTED,
                rejection_reason=RejectionReason.INSUFFICIENT_EVIDENCE,
                comment="Synthetic rework regression.",
            )
            for finding in packet.findings_needing_decision()
        ],
        general_notes="拒绝本次 synthetic AE promotion，用于 rework 回归。",
    )
    return queue.submit_decision(receipt)


def apply_ae_review_decision(
    study_dir: str | Path,
    wiki_package_dir: str | Path,
    review_id: str = AE_REVIEW_ID,
) -> AEWorkflowResult:
    """Apply a DecisionReceipt and promote draft AE only when all gates pass."""

    study = Path(study_dir)
    package = Path(wiki_package_dir)
    queue = ReviewQueue(study)
    packet = queue.load_packet(review_id)
    receipt = queue.check_decision(review_id)
    if packet is None or receipt is None:
        raise AEWorkflowError(f"ReviewPacket or DecisionReceipt missing for {review_id}")
    if receipt.rejected_count():
        rework_path = _write_rework(study, packet, receipt)
        confirmation_path = _write_confirmation(study, review_id, receipt, applied=False)
        return AEWorkflowResult(
            status="rework_required",
            review_id=review_id,
            draft_dataset_path="output/sdtm/drafts/ae.csv",
            canonical_dataset_path=None,
            traceability_report_path=_relative(study, rework_path),
            confirmation_receipt_path=_relative(study, confirmation_path),
            review_packet_path=f".review_queue/{review_id}.json",
            decision_receipt_path=f".review_queue/{review_id}_decision.json",
            canonical_dataset_sha256=None,
        )
    if receipt.approved_count() != len(packet.findings_needing_decision()):
        raise AEWorkflowError("all P7 AE review findings must be approved before promotion")

    draft_path = study / "output" / "sdtm" / "drafts" / "ae.csv"
    draft_provenance_path = study / "output" / "sdtm" / "drafts" / "ae.csv.provenance.json"
    if not draft_path.exists() or not draft_provenance_path.exists():
        raise AEWorkflowError("draft AE artifact or provenance missing")
    draft_provenance = _read_json(draft_provenance_path)
    _assert_traceability_closed(draft_provenance)

    canonical_path = study / "output" / "sdtm" / "datasets" / "ae.csv"
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(draft_path, canonical_path)
    canonical_sha256 = _sha256_file(canonical_path)
    traceability = _traceability_report(
        study=study,
        package=package,
        review_id=review_id,
        receipt=receipt,
        draft_provenance=draft_provenance,
        canonical_path=canonical_path,
        canonical_sha256=canonical_sha256,
    )
    traceability_path = study / "output" / "sdtm" / "traceability" / "ae_traceability_report.json"
    _write_json(traceability_path, traceability)
    canonical_provenance_path = canonical_path.with_suffix(".csv.provenance.json")
    canonical_provenance = {
        **draft_provenance,
        "canonical_dataset_path": _relative(study, canonical_path),
        "canonical_dataset_sha256": canonical_sha256,
        "promotion_review_id": review_id,
        "decision_receipt_sha256": _sha256_file(study / f".review_queue/{review_id}_decision.json"),
        "traceability_report_path": _relative(study, traceability_path),
        "traceability_report_sha256": _sha256_file(traceability_path),
    }
    _write_json(canonical_provenance_path, canonical_provenance)
    confirmation_path = _write_confirmation(study, review_id, receipt, applied=True)
    return AEWorkflowResult(
        status="canonical_written",
        review_id=review_id,
        draft_dataset_path="output/sdtm/drafts/ae.csv",
        canonical_dataset_path=_relative(study, canonical_path),
        traceability_report_path=_relative(study, traceability_path),
        confirmation_receipt_path=_relative(study, confirmation_path),
        review_packet_path=f".review_queue/{review_id}.json",
        decision_receipt_path=f".review_queue/{review_id}_decision.json",
        canonical_dataset_sha256=canonical_sha256,
    )


def _gap_category(gap: dict[str, Any]) -> FindingCategory:
    if gap.get("review_type") == "ct_gap":
        return FindingCategory.TERMINOLOGY
    if gap.get("review_type") == "study_context_gap":
        return FindingCategory.DERIVATION
    return FindingCategory.MAPPING


def _write_rework(study: Path, packet: ReviewPacket, receipt: DecisionReceipt) -> Path:
    path = study / f".review_queue/{packet.review_id}_rework.json"
    payload = {
        "review_id": packet.review_id,
        "status": "rework_required",
        "rejected_findings": [
            {
                "finding_id": decision.finding_id,
                "decision": decision.decision.value,
                "rejection_reason": decision.rejection_reason.value
                if decision.rejection_reason
                else None,
                "comment": decision.comment,
            }
            for decision in receipt.decisions
            if decision.decision == Decision.REJECTED
        ],
    }
    _write_json(path, payload)
    return path


def _write_confirmation(
    study: Path,
    review_id: str,
    receipt: DecisionReceipt,
    *,
    applied: bool,
) -> Path:
    status = "applied" if applied else "failed"
    payload = {
        "review_id": review_id,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "P7 AE Workflow Orchestrator",
        "results": [
            {
                "finding_id": decision.finding_id,
                "original_decision": decision.decision.value,
                "application_status": status,
                "actual_value": "canonical AE promoted" if applied else "canonical AE not promoted",
            }
            for decision in receipt.decisions
        ],
        "summary": {
            "total": len(receipt.decisions),
            "applied": len(receipt.decisions) if applied else 0,
            "adjusted": 0,
            "failed": 0 if applied else len(receipt.decisions),
        },
    }
    violations = sorted(
        Draft202012Validator(
            CONFIRMATION_RECEIPT_SCHEMA,
            format_checker=FormatChecker(),
        ).iter_errors(payload),
        key=lambda item: list(item.absolute_path),
    )
    if violations:
        raise AEWorkflowError(f"ConfirmationReceipt schema violation: {violations[0].message}")
    path = study / f".review_queue/{review_id}_confirmation.json"
    _write_json(path, payload)
    return path


def _traceability_report(
    *,
    study: Path,
    package: Path,
    review_id: str,
    receipt: DecisionReceipt,
    draft_provenance: dict[str, Any],
    canonical_path: Path,
    canonical_sha256: str,
) -> dict[str, Any]:
    citation_bundle = _read_json(package / "ae-citation-bundle.json")
    source_version = citation_bundle["source"]["source_version"]
    rules = []
    for rule_id, evidence in sorted(draft_provenance["applied_rule_evidence"].items()):
        mapping_ids = [
            mapping["mapping_id"]
            for mapping in draft_provenance["applied_mappings"]
            if rule_id in mapping["rule_refs"]
        ]
        rules.append(
            {
                "rule_id": rule_id,
                "mapping_ids": mapping_ids,
                "source_version": source_version,
                "evidence": evidence,
            }
        )
    study_decisions = sorted(
        {
            ref
            for mapping in draft_provenance["applied_mappings"]
            for ref in mapping.get("study_decision_refs", [])
        }
    )
    return {
        "traceability_id": "ae-traceability-synth-ae-001-v1",
        "target_dataset": "AE",
        "synthetic_only": True,
        "review_id": review_id,
        "decision_receipt_sha256": _sha256_file(study / f".review_queue/{review_id}_decision.json"),
        "canonical_dataset_path": _relative(study, canonical_path),
        "canonical_dataset_sha256": canonical_sha256,
        "context_sha256": draft_provenance["context_sha256"],
        "mapping_spec_sha256": draft_provenance["mapping_spec_sha256"],
        "program_manifest_path": draft_provenance["program_manifest_path"],
        "validation_report_path": draft_provenance["validation_report_path"],
        "applied_rules": rules,
        "applied_study_decisions": study_decisions,
        "explicit_gaps": draft_provenance["explicit_gaps"],
        "receipt_summary": receipt.summary(),
        "scope_statement": "P7 synthetic AE baseline only; not GxP or real Study approval.",
    }


def _assert_traceability_closed(draft_provenance: dict[str, Any]) -> None:
    applied_rules = {ref for mapping in draft_provenance["applied_mappings"] for ref in mapping["rule_refs"]}
    evidence_by_rule = draft_provenance.get("applied_rule_evidence", {})
    missing_rules = applied_rules - set(evidence_by_rule)
    if missing_rules:
        raise AEWorkflowError(f"applied rule evidence missing: {sorted(missing_rules)}")
    for rule_id, evidence_items in evidence_by_rule.items():
        if not evidence_items:
            raise AEWorkflowError(f"applied rule has no evidence: {rule_id}")
        for item in evidence_items:
            for key in ("source_id", "artifact_id", "locator_id", "artifact_sha256"):
                if not item.get(key):
                    raise AEWorkflowError(f"applied rule evidence missing {key}: {rule_id}")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Test/helper API for comparing generated AE datasets."""

    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
