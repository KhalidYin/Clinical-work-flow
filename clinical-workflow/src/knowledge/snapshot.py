"""Immutable Study snapshot validation and offline context construction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .compatibility import sha256_canonical_json
from .models import (
    ExecutionContext,
    KnowledgeItem,
    KnowledgeSnapshotLock,
    ProvenanceEntry,
    ResolvedRule,
    RuleLayer,
    RuntimeManifest,
    WorkflowPlaybook,
)


class SnapshotError(ValueError):
    """A fallback snapshot cannot prove the manifest lock it claims to satisfy."""


@dataclass(frozen=True, slots=True)
class LockedSnapshot:
    snapshot_id: str
    version: str
    sha256: str
    schema_version: str
    schema_sha256: str
    items: tuple[Mapping[str, Any], ...]


def load_locked_snapshot(
    project_dir: Path,
    lock: KnowledgeSnapshotLock,
    *,
    expected_bundle_version: str,
    expected_bundle_sha256: str,
) -> LockedSnapshot:
    """Load one manifest-locked snapshot without allowing path escape or mutation."""
    path = _contained_path(project_dir, lock.fallback_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"locked snapshot cannot be read: {lock.snapshot_id}") from exc
    if not isinstance(raw, dict):
        raise SnapshotError("locked snapshot must be a JSON object")
    try:
        snapshot_id = _text(raw, "snapshot_id")
        version = _text(raw, "version")
        snapshot_sha = _text(raw, "sha256")
        bundle = raw["schema_bundle"]
        items = raw["items"]
    except (KeyError, TypeError, ValueError) as exc:
        raise SnapshotError("locked snapshot has an invalid envelope") from exc
    if not isinstance(bundle, dict) or not isinstance(items, list) or not all(
        isinstance(item, dict) for item in items
    ):
        raise SnapshotError("locked snapshot has an invalid schema bundle or item list")
    if (
        snapshot_id != lock.snapshot_id
        or version != lock.version
        or snapshot_sha != lock.sha256
        or bundle.get("version") != expected_bundle_version
        or bundle.get("sha256") != expected_bundle_sha256
    ):
        raise SnapshotError("locked snapshot identity/version/hash does not match runtime manifest")
    expected_hash = sha256_canonical_json({"schema_bundle": bundle, "items": items})
    if expected_hash != snapshot_sha:
        raise SnapshotError("locked snapshot content hash mismatch")
    return LockedSnapshot(
        snapshot_id=snapshot_id,
        version=version,
        sha256=snapshot_sha,
        schema_version=str(bundle["version"]),
        schema_sha256=str(bundle["sha256"]),
        items=tuple(items),
    )


def context_from_snapshots(
    *,
    manifest: RuntimeManifest,
    stage: str,
    workflow_snapshot: LockedSnapshot,
    domain_snapshot: LockedSnapshot,
    study_rules: Iterable[ResolvedRule] = (),
) -> ExecutionContext:
    """Build the same non-executable data shape as online resolution from locks."""
    workflow_rules: list[ResolvedRule] = []
    domain_rules: list[ResolvedRule] = []
    provenance = [_pipeline_provenance(manifest)]
    for item in workflow_snapshot.items:
        if item.get("type") != "workflow_playbook" or item.get("stage") != stage:
            continue
        playbook = WorkflowPlaybook.model_validate(item)
        workflow_rules.append(
            ResolvedRule(
                rule_id=playbook.id,
                layer=RuleLayer.WORKFLOW,
                priority=400,
                title=playbook.title,
                statement=playbook.purpose + " " + " ".join(step.objective for step in playbook.steps),
                source_ids=playbook.sources or (playbook.id,),
                source_version=playbook.version,
                source_sha256=playbook.content_hash,
                approval_receipt_id=playbook.approval_receipt_id or "receipt-missing",
            )
        )
        provenance.append(_knowledge_provenance(playbook, "workflow_knowledge", workflow_snapshot))
    for item in domain_snapshot.items:
        if item.get("type") in {"workflow_playbook", "source_record", "figure_record"}:
            continue
        knowledge = KnowledgeItem.model_validate(item)
        if stage not in knowledge.workflow_stages:
            continue
        for statement in knowledge.statements:
            domain_rules.append(
                ResolvedRule(
                    rule_id=statement.rule_id,
                    layer=RuleLayer.DOMAIN,
                    priority=300,
                    title=knowledge.title,
                    statement=statement.statement,
                    source_ids=statement.evidence_refs,
                    source_version=knowledge.version,
                    source_sha256=knowledge.content_hash,
                    approval_receipt_id=knowledge.approval_receipt_id or "receipt-missing",
                )
            )
        provenance.append(_knowledge_provenance(knowledge, "domain_knowledge", domain_snapshot))
    combined_study_rules = tuple(study_rules)
    payload: dict[str, Any] = {
        "bundle_id": f"ctx-{manifest.study_id.lower()}-{stage.replace('_', '-')}",
        "schema_version": manifest.schema_version,
        "study_id": manifest.study_id,
        "stage": stage,
        "resolved_at": datetime.now(timezone.utc),
        "manifest_id": manifest.manifest_id,
        "manifest_sha256": manifest.manifest_sha256,
        "pipeline_contract": manifest.pipeline_contract,
        "workflow_rules": tuple(workflow_rules),
        "domain_rules": tuple(domain_rules),
        "study_rules": combined_study_rules,
        "conflicts": (),
        "missing_requirements": (),
        "provenance": tuple(provenance),
        "executable": True,
    }
    payload["execution_context_sha256"] = sha256_canonical_json(_jsonable(payload))
    return ExecutionContext.model_validate(payload)


def _contained_path(root: Path, value: str) -> Path:
    candidate = (root / value).resolve()
    resolved_root = root.resolve()
    if resolved_root not in (candidate, *candidate.parents):
        raise SnapshotError("locked snapshot path must stay inside the Study directory")
    return candidate


def _text(value: Mapping[str, Any], key: str) -> str:
    item = value[key]
    if not isinstance(item, str) or not item:
        raise ValueError(key)
    return item


def _pipeline_provenance(manifest: RuntimeManifest) -> ProvenanceEntry:
    pipeline = manifest.pipeline_contract
    return ProvenanceEntry(
        provenance_id="prov-pipeline-contract",
        object_id=pipeline.artifact_id,
        object_version=pipeline.version,
        object_sha256=pipeline.sha256,
        source_kind="pipeline_contract",
        snapshot_id=None,
        audit_reference="runtime-manifest",
    )


def _knowledge_provenance(
    item: WorkflowPlaybook | KnowledgeItem, source_kind: str, snapshot: LockedSnapshot
) -> ProvenanceEntry:
    return ProvenanceEntry(
        provenance_id=f"prov-{item.id}",
        object_id=item.id,
        object_version=item.version,
        object_sha256=item.content_hash,
        source_kind=source_kind,
        snapshot_id=snapshot.snapshot_id,
        audit_reference=item.audit_reference or "snapshot",
    )


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return value
