"""P6-P3-B SDTMIG 3.4 Gold proposal calibration gates."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.content.sdtmig34_gold_calibration import (
    DEFAULT_PACKAGE,
    DEFAULT_RESPONSE,
    GoldCalibrationError,
    load_json,
    run_gold_calibration,
)


def _write_response(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def test_gold_calibration_input_projects_scope_without_restricted_source_text() -> None:
    result = run_gold_calibration(include_source_text=False)
    projection = result["report"]["input_projection"]

    assert projection["unit_total"] == 8
    assert projection["deep_structure_map_unit_count"] == 7
    assert projection["release_accession_unit_count"] == 1
    assert projection["source_text_included"] is False
    assert all("source_text" not in unit for unit in result["input"]["source_units"])
    assert {
        "unit-sdtmig34-xlsx-variable-ae-aeterm",
        "unit-sdtmig34-xlsx-variable-ae-aeenrf",
        "unit-sdtmig34-web-errata-section15",
    } <= {unit["unit_id"] for unit in result["input"]["source_units"]}


def test_gold_calibration_batch_passes_gate_and_remains_proposed() -> None:
    result = run_gold_calibration()
    batch = result["batch"]
    evaluation = batch["gold_evaluation"]
    statements = batch["extraction_package"]["statements"]

    assert evaluation["gate_status"] == "pass"
    assert evaluation["expected_total"] == 7
    assert evaluation["structural_match_count"] == 7
    assert evaluation["field_mismatch_count"] == 0
    assert evaluation["missing_count"] == 0
    assert evaluation["unexpected_count"] == 0
    assert evaluation["text_exact_count"] == 0
    assert evaluation["text_review_required_count"] == 7
    assert len(batch["coverage"]) == 8
    assert all(statement["review_status"] == "proposed" for statement in statements)
    assert all(statement["review_receipt_id"] is None for statement in statements)
    assert all(statement["statement_id"].startswith("proposal-") for statement in statements)

    aeterm = next(statement for statement in statements if statement["subject"] == "AE.AETERM")
    assert {item["locator_id"] for item in aeterm["evidence"]} == {
        "loc-sdtmig34-p137-aeterm-assumption",
        "loc-sdtmig34-xlsx-variables-r293",
    }


def test_gold_calibration_report_matches_committed_compact_artifact() -> None:
    result = run_gold_calibration(include_source_text=True)
    report_path = DEFAULT_PACKAGE / "gold-proposal-calibration-report.json"

    assert result["report"] == load_json(report_path)


def test_gold_calibration_rejects_unknown_source_unit(tmp_path: Path) -> None:
    response = deepcopy(load_json(DEFAULT_RESPONSE))
    response["proposals"][0]["source_unit_ids"] = ["unit-sdtmig34-missing"]

    with pytest.raises(GoldCalibrationError, match="unknown source unit"):
        run_gold_calibration(
            response_path=_write_response(tmp_path / "bad-response.json", response)
        )


def test_gold_calibration_fails_closed_on_structural_mismatch(tmp_path: Path) -> None:
    response = deepcopy(load_json(DEFAULT_RESPONSE))
    response["proposals"][0]["modality"] = "may"
    response_path = _write_response(tmp_path / "mismatch-response.json", response)

    with pytest.raises(GoldCalibrationError, match="did not pass"):
        run_gold_calibration(response_path=response_path)

    result = run_gold_calibration(response_path=response_path, require_gold_pass=False)
    evaluation = result["batch"]["gold_evaluation"]
    mismatch = next(
        item for item in evaluation["comparisons"] if item["status"] == "field_mismatch"
    )
    assert evaluation["gate_status"] == "fail"
    assert evaluation["field_mismatch_count"] == 1
    assert mismatch["field_differences"] == [
        {"field": "modality", "expected": "should", "actual": "may"}
    ]
