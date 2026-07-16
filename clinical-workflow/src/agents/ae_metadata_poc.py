"""P9 metadata-driven SDTM AE mapping and review boundary.

This module is deliberately separate from the P7 synthetic fixture adapter.  It
accepts a registered clinical source, a P3 minimum-information plan, and one
locked governed Wiki snapshot.  It emits a schema-constrained MappingSpec and
ReviewPacket; it never accepts or emits arbitrary executable commands.
"""

from __future__ import annotations

from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator, FormatChecker
import yaml

from src.knowledge.compatibility import sha256_canonical_json
from src.mcp_tools.edc_importer import (
    parse_registered_edc_source,
    validate_source_metadata_artifact,
)
from src.runtime.minimum_information import validate_minimum_information_plan
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


MAPPING_SCHEMA_PATH = Path(__file__).resolve().parent / "contracts" / (
    "ae-metadata-mapping-spec.schema.json"
)
MAPPING_CONTEXT_PATH = "work/mapping/ae-mapping-context.json"
MAPPING_CANDIDATE_PATH = "work/mapping/ae-mapping-spec-candidate.json"
MAPPING_APPROVED_PATH = "work/mapping/ae-mapping-spec-approved.json"
MAPPING_REVIEW_ID = "sdtm_spec_sample_ae_001_mapping_v1_001"

REQUIRED_RULE_IDS = (
    "proposal-sdtmig34-core-identifier-variable-role-v1",
    "proposal-sdtmig34-core-domain-code-consistency-v1",
    "proposal-sdtmig34-core-missing-values-as-nulls-v1",
    "proposal-sdtmig34-gold-ae-structure-v1",
    "proposal-sdtmig34-gold-aeterm-required-v1",
)
CONTROLLED_TARGETS = ("AESEV", "AESER", "AEREL", "AEACN", "AEOUT")
DAY_TARGETS = ("AESTDY", "AEENDY")


class AEMetadataPOCError(RuntimeError):
    """The P9 AE evidence chain is incomplete or has drifted."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AEMetadataPOCError(f"Cannot read trusted JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise AEMetadataPOCError(f"Trusted JSON object expected: {path}")
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _content_hash(payload: Mapping[str, Any], field: str) -> str:
    body = dict(payload)
    body.pop(field, None)
    return sha256_canonical_json(body)


def validate_mapping_spec(spec: Mapping[str, Any]) -> list[str]:
    schema = _read_json(MAPPING_SCHEMA_PATH)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(spec),
        key=lambda error: list(error.absolute_path),
    )
    violations = [
        f"{'/'.join(str(item) for item in error.absolute_path) or '$'}: {error.message}"
        for error in errors
    ]
    if not violations and spec.get("spec_sha256") != _content_hash(spec, "spec_sha256"):
        violations.append("spec_sha256: content hash mismatch")
    return violations


def _snapshot_rules(snapshot: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for card in snapshot.get("items", []):
        if card.get("approval_status") != "approved" or card.get("content_status") != "verified":
            continue
        for statement in card.get("statements", []):
            result[statement["rule_id"]] = statement
    return result


def _rule_evidence(
    snapshot: Mapping[str, Any],
    release: Mapping[str, Any],
    rule_ids: Iterable[str],
) -> list[dict[str, Any]]:
    snapshot_rules = _snapshot_rules(snapshot)
    extraction = release.get("extraction_package", {})
    statements = {
        item["statement_id"]: item for item in extraction.get("statements", [])
    }
    units = {
        item["locator"]["locator_id"]: item
        for item in extraction.get("units", [])
        if item.get("locator", {}).get("locator_id")
    }
    result = []
    for rule_id in rule_ids:
        if rule_id not in snapshot_rules:
            raise AEMetadataPOCError(f"Approved snapshot does not contain required rule: {rule_id}")
        statement = statements.get(rule_id)
        if not statement or statement.get("review_status") != "approved":
            raise AEMetadataPOCError(f"Approved extraction release missing rule: {rule_id}")
        locators = []
        for evidence in statement.get("evidence", []):
            locator_id = evidence.get("locator_id")
            unit = units.get(locator_id)
            if not unit or not unit.get("text_sha256"):
                raise AEMetadataPOCError(f"Rule locator is not closed: {rule_id}/{locator_id}")
            locators.append({
                "locator_id": locator_id,
                "artifact_id": evidence["artifact_id"],
                "artifact_sha256": evidence["artifact_sha256"],
                "text_sha256": unit["text_sha256"],
            })
        if not locators:
            raise AEMetadataPOCError(f"Approved rule has no locator: {rule_id}")
        result.append({
            "rule_id": rule_id,
            "statement": statement["statement"],
            "source_id": release["source_id"],
            "source_version": "SDTMIG 3.4",
            "source_sha256": release["source_sha256"],
            "locators": locators,
        })
    return result


def _source_variable_map(metadata: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(variable["name"]).upper(): dict(variable)
        for variable in metadata.get("variables", [])
        if isinstance(variable, Mapping) and variable.get("name")
    }


def _require_source_variable(
    variables: Mapping[str, dict[str, Any]], name: str
) -> dict[str, Any]:
    try:
        return variables[name.upper()]
    except KeyError as exc:
        raise AEMetadataPOCError(f"Required source variable is absent: {name}") from exc


def _reference_join_evidence(study: Path, source_data: Any) -> dict[str, Any]:
    reference_path = study / "input" / "raw" / "subject-reference.csv"
    if not reference_path.exists():
        return {"available": False, "source_subject_count": 0, "reference_subject_count": 0,
                "matched_subject_count": 0, "reason": "reference date source is absent"}
    with reference_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    reference_ids = {
        str(value).strip()
        for row in rows
        for value in (row.get("subject_id"), row.get("usubjid"))
        if value
    }
    source_ids = {
        str(value).strip()
        for value in source_data["Subject"].dropna().tolist()
        if str(value).strip()
    }
    matched = source_ids & reference_ids
    return {
        "available": bool(matched),
        "source_subject_count": len(source_ids),
        "reference_subject_count": len(rows),
        "matched_subject_count": len(matched),
        "reason": None if matched else "registered reference identifiers do not join to Source.Subject",
    }


def build_metadata_mapping_context(
    study_dir: str | Path,
    wiki_dir: str | Path,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Build a bounded, hash-locked P9 Mapping context without CRF dependency."""
    study = Path(study_dir).resolve()
    wiki = Path(wiki_dir).resolve()
    plan = _read_json(study / "work/derived/plans/minimum-information-sdtm-ae.json")
    plan_errors = validate_minimum_information_plan(plan)
    if plan_errors:
        raise AEMetadataPOCError(f"Minimum Information Plan invalid: {plan_errors[0]}")
    if plan["execution_eligibility"] not in {"draft_allowed", "canonical_candidate"}:
        raise AEMetadataPOCError("Minimum Information Plan does not allow a Mapping draft")

    metadata = _read_json(study / "work/derived/edc/source-metadata.json")
    metadata_errors = validate_source_metadata_artifact(metadata)
    if metadata_errors:
        raise AEMetadataPOCError(f"Source Metadata invalid: {metadata_errors[0]}")
    source = metadata["source"]
    parsed = parse_registered_edc_source(
        source["relative_path"],
        source["format"],
        allowed_root=study,
        expected_sha256=source["sha256"],
        generated_at=metadata["generated_at"],
    )
    if parsed.source_metadata["artifact_id"] != metadata["artifact_id"]:
        raise AEMetadataPOCError("Reparsed source identity differs from Source Metadata")

    snapshot_path = wiki / "snapshots/snapshot-sdtmig34-core-events-ae-v1.json"
    release_path = wiki / (
        "sources/packages/src-cdisc-sdtmig-3-4/approved-proposal-release.json"
    )
    snapshot = _read_json(snapshot_path)
    snapshot_content_sha = sha256_canonical_json({
        "schema_bundle": snapshot.get("schema_bundle"),
        "items": snapshot.get("items"),
    })
    if snapshot.get("sha256") != snapshot_content_sha:
        raise AEMetadataPOCError("Knowledge snapshot content hash drifted")
    if snapshot.get("snapshot_id") != "snapshot-sdtmig34-core-events-ae-v1":
        raise AEMetadataPOCError("Unexpected knowledge snapshot identity")
    release = _read_json(release_path)
    rules = _rule_evidence(snapshot, release, REQUIRED_RULE_IDS)

    project = yaml.safe_load((study / "project.yaml").read_text(encoding="utf-8"))
    if project.get("study_id") != plan["study_id"]:
        raise AEMetadataPOCError("Project and Minimum Information Plan study_id differ")
    variables = _source_variable_map(metadata)
    selected = {}
    for name in (
        "Subject", "RecordPosition", "AETERM", "AESTDAT", "AEENDAT",
        "AESEV_STD", "AESER_STD", "AEREL_STD", "AEACN_STD", "AEOUT_STD",
        "AETERM_PT", "AETERM_SOC", "AETERM_CoderDictName",
        "AETERM_CoderDictVersion",
    ):
        item = variables.get(name.upper())
        if item:
            selected[item["name"]] = item
    for required_name in ("Subject", "RecordPosition", "AETERM", "AESTDAT", "AEENDAT"):
        _require_source_variable(variables, required_name)

    context = {
        "schema_version": "1.0.0",
        "context_id": "ae-metadata-context-sample-ae-001-v1",
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "study": {"study_id": project["study_id"], "crf_required": False},
        "target_standard": {"name": "SDTMIG", "version": "3.4"},
        "source": {
            "metadata_artifact_id": metadata["artifact_id"],
            "relative_path": source["relative_path"],
            "format": source["format"],
            "sha256": source["sha256"],
            "row_count": metadata["dataset"]["row_count"],
            "variables": selected,
            "value_labels_status": metadata["metadata_availability"]["value_labels"]["status"],
        },
        "minimum_information_plan": {
            "plan_id": plan["plan_id"],
            "plan_sha256": plan["plan_sha256"],
            "execution_eligibility": plan["execution_eligibility"],
            "explicit_gaps": plan["explicit_gaps"],
        },
        "knowledge": {
            "snapshot_id": snapshot["snapshot_id"],
            "snapshot_version": snapshot["version"],
            "snapshot_sha256": snapshot["sha256"],
            "release_id": release["release_id"],
            "release_sha256": _sha256_file(release_path),
            "rules": rules,
        },
        "reference_join": _reference_join_evidence(study, parsed.data),
        "allowed_operations": [
            "constant", "concat", "sequence_by_group", "copy_trim", "partial_date_iso"
        ],
        "arbitrary_commands_allowed": False,
    }
    context["context_sha256"] = sha256_canonical_json(context)
    return context


def _mapping(
    mapping_id: str,
    target: str,
    operation: str,
    sources: Iterable[str],
    parameters: Mapping[str, Any],
    rule_refs: Iterable[str],
) -> dict[str, Any]:
    return {
        "mapping_id": mapping_id,
        "target_variable": target,
        "operation": operation,
        "source_variables": list(sources),
        "parameters": dict(parameters),
        "rule_refs": list(rule_refs),
        "review_status": "review_required",
    }


def build_mapping_candidate(context: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic regression candidate matching the LLM output schema."""
    if context.get("context_sha256") != _content_hash(context, "context_sha256"):
        raise AEMetadataPOCError("Mapping context content hash drifted")
    available = set(context["source"]["variables"])
    mappings = [
        _mapping("map-studyid", "STUDYID", "constant", [],
                 {"value": context["study"]["study_id"]},
                 ["proposal-sdtmig34-core-identifier-variable-role-v1"]),
        _mapping("map-domain", "DOMAIN", "constant", [], {"value": "AE"},
                 ["proposal-sdtmig34-core-domain-code-consistency-v1"]),
        _mapping("map-usubjid", "USUBJID", "concat", ["Subject"],
                 {"prefix": context["study"]["study_id"], "separator": "-"},
                 ["proposal-sdtmig34-core-identifier-variable-role-v1"]),
        _mapping("map-aeseq", "AESEQ", "sequence_by_group", ["Subject", "RecordPosition"],
                 {"group": "Subject", "order": "RecordPosition"},
                 ["proposal-sdtmig34-gold-ae-structure-v1"]),
        _mapping("map-aeterm", "AETERM", "copy_trim", ["AETERM"], {},
                 ["proposal-sdtmig34-gold-aeterm-required-v1"]),
        _mapping("map-aestdtc", "AESTDTC", "partial_date_iso", ["AESTDAT"], {},
                 ["proposal-sdtmig34-core-missing-values-as-nulls-v1"]),
        _mapping("map-aeendtc", "AEENDTC", "partial_date_iso", ["AEENDAT"], {},
                 ["proposal-sdtmig34-core-missing-values-as-nulls-v1"]),
    ]
    if "AETERM_PT" in available:
        mappings.append(_mapping("map-aedecod", "AEDECOD", "copy_trim", ["AETERM_PT"], {},
                                 ["proposal-sdtmig34-gold-ae-structure-v1"]))
    if "AETERM_SOC" in available:
        mappings.extend([
            _mapping("map-aebodsys", "AEBODSYS", "copy_trim", ["AETERM_SOC"], {},
                     ["proposal-sdtmig34-gold-ae-structure-v1"]),
            _mapping("map-aesoc", "AESOC", "copy_trim", ["AETERM_SOC"], {},
                     ["proposal-sdtmig34-gold-ae-structure-v1"]),
        ])

    gaps = []
    if context["source"]["value_labels_status"] != "available":
        gaps.append({
            "gap_id": "gap-controlled-value-labels",
            "category": "source_metadata",
            "description": "SAS catalog/value-label mapping unavailable; controlled fields are not mapped",
            "affects_variables": list(CONTROLLED_TARGETS),
            "blocking_for_canonical": False,
        })
    if not context["reference_join"]["available"]:
        gaps.append({
            "gap_id": "gap-reference-date-identity-no-overlap",
            "category": "study_context",
            "description": "Reference-date source cannot join to Source.Subject; study-day fields are omitted",
            "affects_variables": list(DAY_TARGETS),
            "blocking_for_canonical": False,
        })
    gaps.append({
        "gap_id": "gap-full-sdtmig-conformance-not-claimed",
        "category": "scope",
        "description": "This POC validates a bounded AE subset, not complete SDTMIG conformance",
        "affects_variables": ["AE"],
        "blocking_for_canonical": False,
    })
    rules = {item["rule_id"]: item for item in context["knowledge"]["rules"]}
    used_rule_ids = sorted({ref for item in mappings for ref in item["rule_refs"]})
    candidate = {
        "schema_version": "1.0.0",
        "spec_id": "ae-mapping-spec-sample-ae-001-v1",
        "study_id": context["study"]["study_id"],
        "target_dataset": "AE",
        "target_standard": context["target_standard"],
        "status": "candidate",
        "source": {
            key: context["source"][key]
            for key in ("metadata_artifact_id", "relative_path", "format", "sha256")
        },
        "minimum_information_plan": {
            key: context["minimum_information_plan"][key]
            for key in ("plan_id", "plan_sha256", "execution_eligibility")
        },
        "knowledge": {
            "snapshot_id": context["knowledge"]["snapshot_id"],
            "snapshot_version": context["knowledge"]["snapshot_version"],
            "snapshot_sha256": context["knowledge"]["snapshot_sha256"],
            "rules": [rules[rule_id] for rule_id in used_rule_ids],
        },
        "mappings": mappings,
        "explicit_gaps": gaps,
        "arbitrary_commands_allowed": False,
        "creates_stage_completion_evidence": False,
    }
    candidate["spec_sha256"] = sha256_canonical_json(candidate)
    violations = validate_mapping_spec(candidate)
    if violations:
        raise AEMetadataPOCError(f"Generated MappingSpec invalid: {violations[0]}")
    return candidate


def _mapping_review_packet(
    context: Mapping[str, Any], candidate: Mapping[str, Any]
) -> ReviewPacket:
    mapped = ", ".join(item["target_variable"] for item in candidate["mappings"])
    findings = [ReviewFinding(
        id="F-001",
        category=FindingCategory.MAPPING,
        severity=Severity.WARNING,
        location=MAPPING_CANDIDATE_PATH,
        title="确认基于真实 SAS7BDAT metadata 的 AE MappingSpec",
        current_value="MappingSpec 为候选状态，尚未生成或执行程序",
        proposed_value=f"批准以下变量进入受控程序生成：{mapped}",
        rationale=(
            "候选仅使用已登记来源、P3 最小信息计划和锁定 SDTMIG 3.4 Wiki 证据；"
            "CRF、Protocol、SAP 均不是本步骤的硬依赖。"
        ),
        evidence_refs=[MAPPING_CONTEXT_PATH, MAPPING_CANDIDATE_PATH],
    )]
    for index, gap in enumerate(candidate["explicit_gaps"], start=2):
        findings.append(ReviewFinding(
            id=f"F-{index:03d}",
            category=(FindingCategory.TERMINOLOGY
                      if gap["category"] == "source_metadata" else FindingCategory.MAPPING),
            severity=Severity.WARNING,
            location=f"AE:{','.join(gap['affects_variables'])}",
            title=f"确认保留显式缺口：{gap['gap_id']}",
            current_value=gap["description"],
            proposed_value="本轮不推断、不补齐，继续保留为可追溯 gap",
            rationale="证据不足的字段不得因名称相似或模型推测进入 mapped 状态。",
            evidence_refs=[MAPPING_CONTEXT_PATH, gap["gap_id"]],
        ))
    return ReviewPacket(
        review_id=MAPPING_REVIEW_ID,
        review_type=ReviewType.SDTM_SPEC,
        source_documents=[MAPPING_CONTEXT_PATH, MAPPING_CANDIDATE_PATH,
                          "work/derived/plans/minimum-information-sdtm-ae.json"],
        agent_summary=(
            "已完成最小信息规划后的 AE Mapping 候选。请审核来源变量、受控操作、Wiki 引用和"
            "显式缺口；批准前不会生成或执行 Python/R/SAS 程序。"
        ),
        findings=findings,
        urgency=Urgency.BLOCKING,
        generated_by="P9 Metadata-driven AE Mapping Planner",
    )


def prepare_metadata_mapping_review(
    study_dir: str | Path,
    wiki_dir: str | Path,
    *,
    generated_at: str | None = None,
) -> dict[str, str]:
    """Persist Mapping context/candidate and submit the runtime Human-loop packet."""
    study = Path(study_dir).resolve()
    context = build_metadata_mapping_context(study, wiki_dir, generated_at=generated_at)
    candidate = build_mapping_candidate(context)
    context_path = _write_json(study / MAPPING_CONTEXT_PATH, context)
    candidate_path = _write_json(study / MAPPING_CANDIDATE_PATH, candidate)
    packet_path = ReviewQueue(study).submit_packet(_mapping_review_packet(context, candidate))
    return {
        "status": "mapping_review_required",
        "context": _relative(study, context_path),
        "candidate": _relative(study, candidate_path),
        "review_packet": _relative(study, packet_path),
    }


def approve_mapping_from_receipt(study_dir: str | Path) -> dict[str, Any]:
    """Create an immutable approved MappingSpec only from a complete human receipt."""
    study = Path(study_dir).resolve()
    queue = ReviewQueue(study)
    packet = queue.load_packet(MAPPING_REVIEW_ID)
    receipt = queue.check_decision(MAPPING_REVIEW_ID)
    if packet is None or receipt is None:
        raise AEMetadataPOCError("Mapping ReviewPacket or DecisionReceipt is missing")
    if receipt.rejected_count() or receipt.modified_count():
        raise AEMetadataPOCError("Mapping receipt requires rework; approved spec not created")
    required = {finding.id for finding in packet.findings_needing_decision()}
    approved = {
        decision.finding_id for decision in receipt.decisions
        if decision.decision == Decision.APPROVED
    }
    if approved != required:
        raise AEMetadataPOCError("Every mapping finding must be approved before code generation")
    candidate = _read_json(study / MAPPING_CANDIDATE_PATH)
    violations = validate_mapping_spec(candidate)
    if violations:
        raise AEMetadataPOCError(f"Mapping candidate drifted: {violations[0]}")
    receipt_path = study / f".review_queue/{MAPPING_REVIEW_ID}_decision.json"
    approved_spec = dict(candidate)
    approved_spec["status"] = "approved"
    approved_spec["mappings"] = [
        {**mapping, "review_status": "approved"} for mapping in candidate["mappings"]
    ]
    approved_spec["approval"] = {
        "review_id": MAPPING_REVIEW_ID,
        "decision_receipt_sha256": _sha256_file(receipt_path),
        "approved_at": receipt.timestamp,
    }
    approved_spec["spec_sha256"] = _content_hash(approved_spec, "spec_sha256")
    violations = validate_mapping_spec(approved_spec)
    if violations:
        raise AEMetadataPOCError(f"Approved MappingSpec invalid: {violations[0]}")
    _write_json(study / MAPPING_APPROVED_PATH, approved_spec)
    return approved_spec
