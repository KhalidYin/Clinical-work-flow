"""Immutable, hash-addressed Wiki snapshots for Study fallback locks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
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
