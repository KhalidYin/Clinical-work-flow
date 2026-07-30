"""Opt-in PostgreSQL acceptance test for P2-B1 governance transactions."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from alembic import command
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
    AuditEvent,
    CandidateRelationProposal,
    Evidence,
    KnowledgeCandidate,
    KnowledgeRevision,
    KnowledgeUnit,
    ProcessingRun,
    RelationProposalEvidence,
    ReviewDecision,
    Source,
    SourceArtifact,
    SourceVersion,
)
from service.db.session import create_database_engine, create_session_factory
from service.governance.repository import SqlAlchemyGovernanceRepository
from service.governance.service import (
    DuplicateDecisionError,
    KnowledgeGovernanceService,
    StaleRevisionError,
)
from service.knowledge import (
    AuthorConfirmationCommand,
    KnowledgeCandidateDraft,
    ReviewDecisionCommand,
)


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="KNOWLEDGE_TEST_DATABASE_URL is required for PostgreSQL integration",
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _actor(
    actor_id: str,
    *,
    role: ProductRole,
    permissions: set[Permission],
) -> ActorContext:
    return ActorContext(
        actor_id=actor_id,
        display_name=actor_id,
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({role}),
        permissions=frozenset(permissions),
        identity_source=IdentitySource.OIDC,
    )


def _seed_evidence(session) -> None:
    session.add(
        Source(
            source_id="src-gov-sdtm",
            title="Governance SDTM fixture",
            source_type="test_fixture",
        )
    )
    session.flush()
    source_hash = _hash("governance-source")
    session.add(
        SourceVersion(
            source_version_id="srcv-gov-sdtm-34",
            source_id="src-gov-sdtm",
            version="3.4",
            sha256=source_hash,
            rights={
                "classification": "licensed",
                "storage_allowed": True,
                "citation_required": True,
            },
            data_boundary="local_processing_only",
            status="parsed",
        )
    )
    session.flush()
    session.add(
        ProcessingRun(
            run_id="run-gov-ae",
            source_version_id="srcv-gov-sdtm-34",
            status="evidence_ready",
            requested_by_subject="usr-gov-author",
        )
    )
    original_id = "artifact-gov-original"
    derived_id = "artifact-gov-derived"
    session.add(
        SourceArtifact(
            artifact_id=original_id,
            source_version_id="srcv-gov-sdtm-34",
            artifact_kind="original",
            object_key="sources/src-gov-sdtm/original.md",
            sha256=source_hash,
            media_type="text/markdown",
            size_bytes=100,
            status="available",
        )
    )
    session.flush()
    session.add(
        SourceArtifact(
            artifact_id=derived_id,
            source_version_id="srcv-gov-sdtm-34",
            artifact_kind="parser_output",
            parent_artifact_id=original_id,
            object_key="sources/src-gov-sdtm/parsed.json",
            sha256=_hash("parsed"),
            media_type="application/json",
            size_bytes=200,
            parser_profile_version="parser-test-v1",
            status="available",
        )
    )
    session.flush()
    content = "AESEQ is the sequence identifier within the AE domain."
    session.add(
        Evidence(
            evidence_id="ev-gov-ae-1",
            source_version_id="srcv-gov-sdtm-34",
            source_artifact_id=original_id,
            derived_artifact_id=derived_id,
            source_sha256=source_hash,
            parser_profile_version="parser-test-v1",
            evidence_type="paragraph",
            locator={"page": 35, "section": "6.2 AE"},
            locator_sha256=_hash("35:6.2 AE"),
            content=content,
            content_sha256=_hash(content),
            schema_version="1",
        )
    )
    session.add(
        KnowledgeUnit(
            knowledge_unit_id="ku-gov-sdtm-ae",
            stable_key="sdtm.ae",
            knowledge_type="domain",
        )
    )


def _draft() -> KnowledgeCandidateDraft:
    return KnowledgeCandidateDraft(
        candidate_group_id="candgrp-gov-aeseq",
        run_id="run-gov-ae",
        revision_number=1,
        knowledge_type="variable_definition",
        claim="AESEQ is the sequence identifier within the AE domain.",
        scope={"standard": "SDTM", "domain": "AE"},
        applicability={"standard_version": "3.4"},
        evidence=[
            {
                "evidence_id": "ev-gov-ae-1",
                "source_version_id": "srcv-gov-sdtm-34",
                "locator": {"page": 35, "section": "6.2 AE"},
                "content_sha256": _hash("AESEQ is the sequence identifier within the AE domain."),
                "rights": {
                    "classification": "licensed",
                    "storage_allowed": True,
                    "citation_required": True,
                },
            }
        ],
        relation_proposals=[
            {
                "relation_type": "applies_to",
                "target_knowledge_unit_id": "ku-gov-sdtm-ae",
                "evidence_ids": ["ev-gov-ae-1"],
            }
        ],
    )


def test_governance_transitions_are_atomic_and_append_only(
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
            _seed_evidence(session)

        service = KnowledgeGovernanceService(repository=SqlAlchemyGovernanceRepository(sessions))
        enrichment = ActorContext(
            actor_id="svc-gov-enrichment",
            display_name="Enrichment worker",
            principal_type=PrincipalType.SERVICE_ACCOUNT,
            roles=frozenset({ProductRole.SERVICE_ACCOUNT}),
            permissions=frozenset({Permission.CANDIDATE_WRITE, Permission.RELATION_PROPOSE}),
            worker_pool=WorkerPool.ENRICHMENT,
        )
        author = _actor(
            "usr-gov-author",
            role=ProductRole.KNOWLEDGE_CURATOR,
            permissions={Permission.CANDIDATE_SUBMIT},
        )
        reviewer = _actor(
            "usr-gov-reviewer",
            role=ProductRole.REVIEWER,
            permissions={Permission.REVIEW_DECIDE},
        )

        candidate = service.register_candidate(actor=enrichment, draft=_draft())
        with sessions() as session:
            assert session.get(ProcessingRun, "run-gov-ae").status == (
                "author_confirmation_required"
            )
            stored = session.get(KnowledgeCandidate, candidate.candidate_id)
            assert stored is not None
            assert stored.content_sha256 == candidate.content_sha256
            proposal = session.scalar(
                select(CandidateRelationProposal).where(
                    CandidateRelationProposal.candidate_id == candidate.candidate_id
                )
            )
            assert proposal is not None
            assert proposal.target_knowledge_unit_id == "ku-gov-sdtm-ae"
            assert (
                session.scalar(
                    select(RelationProposalEvidence).where(
                        RelationProposalEvidence.proposal_id == proposal.proposal_id
                    )
                )
                is not None
            )

        confirmation_command = AuthorConfirmationCommand(
            candidate_id=candidate.candidate_id,
            expected_revision_number=1,
            expected_content_sha256=candidate.content_sha256,
            idempotency_key="pg-author-confirm-ae-1",
        )
        confirmation = service.confirm_candidate(
            actor=author,
            command=confirmation_command,
        )
        with pytest.raises(DuplicateDecisionError):
            service.confirm_candidate(actor=author, command=confirmation_command)
        with pytest.raises(StaleRevisionError):
            service.review_revision(
                actor=reviewer,
                command=ReviewDecisionCommand(
                    candidate_id=candidate.candidate_id,
                    knowledge_revision_id=confirmation.revision.knowledge_revision_id,
                    expected_revision_number=2,
                    expected_content_sha256=confirmation.revision.content_sha256,
                    decision="approved",
                    idempotency_key="pg-review-stale-ae-1",
                ),
            )

        approval = service.review_revision(
            actor=reviewer,
            command=ReviewDecisionCommand(
                candidate_id=candidate.candidate_id,
                knowledge_revision_id=confirmation.revision.knowledge_revision_id,
                expected_revision_number=1,
                expected_content_sha256=confirmation.revision.content_sha256,
                decision="approved",
                idempotency_key="pg-review-approve-ae-1",
            ),
        )

        with sessions() as session:
            assert session.get(ProcessingRun, "run-gov-ae").status == "approved"
            assert (
                session.get(
                    KnowledgeRevision,
                    approval.revision.knowledge_revision_id,
                ).status
                == "approved"
            )
            decisions = list(
                session.scalars(
                    select(ReviewDecision)
                    .where(ReviewDecision.candidate_id == candidate.candidate_id)
                    .order_by(ReviewDecision.created_at)
                )
            )
            assert [decision.decision for decision in decisions] == [
                "author_confirmed",
                "approved",
            ]
            assert all(
                decision.content_sha256 == candidate.content_sha256 for decision in decisions
            )
            events = list(
                session.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.run_id == "run-gov-ae")
                    .order_by(AuditEvent.created_at, AuditEvent.audit_event_id)
                )
            )
            assert {event.action for event in events} >= {
                "candidate.created",
                "candidate.author_confirmed",
                "knowledge_revision.approved",
            }
    finally:
        engine.dispose()
