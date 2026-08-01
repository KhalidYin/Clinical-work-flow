"""P12 immutable Release adapter for the clinical Workflow runtime contract."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

from service.object_store import ObjectIntegrityError, ObjectStorePort


class PublishedKnowledgeError(RuntimeError):
    """Published knowledge cannot satisfy a locked runtime request."""


def load_release_manifest(
    object_store: ObjectStorePort,
    *,
    object_key: str,
    expected_sha256: str,
) -> dict[str, Any]:
    content = object_store.get_bytes(object_key)
    if sha256(content).hexdigest() != expected_sha256:
        raise ObjectIntegrityError("published release manifest hash mismatch")
    try:
        manifest = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublishedKnowledgeError("published release manifest is not JSON") from exc
    if not isinstance(manifest, dict):
        raise PublishedKnowledgeError("published release manifest must be an object")
    snapshots = manifest.get("runtime_snapshots")
    bundle = manifest.get("schema_bundle")
    if not isinstance(snapshots, list) or not isinstance(bundle, dict):
        raise PublishedKnowledgeError("release lacks runtime snapshots or schema bundle")
    return manifest


def published_version(manifest: Mapping[str, Any]) -> dict[str, str]:
    bundle = _mapping(manifest, "schema_bundle")
    return {
        "bundle_id": _text(bundle, "id"),
        "bundle_version": _text(bundle, "version"),
        "bundle_sha256": _sha(bundle, "sha256"),
    }


def resolve_published_runtime_context(
    release_manifest: Mapping[str, Any], request: Mapping[str, Any]
) -> dict[str, Any]:
    _reject_control_fields(request)
    allowed = {
        "study_id",
        "stage",
        "runtime_manifest",
        "schema_bundle",
        "require_workflow",
        "require_domain",
    }
    unknown = set(request) - allowed
    if unknown:
        raise PublishedKnowledgeError(f"unsupported runtime request fields: {sorted(unknown)}")
    study_id = _text(request, "study_id")
    stage = _text(request, "stage")
    runtime_manifest = _mapping(request, "runtime_manifest")
    if _text(runtime_manifest, "study_id") != study_id:
        raise PublishedKnowledgeError("runtime manifest study differs from request")
    requested_bundle = _mapping(request, "schema_bundle")
    published_bundle = _mapping(release_manifest, "schema_bundle")
    if (
        _text(requested_bundle, "version") != _text(published_bundle, "version")
        or _sha(requested_bundle, "sha256") != _sha(published_bundle, "sha256")
    ):
        raise PublishedKnowledgeError("schema bundle lock differs from published release")

    workflow_lock = _mapping(runtime_manifest, "workflow_knowledge")
    domain_lock = _mapping(runtime_manifest, "domain_knowledge")
    workflow_snapshot = _locked_snapshot(release_manifest, workflow_lock)
    domain_snapshot = _locked_snapshot(release_manifest, domain_lock)
    workflow_records = [
        item
        for item in workflow_snapshot["items"]
        if item.get("type") == "workflow_playbook"
        and stage in item.get("workflow_stages", [])
        and _applies_to_study(item, study_id)
    ]
    domain_records = [
        item
        for item in domain_snapshot["items"]
        if item.get("type") not in {"workflow_playbook", "source_record", "figure_record"}
        and stage in item.get("workflow_stages", [])
        and _applies_to_study(item, study_id)
    ]
    missing: list[dict[str, Any]] = []
    if request.get("require_workflow", True) and not workflow_records:
        missing.append(
            {
                "requirement_id": "requirement-workflow-context",
                "description": "No released workflow playbook matches this stage.",
                "blocking": True,
            }
        )
    if request.get("require_domain", False) and not domain_records:
        missing.append(
            {
                "requirement_id": "requirement-domain-context",
                "description": "No released domain knowledge matches this stage.",
                "blocking": True,
            }
        )
    provenance = [_pipeline_provenance(runtime_manifest)]
    provenance.extend(
        _knowledge_provenance(item, "workflow_knowledge", workflow_lock)
        for item in workflow_records
    )
    provenance.extend(
        _knowledge_provenance(item, "domain_knowledge", domain_lock)
        for item in domain_records
    )
    payload: dict[str, Any] = {
        "bundle_id": f"ctx-{_slug(study_id)}-{stage.replace('_', '-')}",
        "schema_version": _text(published_bundle, "version"),
        "study_id": study_id,
        "stage": stage,
        "resolved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "manifest_id": _text(runtime_manifest, "manifest_id"),
        "manifest_sha256": _sha(runtime_manifest, "manifest_sha256"),
        "pipeline_contract": dict(_mapping(runtime_manifest, "pipeline_contract")),
        "workflow_rules": _workflow_rules(workflow_records),
        "domain_rules": _domain_rules(domain_records),
        "study_rules": [],
        "conflicts": [],
        "missing_requirements": missing,
        "provenance": provenance,
        "executable": not missing,
    }
    payload["execution_context_sha256"] = _canonical_hash(payload)
    return payload


def _locked_snapshot(
    release_manifest: Mapping[str, Any], lock: Mapping[str, Any]
) -> Mapping[str, Any]:
    snapshot_id = _text(lock, "snapshot_id")
    matches = [
        item
        for item in release_manifest.get("runtime_snapshots", [])
        if isinstance(item, Mapping) and item.get("snapshot_id") == snapshot_id
    ]
    if len(matches) != 1:
        raise PublishedKnowledgeError(f"published snapshot is not unique: {snapshot_id}")
    snapshot = matches[0]
    if _text(snapshot, "version") != _text(lock, "version") or _sha(
        snapshot, "sha256"
    ) != _sha(lock, "sha256"):
        raise PublishedKnowledgeError(f"published snapshot lock mismatch: {snapshot_id}")
    items = snapshot.get("items")
    bundle = snapshot.get("schema_bundle")
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise PublishedKnowledgeError(f"published snapshot items are invalid: {snapshot_id}")
    if not isinstance(bundle, dict):
        raise PublishedKnowledgeError(f"published snapshot bundle is invalid: {snapshot_id}")
    expected = _canonical_hash({"schema_bundle": bundle, "items": items})
    if expected != _sha(snapshot, "sha256"):
        raise PublishedKnowledgeError(f"published snapshot content hash mismatch: {snapshot_id}")
    return snapshot


def _workflow_rules(records: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "rule_id": item["id"],
            "layer": "workflow",
            "priority": 400,
            "title": item["title"],
            "statement": item["purpose"]
            + " "
            + " ".join(step["objective"] for step in item["steps"]),
            "source_ids": list(item.get("sources", [])) or [item["id"]],
            "source_version": item["version"],
            "source_sha256": item["content_hash"],
            "approval_receipt_id": item["approval_receipt_id"],
        }
        for item in records
    ]


def _domain_rules(records: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for item in records:
        for statement in item.get("statements", []):
            rules.append(
                {
                    "rule_id": statement["rule_id"],
                    "layer": "domain",
                    "priority": 300,
                    "title": item["title"],
                    "statement": statement["statement"],
                    "source_ids": list(statement["evidence_refs"]),
                    "source_version": item["version"],
                    "source_sha256": item["content_hash"],
                    "approval_receipt_id": item["approval_receipt_id"],
                }
            )
    return rules


def _pipeline_provenance(manifest: Mapping[str, Any]) -> dict[str, Any]:
    pipeline = _mapping(manifest, "pipeline_contract")
    return {
        "provenance_id": "prov-pipeline-contract",
        "object_id": pipeline["artifact_id"],
        "object_version": pipeline["version"],
        "object_sha256": pipeline["sha256"],
        "source_kind": "pipeline_contract",
        "snapshot_id": None,
        "audit_reference": "runtime-manifest",
    }


def _knowledge_provenance(
    item: Mapping[str, Any], source_kind: str, lock: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "provenance_id": f"prov-{item['id']}",
        "object_id": item["id"],
        "object_version": item["version"],
        "object_sha256": item["content_hash"],
        "source_kind": source_kind,
        "snapshot_id": lock["snapshot_id"],
        "audit_reference": item.get("audit_reference") or "p13-migration-report",
    }


def _applies_to_study(item: Mapping[str, Any], study_id: str) -> bool:
    applicability = item.get("applicability", {})
    if not isinstance(applicability, Mapping):
        raise PublishedKnowledgeError(f"invalid applicability: {item.get('id')}")
    study_ids = applicability.get("study_ids", [])
    if study_ids and study_id not in study_ids:
        return False
    conditions = applicability.get("conditions", [])
    if "synthetic-pilot-only" in conditions and study_id != "SYNTH-ONCO-001":
        return False
    return True


def _reject_control_fields(value: Any, path: tuple[str, ...] = ()) -> None:
    forbidden = {
        "command",
        "commands",
        "next_stage",
        "skip_stage",
        "stage_override",
        "capabilities",
        "tool_calls",
    }
    if isinstance(value, Mapping):
        for key, item in value.items():
            # Engine-owned RuntimeManifest.toolchain.capabilities is a locked
            # evidence field, not a request to grant capabilities.  Every other
            # occurrence of an execution-control name remains forbidden.
            if key in forbidden and not (
                key == "capabilities" and path == ("runtime_manifest", "toolchain")
            ):
                raise PublishedKnowledgeError(
                    "runtime request contains execution-control fields"
                )
            _reject_control_fields(item, (*path, str(key)))
    elif isinstance(value, list):
        for item in value:
            _reject_control_fields(item, path)


def _mapping(value: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    item = value.get(key)
    if not isinstance(item, Mapping):
        raise PublishedKnowledgeError(f"{key} must be an object")
    return item


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise PublishedKnowledgeError(f"{key} is required")
    return item


def _sha(value: Mapping[str, Any], key: str) -> str:
    item = _text(value, key)
    if len(item) != 64 or any(char not in "0123456789abcdef" for char in item):
        raise PublishedKnowledgeError(f"{key} must be a lowercase SHA-256")
    return item


def _canonical_hash(value: Any) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _slug(value: str) -> str:
    return "-".join(
        part
        for part in "".join(char.lower() if char.isalnum() else "-" for char in value).split("-")
        if part
    ) or "study"
