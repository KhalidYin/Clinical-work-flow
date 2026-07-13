"""Immutable, hash-addressed Wiki snapshots for Study fallback locks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import canonical_json_sha256
from .repository import VaultRepository


class SnapshotError(ValueError):
    """Snapshot creation cannot prove an immutable, governed result."""


def create_snapshot(repository: VaultRepository, payload: dict[str, Any]) -> dict[str, Any]:
    requested_ids = payload.get("item_ids")
    if requested_ids is None:
        cards = [card for card in repository.cards.values() if card.production_eligible]
    elif isinstance(requested_ids, list) and all(isinstance(item, str) for item in requested_ids):
        cards = []
        for item_id in requested_ids:
            card = repository.get(item_id)
            if card is None:
                raise SnapshotError(f"snapshot item not found: {item_id}")
            if not card.production_eligible:
                raise SnapshotError(f"snapshot item is not production eligible: {item_id}")
            cards.append(card)
    else:
        raise SnapshotError("item_ids must be an array of governed IDs")
    content = {
        "schema_bundle": {"version": repository.bundle.version, "sha256": repository.bundle.sha256},
        "items": [card.record for card in sorted(cards, key=lambda value: value.record["id"])],
    }
    content_hash = canonical_json_sha256(content)
    snapshot_id = payload.get("snapshot_id") or f"snapshot-{content_hash[:16]}"
    if not isinstance(snapshot_id, str) or not snapshot_id.startswith("snapshot-"):
        raise SnapshotError("snapshot_id must start with 'snapshot-'")
    response = {
        "snapshot_id": snapshot_id,
        "version": payload.get("version", "1.0.0"),
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sha256": content_hash,
        **content,
    }
    snapshots = repository.root / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    path = snapshots / f"{snapshot_id}.json"
    serialized = json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        # Same name does not imply a mutable rewrite. Exact content is idempotent;
        # every other attempt signals a locked-snapshot conflict.
        if path.read_text(encoding="utf-8") != serialized:
            raise SnapshotError(f"snapshot is immutable and already exists: {snapshot_id}")
        return response
    path.write_text(serialized, encoding="utf-8")
    return response


def load_locked_snapshot(
    repository: VaultRepository, lock: dict[str, Any]
) -> list[dict[str, Any]]:
    """Load one manifest-selected snapshot and prove every immutable lock.

    Runtime resolution must never widen a Study lock by searching the live
    Vault.  This loader therefore returns records from the snapshot document,
    after proving its identity, version, schema bundle, and canonical content
    hash against the manifest.
    """

    snapshot_id = lock.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id.startswith("snapshot-"):
        raise SnapshotError("snapshot lock requires a valid snapshot_id")
    path = _snapshot_path(repository.root, snapshot_id)
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SnapshotError(f"locked snapshot not found: {snapshot_id}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"cannot read locked snapshot {snapshot_id}: {exc}") from exc
    if not isinstance(snapshot, dict):
        raise SnapshotError(f"locked snapshot must be an object: {snapshot_id}")
    if snapshot.get("snapshot_id") != snapshot_id:
        raise SnapshotError(f"locked snapshot_id mismatch: {snapshot_id}")
    if snapshot.get("version") != lock.get("version"):
        raise SnapshotError(f"locked snapshot version mismatch: {snapshot_id}")

    schema_bundle = snapshot.get("schema_bundle")
    if not isinstance(schema_bundle, dict):
        raise SnapshotError(f"locked snapshot schema_bundle is invalid: {snapshot_id}")
    try:
        repository.bundle.assert_requested(schema_bundle)
    except ValueError as exc:
        raise SnapshotError(f"locked snapshot schema_bundle mismatch: {snapshot_id}") from exc

    items = snapshot.get("items")
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise SnapshotError(f"locked snapshot items must be objects: {snapshot_id}")
    content_hash = canonical_json_sha256({"schema_bundle": schema_bundle, "items": items})
    if snapshot.get("sha256") != content_hash:
        raise SnapshotError(f"locked snapshot canonical content hash mismatch: {snapshot_id}")
    if lock.get("sha256") != content_hash:
        raise SnapshotError(f"manifest snapshot sha256 mismatch: {snapshot_id}")

    record_ids: set[str] = set()
    records: list[dict[str, Any]] = []
    for item in items:
        record_id = item.get("id")
        if not isinstance(record_id, str) or not record_id:
            raise SnapshotError(f"locked snapshot item has no governed id: {snapshot_id}")
        if record_id in record_ids:
            raise SnapshotError(f"locked snapshot contains duplicate item: {record_id}")
        _validate_snapshot_item(repository, item)
        record_ids.add(record_id)
        records.append(item)
    return records


def _snapshot_path(root: Path, snapshot_id: str) -> Path:
    snapshots = (root / "snapshots").resolve()
    path = (snapshots / f"{snapshot_id}.json").resolve()
    if path.parent != snapshots:
        raise SnapshotError("snapshot path must stay within the Wiki snapshot directory")
    return path


def _validate_snapshot_item(repository: VaultRepository, record: dict[str, Any]) -> None:
    schema = {
        "workflow_playbook": "knowledge/workflow-playbook.schema.json",
        "source_record": "knowledge/source.schema.json",
        "figure_record": "knowledge/figure.schema.json",
    }.get(str(record.get("type")), "knowledge/knowledge-item.schema.json")
    try:
        repository.bundle.validate(schema, record)
    except ValueError as exc:
        raise SnapshotError(f"locked snapshot item fails schema: {record.get('id')}") from exc
