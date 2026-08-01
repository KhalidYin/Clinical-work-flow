"""Opt-in real PostgreSQL acceptance test for the P1-D read boundary."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, func, select

from service.auth.password_sessions import (
    Argon2idPasswordHasher,
    PasswordSessionService,
    SqlAlchemyPasswordSessionRepository,
)
from service.db.models import (
    AuditEvent,
    CandidateRelationProposal,
    Evidence,
    KnowledgeCandidate,
    KnowledgeRevision,
    KnowledgeUnit,
    ModelInvocation,
    ModelProfile,
    PlatformUser,
    ProcessingRun,
    Release,
    ReleaseItem,
    RelationProposalEvidence,
    RoleBinding,
    Source,
    SourceArtifact,
    SourceVersion,
    UserCredential,
)
from service.db.session import create_database_engine, create_session_factory
from service.platform_api.app import PlatformApiServices, create_platform_app
from service.platform_api.repository import SqlAlchemyPlatformRepository


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="KNOWLEDGE_TEST_DATABASE_URL is required for PostgreSQL integration",
)


def test_model_profile_registry_is_immutable_audited_and_does_not_invoke_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setenv("KNOWLEDGE_DATABASE_URL", TEST_DATABASE_URL)
    command.upgrade(Config(ROOT / "alembic.ini"), "head")
    engine = create_database_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)
    profile_id = "integration-model-config"
    version = "1.0.0"

    with session_factory.begin() as session:
        session.execute(
            delete(AuditEvent).where(
                AuditEvent.entity_type == "model_profile",
                AuditEvent.entity_id == f"{profile_id}@{version}",
            )
        )
        session.execute(
            delete(ModelProfile).where(
                ModelProfile.profile_id == profile_id,
                ModelProfile.version == version,
            )
        )
        invocation_count_before = session.scalar(
            select(func.count()).select_from(ModelInvocation)
        )

    repository = SqlAlchemyPlatformRepository(session_factory)
    created, was_created = repository.register_model_profile(
        profile_id=profile_id,
        version=version,
        provider="deepseek",
        model="deepseek-v4-flash",
        deployment_class="external_api",
        secret_ref="env://KNOWLEDGE_MODEL_API_KEY",
        endpoint_ref="env://KNOWLEDGE_MODEL_ENDPOINT",
        allowed_data_boundaries=["external_allowed"],
        capabilities=["structured_generation"],
        timeout_seconds=60,
        max_output_tokens=4096,
        cost_policy={"maxCostUsd": "0.05"},
        actor_id="usr-p2b3-admin",
        correlation_id="cfg-integration-001",
    )
    repeated, repeated_created = repository.register_model_profile(
        profile_id=profile_id,
        version=version,
        provider="deepseek",
        model="deepseek-v4-flash",
        deployment_class="external_api",
        secret_ref="env://KNOWLEDGE_MODEL_API_KEY",
        endpoint_ref="env://KNOWLEDGE_MODEL_ENDPOINT",
        allowed_data_boundaries=["external_allowed"],
        capabilities=["structured_generation"],
        timeout_seconds=60,
        max_output_tokens=4096,
        cost_policy={"maxCostUsd": "0.05"},
        actor_id="usr-p2b3-admin",
        correlation_id="cfg-integration-repeat",
    )

    assert was_created is True
    assert repeated_created is False
    assert repeated == created
    assert created.secret_ref == "env://KNOWLEDGE_MODEL_API_KEY"
    with session_factory() as session:
        invocation_count_after = session.scalar(
            select(func.count()).select_from(ModelInvocation)
        )
        events = list(
            session.scalars(
                select(AuditEvent).where(
                    AuditEvent.entity_type == "model_profile",
                    AuditEvent.entity_id == f"{profile_id}@{version}",
                )
            )
        )
    assert invocation_count_after == invocation_count_before
    assert len(events) == 1
    assert events[0].details["result"] == "registered_not_verified"
    assert "secret_ref" not in events[0].details

    with session_factory.begin() as session:
        session.execute(
            delete(AuditEvent).where(
                AuditEvent.entity_type == "model_profile",
                AuditEvent.entity_id == f"{profile_id}@{version}",
            )
        )
        session.execute(
            delete(ModelProfile).where(
                ModelProfile.profile_id == profile_id,
                ModelProfile.version == version,
            )
        )
    engine.dispose()


def test_real_postgres_repository_serves_authorized_read_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setenv("KNOWLEDGE_DATABASE_URL", TEST_DATABASE_URL)
    command.upgrade(Config(ROOT / "alembic.ini"), "head")
    engine = create_database_engine(TEST_DATABASE_URL)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 7, 30, 3, 30, tzinfo=timezone.utc)

    with session_factory.begin() as session:
        session.add_all(
            [
                PlatformUser(
                    user_id="usr-p1d-integration",
                    identity_source="local_password",
                    issuer="local://p1d-integration",
                    subject="p1d-admin",
                    display_name="P1-D Admin",
                    email="p1d-admin@example.test",
                    status="active",
                    last_authenticated_at=now,
                ),
                Source(
                    source_id="src-p1d-integration",
                    title="P1-D Integration Source",
                    source_type="standard",
                    owner_org="Clinical Knowledge Lab",
                ),
                Release(
                    release_id="rel-p1d-integration",
                    version="2026.07-p1d-integration",
                    status="released",
                    manifest_object_key="release/p1d/manifest.json",
                    manifest_sha256="d" * 64,
                    db_schema_revision="20260730_0002",
                    knowledge_contract_version="prerelease-v1",
                    parser_profile_version="parser-none",
                    model_profile_version="model-none",
                    prompt_profile_version="prompt-none",
                    index_manifest_version="idx-p1d-integration",
                    release_manager_subject="usr-release-manager",
                    published_at=now,
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                RoleBinding(
                    user_id="usr-p1d-integration",
                    role="platform_admin",
                    granted_by_actor_id="bootstrap-p1d-integration",
                ),
                UserCredential(
                    user_id="usr-p1d-integration",
                    username_normalized="p1d-admin",
                    password_hash=Argon2idPasswordHasher().hash(
                        "P1-D integration password 2026!"
                    ),
                    must_change_password=False,
                ),
                SourceVersion(
                    source_version_id="srcv-p1d-integration",
                    source_id="src-p1d-integration",
                    version="1.0",
                    sha256="a" * 64,
                    rights={"status": "licensed"},
                    data_boundary="local_processing_only",
                    status="registered",
                ),
            ]
        )
        session.flush()
        session.add(
            SourceArtifact(
                artifact_id="artifact-p1d-integration",
                source_version_id="srcv-p1d-integration",
                artifact_kind="canonical_source",
                object_key="sources/p1d/source.pdf",
                sha256="b" * 64,
                media_type="application/pdf",
                size_bytes=128,
            )
        )
        session.add(
            SourceArtifact(
                artifact_id="artifact-p1d-integration-derived",
                source_version_id="srcv-p1d-integration",
                artifact_kind="parser_output",
                parent_artifact_id="artifact-p1d-integration",
                object_key="sources/p1d/derived.json",
                sha256="c" * 64,
                media_type="application/json",
                size_bytes=96,
                parser_profile_version="parser-integration",
            )
        )
        session.add_all(
            [
                ProcessingRun(
                    run_id="run-p1d-integration",
                    source_version_id="srcv-p1d-integration",
                    status="approved",
                    requested_by_subject="usr-p1d-integration",
                ),
                KnowledgeUnit(
                    knowledge_unit_id="ku-p1d-source",
                    stable_key="integration.sdtm.aeseq",
                    knowledge_type="variable_definition",
                ),
                KnowledgeUnit(
                    knowledge_unit_id="ku-p1d-target",
                    stable_key="integration.sdtm.ae",
                    knowledge_type="domain_definition",
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                Evidence(
                    evidence_id="evidence-p1d-integration",
                    source_version_id="srcv-p1d-integration",
                    source_artifact_id="artifact-p1d-integration",
                    derived_artifact_id="artifact-p1d-integration-derived",
                    source_sha256="a" * 64,
                    parser_profile_version="parser-integration",
                    evidence_type="paragraph",
                    locator={"page": 35, "section": "AE"},
                    locator_sha256="e" * 64,
                    content="AESEQ identifies a record within SDTM AE.",
                    content_sha256="f" * 64,
                    schema_version="evidence.v1",
                ),
                KnowledgeCandidate(
                    candidate_id="cand-p1d-integration",
                    candidate_group_id="candgrp-p1d-integration",
                    run_id="run-p1d-integration",
                    revision_number=1,
                    status="author_confirmed",
                    knowledge_type="variable_definition",
                    claim="AESEQ identifies a record within SDTM AE.",
                    scope={"standard": "SDTM", "domain": "AE"},
                    applicability={"version": "3.4"},
                    conditions=[],
                    exceptions=[],
                    content_sha256="f" * 64,
                    author_actor_id="usr-p1d-integration",
                ),
                AuditEvent(
                    audit_event_id="audit-p1d-integration",
                    actor_subject="usr-p1d-integration",
                    action="knowledge_revision.approved",
                    entity_type="knowledge_revision",
                    entity_id="krev-p1d-integration",
                    run_id="run-p1d-integration",
                    details={
                        "revision_number": 1,
                        "input_sha256": "f" * 64,
                        "output_sha256": "f" * 64,
                        "result": "approved",
                        "correlation_id": "integration-review-001",
                        "rationale": "must not leave the audit projection",
                    },
                ),
            ]
        )
        session.flush()
        session.add(
            KnowledgeRevision(
                knowledge_revision_id="krev-p1d-integration",
                knowledge_unit_id="ku-p1d-source",
                candidate_id="cand-p1d-integration",
                revision_number=1,
                status="approved",
                claim="AESEQ identifies a record within SDTM AE.",
                scope={"standard": "SDTM", "domain": "AE"},
                applicability={"version": "3.4"},
                conditions=[],
                exceptions=[],
                content_sha256="f" * 64,
                author_actor_id="usr-p1d-integration",
                approved_at=now,
            )
        )
        session.flush()
        session.add_all(
            [
                CandidateRelationProposal(
                    proposal_id="proposal-p1d-integration",
                    candidate_id="cand-p1d-integration",
                    relation_type="applies_to",
                    target_knowledge_unit_id="ku-p1d-target",
                    status="accepted",
                ),
                ReleaseItem(
                    release_id="rel-p1d-integration",
                    knowledge_revision_id="krev-p1d-integration",
                    content_sha256="f" * 64,
                ),
            ]
        )
        session.flush()
        session.add(
            RelationProposalEvidence(
                proposal_id="proposal-p1d-integration",
                evidence_id="evidence-p1d-integration",
            )
        )

    password_sessions = PasswordSessionService(
        repository=SqlAlchemyPasswordSessionRepository(session_factory),
        hasher=Argon2idPasswordHasher(),
    )
    client = TestClient(
        create_platform_app(
            PlatformApiServices(
                repository=SqlAlchemyPlatformRepository(session_factory),
                password_sessions=password_sessions,
                organization_name="Clinical Knowledge Lab",
                allowed_browser_origins=frozenset({"http://testserver"}),
                secure_session_cookie=False,
            )
        )
    )
    login = client.post(
        "/api/prerelease/v1/auth/login",
        headers={"Origin": "http://testserver", "X-CSRF-Protection": "1"},
        json={
            "username": "p1d-admin",
            "password": "P1-D integration password 2026!",
        },
    )
    assert login.status_code == 200

    try:
        session = client.get("/api/prerelease/v1/session")
        sources = client.get("/api/prerelease/v1/sources")
        users = client.get("/api/prerelease/v1/admin/users")
        release = client.get("/api/prerelease/v1/releases/current")
        relations = client.get(
            "/api/prerelease/v1/relations/query",
            params={"node_id": "ku-p1d-source", "depth": 1},
        )
        audit = client.get("/api/prerelease/v1/audit-events")

        assert session.status_code == sources.status_code == users.status_code == 200
        assert release.status_code == relations.status_code == audit.status_code == 200
        assert session.json()["data"]["roles"] == ["platform_admin"]
        assert any(
            item["sourceId"] == "src-p1d-integration" for item in sources.json()["data"]["items"]
        )
        assert any(
            item["userId"] == "usr-p1d-integration" for item in users.json()["data"]["items"]
        )
        assert release.json()["data"]["releaseId"] == "rel-p1d-integration"
        relation_data = relations.json()["data"]
        assert relation_data["nodes"][0]["releaseIds"] == ["rel-p1d-integration"]
        assert relation_data["edges"][0]["evidence"][0]["evidenceId"] == (
            "evidence-p1d-integration"
        )
        audit_event = next(
            item
            for item in audit.json()["data"]["items"]
            if item["auditEventId"] == "audit-p1d-integration"
        )
        assert audit_event["correlationId"] == "integration-review-001"
        assert "details" not in audit_event
        assert "rationale" not in audit_event
    finally:
        with session_factory.begin() as database_session:
            database_session.execute(
                delete(RelationProposalEvidence).where(
                    RelationProposalEvidence.proposal_id == "proposal-p1d-integration"
                )
            )
            database_session.execute(
                delete(CandidateRelationProposal).where(
                    CandidateRelationProposal.proposal_id == "proposal-p1d-integration"
                )
            )
            database_session.execute(
                delete(ReleaseItem).where(
                    ReleaseItem.knowledge_revision_id == "krev-p1d-integration"
                )
            )
            database_session.execute(
                delete(KnowledgeRevision).where(
                    KnowledgeRevision.knowledge_revision_id == "krev-p1d-integration"
                )
            )
            database_session.execute(
                delete(AuditEvent).where(
                    AuditEvent.audit_event_id == "audit-p1d-integration"
                )
            )
            database_session.execute(
                delete(KnowledgeCandidate).where(
                    KnowledgeCandidate.candidate_id == "cand-p1d-integration"
                )
            )
            database_session.execute(
                delete(Evidence).where(
                    Evidence.evidence_id == "evidence-p1d-integration"
                )
            )
            database_session.execute(
                delete(KnowledgeUnit).where(
                    KnowledgeUnit.knowledge_unit_id.in_(
                        ("ku-p1d-source", "ku-p1d-target")
                    )
                )
            )
            database_session.execute(
                delete(ProcessingRun).where(
                    ProcessingRun.run_id == "run-p1d-integration"
                )
            )
            database_session.execute(
                delete(SourceArtifact).where(
                    SourceArtifact.artifact_id == "artifact-p1d-integration-derived"
                )
            )
            database_session.execute(
                delete(SourceArtifact).where(
                    SourceArtifact.artifact_id == "artifact-p1d-integration"
                )
            )
            database_session.execute(
                delete(SourceVersion).where(
                    SourceVersion.source_version_id == "srcv-p1d-integration"
                )
            )
            database_session.execute(
                delete(Source).where(Source.source_id == "src-p1d-integration")
            )
            database_session.execute(
                delete(RoleBinding).where(RoleBinding.user_id == "usr-p1d-integration")
            )
            database_session.execute(
                delete(PlatformUser).where(PlatformUser.user_id == "usr-p1d-integration")
            )
            database_session.execute(
                delete(Release).where(Release.release_id == "rel-p1d-integration")
            )
        engine.dispose()
