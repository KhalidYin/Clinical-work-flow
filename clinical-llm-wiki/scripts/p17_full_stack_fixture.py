"""Build the isolated two-stage P17 knowledge-governance acceptance fixture.

This fixture intentionally seeds only canonical prerequisites. Evaluation,
Release construction/publication, impact materialization, and rotation decisions
continue to use the production application services.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from secrets import token_urlsafe

from alembic import command as alembic_command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from scripts.ich_e9_poc import DEFAULT_GOLD_SUITE, run_poc
from service.auth import (
    ActorContext,
    IdentitySource,
    PrincipalType,
    ProductRole,
    ROLE_PERMISSIONS,
    WORKER_POOL_PERMISSIONS,
    WorkerPool,
)
from service.auth.password_sessions import (
    Argon2idPasswordHasher,
    PasswordSessionService,
    SqlAlchemyPasswordSessionRepository,
)
from service.db.models import (
    CandidateEvidence,
    ChunkProfile,
    EvaluationRun,
    Evidence,
    KnowledgeCandidate,
    KnowledgeRevision,
    KnowledgeUnit,
    ProcessingRun,
    Release,
    RetrievalChunk,
    RetrievalChunkEvidence,
    RotationCase,
    Source,
    SourceArtifact,
    SourceVersion,
)
from service.db.session import create_database_engine, create_session_factory
from service.evaluation import (
    ReleaseEvaluationGateService,
    SqlAlchemyEvaluationReadRepository,
    SqlAlchemyEvaluationRunRepository,
    SyntheticEvaluationSuite,
)
from service.object_store import LocalObjectStore
from service.platform_api.repository import SqlAlchemyKnowledgeLifecycleRepository
from service.releases import (
    PreparedRelease,
    ImmutableReleaseResolver,
    ReleaseBuildCommand,
    ReleaseBuilder,
    ReleasePublishCommand,
    ReleasePublisher,
    SqlAlchemyReleaseRepository,
    SqlAlchemyReleaseWorkbenchRepository,
    ReleaseWorkbenchService,
)


ROOT = Path(__file__).resolve().parents[1]

SOURCE_ID = "src-p17-full-stack-fixture"
OLD_VERSION_ID = "srcv-p17-full-stack-v1"
NEW_VERSION_ID = "srcv-p17-full-stack-v2"
OLD_ARTIFACT_ID = "artifact-p17-full-stack-v1"
NEW_ARTIFACT_ID = "artifact-p17-full-stack-v2"
OLD_EVIDENCE_ID = "evidence-p17-full-stack-v1"
NEW_EVIDENCE_ID = "evidence-p17-full-stack-v2"
RUN_ID = "run-p17-full-stack-fixture"
CHUNK_PROFILE_ID = "chunk-profile-p17-full-stack"
CHUNK_ID = "chunk-p17-full-stack-v1"
CANDIDATE_ID = "candidate-p17-full-stack-v1"
UNIT_ID = "unit-p17-full-stack"
REVISION_ID = "revision-p17-full-stack-v1"
HISTORICAL_RELEASE_ID = "release-p17-full-stack-a"
STALE_CANDIDATE_ID = "release-p17-full-stack-stale"
PUBLISHABLE_CANDIDATE_ID = "release-p17-full-stack-c"

_OLD_CONTENT = b"Synthetic governed statistical principle, version one.\n"
_NEW_CONTENT = b"Synthetic governed statistical principle, version two.\n"
_LOCATOR = {"section": "fixture.1", "paragraph": 1}


@dataclass(frozen=True, slots=True)
class P17FullStackFixture:
    """Stable identities required by browser and integration acceptance."""

    e9_evaluation_run_id: str
    historical_release_id: str
    stale_candidate_id: str
    publishable_candidate_id: str
    rotation_case_id: str


@dataclass(frozen=True, slots=True)
class P17FixtureCredential:
    """One local-only browser credential generated for the isolated POC."""

    username: str
    password: str
    role: ProductRole


def prepare_full_stack_fixture(
    *,
    database_url: str,
    asset_path: Path,
    object_store_root: Path,
    allow_container_host: bool = False,
) -> P17FullStackFixture:
    """Prepare E9 baseline, historical Release, stale candidate, and open case."""

    _require_isolated_database(
        database_url,
        allow_container_host=allow_container_host,
    )
    _upgrade_database(database_url)
    engine = create_database_engine(database_url)
    sessions = create_session_factory(engine)
    try:
        _require_empty_database(sessions)
    finally:
        engine.dispose()

    report = run_poc(
        database_url=database_url,
        asset_path=asset_path,
        gold_suite_path=ROOT / DEFAULT_GOLD_SUITE,
        object_store_root=object_store_root,
        database_retention="isolated_full_stack_fixture",
    )
    evaluation_run = report["evaluation_run"]
    if not isinstance(evaluation_run, dict):
        raise RuntimeError("E9 POC did not return an EvaluationRun receipt")
    e9_evaluation_run_id = evaluation_run.get("evaluation_run_id")
    if not isinstance(e9_evaluation_run_id, str):
        raise RuntimeError("E9 POC EvaluationRun identity is missing")

    engine = create_database_engine(database_url)
    sessions = create_session_factory(engine)
    objects = LocalObjectStore(root=object_store_root)
    try:
        _seed_canonical_prerequisites(sessions, objects)
        evaluations = ReleaseEvaluationGateService(
            repository=SqlAlchemyEvaluationRunRepository(sessions)
        )
        repository = SqlAlchemyReleaseRepository(sessions, object_store=objects)
        builder = ReleaseBuilder(repository=repository, object_store=objects)
        publisher = ReleasePublisher(repository=repository, object_store=objects)

        first_evaluation = _evaluate(evaluations, HISTORICAL_RELEASE_ID)
        stale_evaluation = _evaluate(evaluations, STALE_CANDIDATE_ID)
        _evaluate(evaluations, PUBLISHABLE_CANDIDATE_ID)
        first = builder.build(
            actor=_release_worker(),
            command=_build_command(
                release_id=HISTORICAL_RELEASE_ID,
                version="p17.fixture.a",
                base_release_id=None,
                evaluation_run_id=first_evaluation.evaluation_run_id,
                additional_revision_ids=(REVISION_ID,),
            ),
        )
        builder.build(
            actor=_release_worker(),
            command=_build_command(
                release_id=STALE_CANDIDATE_ID,
                version="p17.fixture.stale",
                base_release_id=None,
                evaluation_run_id=stale_evaluation.evaluation_run_id,
                additional_revision_ids=(REVISION_ID,),
            ),
        )
        publisher.publish(
            actor=_release_manager(),
            command=ReleasePublishCommand(
                release_id=first.release_id,
                base_release_id=None,
            ),
        )

        lifecycle = SqlAlchemyKnowledgeLifecycleRepository(sessions)
        impact = lifecycle.materialize_impact_assessment(
            actor=_curator(),
            source_id=SOURCE_ID,
            from_source_version_id=OLD_VERSION_ID,
            to_source_version_id=NEW_VERSION_ID,
            comparison_profile_version="p17-fixture-comparison-v1",
        )
        with sessions() as session:
            rotation_case_ids = tuple(
                session.scalars(
                    select(RotationCase.rotation_case_id)
                    .where(RotationCase.impact_assessment_id == impact.assessment_id)
                    .order_by(RotationCase.rotation_case_id)
                )
            )
        if len(rotation_case_ids) != 1:
            raise RuntimeError("P17 fixture must materialize exactly one RotationCase")
        return P17FullStackFixture(
            e9_evaluation_run_id=e9_evaluation_run_id,
            historical_release_id=HISTORICAL_RELEASE_ID,
            stale_candidate_id=STALE_CANDIDATE_ID,
            publishable_candidate_id=PUBLISHABLE_CANDIDATE_ID,
            rotation_case_id=rotation_case_ids[0],
        )
    finally:
        engine.dispose()


def build_publishable_candidate(
    *,
    database_url: str,
    object_store_root: Path,
    fixture: P17FullStackFixture,
    allow_container_host: bool = False,
) -> PreparedRelease:
    """Continue the Release Worker stage after the human rotation decision."""

    _require_isolated_database(
        database_url,
        allow_container_host=allow_container_host,
    )
    engine = create_database_engine(database_url)
    sessions = create_session_factory(engine)
    objects = LocalObjectStore(root=object_store_root)
    try:
        evaluation = SqlAlchemyEvaluationRunRepository(sessions).get(
            _evaluation_id_for_target(fixture.publishable_candidate_id)
        )
        if evaluation is None:
            raise RuntimeError("publishable candidate EvaluationRun is missing")
        repository = SqlAlchemyReleaseRepository(sessions, object_store=objects)
        return ReleaseBuilder(repository=repository, object_store=objects).build(
            actor=_release_worker(),
            command=_build_command(
                release_id=fixture.publishable_candidate_id,
                version="p17.fixture.c",
                base_release_id=fixture.historical_release_id,
                evaluation_run_id=evaluation.evaluation_run_id,
                rotation_case_ids=(fixture.rotation_case_id,),
            ),
        )
    finally:
        engine.dispose()


def provision_fixture_users(
    *,
    database_url: str,
    allow_container_host: bool = False,
) -> tuple[P17FixtureCredential, ...]:
    """Create three isolated browser actors without touching any existing admin."""

    _require_isolated_database(
        database_url,
        allow_container_host=allow_container_host,
    )
    definitions = (
        (
            "usr-p17-browser-curator",
            "p17.curator",
            "P17 Knowledge Curator",
            "p17.curator@example.test",
            ProductRole.KNOWLEDGE_CURATOR,
        ),
        (
            "usr-p17-browser-reviewer",
            "p17.reviewer",
            "P17 Independent Reviewer",
            "p17.reviewer@example.test",
            ProductRole.REVIEWER,
        ),
        (
            "usr-p17-browser-release-manager",
            "p17.release-manager",
            "P17 Release Manager",
            "p17.release-manager@example.test",
            ProductRole.RELEASE_MANAGER,
        ),
    )
    passwords = tuple(token_urlsafe(18) for _definition in definitions)
    password_iterator = iter(passwords)
    user_id_iterator = iter(definition[0] for definition in definitions)
    engine = create_database_engine(database_url)
    sessions = create_session_factory(engine)
    service = PasswordSessionService(
        repository=SqlAlchemyPasswordSessionRepository(sessions),
        hasher=Argon2idPasswordHasher(),
        temporary_password_factory=lambda: next(password_iterator),
        user_id_factory=lambda: next(user_id_iterator),
    )
    try:
        admin = _platform_admin()
        credentials: list[P17FixtureCredential] = []
        for definition, password in zip(definitions, passwords, strict=True):
            _user_id, username, display_name, email, role = definition
            result = service.create_user(
                actor=admin,
                username=username,
                display_name=display_name,
                email=email,
                roles=(role,),
                require_password_change=False,
            )
            if result.temporary_password != password:
                raise RuntimeError("P17 fixture credential generation drifted")
            credentials.append(
                P17FixtureCredential(
                    username=result.username,
                    password=result.temporary_password,
                    role=role,
                )
            )
        return tuple(credentials)
    finally:
        engine.dispose()


def verify_full_stack_fixture(
    *,
    database_url: str,
    object_store_root: Path,
    fixture: P17FullStackFixture,
    allow_container_host: bool = False,
) -> dict[str, object]:
    """Fail closed on the durable fixture facts at any governed POC stage."""

    _require_isolated_database(
        database_url,
        allow_container_host=allow_container_host,
    )
    engine = create_database_engine(database_url)
    sessions = create_session_factory(engine)
    objects = LocalObjectStore(root=object_store_root)
    try:
        releases = SqlAlchemyReleaseRepository(sessions, object_store=objects)
        resolver = ImmutableReleaseResolver(repository=releases)
        current = resolver.resolve()
        if current.release_id not in {
            fixture.historical_release_id,
            fixture.publishable_candidate_id,
        }:
            raise RuntimeError("P17 fixture current Release identity is invalid")
        historical = resolver.resolve(release_id=fixture.historical_release_id)
        if historical.release_id != fixture.historical_release_id:
            raise RuntimeError("P17 historical Release is not replayable")
        e9_run = SqlAlchemyEvaluationReadRepository(sessions).get_run(
            evaluation_run_id=fixture.e9_evaluation_run_id
        )
        if (
            e9_run is None
            or e9_run.purpose != "retrieval_baseline"
            or e9_run.outcome != "informational"
            or e9_run.external_model_requests != 0
        ):
            raise RuntimeError("P17 E9 informational EvaluationRun is invalid")
        workbench = ReleaseWorkbenchService(
            repository=SqlAlchemyReleaseWorkbenchRepository(
                sessions,
                releases=releases,
            )
        )
        stale = workbench.get(
            actor=_release_manager(),
            candidate_id=fixture.stale_candidate_id,
        )
        if "base_release_is_stale" not in stale.blockers or stale.allowed_actions:
            raise RuntimeError("P17 stale candidate Gate is invalid")
        lifecycle = SqlAlchemyKnowledgeLifecycleRepository(sessions)
        rotation = lifecycle.get_rotation_case(rotation_case_id=fixture.rotation_case_id)
        if rotation is None or rotation.status not in {
            "open",
            "in_review",
            "decided",
            "included_in_release",
        }:
            raise RuntimeError("P17 RotationCase state is invalid")
        if current.release_id == fixture.publishable_candidate_id and (
            rotation.status != "included_in_release"
            or rotation.included_release_id != fixture.publishable_candidate_id
        ):
            raise RuntimeError("published P17 candidate did not consume RotationCase")
        return {
            "schemaVersion": "p17-full-stack-verification-v1",
            "currentReleaseId": current.release_id,
            "historicalReleaseId": historical.release_id,
            "e9EvaluationRunId": e9_run.evaluation_run_id,
            "e9ExternalModelRequests": e9_run.external_model_requests,
            "staleBlockers": list(stale.blockers),
            "rotationCaseId": rotation.rotation_case_id,
            "rotationStatus": rotation.status,
        }
    finally:
        engine.dispose()


def _require_isolated_database(
    database_url: str,
    *,
    allow_container_host: bool = False,
) -> None:
    url = make_url(database_url)
    if url.drivername != "postgresql+psycopg":
        raise ValueError("P17 fixture requires postgresql+psycopg")
    allowed_hosts = {"127.0.0.1", "localhost"}
    if allow_container_host:
        allowed_hosts.add("postgres")
    if url.host not in allowed_hosts:
        raise ValueError("P17 fixture requires an explicitly local PostgreSQL host")
    if not url.database or not url.database.startswith("clinical_p17_"):
        raise ValueError("P17 fixture database name must start with clinical_p17_")


def _upgrade_database(database_url: str) -> None:
    previous = os.environ.get("KNOWLEDGE_DATABASE_URL")
    os.environ["KNOWLEDGE_DATABASE_URL"] = database_url
    try:
        alembic_command.upgrade(Config(ROOT / "alembic.ini"), "head")
    finally:
        if previous is None:
            os.environ.pop("KNOWLEDGE_DATABASE_URL", None)
        else:
            os.environ["KNOWLEDGE_DATABASE_URL"] = previous


def _require_empty_database(sessions) -> None:
    with sessions() as session:
        counts = {
            "source": session.scalar(select(func.count(Source.source_id))),
            "evaluation": session.scalar(select(func.count(EvaluationRun.evaluation_run_id))),
            "release": session.scalar(select(func.count(Release.release_id))),
        }
    if any(counts.values()):
        present = ", ".join(f"{name}={int(value or 0)}" for name, value in counts.items())
        raise RuntimeError(f"P17 fixture database must be empty: {present}")


def _seed_canonical_prerequisites(sessions, objects: LocalObjectStore) -> None:
    old_descriptor = objects.put_bytes(
        "p17-fixture/source-v1.md",
        _OLD_CONTENT,
        media_type="text/markdown",
    )
    new_descriptor = objects.put_bytes(
        "p17-fixture/source-v2.md",
        _NEW_CONTENT,
        media_type="text/markdown",
    )
    locator_hash = _hash_jsonish("fixture.1:1")
    claim_hash = _hash_jsonish("p17-full-stack-governed-claim-v1")
    old_text = _OLD_CONTENT.decode("utf-8").strip()
    new_text = _NEW_CONTENT.decode("utf-8").strip()
    with sessions.begin() as session:
        session.add(
            Source(
                source_id=SOURCE_ID,
                title="P17 full-stack synthetic rotation fixture",
                source_type="test_fixture",
            )
        )
        session.add_all(
            [
                SourceVersion(
                    source_version_id=OLD_VERSION_ID,
                    source_id=SOURCE_ID,
                    version="1",
                    sha256=old_descriptor.sha256,
                    rights=_rights(),
                    data_boundary="local_processing_only",
                    status="approved",
                ),
                SourceVersion(
                    source_version_id=NEW_VERSION_ID,
                    source_id=SOURCE_ID,
                    version="2",
                    sha256=new_descriptor.sha256,
                    rights=_rights(),
                    data_boundary="local_processing_only",
                    status="approved",
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                SourceArtifact(
                    artifact_id=OLD_ARTIFACT_ID,
                    source_version_id=OLD_VERSION_ID,
                    artifact_kind="canonical_source",
                    object_key=old_descriptor.object_key,
                    sha256=old_descriptor.sha256,
                    media_type=old_descriptor.media_type,
                    size_bytes=old_descriptor.size_bytes,
                    status="available",
                ),
                SourceArtifact(
                    artifact_id=NEW_ARTIFACT_ID,
                    source_version_id=NEW_VERSION_ID,
                    artifact_kind="canonical_source",
                    object_key=new_descriptor.object_key,
                    sha256=new_descriptor.sha256,
                    media_type=new_descriptor.media_type,
                    size_bytes=new_descriptor.size_bytes,
                    status="available",
                ),
            ]
        )
        session.add(
            ProcessingRun(
                run_id=RUN_ID,
                source_version_id=OLD_VERSION_ID,
                status="approved",
                requested_by_subject="usr-p17-fixture-author",
            )
        )
        session.add(
            ChunkProfile(
                chunk_profile_id=CHUNK_PROFILE_ID,
                version="p17-full-stack-fixture-v1",
                tokenizer_id="whitespace-v1",
                target_min_tokens=8,
                target_max_tokens=32,
                hard_max_tokens=48,
                overlap_tokens=2,
                table_hard_max_tokens=64,
                format_rules={"major_section_boundary": True},
            )
        )
        session.flush()
        session.add_all(
            [
                Evidence(
                    evidence_id=OLD_EVIDENCE_ID,
                    source_version_id=OLD_VERSION_ID,
                    source_artifact_id=OLD_ARTIFACT_ID,
                    derived_artifact_id=OLD_ARTIFACT_ID,
                    source_sha256=old_descriptor.sha256,
                    parser_profile_version="parser-p17-fixture-v1",
                    evidence_type="prose",
                    locator=_LOCATOR,
                    locator_sha256=locator_hash,
                    content=old_text,
                    content_sha256=_hash_jsonish(old_text),
                    schema_version="evidence-v1",
                ),
                Evidence(
                    evidence_id=NEW_EVIDENCE_ID,
                    source_version_id=NEW_VERSION_ID,
                    source_artifact_id=NEW_ARTIFACT_ID,
                    derived_artifact_id=NEW_ARTIFACT_ID,
                    source_sha256=new_descriptor.sha256,
                    parser_profile_version="parser-p17-fixture-v1",
                    evidence_type="prose",
                    locator=_LOCATOR,
                    locator_sha256=locator_hash,
                    content=new_text,
                    content_sha256=_hash_jsonish(new_text),
                    schema_version="evidence-v1",
                ),
            ]
        )
        session.add(
            RetrievalChunk(
                chunk_id=CHUNK_ID,
                chunk_profile_id=CHUNK_PROFILE_ID,
                source_version_id=OLD_VERSION_ID,
                evidence_type="prose",
                ordinal=0,
                content=old_text,
                content_sha256=_hash_jsonish(old_text),
                token_count=len(old_text.split()),
                locator=_LOCATOR,
                data_boundary="local_processing_only",
                rights=_rights(),
            )
        )
        session.add(
            KnowledgeCandidate(
                candidate_id=CANDIDATE_ID,
                candidate_group_id="candidate-group-p17-full-stack",
                run_id=RUN_ID,
                revision_number=1,
                status="author_confirmed",
                knowledge_type="statistical_principle",
                claim="Synthetic governed statistical principle",
                scope={"fixture": "P17", "document": "synthetic"},
                applicability=None,
                conditions=[],
                exceptions=[],
                advisory_signals=[],
                content_sha256=claim_hash,
                author_actor_id="usr-p17-fixture-author",
            )
        )
        session.add(
            KnowledgeUnit(
                knowledge_unit_id=UNIT_ID,
                stable_key="p17.fixture.statistical-principle",
                knowledge_type="statistical_principle",
            )
        )
        session.flush()
        session.add(
            CandidateEvidence(
                candidate_id=CANDIDATE_ID,
                evidence_id=OLD_EVIDENCE_ID,
                evidence_role="supports",
            )
        )
        session.add(
            RetrievalChunkEvidence(
                chunk_id=CHUNK_ID,
                position=0,
                evidence_id=OLD_EVIDENCE_ID,
                start_offset=0,
                end_offset=len(old_text),
                span_role="primary",
            )
        )
        session.add(
            KnowledgeRevision(
                knowledge_revision_id=REVISION_ID,
                knowledge_unit_id=UNIT_ID,
                candidate_id=CANDIDATE_ID,
                revision_number=1,
                status="approved",
                claim="Synthetic governed statistical principle",
                scope={"fixture": "P17", "document": "synthetic"},
                applicability=None,
                conditions=[],
                exceptions=[],
                content_sha256=claim_hash,
                author_actor_id="usr-p17-fixture-author",
            )
        )


def _evaluate(service: ReleaseEvaluationGateService, target_id: str):
    return service.evaluate(
        suite=SyntheticEvaluationSuite(
            suite_id="synthetic-p17-full-stack-release-gate",
            version="v1",
            purpose="release_gate_synthetic",
            thresholds={"recall_at_5_min": 0.5, "recall_at_10_min": 1.0},
            cases=(
                {"case_id": "fixture-1", "hit_at_5": True, "hit_at_10": True},
                {"case_id": "fixture-2", "hit_at_5": False, "hit_at_10": True},
            ),
        ),
        target_id=target_id,
    )


def _evaluation_id_for_target(target_id: str) -> str:
    # Use the production service to derive the deterministic identity without
    # duplicating its UUID algorithm, then read the already persisted record.
    from service.evaluation.release_gate import ReleaseEvaluationGateService as Service

    class _CaptureRepository:
        def record(self, run):
            return run

    return _evaluate(Service(repository=_CaptureRepository()), target_id).evaluation_run_id


def _build_command(
    *,
    release_id: str,
    version: str,
    base_release_id: str | None,
    evaluation_run_id: str,
    rotation_case_ids: tuple[str, ...] = (),
    additional_revision_ids: tuple[str, ...] = (),
) -> ReleaseBuildCommand:
    return ReleaseBuildCommand(
        release_candidate_id=release_id,
        version=version,
        base_release_id=base_release_id,
        evaluation_run_id=evaluation_run_id,
        chunk_profile_id=CHUNK_PROFILE_ID,
        rotation_case_ids=rotation_case_ids,
        additional_revision_ids=additional_revision_ids,
        index_capabilities={
            "metadata": "available",
            "full_text": "available",
            "vector": "degraded",
            "relation": "degraded",
        },
        db_schema_revision="20260816_0012",
        knowledge_contract_version="p17-v1",
        parser_profile_version="parser-p17-fixture-v1",
        model_profile_version="replay-v1",
        prompt_profile_version="prompt-v1",
    )


def _release_worker() -> ActorContext:
    return ActorContext(
        actor_id="svc-p17-full-stack-release",
        display_name="P17 full-stack Release Worker",
        principal_type=PrincipalType.SERVICE_ACCOUNT,
        roles=frozenset({ProductRole.SERVICE_ACCOUNT}),
        permissions=WORKER_POOL_PERMISSIONS[WorkerPool.RELEASE],
        worker_pool=WorkerPool.RELEASE,
    )


def _release_manager() -> ActorContext:
    role = ProductRole.RELEASE_MANAGER
    return ActorContext(
        actor_id="usr-p17-full-stack-manager",
        display_name="P17 full-stack Release Manager",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({role}),
        permissions=ROLE_PERMISSIONS[role],
        identity_source=IdentitySource.LOCAL_TEST,
    )


def _curator() -> ActorContext:
    role = ProductRole.KNOWLEDGE_CURATOR
    return ActorContext(
        actor_id="usr-p17-full-stack-curator",
        display_name="P17 full-stack Knowledge Curator",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({role}),
        permissions=ROLE_PERMISSIONS[role],
        identity_source=IdentitySource.LOCAL_TEST,
    )


def _platform_admin() -> ActorContext:
    role = ProductRole.PLATFORM_ADMIN
    return ActorContext(
        actor_id="usr-p17-fixture-bootstrap-admin",
        display_name="P17 fixture bootstrap administrator",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({role}),
        permissions=ROLE_PERMISSIONS[role],
        identity_source=IdentitySource.LOCAL_TEST,
    )


def _rights() -> dict[str, object]:
    return {
        "classification": "internal",
        "storage_allowed": True,
        "citation_required": True,
    }


def _hash_jsonish(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _container_mode() -> bool:
    return os.environ.get("P17_FIXTURE_CONTAINER_MODE", "").casefold() in {
        "1",
        "true",
        "yes",
    }


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _write_receipt(
    path: Path,
    *,
    fixture: P17FullStackFixture,
    credentials: tuple[P17FixtureCredential, ...],
) -> None:
    payload = {
        "schemaVersion": "p17-full-stack-fixture-v1",
        "fixture": asdict(fixture),
        "credentials": [
            {
                "username": credential.username,
                "password": credential.password,
                "role": credential.role.value,
            }
            for credential in credentials
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    os.chmod(path, 0o600)


def _read_fixture_receipt(path: Path) -> P17FullStackFixture:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != "p17-full-stack-fixture-v1":
        raise RuntimeError("P17 fixture receipt schema is invalid")
    facts = payload.get("fixture")
    if not isinstance(facts, dict):
        raise RuntimeError("P17 fixture receipt facts are missing")
    try:
        return P17FullStackFixture(**facts)
    except TypeError as exc:
        raise RuntimeError("P17 fixture receipt facts are invalid") from exc


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--asset-path", type=Path, required=True)
    prepare_parser.add_argument("--receipt", type=Path, required=True)
    for action in ("build", "verify"):
        action_parser = subparsers.add_parser(action)
        action_parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args(argv)

    database_url = _required_environment("KNOWLEDGE_DATABASE_URL")
    object_store_root = Path(_required_environment("KNOWLEDGE_OBJECT_STORE_ROOT"))
    container_mode = _container_mode()
    if args.action == "prepare":
        fixture = prepare_full_stack_fixture(
            database_url=database_url,
            asset_path=args.asset_path,
            object_store_root=object_store_root,
            allow_container_host=container_mode,
        )
        credentials = provision_fixture_users(
            database_url=database_url,
            allow_container_host=container_mode,
        )
        _write_receipt(args.receipt, fixture=fixture, credentials=credentials)
        print(
            json.dumps(
                {
                    "fixture": asdict(fixture),
                    "credentialUsernames": [item.username for item in credentials],
                    "receipt": str(args.receipt),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return

    fixture = _read_fixture_receipt(args.receipt)
    if args.action == "build":
        prepared = build_publishable_candidate(
            database_url=database_url,
            object_store_root=object_store_root,
            fixture=fixture,
            allow_container_host=container_mode,
        )
        print(
            json.dumps(
                {"preparedReleaseId": prepared.release_id},
                sort_keys=True,
            )
        )
        return
    print(
        json.dumps(
            verify_full_stack_fixture(
                database_url=database_url,
                object_store_root=object_store_root,
                fixture=fixture,
                allow_container_host=container_mode,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


__all__ = [
    "P17FixtureCredential",
    "P17FullStackFixture",
    "build_publishable_candidate",
    "prepare_full_stack_fixture",
    "provision_fixture_users",
    "verify_full_stack_fixture",
]


if __name__ == "__main__":
    main()
