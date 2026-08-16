"""PostgreSQL adapter for atomic P17 impact and RotationCase materialization."""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from service.db.models import (
    AuditEvent,
    CandidateEvidence,
    Evidence,
    EvidenceImpact,
    ImpactAssessment,
    KnowledgeRevision,
    Release,
    ReleaseItem,
    RotationCase,
    SourceVersion,
)
from service.knowledge import ComparableEvidence, EvidenceImpactRecord, EvidenceMappingBasis

from .rotation import (
    ImpactMaterializationError,
    ReleasedRevisionEvidence,
    RotationMaterializationResult,
)


class SqlAlchemyRotationRepository:
    """Persist one comparison and all affected released-revision cases atomically."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def source_id_for_version(self, source_version_id: str) -> str | None:
        with self._sessions() as session:
            return session.scalar(
                select(SourceVersion.source_id).where(
                    SourceVersion.source_version_id == source_version_id
                )
            )

    def comparable_evidence(
        self,
        source_version_id: str,
    ) -> tuple[ComparableEvidence, ...]:
        with self._sessions() as session:
            version = session.get(SourceVersion, source_version_id)
            if version is None:
                return ()
            rows = session.scalars(
                select(Evidence)
                .where(Evidence.source_version_id == source_version_id)
                .order_by(Evidence.evidence_id)
            )
            return tuple(
                ComparableEvidence(
                    evidence_id=row.evidence_id,
                    content_sha256=row.content_sha256,
                    locator_sha256=row.locator_sha256,
                    rights=version.rights,
                )
                for row in rows
            )

    def released_revision_evidence(
        self,
        evidence_ids: frozenset[str],
    ) -> tuple[ReleasedRevisionEvidence, ...]:
        if not evidence_ids:
            return ()
        with self._sessions() as session:
            rows = session.execute(
                select(
                    KnowledgeRevision.knowledge_revision_id,
                    CandidateEvidence.evidence_id,
                )
                .join(
                    CandidateEvidence,
                    CandidateEvidence.candidate_id == KnowledgeRevision.candidate_id,
                )
                .join(
                    ReleaseItem,
                    ReleaseItem.knowledge_revision_id
                    == KnowledgeRevision.knowledge_revision_id,
                )
                .join(Release, Release.release_id == ReleaseItem.release_id)
                .where(
                    CandidateEvidence.evidence_id.in_(evidence_ids),
                    KnowledgeRevision.status == "released",
                    Release.status == "released",
                )
                .distinct()
                .order_by(
                    KnowledgeRevision.knowledge_revision_id,
                    CandidateEvidence.evidence_id,
                )
            )
            grouped: dict[str, list[str]] = {}
            for revision_id, evidence_id in rows:
                grouped.setdefault(revision_id, []).append(evidence_id)
            return tuple(
                ReleasedRevisionEvidence(
                    knowledge_revision_id=revision_id,
                    evidence_ids=tuple(ids),
                )
                for revision_id, ids in grouped.items()
            )

    def persist_materialization(
        self,
        *,
        result: RotationMaterializationResult,
        actor_id: str,
    ) -> RotationMaterializationResult:
        assessment = result.assessment
        with self._sessions.begin() as session:
            locked_versions = tuple(
                session.scalars(
                    select(SourceVersion)
                    .where(
                        SourceVersion.source_version_id.in_(
                            (
                                assessment.from_source_version_id,
                                assessment.to_source_version_id,
                            )
                        )
                    )
                    .order_by(SourceVersion.source_version_id)
                    .with_for_update()
                )
            )
            if len(locked_versions) != 2:
                raise ImpactMaterializationError(
                    "source versions disappeared before materialization"
                )
            existing = session.get(ImpactAssessment, assessment.assessment_id)
            if existing is not None:
                _require_matching_materialization(session, result)
                return result
            session.add(
                ImpactAssessment(
                    assessment_id=assessment.assessment_id,
                    from_source_version_id=assessment.from_source_version_id,
                    to_source_version_id=assessment.to_source_version_id,
                    comparison_profile_version=assessment.comparison_profile_version,
                )
            )
            session.flush()
            for impact in assessment.impacts:
                session.add(
                    EvidenceImpact(
                        evidence_impact_id=impact.evidence_impact_id,
                        assessment_id=assessment.assessment_id,
                        change_type=impact.change_type.value,
                        from_evidence_id=impact.from_evidence_id,
                        to_evidence_id=impact.to_evidence_id,
                        mapping_basis=impact.mapping_basis.value,
                        details=impact.details,
                    )
                )
            for case in result.cases:
                session.add(
                    RotationCase(
                        rotation_case_id=case.rotation_case_id,
                        impact_assessment_id=case.impact_assessment_id,
                        knowledge_revision_id=case.knowledge_revision_id,
                        status="open",
                        case_version=1,
                    )
                )
            session.add(
                AuditEvent(
                    audit_event_id=(
                        f"audit-{uuid5(NAMESPACE_URL, f'impact_assessment.materialized:{assessment.assessment_id}').hex}"
                    ),
                    actor_subject=actor_id,
                    action="impact_assessment.materialized",
                    entity_type="impact_assessment",
                    entity_id=assessment.assessment_id,
                    run_id=None,
                    details={
                        "from_source_version_id": assessment.from_source_version_id,
                        "to_source_version_id": assessment.to_source_version_id,
                        "comparison_profile_version": (
                            assessment.comparison_profile_version
                        ),
                        "impact_count": len(assessment.impacts),
                        "rotation_case_count": len(result.cases),
                        "result": "open_cases_materialized",
                    },
                )
            )
            session.flush()
        return result


def _require_matching_materialization(
    session: Session,
    expected: RotationMaterializationResult,
) -> None:
    assessment = session.get(ImpactAssessment, expected.assessment.assessment_id)
    if assessment is None:
        raise ImpactMaterializationError("impact materialization disappeared")
    if (
        assessment.from_source_version_id
        != expected.assessment.from_source_version_id
        or assessment.to_source_version_id != expected.assessment.to_source_version_id
        or assessment.comparison_profile_version
        != expected.assessment.comparison_profile_version
    ):
        raise ImpactMaterializationError("impact assessment identity drift")
    actual_impacts = tuple(
        EvidenceImpactRecord(
            evidence_impact_id=row.evidence_impact_id,
            change_type=row.change_type,
            from_evidence_id=row.from_evidence_id,
            to_evidence_id=row.to_evidence_id,
            mapping_basis=EvidenceMappingBasis(row.mapping_basis),
            details=row.details,
        )
        for row in session.scalars(
            select(EvidenceImpact)
            .where(EvidenceImpact.assessment_id == assessment.assessment_id)
            .order_by(EvidenceImpact.evidence_impact_id)
        )
    )
    expected_impacts = tuple(
        sorted(
            expected.assessment.impacts,
            key=lambda item: item.evidence_impact_id,
        )
    )
    if actual_impacts != expected_impacts:
        raise ImpactMaterializationError("Evidence impact materialization drift")
    actual_cases = tuple(
        session.execute(
            select(
                RotationCase.rotation_case_id,
                RotationCase.knowledge_revision_id,
            )
            .where(RotationCase.impact_assessment_id == assessment.assessment_id)
            .order_by(RotationCase.rotation_case_id)
        )
    )
    expected_cases = tuple(
        sorted(
            (
                (case.rotation_case_id, case.knowledge_revision_id)
                for case in expected.cases
            ),
            key=lambda item: item[0],
        )
    )
    if actual_cases != expected_cases:
        raise ImpactMaterializationError("RotationCase materialization drift")
