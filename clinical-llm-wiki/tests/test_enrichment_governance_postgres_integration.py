"""PostgreSQL acceptance for replay Enrichment and two-person Candidate governance."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
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
    AuditEvent,
    Evidence,
    JobStep,
    KnowledgeCandidate,
    KnowledgeRevision,
    KnowledgeUnit,
    ModelInvocation,
    ModelProfile,
    ProcessingRun,
    PromptProfile,
    Release,
    ReleaseItem,
    Source,
    SourceArtifact,
    SourceVersion,
    StepAttempt,
)
from service.db.session import create_database_engine, create_session_factory
from service.governance import KnowledgeGovernanceService, SqlAlchemyGovernanceRepository
from service.knowledge import (
    AuthorConfirmationCommand,
    CandidateRevisionCommand,
    ReviewDecisionCommand,
)
from service.processing.contracts import ArtifactManifest, StepDefinition, StepOutcome
from service.processing.enrichment import (
    ENRICHMENT_OUTPUT_SCHEMA,
    EnrichmentWorkerService,
    SqlAlchemyEnrichmentRepository,
    enrichment_step_handlers,
)
from service.processing.ledger import PostgresProcessingLedger
from service.processing.model_provider import (
    ModelProfile as ModelProfileContract,
    PromptProfile as PromptProfileContract,
    ReplayMissError,
    ReplayModelProvider,
)
from service.processing.worker import WorkerRuntime
from service.platform_api.repository import SqlAlchemyPlatformRepository


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="KNOWLEDGE_TEST_DATABASE_URL is required for PostgreSQL integration",
)


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _worker(pool: WorkerPool) -> ActorContext:
    return resolve_service_account_actor(
        ServiceAccountGrant(
            service_account_id=f"svc-p2b2-{pool.value}",
            display_name=f"P2-B2 {pool.value.title()} Worker",
            worker_pool=pool,
            scopes=WORKER_POOL_PERMISSIONS[pool],
            secret_ref=f"env://P12_{pool.value.upper()}_WORKER_TOKEN",
            status=GrantStatus.ACTIVE,
        )
    )


def _human(actor_id: str, role: ProductRole) -> ActorContext:
    return ActorContext(
        actor_id=actor_id,
        display_name=actor_id,
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({role}),
        permissions=ROLE_PERMISSIONS[role],
        identity_source=IdentitySource.LOCAL_TEST,
    )


class _CaptureReplayMiss:
    def __init__(self) -> None:
        self.request = None

    def invoke(self, request):
        self.request = request
        raise ReplayMissError("intentional replay miss")


def test_replay_retry_candidate_revision_and_independent_approval_are_durable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setenv("KNOWLEDGE_DATABASE_URL", TEST_DATABASE_URL)
    command.upgrade(Config(ROOT / "alembic.ini"), "head")
    engine = create_database_engine(TEST_DATABASE_URL)
    sessions = create_session_factory(engine)
    suffix = uuid4().hex[:10]
    source_id = f"src-p2b2-{suffix}"
    source_version_id = f"srcv-p2b2-{suffix}"
    run_id = f"run-p2b2-{suffix}"
    evidence_id = f"evidence-p2b2-{suffix}"
    target_unit_id = f"ku-p2b2-ae-{suffix}"
    model_profile_id = f"model-p2b2-{suffix}"
    prompt_profile_id = f"prompt-p2b2-{suffix}"
    source_content = "AESEQ is the sequence identifier within the AE domain."
    source_hash = _digest(source_content)
    model_profile = ModelProfileContract(
        profile_id=model_profile_id,
        version="1.0.0",
        provider="replay",
        model="atomic-candidate",
        deployment_class="enterprise_managed",
        secret_ref="env://P12_ENRICHMENT_WORKER_TOKEN",
        allowed_data_boundaries=["enterprise_provider_only"],
        capabilities=["structured_generation"],
    )
    prompt_profile = PromptProfileContract(
        profile_id=prompt_profile_id,
        version="1.0.0",
        system_template="Extract one evidence-grounded knowledge candidate.",
        output_schema_id="knowledge-candidate.v1",
        output_schema=ENRICHMENT_OUTPUT_SCHEMA,
    )

    try:
        with sessions.begin() as session:
            session.add(
                Source(
                    source_id=source_id,
                    title="P2-B2 replay fixture",
                    source_type="test_fixture",
                )
            )
            session.flush()
            session.add(
                SourceVersion(
                    source_version_id=source_version_id,
                    source_id=source_id,
                    version="1.0",
                    sha256=source_hash,
                    rights={
                        "classification": "internal",
                        "storage_allowed": True,
                        "citation_required": True,
                    },
                    data_boundary="enterprise_provider_only",
                    status="parsed",
                )
            )
            session.flush()
            original_id = f"artifact-original-{suffix}"
            derived_id = f"artifact-derived-{suffix}"
            session.add(
                SourceArtifact(
                    artifact_id=original_id,
                    source_version_id=source_version_id,
                    artifact_kind="original",
                    object_key=f"sources/{source_id}/original.md",
                    sha256=source_hash,
                    media_type="text/markdown",
                    size_bytes=len(source_content),
                    status="available",
                )
            )
            session.flush()
            session.add(
                SourceArtifact(
                    artifact_id=derived_id,
                    source_version_id=source_version_id,
                    artifact_kind="parser_output",
                    parent_artifact_id=original_id,
                    object_key=f"derived/{source_id}/parsed.json",
                    sha256=_digest("parsed"),
                    media_type="application/json",
                    size_bytes=100,
                    parser_profile_version="parser-p2b2-v1",
                    status="available",
                )
            )
            session.flush()
            session.add(
                Evidence(
                    evidence_id=evidence_id,
                    source_version_id=source_version_id,
                    source_artifact_id=original_id,
                    derived_artifact_id=derived_id,
                    source_sha256=source_hash,
                    parser_profile_version="parser-p2b2-v1",
                    evidence_type="paragraph",
                    locator={"section": "AE", "paragraph": 1},
                    locator_sha256=_digest("AE:1"),
                    content=source_content,
                    content_sha256=source_hash,
                    schema_version="evidence.v1",
                )
            )
            session.add(
                KnowledgeUnit(
                    knowledge_unit_id=target_unit_id,
                    stable_key=f"sdtm.ae.{suffix}",
                    knowledge_type="domain",
                )
            )
            session.add(
                ModelProfile(
                    profile_id=model_profile.profile_id,
                    version=model_profile.version,
                    provider=model_profile.provider,
                    model=model_profile.model,
                    deployment_class=model_profile.deployment_class.value,
                    secret_ref=model_profile.secret_ref,
                    endpoint_ref=None,
                    allowed_data_boundaries=[
                        item.value for item in model_profile.allowed_data_boundaries
                    ],
                    capabilities=[item.value for item in model_profile.capabilities],
                    timeout_seconds=model_profile.timeout_seconds,
                    max_output_tokens=model_profile.max_output_tokens,
                    cost_policy=None,
                )
            )
            session.add(
                PromptProfile(
                    profile_id=prompt_profile.profile_id,
                    version=prompt_profile.version,
                    system_template=prompt_profile.system_template,
                    output_schema_id=prompt_profile.output_schema_id,
                    output_schema=prompt_profile.output_schema,
                    output_schema_sha256=prompt_profile.output_schema_sha256,
                )
            )

        ledger = PostgresProcessingLedger(sessions)
        ledger.create_run(
            run_id=run_id,
            source_version_id=source_version_id,
            requested_by_subject=f"usr-author-{suffix}",
            steps=[
                StepDefinition(
                    step_key="document.persist_evidence",
                    pool=WorkerPool.DOCUMENT,
                    input_sha256=source_hash,
                ),
                StepDefinition(
                    step_key="enrichment.extract_candidate",
                    pool=WorkerPool.ENRICHMENT,
                    input_sha256=source_hash,
                    depends_on=["document.persist_evidence"],
                ),
            ],
        )
        document = ledger.claim_next(
            actor=_worker(WorkerPool.DOCUMENT),
            worker_id=f"document-{suffix}",
            supported_step_keys=frozenset({"document.persist_evidence"}),
            lease_seconds=60,
        )
        assert document is not None
        ledger.complete_attempt(
            actor=_worker(WorkerPool.DOCUMENT),
            worker_id=f"document-{suffix}",
            attempt_id=document.attempt_id,
            outcome=StepOutcome(
                output_sha256=source_hash,
                artifact_manifest=ArtifactManifest(),
            ),
        )
        with sessions.begin() as session:
            session.get(ProcessingRun, run_id).status = "evidence_ready"

        governance = KnowledgeGovernanceService(
            repository=SqlAlchemyGovernanceRepository(sessions)
        )
        enrichment_repository = SqlAlchemyEnrichmentRepository(sessions)
        enrichment_actor = _worker(WorkerPool.ENRICHMENT)
        capture = _CaptureReplayMiss()
        failed_runtime = WorkerRuntime(
            ledger=ledger,
            actor=enrichment_actor,
            worker_id=f"enrichment-fail-{suffix}",
            handlers=enrichment_step_handlers(
                EnrichmentWorkerService(
                    repository=enrichment_repository,
                    governance=governance,
                    provider=capture,
                    model_profile=model_profile,
                    prompt_profile=prompt_profile,
                    actor=enrichment_actor,
                )
            ),
            pool=WorkerPool.ENRICHMENT,
        )
        assert failed_runtime.run_once() is True
        assert capture.request is not None
        with sessions() as session:
            enrichment_step = session.scalar(
                select(JobStep).where(
                    JobStep.run_id == run_id,
                    JobStep.step_key == "enrichment.extract_candidate",
                )
            )
            assert enrichment_step is not None
            enrichment_step_id = enrichment_step.step_id
        ledger.retry_step(
            actor=_human(f"usr-author-{suffix}", ProductRole.KNOWLEDGE_CURATOR),
            run_id=run_id,
            step_id=enrichment_step_id,
        )

        output = {
            "candidate_group_id": f"sdtm.ae.aeseq.{suffix}",
            "knowledge_type": "variable_definition",
            "claim": source_content,
            "scope": {"standard": "SDTM", "domain": "AE"},
            "applicability": {"standard_version": "3.4"},
            "conditions": [],
            "exceptions": [],
            "evidence_ids": [evidence_id],
            "relation_proposals": [
                {
                    "relation_type": "applies_to",
                    "target_knowledge_unit_id": target_unit_id,
                    "evidence_ids": [evidence_id],
                }
            ],
            "confidence": 0.99,
        }
        replay_runtime = WorkerRuntime(
            ledger=ledger,
            actor=enrichment_actor,
            worker_id=f"enrichment-replay-{suffix}",
            handlers=enrichment_step_handlers(
                EnrichmentWorkerService(
                    repository=enrichment_repository,
                    governance=governance,
                    provider=ReplayModelProvider(
                        records={capture.request.input_sha256: output}
                    ),
                    model_profile=model_profile,
                    prompt_profile=prompt_profile,
                    actor=enrichment_actor,
                )
            ),
            pool=WorkerPool.ENRICHMENT,
        )
        assert replay_runtime.run_once() is True
        assert replay_runtime.run_once() is False

        with sessions() as session:
            candidates = list(
                session.scalars(
                    select(KnowledgeCandidate).where(KnowledgeCandidate.run_id == run_id)
                )
            )
            assert len(candidates) == 1
            first_candidate_id = candidates[0].candidate_id
            first_hash = candidates[0].content_sha256
            assert session.get(ProcessingRun, run_id).status == "author_confirmation_required"
            assert session.scalar(
                select(func.count(StepAttempt.attempt_id))
                .join(JobStep, JobStep.step_id == StepAttempt.step_id)
                .where(
                    JobStep.run_id == run_id,
                    JobStep.step_key == "document.persist_evidence",
                )
            ) == 1
            assert session.scalar(
                select(func.count(StepAttempt.attempt_id))
                .join(JobStep, JobStep.step_id == StepAttempt.step_id)
                .where(
                    JobStep.run_id == run_id,
                    JobStep.step_key == "enrichment.extract_candidate",
                )
            ) == 2
            invocation = session.scalar(
                select(ModelInvocation).where(ModelInvocation.run_id == run_id)
            )
            assert invocation is not None
            assert invocation.status == "replayed"
            assert invocation.input_sha256 == capture.request.input_sha256

        author = _human(f"usr-author-{suffix}", ProductRole.KNOWLEDGE_CURATOR)
        reviewer = _human(f"usr-reviewer-{suffix}", ProductRole.REVIEWER)
        confirmed = governance.confirm_candidate(
            actor=author,
            command=AuthorConfirmationCommand(
                candidate_id=first_candidate_id,
                expected_revision_number=1,
                expected_content_sha256=first_hash,
                idempotency_key=f"confirm-{suffix}-1",
            ),
        )
        governance.review_revision(
            actor=reviewer,
            command=ReviewDecisionCommand(
                candidate_id=first_candidate_id,
                knowledge_revision_id=confirmed.revision.knowledge_revision_id,
                expected_revision_number=1,
                expected_content_sha256=first_hash,
                decision="changes_requested",
                idempotency_key=f"change-{suffix}-1",
                rationale="Clarify record scope.",
            ),
        )
        revised = governance.revise_candidate(
            actor=author,
            command=CandidateRevisionCommand(
                candidate_id=first_candidate_id,
                expected_revision_number=1,
                expected_content_sha256=first_hash,
                claim="AESEQ identifies records in the SDTM AE domain.",
                scope={"standard": "SDTM", "domain": "AE"},
                applicability={"standard_version": "3.4"},
                conditions=[],
                exceptions=[],
                idempotency_key=f"revise-{suffix}-2",
            ),
        )
        reconfirmed = governance.confirm_candidate(
            actor=author,
            command=AuthorConfirmationCommand(
                candidate_id=revised.candidate_id,
                expected_revision_number=2,
                expected_content_sha256=revised.content_sha256,
                idempotency_key=f"confirm-{suffix}-2",
            ),
        )
        approved = governance.review_revision(
            actor=reviewer,
            command=ReviewDecisionCommand(
                candidate_id=revised.candidate_id,
                knowledge_revision_id=reconfirmed.revision.knowledge_revision_id,
                expected_revision_number=2,
                expected_content_sha256=revised.content_sha256,
                decision="approved",
                idempotency_key=f"approve-{suffix}-2",
                rationale="Evidence and scope verified.",
            ),
        )

        with sessions() as session:
            assert session.get(ProcessingRun, run_id).status == "approved"
            assert session.get(KnowledgeRevision, confirmed.revision.knowledge_revision_id).status == (
                "changes_requested"
            )
            assert session.get(KnowledgeCandidate, first_candidate_id).status == "superseded"
            assert session.get(KnowledgeRevision, approved.revision.knowledge_revision_id).status == (
                "approved"
            )
            assert session.scalar(select(func.count(Release.release_id))) == 0
            assert (
                session.scalar(
                    select(func.count()).select_from(ReleaseItem)
                )
                == 0
            )
            events = list(
                session.scalars(select(AuditEvent).where(AuditEvent.run_id == run_id))
            )
            assert {event.action for event in events} >= {
                "model.invocation.replayed",
                "candidate.created",
                "candidate.author_confirmed",
                "knowledge_revision.changes_requested",
                "candidate.revised",
                "knowledge_revision.approved",
            }
            governed = [
                event
                for event in events
                if event.action.startswith("candidate.")
                or event.action.startswith("knowledge_revision.")
                or event.action.startswith("model.invocation.")
            ]
            assert governed
            for event in governed:
                assert {
                    "permission",
                    "correlation_id",
                    "input_sha256",
                    "output_sha256",
                    "result",
                } <= event.details.keys()
        assert SqlAlchemyPlatformRepository(sessions).get_current_release() is None
    finally:
        engine.dispose()
