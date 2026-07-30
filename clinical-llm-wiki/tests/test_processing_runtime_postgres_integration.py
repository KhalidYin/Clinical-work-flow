"""Opt-in PostgreSQL acceptance for claim/lease/checkpoint/retry semantics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import delete

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
from service.db.models import JobStep, ProcessingRun, Source, SourceVersion, StepAttempt
from service.db.session import create_database_engine, create_session_factory
from service.processing.contracts import ArtifactManifest, StepDefinition, StepOutcome
from service.processing.ledger import PostgresProcessingLedger


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="KNOWLEDGE_TEST_DATABASE_URL is required for PostgreSQL integration",
)


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _worker(pool: WorkerPool) -> ActorContext:
    return resolve_service_account_actor(
        ServiceAccountGrant(
            service_account_id=f"svc-{pool.value}",
            display_name=f"{pool.value.title()} Worker",
            worker_pool=pool,
            scopes=WORKER_POOL_PERMISSIONS[pool],
            secret_ref=f"env://P12_{pool.value.upper()}_WORKER_TOKEN",
            status=GrantStatus.ACTIVE,
        )
    )


def _curator() -> ActorContext:
    return ActorContext(
        actor_id="usr-p1e-curator",
        display_name="P1-E Curator",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({ProductRole.KNOWLEDGE_CURATOR}),
        permissions=ROLE_PERMISSIONS[ProductRole.KNOWLEDGE_CURATOR],
        identity_source=IdentitySource.LOCAL_TEST,
    )


def test_postgres_ledger_preserves_dependencies_leases_and_attempt_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setenv("KNOWLEDGE_DATABASE_URL", TEST_DATABASE_URL)
    command.upgrade(Config(ROOT / "alembic.ini"), "head")
    engine = create_database_engine(TEST_DATABASE_URL)
    sessions = create_session_factory(engine)
    ledger = PostgresProcessingLedger(sessions)
    run_id = "run-p1e-integration"

    with sessions.begin() as session:
        session.add(
            Source(
                source_id="src-p1e-integration",
                title="P1-E Integration Source",
                source_type="standard",
                owner_org="Clinical Knowledge Lab",
            )
        )
        session.flush()
        session.add(
            SourceVersion(
                source_version_id="srcv-p1e-integration",
                source_id="src-p1e-integration",
                version="1.0",
                sha256=_hash("source"),
                rights={"status": "licensed"},
                data_boundary="local_processing_only",
                status="registered",
            )
        )

    try:
        ledger.create_run(
            run_id=run_id,
            source_version_id="srcv-p1e-integration",
            requested_by_subject="usr-p1e-curator",
            steps=[
                StepDefinition(
                    step_key="parse",
                    pool=WorkerPool.DOCUMENT,
                    input_sha256=_hash("source"),
                ),
                StepDefinition(
                    step_key="extract",
                    pool=WorkerPool.ENRICHMENT,
                    input_sha256=_hash("evidence"),
                    depends_on=["parse"],
                ),
            ],
        )

        # A dependent step cannot be claimed before its prerequisite succeeds.
        assert ledger.claim_next(
            actor=_worker(WorkerPool.ENRICHMENT),
            worker_id="enrichment-1",
            supported_step_keys=frozenset({"extract"}),
            lease_seconds=60,
        ) is None
        parse = ledger.claim_next(
            actor=_worker(WorkerPool.DOCUMENT),
            worker_id="document-1",
            supported_step_keys=frozenset({"parse"}),
            lease_seconds=60,
        )
        assert parse is not None
        ledger.save_checkpoint(
            actor=_worker(WorkerPool.DOCUMENT),
            worker_id="document-1",
            attempt_id=parse.attempt_id,
            checkpoint={"page": 5},
        )
        ledger.heartbeat(
            actor=_worker(WorkerPool.DOCUMENT),
            worker_id="document-1",
            attempt_id=parse.attempt_id,
            lease_seconds=60,
        )
        ledger.complete_attempt(
            actor=_worker(WorkerPool.DOCUMENT),
            worker_id="document-1",
            attempt_id=parse.attempt_id,
            outcome=StepOutcome(
                output_sha256=_hash("evidence"),
                artifact_manifest=ArtifactManifest(artifacts=[]),
            ),
        )

        extract = ledger.claim_next(
            actor=_worker(WorkerPool.ENRICHMENT),
            worker_id="enrichment-1",
            supported_step_keys=frozenset({"extract"}),
            lease_seconds=60,
        )
        assert extract is not None
        assert extract.step_key == "extract"

        # Expired leases are never silently reused: recovery creates attempt N+1.
        with sessions.begin() as session:
            attempt = session.get(StepAttempt, extract.attempt_id)
            assert attempt is not None
            attempt.leased_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert ledger.recover_expired_leases(
            actor=_worker(WorkerPool.ENRICHMENT),
            pool=WorkerPool.ENRICHMENT,
        ) == 1
        recovered = ledger.claim_next(
            actor=_worker(WorkerPool.ENRICHMENT),
            worker_id="enrichment-2",
            supported_step_keys=frozenset({"extract"}),
            lease_seconds=60,
        )
        assert recovered is not None
        assert recovered.attempt_number == 2
        assert recovered.previous_attempt_id == extract.attempt_id
        assert recovered.checkpoint is None

        ledger.fail_attempt(
            actor=_worker(WorkerPool.ENRICHMENT),
            worker_id="enrichment-2",
            attempt_id=recovered.attempt_id,
            error_type="handler_error",
            error_message="handler_error: RuntimeError",
        )
        retry_id = ledger.retry_step(
            actor=_curator(),
            run_id=run_id,
            step_id=recovered.step_id,
        )

        with sessions.begin() as session:
            retry = session.get(StepAttempt, retry_id)
            step = session.get(JobStep, recovered.step_id)
            run = session.get(ProcessingRun, run_id)
            assert retry is not None and step is not None and run is not None
            assert retry.attempt_number == 3
            assert retry.previous_attempt_id == recovered.attempt_id
            assert step.checkpoint is None  # StepAttempt is the only checkpoint authority.
            assert step.status == "queued"
            assert run.status == "queued"

        ledger.cancel_run(actor=_curator(), run_id=run_id)
        assert ledger.claim_next(
            actor=_worker(WorkerPool.ENRICHMENT),
            worker_id="enrichment-3",
            supported_step_keys=frozenset({"extract"}),
            lease_seconds=60,
        ) is None
    finally:
        with sessions.begin() as session:
            session.execute(delete(ProcessingRun).where(ProcessingRun.run_id == run_id))
            session.execute(
                delete(SourceVersion).where(
                    SourceVersion.source_version_id == "srcv-p1e-integration"
                )
            )
            session.execute(
                delete(Source).where(Source.source_id == "src-p1e-integration")
            )
        engine.dispose()
