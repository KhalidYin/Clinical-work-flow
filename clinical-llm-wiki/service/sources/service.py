"""Application service coordinating Source Registry, objects, and processing runs."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from zipfile import BadZipFile, ZipFile
from uuid import NAMESPACE_URL, uuid5

from service.auth import (
    ActorContext,
    Permission,
    PrincipalType,
    WorkerPool,
    require_permission,
)
from service.object_store import (
    ObjectNotFoundError,
    ObjectStorePort,
)
from service.processing.contracts import StepDefinition
from service.processing.ledger import ProcessingLedgerPort

from .contracts import (
    DataBoundary,
    OrphanReconcileResult,
    RegistrationIntentRecord,
    RegistrationIntentStatus,
    SourceRegistrationCommand,
    SourceRegistrationReceipt,
)
from .repository import (
    RegistrationConflictError,
    SourceRegistryRepository,
)


class SourceRegistrationError(RuntimeError):
    """A source cannot become a visible registered version."""


class UnsupportedSourceMediaError(SourceRegistrationError):
    """Declared media type is unsupported or does not match the bytes."""


_MEDIA_EXTENSIONS = {
    "text/plain": "txt",
    "text/markdown": "md",
    "application/pdf": "pdf",
    ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"): "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
}


class SourceRegistryService:
    """A lightweight saga: invisible intent -> object -> canonical DB -> run."""

    def __init__(
        self,
        *,
        repository: SourceRegistryRepository,
        object_store: ObjectStorePort,
        ledger: ProcessingLedgerPort,
    ) -> None:
        self._repository = repository
        self._objects = object_store
        self._ledger = ledger

    def register_and_start(
        self,
        *,
        actor: ActorContext,
        command: SourceRegistrationCommand,
        content: bytes,
    ) -> SourceRegistrationReceipt:
        _require_source_registration(actor)
        digest = _validate_source(command=command, content=content)
        existing = self._repository.find_committed(command=command)
        if existing is not None:
            try:
                descriptor = self._objects.head(existing.original_object.object_key)
            except ObjectNotFoundError as exc:
                raise SourceRegistrationError("committed source object is missing") from exc
            if descriptor != existing.original_object:
                raise SourceRegistrationError(
                    "committed source object metadata no longer matches the registry"
                )
            self._ensure_processing_run(existing, actor=actor, command=command)
            return existing

        stable_id = uuid5(
            NAMESPACE_URL,
            f"clinical-source:{actor.actor_id}:{command.idempotency_key}",
        ).hex
        source_version_id = f"srcv-{stable_id}"
        registration_id = f"reg-{stable_id}"
        run_id = f"run-{stable_id}"
        extension = _MEDIA_EXTENSIONS[command.media_type]
        object_key = f"sources/{command.source_id}/{source_version_id}/{digest}.{extension}"
        proposed_intent = RegistrationIntentRecord(
            registration_id=registration_id,
            purpose="raw_source",
            source_id=command.source_id,
            source_version_id=source_version_id,
            version=command.version,
            object_key=object_key,
            sha256=digest,
            media_type=command.media_type,
            size_bytes=len(content),
            actor_id=actor.actor_id,
            idempotency_key=command.idempotency_key,
            status=RegistrationIntentStatus.PENDING,
        )
        intent = self._repository.prepare_intent(intent=proposed_intent)
        object_written = False
        try:
            descriptor = self._objects.put_bytes(
                intent.object_key,
                content,
                media_type=command.media_type,
                expected_sha256=digest,
            )
            object_written = True
            self._repository.mark_intent(
                registration_id=intent.registration_id,
                status=RegistrationIntentStatus.OBJECT_WRITTEN,
            )
            receipt = self._repository.commit_registration(
                command=command,
                intent=intent,
                descriptor=descriptor,
                run_id=run_id,
            )
        except RegistrationConflictError:
            if object_written:
                self._compensate(intent)
            raise
        except Exception as exc:
            if object_written:
                self._compensate(intent)
            else:
                self._safe_mark(
                    intent.registration_id,
                    RegistrationIntentStatus.FAILED,
                    "object_write_failed",
                )
            if isinstance(exc, SourceRegistrationError):
                raise
            raise SourceRegistrationError("source registration commit failed") from exc

        try:
            self._ensure_processing_run(receipt, actor=actor, command=command)
        except Exception as exc:
            # The source is fully registered and safe to retry. A deterministic run ID
            # makes a repeated registration request resume rather than duplicate it.
            raise SourceRegistrationError(
                "source registered but processing run could not be started"
            ) from exc
        return receipt

    def reconcile_orphans(
        self,
        *,
        actor: ActorContext,
        limit: int = 100,
        minimum_age_seconds: int = 300,
    ) -> OrphanReconcileResult:
        if (
            actor.principal_type is not PrincipalType.SERVICE_ACCOUNT
            or actor.worker_pool is not WorkerPool.DOCUMENT
        ):
            raise PermissionError("orphan reconciliation requires the document worker")
        require_permission(actor, Permission.OBJECT_WRITE_DERIVED)
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        if minimum_age_seconds < 0:
            raise ValueError("minimum_age_seconds cannot be negative")

        intents = self._repository.list_reconcilable_intents(
            limit=limit,
            minimum_age_seconds=minimum_age_seconds,
        )
        deleted = 0
        missing = 0
        failed = 0
        for intent in intents:
            try:
                self._objects.delete(intent.object_key)
            except ObjectNotFoundError:
                missing += 1
                self._repository.mark_intent(
                    registration_id=intent.registration_id,
                    status=RegistrationIntentStatus.COMPENSATED,
                    failure_code="object_already_missing",
                )
                self._repository.record_cleanup_audit(
                    actor_id=actor.actor_id,
                    intent=intent,
                    action="object.orphan_missing",
                    result="compensated",
                )
            except Exception:
                failed += 1
                self._repository.mark_intent(
                    registration_id=intent.registration_id,
                    status=RegistrationIntentStatus.COMPENSATION_REQUIRED,
                    failure_code="object_delete_failed",
                )
                self._repository.record_cleanup_audit(
                    actor_id=actor.actor_id,
                    intent=intent,
                    action="object.orphan_cleanup_failed",
                    result="failed",
                )
            else:
                deleted += 1
                self._repository.mark_intent(
                    registration_id=intent.registration_id,
                    status=RegistrationIntentStatus.COMPENSATED,
                )
                self._repository.record_cleanup_audit(
                    actor_id=actor.actor_id,
                    intent=intent,
                    action="object.orphan_compensated",
                    result="deleted",
                )
        return OrphanReconcileResult(
            scanned=len(intents),
            deleted=deleted,
            missing=missing,
            failed=failed,
        )

    def _ensure_processing_run(
        self,
        receipt: SourceRegistrationReceipt,
        *,
        actor: ActorContext,
        command: SourceRegistrationCommand,
    ) -> None:
        from service.processing.document_worker import build_document_step_definitions
        from service.processing.enrichment import build_enrichment_step_definition

        steps: list[StepDefinition] = build_document_step_definitions(
            media_type=command.media_type,
            input_sha256=command.expected_sha256,
        )
        steps.append(
            build_enrichment_step_definition(input_sha256=command.expected_sha256)
        )
        self._ledger.create_run(
            source_version_id=receipt.source_version_id,
            requested_by_subject=actor.actor_id,
            steps=steps,
            run_id=receipt.run_id,
        )

    def _compensate(self, intent: RegistrationIntentRecord) -> None:
        try:
            self._objects.delete(intent.object_key)
        except Exception:
            self._safe_mark(
                intent.registration_id,
                RegistrationIntentStatus.COMPENSATION_REQUIRED,
                "object_delete_failed",
            )
        else:
            self._safe_mark(
                intent.registration_id,
                RegistrationIntentStatus.COMPENSATED,
                "source_commit_failed",
            )

    def _safe_mark(
        self,
        registration_id: str,
        status: RegistrationIntentStatus,
        failure_code: str,
    ) -> None:
        try:
            self._repository.mark_intent(
                registration_id=registration_id,
                status=status,
                failure_code=failure_code,
            )
        except Exception:
            # A persisted pending intent and deterministic object key allow the
            # reconciler to resume after the database becomes available.
            return


def _require_source_registration(actor: ActorContext) -> None:
    if actor.principal_type is not PrincipalType.HUMAN:
        raise PermissionError("only a human curator may register a source")
    for permission in (
        Permission.SOURCE_REGISTER,
        Permission.SOURCE_UPLOAD,
        Permission.PROCESSING_START,
    ):
        require_permission(actor, permission)


def _validate_source(*, command: SourceRegistrationCommand, content: bytes) -> str:
    if not isinstance(content, bytes) or not content:
        raise SourceRegistrationError("source content is required")
    digest = sha256(content).hexdigest()
    if digest != command.expected_sha256:
        raise SourceRegistrationError("source hash does not match expected hash")
    if not command.rights.storage_allowed or command.data_boundary is DataBoundary.PROHIBITED:
        raise SourceRegistrationError("source rights do not permit storage")
    _validate_media_signature(command.media_type, content)
    return digest


def _validate_media_signature(media_type: str, content: bytes) -> None:
    if media_type not in _MEDIA_EXTENSIONS:
        raise UnsupportedSourceMediaError(f"unsupported media type: {media_type}")
    if media_type == "application/pdf":
        if not content.startswith(b"%PDF-"):
            raise UnsupportedSourceMediaError("PDF media signature does not match bytes")
        return
    if media_type in {"text/plain", "text/markdown"}:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UnsupportedSourceMediaError("text media must be valid UTF-8") from exc
        return
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
    except BadZipFile as exc:
        raise UnsupportedSourceMediaError("OOXML media signature is not a ZIP package") from exc
    required = (
        "word/document.xml"
        if media_type.endswith("wordprocessingml.document")
        else "xl/workbook.xml"
    )
    if "[Content_Types].xml" not in names or required not in names:
        raise UnsupportedSourceMediaError("OOXML media signature does not match declared type")


__all__ = [
    "RegistrationConflictError",
    "SourceRegistrationError",
    "SourceRegistryService",
    "UnsupportedSourceMediaError",
]
