"""Run the complete ICH E9 retrieval baseline in an ephemeral PostgreSQL container."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from typing import Iterator
from uuid import NAMESPACE_URL, uuid5

from alembic import command as alembic_command
from alembic.config import Config
import fitz
import psycopg
from sqlalchemy import func, select

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
    ChunkProjectionFinding,
    Evidence,
    KnowledgeCandidate,
    ProcessingRun,
    Release,
    RetrievalChunk,
)
from service.db.session import create_database_engine, create_session_factory
from service.evaluation import (
    EvaluationOperationsService,
    EvaluationStartCommand,
    GoldSuite,
    RegisteredEvaluationSuite,
    SqlAlchemyEvaluationReadRepository,
)
from service.object_store import LocalObjectStore
from service.processing.document_worker import (
    DocumentWorkerService,
    ICH_E9_CHUNK_PROFILE_V1,
    SqlAlchemyDocumentRepository,
    document_step_handlers,
)
from service.processing.ledger import PostgresProcessingLedger
from service.processing.parsers import ParserRegistry
from service.processing.worker import WorkerRuntime
from service.retrieval import ReleaseCandidateScope, RetrievalService
from service.retrieval.postgres import PostgresCandidateSearchRepository
from service.sources import (
    DataBoundary,
    RightsClassification,
    RightsPolicy,
    SourceRegistrationCommand,
    SourceRegistryService,
    SqlAlchemySourceRegistryRepository,
)

from .ich_e9_asset import (
    DEFAULT_DESTINATION,
    DEFAULT_RECEIPT,
    ICH_E9_MEDIA_TYPE,
    ICH_E9_SHA256,
    download_ich_e9,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLD_SUITE = ROOT / "service/evaluation/suites/ich-e9-retrieval-gold-v1.json"
DEFAULT_REPORT = ROOT / "reports/p17/ich-e9-retrieval-baseline.json"
SOURCE_ID = "src-ich-e9"
SOURCE_VERSION = "1998-02-05"
REGISTRATION_ACTOR_ID = "usr-p17-e9-curator"
REGISTRATION_IDEMPOTENCY_KEY = "p17-ich-e9-1998-v1"
TEMPORARY_POSTGRES_IMAGE = "pgvector/pgvector:0.8.1-pg17"
POC_VERSION = "p17-ich-e9-retrieval-poc-v1"


def expected_source_version_id() -> str:
    stable = uuid5(
        NAMESPACE_URL,
        f"clinical-source:{REGISTRATION_ACTOR_ID}:{REGISTRATION_IDEMPOTENCY_KEY}",
    ).hex
    return f"srcv-{stable}"


def run_poc(
    *,
    database_url: str,
    asset_path: Path,
    gold_suite_path: Path,
    object_store_root: Path,
    database_retention: str,
) -> dict[str, object]:
    asset = download_ich_e9(
        destination=asset_path,
        receipt_path=ROOT / DEFAULT_RECEIPT,
    )
    suite = GoldSuite.model_validate_json(gold_suite_path.read_text(encoding="utf-8"))
    if suite.source_sha256 != asset.sha256:
        raise RuntimeError("GoldSuite source hash does not match the validated E9 asset")
    if suite.source_version_id != expected_source_version_id():
        raise RuntimeError("GoldSuite source version does not match registration identity")
    if (
        suite.chunk_profile_id != ICH_E9_CHUNK_PROFILE_V1.chunk_profile_id
        or suite.chunk_profile_version != ICH_E9_CHUNK_PROFILE_V1.version
    ):
        raise RuntimeError("GoldSuite chunk profile does not match the POC profile")

    previous_database_url = os.environ.get("KNOWLEDGE_DATABASE_URL")
    os.environ["KNOWLEDGE_DATABASE_URL"] = database_url
    try:
        alembic_command.upgrade(Config(ROOT / "alembic.ini"), "head")
    finally:
        if previous_database_url is None:
            os.environ.pop("KNOWLEDGE_DATABASE_URL", None)
        else:
            os.environ["KNOWLEDGE_DATABASE_URL"] = previous_database_url

    engine = create_database_engine(database_url)
    sessions = create_session_factory(engine)
    objects = LocalObjectStore(root=object_store_root)
    ledger = PostgresProcessingLedger(sessions)
    registry = SourceRegistryService(
        repository=SqlAlchemySourceRegistryRepository(sessions),
        object_store=objects,
        ledger=ledger,
    )
    content = asset_path.read_bytes()
    source_command = SourceRegistrationCommand(
        source_id=SOURCE_ID,
        title="ICH E9 Statistical Principles for Clinical Trials",
        source_type="ich_guideline",
        version=SOURCE_VERSION,
        rights=RightsPolicy(
            classification=RightsClassification.LICENSED,
            storage_allowed=True,
            citation_required=True,
        ),
        data_boundary=DataBoundary.LOCAL_PROCESSING_ONLY,
        media_type=ICH_E9_MEDIA_TYPE,
        expected_sha256=ICH_E9_SHA256,
        idempotency_key=REGISTRATION_IDEMPOTENCY_KEY,
    )
    try:
        receipt = registry.register_and_start(
            actor=_curator(),
            command=source_command,
            content=content,
        )
        repeated = registry.register_and_start(
            actor=_curator(),
            command=source_command,
            content=content,
        )
        if repeated != receipt:
            raise RuntimeError("E9 source registration replay drifted")

        document_repository = SqlAlchemyDocumentRepository(sessions)
        document_service = DocumentWorkerService(
            repository=document_repository,
            object_store=objects,
            parsers=ParserRegistry.default(),
            actor_id="svc-p17-e9-document",
        )
        runtime = WorkerRuntime(
            ledger=ledger,
            actor=_document_actor(),
            worker_id="document-p17-e9-poc",
            handlers=document_step_handlers(document_service),
            pool=WorkerPool.DOCUMENT,
            lease_seconds=180,
            target_run_id=receipt.run_id,
        )
        display_errors = bool(fitz.TOOLS.mupdf_display_errors())
        try:
            fitz.TOOLS.mupdf_display_errors(False)
            executed_steps = 0
            while runtime.run_once():
                executed_steps += 1
                if executed_steps > 6:
                    raise RuntimeError("E9 Document Worker exceeded the frozen six-step DAG")
        finally:
            fitz.TOOLS.mupdf_display_errors(display_errors)
        if executed_steps != 6:
            raise RuntimeError(
                f"E9 Document Worker executed {executed_steps} of six expected steps"
            )

        projection_sha256 = document_repository.materialize_chunks(
            run_id=receipt.run_id,
            profile=ICH_E9_CHUNK_PROFILE_V1,
        )
        if (
            document_repository.materialize_chunks(
                run_id=receipt.run_id,
                profile=ICH_E9_CHUNK_PROFILE_V1,
            )
            != projection_sha256
        ):
            raise RuntimeError("E9 Chunk projection replay drifted")

        scope = ReleaseCandidateScope(
            sandbox_id="sandbox-ich-e9-poc-v1",
            source_version_ids=(receipt.source_version_id,),
            chunk_profile_id=ICH_E9_CHUNK_PROFILE_V1.chunk_profile_id,
        )
        retrieval = RetrievalService(
            repository=PostgresCandidateSearchRepository(sessions)
        )
        evaluation_repository = SqlAlchemyEvaluationReadRepository(sessions)
        evaluation_operations = EvaluationOperationsService(
            suites=(
                RegisteredEvaluationSuite(
                    suite=suite,
                    sandbox_id=scope.sandbox_id,
                ),
            ),
            retrieval=retrieval,
            repository=evaluation_repository,
        )
        evaluation_command = EvaluationStartCommand(
            suite_id=suite.suite_id,
            suite_version=suite.version,
        )
        evaluation_run = evaluation_operations.start(
            actor=_release_manager(),
            command=evaluation_command,
        )
        repeated_evaluation_run = evaluation_operations.start(
            actor=_release_manager(),
            command=evaluation_command,
        )
        baseline = evaluation_repository.get_retrieval_baseline(
            evaluation_run_id=evaluation_run.evaluation_run_id
        )
        if baseline is None:
            raise RuntimeError("E9 EvaluationRun cannot be restored after start")
        evaluation = baseline.report
        replay = evaluation_operations.replay_case(
            actor=_release_manager(),
            evaluation_run_id=evaluation_run.evaluation_run_id,
            case_id=suite.cases[0].case_id,
        )
        self_regression = evaluation_operations.compare_runs(
            actor=_release_manager(),
            evaluation_run_id=evaluation_run.evaluation_run_id,
            baseline_run_id=evaluation_run.evaluation_run_id,
        )

        with sessions() as session:
            run = session.get(ProcessingRun, receipt.run_id)
            evidence_ids = set(
                session.scalars(
                    select(Evidence.evidence_id).where(
                        Evidence.source_version_id == receipt.source_version_id
                    )
                )
            )
            counts = {
                "evidence_count": session.scalar(
                    select(func.count(Evidence.evidence_id)).where(
                        Evidence.source_version_id == receipt.source_version_id
                    )
                ),
                "chunk_count": session.scalar(
                    select(func.count(RetrievalChunk.chunk_id)).where(
                        RetrievalChunk.source_version_id == receipt.source_version_id
                    )
                ),
                "finding_count": session.scalar(
                    select(func.count(ChunkProjectionFinding.finding_id)).where(
                        ChunkProjectionFinding.source_version_id == receipt.source_version_id
                    )
                ),
            }
            candidate_count = session.scalar(select(func.count(KnowledgeCandidate.candidate_id)))
            release_count = session.scalar(select(func.count(Release.release_id)))
        expected_ids = {
            evidence_id
            for case in suite.cases
            for evidence_id in case.expected_evidence_ids
        }
        missing_expected = sorted(expected_ids - evidence_ids)
        if missing_expected:
            raise RuntimeError(
                "GoldSuite ExpectedEvidence is absent after E9 processing: "
                + ", ".join(missing_expected)
            )
        if run is None or run.status != "evidence_ready":
            raise RuntimeError("E9 processing run did not reach evidence_ready")
        if candidate_count or release_count:
            raise RuntimeError("E9 POC must not create candidates or publish a Release")
        return {
            "poc_version": POC_VERSION,
            "asset": {
                "document_id": asset.document_id,
                "source_url": asset.source_url,
                "sha256": asset.sha256,
                "size_bytes": asset.size_bytes,
                "page_count": asset.page_count,
                "text_extractable": asset.text_extractable,
                "redistribution": asset.redistribution,
            },
            "sandbox": {
                "kind": "release_candidate",
                "sandbox_id": scope.sandbox_id,
                "source_version_id": receipt.source_version_id,
                "chunk_profile_id": scope.chunk_profile_id,
                "published_release_created": False,
                "knowledge_candidate_created": False,
            },
            "processing": {
                "run_id": receipt.run_id,
                "status": run.status,
                "executed_steps": executed_steps,
                **counts,
                "projection_sha256": projection_sha256,
                "replay_stable": True,
            },
            "evaluation": evaluation.model_dump(mode="json"),
            "evaluation_operations": {
                "registered_suite_count": len(evaluation_operations.list_suites()),
                "start_replay_stable": (
                    repeated_evaluation_run.evaluation_run_id
                    == evaluation_run.evaluation_run_id
                ),
                "case_replay_query_id": replay.query_id,
                "case_replay_external_model_requests": (
                    replay.external_model_requests
                ),
                "self_regression_counts": {
                    "improved": self_regression.counts.improved,
                    "regressed": self_regression.counts.regressed,
                    "unchanged": self_regression.counts.unchanged,
                    "added": self_regression.counts.added,
                    "removed": self_regression.counts.removed,
                },
            },
            "evaluation_run": {
                "evaluation_run_id": evaluation_run.evaluation_run_id,
                "purpose": evaluation_run.purpose,
                "outcome": evaluation_run.outcome,
                "persisted_during_run": True,
                "database_retention": database_retention,
            },
        }
    finally:
        engine.dispose()


def _curator() -> ActorContext:
    return ActorContext(
        actor_id=REGISTRATION_ACTOR_ID,
        display_name="P17 E9 Curator",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({ProductRole.KNOWLEDGE_CURATOR}),
        permissions=ROLE_PERMISSIONS[ProductRole.KNOWLEDGE_CURATOR],
        identity_source=IdentitySource.LOCAL_TEST,
    )


def _document_actor() -> ActorContext:
    return resolve_service_account_actor(
        ServiceAccountGrant(
            service_account_id="svc-p17-e9-document",
            display_name="P17 E9 Document Worker",
            worker_pool=WorkerPool.DOCUMENT,
            scopes=WORKER_POOL_PERMISSIONS[WorkerPool.DOCUMENT],
            secret_ref="env://P17_E9_DOCUMENT_WORKER_TOKEN",
            status=GrantStatus.ACTIVE,
        )
    )


def _release_manager() -> ActorContext:
    role = ProductRole.RELEASE_MANAGER
    return ActorContext(
        actor_id="usr-p17-e9-release-manager",
        display_name="P17 E9 Release Manager",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({role}),
        permissions=ROLE_PERMISSIONS[role],
        identity_source=IdentitySource.LOCAL_TEST,
    )


@contextmanager
def ephemeral_postgres() -> Iterator[str]:
    port = _free_port()
    name = f"clinical-p17-e9-poc-{os.getpid()}"
    password = "clinical_p17_ephemeral"
    database = "clinical_p17_e9"
    existing = _docker(
        "ps",
        "-a",
        "--filter",
        f"name=^/{name}$",
        "--format",
        "{{.Names}}",
    ).stdout.strip()
    if existing:
        raise RuntimeError(f"temporary PostgreSQL container already exists: {name}")
    _docker(
        "run",
        "--rm",
        "-d",
        "--name",
        name,
        "-e",
        "POSTGRES_USER=clinical",
        "-e",
        f"POSTGRES_PASSWORD={password}",
        "-e",
        f"POSTGRES_DB={database}",
        "-p",
        f"127.0.0.1:{port}:5432",
        TEMPORARY_POSTGRES_IMAGE,
    )
    database_url = (
        f"postgresql+psycopg://clinical:{password}@127.0.0.1:{port}/{database}"
    )
    try:
        _wait_for_postgres(database_url)
        yield database_url
    finally:
        subprocess.run(  # noqa: S603 - fixed executable and exact owned container
            ["docker", "rm", "-f", name],
            check=False,
            capture_output=True,
            text=True,
        )


def _docker(*arguments: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(  # noqa: S603 - fixed executable and explicit arguments
            ["docker", *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Docker is required for the ephemeral ICH E9 POC") from exc


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_postgres(database_url: str) -> None:
    plain_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            connection = psycopg.connect(plain_url, connect_timeout=1)
        except psycopg.OperationalError:
            time.sleep(0.5)
            continue
        connection.close()
        return
    raise RuntimeError("ephemeral PostgreSQL did not become reachable within 30 seconds")


def _write_report(path: Path, report: dict[str, object]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the ICH E9 retrieval baseline in an ephemeral pgvector PostgreSQL "
            "container; no model key or model request is used."
        )
    )
    parser.add_argument("--asset", type=Path, default=ROOT / DEFAULT_DESTINATION)
    parser.add_argument("--gold-suite", type=Path, default=DEFAULT_GOLD_SUITE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="clinical-p17-e9-") as temporary_root:
        with ephemeral_postgres() as database_url:
            report = run_poc(
                database_url=database_url,
                asset_path=args.asset.resolve(),
                gold_suite_path=args.gold_suite.resolve(),
                object_store_root=Path(temporary_root) / "objects",
                database_retention="ephemeral",
            )
    _write_report(args.report, report)
    print(
        json.dumps(
            {
                "report": str(args.report.resolve()),
                "recallAt5": report["evaluation"]["metrics"]["recall_at_5"],
                "recallAt10": report["evaluation"]["metrics"]["recall_at_10"],
                "externalModelRequests": 0,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
