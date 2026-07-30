"""Read models and PostgreSQL adapter for prerelease platform routes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from service.auth import PlatformUserGrant
from service.db.models import (
    CandidateEvidence,
    CandidateRelationProposal,
    Evidence,
    JobStep,
    KnowledgeCandidate,
    KnowledgeRevision,
    PlatformUser,
    ProcessingRun,
    Release,
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


class PlatformReadRepository(Protocol):
    def resolve_user(self, *, issuer: str, subject: str) -> PlatformUserGrant | None: ...

    def database_available(self) -> bool: ...

    def get_current_release(self) -> CurrentReleaseRecord | None: ...

    def list_sources(self) -> tuple[Sequence[SourceSummaryRecord], Sequence[str]]: ...

    def list_platform_users(
        self,
    ) -> tuple[Sequence[PlatformUserRecord], Sequence[str]]: ...

    def list_processing_runs(
        self,
    ) -> tuple[Sequence[ProcessingRunRecord], Sequence[str]]: ...

    def get_processing_run(self, *, run_id: str) -> ProcessingRunRecord | None: ...

    def list_candidates(
        self,
    ) -> tuple[Sequence[CandidateSummaryRecord], Sequence[str]]: ...


class SqlAlchemyPlatformRepository:
    """Read-only adapter over the canonical SQLAlchemy metadata."""

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
