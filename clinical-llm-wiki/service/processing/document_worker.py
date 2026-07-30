"""Deterministic Document Worker handlers for P2-A Source -> Evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from collections.abc import Callable
from typing import Any, Mapping, Protocol, Sequence
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from service.auth import WorkerPool
from service.db.models import (
    AuditEvent,
    Evidence,
    JobStep,
    ObjectWriteIntent,
    ProcessingRun,
    Source,
    SourceArtifact,
    SourceVersion,
    StepAttempt,
)
from service.object_store import ObjectDescriptor, ObjectStorePort

from .contracts import ArtifactManifest, ClaimedStepAttempt, StepDefinition, StepOutcome
from .parsers import (
    DOCUMENT_PARSER_PROFILE_VERSION,
    ParserRegistry,
    ParserResult,
    SourceDocument,
)


class DocumentStepContext(Protocol):
    claim: ClaimedStepAttempt

    def heartbeat(self) -> None: ...

    def checkpoint(self, value: dict[str, Any]) -> None: ...


@dataclass(frozen=True, slots=True)
class PreparedDerivedWrite:
    write_intent_id: str
    already_committed: bool


class DocumentRepositoryPort(Protocol):
    def load_source_for_run(self, *, run_id: str) -> SourceDocument: ...

    def prepare_derived_write(
        self,
        *,
        actor_id: str,
        run_id: str,
        attempt_id: str,
        source: SourceDocument,
        descriptor: ObjectDescriptor,
        parser_profile_version: str,
    ) -> PreparedDerivedWrite: ...

    def mark_derived_write(
        self,
        *,
        write_intent_id: str,
        status: str,
        failure_code: str | None = None,
    ) -> None: ...

    def record_derived_artifact(
        self,
        *,
        write_intent_id: str,
        run_id: str,
        attempt_id: str,
        source: SourceDocument,
        descriptor: ObjectDescriptor,
        parser_profile_version: str,
    ) -> None: ...

    def successful_parse_artifacts(
        self,
        *,
        run_id: str,
    ) -> Sequence[ObjectDescriptor]: ...

    def persist_evidence(
        self,
        *,
        run_id: str,
        source: SourceDocument,
        parsed_results: Sequence[tuple[ObjectDescriptor, ParserResult]],
    ) -> str: ...


class InMemoryDocumentRepository:
    """Deterministic unit-test repository; PostgreSQL owns production state."""

    def __init__(self, *, source: SourceDocument) -> None:
        self.source = source
        self.derived: dict[str, dict[str, Any]] = {}
        self.manifests: dict[tuple[str, str], ArtifactManifest] = {}
        self.evidence: list[dict[str, Any]] = []
        self.run_status = "processing"
        self.candidates: list[object] = []
        self.releases: list[object] = []
        self.write_intents: dict[str, str] = {}
        self.intent_by_object_key: dict[str, str] = {}

    def load_source_for_run(self, *, run_id: str) -> SourceDocument:
        del run_id
        return self.source

    def prepare_derived_write(
        self,
        *,
        actor_id: str,
        run_id: str,
        attempt_id: str,
        source: SourceDocument,
        descriptor: ObjectDescriptor,
        parser_profile_version: str,
    ) -> PreparedDerivedWrite:
        del actor_id, run_id, source, parser_profile_version
        existing_id = self.intent_by_object_key.get(descriptor.object_key)
        if existing_id is not None:
            return PreparedDerivedWrite(
                write_intent_id=existing_id,
                already_committed=self.write_intents[existing_id] == "committed",
            )
        intent_id = f"ow-{attempt_id}"
        self.write_intents[intent_id] = "pending"
        self.intent_by_object_key[descriptor.object_key] = intent_id
        return PreparedDerivedWrite(
            write_intent_id=intent_id,
            already_committed=False,
        )

    def mark_derived_write(
        self,
        *,
        write_intent_id: str,
        status: str,
        failure_code: str | None = None,
    ) -> None:
        del failure_code
        self.write_intents[write_intent_id] = status

    def record_derived_artifact(
        self,
        *,
        write_intent_id: str,
        run_id: str,
        attempt_id: str,
        source: SourceDocument,
        descriptor: ObjectDescriptor,
        parser_profile_version: str,
    ) -> None:
        del run_id, source
        self.derived[descriptor.object_key] = {
            "attempt_id": attempt_id,
            "descriptor": descriptor,
            "parser_profile_version": parser_profile_version,
        }
        self.write_intents[write_intent_id] = "committed"

    def record_successful_manifest(
        self,
        run_id: str,
        step_key: str,
        manifest: ArtifactManifest,
    ) -> None:
        self.manifests[(run_id, step_key)] = manifest

    def successful_parse_artifacts(self, *, run_id: str) -> list[ObjectDescriptor]:
        descriptors: list[ObjectDescriptor] = []
        for (manifest_run_id, step_key), manifest in self.manifests.items():
            if manifest_run_id == run_id and step_key.startswith("document.parse_"):
                descriptors.extend(manifest.artifacts)
        return descriptors

    def persist_evidence(
        self,
        *,
        run_id: str,
        source: SourceDocument,
        parsed_results: Sequence[tuple[ObjectDescriptor, ParserResult]],
    ) -> str:
        del run_id
        hashes: list[str] = []
        for descriptor, result in parsed_results:
            for fragment in result.fragments:
                self.evidence.append(
                    {
                        "source_version_id": source.source_version_id,
                        "source_sha256": source.source_sha256,
                        "source_artifact_kind": "original",
                        "derived_artifact_kind": "parser_output",
                        "derived_object_key": descriptor.object_key,
                        "derived_object_sha256": descriptor.sha256,
                        "parser_profile_version": result.parser_profile_version,
                        "evidence_type": fragment.evidence_type,
                        "locator": fragment.locator,
                        "content": fragment.content,
                        "content_sha256": fragment.content_sha256,
                    }
                )
                hashes.append(fragment.content_sha256)
        if not hashes:
            raise ValueError("fan-in produced no evidence")
        self.run_status = "evidence_ready"
        return sha256("\n".join(sorted(hashes)).encode("utf-8")).hexdigest()


class DocumentWorkerService:
    def __init__(
        self,
        *,
        repository: DocumentRepositoryPort,
        object_store: ObjectStorePort,
        parsers: ParserRegistry,
        actor_id: str = "svc-document",
    ) -> None:
        self._repository = repository
        self._objects = object_store
        self._parsers = parsers
        self._actor_id = actor_id

    def validate(self, context: DocumentStepContext) -> StepOutcome:
        source = self._repository.load_source_for_run(run_id=context.claim.run_id)
        if not source.rights.get("storage_allowed", False) or source.data_boundary == "prohibited":
            raise PermissionError("source rights prohibit document processing")
        descriptor = self._objects.head(source.object_key)
        content = self._objects.get_bytes(source.object_key)
        if (
            descriptor.sha256 != source.source_sha256
            or sha256(content).hexdigest() != source.source_sha256
            or descriptor.media_type != source.media_type
        ):
            raise ValueError("source object hash or media type drift")
        context.checkpoint({"validated_source_sha256": source.source_sha256})
        return StepOutcome(
            output_sha256=source.source_sha256,
            artifact_manifest=ArtifactManifest(),
        )

    def parse(self, context: DocumentStepContext, *, branch: str) -> StepOutcome:
        source = self._repository.load_source_for_run(run_id=context.claim.run_id)
        content = self._objects.get_bytes(source.object_key)
        result = self._parsers.for_media_type(source.media_type).parse(
            source=source,
            content=content,
            branch=branch,
        )
        payload = json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        payload_hash = sha256(payload).hexdigest()
        object_key = (
            f"derived/{source.source_version_id}/"
            f"{DOCUMENT_PARSER_PROFILE_VERSION}/{branch}/{payload_hash}.json"
        )
        planned = ObjectDescriptor(
            object_key=object_key,
            sha256=payload_hash,
            media_type="application/json",
            size_bytes=len(payload),
        )
        prepared_write = self._repository.prepare_derived_write(
            actor_id=self._actor_id,
            run_id=context.claim.run_id,
            attempt_id=context.claim.attempt_id,
            source=source,
            descriptor=planned,
            parser_profile_version=DOCUMENT_PARSER_PROFILE_VERSION,
        )
        if prepared_write.already_committed:
            descriptor = self._objects.head(object_key)
            if descriptor != planned:
                raise ValueError("committed derived object metadata drift")
            context.checkpoint(
                {
                    "branch": branch,
                    "derived_object_key": descriptor.object_key,
                    "derived_object_sha256": descriptor.sha256,
                    "reused_committed_artifact": True,
                }
            )
            return StepOutcome(
                output_sha256=descriptor.sha256,
                artifact_manifest=ArtifactManifest(artifacts=(descriptor,)),
            )
        write_intent_id = prepared_write.write_intent_id
        descriptor: ObjectDescriptor | None = None
        try:
            descriptor = self._objects.put_bytes(
                object_key,
                payload,
                media_type="application/json",
                expected_sha256=payload_hash,
            )
            self._repository.mark_derived_write(
                write_intent_id=write_intent_id,
                status="object_written",
            )
            self._repository.record_derived_artifact(
                write_intent_id=write_intent_id,
                run_id=context.claim.run_id,
                attempt_id=context.claim.attempt_id,
                source=source,
                descriptor=descriptor,
                parser_profile_version=DOCUMENT_PARSER_PROFILE_VERSION,
            )
        except Exception:
            if descriptor is not None:
                try:
                    self._objects.delete(descriptor.object_key)
                except Exception:
                    self._repository.mark_derived_write(
                        write_intent_id=write_intent_id,
                        status="compensation_required",
                        failure_code="object_delete_failed",
                    )
                else:
                    self._repository.mark_derived_write(
                        write_intent_id=write_intent_id,
                        status="compensated",
                        failure_code="derived_commit_failed",
                    )
            else:
                self._repository.mark_derived_write(
                    write_intent_id=write_intent_id,
                    status="failed",
                    failure_code="object_write_failed",
                )
            raise
        context.checkpoint(
            {
                "branch": branch,
                "derived_object_key": descriptor.object_key,
                "derived_object_sha256": descriptor.sha256,
            }
        )
        return StepOutcome(
            output_sha256=descriptor.sha256,
            artifact_manifest=ArtifactManifest(artifacts=(descriptor,)),
        )

    def persist_evidence(self, context: DocumentStepContext) -> StepOutcome:
        source = self._repository.load_source_for_run(run_id=context.claim.run_id)
        descriptors = self._repository.successful_parse_artifacts(run_id=context.claim.run_id)
        if not descriptors:
            raise ValueError("no successful parser artifacts are available for fan-in")
        results: list[tuple[ObjectDescriptor, ParserResult]] = []
        for descriptor in descriptors:
            payload = self._objects.get_bytes(descriptor.object_key)
            if sha256(payload).hexdigest() != descriptor.sha256:
                raise ValueError("derived parser artifact hash drift")
            result = ParserResult.model_validate_json(payload)
            if (
                result.source_version_id != source.source_version_id
                or result.source_sha256 != source.source_sha256
                or result.parser_profile_version != DOCUMENT_PARSER_PROFILE_VERSION
            ):
                raise ValueError("parser artifact provenance mismatch")
            results.append((descriptor, result))
        output_hash = self._repository.persist_evidence(
            run_id=context.claim.run_id,
            source=source,
            parsed_results=results,
        )
        context.checkpoint(
            {
                "evidence_output_sha256": output_hash,
                "parser_artifact_count": len(results),
            }
        )
        return StepOutcome(
            output_sha256=output_hash,
            artifact_manifest=ArtifactManifest(
                artifacts=tuple(descriptor for descriptor, _ in results)
            ),
        )


class SqlAlchemyDocumentRepository:
    """PostgreSQL adapter for source validation, derived lineage, and Evidence fan-in."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def load_source_for_run(self, *, run_id: str) -> SourceDocument:
        with self._sessions() as session:
            row = session.execute(
                select(ProcessingRun, SourceVersion, Source, SourceArtifact)
                .join(
                    SourceVersion,
                    SourceVersion.source_version_id == ProcessingRun.source_version_id,
                )
                .join(Source, Source.source_id == SourceVersion.source_id)
                .join(
                    SourceArtifact,
                    (SourceArtifact.source_version_id == SourceVersion.source_version_id)
                    & SourceArtifact.artifact_kind.in_(("original", "canonical_source")),
                )
                .where(ProcessingRun.run_id == run_id)
            ).one_or_none()
        if row is None:
            raise ValueError("processing run has no complete original source artifact")
        _run, version, source, artifact = row
        return SourceDocument(
            source_id=source.source_id,
            source_version_id=version.source_version_id,
            source_sha256=version.sha256,
            media_type=artifact.media_type,
            object_key=artifact.object_key,
            data_boundary=version.data_boundary,
            rights=version.rights,
        )

    def prepare_derived_write(
        self,
        *,
        actor_id: str,
        run_id: str,
        attempt_id: str,
        source: SourceDocument,
        descriptor: ObjectDescriptor,
        parser_profile_version: str,
    ) -> PreparedDerivedWrite:
        del run_id, parser_profile_version
        stable = uuid5(
            NAMESPACE_URL,
            f"clinical-derived:{attempt_id}:{descriptor.object_key}",
        ).hex
        write_intent_id = f"ow-{stable}"
        idempotency_key = f"derived:{attempt_id}:{descriptor.sha256}"
        with self._sessions.begin() as session:
            canonical_artifact = session.scalar(
                select(SourceArtifact).where(SourceArtifact.object_key == descriptor.object_key)
            )
            if canonical_artifact is not None:
                if (
                    canonical_artifact.sha256 != descriptor.sha256
                    or canonical_artifact.source_version_id != source.source_version_id
                ):
                    raise ValueError("derived artifact key conflicts with canonical facts")
                canonical_intent = session.scalar(
                    select(ObjectWriteIntent).where(
                        ObjectWriteIntent.object_key == descriptor.object_key
                    )
                )
                if canonical_intent is None:
                    raise ValueError("canonical derived artifact has no write intent")
                if canonical_intent.status != "committed":
                    raise ValueError("canonical derived artifact has an uncommitted intent")
                return PreparedDerivedWrite(
                    write_intent_id=canonical_intent.write_intent_id,
                    already_committed=True,
                )
            object_intent = session.scalar(
                select(ObjectWriteIntent)
                .where(ObjectWriteIntent.object_key == descriptor.object_key)
                .with_for_update()
            )
            if object_intent is not None:
                if (
                    object_intent.purpose != "parser_output"
                    or object_intent.source_version_id != source.source_version_id
                    or object_intent.sha256 != descriptor.sha256
                    or object_intent.media_type != descriptor.media_type
                    or object_intent.size_bytes != descriptor.size_bytes
                ):
                    raise ValueError("derived object key conflicts with write intent facts")
                if object_intent.status == "committed":
                    raise ValueError("committed derived intent has no canonical artifact")
                object_intent.owner_id = attempt_id
                object_intent.actor_id = actor_id
                object_intent.idempotency_key = idempotency_key
                object_intent.status = "pending"
                object_intent.failure_code = None
                object_intent.updated_at = _utcnow()
                return PreparedDerivedWrite(
                    write_intent_id=object_intent.write_intent_id,
                    already_committed=False,
                )
            existing = session.get(ObjectWriteIntent, write_intent_id)
            if existing is not None:
                if (
                    existing.object_key != descriptor.object_key
                    or existing.sha256 != descriptor.sha256
                    or existing.owner_id != attempt_id
                ):
                    raise ValueError("derived write intent conflicts with existing facts")
                return PreparedDerivedWrite(
                    write_intent_id=write_intent_id,
                    already_committed=existing.status == "committed",
                )
            version_label = session.scalar(
                select(SourceVersion.version).where(
                    SourceVersion.source_version_id == source.source_version_id
                )
            )
            if version_label is None:
                raise ValueError("source version does not exist")
            session.add(
                ObjectWriteIntent(
                    write_intent_id=write_intent_id,
                    purpose="parser_output",
                    owner_type="step_attempt",
                    owner_id=attempt_id,
                    source_id=source.source_id,
                    source_version_id=source.source_version_id,
                    source_version_label=version_label,
                    object_key=descriptor.object_key,
                    sha256=descriptor.sha256,
                    media_type=descriptor.media_type,
                    size_bytes=descriptor.size_bytes,
                    actor_id=actor_id,
                    idempotency_key=idempotency_key,
                    status="pending",
                    failure_code=None,
                )
            )
        return PreparedDerivedWrite(
            write_intent_id=write_intent_id,
            already_committed=False,
        )

    def mark_derived_write(
        self,
        *,
        write_intent_id: str,
        status: str,
        failure_code: str | None = None,
    ) -> None:
        with self._sessions.begin() as session:
            intent = session.scalar(
                select(ObjectWriteIntent)
                .where(ObjectWriteIntent.write_intent_id == write_intent_id)
                .with_for_update()
            )
            if intent is None:
                raise ValueError("derived write intent does not exist")
            if intent.status == "committed" and status == "object_written":
                return
            intent.status = status
            intent.failure_code = failure_code
            intent.updated_at = _utcnow()

    def record_derived_artifact(
        self,
        *,
        write_intent_id: str,
        run_id: str,
        attempt_id: str,
        source: SourceDocument,
        descriptor: ObjectDescriptor,
        parser_profile_version: str,
    ) -> None:
        with self._sessions.begin() as session:
            intent = session.scalar(
                select(ObjectWriteIntent)
                .where(ObjectWriteIntent.write_intent_id == write_intent_id)
                .with_for_update()
            )
            if intent is None:
                raise ValueError("derived write intent does not exist")
            original = session.scalar(
                select(SourceArtifact).where(
                    SourceArtifact.source_version_id == source.source_version_id,
                    SourceArtifact.artifact_kind.in_(("original", "canonical_source")),
                )
            )
            if original is None:
                raise ValueError("source has no original artifact")
            existing = session.scalar(
                select(SourceArtifact).where(SourceArtifact.object_key == descriptor.object_key)
            )
            if existing is None:
                stable = uuid5(
                    NAMESPACE_URL,
                    f"clinical-artifact:{descriptor.object_key}:{descriptor.sha256}",
                ).hex
                session.add(
                    SourceArtifact(
                        artifact_id=f"artifact-{stable}",
                        source_version_id=source.source_version_id,
                        artifact_kind="parser_output",
                        parent_artifact_id=original.artifact_id,
                        object_key=descriptor.object_key,
                        sha256=descriptor.sha256,
                        media_type=descriptor.media_type,
                        size_bytes=descriptor.size_bytes,
                        parser_profile_version=parser_profile_version,
                        status="available",
                    )
                )
            elif (
                existing.sha256 != descriptor.sha256
                or existing.parent_artifact_id != original.artifact_id
            ):
                raise ValueError("derived artifact key conflicts with canonical lineage")
            intent.status = "committed"
            intent.failure_code = None
            intent.updated_at = _utcnow()
            session.add(
                AuditEvent(
                    audit_event_id=f"audit-{uuid4()}",
                    actor_subject=intent.actor_id,
                    action="object.derived_committed",
                    entity_type="source_artifact",
                    entity_id=descriptor.object_key,
                    run_id=run_id,
                    details={
                        "attempt_id": attempt_id,
                        "sha256": descriptor.sha256,
                        "parser_profile_version": parser_profile_version,
                    },
                )
            )

    def successful_parse_artifacts(
        self,
        *,
        run_id: str,
    ) -> list[ObjectDescriptor]:
        with self._sessions() as session:
            rows = session.execute(
                select(StepAttempt.artifact_manifest)
                .join(
                    JobStep,
                    (JobStep.step_id == StepAttempt.step_id)
                    & (JobStep.run_id == StepAttempt.run_id),
                )
                .where(
                    StepAttempt.run_id == run_id,
                    StepAttempt.status == "succeeded",
                    JobStep.step_key.like("document.parse_%"),
                )
                .order_by(JobStep.step_key)
            ).scalars()
            manifests = [
                ArtifactManifest.model_validate(value) for value in rows if value is not None
            ]
        return [descriptor for manifest in manifests for descriptor in manifest.artifacts]

    def persist_evidence(
        self,
        *,
        run_id: str,
        source: SourceDocument,
        parsed_results: Sequence[tuple[ObjectDescriptor, ParserResult]],
    ) -> str:
        hashes: list[str] = []
        with self._sessions.begin() as session:
            run = session.scalar(
                select(ProcessingRun).where(ProcessingRun.run_id == run_id).with_for_update()
            )
            if run is None:
                raise ValueError("processing run does not exist")
            original = session.scalar(
                select(SourceArtifact).where(
                    SourceArtifact.source_version_id == source.source_version_id,
                    SourceArtifact.artifact_kind.in_(("original", "canonical_source")),
                )
            )
            if original is None:
                raise ValueError("source has no original artifact")
            for descriptor, result in parsed_results:
                derived = session.scalar(
                    select(SourceArtifact).where(
                        SourceArtifact.object_key == descriptor.object_key,
                        SourceArtifact.artifact_kind == "parser_output",
                    )
                )
                if derived is None:
                    raise ValueError("parser output is not registered as a derived artifact")
                for fragment in result.fragments:
                    locator_payload = json.dumps(
                        fragment.locator,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    locator_hash = sha256(locator_payload.encode("utf-8")).hexdigest()
                    stable = uuid5(
                        NAMESPACE_URL,
                        (
                            f"clinical-evidence:{source.source_version_id}:"
                            f"{fragment.content_sha256}:{locator_hash}"
                        ),
                    ).hex
                    evidence_id = f"evidence-{stable}"
                    if session.get(Evidence, evidence_id) is None:
                        session.add(
                            Evidence(
                                evidence_id=evidence_id,
                                source_version_id=source.source_version_id,
                                source_artifact_id=original.artifact_id,
                                derived_artifact_id=derived.artifact_id,
                                source_sha256=source.source_sha256,
                                parser_profile_version=result.parser_profile_version,
                                evidence_type=fragment.evidence_type,
                                locator=fragment.locator,
                                locator_sha256=locator_hash,
                                content=fragment.content,
                                content_sha256=fragment.content_sha256,
                                schema_version="evidence.v1",
                            )
                        )
                    hashes.append(fragment.content_sha256)
            if not hashes:
                raise ValueError("fan-in produced no evidence")
            run.status = "evidence_ready"
            run.updated_at = _utcnow()
            session.add(
                AuditEvent(
                    audit_event_id=f"audit-{uuid4()}",
                    actor_subject="svc-document",
                    action="evidence.fan_in_committed",
                    entity_type="processing_run",
                    entity_id=run_id,
                    run_id=run_id,
                    details={
                        "evidence_count": len(hashes),
                        "parser_profile_version": DOCUMENT_PARSER_PROFILE_VERSION,
                    },
                )
            )
        return sha256("\n".join(sorted(hashes)).encode("utf-8")).hexdigest()


def build_document_step_definitions(
    *,
    media_type: str,
    input_sha256: str,
) -> list[StepDefinition]:
    branches: tuple[str, ...]
    if media_type == "application/pdf":
        branches = ("text", "tables", "images")
    elif media_type.endswith("wordprocessingml.document"):
        branches = ("text", "tables")
    elif media_type.endswith("spreadsheetml.sheet"):
        branches = ("tables",)
    elif media_type in {"text/plain", "text/markdown"}:
        branches = ("text",)
    else:
        raise ValueError(f"unsupported document media type: {media_type}")
    parse_keys = tuple(f"document.parse_{branch}" for branch in branches)
    return [
        StepDefinition(
            step_key="document.validate",
            pool=WorkerPool.DOCUMENT,
            input_sha256=input_sha256,
        ),
        *[
            StepDefinition(
                step_key=step_key,
                pool=WorkerPool.DOCUMENT,
                input_sha256=input_sha256,
                depends_on=("document.validate",),
            )
            for step_key in parse_keys
        ],
        StepDefinition(
            step_key="document.persist_evidence",
            pool=WorkerPool.DOCUMENT,
            input_sha256=input_sha256,
            depends_on=parse_keys,
        ),
    ]


def document_step_handlers(
    service: DocumentWorkerService,
) -> Mapping[str, Callable[[DocumentStepContext], StepOutcome]]:
    return {
        "document.validate": service.validate,
        "document.parse_text": lambda context: service.parse(context, branch="text"),
        "document.parse_tables": lambda context: service.parse(context, branch="tables"),
        "document.parse_images": lambda context: service.parse(context, branch="images"),
        "document.persist_evidence": service.persist_evidence,
    }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "DOCUMENT_PARSER_PROFILE_VERSION",
    "DocumentRepositoryPort",
    "DocumentWorkerService",
    "InMemoryDocumentRepository",
    "PreparedDerivedWrite",
    "SqlAlchemyDocumentRepository",
    "build_document_step_definitions",
    "document_step_handlers",
]
