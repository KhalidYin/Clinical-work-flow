"""Repository ports and deterministic in-memory adapter for Source Registry."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol, Sequence
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from service.db.models import (
    AuditEvent,
    ObjectWriteIntent,
    ProcessingRun,
    Source,
    SourceArtifact,
    SourceVersion,
)
from service.object_store import ObjectDescriptor

from .contracts import (
    RegistrationIntentRecord,
    RegistrationIntentStatus,
    SourceRegistrationCommand,
    SourceRegistrationReceipt,
)


class SourceRepositoryError(RuntimeError):
    """Base error raised by Source Registry persistence."""


class RegistrationConflictError(SourceRepositoryError):
    """The same source version or idempotency key has conflicting facts."""


class SourceRegistryRepository(Protocol):
    def find_committed(
        self,
        *,
        command: SourceRegistrationCommand,
    ) -> SourceRegistrationReceipt | None: ...

    def prepare_intent(self, *, intent: RegistrationIntentRecord) -> RegistrationIntentRecord: ...

    def mark_intent(
        self,
        *,
        registration_id: str,
        status: RegistrationIntentStatus,
        failure_code: str | None = None,
    ) -> None: ...

    def commit_registration(
        self,
        *,
        command: SourceRegistrationCommand,
        intent: RegistrationIntentRecord,
        descriptor: ObjectDescriptor,
        run_id: str,
    ) -> SourceRegistrationReceipt: ...

    def list_reconcilable_intents(
        self,
        *,
        limit: int,
        minimum_age_seconds: int,
    ) -> Sequence[RegistrationIntentRecord]: ...

    def record_cleanup_audit(
        self,
        *,
        actor_id: str,
        intent: RegistrationIntentRecord,
        action: str,
        result: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class _CommittedSource:
    command: SourceRegistrationCommand
    receipt: SourceRegistrationReceipt


class InMemorySourceRegistryRepository:
    """Small test adapter with the same visibility and conflict semantics as PostgreSQL."""

    def __init__(self) -> None:
        self._intents: dict[str, RegistrationIntentRecord] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._committed: dict[tuple[str, str], _CommittedSource] = {}
        self._audit: list[str] = []
        self.fail_next_commit = False

    def find_committed(
        self,
        *,
        command: SourceRegistrationCommand,
    ) -> SourceRegistrationReceipt | None:
        existing = self._committed.get((command.source_id, command.version))
        if existing is None:
            return None
        if (
            existing.command.expected_sha256 != command.expected_sha256
            or existing.command.media_type != command.media_type
            or existing.command.rights != command.rights
            or existing.command.data_boundary != command.data_boundary
        ):
            raise RegistrationConflictError(
                f"source version {command.source_id} {command.version} already has different facts"
            )
        return existing.receipt

    def prepare_intent(self, *, intent: RegistrationIntentRecord) -> RegistrationIntentRecord:
        idempotency_key = (intent.actor_id, intent.idempotency_key)
        existing_id = self._idempotency.get(idempotency_key)
        if existing_id is not None:
            existing = self._intents[existing_id]
            comparable = (
                existing.source_id,
                existing.version,
                existing.sha256,
                existing.media_type,
                existing.size_bytes,
            )
            proposed = (
                intent.source_id,
                intent.version,
                intent.sha256,
                intent.media_type,
                intent.size_bytes,
            )
            if comparable != proposed:
                raise RegistrationConflictError("idempotency key was reused with different facts")
            return existing
        self._intents[intent.registration_id] = intent
        self._idempotency[idempotency_key] = intent.registration_id
        return intent

    def mark_intent(
        self,
        *,
        registration_id: str,
        status: RegistrationIntentStatus,
        failure_code: str | None = None,
    ) -> None:
        current = self._intents[registration_id]
        self._intents[registration_id] = current.model_copy(
            update={"status": status, "failure_code": failure_code}
        )

    def commit_registration(
        self,
        *,
        command: SourceRegistrationCommand,
        intent: RegistrationIntentRecord,
        descriptor: ObjectDescriptor,
        run_id: str,
    ) -> SourceRegistrationReceipt:
        if self.fail_next_commit:
            self.fail_next_commit = False
            raise SourceRepositoryError("source database commit failed")
        existing = self.find_committed(command=command)
        if existing is not None:
            return existing
        receipt = SourceRegistrationReceipt(
            source_id=command.source_id,
            source_version_id=intent.source_version_id,
            run_id=run_id,
            original_object=descriptor,
        )
        self._committed[(command.source_id, command.version)] = _CommittedSource(
            command=command,
            receipt=receipt,
        )
        self.mark_intent(
            registration_id=intent.registration_id,
            status=RegistrationIntentStatus.COMMITTED,
        )
        self._audit.append("source.registration_committed")
        return receipt

    def list_reconcilable_intents(
        self,
        *,
        limit: int,
        minimum_age_seconds: int,
    ) -> list[RegistrationIntentRecord]:
        del minimum_age_seconds
        allowed = {
            RegistrationIntentStatus.PENDING,
            RegistrationIntentStatus.OBJECT_WRITTEN,
            RegistrationIntentStatus.COMPENSATION_REQUIRED,
        }
        return [intent for intent in self._intents.values() if intent.status in allowed][:limit]

    def record_cleanup_audit(
        self,
        *,
        actor_id: str,
        intent: RegistrationIntentRecord,
        action: str,
        result: str,
    ) -> None:
        del actor_id, intent, result
        self._audit.append(action)

    def visible_source_versions(self) -> list[str]:
        return [committed.receipt.source_version_id for committed in self._committed.values()]

    def registration_intents(self) -> list[RegistrationIntentRecord]:
        return list(self._intents.values())

    def audit_actions(self) -> list[str]:
        return list(self._audit)


class SqlAlchemySourceRegistryRepository:
    """PostgreSQL adapter with invisible intents and atomic canonical commit."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def find_committed(
        self,
        *,
        command: SourceRegistrationCommand,
    ) -> SourceRegistrationReceipt | None:
        with self._sessions() as session:
            version = session.scalar(
                select(SourceVersion).where(
                    SourceVersion.source_id == command.source_id,
                    SourceVersion.version == command.version,
                )
            )
            if version is None:
                return None
            artifact = session.scalar(
                select(SourceArtifact)
                .where(
                    SourceArtifact.source_version_id == version.source_version_id,
                    SourceArtifact.artifact_kind.in_(("original", "canonical_source")),
                )
                .order_by(SourceArtifact.created_at)
                .limit(1)
            )
            run = session.scalar(
                select(ProcessingRun)
                .where(ProcessingRun.source_version_id == version.source_version_id)
                .order_by(ProcessingRun.created_at)
                .limit(1)
            )
        expected_rights = command.rights.model_dump(mode="json")
        if (
            version.sha256 != command.expected_sha256
            or version.rights != expected_rights
            or version.data_boundary != command.data_boundary.value
            or artifact is not None
            and artifact.media_type != command.media_type
        ):
            raise RegistrationConflictError(
                f"source version {command.source_id} {command.version} already has different facts"
            )
        if artifact is None:
            raise SourceRepositoryError("committed source version has no original artifact")
        suffix = version.source_version_id.removeprefix("srcv-")
        return SourceRegistrationReceipt(
            source_id=command.source_id,
            source_version_id=version.source_version_id,
            run_id=run.run_id if run is not None else f"run-{suffix}",
            original_object=ObjectDescriptor(
                object_key=artifact.object_key,
                sha256=artifact.sha256,
                media_type=artifact.media_type,
                size_bytes=artifact.size_bytes,
            ),
        )

    def prepare_intent(self, *, intent: RegistrationIntentRecord) -> RegistrationIntentRecord:
        with self._sessions.begin() as session:
            existing = session.scalar(
                select(ObjectWriteIntent)
                .where(
                    ObjectWriteIntent.actor_id == intent.actor_id,
                    ObjectWriteIntent.idempotency_key == intent.idempotency_key,
                )
                .with_for_update()
            )
            if existing is not None:
                record = _intent_record(existing)
                comparable = (
                    record.source_id,
                    record.version,
                    record.sha256,
                    record.media_type,
                    record.size_bytes,
                )
                proposed = (
                    intent.source_id,
                    intent.version,
                    intent.sha256,
                    intent.media_type,
                    intent.size_bytes,
                )
                if comparable != proposed:
                    raise RegistrationConflictError(
                        "idempotency key was reused with different facts"
                    )
                return record
            session.add(
                ObjectWriteIntent(
                    write_intent_id=intent.registration_id,
                    purpose="raw_source",
                    owner_type="source_registration",
                    owner_id=intent.source_version_id,
                    source_id=intent.source_id,
                    source_version_id=intent.source_version_id,
                    source_version_label=intent.version,
                    object_key=intent.object_key,
                    sha256=intent.sha256,
                    media_type=intent.media_type,
                    size_bytes=intent.size_bytes,
                    actor_id=intent.actor_id,
                    idempotency_key=intent.idempotency_key,
                    status=intent.status.value,
                    failure_code=intent.failure_code,
                )
            )
        return intent

    def mark_intent(
        self,
        *,
        registration_id: str,
        status: RegistrationIntentStatus,
        failure_code: str | None = None,
    ) -> None:
        with self._sessions.begin() as session:
            intent = session.scalar(
                select(ObjectWriteIntent)
                .where(ObjectWriteIntent.write_intent_id == registration_id)
                .with_for_update()
            )
            if intent is None:
                raise SourceRepositoryError("object write intent does not exist")
            intent.status = status.value
            intent.failure_code = failure_code
            intent.updated_at = _utcnow()

    def commit_registration(
        self,
        *,
        command: SourceRegistrationCommand,
        intent: RegistrationIntentRecord,
        descriptor: ObjectDescriptor,
        run_id: str,
    ) -> SourceRegistrationReceipt:
        del run_id
        with self._sessions.begin() as session:
            write_intent = session.scalar(
                select(ObjectWriteIntent)
                .where(ObjectWriteIntent.write_intent_id == intent.registration_id)
                .with_for_update()
            )
            if write_intent is None:
                raise SourceRepositoryError("object write intent does not exist")
            source = session.get(Source, command.source_id)
            if source is None:
                source = Source(
                    source_id=command.source_id,
                    title=command.title,
                    source_type=command.source_type,
                    owner_org=None,
                )
                session.add(source)
                session.flush()
            elif source.source_type != command.source_type:
                raise RegistrationConflictError(
                    "source_id is already registered with another source_type"
                )
            version = session.scalar(
                select(SourceVersion)
                .where(
                    SourceVersion.source_id == command.source_id,
                    SourceVersion.version == command.version,
                )
                .with_for_update()
            )
            if version is not None:
                raise RegistrationConflictError(
                    f"source version {command.source_id} {command.version} already exists"
                )
            session.add(
                SourceVersion(
                    source_version_id=intent.source_version_id,
                    source_id=command.source_id,
                    version=command.version,
                    sha256=command.expected_sha256,
                    rights=command.rights.model_dump(mode="json"),
                    data_boundary=command.data_boundary.value,
                    status="registered",
                )
            )
            session.flush()
            artifact_id = f"artifact-{uuid4()}"
            session.add(
                SourceArtifact(
                    artifact_id=artifact_id,
                    source_version_id=intent.source_version_id,
                    artifact_kind="original",
                    parent_artifact_id=None,
                    object_key=descriptor.object_key,
                    sha256=descriptor.sha256,
                    media_type=descriptor.media_type,
                    size_bytes=descriptor.size_bytes,
                    parser_profile_version=None,
                    status="available",
                )
            )
            write_intent.status = RegistrationIntentStatus.COMMITTED.value
            write_intent.failure_code = None
            write_intent.updated_at = _utcnow()
            session.add(
                AuditEvent(
                    audit_event_id=f"audit-{uuid4()}",
                    actor_subject=intent.actor_id,
                    action="source.registration_committed",
                    entity_type="source_version",
                    entity_id=intent.source_version_id,
                    run_id=None,
                    details={
                        "object_key": descriptor.object_key,
                        "sha256": descriptor.sha256,
                        "rights": command.rights.model_dump(mode="json"),
                        "data_boundary": command.data_boundary.value,
                    },
                )
            )
        suffix = intent.source_version_id.removeprefix("srcv-")
        return SourceRegistrationReceipt(
            source_id=command.source_id,
            source_version_id=intent.source_version_id,
            run_id=f"run-{suffix}",
            original_object=descriptor,
        )

    def list_reconcilable_intents(
        self,
        *,
        limit: int,
        minimum_age_seconds: int,
    ) -> list[RegistrationIntentRecord]:
        cutoff = _utcnow() - timedelta(seconds=minimum_age_seconds)
        with self._sessions() as session:
            rows = list(
                session.scalars(
                    select(ObjectWriteIntent)
                    .where(
                        ObjectWriteIntent.status.in_(
                            [
                                RegistrationIntentStatus.PENDING.value,
                                RegistrationIntentStatus.OBJECT_WRITTEN.value,
                                RegistrationIntentStatus.COMPENSATION_REQUIRED.value,
                            ]
                        ),
                        ObjectWriteIntent.updated_at <= cutoff,
                    )
                    .order_by(
                        ObjectWriteIntent.updated_at,
                        ObjectWriteIntent.write_intent_id,
                    )
                    .limit(limit)
                )
            )
        return [_intent_record(row) for row in rows]

    def record_cleanup_audit(
        self,
        *,
        actor_id: str,
        intent: RegistrationIntentRecord,
        action: str,
        result: str,
    ) -> None:
        with self._sessions.begin() as session:
            session.add(
                AuditEvent(
                    audit_event_id=f"audit-{uuid4()}",
                    actor_subject=actor_id,
                    action=action,
                    entity_type="object_write_intent",
                    entity_id=intent.registration_id,
                    run_id=None,
                    details={
                        "result": result,
                        "purpose": intent.purpose,
                        "object_key": intent.object_key,
                        "sha256": intent.sha256,
                    },
                )
            )


def _intent_record(intent: ObjectWriteIntent) -> RegistrationIntentRecord:
    return RegistrationIntentRecord(
        registration_id=intent.write_intent_id,
        purpose=intent.purpose,
        source_id=intent.source_id,
        source_version_id=intent.source_version_id,
        version=intent.source_version_label,
        object_key=intent.object_key,
        sha256=intent.sha256,
        media_type=intent.media_type,
        size_bytes=intent.size_bytes,
        actor_id=intent.actor_id,
        idempotency_key=intent.idempotency_key,
        status=RegistrationIntentStatus(intent.status),
        failure_code=intent.failure_code,
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "InMemorySourceRegistryRepository",
    "RegistrationConflictError",
    "SqlAlchemySourceRegistryRepository",
    "SourceRegistryRepository",
    "SourceRepositoryError",
]
