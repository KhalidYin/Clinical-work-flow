"""Read models and PostgreSQL adapter for prerelease platform routes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from service.auth import PlatformUserGrant
from service.db.models import (
    AuditEvent,
    CandidateEvidence,
    CandidateRelationProposal,
    Evidence,
    JobStep,
    KnowledgeCandidate,
    KnowledgeRelation,
    KnowledgeRevision,
    KnowledgeUnit,
    ModelProfile,
    PlatformUser,
    ProcessingRun,
    Release,
    ReleaseItem,
    RelationProposalEvidence,
    RoleBinding,
    Source,
    SourceArtifact,
    SourceVersion,
    StepAttempt,
)


@dataclass(frozen=True, slots=True)
class CurrentReleaseRecord:
    release_id: str
    version: str
    status: str
    index_version: str
    released_at: datetime | None


@dataclass(frozen=True, slots=True)
class SourceSummaryRecord:
    source_id: str
    title: str
    version: str
    media_type: str
    rights: str
    status: str
    source_hash: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PlatformUserRecord:
    user_id: str
    display_name: str
    email: str
    identity_source: str
    roles: tuple[str, ...]
    status: str
    last_active_at: datetime | None


@dataclass(frozen=True, slots=True)
class ModelProfileRecord:
    profile_id: str
    version: str
    provider: str
    model: str
    deployment_class: str
    secret_ref: str
    endpoint_ref: str | None
    allowed_data_boundaries: tuple[str, ...]
    capabilities: tuple[str, ...]
    timeout_seconds: int
    max_output_tokens: int
    cost_policy: dict[str, object] | None
    created_at: datetime


class ModelProfileConflictError(RuntimeError):
    """An immutable profile ID/version already exists with different facts."""


@dataclass(frozen=True, slots=True)
class ProcessingAttemptRecord:
    attempt_id: str
    attempt_number: int
    status: str
    error_type: str | None
    checkpoint: dict[str, object] | None
    artifact_count: int


@dataclass(frozen=True, slots=True)
class ProcessingStepRecord:
    step_id: str
    step_key: str
    pool: str
    status: str
    depends_on: tuple[str, ...]
    latest_attempt: ProcessingAttemptRecord


@dataclass(frozen=True, slots=True)
class ProcessingRunRecord:
    run_id: str
    source_version_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    original_artifact_count: int
    derived_artifact_count: int
    evidence_count: int
    steps: tuple[ProcessingStepRecord, ...]


@dataclass(frozen=True, slots=True)
class CandidateSummaryRecord:
    candidate_id: str
    candidate_group_id: str
    run_id: str
    revision_number: int
    status: str
    knowledge_type: str
    claim: str
    scope: dict[str, object]
    applicability: dict[str, object]
    content_sha256: str
    evidence_count: int
    relation_proposal_count: int
    author_actor_id: str | None
    knowledge_revision_id: str | None
    review_status: str | None


@dataclass(frozen=True, slots=True)
class CandidateEvidenceRecord:
    evidence_id: str
    source_version_id: str
    locator: dict[str, object]
    content: str
    content_sha256: str
    rights: dict[str, object]


@dataclass(frozen=True, slots=True)
class CandidateRelationProposalRecord:
    relation_type: str
    target_knowledge_unit_id: str
    evidence_ids: tuple[str, ...]
    status: str


@dataclass(frozen=True, slots=True)
class CandidateAdvisorySignalRecord:
    signal_type: str
    description: str
    target_knowledge_unit_id: str | None
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateDetailRecord(CandidateSummaryRecord):
    parent_candidate_id: str | None
    conditions: tuple[dict[str, object], ...]
    exceptions: tuple[dict[str, object], ...]
    evidence: tuple[CandidateEvidenceRecord, ...]
    relation_proposals: tuple[CandidateRelationProposalRecord, ...]
    advisory_signals: tuple[CandidateAdvisorySignalRecord, ...]
    origin_model_invocation_id: str | None


@dataclass(frozen=True, slots=True)
class RelationEvidenceRecord:
    evidence_id: str
    source_version_id: str
    locator: dict[str, object]
    content: str
    content_sha256: str


@dataclass(frozen=True, slots=True)
class RelationNodeRecord:
    knowledge_unit_id: str
    stable_key: str
    knowledge_type: str
    knowledge_revision_id: str | None
    revision_number: int | None
    status: str
    claim: str | None
    release_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RelationEdgeRecord:
    relation_id: str
    source_knowledge_unit_id: str
    target_knowledge_unit_id: str
    relation_type: str
    status: str
    evidence: tuple[RelationEvidenceRecord, ...]


@dataclass(frozen=True, slots=True)
class RelationQueryRecord:
    root_node_id: str | None
    requested_depth: int
    applied_depth: int
    nodes: tuple[RelationNodeRecord, ...]
    edges: tuple[RelationEdgeRecord, ...]
    total_nodes: int
    truncated: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AuditVersionRecord:
    revision_number: int | None
    content_sha256: str | None


@dataclass(frozen=True, slots=True)
class AuditEventRecord:
    audit_event_id: str
    actor_id: str
    action: str
    object_type: str
    object_id: str
    run_id: str | None
    before_version: AuditVersionRecord | None
    after_version: AuditVersionRecord | None
    result: str | None
    correlation_id: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AuditEventPageRecord:
    items: tuple[AuditEventRecord, ...]
    total: int
    next_cursor: str | None
    warnings: tuple[str, ...]


class PlatformReadRepository(Protocol):
    def resolve_user(self, *, issuer: str, subject: str) -> PlatformUserGrant | None: ...

    def database_available(self) -> bool: ...

    def get_current_release(self) -> CurrentReleaseRecord | None: ...

    def list_sources(self) -> tuple[Sequence[SourceSummaryRecord], Sequence[str]]: ...

    def list_platform_users(
        self,
    ) -> tuple[Sequence[PlatformUserRecord], Sequence[str]]: ...

    def list_model_profiles(
        self,
    ) -> tuple[Sequence[ModelProfileRecord], Sequence[str]]: ...

    def register_model_profile(
        self,
        *,
        profile_id: str,
        version: str,
        provider: str,
        model: str,
        deployment_class: str,
        secret_ref: str,
        endpoint_ref: str | None,
        allowed_data_boundaries: Sequence[str],
        capabilities: Sequence[str],
        timeout_seconds: int,
        max_output_tokens: int,
        cost_policy: dict[str, object] | None,
        actor_id: str,
        correlation_id: str,
    ) -> tuple[ModelProfileRecord, bool]: ...

    def list_processing_runs(
        self,
    ) -> tuple[Sequence[ProcessingRunRecord], Sequence[str]]: ...

    def get_processing_run(self, *, run_id: str) -> ProcessingRunRecord | None: ...

    def list_candidates(
        self,
    ) -> tuple[Sequence[CandidateSummaryRecord], Sequence[str]]: ...

    def get_candidate_detail(self, *, candidate_id: str) -> CandidateDetailRecord | None: ...

    def query_relations(
        self,
        *,
        node_id: str | None,
        query: str | None,
        depth: int,
    ) -> RelationQueryRecord: ...

    def list_audit_events(
        self,
        *,
        actor: str | None,
        action: str | None,
        object_type: str | None,
        result: str | None,
        cursor: str | None,
        limit: int,
    ) -> AuditEventPageRecord: ...


class SqlAlchemyPlatformRepository:
    """API adapter over canonical reads and the bounded ModelProfile registry."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def resolve_user(self, *, issuer: str, subject: str) -> PlatformUserGrant | None:
        with self._session_factory() as session:
            user = session.scalar(
                select(PlatformUser).where(
                    PlatformUser.issuer == issuer,
                    PlatformUser.subject == subject,
                )
            )
            if user is None:
                return None
            roles = tuple(
                session.scalars(
                    select(RoleBinding.role)
                    .where(RoleBinding.user_id == user.user_id)
                    .order_by(RoleBinding.role)
                )
            )
        if not roles:
            return None
        return PlatformUserGrant(
            user_id=user.user_id,
            identity_source=user.identity_source,
            issuer=user.issuer,
            subject=user.subject,
            display_name=user.display_name,
            email=user.email,
            status=user.status,
            roles=roles,
        )

    def database_available(self) -> bool:
        try:
            with self._session_factory() as session:
                session.execute(select(1)).scalar_one()
        except SQLAlchemyError:
            return False
        return True

    def get_current_release(self) -> CurrentReleaseRecord | None:
        with self._session_factory() as session:
            release = session.scalar(
                select(Release)
                .where(Release.status == "released")
                .order_by(Release.published_at.desc().nullslast(), Release.created_at.desc())
                .limit(1)
            )
        if release is None:
            return None
        return CurrentReleaseRecord(
            release_id=release.release_id,
            version=release.version,
            status="released",
            index_version=release.index_manifest_version,
            released_at=release.published_at,
        )

    def list_sources(self) -> tuple[list[SourceSummaryRecord], list[str]]:
        with self._session_factory() as session:
            sources = list(session.scalars(select(Source).order_by(Source.title, Source.source_id)))
            versions = list(
                session.scalars(
                    select(SourceVersion).order_by(
                        SourceVersion.source_id,
                        SourceVersion.created_at.desc(),
                    )
                )
            )
            artifacts = list(
                session.scalars(
                    select(SourceArtifact)
                    .where(SourceArtifact.artifact_kind.in_(("original", "canonical_source")))
                    .order_by(
                        SourceArtifact.source_version_id,
                        SourceArtifact.created_at.desc(),
                    )
                )
            )

        version_by_source: dict[str, SourceVersion] = {}
        for version in versions:
            version_by_source.setdefault(version.source_id, version)
        artifact_by_version: dict[str, SourceArtifact] = {}
        for artifact in artifacts:
            artifact_by_version.setdefault(artifact.source_version_id, artifact)

        items: list[SourceSummaryRecord] = []
        warnings: list[str] = []
        for source in sources:
            version = version_by_source.get(source.source_id)
            artifact = (
                artifact_by_version.get(version.source_version_id) if version is not None else None
            )
            if version is None or artifact is None:
                warnings.append(f"source {source.source_id} has no complete version artifact")
                continue
            media_type = _media_type_label(artifact.media_type, artifact.object_key)
            rights = _rights_label(version.rights)
            status = _source_status_label(version.status)
            if media_type is None or rights is None or status is None:
                warnings.append(
                    f"source {source.source_id} has unsupported media, rights or status"
                )
                continue
            items.append(
                SourceSummaryRecord(
                    source_id=source.source_id,
                    title=source.title,
                    version=version.version,
                    media_type=media_type,
                    rights=rights,
                    status=status,
                    source_hash=version.sha256,
                    updated_at=version.created_at,
                )
            )
        return items, warnings

    def list_platform_users(self) -> tuple[list[PlatformUserRecord], list[str]]:
        with self._session_factory() as session:
            users = list(
                session.scalars(
                    select(PlatformUser).order_by(
                        PlatformUser.display_name,
                        PlatformUser.user_id,
                    )
                )
            )
            bindings = list(
                session.execute(
                    select(RoleBinding.user_id, RoleBinding.role).order_by(
                        RoleBinding.user_id,
                        RoleBinding.role,
                    )
                )
            )
        roles_by_user: dict[str, list[str]] = {}
        for user_id, role in bindings:
            roles_by_user.setdefault(user_id, []).append(role)

        items: list[PlatformUserRecord] = []
        warnings: list[str] = []
        for user in users:
            roles = tuple(roles_by_user.get(user.user_id, []))
            if not roles:
                warnings.append(f"user {user.user_id} has no product role")
                continue
            items.append(
                PlatformUserRecord(
                    user_id=user.user_id,
                    display_name=user.display_name,
                    email=user.email,
                    identity_source=user.identity_source,
                    roles=roles,
                    status=user.status,
                    last_active_at=user.last_authenticated_at,
                )
            )
        return items, warnings

    def list_model_profiles(self) -> tuple[list[ModelProfileRecord], list[str]]:
        with self._session_factory() as session:
            profiles = list(
                session.scalars(
                    select(ModelProfile).order_by(
                        ModelProfile.provider,
                        ModelProfile.model,
                        ModelProfile.profile_id,
                        ModelProfile.version,
                    )
                )
            )
        return [_model_profile_record(profile) for profile in profiles], []

    def register_model_profile(
        self,
        *,
        profile_id: str,
        version: str,
        provider: str,
        model: str,
        deployment_class: str,
        secret_ref: str,
        endpoint_ref: str | None,
        allowed_data_boundaries: Sequence[str],
        capabilities: Sequence[str],
        timeout_seconds: int,
        max_output_tokens: int,
        cost_policy: dict[str, object] | None,
        actor_id: str,
        correlation_id: str,
    ) -> tuple[ModelProfileRecord, bool]:
        desired = {
            "provider": provider,
            "model": model,
            "deployment_class": deployment_class,
            "secret_ref": secret_ref,
            "endpoint_ref": endpoint_ref,
            "allowed_data_boundaries": sorted(set(allowed_data_boundaries)),
            "capabilities": sorted(set(capabilities)),
            "timeout_seconds": timeout_seconds,
            "max_output_tokens": max_output_tokens,
            "cost_policy": cost_policy,
        }
        with self._session_factory.begin() as session:
            existing = session.get(ModelProfile, (profile_id, version))
            if existing is not None:
                if _model_profile_facts(existing) != desired:
                    raise ModelProfileConflictError(
                        "model profile ID/version already exists with different configuration"
                    )
                return _model_profile_record(existing), False

            profile = ModelProfile(
                profile_id=profile_id,
                version=version,
                **desired,
            )
            session.add(profile)
            session.flush()
            session.add(
                AuditEvent(
                    audit_event_id=f"audit-{uuid5(NAMESPACE_URL, f'model-profile:{profile_id}:{version}').hex}",
                    actor_subject=actor_id,
                    action="model_profile.registered",
                    entity_type="model_profile",
                    entity_id=f"{profile_id}@{version}",
                    run_id=None,
                    details={
                        "provider": provider,
                        "model": model,
                        "deployment_class": deployment_class,
                        "result": "registered_not_verified",
                        "correlation_id": correlation_id,
                    },
                )
            )
            session.flush()
            return _model_profile_record(profile), True

    def list_processing_runs(self) -> tuple[list[ProcessingRunRecord], list[str]]:
        with self._session_factory() as session:
            runs = list(
                session.scalars(
                    select(ProcessingRun)
                    .order_by(ProcessingRun.created_at.desc(), ProcessingRun.run_id)
                    .limit(100)
                )
            )
        records: list[ProcessingRunRecord] = []
        warnings: list[str] = []
        for run in runs:
            record = self.get_processing_run(run_id=run.run_id)
            if record is None:
                warnings.append(f"processing run {run.run_id} disappeared during read")
            else:
                records.append(record)
        return records, warnings

    def get_processing_run(self, *, run_id: str) -> ProcessingRunRecord | None:
        with self._session_factory() as session:
            run = session.get(ProcessingRun, run_id)
            if run is None:
                return None
            steps = list(
                session.scalars(
                    select(JobStep)
                    .where(JobStep.run_id == run_id)
                    .order_by(JobStep.created_at, JobStep.step_key)
                )
            )
            attempts = list(
                session.scalars(
                    select(StepAttempt)
                    .where(StepAttempt.run_id == run_id)
                    .order_by(
                        StepAttempt.step_id,
                        StepAttempt.attempt_number.desc(),
                    )
                )
            )
            artifacts = list(
                session.scalars(
                    select(SourceArtifact).where(
                        SourceArtifact.source_version_id == run.source_version_id
                    )
                )
            )
            evidence_count = len(
                list(
                    session.scalars(
                        select(Evidence.evidence_id).where(
                            Evidence.source_version_id == run.source_version_id
                        )
                    )
                )
            )
        latest_by_step: dict[str, StepAttempt] = {}
        for attempt in attempts:
            latest_by_step.setdefault(attempt.step_id, attempt)
        step_records: list[ProcessingStepRecord] = []
        for step in steps:
            attempt = latest_by_step.get(step.step_id)
            if attempt is None:
                continue
            manifest = attempt.artifact_manifest or {}
            manifest_artifacts = manifest.get("artifacts", [])
            step_records.append(
                ProcessingStepRecord(
                    step_id=step.step_id,
                    step_key=step.step_key,
                    pool=step.pool,
                    status=step.status,
                    depends_on=tuple(step.depends_on or ()),
                    latest_attempt=ProcessingAttemptRecord(
                        attempt_id=attempt.attempt_id,
                        attempt_number=attempt.attempt_number,
                        status=attempt.status,
                        error_type=attempt.error_type,
                        checkpoint=attempt.checkpoint,
                        artifact_count=(
                            len(manifest_artifacts) if isinstance(manifest_artifacts, list) else 0
                        ),
                    ),
                )
            )
        return ProcessingRunRecord(
            run_id=run.run_id,
            source_version_id=run.source_version_id,
            status=run.status,
            created_at=run.created_at,
            updated_at=run.updated_at,
            original_artifact_count=sum(
                artifact.artifact_kind in {"original", "canonical_source"} for artifact in artifacts
            ),
            derived_artifact_count=sum(
                artifact.artifact_kind == "parser_output" for artifact in artifacts
            ),
            evidence_count=evidence_count,
            steps=tuple(step_records),
        )

    def list_candidates(self) -> tuple[list[CandidateSummaryRecord], list[str]]:
        with self._session_factory() as session:
            candidates = list(
                session.scalars(
                    select(KnowledgeCandidate)
                    .order_by(
                        KnowledgeCandidate.updated_at.desc(),
                        KnowledgeCandidate.candidate_id,
                    )
                    .limit(100)
                )
            )
            records: list[CandidateSummaryRecord] = []
            warnings: list[str] = []
            for candidate in candidates:
                if (
                    candidate.candidate_group_id is None
                    or candidate.content_sha256 is None
                    or candidate.applicability is None
                ):
                    warnings.append(
                        f"candidate {candidate.candidate_id} lacks P2-B1 governance facts"
                    )
                    continue
                evidence_count = session.scalar(
                    select(func.count(CandidateEvidence.evidence_id)).where(
                        CandidateEvidence.candidate_id == candidate.candidate_id
                    )
                )
                proposal_count = session.scalar(
                    select(func.count(CandidateRelationProposal.proposal_id)).where(
                        CandidateRelationProposal.candidate_id == candidate.candidate_id
                    )
                )
                revision = session.scalar(
                    select(KnowledgeRevision)
                    .where(KnowledgeRevision.candidate_id == candidate.candidate_id)
                    .order_by(KnowledgeRevision.revision_number.desc())
                    .limit(1)
                )
                records.append(
                    CandidateSummaryRecord(
                        candidate_id=candidate.candidate_id,
                        candidate_group_id=candidate.candidate_group_id,
                        run_id=candidate.run_id,
                        revision_number=candidate.revision_number,
                        status=candidate.status,
                        knowledge_type=candidate.knowledge_type,
                        claim=candidate.claim,
                        scope=candidate.scope,
                        applicability=candidate.applicability,
                        content_sha256=candidate.content_sha256,
                        evidence_count=evidence_count or 0,
                        relation_proposal_count=proposal_count or 0,
                        author_actor_id=candidate.author_actor_id,
                        knowledge_revision_id=(
                            revision.knowledge_revision_id if revision is not None else None
                        ),
                        review_status=(revision.status if revision is not None else None),
                    )
                )
        return records, warnings

    def get_candidate_detail(self, *, candidate_id: str) -> CandidateDetailRecord | None:
        with self._session_factory() as session:
            candidate = session.get(KnowledgeCandidate, candidate_id)
            if candidate is None:
                return None
            if (
                candidate.candidate_group_id is None
                or candidate.content_sha256 is None
                or candidate.applicability is None
            ):
                return None
            evidence_rows = list(
                session.execute(
                    select(Evidence, SourceVersion)
                    .join(
                        CandidateEvidence,
                        CandidateEvidence.evidence_id == Evidence.evidence_id,
                    )
                    .join(
                        SourceVersion,
                        SourceVersion.source_version_id == Evidence.source_version_id,
                    )
                    .where(CandidateEvidence.candidate_id == candidate_id)
                    .order_by(Evidence.evidence_id)
                )
            )
            proposals = list(
                session.scalars(
                    select(CandidateRelationProposal)
                    .where(CandidateRelationProposal.candidate_id == candidate_id)
                    .order_by(CandidateRelationProposal.proposal_id)
                )
            )
            revision = session.scalar(
                select(KnowledgeRevision)
                .where(KnowledgeRevision.candidate_id == candidate_id)
                .order_by(KnowledgeRevision.revision_number.desc())
                .limit(1)
            )
            proposal_records = []
            for proposal in proposals:
                evidence_ids = tuple(
                    session.scalars(
                        select(RelationProposalEvidence.evidence_id)
                        .where(RelationProposalEvidence.proposal_id == proposal.proposal_id)
                        .order_by(RelationProposalEvidence.evidence_id)
                    )
                )
                proposal_records.append(
                    CandidateRelationProposalRecord(
                        relation_type=proposal.relation_type,
                        target_knowledge_unit_id=proposal.target_knowledge_unit_id,
                        evidence_ids=evidence_ids,
                        status=proposal.status,
                    )
                )
            rights_by_version = {
                version.source_version_id: version.rights for _, version in evidence_rows
            }
            evidence_records = tuple(
                CandidateEvidenceRecord(
                    evidence_id=evidence.evidence_id,
                    source_version_id=evidence.source_version_id,
                    locator=evidence.locator,
                    content=evidence.content,
                    content_sha256=evidence.content_sha256,
                    rights=rights_by_version[evidence.source_version_id],
                )
                for evidence, _ in evidence_rows
            )
        return CandidateDetailRecord(
            candidate_id=candidate.candidate_id,
            candidate_group_id=candidate.candidate_group_id,
            run_id=candidate.run_id,
            revision_number=candidate.revision_number,
            status=candidate.status,
            knowledge_type=candidate.knowledge_type,
            claim=candidate.claim,
            scope=candidate.scope,
            applicability=candidate.applicability,
            content_sha256=candidate.content_sha256,
            evidence_count=len(evidence_records),
            relation_proposal_count=len(proposal_records),
            author_actor_id=candidate.author_actor_id,
            knowledge_revision_id=(
                revision.knowledge_revision_id if revision is not None else None
            ),
            review_status=(revision.status if revision is not None else None),
            parent_candidate_id=candidate.parent_candidate_id,
            conditions=tuple(candidate.conditions),
            exceptions=tuple(candidate.exceptions),
            evidence=evidence_records,
            relation_proposals=tuple(proposal_records),
            advisory_signals=tuple(
                CandidateAdvisorySignalRecord(
                    signal_type=signal["signal_type"],
                    description=signal["description"],
                    target_knowledge_unit_id=signal.get(
                        "target_knowledge_unit_id"
                    ),
                    evidence_ids=tuple(signal["evidence_ids"]),
                )
                for signal in candidate.advisory_signals
            ),
            origin_model_invocation_id=candidate.origin_model_invocation_id,
        )

    def query_relations(
        self,
        *,
        node_id: str | None,
        query: str | None,
        depth: int,
    ) -> RelationQueryRecord:
        requested_depth = max(depth, 0)
        applied_depth = min(requested_depth, 2)
        warnings: list[str] = []
        if requested_depth != applied_depth:
            warnings.append("relation depth was capped at 2")

        with self._session_factory() as session:
            units = list(
                session.scalars(
                    select(KnowledgeUnit).order_by(
                        KnowledgeUnit.stable_key,
                        KnowledgeUnit.knowledge_unit_id,
                    )
                )
            )
            revisions = list(
                session.scalars(
                    select(KnowledgeRevision).order_by(
                        KnowledgeRevision.knowledge_unit_id,
                        KnowledgeRevision.revision_number.desc(),
                    )
                )
            )
            releases = list(
                session.execute(
                    select(ReleaseItem.knowledge_revision_id, ReleaseItem.release_id)
                    .join(Release, Release.release_id == ReleaseItem.release_id)
                    .where(Release.status == "released")
                    .order_by(ReleaseItem.knowledge_revision_id, ReleaseItem.release_id)
                )
            )
            canonical_relations = (
                list(
                    session.scalars(
                        select(KnowledgeRelation).order_by(KnowledgeRelation.relation_id)
                    )
                )
                if node_id is not None
                else []
            )
            proposals = (
                list(
                    session.scalars(
                        select(CandidateRelationProposal)
                        .where(CandidateRelationProposal.status.in_(("proposed", "accepted")))
                        .order_by(CandidateRelationProposal.proposal_id)
                    )
                )
                if node_id is not None
                else []
            )
            proposal_evidence = (
                list(
                    session.execute(
                        select(
                            RelationProposalEvidence.proposal_id,
                            RelationProposalEvidence.evidence_id,
                        ).order_by(
                            RelationProposalEvidence.proposal_id,
                            RelationProposalEvidence.evidence_id,
                        )
                    )
                )
                if node_id is not None
                else []
            )
            evidence_ids = {
                evidence_id for _, evidence_id in proposal_evidence
            }
            for relation in canonical_relations:
                evidence_ids.update(_provenance_evidence_ids(relation.provenance))
            evidence_rows = (
                list(
                    session.scalars(
                        select(Evidence)
                        .where(Evidence.evidence_id.in_(evidence_ids))
                        .order_by(Evidence.evidence_id)
                    )
                )
                if evidence_ids
                else []
            )

        latest_revision_by_unit: dict[str, KnowledgeRevision] = {}
        revision_by_id = {revision.knowledge_revision_id: revision for revision in revisions}
        revision_by_candidate: dict[str, KnowledgeRevision] = {}
        for revision in revisions:
            latest_revision_by_unit.setdefault(revision.knowledge_unit_id, revision)
            revision_by_candidate.setdefault(revision.candidate_id, revision)

        releases_by_revision: dict[str, list[str]] = {}
        for revision_id, release_id in releases:
            releases_by_revision.setdefault(revision_id, []).append(release_id)

        nodes_by_id: dict[str, RelationNodeRecord] = {}
        for unit in units:
            revision = latest_revision_by_unit.get(unit.knowledge_unit_id)
            release_ids = (
                tuple(releases_by_revision.get(revision.knowledge_revision_id, ()))
                if revision is not None
                else ()
            )
            nodes_by_id[unit.knowledge_unit_id] = RelationNodeRecord(
                knowledge_unit_id=unit.knowledge_unit_id,
                stable_key=unit.stable_key,
                knowledge_type=unit.knowledge_type,
                knowledge_revision_id=(
                    revision.knowledge_revision_id if revision is not None else None
                ),
                revision_number=revision.revision_number if revision is not None else None,
                status=(
                    "released"
                    if release_ids
                    else revision.status if revision is not None else "unversioned"
                ),
                claim=revision.claim if revision is not None else None,
                release_ids=release_ids,
            )

        evidence_by_id = {evidence.evidence_id: evidence for evidence in evidence_rows}
        proposal_evidence_ids: dict[str, list[str]] = {}
        for proposal_id, evidence_id in proposal_evidence:
            proposal_evidence_ids.setdefault(proposal_id, []).append(evidence_id)

        edge_records: list[RelationEdgeRecord] = []
        for relation in canonical_relations:
            source_revision = revision_by_id.get(relation.source_revision_id)
            if source_revision is None:
                warnings.append(f"relation {relation.relation_id} has no source revision")
                continue
            evidence_ids = _provenance_evidence_ids(relation.provenance)
            evidence = _relation_evidence_records(evidence_ids, evidence_by_id)
            if not evidence:
                warnings.append(f"relation {relation.relation_id} has no readable evidence")
                continue
            edge_records.append(
                RelationEdgeRecord(
                    relation_id=relation.relation_id,
                    source_knowledge_unit_id=source_revision.knowledge_unit_id,
                    target_knowledge_unit_id=relation.target_knowledge_unit_id,
                    relation_type=relation.relation_type,
                    status=relation.status,
                    evidence=evidence,
                )
            )

        for proposal in proposals:
            source_revision = revision_by_candidate.get(proposal.candidate_id)
            if source_revision is None:
                warnings.append(f"proposal {proposal.proposal_id} has no confirmed source unit")
                continue
            latest_source_revision = latest_revision_by_unit.get(
                source_revision.knowledge_unit_id
            )
            if (
                latest_source_revision is None
                or latest_source_revision.knowledge_revision_id
                != source_revision.knowledge_revision_id
            ):
                continue
            evidence = _relation_evidence_records(
                proposal_evidence_ids.get(proposal.proposal_id, ()),
                evidence_by_id,
            )
            if not evidence:
                warnings.append(f"proposal {proposal.proposal_id} has no readable evidence")
                continue
            edge_records.append(
                RelationEdgeRecord(
                    relation_id=proposal.proposal_id,
                    source_knowledge_unit_id=source_revision.knowledge_unit_id,
                    target_knowledge_unit_id=proposal.target_knowledge_unit_id,
                    relation_type=proposal.relation_type,
                    status=proposal.status,
                    evidence=evidence,
                )
            )

        matching_nodes = list(nodes_by_id.values())
        if query:
            needle = query.casefold()
            matching_nodes = [
                node
                for node in matching_nodes
                if needle
                in " ".join(
                    (
                        node.knowledge_unit_id,
                        node.stable_key,
                        node.knowledge_type,
                        node.claim or "",
                    )
                ).casefold()
            ]
        total_nodes = len(matching_nodes)
        truncated = total_nodes > 100

        if node_id is None:
            selected_nodes = tuple(matching_nodes[:100])
            selected_edges: tuple[RelationEdgeRecord, ...] = ()
        elif node_id not in nodes_by_id:
            warnings.append(f"relation root {node_id} was not found")
            selected_nodes = ()
            selected_edges = ()
        else:
            selected_ids = {node_id}
            frontier = {node_id}
            selected_edge_list: list[RelationEdgeRecord] = []
            for _ in range(applied_depth):
                next_frontier: set[str] = set()
                for edge in edge_records:
                    if (
                        edge.source_knowledge_unit_id in frontier
                        or edge.target_knowledge_unit_id in frontier
                    ):
                        if edge not in selected_edge_list:
                            selected_edge_list.append(edge)
                        next_frontier.update(
                            (
                                edge.source_knowledge_unit_id,
                                edge.target_knowledge_unit_id,
                            )
                        )
                next_frontier -= selected_ids
                selected_ids.update(next_frontier)
                frontier = next_frontier
                if not frontier:
                    break
            selected_nodes = tuple(
                node
                for unit_id in sorted(selected_ids)
                if (node := nodes_by_id.get(unit_id)) is not None
            )
            selected_edges = tuple(selected_edge_list)

        return RelationQueryRecord(
            root_node_id=node_id,
            requested_depth=requested_depth,
            applied_depth=applied_depth,
            nodes=selected_nodes,
            edges=selected_edges,
            total_nodes=total_nodes,
            truncated=truncated,
            warnings=tuple(warnings),
        )

    def list_audit_events(
        self,
        *,
        actor: str | None,
        action: str | None,
        object_type: str | None,
        result: str | None,
        cursor: str | None,
        limit: int,
    ) -> AuditEventPageRecord:
        with self._session_factory() as session:
            statement = select(AuditEvent)
            if actor:
                statement = statement.where(AuditEvent.actor_subject.ilike(f"%{actor}%"))
            if action:
                statement = statement.where(AuditEvent.action.ilike(f"%{action}%"))
            if object_type:
                statement = statement.where(AuditEvent.entity_type.ilike(f"%{object_type}%"))
            rows = list(
                session.scalars(
                    statement.order_by(
                        AuditEvent.created_at.desc(),
                        AuditEvent.audit_event_id.desc(),
                    ).limit(1001)
                )
            )

        warnings: list[str] = []
        if len(rows) > 1000:
            rows = rows[:1000]
            warnings.append(
                "audit query was capped at 1000 events; narrow the filters for a complete result"
            )
        if result:
            result_needle = result.casefold()
            rows = [
                row
                for row in rows
                if result_needle in str(row.details.get("result", "")).casefold()
            ]
        total = len(rows)
        start = 0
        if cursor:
            cursor_index = next(
                (index for index, row in enumerate(rows) if row.audit_event_id == cursor),
                None,
            )
            if cursor_index is None:
                warnings.append("audit cursor was not found; the first page was returned")
            else:
                start = cursor_index + 1
        page = rows[start : start + limit]
        next_cursor = (
            page[-1].audit_event_id if page and start + len(page) < total else None
        )
        return AuditEventPageRecord(
            items=tuple(_audit_event_record(row) for row in page),
            total=total,
            next_cursor=next_cursor,
            warnings=tuple(warnings),
        )


def _media_type_label(media_type: str, object_key: str) -> str | None:
    normalized = media_type.lower()
    suffix = object_key.lower().rsplit(".", maxsplit=1)[-1]
    if normalized == "application/pdf" or suffix == "pdf":
        return "PDF"
    if normalized in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    } or suffix in {"docx", "doc"}:
        return "DOCX"
    if normalized in {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    } or suffix in {"xlsx", "xls"}:
        return "XLSX"
    if normalized in {"text/markdown", "text/plain"} or suffix in {"md", "markdown"}:
        return "Markdown"
    return None


def _model_profile_record(profile: ModelProfile) -> ModelProfileRecord:
    return ModelProfileRecord(
        profile_id=profile.profile_id,
        version=profile.version,
        provider=profile.provider,
        model=profile.model,
        deployment_class=profile.deployment_class,
        secret_ref=profile.secret_ref,
        endpoint_ref=profile.endpoint_ref,
        allowed_data_boundaries=tuple(profile.allowed_data_boundaries),
        capabilities=tuple(profile.capabilities),
        timeout_seconds=profile.timeout_seconds,
        max_output_tokens=profile.max_output_tokens,
        cost_policy=profile.cost_policy,
        created_at=profile.created_at,
    )


def _model_profile_facts(profile: ModelProfile) -> dict[str, object]:
    return {
        "provider": profile.provider,
        "model": profile.model,
        "deployment_class": profile.deployment_class,
        "secret_ref": profile.secret_ref,
        "endpoint_ref": profile.endpoint_ref,
        "allowed_data_boundaries": sorted(set(profile.allowed_data_boundaries)),
        "capabilities": sorted(set(profile.capabilities)),
        "timeout_seconds": profile.timeout_seconds,
        "max_output_tokens": profile.max_output_tokens,
        "cost_policy": profile.cost_policy,
    }


def _rights_label(rights: object) -> str | None:
    if not isinstance(rights, dict):
        return None
    value = rights.get("status", rights.get("classification"))
    return value if value in {"licensed", "internal", "restricted"} else None


def _source_status_label(status: str) -> str | None:
    allowed = {
        "registered",
        "processing",
        "candidate",
        "approved",
        "released",
        "restricted",
        "disabled",
    }
    return status if status in allowed else None


def _provenance_evidence_ids(provenance: object) -> tuple[str, ...]:
    if not isinstance(provenance, dict):
        return ()
    raw = provenance.get("evidence_ids", provenance.get("evidenceIds", ()))
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, str))


def _relation_evidence_records(
    evidence_ids: Sequence[str],
    evidence_by_id: dict[str, Evidence],
) -> tuple[RelationEvidenceRecord, ...]:
    records: list[RelationEvidenceRecord] = []
    for evidence_id in evidence_ids:
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None:
            continue
        records.append(
            RelationEvidenceRecord(
                evidence_id=evidence.evidence_id,
                source_version_id=evidence.source_version_id,
                locator=evidence.locator,
                content=evidence.content,
                content_sha256=evidence.content_sha256,
            )
        )
    return tuple(records)


def _audit_event_record(event: AuditEvent) -> AuditEventRecord:
    details = event.details if isinstance(event.details, dict) else {}
    revision_number = details.get("revision_number")
    safe_revision_number = revision_number if isinstance(revision_number, int) else None
    input_sha256 = _safe_sha256(details.get("input_sha256"))
    output_sha256 = _safe_sha256(
        details.get("output_sha256", details.get("content_sha256", details.get("sha256")))
    )
    before = (
        AuditVersionRecord(
            revision_number=None,
            content_sha256=input_sha256,
        )
        if input_sha256
        else None
    )
    after = (
        AuditVersionRecord(
            revision_number=safe_revision_number,
            content_sha256=output_sha256,
        )
        if safe_revision_number is not None or output_sha256
        else None
    )
    result = details.get("result")
    correlation_id = details.get("correlation_id")
    return AuditEventRecord(
        audit_event_id=event.audit_event_id,
        actor_id=event.actor_subject,
        action=event.action,
        object_type=event.entity_type,
        object_id=event.entity_id,
        run_id=event.run_id,
        before_version=before,
        after_version=after,
        result=result if isinstance(result, str) else None,
        correlation_id=(
            correlation_id
            if isinstance(correlation_id, str)
            else event.run_id
        ),
        created_at=event.created_at,
    )


def _safe_sha256(value: object) -> str | None:
    if not isinstance(value, str) or len(value) != 64:
        return None
    return value if all(character in "0123456789abcdef" for character in value) else None
