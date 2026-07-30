"""Opt-in real PostgreSQL acceptance test for the P1-D read boundary."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete

from service.auth import IdentityAssertion, LocalIdentityProvider
from service.db.models import (
    PlatformUser,
    Release,
    RoleBinding,
    Source,
    SourceArtifact,
    SourceVersion,
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
                    identity_source="local_test",
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

    assertion = IdentityAssertion(
        identity_source="local_test",
        issuer="local://p1d-integration",
        subject="p1d-admin",
        display_name="P1-D Admin",
        email="p1d-admin@example.test",
        claims_sha256=sha256(b"p1d-admin").hexdigest(),
    )
    provider = LocalIdentityProvider(
        environment="test",
        token_assertions={"p1d-integration-token": assertion},
    )
    client = TestClient(
        create_platform_app(
            PlatformApiServices(
                identity_provider=provider,
                repository=SqlAlchemyPlatformRepository(session_factory),
                organization_name="Clinical Knowledge Lab",
            )
        )
    )
    headers = {"Authorization": "Bearer p1d-integration-token"}

    try:
        session = client.get("/api/prerelease/v1/session", headers=headers)
        sources = client.get("/api/prerelease/v1/sources", headers=headers)
        users = client.get("/api/prerelease/v1/admin/users", headers=headers)
        release = client.get("/api/prerelease/v1/releases/current", headers=headers)

        assert session.status_code == sources.status_code == users.status_code == 200
        assert release.status_code == 200
        assert session.json()["data"]["roles"] == ["platform_admin"]
        assert any(
            item["sourceId"] == "src-p1d-integration" for item in sources.json()["data"]["items"]
        )
        assert any(
            item["userId"] == "usr-p1d-integration" for item in users.json()["data"]["items"]
        )
        assert release.json()["data"]["releaseId"] == "rel-p1d-integration"
    finally:
        with session_factory.begin() as database_session:
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
