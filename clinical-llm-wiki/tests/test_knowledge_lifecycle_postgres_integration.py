"""Opt-in PostgreSQL acceptance for P17 rotation governance transactions."""

from __future__ import annotations

from hashlib import sha256
from importlib import import_module
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
    ChunkProfile,
    ChunkProjectionFinding,
    Evidence,
    EvidenceImpact,
    ImpactAssessment,
    KnowledgeCandidate,
    KnowledgeRevision,
    KnowledgeUnit,
    ProcessingRun,
    Release,
    ReleaseItem,
    RetrievalChunk,
    RetrievalChunkEvidence,
    RotationCase,
    RotationDecisionReceipt,
    Source,
    SourceArtifact,
    SourceVersion,
)
from service.db.session import create_database_engine, create_session_factory
from service.knowledge import (
    RotationDecisionCommand,
    RotationProposalCommand,
    StaleRotationCaseError,
)


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="KNOWLEDGE_TEST_DATABASE_URL is required for PostgreSQL integration",
)


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _actor(actor_id: str, role: ProductRole, permission: Permission) -> ActorContext:
    return ActorContext(
        actor_id=actor_id,
        display_name=actor_id,
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({role}),
        permissions=frozenset({permission}),
        identity_source=IdentitySource.OIDC,
    )


def _seed_rotation_case(session) -> None:
    session.add(Source(source_id="src-p17", title="P17 fixture", source_type="test_fixture"))
    session.flush()
    for number in (1, 2):
        session.add(
            SourceVersion(
                source_version_id=f"srcv-p17-{number}",
                source_id="src-p17",
                version=str(number),
                sha256=_hash(f"source-{number}"),
                rights={"classification": "internal", "storage_allowed": True},
                data_boundary="local_processing_only",
                status="parsed",
            )
        )
    session.flush()
    session.add(
        ProcessingRun(
            run_id="run-p17",
            source_version_id="srcv-p17-1",
            status="approved",
            requested_by_subject="usr-p17-author",
        )
    )
    session.add(
        SourceArtifact(
            artifact_id="artifact-p17-derived-1",
            source_version_id="srcv-p17-1",
            artifact_kind="canonical_source",
            object_key="p17/source-1.md",
            sha256=_hash("source-1"),
            media_type="text/markdown",
            size_bytes=100,
            status="available",
        )
    )
    session.add(
        SourceArtifact(
            artifact_id="artifact-p17-derived-2",
            source_version_id="srcv-p17-2",
            artifact_kind="canonical_source",
            object_key="p17/source-2.md",
            sha256=_hash("source-2"),
            media_type="text/markdown",
            size_bytes=110,
            status="available",
        )
    )
    session.flush()
    for number in (1, 2):
        session.add(
            Evidence(
                evidence_id=f"evidence-p17-{number}",
                source_version_id=f"srcv-p17-{number}",
                derived_artifact_id=f"artifact-p17-derived-{number}",
                source_sha256=_hash(f"source-{number}"),
                parser_profile_version="parser-p17-v1",
                evidence_type="prose",
                locator={"section": "1", "ordinal": number},
                locator_sha256=_hash(f"locator-{number}"),
                content=f"P17 evidence {number}",
                content_sha256=_hash(f"evidence-{number}"),
                schema_version="evidence-v1",
            )
        )
    session.add(
        KnowledgeCandidate(
            candidate_id="candidate-p17-1",
            candidate_group_id="candidate-group-p17",
            run_id="run-p17",
            revision_number=1,
            status="author_confirmed",
            knowledge_type="statistical_principle",
            claim="Original released claim",
            scope={"document": "E9"},
            applicability={"version": "1"},
            conditions=[],
            exceptions=[],
            advisory_signals=[],
            content_sha256=_hash("revision-1"),
            author_actor_id="usr-p17-author",
        )
    )
    session.add(
        KnowledgeCandidate(
            candidate_id="candidate-p17-2",
            candidate_group_id="candidate-group-p17-next",
            run_id="run-p17",
            revision_number=1,
            status="author_confirmed",
            knowledge_type="statistical_principle",
            claim="Replacement claim",
            scope={"document": "E9"},
            applicability={"version": "2"},
            conditions=[],
            exceptions=[],
            advisory_signals=[],
            content_sha256=_hash("revision-2"),
            author_actor_id="usr-p17-author",
        )
    )
    session.flush()
    session.add(
        CandidateEvidence(
            candidate_id="candidate-p17-1",
            evidence_id="evidence-p17-1",
            evidence_role="supports",
        )
    )
    session.add(KnowledgeUnit(knowledge_unit_id="unit-p17-1", stable_key="p17.unit.1", knowledge_type="statistical_principle"))
    session.add(KnowledgeUnit(knowledge_unit_id="unit-p17-2", stable_key="p17.unit.2", knowledge_type="statistical_principle"))
    session.flush()
    session.add(
        KnowledgeRevision(
            knowledge_revision_id="revision-p17-1",
            knowledge_unit_id="unit-p17-1",
            candidate_id="candidate-p17-1",
            revision_number=1,
            status="released",
            claim="Original released claim",
            scope={"document": "E9"},
            applicability={"version": "1"},
            conditions=[],
            exceptions=[],
            content_sha256=_hash("revision-1"),
            author_actor_id="usr-p17-author",
        )
    )
    session.add(
        KnowledgeRevision(
            knowledge_revision_id="revision-p17-2",
            knowledge_unit_id="unit-p17-2",
            candidate_id="candidate-p17-2",
            revision_number=1,
            status="approved",
            claim="Replacement claim",
            scope={"document": "E9"},
            applicability={"version": "2"},
            conditions=[],
            exceptions=[],
            content_sha256=_hash("revision-2"),
            author_actor_id="usr-p17-author",
        )
    )
    session.flush()
    session.add(
        Release(
            release_id="release-p17-1",
            version="p17.1",
            status="released",
            manifest_object_key="p17/release.json",
            manifest_sha256=_hash("manifest"),
            db_schema_revision="20260816_0011",
            knowledge_contract_version="p17-v1",
            parser_profile_version="parser-p17-v1",
            model_profile_version="replay-v1",
            prompt_profile_version="prompt-v1",
            index_manifest_version="index-v1",
            release_manager_subject="usr-p17-release",
        )
    )
    session.add(
        ReleaseItem(
            release_id="release-p17-1",
            knowledge_revision_id="revision-p17-1",
            content_sha256=_hash("revision-1"),
        )
    )
    session.add(
        ImpactAssessment(
            assessment_id="impact-p17-1",
            from_source_version_id="srcv-p17-1",
            to_source_version_id="srcv-p17-2",
            comparison_profile_version="comparison-p17-v1",
        )
    )
    session.flush()
    session.add(
        EvidenceImpact(
            evidence_impact_id="evidence-impact-p17-1",
            assessment_id="impact-p17-1",
            change_type="modified",
            from_evidence_id="evidence-p17-1",
            to_evidence_id="evidence-p17-2",
            mapping_basis="ordered_alignment",
            details={"reason": "content_changed"},
        )
    )
    session.add(
        RotationCase(
            rotation_case_id="rotation-p17-1",
            impact_assessment_id="impact-p17-1",
            knowledge_revision_id="revision-p17-1",
            status="open",
            case_version=1,
        )
    )
    session.add(
        ChunkProfile(
            chunk_profile_id="chunk-profile-p17-v1",
            version="p17-v1",
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
        RetrievalChunk(
            chunk_id="chunk-p17-1",
            chunk_profile_id="chunk-profile-p17-v1",
            source_version_id="srcv-p17-1",
            evidence_type="prose",
            ordinal=0,
            content="P17 evidence 1",
            content_sha256=_hash("P17 evidence 1"),
            token_count=3,
            locator={"majorSection": "1"},
            data_boundary="local_processing_only",
            rights={"classification": "internal", "storage_allowed": True},
        )
    )
    session.flush()
    session.add(
        RetrievalChunkEvidence(
            chunk_id="chunk-p17-1",
            position=0,
            evidence_id="evidence-p17-1",
            start_offset=0,
            end_offset=len("P17 evidence 1"),
            span_role="primary",
        )
    )
    session.add(
        ChunkProjectionFinding(
            finding_id="finding-p17-1",
            chunk_profile_id="chunk-profile-p17-v1",
            source_version_id="srcv-p17-1",
            evidence_id=None,
            finding_type="empty",
            details={"count": 1},
        )
    )


def test_postgres_rotation_is_role_scoped_idempotent_stale_safe_and_append_only() -> None:
    assert TEST_DATABASE_URL is not None
    repository_module = import_module("service.platform_api.repository")
    repository_type = getattr(
        repository_module,
        "SqlAlchemyKnowledgeLifecycleRepository",
        None,
    )
    assert repository_type is not None, "P17 lifecycle PostgreSQL repository is missing"

    os.environ["KNOWLEDGE_DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(Config(ROOT / "alembic.ini"), "head")
    engine = create_database_engine(TEST_DATABASE_URL)
    sessions = create_session_factory(engine)
    curator = _actor(
        "usr-p17-author",
        ProductRole.KNOWLEDGE_CURATOR,
        Permission.CANDIDATE_WRITE,
    )
    reviewer = _actor(
        "usr-p17-reviewer",
        ProductRole.REVIEWER,
        Permission.REVIEW_DECIDE,
    )

    try:
        with sessions.begin() as session:
            _seed_rotation_case(session)
        repository = repository_type(sessions)

        assessment = repository.get_impact_assessment(assessment_id="impact-p17-1")
        assert assessment is not None
        assert assessment.impacts[0].change_type == "modified"
        projection = repository.get_chunk_projection(run_id="run-p17")
        assert projection is not None
        assert projection.profile.version == "p17-v1"
        assert projection.chunks[0].data_boundary == "local_processing_only"
        assert projection.chunks[0].spans[0].evidence_id == "evidence-p17-1"
        assert projection.findings[0].finding_type == "empty"

        initial = repository.get_rotation_case(rotation_case_id="rotation-p17-1")
        assert initial is not None
        assert initial.change_types == ("modified",)
        assert initial.released_in_release_ids == ("release-p17-1",)

        proposal = RotationProposalCommand(
            rotation_case_id="rotation-p17-1",
            expected_case_version=1,
            outcome="replace",
            target_knowledge_revision_id="revision-p17-2",
            idempotency_key="rotation-proposal-p17-1",
            rationale="Evidence changed.",
        )
        proposed = repository.propose_rotation_case(actor=curator, command=proposal)
        replayed_proposal = repository.propose_rotation_case(
            actor=curator,
            command=proposal,
        )
        assert proposed == replayed_proposal
        assert proposed.status == "in_review"
        assert proposed.case_version == 2

        with pytest.raises(StaleRotationCaseError):
            repository.propose_rotation_case(
                actor=curator,
                command=proposal.model_copy(
                    update={"idempotency_key": "rotation-proposal-p17-stale"}
                ),
            )

        decision = RotationDecisionCommand(
            rotation_case_id="rotation-p17-1",
            expected_case_version=2,
            outcome="replace",
            target_knowledge_revision_id="revision-p17-2",
            idempotency_key="rotation-decision-p17-1",
            rationale="Replacement is supported.",
        )
        decided, receipt = repository.decide_rotation_case(
            actor=reviewer,
            command=decision,
        )
        replayed_case, replayed_receipt = repository.decide_rotation_case(
            actor=reviewer,
            command=decision,
        )
        assert (decided, receipt) == (replayed_case, replayed_receipt)
        assert decided.status == "decided"
        assert decided.case_version == 3
        assert receipt.actor_role == "reviewer"

        with pytest.raises(StaleRotationCaseError):
            repository.decide_rotation_case(
                actor=reviewer,
                command=decision.model_copy(
                    update={"idempotency_key": "rotation-decision-p17-stale"}
                ),
            )

        with sessions() as session:
            assert session.scalar(select(func.count()).select_from(RotationDecisionReceipt)) == 1
            assert session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.entity_id == "rotation-p17-1")
            ) == 2
            assert session.get(KnowledgeRevision, "revision-p17-1").status == "released"
            assert session.get(Release, "release-p17-1").status == "released"
    finally:
        engine.dispose()
