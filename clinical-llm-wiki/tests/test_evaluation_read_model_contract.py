from __future__ import annotations

import json
from pathlib import Path

from service.evaluation import EvaluationReport, RetrievalBaselineRun


ROOT = Path(__file__).resolve().parents[1]


def test_checked_e9_report_gets_a_deterministic_informational_run_identity() -> None:
    payload = json.loads(
        (ROOT / "reports/p17/ich-e9-retrieval-baseline.json").read_text(
            encoding="utf-8"
        )
    )
    report = EvaluationReport.model_validate(payload["evaluation"])

    first = RetrievalBaselineRun.from_report(report)
    repeated = RetrievalBaselineRun.from_report(report)

    assert first == repeated
    assert first.purpose == "retrieval_baseline"
    assert first.outcome == "informational"
    assert first.report.case_count == 18
    assert first.report.metrics.recall_at_5 == 0.888889
    assert first.report.metrics.recall_at_10 == 0.944444
    assert first.report.external_model_requests == 0
    assert "threshold" not in first.model_dump(mode="json")
