"""Authoritative Release workbench projection for the governance UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, Sequence

from service.auth import ActorContext, Permission, PrincipalType, ProductRole

from .contracts import ReleaseManifestPayload


ReleaseGateCode = Literal[
    "candidate_integrity",
    "base_release_current",
    "evaluation_passed",
    "publication_snapshot",
]
ReleaseAllowedAction = Literal["publish"]


@dataclass(frozen=True, slots=True)
class ReleaseSummaryRecord:
    release_id: str
    version: str
    status: str
    base_release_id: str | None
    item_count: int
    is_current: bool
    created_at: datetime
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class ReleaseGateFact:
    code: ReleaseGateCode
    passed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class ReleaseWorkbenchSnapshot:
    current: ReleaseSummaryRecord | None
    candidate: ReleaseSummaryRecord | None
    history: Sequence[ReleaseSummaryRecord]
    candidate_manifest: ReleaseManifestPayload | None
    base_manifest: ReleaseManifestPayload | None
    gates: Sequence[ReleaseGateFact]


@dataclass(frozen=True, slots=True)
class ReleaseDiffRecord:
    included_count: int
    carried_count: int
    replaced_count: int
    added_count: int
    retired_count: int
    included_revision_ids: tuple[str, ...]
    carried_revision_ids: tuple[str, ...]
    replaced_revision_ids: tuple[str, ...]
    added_revision_ids: tuple[str, ...]
    retired_revision_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReleaseWorkbenchRecord:
    current: ReleaseSummaryRecord | None
    candidate: ReleaseSummaryRecord | None
    history: tuple[ReleaseSummaryRecord, ...]
    diff: ReleaseDiffRecord | None
    gates: tuple[ReleaseGateFact, ...]
    blockers: tuple[str, ...]
    allowed_actions: tuple[ReleaseAllowedAction, ...]


class ReleaseWorkbenchRepository(Protocol):
    def load_workbench(
        self,
        *,
        candidate_id: str | None,
    ) -> ReleaseWorkbenchSnapshot: ...


class ReleaseWorkbenchService:
    def __init__(self, *, repository: ReleaseWorkbenchRepository) -> None:
        self._repository = repository

    def get(
        self,
        *,
        actor: ActorContext,
        candidate_id: str | None,
    ) -> ReleaseWorkbenchRecord:
        snapshot = self._repository.load_workbench(candidate_id=candidate_id)
        gates = tuple(snapshot.gates)
        blockers = tuple(gate.reason for gate in gates if not gate.passed)
        diff = (
            None
            if (
                snapshot.candidate is not None
                and snapshot.candidate.base_release_id is not None
                and snapshot.base_manifest is None
            )
            else _release_diff(snapshot.candidate_manifest, snapshot.base_manifest)
        )
        publishable = (
            snapshot.candidate is not None
            and bool(gates)
            and not blockers
            and actor.principal_type is PrincipalType.HUMAN
            and ProductRole.RELEASE_MANAGER in actor.roles
            and Permission.RELEASE_PUBLISH in actor.permissions
        )
        return ReleaseWorkbenchRecord(
            current=snapshot.current,
            candidate=snapshot.candidate,
            history=tuple(snapshot.history),
            diff=diff,
            gates=gates,
            blockers=blockers,
            allowed_actions=("publish",) if publishable else (),
        )


def _release_diff(
    candidate: ReleaseManifestPayload | None,
    base: ReleaseManifestPayload | None,
) -> ReleaseDiffRecord | None:
    if candidate is None:
        return None
    candidate_items = {item.knowledge_revision_id: item for item in candidate.items}
    base_ids = (
        frozenset(item.knowledge_revision_id for item in base.items)
        if base is not None
        else frozenset()
    )
    candidate_ids = frozenset(candidate_items)
    included = tuple(sorted(candidate_ids))
    carried = tuple(
        sorted(
            revision_id
            for revision_id, item in candidate_items.items()
            if item.disposition in {"carry_forward", "no_action"}
        )
    )
    replaced = tuple(
        sorted(
            revision_id
            for revision_id, item in candidate_items.items()
            if item.disposition == "replace"
        )
    )
    added = tuple(
        sorted(
            revision_id
            for revision_id, item in candidate_items.items()
            if item.disposition == "add"
        )
    )
    retired = tuple(sorted(base_ids - candidate_ids))
    return ReleaseDiffRecord(
        included_count=len(included),
        carried_count=len(carried),
        replaced_count=len(replaced),
        added_count=len(added),
        retired_count=len(retired),
        included_revision_ids=included,
        carried_revision_ids=carried,
        replaced_revision_ids=replaced,
        added_revision_ids=added,
        retired_revision_ids=retired,
    )


__all__ = [
    "ReleaseAllowedAction",
    "ReleaseDiffRecord",
    "ReleaseGateCode",
    "ReleaseGateFact",
    "ReleaseSummaryRecord",
    "ReleaseWorkbenchRecord",
    "ReleaseWorkbenchRepository",
    "ReleaseWorkbenchService",
    "ReleaseWorkbenchSnapshot",
]
