from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest
from pydantic import ValidationError

from service.evaluation import EvaluationService, GoldCase, GoldSuite
from service.retrieval import (
    CandidateSearchRecord,
    EvidenceCitation,
    ReleaseCandidateScope,
    RetrievalService,
)


ROOT = Path(__file__).resolve().parents[1]


class GoldSearchRepository:
    def search_metadata_fts(self, *, query, scope, limit):
        del limit
        case_number = int(query.rsplit("-", maxsplit=1)[1])
        expected_rank = 1 if case_number <= 12 else 6 if case_number <= 14 else None
        records = []
        for index in range(1, 11):
            evidence_id = (
                f"evidence-case-{case_number:02d}"
                if index == expected_rank
                else f"evidence-distractor-{case_number:02d}-{index:02d}"
            )
            digest = sha256(evidence_id.encode()).hexdigest()
            records.append(
                CandidateSearchRecord(
                    chunk_id=f"chunk-{case_number:02d}-{index:02d}",
                    chunk_profile_id=scope.chunk_profile_id,
                    source_version_id=scope.source_version_ids[0],
                    source_title="Synthetic E9 retrieval fixture",
                    source_version="1",
                    ordinal=index,
                    evidence_type="text",
                    content=f"Synthetic candidate {index} for {query}.",
                    content_sha256=digest,
                    token_count=6,
                    locator={"kind": "page", "page": index},
                    metadata_score=0,
                    full_text_score=float(11 - index),
                    citations=(
                        EvidenceCitation(
                            evidence_id=evidence_id,
                            source_version_id=scope.source_version_ids[0],
                            source_artifact_id="artifact-synthetic",
                            locator={"kind": "page", "page": index},
                            content_sha256=digest,
                            start_offset=0,
                            end_offset=10,
                            span_role="primary",
                        ),
                    ),
                )
            )
        return records


def _suite() -> GoldSuite:
    return GoldSuite(
        suite_id="gold-suite-synthetic-e9",
        version="1.0.0",
        document_id="ICH-E9-1998",
        source_version_id="srcv-synthetic-e9",
        source_sha256="a" * 64,
        chunk_profile_id="chunk-profile-e9-v1",
        chunk_profile_version="ich-e9-poc-v1",
        cases=tuple(
            GoldCase(
                case_id=f"case-{index:02d}",
                topic=f"synthetic-topic-{index:02d}",
                question=f"question-{index:02d}",
                expected_evidence_ids=(f"evidence-case-{index:02d}",),
            )
            for index in range(1, 16)
        ),
    )


def _scope() -> ReleaseCandidateScope:
    return ReleaseCandidateScope(
        sandbox_id="sandbox-synthetic-e9",
        source_version_ids=("srcv-synthetic-e9",),
        chunk_profile_id="chunk-profile-e9-v1",
    )


def test_gold_suite_requires_15_to_20_unique_cases_with_expected_evidence() -> None:
    with pytest.raises(ValidationError):
        GoldSuite(
            suite_id="too-small",
            version="1",
            document_id="ICH-E9-1998",
            source_version_id="srcv-synthetic-e9",
            source_sha256="a" * 64,
            chunk_profile_id="chunk-profile-e9-v1",
            chunk_profile_version="ich-e9-poc-v1",
            cases=tuple(_suite().cases[:14]),
        )

    duplicate = list(_suite().cases)
    duplicate[-1] = duplicate[0]
    with pytest.raises(ValidationError, match="unique"):
        GoldSuite(
            suite_id="duplicate",
            version="1",
            document_id="ICH-E9-1998",
            source_version_id="srcv-synthetic-e9",
            source_sha256="a" * 64,
            chunk_profile_id="chunk-profile-e9-v1",
            chunk_profile_version="ich-e9-poc-v1",
            cases=tuple(duplicate),
        )


def test_evaluation_reports_recall_at_5_and_10_per_case_without_model_judge() -> None:
    evaluator = EvaluationService(
        retrieval=RetrievalService(repository=GoldSearchRepository())
    )

    first = evaluator.run(suite=_suite(), scope=_scope())
    repeated = evaluator.run(suite=_suite(), scope=_scope())

    assert first == repeated
    assert first.case_count == 15
    assert first.metrics.recall_at_5 == 0.8
    assert first.metrics.recall_at_10 == pytest.approx(14 / 15, abs=1e-6)
    assert first.case_results[0].first_relevant_rank == 1
    assert first.case_results[12].outcome == "hit_top_10_only"
    assert first.case_results[12].failure_category == "ranked_below_5"
    assert first.case_results[12].first_relevant_rank == 6
    assert first.case_results[-1].outcome == "expected_not_in_top_10"
    assert first.case_results[-1].failure_category == "expected_not_retrieved"
    assert first.case_results[-1].first_relevant_rank is None
    assert first.external_model_requests == 0
    assert first.evaluation_notice == (
        "single_document_retrieval_baseline_not_clinical_quality_certification"
    )
    assert first.capabilities.vector.status == "degraded"


def test_evaluation_rejects_scope_that_does_not_match_pinned_suite_inputs() -> None:
    wrong_scope = _scope().model_copy(
        update={"source_version_ids": ("srcv-other",)}
    )

    with pytest.raises(ValueError, match="pinned inputs"):
        EvaluationService(
            retrieval=RetrievalService(repository=GoldSearchRepository())
        ).run(suite=_suite(), scope=wrong_scope)


def test_checked_in_ich_e9_gold_suite_is_pinned_and_contains_no_source_excerpts() -> None:
    path = ROOT / "service/evaluation/suites/ich-e9-retrieval-gold-v1.json"
    suite = GoldSuite.model_validate_json(path.read_text(encoding="utf-8"))

    assert len(suite.cases) == 18
    assert suite.source_sha256 == (
        "0c0ddc93cb427a70265dbcb0e7c25bfc9a3f7b52e178212b3630ea2408ad9c7e"
    )
    assert suite.source_version_id == "srcv-af08bc3a1bf2569fa608724c63f9c5fc"
    assert suite.chunk_profile_version == "ich-e9-poc-v1"
    assert all("E9(R1)" not in case.question for case in suite.cases)
    assert all(case.expected_evidence_ids for case in suite.cases)
    raw = path.read_text(encoding="utf-8")
    assert '"answer"' not in raw
    assert '"source_excerpt"' not in raw
