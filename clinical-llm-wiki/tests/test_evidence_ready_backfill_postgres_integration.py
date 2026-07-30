"""Opt-in PostgreSQL acceptance test for the P2-B1 evidence-ready backfill."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest

from service.db.models import (
    Evidence,
    KnowledgeCandidate,
    ProcessingRun,
    Source,
    SourceArtifact,
    SourceVersion,
)
from service.db.session import create_database_engine, create_session_factory
from service.maintenance.evidence_ready import run_from_environment


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="KNOWLEDGE_TEST_DATABASE_URL is required for PostgreSQL integration",
)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _seed_run(
    session,
    *,
    suffix: str,
    status: str = "author_confirmation_required",
    with_evidence: bool,
    with_candidate: bool,
) -> str:
    source_id = f"src-backfill-{suffix}"
    source_version_id = f"srcv-backfill-{suffix}"
    run_id = f"run-backfill-{suffix}"
    session.add(
        Source(
            source_id=source_id,
            title=f"Backfill fixture {suffix}",
            source_type="test_fixture",
        )
    )
    session.flush()
    source_sha256 = _sha256(f"source-{suffix}")
    session.add(
        SourceVersion(
            source_version_id=source_version_id,
            source_id=source_id,
            version="1",
            sha256=source_sha256,
            rights={"classification": "synthetic", "storage_allowed": True},
            data_boundary="local_processing_only",
            status="parsed",
        )
    )
    session.flush()
    session.add(
        ProcessingRun(
            run_id=run_id,
            source_version_id=source_version_id,
            status=status,
            requested_by_subject="user-backfill-author",
        )
    )
    session.flush()

    if with_evidence:
        original_id = f"artifact-original-{suffix}"
        derived_id = f"artifact-derived-{suffix}"
        session.add(
            SourceArtifact(
                artifact_id=original_id,
                source_version_id=source_version_id,
                artifact_kind="original",
                parent_artifact_id=None,
                object_key=f"sources/{source_id}/original-{suffix}.md",
                sha256=source_sha256,
                media_type="text/markdown",
                size_bytes=10,
                parser_profile_version=None,
                status="available",
            )
        )
        session.flush()
        derived_sha256 = _sha256(f"derived-{suffix}")
        session.add(
            SourceArtifact(
                artifact_id=derived_id,
                source_version_id=source_version_id,
                artifact_kind="parser_output",
                parent_artifact_id=original_id,
                object_key=f"sources/{source_id}/derived-{suffix}.json",
                sha256=derived_sha256,
                media_type="application/json",
                size_bytes=20,
                parser_profile_version="test-parser-v1",
                status="available",
            )
        )
        session.flush()
        content = f"Evidence content {suffix}"
        locator = {"kind": "paragraph", "index": 1}
        session.add(
            Evidence(
                evidence_id=f"evidence-backfill-{suffix}",
                source_version_id=source_version_id,
                source_artifact_id=original_id,
                derived_artifact_id=derived_id,
                source_sha256=source_sha256,
                parser_profile_version="test-parser-v1",
                evidence_type="paragraph",
                locator=locator,
                locator_sha256=_sha256(str(locator)),
                content=content,
                content_sha256=_sha256(content),
                schema_version="1",
            )
        )
        session.flush()

    if with_candidate:
        session.add(
            KnowledgeCandidate(
                candidate_id=f"candidate-backfill-{suffix}",
                run_id=run_id,
                revision_number=1,
                status="author_confirmation_required",
                knowledge_type="definition",
                claim=f"Candidate claim {suffix}",
                scope={"domain": "test"},
                applicability=None,
                conditions=[],
                exceptions=[],
                confidence=None,
                author_subject="user-backfill-author",
            )
        )
        session.flush()
    return run_id


def test_backfill_updates_only_evidence_without_candidate_and_replays_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setenv("KNOWLEDGE_DATABASE_URL", TEST_DATABASE_URL)
    config = Config(ROOT / "alembic.ini")
    command.upgrade(config, "head")
    engine = create_database_engine(TEST_DATABASE_URL)
    sessions = create_session_factory(engine)

    try:
        with sessions.begin() as session:
            eligible = _seed_run(
                session,
                suffix="001",
                with_evidence=True,
                with_candidate=False,
            )
            no_evidence = _seed_run(
                session,
                suffix="002",
                with_evidence=False,
                with_candidate=False,
            )
            has_candidate = _seed_run(
                session,
                suffix="003",
                with_evidence=True,
                with_candidate=True,
            )
            already_ready = _seed_run(
                session,
                suffix="004",
                status="evidence_ready",
                with_evidence=True,
                with_candidate=False,
            )

        cursor: str | None = None
        processed = 0
        while True:
            count, cursor = run_from_environment(1, cursor)
            processed += count
            if cursor is None:
                break

        assert processed == 1
        with sessions() as session:
            assert session.get(ProcessingRun, eligible).status == "evidence_ready"
            assert session.get(ProcessingRun, no_evidence).status == (
                "author_confirmation_required"
            )
            assert session.get(ProcessingRun, has_candidate).status == (
                "author_confirmation_required"
            )
            assert session.get(ProcessingRun, already_ready).status == "evidence_ready"

        assert run_from_environment(100, None) == (0, None)
    finally:
        engine.dispose()
