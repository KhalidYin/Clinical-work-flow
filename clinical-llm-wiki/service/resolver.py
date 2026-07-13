"""Structured runtime-context resolution with no executable instruction channel."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .contracts import SchemaBundle, canonical_json_sha256
from .repository import Card, VaultRepository


_STAGES = frozenset({
    "protocol_analysis", "sap_generation", "sdtm_spec", "sdtm_programming",
    "adam_spec", "adam_programming", "tfl_shell_design", "tfl_programming",
    "qc_validation", "submission_packaging",
})


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
    workflow_cards = repository.search(
        record_type="workflow_playbook", stage=stage, production_only=True, limit=200
    )
    domain_cards = [
        card for card in repository.search(stage=stage, production_only=True, limit=500)
        if card.record.get("type") not in {"workflow_playbook", "source_record", "figure_record"}
    ]
    # Study-specific decisions are supplied only by the Engine in a separate P4
    # merge.  The Wiki service neither owns nor accepts them as an instruction path.
    missing: list[dict[str, Any]] = []
    if request.get("require_workflow", True) and not workflow_cards:
        missing.append({"requirement_id": "requirement-workflow-context", "description": "No production-approved workflow playbook matches this stage."})
    if request.get("require_domain", False) and not domain_cards:
        missing.append({"requirement_id": "requirement-domain-context", "description": "No production-approved domain knowledge matches this stage."})
    workflow_rules = _workflow_rules(workflow_cards)
    domain_rules = _domain_rules(domain_cards)
    provenance = [_pipeline_provenance(manifest)]
    provenance.extend(_provenance_for(card, "workflow_knowledge", manifest) for card in workflow_cards)
    provenance.extend(_provenance_for(card, "domain_knowledge", manifest) for card in domain_cards)
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


def _workflow_rules(cards: list[Card]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for card in cards:
        record = card.record
        statement = record["purpose"] + " " + " ".join(step["objective"] for step in record["steps"])
        rules.append({
            "rule_id": record["id"], "layer": "workflow", "priority": 400,
            "title": record["title"], "statement": statement,
            "source_ids": list(record.get("sources", [])) or [record["id"]],
            "source_version": record["version"], "source_sha256": record["content_hash"],
            "approval_receipt_id": record["approval_receipt_id"],
        })
    return rules


def _domain_rules(cards: list[Card]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for card in cards:
        record = card.record
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


def _provenance_for(card: Card, source_kind: str, manifest: dict[str, Any]) -> dict[str, Any]:
    lock = manifest["workflow_knowledge"] if source_kind == "workflow_knowledge" else manifest["domain_knowledge"]
    record = card.record
    return {
        "provenance_id": f"prov-{record['id']}", "object_id": record["id"],
        "object_version": record["version"], "object_sha256": record["content_hash"],
        "source_kind": source_kind, "snapshot_id": lock["snapshot_id"],
        "audit_reference": record["audit_reference"],
    }


def _safe_slug(value: str) -> str:
    lowered = "".join(char.lower() if char.isalnum() else "-" for char in value)
    collapsed = "-".join(part for part in lowered.split("-") if part)
    return collapsed or "study"
