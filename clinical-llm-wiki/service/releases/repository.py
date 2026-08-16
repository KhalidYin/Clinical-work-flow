"""PostgreSQL authority for P17 candidate build and atomic Release publication."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from service.db.models import (
    AuditEvent,
    CandidateEvidence,
    ChunkProfile,
    EvaluationRun,
    Evidence,
    IndexManifest,
    KnowledgeRevision,
    Release,
    ReleaseItem,
    ReleasePointer,
    RetrievalChunk,
    RetrievalChunkEvidence,
    RotationCase,
    RotationDecisionReceipt,
)
from service.evaluation import ReleaseEvaluationRun, require_passed_evaluation
from service.object_store import ObjectDescriptor, ObjectIntegrityError, ObjectStorePort

from .contracts import (
    PreparedRelease,
    PublishedReleaseRecord,
    ReleaseBuildCommand,
    ReleaseBuildSnapshot,
    ReleaseItemSnapshot,
    ReleaseManifestItem,
    ReleaseManifestPayload,
    ReleasePublishCommand,
    IndexManifestPayload,
)


class ReleaseStateError(RuntimeError):
    """Canonical lifecycle state cannot satisfy a Release operation."""


class ReleaseMembershipError(ReleaseStateError):
    """The requested Release membership is incomplete or ineligible."""


class SqlAlchemyReleaseRepository:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        object_store: ObjectStorePort,
    ) -> None:
        self._sessions = session_factory
        self._objects = object_store

    def resolve_build(self, command: ReleaseBuildCommand) -> ReleaseBuildSnapshot:
        with self._sessions() as session:
            return _resolve_snapshot(session, command)

    def record_candidate(
        self,
        *,
        command: ReleaseBuildCommand,
        prepared: PreparedRelease,
        actor_id: str,
    ) -> PreparedRelease:
        with self._sessions.begin() as session:
            pointer = _locked_pointer(session)
            if pointer.current_release_id != command.base_release_id:
                raise ReleaseStateError("current Release changed during candidate build")
            existing = session.get(Release, command.release_candidate_id)
            if existing is not None:
                _require_candidate_replay(session, existing, prepared)
                return prepared

            session.add(
                Release(
                    release_id=prepared.release_id,
                    version=prepared.version,
                    status="candidate",
                    previous_release_id=prepared.base_release_id,
                    manifest_object_key=prepared.manifest_descriptor.object_key,
                    manifest_sha256=prepared.manifest_descriptor.sha256,
                    db_schema_revision=command.db_schema_revision,
                    knowledge_contract_version=command.knowledge_contract_version,
                    parser_profile_version=command.parser_profile_version,
                    model_profile_version=command.model_profile_version,
                    prompt_profile_version=command.prompt_profile_version,
                    index_manifest_version=prepared.index_manifest.version,
                    release_manager_subject=None,
                )
            )
            session.flush()
            session.add(
                IndexManifest(
                    index_manifest_id=_index_manifest_id(prepared.release_id),
                    release_id=prepared.release_id,
                    version=prepared.index_manifest.version,
                    status="candidate",
                    capabilities=prepared.index_manifest.model_dump(mode="json"),
                    object_key=prepared.index_descriptor.object_key,
                    sha256=prepared.index_descriptor.sha256,
                )
            )
            for item in prepared.manifest.items:
                session.add(
                    ReleaseItem(
                        release_id=prepared.release_id,
                        knowledge_revision_id=item.knowledge_revision_id,
                        content_sha256=item.content_sha256,
                    )
                )
            session.add(
                AuditEvent(
                    audit_event_id=_audit_id("release.candidate_built", prepared.release_id),
                    actor_subject=actor_id,
                    action="release.candidate_built",
                    entity_type="release",
                    entity_id=prepared.release_id,
                    run_id=None,
                    details={
                        "base_release_id": prepared.base_release_id,
                        "evaluation_run_id": prepared.evaluation_run_id,
                        "item_count": len(prepared.manifest.items),
                        "result": "candidate",
                    },
                )
            )
            session.flush()
        return prepared

    def get_candidate(self, release_id: str) -> PreparedRelease | None:
        return self._get_prepared(release_id=release_id, required_status="candidate")

    def get_released(self, release_id: str | None = None) -> PreparedRelease | None:
        with self._sessions() as session:
            resolved_id = release_id
            if resolved_id is None:
                pointer = session.get(ReleasePointer, "current")
                resolved_id = pointer.current_release_id if pointer is not None else None
        if resolved_id is None:
            return None
        return self._get_prepared(release_id=resolved_id, required_status="released")

    def _get_prepared(
        self,
        *,
        release_id: str,
        required_status: str,
    ) -> PreparedRelease | None:
        with self._sessions() as session:
            release = session.get(Release, release_id)
            if release is None or release.status != required_status:
                return None
            index = session.scalar(
                select(IndexManifest).where(IndexManifest.release_id == release_id)
            )
            if index is None or index.status != required_status:
                raise ReleaseStateError("Release IndexManifest is unavailable")
            item_facts = tuple(
                session.execute(
                    select(
                        ReleaseItem.knowledge_revision_id,
                        ReleaseItem.content_sha256,
                    )
                    .where(ReleaseItem.release_id == release_id)
                    .order_by(ReleaseItem.knowledge_revision_id)
                )
            )
            manifest_descriptor = ObjectDescriptor(
                object_key=release.manifest_object_key,
                sha256=release.manifest_sha256,
                media_type="application/json",
                size_bytes=self._objects.head(release.manifest_object_key).size_bytes,
            )
            index_descriptor = ObjectDescriptor(
                object_key=index.object_key,
                sha256=index.sha256,
                media_type="application/json",
                size_bytes=self._objects.head(index.object_key).size_bytes,
            )
        try:
            manifest = ReleaseManifestPayload.model_validate_json(
                self._objects.get_bytes(manifest_descriptor.object_key)
            )
            index_manifest = IndexManifestPayload.model_validate_json(
                self._objects.get_bytes(index_descriptor.object_key)
            )
        except (ValidationError, ValueError) as exc:
            raise ObjectIntegrityError("Release candidate object payload is invalid") from exc
        if manifest.index_descriptor != index_descriptor:
            raise ObjectIntegrityError("Release manifest index descriptor mismatch")
        if manifest.release_id != release_id or index_manifest.release_id != release_id:
            raise ObjectIntegrityError("Release candidate object identity mismatch")
        manifest_item_facts = tuple(
            sorted(
                (item.knowledge_revision_id, item.content_sha256)
                for item in manifest.items
            )
        )
        if item_facts != manifest_item_facts:
            raise ObjectIntegrityError("Release manifest membership differs from PostgreSQL")
        return PreparedRelease(
            release_id=release_id,
            version=release.version,
            base_release_id=release.previous_release_id,
            evaluation_run_id=manifest.evaluation_run_id,
            index_manifest=index_manifest,
            index_descriptor=index_descriptor,
            manifest=manifest,
            manifest_descriptor=manifest_descriptor,
        )

    def publish_candidate(
        self,
        *,
        command: ReleasePublishCommand,
        actor_id: str,
    ) -> PublishedReleaseRecord:
        prepared = self.get_candidate(command.release_id)
        if prepared is None:
            raise ReleaseStateError("Release candidate is unavailable")
        build_command = _command_from_prepared(prepared)
        now = datetime.now(timezone.utc)
        with self._sessions.begin() as session:
            pointer = _locked_pointer(session)
            if pointer.current_release_id != command.base_release_id:
                raise ReleaseStateError("current Release changed before publication")
            release = session.scalar(
                select(Release)
                .where(Release.release_id == command.release_id)
                .with_for_update()
            )
            if release is None or release.status != "candidate":
                raise ReleaseStateError("Release candidate is no longer publishable")
            index = session.scalar(
                select(IndexManifest)
                .where(IndexManifest.release_id == command.release_id)
                .with_for_update()
            )
            if index is None or index.status != "candidate":
                raise ReleaseStateError("Release candidate index is no longer publishable")

            snapshot = _resolve_snapshot(session, build_command, lock_cases=True)
            _require_snapshot_matches_manifest(snapshot, prepared.manifest)
            _require_candidate_columns(release, index, prepared)

            selected_cases = tuple(
                session.scalars(
                    select(RotationCase)
                    .where(
                        RotationCase.rotation_case_id.in_(
                            prepared.manifest.rotation_case_ids
                        )
                    )
                    .order_by(RotationCase.rotation_case_id)
                    .with_for_update()
                )
            ) if prepared.manifest.rotation_case_ids else ()
            decisions = {
                row.rotation_case_id: row
                for row in session.scalars(
                    select(RotationDecisionReceipt).where(
                        RotationDecisionReceipt.rotation_case_id.in_(
                            prepared.manifest.rotation_case_ids
                        )
                    )
                )
            } if prepared.manifest.rotation_case_ids else {}
            for case in selected_cases:
                decision = decisions[case.rotation_case_id]
                if decision.outcome == "retire":
                    session.get(KnowledgeRevision, case.knowledge_revision_id).status = "retired"
                elif decision.outcome == "replace":
                    session.get(KnowledgeRevision, case.knowledge_revision_id).status = "superseded"
                case.status = "included_in_release"
                case.included_release_id = release.release_id
                case.case_version += 1
                case.updated_at = now

            for item in prepared.manifest.items:
                revision = session.get(KnowledgeRevision, item.knowledge_revision_id)
                if revision.status == "approved":
                    revision.status = "released"
            release.status = "released"
            release.release_manager_subject = actor_id
            release.published_at = now
            index.status = "released"
            pointer.current_release_id = release.release_id
            pointer.pointer_version += 1
            pointer.updated_at = now
            session.add(
                AuditEvent(
                    audit_event_id=_audit_id("release.published", release.release_id),
                    actor_subject=actor_id,
                    action="release.published",
                    entity_type="release",
                    entity_id=release.release_id,
                    run_id=None,
                    details={
                        "previous_release_id": command.base_release_id,
                        "pointer_version": pointer.pointer_version,
                        "result": "released",
                    },
                )
            )
            session.flush()
        return PublishedReleaseRecord(
            release_id=release.release_id,
            version=release.version,
            previous_release_id=release.previous_release_id,
            manifest_object_key=release.manifest_object_key,
            manifest_sha256=release.manifest_sha256,
            index_manifest_version=release.index_manifest_version,
            published_at=now,
        )


def _resolve_snapshot(
    session: Session,
    command: ReleaseBuildCommand,
    *,
    lock_cases: bool = False,
) -> ReleaseBuildSnapshot:
    pointer = session.get(ReleasePointer, "current")
    if pointer is None:
        raise ReleaseStateError("current Release pointer is missing")
    if pointer.current_release_id != command.base_release_id:
        raise ReleaseStateError("current Release does not match base_release_id")
    evaluation_row = session.get(EvaluationRun, command.evaluation_run_id)
    evaluation = _evaluation_from_row(evaluation_row)
    require_passed_evaluation(evaluation)
    if evaluation.target_id != command.release_candidate_id:
        raise ReleaseStateError("EvaluationRun target does not match Release candidate")
    profile = session.get(ChunkProfile, command.chunk_profile_id)
    if profile is None:
        raise ReleaseMembershipError("ChunkProfile does not exist")

    membership: dict[str, str] = {}
    if command.base_release_id is not None:
        base = session.get(Release, command.base_release_id)
        if base is None or base.status != "released":
            raise ReleaseStateError("base Release is not released")
        for revision_id in session.scalars(
            select(ReleaseItem.knowledge_revision_id).where(
                ReleaseItem.release_id == command.base_release_id
            )
        ):
            membership[revision_id] = "carry_forward"

    pending_query = select(RotationCase).where(
        RotationCase.knowledge_revision_id.in_(tuple(membership)),
        RotationCase.status.in_(("open", "in_review", "decided")),
    ).order_by(RotationCase.rotation_case_id)
    if lock_cases:
        pending_query = pending_query.with_for_update()
    pending_cases = tuple(session.scalars(pending_query)) if membership else ()
    if tuple(case.rotation_case_id for case in pending_cases) != command.rotation_case_ids:
        raise ReleaseMembershipError(
            "all pending RotationCases affecting the base Release must be selected"
        )
    decisions: dict[str, RotationDecisionReceipt] = {}
    if pending_cases:
        if any(case.status != "decided" for case in pending_cases):
            raise ReleaseMembershipError("selected RotationCases must be decided")
        decisions = {
            row.rotation_case_id: row
            for row in session.scalars(
                select(RotationDecisionReceipt).where(
                    RotationDecisionReceipt.rotation_case_id.in_(
                        command.rotation_case_ids
                    )
                )
            )
        }
        if len(decisions) != len(pending_cases):
            raise ReleaseMembershipError("RotationCase decision receipt is missing")
    for case in pending_cases:
        decision = decisions[case.rotation_case_id]
        if decision.outcome == "retire":
            membership.pop(case.knowledge_revision_id, None)
        elif decision.outcome == "replace":
            membership.pop(case.knowledge_revision_id, None)
            membership[decision.target_knowledge_revision_id] = "replace"
        elif decision.outcome == "no_action":
            membership[case.knowledge_revision_id] = "no_action"
        else:
            if decision.target_knowledge_revision_id != case.knowledge_revision_id:
                raise ReleaseMembershipError("carry_forward target must remain unchanged")
            membership[case.knowledge_revision_id] = "carry_forward"
    for revision_id in command.additional_revision_ids:
        membership.setdefault(revision_id, "add")
    if not membership:
        raise ReleaseMembershipError("Release membership cannot be empty")

    items = tuple(
        _resolve_item(session, revision_id, disposition, command.chunk_profile_id)
        for revision_id, disposition in sorted(membership.items())
    )
    return ReleaseBuildSnapshot(
        current_release_id=pointer.current_release_id,
        evaluation=evaluation,
        chunk_profile_version=profile.version,
        items=items,
        rotation_case_ids=command.rotation_case_ids,
    )


def _resolve_item(
    session: Session,
    revision_id: str,
    disposition: str,
    chunk_profile_id: str,
) -> ReleaseItemSnapshot:
    revision = session.get(KnowledgeRevision, revision_id)
    if revision is None or revision.status not in {"approved", "released"}:
        raise ReleaseMembershipError(
            f"KnowledgeRevision is not approved for Release: {revision_id}"
        )
    evidence_ids = tuple(
        session.scalars(
            select(CandidateEvidence.evidence_id)
            .where(CandidateEvidence.candidate_id == revision.candidate_id)
            .order_by(CandidateEvidence.evidence_id)
        )
    )
    if not evidence_ids:
        raise ReleaseMembershipError(f"Release revision has no Evidence: {revision_id}")
    chunks = tuple(
        session.scalars(
            select(RetrievalChunk)
            .join(
                RetrievalChunkEvidence,
                RetrievalChunkEvidence.chunk_id == RetrievalChunk.chunk_id,
            )
            .where(
                RetrievalChunkEvidence.evidence_id.in_(evidence_ids),
                RetrievalChunk.chunk_profile_id == chunk_profile_id,
            )
            .distinct()
            .order_by(RetrievalChunk.chunk_id)
        )
    )
    chunk_ids = tuple(chunk.chunk_id for chunk in chunks)
    covered_evidence = frozenset(
        session.scalars(
            select(RetrievalChunkEvidence.evidence_id).where(
                RetrievalChunkEvidence.chunk_id.in_(chunk_ids),
                RetrievalChunkEvidence.evidence_id.in_(evidence_ids),
            )
        )
    ) if chunk_ids else frozenset()
    if covered_evidence != frozenset(evidence_ids):
        raise ReleaseMembershipError(
            f"Release Evidence is not fully projected by ChunkProfile: {revision_id}"
        )
    evidence_rows = tuple(
        session.scalars(select(Evidence).where(Evidence.evidence_id.in_(evidence_ids)))
    )
    if len(evidence_rows) != len(evidence_ids):
        raise ReleaseMembershipError(f"Release Evidence is missing: {revision_id}")
    if any(
        chunk.data_boundary == "prohibited"
        or chunk.rights.get("storage_allowed") is not True
        for chunk in chunks
    ):
        raise ReleaseMembershipError(
            f"Release chunk violates rights or data boundary: {revision_id}"
        )
    return ReleaseItemSnapshot(
        knowledge_revision_id=revision_id,
        content_sha256=revision.content_sha256,
        disposition=disposition,
        evidence_ids=evidence_ids,
        chunk_ids=chunk_ids,
    )


def _evaluation_from_row(row: EvaluationRun | None) -> ReleaseEvaluationRun:
    if row is None or row.metrics is None or row.release_id is not None:
        raise ReleaseStateError("immutable EvaluationRun is unavailable")
    try:
        run = ReleaseEvaluationRun.model_validate(row.metrics)
    except ValidationError as exc:
        raise ReleaseStateError("immutable EvaluationRun payload drift") from exc
    if (
        run.evaluation_run_id != row.evaluation_run_id
        or run.suite_version != row.suite_version
        or run.status != row.status
    ):
        raise ReleaseStateError("immutable EvaluationRun column drift")
    return run


def _locked_pointer(session: Session) -> ReleasePointer:
    pointer = session.scalar(
        select(ReleasePointer)
        .where(ReleasePointer.pointer_key == "current")
        .with_for_update()
    )
    if pointer is None:
        raise ReleaseStateError("current Release pointer is missing")
    return pointer


def _command_from_prepared(prepared: PreparedRelease) -> ReleaseBuildCommand:
    manifest = prepared.manifest
    return ReleaseBuildCommand(
        release_candidate_id=prepared.release_id,
        version=prepared.version,
        base_release_id=prepared.base_release_id,
        evaluation_run_id=prepared.evaluation_run_id,
        chunk_profile_id=manifest.chunk_profile_id,
        rotation_case_ids=manifest.rotation_case_ids,
        additional_revision_ids=tuple(
            item.knowledge_revision_id
            for item in manifest.items
            if item.disposition == "add"
        ),
        index_capabilities=prepared.index_manifest.capabilities,
        embedding_profile_id=prepared.index_manifest.embedding_profile_id,
        relation_index_version=prepared.index_manifest.relation_index_version,
        db_schema_revision=manifest.db_schema_revision,
        knowledge_contract_version=manifest.knowledge_contract_version,
        parser_profile_version=manifest.parser_profile_version,
        model_profile_version=manifest.model_profile_version,
        prompt_profile_version=manifest.prompt_profile_version,
    )


def _require_snapshot_matches_manifest(
    snapshot: ReleaseBuildSnapshot,
    manifest: ReleaseManifestPayload,
) -> None:
    expected_items = tuple(
        ReleaseManifestItem(**item.model_dump(mode="python"))
        for item in snapshot.items
    )
    if (
        snapshot.chunk_profile_version != manifest.chunk_profile_version
        or snapshot.rotation_case_ids != manifest.rotation_case_ids
        or expected_items != manifest.items
    ):
        raise ReleaseMembershipError("Release membership changed before publication")


def _require_candidate_columns(
    release: Release,
    index: IndexManifest,
    prepared: PreparedRelease,
) -> None:
    if (
        release.version != prepared.version
        or release.previous_release_id != prepared.base_release_id
        or release.manifest_object_key != prepared.manifest_descriptor.object_key
        or release.manifest_sha256 != prepared.manifest_descriptor.sha256
        or release.index_manifest_version != prepared.index_manifest.version
        or index.object_key != prepared.index_descriptor.object_key
        or index.sha256 != prepared.index_descriptor.sha256
        or index.version != prepared.index_manifest.version
    ):
        raise ReleaseStateError("Release candidate database facts drifted")


def _require_candidate_replay(
    session: Session,
    existing: Release,
    prepared: PreparedRelease,
) -> None:
    index = session.scalar(
        select(IndexManifest).where(IndexManifest.release_id == existing.release_id)
    )
    if index is None:
        raise ReleaseStateError("Release candidate replay is incomplete")
    _require_candidate_columns(existing, index, prepared)
    actual_items = tuple(
        session.execute(
            select(ReleaseItem.knowledge_revision_id, ReleaseItem.content_sha256)
            .where(ReleaseItem.release_id == existing.release_id)
            .order_by(ReleaseItem.knowledge_revision_id)
        )
    )
    expected_items = tuple(
        sorted(
            (item.knowledge_revision_id, item.content_sha256)
            for item in prepared.manifest.items
        )
    )
    if existing.status != "candidate" or actual_items != expected_items:
        raise ReleaseStateError("immutable Release candidate replay drift")


def _index_manifest_id(release_id: str) -> str:
    return f"index-{uuid5(NAMESPACE_URL, f'p17-index:{release_id}').hex}"


def _audit_id(action: str, release_id: str) -> str:
    return f"audit-{uuid5(NAMESPACE_URL, f'{action}:{release_id}').hex}"


__all__ = [
    "ReleaseMembershipError",
    "ReleaseStateError",
    "SqlAlchemyReleaseRepository",
]
