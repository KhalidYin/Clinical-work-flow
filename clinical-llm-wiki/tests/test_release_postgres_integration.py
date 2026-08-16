"""Opt-in PostgreSQL acceptance for immutable Release publication."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config
import pytest
from sqlalchemy import select

from service.auth import (
    ActorContext,
    IdentitySource,
    Permission,
    PrincipalType,
    ProductRole,
    WorkerPool,
)
from service.db.models import (
    CandidateEvidence,
    ChunkProfile,
    Evidence,
    ImpactAssessment,
    KnowledgeCandidate,
    KnowledgeRevision,
    KnowledgeUnit,
    ProcessingRun,
    Release,
    ReleaseItem,
    ReleasePointer,
    RetrievalChunk,
    RetrievalChunkEvidence,
    RotationCase,
    RotationDecisionReceipt,
    Source,
    SourceArtifact,
    SourceVersion,
)
from service.db.session import create_database_engine, create_session_factory
from service.evaluation import (
    ReleaseEvaluationGateService,
    SqlAlchemyEvaluationRunRepository,
    SyntheticEvaluationSuite,
)
from service.object_store import InMemoryObjectStore
from service.platform_api.repository import SqlAlchemyPlatformRepository
from service.retrieval import (
    ImmutableReleaseRetrievalService,
    ReleasedRetrievalRequest,
)
from service.retrieval.postgres import PostgresCandidateSearchRepository
from service.releases import (
    ImmutableReleaseResolver,
    ReleaseBuildCommand,
    ReleaseBuilder,
    ReleasePublishCommand,
    ReleasePublisher,
    ReleaseWorkbenchService,
    SqlAlchemyReleaseWorkbenchRepository,
)


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="KNOWLEDGE_TEST_DATABASE_URL is required for PostgreSQL integration",
)


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _worker() -> ActorContext:
    return ActorContext(
        actor_id="svc-release-p17",
        display_name="P17 Release worker",
        principal_type=PrincipalType.SERVICE_ACCOUNT,
        roles=frozenset({ProductRole.SERVICE_ACCOUNT}),
        permissions=frozenset(
            {
                Permission.RELEASE_BUILD,
                Permission.INDEX_BUILD,
                Permission.OBJECT_WRITE_DERIVED,
            }
        ),
        worker_pool=WorkerPool.RELEASE,
    )


def _manager() -> ActorContext:
    return ActorContext(
        actor_id="usr-release-p17",
        display_name="P17 Release manager",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({ProductRole.RELEASE_MANAGER}),
        permissions=frozenset({Permission.RELEASE_PUBLISH}),
        identity_source=IdentitySource.LOCAL_TEST,
    )


def _seed_approved_revision(session) -> None:
    session.add(Source(source_id="src-release-p17", title="Release fixture", source_type="test_fixture"))
    session.flush()
    session.add(
        SourceVersion(
            source_version_id="srcv-release-p17",
            source_id="src-release-p17",
            version="1",
            sha256=_hash("source-release-p17"),
            rights={"classification": "internal", "storage_allowed": True},
            data_boundary="local_processing_only",
            status="parsed",
        )
    )
    session.flush()
    session.add(
        SourceArtifact(
            artifact_id="artifact-release-p17",
            source_version_id="srcv-release-p17",
            artifact_kind="canonical_source",
            object_key="p17/release/source.md",
            sha256=_hash("source-release-p17"),
            media_type="text/markdown",
            size_bytes=100,
            status="available",
        )
    )
    session.add(
        ProcessingRun(
            run_id="run-release-p17",
            source_version_id="srcv-release-p17",
            status="approved",
            requested_by_subject="usr-author-p17",
        )
    )
    session.add(
        ChunkProfile(
            chunk_profile_id="chunk-profile-release-p17",
            version="release-p17-v1",
            tokenizer_id="whitespace-v1",
            target_min_tokens=400,
            target_max_tokens=700,
            hard_max_tokens=900,
            overlap_tokens=80,
            table_hard_max_tokens=1200,
            format_rules={"major_section_boundary": True},
        )
    )
    session.flush()
    session.add(
        Evidence(
            evidence_id="evidence-release-p17",
            source_version_id="srcv-release-p17",
            source_artifact_id="artifact-release-p17",
            derived_artifact_id="artifact-release-p17",
            source_sha256=_hash("source-release-p17"),
            parser_profile_version="parser-p17-v1",
            evidence_type="prose",
            locator={"section": "1"},
            locator_sha256=_hash("locator-release-p17"),
            content="Release evidence",
            content_sha256=_hash("evidence-release-p17"),
            schema_version="evidence-v1",
        )
    )
    session.add(
        RetrievalChunk(
            chunk_id="chunk-release-p17",
            chunk_profile_id="chunk-profile-release-p17",
            source_version_id="srcv-release-p17",
            evidence_type="prose",
            ordinal=0,
            content="Release evidence",
            content_sha256=_hash("Release evidence"),
            token_count=2,
            locator={"majorSection": "1"},
            data_boundary="local_processing_only",
            rights={"classification": "internal", "storage_allowed": True},
        )
    )
    session.add(
        KnowledgeCandidate(
            candidate_id="candidate-release-p17",
            candidate_group_id="candidate-group-release-p17",
            run_id="run-release-p17",
            revision_number=1,
            status="author_confirmed",
            knowledge_type="statistical_principle",
            claim="Immutable Release fact",
            scope={"document": "E9"},
            applicability=None,
            conditions=[],
            exceptions=[],
            advisory_signals=[],
            content_sha256=_hash("revision-release-p17"),
            author_actor_id="usr-author-p17",
        )
    )
    session.add(
        KnowledgeCandidate(
            candidate_id="candidate-release-p17-keep",
            candidate_group_id="candidate-group-release-p17-keep",
            run_id="run-release-p17",
            revision_number=1,
            status="author_confirmed",
            knowledge_type="statistical_principle",
            claim="Retained Release fact",
            scope={"document": "E9"},
            applicability=None,
            conditions=[],
            exceptions=[],
            advisory_signals=[],
            content_sha256=_hash("revision-release-p17-keep"),
            author_actor_id="usr-author-p17",
        )
    )
    session.add(
        KnowledgeUnit(
            knowledge_unit_id="unit-release-p17",
            stable_key="release.p17.unit",
            knowledge_type="statistical_principle",
        )
    )
    session.add(
        KnowledgeUnit(
            knowledge_unit_id="unit-release-p17-keep",
            stable_key="release.p17.unit.keep",
            knowledge_type="statistical_principle",
        )
    )
    session.flush()
    session.add(
        CandidateEvidence(
            candidate_id="candidate-release-p17",
            evidence_id="evidence-release-p17",
            evidence_role="supports",
        )
    )
    session.add(
        CandidateEvidence(
            candidate_id="candidate-release-p17-keep",
            evidence_id="evidence-release-p17",
            evidence_role="supports",
        )
    )
    session.add(
        RetrievalChunkEvidence(
            chunk_id="chunk-release-p17",
            position=0,
            evidence_id="evidence-release-p17",
            start_offset=0,
            end_offset=len("Release evidence"),
            span_role="primary",
        )
    )
    session.add(
        KnowledgeRevision(
            knowledge_revision_id="revision-release-p17",
            knowledge_unit_id="unit-release-p17",
            candidate_id="candidate-release-p17",
            revision_number=1,
            status="approved",
            claim="Immutable Release fact",
            scope={"document": "E9"},
            applicability=None,
            conditions=[],
            exceptions=[],
            content_sha256=_hash("revision-release-p17"),
            author_actor_id="usr-author-p17",
        )
    )
    session.add(
        KnowledgeRevision(
            knowledge_revision_id="revision-release-p17-keep",
            knowledge_unit_id="unit-release-p17-keep",
            candidate_id="candidate-release-p17-keep",
            revision_number=1,
            status="approved",
            claim="Retained Release fact",
            scope={"document": "E9"},
            applicability=None,
            conditions=[],
            exceptions=[],
            content_sha256=_hash("revision-release-p17-keep"),
            author_actor_id="usr-author-p17",
        )
    )


def _evaluation(service, target_id: str):
    return service.evaluate(
        suite=SyntheticEvaluationSuite(
            suite_id="synthetic-release-publication",
            version="v1",
            purpose="release_gate_synthetic",
            thresholds={"recall_at_5_min": 0.5, "recall_at_10_min": 1.0},
            cases=(
                {"case_id": "publish-1", "hit_at_5": True, "hit_at_10": True},
                {"case_id": "publish-2", "hit_at_5": False, "hit_at_10": True},
            ),
        ),
        target_id=target_id,
    )


def _build_command(
    *,
    release_id: str,
    version: str,
    base_release_id: str | None,
    evaluation_run_id: str,
    rotation_case_ids: tuple[str, ...] = (),
):
    return ReleaseBuildCommand(
        release_candidate_id=release_id,
        version=version,
        base_release_id=base_release_id,
        evaluation_run_id=evaluation_run_id,
        chunk_profile_id="chunk-profile-release-p17",
        rotation_case_ids=rotation_case_ids,
        additional_revision_ids=(
            ("revision-release-p17", "revision-release-p17-keep")
            if base_release_id is None
            else ()
        ),
        index_capabilities={
            "metadata": "available",
            "full_text": "available",
            "vector": "degraded",
            "relation": "degraded",
        },
        db_schema_revision="20260816_0012",
        knowledge_contract_version="p17-v1",
        parser_profile_version="parser-p17-v1",
        model_profile_version="replay-v1",
        prompt_profile_version="prompt-v1",
    )


def test_postgres_release_publish_is_atomic_stale_safe_and_replayable() -> None:
    assert TEST_DATABASE_URL is not None
    from service.releases.repository import (
        ReleaseMembershipError,
        ReleaseStateError,
        SqlAlchemyReleaseRepository,
    )

    os.environ["KNOWLEDGE_DATABASE_URL"] = TEST_DATABASE_URL
    alembic_command.upgrade(Config(ROOT / "alembic.ini"), "head")
    engine = create_database_engine(TEST_DATABASE_URL)
    sessions = create_session_factory(engine)
    objects = InMemoryObjectStore()
    try:
        with sessions.begin() as session:
            _seed_approved_revision(session)
        evaluations = ReleaseEvaluationGateService(
            repository=SqlAlchemyEvaluationRunRepository(sessions)
        )
        repository = SqlAlchemyReleaseRepository(sessions, object_store=objects)
        builder = ReleaseBuilder(repository=repository, object_store=objects)
        publisher = ReleasePublisher(repository=repository, object_store=objects)
        workbench = ReleaseWorkbenchService(
            repository=SqlAlchemyReleaseWorkbenchRepository(
                sessions,
                releases=repository,
            )
        )

        with sessions.begin() as session:
            evidence = session.get(Evidence, "evidence-release-p17")
            assert evidence is not None
            evidence.source_artifact_id = None
        uncited_evaluation = _evaluation(evaluations, "release-candidate-p17-uncited")
        with pytest.raises(ReleaseMembershipError, match="canonical source artifact"):
            builder.build(
                actor=_worker(),
                command=_build_command(
                    release_id="release-candidate-p17-uncited",
                    version="p17.uncited",
                    base_release_id=None,
                    evaluation_run_id=uncited_evaluation.evaluation_run_id,
                ),
            )
        with sessions.begin() as session:
            evidence = session.get(Evidence, "evidence-release-p17")
            assert evidence is not None
            evidence.source_artifact_id = "artifact-release-p17"

        first_evaluation = _evaluation(evaluations, "release-candidate-p17-a")
        stale_evaluation = _evaluation(evaluations, "release-candidate-p17-stale")
        first = builder.build(
            actor=_worker(),
            command=_build_command(
                release_id="release-candidate-p17-a",
                version="p17.a",
                base_release_id=None,
                evaluation_run_id=first_evaluation.evaluation_run_id,
            ),
        )
        stale = builder.build(
            actor=_worker(),
            command=_build_command(
                release_id="release-candidate-p17-stale",
                version="p17.stale",
                base_release_id=None,
                evaluation_run_id=stale_evaluation.evaluation_run_id,
            ),
        )
        first_workbench = workbench.get(
            actor=_manager(),
            candidate_id=first.release_id,
        )
        assert first_workbench.current is None
        assert first_workbench.diff is not None
        assert first_workbench.diff.added_count == 2
        assert all(gate.passed for gate in first_workbench.gates)
        assert first_workbench.allowed_actions == ("publish",)
        publisher.publish(
            actor=_manager(),
            command=ReleasePublishCommand(release_id=first.release_id, base_release_id=None),
        )
        stale_workbench = workbench.get(
            actor=_manager(),
            candidate_id=stale.release_id,
        )
        assert "base_release_is_stale" in stale_workbench.blockers
        assert stale_workbench.allowed_actions == ()
        released_retrieval = ImmutableReleaseRetrievalService(
            resolver=ImmutableReleaseResolver(repository=repository),
            repository=PostgresCandidateSearchRepository(sessions),
        )
        current_query = released_retrieval.query(
            ReleasedRetrievalRequest(query="Release evidence", top_k=5)
        )
        assert current_query.release_id == first.release_id
        assert [hit.chunk_id for hit in current_query.hits] == ["chunk-release-p17"]
        assert current_query.hits[0].citations[0].evidence_id == "evidence-release-p17"
        with pytest.raises(ReleaseStateError, match="current Release"):
            publisher.publish(
                actor=_manager(),
                command=ReleasePublishCommand(release_id=stale.release_id, base_release_id=None),
            )

        second_evaluation = _evaluation(evaluations, "release-candidate-p17-b")
        second = builder.build(
            actor=_worker(),
            command=_build_command(
                release_id="release-candidate-p17-b",
                version="p17.b",
                base_release_id=first.release_id,
                evaluation_run_id=second_evaluation.evaluation_run_id,
            ),
        )
        second_workbench = workbench.get(
            actor=_manager(),
            candidate_id=second.release_id,
        )
        assert second_workbench.current is not None
        assert second_workbench.current.release_id == first.release_id
        assert second_workbench.diff is not None
        assert second_workbench.diff.carried_count == 2
        assert second_workbench.blockers == ()
        publisher.publish(
            actor=_manager(),
            command=ReleasePublishCommand(
                release_id=second.release_id,
                base_release_id=first.release_id,
            ),
        )
        historical_query = released_retrieval.query(
            ReleasedRetrievalRequest(
                query="Release evidence",
                top_k=5,
                release_id=first.release_id,
            )
        )
        assert historical_query.release_id == first.release_id

        with sessions.begin() as session:
            session.add(
                SourceVersion(
                    source_version_id="srcv-release-p17-retire",
                    source_id="src-release-p17",
                    version="2",
                    sha256=_hash("source-release-p17-retire"),
                    rights={"classification": "internal", "storage_allowed": True},
                    data_boundary="local_processing_only",
                    status="parsed",
                )
            )
            session.flush()
            session.add(
                ImpactAssessment(
                    assessment_id="impact-release-p17-retire",
                    from_source_version_id="srcv-release-p17",
                    to_source_version_id="srcv-release-p17-retire",
                    comparison_profile_version="comparison-p17-v1",
                )
            )
            session.flush()
            session.add(
                RotationCase(
                    rotation_case_id="rotation-release-p17-retire",
                    impact_assessment_id="impact-release-p17-retire",
                    knowledge_revision_id="revision-release-p17",
                    status="open",
                    case_version=1,
                )
            )

        blocked_evaluation = _evaluation(evaluations, "release-candidate-p17-blocked")
        with pytest.raises(ReleaseMembershipError, match="must be decided"):
            builder.build(
                actor=_worker(),
                command=_build_command(
                    release_id="release-candidate-p17-blocked",
                    version="p17.blocked",
                    base_release_id=second.release_id,
                    evaluation_run_id=blocked_evaluation.evaluation_run_id,
                    rotation_case_ids=("rotation-release-p17-retire",),
                ),
            )

        with sessions.begin() as session:
            rotation = session.get(RotationCase, "rotation-release-p17-retire")
            rotation.status = "decided"
            rotation.proposed_outcome = "retire"
            rotation.proposed_by_actor_id = "usr-curator-p17"
            rotation.proposal_idempotency_key = "proposal-release-p17-retire"
            rotation.proposed_rationale = "Emergency retirement test."
            rotation.case_version = 2
            session.add(
                RotationDecisionReceipt(
                    rotation_decision_id="decision-release-p17-retire",
                    rotation_case_id="rotation-release-p17-retire",
                    outcome="retire",
                    expected_case_version=2,
                    target_knowledge_revision_id=None,
                    actor_id="usr-reviewer-p17",
                    actor_role="reviewer",
                    idempotency_key="decision-release-p17-retire",
                    rationale="The old fact must leave the current Release.",
                )
            )

        retire_evaluation = _evaluation(evaluations, "release-candidate-p17-retire")
        retired = builder.build(
            actor=_worker(),
            command=_build_command(
                release_id="release-candidate-p17-retire",
                version="p17.retire",
                base_release_id=second.release_id,
                evaluation_run_id=retire_evaluation.evaluation_run_id,
                rotation_case_ids=("rotation-release-p17-retire",),
            ),
        )
        retired_workbench = workbench.get(
            actor=_manager(),
            candidate_id=retired.release_id,
        )
        assert retired_workbench.diff is not None
        assert retired_workbench.diff.retired_revision_ids == ("revision-release-p17",)
        publisher.publish(
            actor=_manager(),
            command=ReleasePublishCommand(
                release_id=retired.release_id,
                base_release_id=second.release_id,
            ),
        )

        with sessions.begin() as session:
            session.add(
                Release(
                    release_id="release-p17-unpointed",
                    version="p17.unpointed",
                    status="released",
                    previous_release_id=retired.release_id,
                    manifest_object_key="p17/unpointed/manifest.json",
                    manifest_sha256=_hash("unpointed-manifest"),
                    db_schema_revision="20260816_0012",
                    knowledge_contract_version="p17-v1",
                    parser_profile_version="parser-p17-v1",
                    model_profile_version="replay-v1",
                    prompt_profile_version="prompt-v1",
                    index_manifest_version="p17-index-v1",
                    release_manager_subject="usr-out-of-band",
                    published_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
                )
            )

        current = SqlAlchemyPlatformRepository(sessions).get_current_release()
        assert current is not None
        assert current.release_id == retired.release_id
        replayed_first = repository.get_released(first.release_id)
        replayed_current = repository.get_released()
        assert replayed_first is not None
        assert replayed_current is not None
        assert tuple(
            item.knowledge_revision_id for item in replayed_first.manifest.items
        ) == ("revision-release-p17", "revision-release-p17-keep")
        assert tuple(
            item.knowledge_revision_id for item in replayed_current.manifest.items
        ) == ("revision-release-p17-keep",)
        assert repository.get_released(stale.release_id) is None
        with sessions() as session:
            pointer = session.get(ReleasePointer, "current")
            assert pointer.current_release_id == retired.release_id
            assert pointer.pointer_version == 3
            assert session.get(Release, first.release_id).status == "released"
            assert session.get(Release, stale.release_id).status == "candidate"
            assert tuple(
                session.scalars(
                    select(ReleaseItem).where(ReleaseItem.release_id == first.release_id)
                )
            )
            assert tuple(
                session.scalars(
                    select(ReleaseItem).where(ReleaseItem.release_id == second.release_id)
                )
            )
            retired_items = tuple(
                session.scalars(
                    select(ReleaseItem.knowledge_revision_id).where(
                        ReleaseItem.release_id == retired.release_id
                    )
                )
            )
            assert retired_items == ("revision-release-p17-keep",)
            assert session.get(KnowledgeRevision, "revision-release-p17").status == "retired"
            rotation = session.get(RotationCase, "rotation-release-p17-retire")
            assert rotation.status == "included_in_release"
            assert rotation.included_release_id == retired.release_id
    finally:
        engine.dispose()
