"""Fail-closed Study decision promotion-candidate generation.

This module writes de-identification/review proposals only inside the current
Study.  It deliberately has no Wiki repository dependency and never promotes
content into Prior Studies or any governed Vault collection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from .compatibility import sha256_canonical_json
from .models import (
    SemVerString,
    Sha256,
    StableId,
    StrictContractModel,
    StudyDecision,
    TEAEWindowRule,
)


class PromotionCandidateError(ValueError):
    """A candidate cannot be safely represented or written within its Study."""


class PromotionReviewStatus(StrEnum):
    """Independent human review state for a de-identified candidate."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PromotionCandidate(StrictContractModel):
    """Public candidate content derived from one approved Study decision."""

    candidate_id: StableId
    schema_version: Literal["1.0.0"] = "1.0.0"
    status: Literal["proposed"] = "proposed"
    source_decision_id: StableId
    source_decision_version: SemVerString
    source_decision_sha256: Sha256
    source_study_sha256: Sha256
    source_ids: tuple[StableId, ...] = Field(min_length=1)
    structured_rule: TEAEWindowRule
    deidentified: bool = False
    review_status: PromotionReviewStatus = PromotionReviewStatus.PENDING
    eligible_for_wiki_proposal: bool = False

    @model_validator(mode="after")
    def eligibility_is_derived_from_governance(self) -> Self:
        expected = self.deidentified and self.review_status is PromotionReviewStatus.APPROVED
        if self.eligible_for_wiki_proposal is not expected:
            raise ValueError(
                "eligible_for_wiki_proposal requires deidentified=true and "
                "review_status=approved"
            )
        return self


@dataclass(frozen=True, slots=True)
class PromotionCandidateArtifact:
    """The validated candidate and its Study-local filesystem location."""

    path: Path
    candidate: PromotionCandidate


def create_promotion_candidate(
    project_dir: str | Path,
    decision: StudyDecision,
    *,
    deidentified: bool = False,
    review_status: PromotionReviewStatus | str = PromotionReviewStatus.PENDING,
    candidate_path: str | Path | None = None,
) -> PromotionCandidateArtifact:
    """Write one immutable candidate under ``knowledge/promotion_candidates``.

    ``decision`` is expected to have already passed ``load_study_decision`` or
    ``load_study_decisions``.  Eligibility is computed here and cannot be
    supplied by the caller.  A candidate remains only a local proposal even
    when eligible; a separate Wiki review/import flow must perform promotion.
    """

    if not isinstance(decision, StudyDecision):
        raise PromotionCandidateError("decision must be a validated StudyDecision")
    try:
        normalized_review_status = PromotionReviewStatus(review_status)
    except ValueError as exc:
        raise PromotionCandidateError(f"unsupported promotion review status: {review_status}") from exc

    project_root = Path(project_dir).resolve()
    if not project_root.is_dir():
        raise PromotionCandidateError("Study project directory must exist and be a directory")

    candidate_root = (project_root / "knowledge" / "promotion_candidates").resolve()
    if project_root not in candidate_root.parents:
        raise PromotionCandidateError(
            "knowledge/promotion_candidates must remain inside the Study project directory"
        )
    try:
        candidate_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PromotionCandidateError(
            "cannot create Study knowledge/promotion_candidates directory"
        ) from exc
    candidate_root = candidate_root.resolve()
    if project_root not in candidate_root.parents:
        raise PromotionCandidateError(
            "knowledge/promotion_candidates resolved outside the Study project directory"
        )

    candidate = _build_candidate(decision, deidentified, normalized_review_status)
    target = _candidate_target(candidate_root, candidate, candidate_path)
    serialized = json.dumps(
        candidate.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if decision.study_id in serialized:
        raise PromotionCandidateError(
            "raw study_id is present in candidate public content; de-identification failed"
        )

    try:
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
    except FileExistsError as exc:
        raise PromotionCandidateError(f"promotion candidate already exists: {target.name}") from exc
    except OSError as exc:
        raise PromotionCandidateError(f"cannot write promotion candidate: {target.name}") from exc
    return PromotionCandidateArtifact(path=target, candidate=candidate)


def _build_candidate(
    decision: StudyDecision,
    deidentified: bool,
    review_status: PromotionReviewStatus,
) -> PromotionCandidate:
    source_study_sha256 = sha256_canonical_json(
        {
            "study_id": decision.study_id,
            "decision_content_sha256": decision.content_sha256,
        }
    )
    return PromotionCandidate(
        candidate_id=f"promotion-{decision.decision_id}",
        source_decision_id=decision.decision_id,
        source_decision_version=decision.version,
        source_decision_sha256=decision.content_sha256,
        source_study_sha256=source_study_sha256,
        source_ids=decision.source_ids,
        structured_rule=decision.structured_rule,
        deidentified=deidentified,
        review_status=review_status,
        eligible_for_wiki_proposal=(
            deidentified and review_status is PromotionReviewStatus.APPROVED
        ),
    )


def _candidate_target(
    candidate_root: Path,
    candidate: PromotionCandidate,
    candidate_path: str | Path | None,
) -> Path:
    relative = (
        Path(f"{candidate.candidate_id}.json")
        if candidate_path is None
        else Path(candidate_path)
    )
    if relative.is_absolute() or len(relative.parts) != 1 or relative.suffix.lower() != ".json":
        raise PromotionCandidateError(
            "candidate_path must be a relative JSON filename directly under "
            "knowledge/promotion_candidates"
        )
    target = (candidate_root / relative).resolve()
    if target.parent != candidate_root:
        raise PromotionCandidateError(
            "candidate path must remain inside knowledge/promotion_candidates"
        )
    return target
