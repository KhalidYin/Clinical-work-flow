"""Opt-in PostgreSQL acceptance for P17 impact/case materialization."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import func, select

from service.auth import (
    ActorContext,
    IdentitySource,
    Permission,
    PrincipalType,
    ProductRole,
)
from service.db.models import (
    AuditEvent,
    CandidateEvidence,
    Evidence,
    EvidenceImpact,
    ImpactAssessment,
    KnowledgeCandidate,
    KnowledgeRevision,
    KnowledgeUnit,
    ProcessingRun,
    Release,
    ReleaseItem,
    RotationCase,
    Source,
    SourceArtifact,
    SourceVersion,
)
from service.db.session import create_database_engine, create_session_factory
from service.governance.rotation import (
    ImpactMaterializationCommand,
    RotationImpactMaterializer,
)
from service.knowledge import InvalidRotationTransitionError, RotationProposalCommand
from service.platform_api.repository import SqlAlchemyKnowledgeLifecycleRepository


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="KNOWLEDGE_TEST_DATABASE_URL is required for PostgreSQL integration",
)


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _curator() -> ActorContext:
    return ActorContext(
        actor_id="usr-rotation-curator",
        display_name="Synthetic curator",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({ProductRole.KNOWLEDGE_CURATOR}),
        permissions=frozenset({Permission.CANDIDATE_WRITE}),
        identity_source=IdentitySource.OIDC,
    )


def _seed_materialization(session) -> None:
    session.add(
        Source(
            source_id="src-rotation-synthetic",
            title="Synthetic rotation fixture",
            source_type="test_fixture",
        )
    )
    session.flush()
    for version in ("old", "new"):
        session.add(
            SourceVersion(
                source_version_id=f"srcv-rotation-{version}",
                source_id="src-rotation-synthetic",
                version=version,
                sha256=_hash(f"source-{version}"),
                rights={"classification": "internal", "storage_allowed": True},
                data_boundary="local_processing_only",
                status="parsed",
            )
        )
    session.flush()
    for version in ("old", "new"):
        session.add(
            SourceArtifact(
                artifact_id=f"artifact-rotation-{version}",
                source_version_id=f"srcv-rotation-{version}",
                artifact_kind="canonical_source",
                object_key=f"synthetic/{version}.md",
                sha256=_hash(f"source-{version}"),
                media_type="text/markdown",
                size_bytes=100,
                status="available",
            )
        )
    session.flush()
    session.add(
        ProcessingRun(
            run_id="run-rotation-old",
            source_version_id="srcv-rotation-old",
            status="approved",
            requested_by_subject="usr-rotation-author",
        )
    )
    session.flush()
    evidence_facts = (
        ("old-safe", "old", "stable content", "section-1"),
        ("old-risk", "old", "before", "section-2"),
        ("new-safe", "new", "stable content", "section-1"),
        ("new-risk", "new", "after", "section-2"),
    )
    for evidence_id, version, content, locator in evidence_facts:
        session.add(
            Evidence(
                evidence_id=f"evidence-{evidence_id}",
                source_version_id=f"srcv-rotation-{version}",
                derived_artifact_id=f"artifact-rotation-{version}",
                source_sha256=_hash(f"source-{version}"),
                parser_profile_version="parser-synthetic-v1",
                evidence_type="prose",
                locator={"section": locator},
                locator_sha256=_hash(locator),
                content=content,
                content_sha256=_hash(content),
                schema_version="evidence-v1",
            )
        )
    for suffix in ("safe", "risk"):
        session.add(
            KnowledgeCandidate(
                candidate_id=f"candidate-rotation-{suffix}",
                candidate_group_id=f"candidate-group-rotation-{suffix}",
                run_id="run-rotation-old",
                revision_number=1,
                status="author_confirmed",
                knowledge_type="synthetic_principle",
                claim=f"Synthetic {suffix} claim",
                scope={"fixture": "rotation"},
                applicability={"version": "old"},
                conditions=[],
                exceptions=[],
                advisory_signals=[],
                content_sha256=_hash(f"revision-{suffix}"),
                author_actor_id="usr-rotation-author",
            )
        )
        session.add(
            KnowledgeUnit(
                knowledge_unit_id=f"unit-rotation-{suffix}",
                stable_key=f"rotation.synthetic.{suffix}",
                knowledge_type="synthetic_principle",
            )
        )
    session.flush()
    for suffix in ("safe", "risk"):
        session.add(
            CandidateEvidence(
                candidate_id=f"candidate-rotation-{suffix}",
                evidence_id=f"evidence-old-{suffix}",
                evidence_role="supports",
            )
        )
        session.add(
            KnowledgeRevision(
                knowledge_revision_id=f"revision-rotation-{suffix}",
                knowledge_unit_id=f"unit-rotation-{suffix}",
                candidate_id=f"candidate-rotation-{suffix}",
                revision_number=1,
                status="released",
                claim=f"Synthetic {suffix} claim",
                scope={"fixture": "rotation"},
                applicability={"version": "old"},
                conditions=[],
                exceptions=[],
                content_sha256=_hash(f"revision-{suffix}"),
                author_actor_id="usr-rotation-author",
            )
        )
    session.flush()
    session.add(
        Release(
            release_id="release-rotation-base",
            version="rotation.base",
            status="released",
            manifest_object_key="synthetic/release.json",
            manifest_sha256=_hash("manifest"),
            db_schema_revision="20260816_0011",
            knowledge_contract_version="p17-v1",
            parser_profile_version="parser-synthetic-v1",
            model_profile_version="replay-v1",
            prompt_profile_version="prompt-v1",
            index_manifest_version="index-v1",
            release_manager_subject="usr-release-manager",
        )
    )
    for suffix in ("safe", "risk"):
        session.add(
            ReleaseItem(
                release_id="release-rotation-base",
                knowledge_revision_id=f"revision-rotation-{suffix}",
                content_sha256=_hash(f"revision-{suffix}"),
            )
        )


def test_postgres_materialization_is_atomic_idempotent_and_release_preserving() -> None:
    assert TEST_DATABASE_URL is not None
    from service.governance.rotation_repository import SqlAlchemyRotationRepository

    os.environ["KNOWLEDGE_DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(Config(ROOT / "alembic.ini"), "head")
    engine = create_database_engine(TEST_DATABASE_URL)
    sessions = create_session_factory(engine)
    try:
        with sessions.begin() as session:
            _seed_materialization(session)
        materializer = RotationImpactMaterializer(
            repository=SqlAlchemyRotationRepository(sessions)
        )
        materialize_command = ImpactMaterializationCommand(
            from_source_version_id="srcv-rotation-old",
            to_source_version_id="srcv-rotation-new",
            comparison_profile_version="comparison-synthetic-v1",
        )

        first = materializer.materialize(
            actor_id="usr-rotation-curator",
            command=materialize_command,
        )
        replay = materializer.materialize(
            actor_id="usr-rotation-curator",
            command=materialize_command,
        )

        assert first == replay
        assert {
            case.knowledge_revision_id: tuple(
                outcome.value for outcome in case.eligible_outcomes
            )
            for case in first.cases
        } == {
            "revision-rotation-risk": ("replace", "retire", "no_action"),
            "revision-rotation-safe": ("carry_forward",),
        }
        lifecycle = SqlAlchemyKnowledgeLifecycleRepository(sessions)
        cases_by_revision = {
            case.knowledge_revision_id: lifecycle.get_rotation_case(
                rotation_case_id=case.rotation_case_id
            )
            for case in first.cases
        }
        assert cases_by_revision["revision-rotation-safe"].change_types == (
            "unchanged",
        )
        assert cases_by_revision["revision-rotation-safe"].eligible_outcomes == (
            "carry_forward",
        )
        assert cases_by_revision["revision-rotation-risk"].change_types == (
            "modified",
        )
        assert cases_by_revision["revision-rotation-risk"].eligible_outcomes == (
            "replace",
            "retire",
            "no_action",
        )
        safe_case = cases_by_revision["revision-rotation-safe"]
        risk_case = cases_by_revision["revision-rotation-risk"]
        with pytest.raises(InvalidRotationTransitionError, match="not eligible"):
            lifecycle.propose_rotation_case(
                actor=_curator(),
                command=RotationProposalCommand(
                    rotation_case_id=safe_case.rotation_case_id,
                    expected_case_version=1,
                    outcome="replace",
                    target_knowledge_revision_id="revision-rotation-risk",
                    idempotency_key="rotation-safe-invalid-replace",
                ),
            )
        with pytest.raises(InvalidRotationTransitionError, match="not eligible"):
            lifecycle.propose_rotation_case(
                actor=_curator(),
                command=RotationProposalCommand(
                    rotation_case_id=risk_case.rotation_case_id,
                    expected_case_version=1,
                    outcome="carry_forward",
                    target_knowledge_revision_id="revision-rotation-risk",
                    idempotency_key="rotation-risk-invalid-carry",
                ),
            )
        proposed_safe = lifecycle.propose_rotation_case(
            actor=_curator(),
            command=RotationProposalCommand(
                rotation_case_id=safe_case.rotation_case_id,
                expected_case_version=1,
                outcome="carry_forward",
                target_knowledge_revision_id="revision-rotation-safe",
                idempotency_key="rotation-safe-carry-forward",
                rationale="Exact Evidence is unchanged.",
            ),
        )
        proposed_risk = lifecycle.propose_rotation_case(
            actor=_curator(),
            command=RotationProposalCommand(
                rotation_case_id=risk_case.rotation_case_id,
                expected_case_version=1,
                outcome="no_action",
                idempotency_key="rotation-risk-human-no-action",
                rationale="Requires independent review.",
            ),
        )
        assert proposed_safe.status == "in_review"
        assert proposed_risk.status == "in_review"
        assert proposed_safe.included_release_id is None
        assert proposed_risk.included_release_id is None
        with sessions() as session:
            assert session.scalar(select(func.count()).select_from(ImpactAssessment)) == 1
            assert session.scalar(select(func.count()).select_from(EvidenceImpact)) == 2
            assert session.scalar(select(func.count()).select_from(RotationCase)) == 2
            assert session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "impact_assessment.materialized")
            ) == 1
            assert session.get(Release, "release-rotation-base").status == "released"
            assert session.get(
                KnowledgeRevision,
                "revision-rotation-safe",
            ).status == "released"
            assert session.get(
                KnowledgeRevision,
                "revision-rotation-risk",
            ).status == "released"
    finally:
        engine.dispose()
