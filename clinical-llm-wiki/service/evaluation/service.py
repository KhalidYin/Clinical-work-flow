"""Deterministic Recall@K evaluation over cited retrieval results."""

from __future__ import annotations

from typing import Protocol

from service.retrieval import ReleaseCandidateScope, RetrievalQuery, RetrievalResult

from .contracts import (
    EvaluationReport,
    GoldCase,
    GoldCaseResult,
    GoldSuite,
    RecallMetrics,
    gold_suite_sha256,
)


class RetrievalQueryPort(Protocol):
    def query(self, request: RetrievalQuery) -> RetrievalResult: ...


class EvaluationService:
    def __init__(self, *, retrieval: RetrievalQueryPort) -> None:
        self._retrieval = retrieval

    def run(
        self,
        *,
        suite: GoldSuite,
        scope: ReleaseCandidateScope,
    ) -> EvaluationReport:
        if (
            scope.source_version_ids != (suite.source_version_id,)
            or scope.chunk_profile_id != suite.chunk_profile_id
        ):
            raise ValueError("evaluation scope does not match suite pinned inputs")
        results: list[GoldCaseResult] = []
        capabilities = None
        fusion_version = None
        for case in suite.cases:
            retrieval = self._retrieval.query(
                RetrievalQuery(query=case.question, top_k=10, scope=scope)
            )
            if retrieval.external_model_requests != 0:
                raise ValueError("retrieval evaluation cannot use external model requests")
            if capabilities is None:
                capabilities = retrieval.capabilities
                fusion_version = retrieval.fusion_version
            elif (
                capabilities != retrieval.capabilities
                or fusion_version != retrieval.fusion_version
            ):
                raise ValueError("retrieval capability or fusion contract drifted within suite")
            results.append(_case_result(case, retrieval))
        if capabilities is None or fusion_version is None:
            raise ValueError("evaluation suite produced no retrieval results")
        total = len(results)
        return EvaluationReport(
            suite_id=suite.suite_id,
            suite_version=suite.version,
            suite_sha256=gold_suite_sha256(suite),
            document_id=suite.document_id,
            source_version_id=suite.source_version_id,
            source_sha256=suite.source_sha256,
            chunk_profile_id=suite.chunk_profile_id,
            chunk_profile_version=suite.chunk_profile_version,
            sandbox_id=scope.sandbox_id,
            fusion_version=fusion_version,
            case_count=total,
            metrics=RecallMetrics(
                recall_at_5=round(sum(item.hit_at_5 for item in results) / total, 6),
                recall_at_10=round(sum(item.hit_at_10 for item in results) / total, 6),
            ),
            capabilities=capabilities,
            case_results=tuple(results),
        )


def _case_result(case: GoldCase, result: RetrievalResult) -> GoldCaseResult:
    expected = set(case.expected_evidence_ids)
    first_relevant_rank = next(
        (
            hit.rank
            for hit in result.hits
            if any(citation.evidence_id in expected for citation in hit.citations)
        ),
        None,
    )
    retrieved_evidence = tuple(
        dict.fromkeys(
            citation.evidence_id
            for hit in result.hits
            for citation in hit.citations
        )
    )
    matched = tuple(item for item in case.expected_evidence_ids if item in retrieved_evidence)
    hit_at_5 = first_relevant_rank is not None and first_relevant_rank <= 5
    hit_at_10 = first_relevant_rank is not None and first_relevant_rank <= 10
    outcome = (
        "hit_top_5"
        if hit_at_5
        else "hit_top_10_only"
        if hit_at_10
        else "expected_not_in_top_10"
    )
    failure_category = (
        "none"
        if hit_at_5
        else "ranked_below_5"
        if hit_at_10
        else "expected_not_retrieved"
    )
    return GoldCaseResult(
        case_id=case.case_id,
        topic=case.topic,
        question=case.question,
        query_id=result.query_id,
        expected_evidence_ids=case.expected_evidence_ids,
        retrieved_chunk_ids=tuple(hit.chunk_id for hit in result.hits),
        retrieved_evidence_ids=retrieved_evidence,
        matched_expected_evidence_ids=matched,
        first_relevant_rank=first_relevant_rank,
        hit_at_5=hit_at_5,
        hit_at_10=hit_at_10,
        outcome=outcome,
        failure_category=failure_category,
    )


__all__ = ["EvaluationService", "RetrievalQueryPort"]
