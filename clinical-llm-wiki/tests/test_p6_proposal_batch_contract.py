"""P6-P3-A proposal-batch, coverage-ledger, and Gold scoring gates."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.content.proposal_batch_contract import (
    ProposalBatchContractError,
    score_gold_proposals,
    validate_proposal_batch,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "knowledge" / "extraction-contract-positive.json"
GOLD_SET = ROOT / "tests" / "fixtures" / "knowledge" / "sdtmig34-gold-set.json"
MAP_HASH = "5" * 64


def _package() -> dict[str, object]:
    package = json.loads(FIXTURE.read_text(encoding="utf-8"))
    package["package_id"] = "pkg-proposal-fixture-v1"
    for statement in package["statements"]:
        statement["review_status"] = "proposed"
        statement["review_receipt_id"] = None
    return package


def _batch() -> dict[str, object]:
    return _batch_from_package(_package())


def _batch_from_package(package: dict[str, object]) -> dict[str, object]:
    units = package["units"]
    return {
        "schema_version": "1.0.0",
        "batch_id": "batch-proposal-fixture-v1",
        "source_id": package["source_id"],
        "source_sha256": package["source_sha256"],
        "structure_map_id": "map-synthetic-v1",
        "structure_map_sha256": MAP_HASH,
        "scope": {
            "scope_id": "scope-synthetic-v1",
            "description": "Synthetic contract fixture only.",
            "unit_ids": [unit["unit_id"] for unit in units],
        },
        "generation": {
            "method": "synthetic_fixture",
            "run_id": "run-synthetic-v1",
            "prompt_id": None,
            "prompt_sha256": None,
            "model_id": None,
        },
        "extraction_package": package,
        "coverage": [
            {
                "unit_id": unit["unit_id"],
                "source_order": index,
                "disposition": "candidate",
                "rationale": None,
                "proposal_ids": unit["statement_ids"],
            }
            for index, unit in enumerate(units)
        ],
        "quality_summary": {
            "unit_total": len(units),
            "candidate_unit_count": len(units),
            "non_knowledge_unit_count": 0,
            "deferred_unit_count": 0,
            "proposal_total": len(package["statements"]),
            "blocking_issue_count": 0,
            "gate_status": "pass",
        },
        "gold_evaluation": None,
    }


def _gold_candidate() -> tuple[dict[str, object], dict[str, object]]:
    gold = json.loads(GOLD_SET.read_text(encoding="utf-8"))
    candidate = deepcopy(gold)
    candidate["package_id"] = "pkg-sdtmig34-gold-candidate-v1"
    for statement in candidate["statements"]:
        statement["statement_id"] = statement["statement_id"].replace("stmt-", "proposal-")
        statement["review_status"] = "proposed"
        statement["review_receipt_id"] = None
    old_to_new = {
        gold_statement["statement_id"]: candidate_statement["statement_id"]
        for gold_statement, candidate_statement in zip(
            gold["statements"], candidate["statements"], strict=True
        )
    }
    for unit in candidate["units"]:
        unit["statement_ids"] = [old_to_new[item] for item in unit["statement_ids"]]
    for relation in candidate["relations"]:
        if relation["from_id"] in old_to_new:
            relation["from_id"] = old_to_new[relation["from_id"]]
        if relation["target_kind"] == "statement" and relation["to_id"] in old_to_new:
            relation["to_id"] = old_to_new[relation["to_id"]]
    return candidate, gold


def test_positive_proposal_batch_has_exact_coverage_and_proposed_only_content() -> None:
    validate_proposal_batch(_batch())


def test_scope_coverage_and_package_units_must_match_exactly() -> None:
    batch = _batch()
    batch["scope"]["unit_ids"].append("unit-outside-extraction-package")
    with pytest.raises(ProposalBatchContractError, match="must match exactly"):
        validate_proposal_batch(batch)


def test_candidate_cannot_inherit_gold_approval_or_receipt() -> None:
    batch = _batch()
    statement = batch["extraction_package"]["statements"][0]
    statement["review_status"] = "approved"
    statement["review_receipt_id"] = "review-invalid-copy"
    with pytest.raises(ProposalBatchContractError, match="must remain proposed"):
        validate_proposal_batch(batch)


def test_quality_summary_cannot_drift_from_coverage_ledger() -> None:
    batch = _batch()
    batch["quality_summary"]["candidate_unit_count"] += 1
    with pytest.raises(ProposalBatchContractError, match="candidate_unit_count"):
        validate_proposal_batch(batch)


def test_batch_can_be_bound_to_actual_source_and_structure_map_hashes() -> None:
    batch = _batch()
    with pytest.raises(ProposalBatchContractError, match="locked structure map"):
        validate_proposal_batch(
            batch,
            expected_source_sha256=batch["source_sha256"],
            expected_structure_map_sha256="6" * 64,
        )


def test_llm_generation_requires_prompt_hash_and_model_identity() -> None:
    batch = _batch()
    batch["generation"]["method"] = "llm_assisted"
    with pytest.raises(ProposalBatchContractError, match="schema validation failed"):
        validate_proposal_batch(batch)


def test_gold_score_matches_by_evidence_not_generated_statement_id() -> None:
    candidate, gold = _gold_candidate()
    report = score_gold_proposals(candidate, gold)

    assert report["gate_status"] == "pass"
    assert report["expected_total"] == 7
    assert report["structural_match_count"] == 7
    assert report["field_mismatch_count"] == 0
    assert report["missing_count"] == 0
    assert report["unexpected_count"] == 0
    assert report["text_exact_count"] == 7

    batch = _batch_from_package(candidate)
    batch["gold_evaluation"] = report
    validate_proposal_batch(batch)


def test_gold_evaluation_summary_cannot_claim_a_false_pass() -> None:
    candidate, gold = _gold_candidate()
    batch = _batch_from_package(candidate)
    batch["gold_evaluation"] = score_gold_proposals(candidate, gold)
    batch["gold_evaluation"]["structural_match_count"] -= 1

    with pytest.raises(ProposalBatchContractError, match="structural_match_count"):
        validate_proposal_batch(batch)


def test_gold_score_separates_text_review_from_structural_gate() -> None:
    candidate, gold = _gold_candidate()
    candidate["statements"][0]["statement"] = "A faithful paraphrase requiring human review."
    report = score_gold_proposals(candidate, gold)

    assert report["gate_status"] == "pass"
    assert report["structural_match_count"] == 7
    assert report["text_exact_count"] == 6
    assert report["text_review_required_count"] == 1


def test_gold_score_reports_field_mismatch_without_fuzzy_acceptance() -> None:
    candidate, gold = _gold_candidate()
    candidate["statements"][0]["modality"] = "may"
    report = score_gold_proposals(candidate, gold)

    assert report["gate_status"] == "fail"
    assert report["field_mismatch_count"] == 1
    comparison = next(
        item for item in report["comparisons"] if item["status"] == "field_mismatch"
    )
    assert comparison["field_differences"] == [
        {"field": "modality", "expected": "should", "actual": "may"}
    ]


def test_gold_score_reports_missing_and_unexpected_candidates() -> None:
    candidate, gold = _gold_candidate()
    missing = candidate["statements"].pop()
    for unit in candidate["units"]:
        unit["statement_ids"] = [
            statement_id
            for statement_id in unit["statement_ids"]
            if statement_id != missing["statement_id"]
        ]
    candidate["relations"] = [
        relation
        for relation in candidate["relations"]
        if relation["from_id"] != missing["statement_id"]
        and relation["to_id"] != missing["statement_id"]
    ]
    candidate["statements"][0]["evidence"].append(
        deepcopy(candidate["statements"][1]["evidence"][0])
    )
    report = score_gold_proposals(candidate, gold)

    assert report["gate_status"] == "fail"
    assert report["missing_count"] == 2
    assert report["unexpected_count"] == 1
