"""Opt-in PostgreSQL acceptance for persistent ICH E9 POC scope checks."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest

from scripts.ich_e9_poc import _poc_scope_counts
from service.db.models import (
    KnowledgeCandidate,
    KnowledgeRevision,
    KnowledgeUnit,
    ProcessingRun,
    Release,
    ReleaseItem,
    Source,
    SourceVersion,
)
from service.db.session import create_database_engine, create_session_factory


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="KNOWLEDGE_TEST_DATABASE_URL is required for PostgreSQL integration",
)


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def test_poc_scope_counts_ignore_unrelated_candidates_and_releases() -> None:
    assert TEST_DATABASE_URL is not None
    os.environ["KNOWLEDGE_DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(Config(ROOT / "alembic.ini"), "head")
    engine = create_database_engine(TEST_DATABASE_URL)
    sessions = create_session_factory(engine)
    try:
        with sessions.begin() as session:
            session.add_all(
                (
                    Source(
                        source_id="src-e9-target",
                        title="E9 target",
                        source_type="ich_guideline",
                    ),
                    Source(
                        source_id="src-unrelated",
                        title="Unrelated governed source",
                        source_type="test_fixture",
                    ),
                )
            )
            session.flush()
            session.add_all(
                (
                    SourceVersion(
                        source_version_id="srcv-e9-target",
                        source_id="src-e9-target",
                        version="1",
                        sha256=_hash("e9-target"),
                        rights={"classification": "licensed", "storage_allowed": True},
                        data_boundary="local_processing_only",
                        status="parsed",
                    ),
                    SourceVersion(
                        source_version_id="srcv-unrelated",
                        source_id="src-unrelated",
                        version="1",
                        sha256=_hash("unrelated"),
                        rights={"classification": "internal", "storage_allowed": True},
                        data_boundary="local_processing_only",
                        status="parsed",
                    ),
                )
            )
            session.flush()
            session.add(
                ProcessingRun(
                    run_id="run-unrelated",
                    source_version_id="srcv-unrelated",
                    status="approved",
                    requested_by_subject="usr-unrelated",
                )
            )
            session.flush()
            session.add(
                KnowledgeCandidate(
                    candidate_id="candidate-unrelated",
                    candidate_group_id="candidate-group-unrelated",
                    run_id="run-unrelated",
                    revision_number=1,
                    status="author_confirmed",
                    knowledge_type="test_fact",
                    claim="Unrelated fact",
                    scope={"fixture": "unrelated"},
                    applicability=None,
                    conditions=[],
                    exceptions=[],
                    advisory_signals=[],
                    content_sha256=_hash("unrelated-revision"),
                    author_actor_id="usr-unrelated",
                )
            )
            session.add(
                KnowledgeUnit(
                    knowledge_unit_id="unit-unrelated",
                    stable_key="p17.unrelated",
                    knowledge_type="test_fact",
                )
            )
            session.flush()
            session.add(
                KnowledgeRevision(
                    knowledge_revision_id="revision-unrelated",
                    knowledge_unit_id="unit-unrelated",
                    candidate_id="candidate-unrelated",
                    revision_number=1,
                    status="released",
                    claim="Unrelated fact",
                    scope={"fixture": "unrelated"},
                    applicability=None,
                    conditions=[],
                    exceptions=[],
                    content_sha256=_hash("unrelated-revision"),
                    author_actor_id="usr-unrelated",
                )
            )
            session.add(
                Release(
                    release_id="release-unrelated",
                    version="unrelated.1",
                    status="released",
                    manifest_object_key="p17/unrelated/manifest.json",
                    manifest_sha256=_hash("unrelated-manifest"),
                    db_schema_revision="20260816_0012",
                    knowledge_contract_version="p17-v1",
                    parser_profile_version="parser-p17-v1",
                    model_profile_version="replay-v1",
                    prompt_profile_version="prompt-v1",
                    index_manifest_version="index-v1",
                    release_manager_subject="usr-unrelated",
                )
            )
            session.flush()
            session.add(
                ReleaseItem(
                    release_id="release-unrelated",
                    knowledge_revision_id="revision-unrelated",
                    content_sha256=_hash("unrelated-revision"),
                )
            )

        with sessions() as session:
            assert _poc_scope_counts(session, "srcv-e9-target") == (0, 0)
            assert _poc_scope_counts(session, "srcv-unrelated") == (1, 1)
    finally:
        engine.dispose()
