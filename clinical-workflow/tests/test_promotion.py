from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.knowledge import (
    PromotionCandidateError,
    PromotionReviewStatus,
    StudyDecision,
    create_promotion_candidate,
)
from src.knowledge.compatibility import sha256_canonical_json


FIXTURE = Path(__file__).parent / "fixtures" / "contracts" / "study" / "study_decision.json"


def _decision() -> StudyDecision:
    return StudyDecision.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_creates_local_proposed_candidate_without_raw_study_id(tmp_path: Path) -> None:
    project = tmp_path / "study"
    project.mkdir()
    decision = _decision()

    artifact = create_promotion_candidate(project, decision)

    expected_path = (
        project
        / "knowledge"
        / "promotion_candidates"
        / f"promotion-{decision.decision_id}.json"
    )
    assert artifact.path == expected_path.resolve()
    assert artifact.candidate.status == "proposed"
    assert artifact.candidate.source_decision_id == decision.decision_id
    assert artifact.candidate.source_decision_sha256 == decision.content_sha256
    assert artifact.candidate.source_ids == decision.source_ids
    assert artifact.candidate.structured_rule == decision.structured_rule
    assert artifact.candidate.deidentified is False
    assert artifact.candidate.review_status is PromotionReviewStatus.PENDING
    assert artifact.candidate.eligible_for_wiki_proposal is False

    serialized = expected_path.read_text(encoding="utf-8")
    assert decision.study_id not in serialized
    assert "study_id" not in serialized
    assert artifact.candidate.source_study_sha256 == sha256_canonical_json(
        {
            "study_id": decision.study_id,
            "decision_content_sha256": decision.content_sha256,
        }
    )


@pytest.mark.parametrize(
    ("deidentified", "review_status", "eligible"),
    [
        (False, PromotionReviewStatus.PENDING, False),
        (False, PromotionReviewStatus.APPROVED, False),
        (True, PromotionReviewStatus.PENDING, False),
        (True, PromotionReviewStatus.REJECTED, False),
        (True, PromotionReviewStatus.APPROVED, True),
    ],
)
def test_eligibility_requires_deidentification_and_approval(
    tmp_path: Path,
    deidentified: bool,
    review_status: PromotionReviewStatus,
    eligible: bool,
) -> None:
    project = tmp_path / review_status.value / str(deidentified)
    project.mkdir(parents=True)

    artifact = create_promotion_candidate(
        project,
        _decision(),
        deidentified=deidentified,
        review_status=review_status,
    )

    assert artifact.candidate.eligible_for_wiki_proposal is eligible


@pytest.mark.parametrize(
    "candidate_path",
    ["../outside.json", "nested/candidate.json", "candidate.txt"],
)
def test_rejects_paths_outside_direct_candidate_directory(
    tmp_path: Path,
    candidate_path: str,
) -> None:
    project = tmp_path / "study"
    project.mkdir()

    with pytest.raises(PromotionCandidateError, match="promotion_candidates"):
        create_promotion_candidate(
            project,
            _decision(),
            candidate_path=candidate_path,
        )

    assert not (project / "knowledge" / "outside.json").exists()
    assert not (project / "knowledge" / "promotion_candidates" / "nested").exists()


def test_rejects_absolute_candidate_path(tmp_path: Path) -> None:
    project = tmp_path / "study"
    project.mkdir()
    outside = tmp_path / "outside.json"

    with pytest.raises(PromotionCandidateError, match="relative JSON filename"):
        create_promotion_candidate(project, _decision(), candidate_path=outside)

    assert not outside.exists()


def test_duplicate_candidate_never_overwrites_existing_evidence(tmp_path: Path) -> None:
    project = tmp_path / "study"
    project.mkdir()
    decision = _decision()
    first = create_promotion_candidate(project, decision)
    original = first.path.read_bytes()

    with pytest.raises(PromotionCandidateError, match="already exists"):
        create_promotion_candidate(
            project,
            decision,
            deidentified=True,
            review_status=PromotionReviewStatus.APPROVED,
        )

    assert first.path.read_bytes() == original
    assert json.loads(original)["eligible_for_wiki_proposal"] is False


def test_rejects_project_path_that_is_not_a_directory(tmp_path: Path) -> None:
    project = tmp_path / "study-file"
    project.write_text("not a Study directory", encoding="utf-8")

    with pytest.raises(PromotionCandidateError, match="Study project directory"):
        create_promotion_candidate(project, _decision())
