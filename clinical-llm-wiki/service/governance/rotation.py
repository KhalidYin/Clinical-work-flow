"""Deterministic SourceVersion impact and RotationCase materialization."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, model_validator

from service.knowledge import (
    ComparableEvidence,
    EvidenceChangeType,
    ImpactAssessmentRecord,
    RotationCaseStatus,
    RotationOutcome,
    compare_evidence_versions,
)
from service.knowledge.lifecycle import StrictLifecycleModel


class ImpactMaterializationError(RuntimeError):
    """Canonical source facts do not permit an impact materialization."""


class ImpactMaterializationCommand(StrictLifecycleModel):
    from_source_version_id: str = Field(min_length=1, max_length=160)
    to_source_version_id: str = Field(min_length=1, max_length=160)
    comparison_profile_version: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_distinct_versions(self) -> "ImpactMaterializationCommand":
        if self.from_source_version_id == self.to_source_version_id:
            raise ValueError("impact materialization requires distinct source versions")
        return self


@dataclass(frozen=True, slots=True)
class ReleasedRevisionEvidence:
    knowledge_revision_id: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.knowledge_revision_id:
            raise ValueError("knowledge_revision_id is required")
        if not self.evidence_ids:
            raise ValueError("released revision requires Evidence")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("released revision Evidence IDs must be unique")


class MaterializedRotationCase(StrictLifecycleModel):
    rotation_case_id: str = Field(min_length=1, max_length=160)
    impact_assessment_id: str = Field(min_length=1, max_length=160)
    knowledge_revision_id: str = Field(min_length=1, max_length=160)
    change_types: tuple[EvidenceChangeType, ...] = Field(min_length=1)
    eligible_outcomes: tuple[RotationOutcome, ...] = Field(min_length=1)
    status: RotationCaseStatus = RotationCaseStatus.OPEN
    proposed_outcome: RotationOutcome | None = None
    included_release_id: str | None = None

    @model_validator(mode="after")
    def validate_initial_case(self) -> "MaterializedRotationCase":
        if self.status is not RotationCaseStatus.OPEN:
            raise ValueError("materialized rotation case must start open")
        if self.proposed_outcome is not None or self.included_release_id is not None:
            raise ValueError("materialization cannot decide or publish a rotation case")
        expected = eligible_rotation_outcomes(self.change_types)
        if self.eligible_outcomes != expected:
            raise ValueError("eligible outcomes do not match case Evidence changes")
        return self


class RotationMaterializationResult(StrictLifecycleModel):
    assessment: ImpactAssessmentRecord
    cases: tuple[MaterializedRotationCase, ...]


class RotationMaterializationRepository(Protocol):
    def source_id_for_version(self, source_version_id: str) -> str | None: ...

    def comparable_evidence(
        self,
        source_version_id: str,
    ) -> tuple[ComparableEvidence, ...]: ...

    def released_revision_evidence(
        self,
        evidence_ids: frozenset[str],
    ) -> tuple[ReleasedRevisionEvidence, ...]: ...

    def persist_materialization(
        self,
        *,
        result: RotationMaterializationResult,
        actor_id: str,
    ) -> RotationMaterializationResult: ...


class RotationImpactMaterializer:
    """Compare immutable Evidence and open cases for affected released revisions."""

    def __init__(self, *, repository: RotationMaterializationRepository) -> None:
        self._repository = repository

    def materialize(
        self,
        *,
        actor_id: str,
        command: ImpactMaterializationCommand,
    ) -> RotationMaterializationResult:
        if not actor_id:
            raise ImpactMaterializationError("actor_id is required")
        from_source_id = self._repository.source_id_for_version(
            command.from_source_version_id
        )
        to_source_id = self._repository.source_id_for_version(
            command.to_source_version_id
        )
        if from_source_id is None or to_source_id is None:
            raise ImpactMaterializationError("source version does not exist")
        if from_source_id != to_source_id:
            raise ImpactMaterializationError(
                "impact materialization requires versions of the same source"
            )
        from_evidence = self._repository.comparable_evidence(
            command.from_source_version_id
        )
        to_evidence = self._repository.comparable_evidence(command.to_source_version_id)
        if not from_evidence or not to_evidence:
            raise ImpactMaterializationError(
                "both source versions require canonical Evidence"
            )
        assessment_id = _stable_id(
            "impact",
            {
                "comparison_profile_version": command.comparison_profile_version,
                "from_source_version_id": command.from_source_version_id,
                "to_source_version_id": command.to_source_version_id,
            },
        )
        assessment = compare_evidence_versions(
            assessment_id=assessment_id,
            from_source_version_id=command.from_source_version_id,
            to_source_version_id=command.to_source_version_id,
            comparison_profile_version=command.comparison_profile_version,
            from_evidence=from_evidence,
            to_evidence=to_evidence,
        )
        impacted_old_evidence_ids = frozenset(
            impact.from_evidence_id
            for impact in assessment.impacts
            if impact.from_evidence_id is not None
        )
        revision_evidence = self._repository.released_revision_evidence(
            impacted_old_evidence_ids
        )
        cases: list[MaterializedRotationCase] = []
        for revision in sorted(
            revision_evidence,
            key=lambda item: item.knowledge_revision_id,
        ):
            evidence_ids = frozenset(revision.evidence_ids)
            change_types = _ordered_change_types(
                impact.change_type
                for impact in assessment.impacts
                if impact.from_evidence_id in evidence_ids
            )
            if not change_types:
                continue
            cases.append(
                MaterializedRotationCase(
                    rotation_case_id=_stable_id(
                        "rotation",
                        {
                            "assessment_id": assessment_id,
                            "knowledge_revision_id": revision.knowledge_revision_id,
                        },
                    ),
                    impact_assessment_id=assessment_id,
                    knowledge_revision_id=revision.knowledge_revision_id,
                    change_types=change_types,
                    eligible_outcomes=eligible_rotation_outcomes(change_types),
                )
            )
        result = RotationMaterializationResult(
            assessment=assessment,
            cases=tuple(cases),
        )
        return self._repository.persist_materialization(
            result=result,
            actor_id=actor_id,
        )


def eligible_rotation_outcomes(
    change_types: tuple[EvidenceChangeType, ...],
) -> tuple[RotationOutcome, ...]:
    """Return proposal choices; this never decides or publishes a case."""

    if not change_types:
        raise ValueError("rotation eligibility requires at least one Evidence change")
    safe = {EvidenceChangeType.UNCHANGED, EvidenceChangeType.MOVED}
    if set(change_types).issubset(safe):
        return (RotationOutcome.CARRY_FORWARD,)
    return (
        RotationOutcome.REPLACE,
        RotationOutcome.RETIRE,
        RotationOutcome.NO_ACTION,
    )


def _ordered_change_types(
    change_types,
) -> tuple[EvidenceChangeType, ...]:
    present = set(change_types)
    return tuple(change_type for change_type in EvidenceChangeType if change_type in present)


def _stable_id(prefix: str, facts: dict[str, str]) -> str:
    canonical = json.dumps(
        facts,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"{prefix}-{uuid5(NAMESPACE_URL, canonical).hex}"
