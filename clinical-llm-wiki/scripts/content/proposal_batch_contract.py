"""Fail-closed contracts for small-batch knowledge proposal extraction.

The embedded extraction package owns statement semantics and evidence.  This
module adds run provenance, exact source-unit coverage, proposed-only status,
and deterministic field-level comparison with a human-approved Gold Set.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from scripts.content.extraction_contract import (
    ExtractionContractError,
    validate_extraction_package,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = ROOT / "schemas" / "extraction" / "proposal-batch.schema.json"
STRUCTURAL_FIELDS = (
    "knowledge_type",
    "modality",
    "scope",
    "conditions",
    "exceptions",
    "evidence",
)


class ProposalBatchContractError(ValueError):
    """Raised when a proposal batch or Gold comparison is not trustworthy."""


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_proposal_batch(
    payload: dict[str, Any],
    *,
    schema_path: str | Path = DEFAULT_SCHEMA,
    expected_source_sha256: str | None = None,
    expected_structure_map_sha256: str | None = None,
) -> None:
    """Validate one extraction batch and all coverage/proposal references."""

    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda item: list(item.path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.path) or "<root>"
        raise ProposalBatchContractError(
            f"schema validation failed at {location}: {first.message}"
        )

    package = payload["extraction_package"]
    try:
        validate_extraction_package(package)
    except ExtractionContractError as error:
        raise ProposalBatchContractError(
            f"embedded extraction package is invalid: {error}"
        ) from error

    if payload["source_id"] != package["source_id"]:
        raise ProposalBatchContractError("batch source_id does not match extraction package")
    if payload["source_sha256"] != package["source_sha256"]:
        raise ProposalBatchContractError(
            "batch source_sha256 does not match extraction package"
        )
    if expected_source_sha256 is not None and payload["source_sha256"] != expected_source_sha256:
        raise ProposalBatchContractError("batch source_sha256 does not match locked source")
    if (
        expected_structure_map_sha256 is not None
        and payload["structure_map_sha256"] != expected_structure_map_sha256
    ):
        raise ProposalBatchContractError(
            "batch structure_map_sha256 does not match locked structure map"
        )

    units = {unit["unit_id"]: unit for unit in package["units"]}
    statements = {
        statement["statement_id"]: statement for statement in package["statements"]
    }
    scope_ids = payload["scope"]["unit_ids"]
    coverage = payload["coverage"]
    coverage_ids = [entry["unit_id"] for entry in coverage]
    source_orders = [entry["source_order"] for entry in coverage]

    if len(set(coverage_ids)) != len(coverage_ids):
        raise ProposalBatchContractError("duplicate source unit in coverage ledger")
    if len(set(source_orders)) != len(source_orders):
        raise ProposalBatchContractError("duplicate source_order in coverage ledger")
    if set(scope_ids) != set(units) or set(coverage_ids) != set(units):
        raise ProposalBatchContractError(
            "scope, coverage ledger, and extraction package units must match exactly"
        )

    linked_proposals: set[str] = set()
    for entry in coverage:
        unit = units[entry["unit_id"]]
        proposal_ids = set(entry["proposal_ids"])
        unit_statement_ids = set(unit["statement_ids"])
        if proposal_ids != unit_statement_ids:
            raise ProposalBatchContractError(
                f"coverage proposals do not match source unit {entry['unit_id']}"
            )
        if not proposal_ids <= set(statements):
            raise ProposalBatchContractError(
                f"coverage for {entry['unit_id']} references an unknown proposal"
            )

        disposition = entry["disposition"]
        if disposition == "candidate":
            if unit["processing_status"] not in {"candidate", "example"}:
                raise ProposalBatchContractError(
                    f"candidate coverage has incompatible processing_status for {entry['unit_id']}"
                )
            linked_proposals.update(proposal_ids)
        elif disposition == "non_knowledge":
            if unit["processing_status"] not in {"context", "navigation"}:
                raise ProposalBatchContractError(
                    f"non_knowledge coverage has incompatible processing_status for {entry['unit_id']}"
                )
        elif unit["processing_status"] != "deferred":
            raise ProposalBatchContractError(
                f"deferred coverage has incompatible processing_status for {entry['unit_id']}"
            )

    if linked_proposals != set(statements):
        raise ProposalBatchContractError(
            "every proposal must be linked by at least one candidate coverage entry"
        )
    for statement in statements.values():
        if statement["review_status"] != "proposed":
            raise ProposalBatchContractError(
                f"proposal {statement['statement_id']} must remain proposed"
            )
        if statement["review_receipt_id"] is not None:
            raise ProposalBatchContractError(
                f"proposal {statement['statement_id']} must not carry a review receipt"
            )

    _validate_quality_summary(payload["quality_summary"], coverage, len(statements))
    evaluation = payload["gold_evaluation"]
    if evaluation is not None:
        if evaluation["candidate_package_id"] != package["package_id"]:
            raise ProposalBatchContractError(
                "gold evaluation candidate_package_id does not match extraction package"
            )
        _validate_gold_evaluation(evaluation)


def _validate_quality_summary(
    summary: dict[str, Any], coverage: list[dict[str, Any]], proposal_total: int
) -> None:
    counts = Counter(entry["disposition"] for entry in coverage)
    expected = {
        "unit_total": len(coverage),
        "candidate_unit_count": counts["candidate"],
        "non_knowledge_unit_count": counts["non_knowledge"],
        "deferred_unit_count": counts["deferred"],
        "proposal_total": proposal_total,
    }
    for field, value in expected.items():
        if summary[field] != value:
            raise ProposalBatchContractError(
                f"quality_summary {field} is {summary[field]}, expected {value}"
            )
    if summary["gate_status"] == "pass" and summary["blocking_issue_count"] != 0:
        raise ProposalBatchContractError(
            "quality gate cannot pass with blocking issues"
        )
    if summary["gate_status"] == "fail" and summary["blocking_issue_count"] == 0:
        raise ProposalBatchContractError(
            "failed quality gate must report at least one blocking issue"
        )


def _validate_gold_evaluation(evaluation: dict[str, Any]) -> None:
    counts = Counter(item["status"] for item in evaluation["comparisons"])
    text_exact_count = sum(
        item["text_exact"] is True for item in evaluation["comparisons"]
    )
    text_review_required_count = sum(
        item["text_exact"] is False for item in evaluation["comparisons"]
    )
    expected = {
        "expected_total": len(evaluation["comparisons"]),
        "structural_match_count": counts["structural_match"],
        "field_mismatch_count": counts["field_mismatch"],
        "missing_count": counts["missing"],
        "unexpected_count": len(evaluation["unexpected_candidates"]),
        "text_exact_count": text_exact_count,
        "text_review_required_count": text_review_required_count,
    }
    expected["candidate_total"] = (
        expected["structural_match_count"]
        + expected["field_mismatch_count"]
        + expected["unexpected_count"]
    )
    for field, value in expected.items():
        if evaluation[field] != value:
            raise ProposalBatchContractError(
                f"gold_evaluation {field} is {evaluation[field]}, expected {value}"
            )
    should_pass = (
        expected["structural_match_count"] == expected["expected_total"]
        and expected["field_mismatch_count"] == 0
        and expected["missing_count"] == 0
        and expected["unexpected_count"] == 0
    )
    if (evaluation["gate_status"] == "pass") != should_pass:
        raise ProposalBatchContractError(
            "gold_evaluation gate_status does not match deterministic counts"
        )


def score_gold_proposals(
    candidate_package: dict[str, Any], gold_package: dict[str, Any]
) -> dict[str, Any]:
    """Compare candidates to Gold by evidence identity and exact structural fields.

    Statement wording is reported separately.  A structural pass never upgrades
    review status and never substitutes for human semantic review.
    """

    try:
        validate_extraction_package(candidate_package)
        validate_extraction_package(gold_package)
    except ExtractionContractError as error:
        raise ProposalBatchContractError(f"cannot score invalid package: {error}") from error

    if candidate_package["source_id"] != gold_package["source_id"]:
        raise ProposalBatchContractError("candidate and Gold source_id must match")
    if candidate_package["source_sha256"] != gold_package["source_sha256"]:
        raise ProposalBatchContractError("candidate and Gold source_sha256 must match")

    candidates = _index_statements(candidate_package["statements"], "candidate")
    expected = _index_statements(gold_package["statements"], "Gold")
    comparisons: list[dict[str, Any]] = []
    structural_match_count = 0
    field_mismatch_count = 0
    missing_count = 0
    text_exact_count = 0
    text_review_required_count = 0

    for evidence_key, gold_statement in sorted(expected.items()):
        candidate = candidates.get(evidence_key)
        if candidate is None:
            missing_count += 1
            comparisons.append(
                {
                    "evidence_key": evidence_key,
                    "expected_statement_id": gold_statement["statement_id"],
                    "candidate_statement_id": None,
                    "status": "missing",
                    "field_differences": [],
                    "text_exact": None,
                }
            )
            continue

        differences = _field_differences(gold_statement, candidate)
        text_exact = candidate["statement"] == gold_statement["statement"]
        if text_exact:
            text_exact_count += 1
        else:
            text_review_required_count += 1
        if differences:
            field_mismatch_count += 1
            status = "field_mismatch"
        else:
            structural_match_count += 1
            status = "structural_match"
        comparisons.append(
            {
                "evidence_key": evidence_key,
                "expected_statement_id": gold_statement["statement_id"],
                "candidate_statement_id": candidate["statement_id"],
                "status": status,
                "field_differences": differences,
                "text_exact": text_exact,
            }
        )

    unexpected = [
        {
            "candidate_statement_id": statement["statement_id"],
            "evidence_key": evidence_key,
        }
        for evidence_key, statement in sorted(candidates.items())
        if evidence_key not in expected
    ]
    unexpected_count = len(unexpected)
    gate_status = (
        "pass"
        if structural_match_count == len(expected)
        and field_mismatch_count == 0
        and missing_count == 0
        and unexpected_count == 0
        else "fail"
    )
    return {
        "schema_version": "1.0.0",
        "gold_package_id": gold_package["package_id"],
        "candidate_package_id": candidate_package["package_id"],
        "expected_total": len(expected),
        "candidate_total": len(candidates),
        "structural_match_count": structural_match_count,
        "field_mismatch_count": field_mismatch_count,
        "missing_count": missing_count,
        "unexpected_count": unexpected_count,
        "text_exact_count": text_exact_count,
        "text_review_required_count": text_review_required_count,
        "gate_status": gate_status,
        "comparisons": comparisons,
        "unexpected_candidates": unexpected,
    }


def _index_statements(
    statements: list[dict[str, Any]], label: str
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for statement in statements:
        key = _evidence_key(statement)
        if key in index:
            raise ProposalBatchContractError(
                f"duplicate {label} evidence identity: {key}"
            )
        index[key] = statement
    return index


def _evidence_key(statement: dict[str, Any]) -> str:
    parts = sorted(
        f"{item['source_id']}::{item['artifact_id']}::{item['locator_id']}"
        for item in statement["evidence"]
    )
    return "|".join(parts)


def _field_differences(
    expected: dict[str, Any], actual: dict[str, Any]
) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    for field in STRUCTURAL_FIELDS:
        expected_value = _normalized_field(field, expected[field])
        actual_value = _normalized_field(field, actual[field])
        if expected_value != actual_value:
            differences.append(
                {
                    "field": field,
                    "expected": deepcopy(expected_value),
                    "actual": deepcopy(actual_value),
                }
            )
    return differences


def _normalized_field(field: str, value: Any) -> Any:
    if field == "scope":
        normalized = deepcopy(value)
        normalized["domains"] = sorted(normalized["domains"])
        normalized["variables"] = sorted(normalized["variables"])
        return normalized
    if field in {"conditions", "exceptions"}:
        return sorted(value)
    if field == "evidence":
        return sorted(
            (
                item["source_id"],
                item["artifact_id"],
                item["artifact_sha256"],
                item["locator_id"],
            )
            for item in value
        )
    return value
