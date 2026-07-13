"""Structured runtime-context resolution with no executable instruction channel."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .contracts import SchemaBundle, canonical_json_sha256
from .repository import VaultRepository
from .snapshot import SnapshotError, load_locked_snapshot


_STAGES = frozenset({
    "protocol_analysis", "sap_generation", "sdtm_spec", "sdtm_programming",
    "adam_spec", "adam_programming", "tfl_shell_design", "tfl_programming",
    "qc_validation", "submission_packaging",
})
_SYNTHETIC_PILOT_CONDITION = "synthetic-pilot-only"
_SYNTHETIC_PILOT_STUDY = "SYNTH-ONCO-001"


class ResolutionError(ValueError):
    """A runtime request is malformed or cannot satisfy fail-closed conditions."""


def resolve_runtime_context(
    repository: VaultRepository, bundle: SchemaBundle, request: dict[str, Any]
) -> dict[str, Any]:
    schema_lock = request.get("schema_bundle")
    if not isinstance(schema_lock, dict):
        raise ResolutionError("schema_bundle version/hash lock is required")
    bundle.assert_requested(schema_lock)
    study_id = request.get("study_id")
    stage = request.get("stage")
    manifest = request.get("runtime_manifest")
    if not isinstance(study_id, str) or not study_id:
        raise ResolutionError("study_id is required")
    if stage not in _STAGES:
        raise ResolutionError("stage must be one of the fixed pipeline stages")
    if not isinstance(manifest, dict):
        raise ResolutionError("runtime_manifest is required")
    _validate_manifest(bundle, manifest, study_id)
    _reject_control_fields(request)
    try:
        workflow_snapshot = load_locked_snapshot(repository, manifest["workflow_knowledge"])
        domain_snapshot = load_locked_snapshot(repository, manifest["domain_knowledge"])
    except SnapshotError as exc:
        raise ResolutionError(str(exc)) from exc
    workflow_records = [
        record for record in workflow_snapshot
        if record.get("type") == "workflow_playbook"
        and stage in record.get("workflow_stages", [])
        and _applies_to_study(record, study_id)
    ]
    domain_records = [
        record for record in domain_snapshot
        if record.get("type") not in {"workflow_playbook", "source_record", "figure_record"}
        and stage in record.get("workflow_stages", [])
        and _applies_to_study(record, study_id)
    ]
    # Study-specific decisions are supplied only by the Engine in a separate P4
    # merge.  The Wiki service neither owns nor accepts them as an instruction path.
    missing: list[dict[str, Any]] = []
    if request.get("require_workflow", True) and not workflow_records:
        missing.append({"requirement_id": "requirement-workflow-context", "description": "No production-approved workflow playbook matches this stage."})
    if request.get("require_domain", False) and not domain_records:
        missing.append({"requirement_id": "requirement-domain-context", "description": "No production-approved domain knowledge matches this stage."})
    workflow_rules = _workflow_rules(workflow_records)
    domain_rules = _domain_rules(domain_records)
    provenance = [_pipeline_provenance(manifest)]
    provenance.extend(
        _provenance_for(record, "workflow_knowledge", manifest)
        for record in workflow_records
    )
    provenance.extend(
        _provenance_for(record, "domain_knowledge", manifest)
        for record in domain_records
    )
    payload: dict[str, Any] = {
        "bundle_id": f"ctx-{_safe_slug(study_id)}-{stage.replace('_', '-')}",
        "schema_version": bundle.version,
        "study_id": study_id,
        "stage": stage,
        "resolved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": manifest["manifest_sha256"],
        "pipeline_contract": manifest["pipeline_contract"],
        "workflow_rules": workflow_rules,
        "domain_rules": domain_rules,
        "study_rules": [],
        "conflicts": [],
        "missing_requirements": missing,
        "provenance": provenance,
        "executable": not missing,
    }
    payload["execution_context_sha256"] = canonical_json_sha256(payload)
    bundle.validate("knowledge/execution-context.schema.json", payload)
    return payload


def _validate_manifest(bundle: SchemaBundle, manifest: dict[str, Any], study_id: str) -> None:
    bundle.validate("knowledge/runtime-manifest.schema.json", manifest)
    if manifest.get("study_id") != study_id:
        raise ResolutionError("runtime_manifest.study_id must match request study_id")
    if manifest.get("schema_version") != bundle.version:
        raise ResolutionError("runtime manifest schema_version differs from local schema bundle")


def _reject_control_fields(request: dict[str, Any]) -> None:
    forbidden = {"command", "commands", "next_stage", "stage_override", "capabilities", "tool_calls"}
    found = forbidden.intersection(request)
    if found:
        raise ResolutionError(f"Wiki runtime endpoint rejects control fields: {sorted(found)}")


def _workflow_rules(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for record in records:
        statement = record["purpose"] + " " + " ".join(step["objective"] for step in record["steps"])
        rules.append({
            "rule_id": record["id"], "layer": "workflow", "priority": 400,
            "title": record["title"], "statement": statement,
            "source_ids": list(record.get("sources", [])) or [record["id"]],
            "source_version": record["version"], "source_sha256": record["content_hash"],
            "approval_receipt_id": record["approval_receipt_id"],
        })
    return rules


def _domain_rules(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for record in records:
        for statement in record.get("statements", []):
            rules.append({
                "rule_id": statement["rule_id"], "layer": "domain", "priority": 300,
                "title": record["title"], "statement": statement["statement"],
                "source_ids": list(statement["evidence_refs"]), "source_version": record["version"],
                "source_sha256": record["content_hash"],
                "approval_receipt_id": record["approval_receipt_id"],
            })
    return rules


def _pipeline_provenance(manifest: dict[str, Any]) -> dict[str, Any]:
    pipeline = manifest["pipeline_contract"]
    return {
        "provenance_id": "prov-pipeline-contract", "object_id": pipeline["artifact_id"],
        "object_version": pipeline["version"], "object_sha256": pipeline["sha256"],
        "source_kind": "pipeline_contract", "snapshot_id": None,
        "audit_reference": "runtime-manifest",
    }


def _provenance_for(
    record: dict[str, Any], source_kind: str, manifest: dict[str, Any]
) -> dict[str, Any]:
    lock = manifest["workflow_knowledge"] if source_kind == "workflow_knowledge" else manifest["domain_knowledge"]
    return {
        "provenance_id": f"prov-{record['id']}", "object_id": record["id"],
        "object_version": record["version"], "object_sha256": record["content_hash"],
        "source_kind": source_kind, "snapshot_id": lock["snapshot_id"],
        "audit_reference": record["audit_reference"],
    }


def _applies_to_study(record: dict[str, Any], study_id: str) -> bool:
    applicability = record.get("applicability", {})
    conditions = applicability.get("conditions", [])
    unknown = set(conditions) - {_SYNTHETIC_PILOT_CONDITION}
    if unknown:
        raise ResolutionError(
            f"unknown applicability conditions for {record.get('id')}: {sorted(unknown)}"
        )
    study_ids = applicability.get("study_ids", [])
    if study_ids and study_id not in study_ids:
        return False
    if _SYNTHETIC_PILOT_CONDITION in conditions and study_id != _SYNTHETIC_PILOT_STUDY:
        return False
    return True


def _safe_slug(value: str) -> str:
    lowered = "".join(char.lower() if char.isalnum() else "-" for char in value)
    collapsed = "-".join(part for part in lowered.split("-") if part)
    return collapsed or "study"
