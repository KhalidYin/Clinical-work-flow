"""P9 AE Human-loop orchestration after MappingSpec approval."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from src.agents.ae_metadata_poc import (
    AEMetadataPOCError,
    MAPPING_APPROVED_PATH,
    approve_mapping_from_receipt,
    validate_mapping_spec,
)
from src.codegen.ae_programs import (
    DRAFT_DATASET_PATH,
    EXECUTION_LOG_PATH,
    PROGRAM_MANIFEST_PATH,
    PROVENANCE_PATH,
    TRACEABILITY_PATH,
    VALIDATION_PATH,
    generate_program_artifacts,
    run_python_reference,
)
from src.runtime.review_protocol import (
    CONFIRMATION_RECEIPT_SCHEMA,
    Decision,
    FindingCategory,
    ReviewFinding,
    ReviewPacket,
    ReviewQueue,
    ReviewType,
    Severity,
    Urgency,
)


PROGRAM_REVIEW_ID = "sdtm_spec_sample_ae_001_program_v1_001"
CANONICAL_DATASET_PATH = "output/sdtm/datasets/ae.csv"
CANONICAL_TRACEABILITY_PATH = "output/sdtm/traceability/ae-canonical-traceability.json"
VALIDATION_REVIEW_PREFIX = "sdtm_spec_sample_ae_001_validation"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AEMetadataPOCError(f"Cannot read trusted JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise AEMetadataPOCError(f"JSON object expected: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _program_review_packet(
    spec: Mapping[str, Any], manifest: Mapping[str, Any], execution: Mapping[str, Any]
) -> ReviewPacket:
    languages = ", ".join(item["language"] for item in manifest["programs"])
    findings = [
        ReviewFinding(
            id="F-001",
            category=FindingCategory.COMPLIANCE,
            severity=Severity.WARNING,
            location=DRAFT_DATASET_PATH,
            title="确认 Python reference AE draft 可提升为 POC canonical",
            current_value=(
                f"draft 已写入，共 {execution['row_count']} 行、{execution['column_count']} 列；"
                "完整 SDTMIG conformity 未声明"
            ),
            proposed_value="批准在 POC 范围内提升为 canonical CSV",
            rationale=(
                "draft 由已批准 MappingSpec 和登记的 SAS7BDAT 经注册 Python adapter 生成，"
                "validation、provenance、traceability 均已落盘。"
            ),
            evidence_refs=[DRAFT_DATASET_PATH, PROVENANCE_PATH, TRACEABILITY_PATH],
        ),
        ReviewFinding(
            id="F-002",
            category=FindingCategory.MAPPING,
            severity=Severity.WARNING,
            location=PROGRAM_MANIFEST_PATH,
            title="确认三语言程序共享同一 MappingSpec",
            current_value=f"已生成 {languages}；仅 Python 作为本轮 reference adapter 执行",
            proposed_value="接受 R/SAS 为待独立 QC/运行环境确认的代码产物",
            rationale="三种语言共享 MappingSpec ID/hash、source hash、rule refs 和 SDTMIG 3.4 锁。",
            evidence_refs=[PROGRAM_MANIFEST_PATH, MAPPING_APPROVED_PATH],
        ),
    ]
    for index, gap in enumerate(spec["explicit_gaps"], start=3):
        findings.append(ReviewFinding(
            id=f"F-{index:03d}",
            category=(FindingCategory.TERMINOLOGY
                      if gap["category"] == "source_metadata" else FindingCategory.COMPLIANCE),
            severity=Severity.WARNING,
            location=f"AE:{','.join(gap['affects_variables'])}",
            title=f"确认 canonical 继续保留缺口：{gap['gap_id']}",
            current_value=gap["description"],
            proposed_value="不补齐该范围，保留在 canonical traceability",
            rationale="POC canonical 表示本轮受控产物，不代表缺口已解决或完整申报合规。",
            evidence_refs=[TRACEABILITY_PATH, gap["gap_id"]],
        ))
    for summary_index, summary in enumerate(execution.get("deferred_review_summary") or []):
        finding_index = len(findings) + 1
        variable = str(summary.get("variable") or "dataset")
        count = int(summary.get("count", 0))
        row_count = int(summary.get("row_count", execution["row_count"]))
        check_code = str(summary.get("check_code") or "validation")
        findings.append(ReviewFinding(
            id=f"F-{finding_index:03d}",
            category=FindingCategory.COMPLIANCE,
            severity=Severity.WARNING,
            location=f"{VALIDATION_PATH}#deferred_review_summary/{summary_index}",
            title=f"后审 AE 数据问题：{variable}",
            current_value=(
                f"检查 {check_code} 发现 {count}/{row_count} 条记录受影响；"
                "reference adapter 已保留全部记录"
            ),
            proposed_value=(
                "本轮不自动过滤或补值；保留问题及行级 finding，供数据修复与后续 QC 跟踪。"
            ),
            rationale=(
                "该 finding 影响数据内容质量，但不破坏本轮程序执行、行级保留或证据追溯，"
                "因此按受控策略延后到 Program Review。"
            ),
            evidence_refs=[
                VALIDATION_PATH,
                EXECUTION_LOG_PATH,
                *[str(item) for item in summary.get("finding_ids", [])[:20]],
            ],
        ))
    deferred_count = sum(
        int(item.get("count", 0))
        for item in execution.get("deferred_review_summary") or []
    )
    return ReviewPacket(
        review_id=PROGRAM_REVIEW_ID,
        review_type=ReviewType.SDTM_SPEC,
        source_documents=[MAPPING_APPROVED_PATH, PROGRAM_MANIFEST_PATH, DRAFT_DATASET_PATH,
                          VALIDATION_PATH, EXECUTION_LOG_PATH, PROVENANCE_PATH,
                          TRACEABILITY_PATH],
        agent_summary=(
            "已完成批准 MappingSpec 的三语言程序生成和 Python reference execution。"
            f"验证中有 {deferred_count} 项可后审数据问题，未触发程序执行阻断。"
            "请审核 draft、验证结果及显式缺口；全部批准后才会提升 canonical。"
        ),
        findings=findings,
        urgency=Urgency.BLOCKING,
        generated_by="P9 Metadata-driven AE Runtime",
    )


def _validation_review_packet(
    validation: Mapping[str, Any],
    review_id: str,
) -> ReviewPacket:
    row_count = int(validation.get("observed_row_count", 0))
    summaries = list(validation.get("blocking_summary") or [])
    findings = []
    for index, summary in enumerate(summaries, start=1):
        variable = str(summary.get("variable") or "dataset")
        count = int(summary.get("count", 0))
        check_code = str(summary.get("check_code") or "validation")
        findings.append(
            ReviewFinding(
                id=f"F-{index:03d}",
                category=FindingCategory.COMPLIANCE,
                severity=Severity.CRITICAL,
                location=f"{VALIDATION_PATH}#blocking_summary/{index - 1}",
                title=f"确认 AE 验证阻断：{variable}",
                current_value=(
                    f"检查 {check_code} 发现 {count}/{row_count} 条记录受影响；"
                    f"影响变量：{variable}"
                ),
                proposed_value=(
                    "保持 canonical 生成阻断；由人工确认源数据修复，或通过新的 MappingSpec "
                    "明确受控处理规则后再 Retry current step。"
                ),
                rationale=(
                    "验证失败属于数据/业务约束，不得由 Runtime 自动过滤、补值或视为普通 codegen 异常。"
                ),
                evidence_refs=[
                    VALIDATION_PATH,
                    EXECUTION_LOG_PATH,
                    *[str(item) for item in summary.get("finding_ids", [])[:20]],
                ],
            )
        )
    if not findings:
        raise AEMetadataPOCError("Validation review requires blocking_summary evidence")
    return ReviewPacket(
        review_id=review_id,
        review_type=ReviewType.SDTM_SPEC,
        source_documents=[
            MAPPING_APPROVED_PATH,
            PROGRAM_MANIFEST_PATH,
            VALIDATION_PATH,
            EXECUTION_LOG_PATH,
        ],
        agent_summary=(
            "Python reference execution 已完成确定性检查，但存在阻断性验证结果。"
            "请确认修复路径；本审核不会自动删除、过滤或补造源记录。"
        ),
        findings=findings,
        urgency=Urgency.BLOCKING,
        generated_by="P9 Metadata-driven AE Runtime",
    )


def prepare_validation_review(study_dir: str | Path) -> dict[str, Any]:
    """Create one evidence-addressed packet without overwriting prior evidence."""

    study = Path(study_dir).resolve()
    validation_path = study / VALIDATION_PATH
    validation = _read_json(validation_path)
    if not validation.get("blocking_findings"):
        raise AEMetadataPOCError("Validation review requires blocking findings")
    digest = _sha256(validation_path)[:12]
    review_id = f"{VALIDATION_REVIEW_PREFIX}_{digest}_v1_001"
    queue = ReviewQueue(study)
    packet_path = study / f".review_queue/{review_id}.json"
    if queue.load_packet(review_id) is None:
        packet_path = queue.submit_packet(_validation_review_packet(validation, review_id))
    return {
        "status": "validation_review_required",
        "review_id": review_id,
        "review_packet_path": _relative(study, packet_path),
        "validation_path": VALIDATION_PATH,
        "blocking_summary": list(validation.get("blocking_summary") or []),
        "canonical_dataset_path": None,
    }


def ensure_approved_mapping(study_dir: str | Path) -> dict[str, Any]:
    """Reuse a valid approved spec; otherwise apply the current mapping receipt."""

    study = Path(study_dir).resolve()
    approved_path = study / MAPPING_APPROVED_PATH
    if approved_path.exists():
        spec = _read_json(approved_path)
        violations = validate_mapping_spec(spec)
        if violations or spec.get("status") != "approved":
            raise AEMetadataPOCError(
                f"Approved MappingSpec invalid: {violations[0] if violations else spec.get('status')}"
            )
        return spec
    return approve_mapping_from_receipt(study)


def retry_validation_after_review(study_dir: str | Path) -> dict[str, Any]:
    """Re-run only the registered Python validation after a validation review."""

    study = Path(study_dir).resolve()
    spec = ensure_approved_mapping(study)
    manifest = _read_json(study / PROGRAM_MANIFEST_PATH)
    try:
        execution = run_python_reference(study)
    except AEMetadataPOCError as exc:
        validation_path = study / VALIDATION_PATH
        if str(exc) == "Blocking AE reference validation finding" and validation_path.exists():
            return {
                **prepare_validation_review(study),
                "program_manifest_path": PROGRAM_MANIFEST_PATH,
            }
        raise
    queue = ReviewQueue(study)
    packet_path = study / f".review_queue/{PROGRAM_REVIEW_ID}.json"
    if queue.load_packet(PROGRAM_REVIEW_ID) is None:
        packet_path = queue.submit_packet(_program_review_packet(spec, manifest, execution))
    return {
        **execution,
        "status": "program_review_required",
        "program_manifest_path": PROGRAM_MANIFEST_PATH,
        "review_packet_path": _relative(study, packet_path),
        "canonical_dataset_path": None,
    }


def run_after_mapping_approval(study_dir: str | Path) -> dict[str, Any]:
    """Apply mapping receipt, generate code, run Python, then pause for program review."""
    study = Path(study_dir).resolve()
    spec = ensure_approved_mapping(study)
    manifest = generate_program_artifacts(study)
    try:
        execution = run_python_reference(study)
    except AEMetadataPOCError as exc:
        validation_path = study / VALIDATION_PATH
        if str(exc) == "Blocking AE reference validation finding" and validation_path.exists():
            return {
                **prepare_validation_review(study),
                "program_manifest_path": PROGRAM_MANIFEST_PATH,
            }
        raise
    packet_path = ReviewQueue(study).submit_packet(
        _program_review_packet(spec, manifest, execution)
    )
    return {
        **execution,
        "status": "program_review_required",
        "program_manifest_path": PROGRAM_MANIFEST_PATH,
        "review_packet_path": _relative(study, packet_path),
        "canonical_dataset_path": None,
    }


def _write_confirmation(study: Path, receipt: Any, *, applied: bool) -> Path:
    application_status = "applied" if applied else "failed"
    payload = {
        "review_id": PROGRAM_REVIEW_ID,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "P9 Metadata-driven AE Runtime",
        "results": [
            {
                "finding_id": decision.finding_id,
                "original_decision": decision.decision.value,
                "application_status": application_status,
                "actual_value": (
                    "canonical AE promoted" if applied else "canonical AE not promoted"
                ),
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
    violations = list(Draft202012Validator(
        CONFIRMATION_RECEIPT_SCHEMA,
        format_checker=FormatChecker(),
    ).iter_errors(payload))
    if violations:
        raise AEMetadataPOCError(f"ConfirmationReceipt invalid: {violations[0].message}")
    return _write_json(study / f".review_queue/{PROGRAM_REVIEW_ID}_confirmation.json", payload)


def apply_program_review(study_dir: str | Path) -> dict[str, Any]:
    """Promote only an unchanged draft after a complete positive DecisionReceipt."""
    study = Path(study_dir).resolve()
    queue = ReviewQueue(study)
    packet = queue.load_packet(PROGRAM_REVIEW_ID)
    receipt = queue.check_decision(PROGRAM_REVIEW_ID)
    if packet is None or receipt is None:
        raise AEMetadataPOCError("Program ReviewPacket or DecisionReceipt is missing")
    if receipt.rejected_count() or receipt.modified_count():
        _write_confirmation(study, receipt, applied=False)
        return {"status": "rework_required", "canonical_dataset_path": None}
    required = {finding.id for finding in packet.findings_needing_decision()}
    approved = {
        decision.finding_id for decision in receipt.decisions
        if decision.decision == Decision.APPROVED
    }
    if approved != required:
        raise AEMetadataPOCError("Every program finding must be approved before promotion")

    draft = study / DRAFT_DATASET_PATH
    provenance_path = study / PROVENANCE_PATH
    trace_path = study / TRACEABILITY_PATH
    if not draft.exists() or not provenance_path.exists() or not trace_path.exists():
        raise AEMetadataPOCError("Draft/provenance/traceability artifact is missing")
    provenance = _read_json(provenance_path)
    trace = _read_json(trace_path)
    if _sha256(draft) != provenance.get("draft_dataset_sha256"):
        raise AEMetadataPOCError("Draft dataset hash drifted after review")
    if _sha256(trace_path) != provenance.get("traceability_sha256"):
        raise AEMetadataPOCError("Draft traceability hash drifted after review")
    spec = _read_json(study / MAPPING_APPROVED_PATH)
    if provenance.get("mapping_spec_sha256") != spec.get("spec_sha256"):
        raise AEMetadataPOCError("Provenance and approved MappingSpec hashes differ")
    for rule_id, evidence in provenance.get("rule_evidence", {}).items():
        if not evidence.get("locators"):
            raise AEMetadataPOCError(f"Rule evidence is not closed: {rule_id}")

    canonical = study / CANONICAL_DATASET_PATH
    canonical.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(draft, canonical)
    receipt_path = study / f".review_queue/{PROGRAM_REVIEW_ID}_decision.json"
    canonical_trace = {
        **trace,
        "canonical_dataset_path": CANONICAL_DATASET_PATH,
        "canonical_dataset_sha256": _sha256(canonical),
        "promotion_review_id": PROGRAM_REVIEW_ID,
        "decision_receipt_sha256": _sha256(receipt_path),
        "scope_statement": (
            "P9 bounded SDTM AE POC only; explicit gaps remain and complete SDTMIG conformity "
            "is not claimed."
        ),
    }
    canonical_trace_path = _write_json(study / CANONICAL_TRACEABILITY_PATH, canonical_trace)
    confirmation_path = _write_confirmation(study, receipt, applied=True)
    return {
        "status": "canonical_written",
        "canonical_dataset_path": CANONICAL_DATASET_PATH,
        "canonical_dataset_sha256": _sha256(canonical),
        "canonical_traceability_path": _relative(study, canonical_trace_path),
        "confirmation_receipt_path": _relative(study, confirmation_path),
    }
