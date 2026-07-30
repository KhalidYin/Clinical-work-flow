"""Opt-in PostgreSQL acceptance for P2-A Source -> Evidence."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import delete, select

from service.auth import (
    ActorContext,
    GrantStatus,
    IdentitySource,
    PrincipalType,
    ProductRole,
    ROLE_PERMISSIONS,
    ServiceAccountGrant,
    WORKER_POOL_PERMISSIONS,
    WorkerPool,
    resolve_service_account_actor,
)
from service.db.models import (
    AuditEvent,
    Evidence,
    KnowledgeCandidate,
    ObjectWriteIntent,
    ProcessingRun,
    Release,
    Source,
    SourceArtifact,
    SourceVersion,
)
from service.db.session import create_database_engine, create_session_factory
from service.object_store import LocalObjectStore
from service.platform_api.repository import SqlAlchemyPlatformRepository
from service.processing.document_worker import (
    DocumentWorkerService,
    SqlAlchemyDocumentRepository,
    document_step_handlers,
)
from service.processing.ledger import PostgresProcessingLedger
from service.processing.parsers import ParserRegistry
from service.processing.worker import WorkerRuntime
from service.sources import (
    DataBoundary,
    RightsClassification,
    RightsPolicy,
    SourceRegistrationCommand,
    SourceRegistryService,
    SqlAlchemySourceRegistryRepository,
)


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="KNOWLEDGE_TEST_DATABASE_URL is required for PostgreSQL integration",
)


def _curator() -> ActorContext:
    return ActorContext(
        actor_id="usr-p2a-curator",
        display_name="P2-A Curator",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({ProductRole.KNOWLEDGE_CURATOR}),
        permissions=ROLE_PERMISSIONS[ProductRole.KNOWLEDGE_CURATOR],
        identity_source=IdentitySource.LOCAL_TEST,
    )


def _document_actor() -> ActorContext:
    return resolve_service_account_actor(
        ServiceAccountGrant(
            service_account_id="svc-p2a-document",
            display_name="P2-A Document Worker",
            worker_pool=WorkerPool.DOCUMENT,
            scopes=WORKER_POOL_PERMISSIONS[WorkerPool.DOCUMENT],
            secret_ref="env://P12_DOCUMENT_WORKER_TOKEN",
            status=GrantStatus.ACTIVE,
        )
    )


def test_postgres_source_registration_and_document_fan_in_are_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setenv("KNOWLEDGE_DATABASE_URL", TEST_DATABASE_URL)
    command.upgrade(Config(ROOT / "alembic.ini"), "head")
    engine = create_database_engine(TEST_DATABASE_URL)
    sessions = create_session_factory(engine)
    objects = LocalObjectStore(root=tmp_path / "objects")
    ledger = PostgresProcessingLedger(sessions)
    source_repository = SqlAlchemySourceRegistryRepository(sessions)
    registry = SourceRegistryService(
        repository=source_repository,
        object_store=objects,
        ledger=ledger,
    )
    content = b"# Safety population\n\nAll treated subjects are included."
    command_model = SourceRegistrationCommand(
        source_id="src-p2a-integration",
        title="P2-A Integration Markdown",
        source_type="test_standard",
        version="1.0",
        rights=RightsPolicy(
            classification=RightsClassification.INTERNAL,
            storage_allowed=True,
        ),
        data_boundary=DataBoundary.LOCAL_PROCESSING_ONLY,
        media_type="text/markdown",
        expected_sha256=sha256(content).hexdigest(),
        idempotency_key="p2a-postgres-source-v1",
    )

    try:
        receipt = registry.register_and_start(
            actor=_curator(),
            command=command_model,
            content=content,
        )
        assert (
            registry.register_and_start(
                actor=_curator(),
                command=command_model,
                content=content,
            )
            == receipt
        )

        document_repository = SqlAlchemyDocumentRepository(sessions)
        document_service = DocumentWorkerService(
            repository=document_repository,
            object_store=objects,
            parsers=ParserRegistry.default(),
            actor_id="svc-p2a-document",
        )
        runtime = WorkerRuntime(
            ledger=ledger,
            actor=_document_actor(),
            worker_id="document-p2a-integration",
            handlers=document_step_handlers(document_service),
            pool=WorkerPool.DOCUMENT,
            lease_seconds=60,
        )
        executed = 0
        while runtime.run_once():
            executed += 1
            assert executed <= 3
        assert executed == 3

        with sessions() as session:
            run = session.get(ProcessingRun, receipt.run_id)
            artifacts = list(
                session.scalars(
                    select(SourceArtifact).where(
                        SourceArtifact.source_version_id == receipt.source_version_id
                    )
                )
            )
            evidence = list(
                session.scalars(
                    select(Evidence).where(Evidence.source_version_id == receipt.source_version_id)
                )
            )
            intents = list(
                session.scalars(
                    select(ObjectWriteIntent).where(
                        ObjectWriteIntent.source_version_id == receipt.source_version_id
                    )
                )
            )
            assert run is not None
            assert run.status == "evidence_ready"
            assert {artifact.artifact_kind for artifact in artifacts} == {
                "original",
                "parser_output",
            }
            assert len(evidence) == 1
            assert evidence[0].source_sha256 == command_model.expected_sha256
            assert evidence[0].derived_artifact_id
            assert {intent.status for intent in intents} == {"committed"}
            assert session.scalar(select(KnowledgeCandidate).limit(1)) is None
            assert session.scalar(select(Release).limit(1)) is None
        listed_sources, warnings = SqlAlchemyPlatformRepository(sessions).list_sources()
        listed = next(item for item in listed_sources if item.source_id == command_model.source_id)
        assert listed.media_type == "Markdown"
        assert warnings == []
    finally:
        with sessions.begin() as session:
            run_ids = list(
                session.scalars(
                    select(ProcessingRun.run_id).where(
                        ProcessingRun.source_version_id.in_(
                            select(SourceVersion.source_version_id).where(
                                SourceVersion.source_id == "src-p2a-integration"
                            )
                        )
                    )
                )
            )
            session.execute(
                delete(AuditEvent).where(
                    (AuditEvent.entity_id.in_(run_ids))
                    | (AuditEvent.actor_subject.in_(["usr-p2a-curator", "svc-p2a-document"]))
                )
            )
            session.execute(
                delete(Evidence).where(
                    Evidence.source_version_id.in_(
                        select(SourceVersion.source_version_id).where(
                            SourceVersion.source_id == "src-p2a-integration"
                        )
                    )
                )
            )
            session.execute(
                delete(ProcessingRun).where(
                    ProcessingRun.source_version_id.in_(
                        select(SourceVersion.source_version_id).where(
                            SourceVersion.source_id == "src-p2a-integration"
                        )
                    )
                )
            )
            session.execute(
                delete(SourceArtifact).where(
                    SourceArtifact.source_version_id.in_(
                        select(SourceVersion.source_version_id).where(
                            SourceVersion.source_id == "src-p2a-integration"
                        )
                    )
                )
            )
            session.execute(
                delete(ObjectWriteIntent).where(
                    ObjectWriteIntent.source_id == "src-p2a-integration"
                )
            )
            session.execute(
                delete(SourceVersion).where(SourceVersion.source_id == "src-p2a-integration")
            )
            session.execute(delete(Source).where(Source.source_id == "src-p2a-integration"))
        engine.dispose()
