from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from review_panel.config import ReviewPanelConfig, ReviewPanelConfigError, ensure_path_within
from review_panel.contracts import QueueKind, QueueRegistration


class QueueRegistryError(ValueError):
    """Raised when trusted review queue discovery fails closed."""


class UnknownQueueError(QueueRegistryError):
    """Raised when a caller asks for a queue ID outside the server allowlist."""


@dataclass(frozen=True)
class QueueCandidate:
    queue_id: str
    queue_kind: QueueKind
    owner_label: str
    owner_root: Path
    queue_path: Path
    expected_protocol_scope: str | None


@dataclass(frozen=True)
class QueueRegistry:
    config: ReviewPanelConfig

    def discover(self) -> list[QueueRegistration]:
        discovered: list[QueueRegistration] = []
        for candidate in self._candidate_queues():
            if not candidate.queue_path.exists():
                continue
            discovered.append(self._register_existing_queue(candidate))

        seen: set[str] = set()
        for registration in discovered:
            if registration.queue_id in seen:
                raise QueueRegistryError(f"Duplicate queue_id discovered: {registration.queue_id}")
            seen.add(registration.queue_id)
        return sorted(discovered, key=lambda item: (item.queue_kind.value, item.queue_id))

    def require_queue(self, queue_id: str) -> QueueRegistration:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,80}", queue_id):
            raise UnknownQueueError(f"Invalid queue_id: {queue_id}")
        queues = {queue.queue_id: queue for queue in self.discover()}
        try:
            return queues[queue_id]
        except KeyError as exc:
            raise UnknownQueueError(f"Unknown queue_id: {queue_id}") from exc

    def _candidate_queues(self) -> Iterable[QueueCandidate]:
        root = self.config.repo_root
        yield QueueCandidate(
            queue_id="platform",
            queue_kind=QueueKind.PLATFORM,
            owner_label="Platform",
            owner_root=root,
            queue_path=root / ".review_queue",
            expected_protocol_scope="platform",
        )
        wiki_root = root / "clinical-llm-wiki"
        yield QueueCandidate(
            queue_id="wiki",
            queue_kind=QueueKind.WIKI,
            owner_label="Clinical LLM Wiki",
            owner_root=wiki_root,
            queue_path=wiki_root / ".review_queue",
            expected_protocol_scope="wiki",
        )

        studies_root = root / "clinical-studies"
        if not studies_root.is_dir():
            return
        for study_root in sorted(path for path in studies_root.iterdir() if path.is_dir()):
            queue_id = f"study-{_slugify(study_root.name)}"
            yield QueueCandidate(
                queue_id=queue_id,
                queue_kind=QueueKind.STUDY,
                owner_label=study_root.name,
                owner_root=study_root,
                queue_path=study_root / ".review_queue",
                expected_protocol_scope="study",
            )

    def _register_existing_queue(self, candidate: QueueCandidate) -> QueueRegistration:
        try:
            owner_root = candidate.owner_root.resolve(strict=True)
            queue_path = ensure_path_within(candidate.queue_path, owner_root)
        except ReviewPanelConfigError as exc:
            raise QueueRegistryError(str(exc)) from exc
        if not queue_path.is_dir():
            raise QueueRegistryError(f"Review queue path is not a directory: {candidate.queue_path}")

        marker_path = queue_path / ".queue_scope.json"
        protocol_scope = None
        resolved_marker = None
        if marker_path.exists():
            resolved_marker = ensure_path_within(marker_path, queue_path)
            protocol_scope = _read_protocol_scope(
                resolved_marker,
                owner_root=owner_root,
                expected_scope=candidate.expected_protocol_scope,
            )

        return QueueRegistration(
            queue_id=candidate.queue_id,
            queue_kind=candidate.queue_kind,
            owner_label=candidate.owner_label,
            owner_root=owner_root,
            queue_path=queue_path,
            protocol_scope=protocol_scope,
            marker_path=resolved_marker,
        )


def _read_protocol_scope(marker_path: Path, *, owner_root: Path, expected_scope: str | None) -> str:
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise QueueRegistryError(f"Invalid queue scope marker: {marker_path}") from exc
    if not isinstance(marker, dict):
        raise QueueRegistryError(f"Queue scope marker must be a JSON object: {marker_path}")

    scope = marker.get("scope")
    if scope != expected_scope:
        raise QueueRegistryError(
            f"Queue scope marker mismatch for {marker_path}: expected {expected_scope}, got {scope}"
        )
    marker_owner = marker.get("owner_root")
    if marker_owner is not None and Path(marker_owner).resolve() != owner_root:
        raise QueueRegistryError(
            f"Queue scope marker owner_root mismatch for {marker_path}: {marker_owner}"
        )
    return str(scope)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "study"

