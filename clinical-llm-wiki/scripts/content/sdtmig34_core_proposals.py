"""P6-P3-C SDTMIG 3.4 Core small-batch proposal extraction.

This module expands from the P3-B Gold calibration into a Core anchor batch.
It remains proposed-only: the generated package, report, and Obsidian Inbox
card are review inputs, not approved production knowledge.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from scripts.content.extraction_contract import validate_extraction_package
from scripts.content.proposal_batch_contract import (
    ProposalBatchContractError,
    validate_proposal_batch,
)
from scripts.pdf.structure_map_contract import (
    project_locator_to_p1,
    structure_map_sha256,
    validate_structure_map,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGE = ROOT / "sources" / "packages" / "src-cdisc-sdtmig-3-4"
DEFAULT_RESPONSE = (
    ROOT / "tests" / "fixtures" / "knowledge" / "sdtmig34-core-proposal-response-v1.json"
)
DEFAULT_PROMPT = ROOT / "scripts" / "content" / "prompts" / "sdtmig34_core_proposal_v1.md"
DEFAULT_REPORT = DEFAULT_PACKAGE / "core-proposal-quality-report.json"
DEFAULT_BATCH = DEFAULT_PACKAGE / "derived" / "core-proposal-batch.json"
DEFAULT_INPUT = DEFAULT_PACKAGE / "derived" / "core-proposal-input.json"
DEFAULT_INBOX_CARD = ROOT / "vault" / "98_Inbox" / "SDTMIG 3.4 Core Proposal Batch.md"

PROMPT_ID = "prompt-sdtmig34-core-proposal-v1"
RUN_ID = "run-sdtmig34-core-proposals-v1"
BATCH_ID = "batch-sdtmig34-core-proposals-v1"
PACKAGE_ID = "pkg-sdtmig34-core-proposals-v1"
SCOPE_ID = "scope-sdtmig34-core-anchor-batch-v1"

CORE_SCOPE_UNIT_IDS = [
    "unit-sdtmig34-deep-p0011-b003",
    "unit-sdtmig34-deep-p0011-b004",
    "unit-sdtmig34-deep-p0011-b005",
    "unit-sdtmig34-deep-p0011-b006",
    "unit-sdtmig34-deep-p0011-b007",
    "unit-sdtmig34-deep-p0011-b008",
    "unit-sdtmig34-deep-p0011-b017",
    "unit-sdtmig34-deep-p0011-b018",
    "unit-sdtmig34-deep-p0012-b001",
    "unit-sdtmig34-deep-p0012-b002",
    "unit-sdtmig34-deep-p0012-b006",
    "unit-sdtmig34-deep-p0021-b012",
    "unit-sdtmig34-pdf-table-p0017-g01",
    "unit-sdtmig34-deep-p0022-b016",
    "unit-sdtmig34-deep-p0023-b001",
    "unit-sdtmig34-deep-p0023-b002",
    "unit-sdtmig34-deep-p0023-b003",
    "unit-sdtmig34-deep-p0023-b004",
    "unit-sdtmig34-deep-p0023-b005",
    "unit-sdtmig34-deep-p0023-b006",
    "unit-sdtmig34-deep-p0029-b014",
    "unit-sdtmig34-deep-p0041-b017",
    "unit-sdtmig34-deep-p0042-b001",
    "unit-sdtmig34-deep-p0042-b003",
    "unit-sdtmig34-deep-p0042-b004",
]

NON_KNOWLEDGE_UNITS = {
    "unit-sdtmig34-pdf-table-p0017-g01": (
        "Context table retained for coverage calibration; the table layout is not "
        "promoted to an atomic Core rule in this batch."
    ),
    "unit-sdtmig34-deep-p0022-b016": (
        "Introductory lead-in for following Core category definitions; not a "
        "standalone atomic statement."
    ),
}

_STABLE_KEY = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ARTIFACT_SHA_BY_ID: dict[str, str] = {}


class CoreProposalError(ValueError):
    """Raised when the Core proposal path cannot be trusted."""


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_payload(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def normalized_text(value: str) -> str:
    return " ".join(value.split())


def sha256_text(value: str) -> str:
    return hashlib.sha256(normalized_text(value).encode("utf-8")).hexdigest()


def build_core_proposal_input(
    *,
    package_dir: str | Path = DEFAULT_PACKAGE,
    prompt_path: str | Path = DEFAULT_PROMPT,
    include_source_text: bool = False,
) -> dict[str, Any]:
    """Project a governed Core anchor scope from the approved deep map."""

    package = Path(package_dir)
    source = load_json(package / "source-manifest.json")
    summary = load_json(package / "deep-structure-summary.json")
    deep_map = load_json(package / "derived" / "structure-map-deep.json")
    validate_structure_map(deep_map)

    actual_map_hash = structure_map_sha256(deep_map)
    if actual_map_hash != summary["deep_structure_map_sha256"]:
        raise CoreProposalError("deep structure map hash differs from summary")
    if deep_map["source_id"] != source["source_id"]:
        raise CoreProposalError("deep structure map source_id differs from manifest")
    if deep_map["source_sha256"] != source["original_sha256"]:
        raise CoreProposalError("deep structure map source_sha256 differs from manifest")

    artifacts = _artifact_identities(source)
    units = _project_scope_units(
        deep_map=deep_map,
        scope_unit_ids=CORE_SCOPE_UNIT_IDS,
        include_source_text=include_source_text,
        package=package,
        source=source,
    )
    prompt_hash = sha256_file(prompt_path)
    payload = {
        "schema_version": "1.0.0",
        "input_id": "input-sdtmig34-core-proposals-v1",
        "source_id": source["source_id"],
        "source_sha256": source["original_sha256"],
        "structure_map_id": deep_map["structure_map_id"],
        "structure_map_sha256": actual_map_hash,
        "prompt_id": PROMPT_ID,
        "prompt_sha256": prompt_hash,
        "source_text_included": include_source_text,
        "artifacts": artifacts,
        "source_units": units,
        "scope": {
            "scope_id": SCOPE_ID,
            "description": (
                "P3-C Core anchor batch covering SDTM foundations, domain/dataset "
                "structure, conformance, Core designations, missing values, and "
                "study day rules."
            ),
        },
    }
    _assert_unique([unit["unit_id"] for unit in units], "source unit")
    _assert_unique([unit["locator"]["locator_id"] for unit in units], "locator")
    return payload


def _artifact_identities(source: dict[str, Any]) -> list[dict[str, str]]:
    artifacts = [
        {
            "artifact_id": artifact["artifact_id"],
            "role": artifact["role"],
            "media_type": artifact["media_type"],
            "artifact_sha256": artifact["original_sha256"],
        }
        for artifact in source["artifacts"]
    ]
    return sorted(artifacts, key=lambda item: item["artifact_id"])


def _project_scope_units(
    *,
    deep_map: dict[str, Any],
    scope_unit_ids: list[str],
    include_source_text: bool,
    package: Path,
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    unit_by_id = {unit["unit_id"]: unit for unit in deep_map["units"]}
    locator_by_id = {locator["locator_id"]: locator for locator in deep_map["locators"]}
    projected: list[dict[str, Any]] = []

    for source_order, unit_id in enumerate(scope_unit_ids):
        owner = unit_by_id.get(unit_id)
        if owner is None:
            raise CoreProposalError(f"scope references unknown source unit {unit_id}")
        locator = locator_by_id[owner["locator_ids"][0]]
        projected.append(
            {
                "unit_id": owner["unit_id"],
                "parent_unit_id": owner.get("parent_unit_id"),
                "unit_type": _unit_type_for_contract(owner["unit_type"]),
                "title": owner.get("title"),
                "text_sha256": owner["text_sha256"],
                "locator": project_locator_to_p1(locator),
                "processing_status": _processing_status(owner),
                "processing_note": _processing_note(owner),
                "source_origin": "deep_structure_map",
                "source_order": source_order,
                "content_role": owner.get("content_role"),
            }
        )

    selected_ids = {unit["unit_id"] for unit in projected}
    for unit in projected:
        if unit["parent_unit_id"] not in selected_ids:
            unit["parent_unit_id"] = None

    if include_source_text:
        _attach_source_text(projected, package=package, source=source)
    return projected


def _unit_type_for_contract(unit_type: str) -> str:
    if unit_type in {
        "chapter",
        "section",
        "domain",
        "table",
        "variable_row",
        "paragraph",
        "example",
        "cross_reference",
        "erratum",
    }:
        return unit_type
    raise CoreProposalError(f"unsupported unit_type for extraction contract: {unit_type}")


def _processing_status(owner: dict[str, Any]) -> str:
    if owner["unit_id"] in NON_KNOWLEDGE_UNITS:
        return "context"
    if owner["unit_type"] == "example" or owner.get("content_role") == "example":
        return "example"
    return "candidate"


def _processing_note(owner: dict[str, Any]) -> str | None:
    if owner["unit_id"] in NON_KNOWLEDGE_UNITS:
        return NON_KNOWLEDGE_UNITS[owner["unit_id"]]
    if owner["unit_type"] == "example" or owner.get("content_role") == "example":
        return "Informative example source unit; do not promote to a universal rule."
    return None


def _attach_source_text(
    units: list[dict[str, Any]], *, package: Path, source: dict[str, Any]
) -> None:
    import fitz

    artifacts = {artifact["artifact_id"]: artifact for artifact in source["artifacts"]}
    pdf_artifact = next(
        artifact for artifact in source["artifacts"] if artifact["role"] == "primary_citation"
    )
    pdf = fitz.open(package / pdf_artifact["original_relative_path"])
    try:
        for unit in units:
            locator = unit["locator"]
            artifact = artifacts.get(locator["artifact_id"])
            if locator["locator_type"] != "pdf_region":
                raise CoreProposalError(
                    f"unsupported Core locator type: {locator['locator_type']}"
                )
            source_text = _pdf_text(pdf, locator, unit["unit_type"])
            if artifact is not None and artifact["original_sha256"] != locator.get(
                "artifact_sha256", artifact["original_sha256"]
            ):
                raise CoreProposalError("artifact hash drift while reading source text")
            unit["source_text"] = normalized_text(source_text)
            unit["source_text_sha256"] = sha256_text(source_text)
    finally:
        pdf.close()


def _pdf_text(document: Any, locator: dict[str, Any], unit_type: str) -> str:
    page = document[locator["physical_page"] - 1]
    bbox = locator["bbox"]
    if unit_type == "table":
        values = [
            word[4]
            for word in page.get_text("words", sort=True)
            if word[0] >= bbox[0] - 1
            and word[1] >= bbox[1] - 1
            and word[2] <= bbox[2] + 1
            and word[3] <= bbox[3] + 1
        ]
        return " ".join(values)
    block = min(
        page.get_text("blocks", sort=True),
        key=lambda item: sum(abs(item[index] - bbox[index]) for index in range(4)),
    )
    return str(block[4])


def load_candidate_response(
    *,
    response_path: str | Path = DEFAULT_RESPONSE,
    proposal_input: dict[str, Any],
) -> dict[str, Any]:
    response = load_json(response_path)
    if response["schema_version"] != "1.0.0":
        raise CoreProposalError("unsupported response schema_version")
    for field in ("source_id", "source_sha256", "prompt_id", "prompt_sha256"):
        if response[field] != proposal_input[field]:
            raise CoreProposalError(f"response {field} differs from proposal input")
    if response["prompt_id"] != PROMPT_ID:
        raise CoreProposalError("response prompt_id is not the frozen P3-C prompt")
    _assert_unique([item["proposal_key"] for item in response["proposals"]], "proposal")
    for proposal in response["proposals"]:
        _assert_stable_key(proposal["proposal_key"], "proposal_key")
    return response


def build_proposal_batch(
    proposal_input: dict[str, Any],
    response: dict[str, Any],
) -> dict[str, Any]:
    _prepare_artifact_lookup(proposal_input)
    package = _candidate_package(proposal_input, response)
    coverage = _coverage_ledger(proposal_input, package)
    counts = Counter(entry["disposition"] for entry in coverage)
    blocking_issues = _blocking_issues(package=package, coverage=coverage)
    batch = {
        "schema_version": "1.0.0",
        "batch_id": BATCH_ID,
        "source_id": proposal_input["source_id"],
        "source_sha256": proposal_input["source_sha256"],
        "structure_map_id": proposal_input["structure_map_id"],
        "structure_map_sha256": proposal_input["structure_map_sha256"],
        "scope": {
            "scope_id": proposal_input["scope"]["scope_id"],
            "description": proposal_input["scope"]["description"],
            "unit_ids": [unit["unit_id"] for unit in proposal_input["source_units"]],
        },
        "generation": {
            "method": "llm_assisted",
            "run_id": RUN_ID,
            "prompt_id": proposal_input["prompt_id"],
            "prompt_sha256": proposal_input["prompt_sha256"],
            "model_id": response["model_id"],
        },
        "extraction_package": package,
        "coverage": coverage,
        "quality_summary": {
            "unit_total": len(proposal_input["source_units"]),
            "candidate_unit_count": counts["candidate"],
            "non_knowledge_unit_count": counts["non_knowledge"],
            "deferred_unit_count": counts["deferred"],
            "proposal_total": len(package["statements"]),
            "blocking_issue_count": len(blocking_issues),
            "gate_status": "pass" if not blocking_issues else "fail",
        },
        "gold_evaluation": None,
    }
    validate_proposal_batch(
        batch,
        expected_source_sha256=proposal_input["source_sha256"],
        expected_structure_map_sha256=proposal_input["structure_map_sha256"],
    )
    return batch


def _candidate_package(
    proposal_input: dict[str, Any], response: dict[str, Any]
) -> dict[str, Any]:
    units = [
        _package_source_unit(unit)
        for unit in sorted(
            proposal_input["source_units"], key=lambda item: item["source_order"]
        )
    ]
    units_by_id = {unit["unit_id"]: unit for unit in units}
    source_units = {unit["unit_id"]: unit for unit in proposal_input["source_units"]}
    statements: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []

    for proposal in response["proposals"]:
        source_unit_ids = _proposal_source_units(proposal, source_units)
        proposal_id = f"proposal-sdtmig34-core-{proposal['proposal_key']}-v1"
        relation_ids = []
        for relation_index, relation in enumerate(proposal["relations"], start=1):
            relation_source_ids = _relation_source_units(
                relation, source_unit_ids, source_units
            )
            relation_id = _relation_id(
                proposal["proposal_key"], relation, relation_index
            )
            relation_ids.append(relation_id)
            relations.append(
                {
                    "relation_id": relation_id,
                    "relation_type": relation["relation_type"],
                    "from_id": proposal_id,
                    "to_id": relation["to_id"],
                    "target_kind": relation["target_kind"],
                    "evidence": _evidence_for_units(relation_source_ids, source_units),
                }
            )
        statements.append(
            {
                "statement_id": proposal_id,
                "knowledge_type": proposal["knowledge_type"],
                "subject": proposal["subject"],
                "statement": proposal["statement"],
                "modality": proposal["modality"],
                "scope": proposal["scope"],
                "conditions": proposal["conditions"],
                "exceptions": proposal["exceptions"],
                "evidence": _evidence_for_units(source_unit_ids, source_units),
                "relation_ids": relation_ids,
                "review_status": "proposed",
                "review_receipt_id": None,
            }
        )
        for unit_id in source_unit_ids:
            units_by_id[unit_id]["statement_ids"].append(proposal_id)

    package = {
        "schema_version": "1.0.0",
        "package_id": PACKAGE_ID,
        "source_id": proposal_input["source_id"],
        "source_sha256": proposal_input["source_sha256"],
        "artifacts": proposal_input["artifacts"],
        "units": units,
        "statements": statements,
        "relations": relations,
    }
    validate_extraction_package(package)
    return package


def _package_source_unit(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "unit_id": unit["unit_id"],
        "parent_unit_id": unit["parent_unit_id"],
        "unit_type": unit["unit_type"],
        "title": unit["title"],
        "text_sha256": unit["text_sha256"],
        "locator": unit["locator"],
        "processing_status": unit["processing_status"],
        "processing_note": unit["processing_note"],
        "statement_ids": [],
    }


def _proposal_source_units(
    proposal: dict[str, Any], source_units: dict[str, dict[str, Any]]
) -> list[str]:
    unit_ids = proposal.get("source_unit_ids") or []
    if not unit_ids:
        raise CoreProposalError(f"proposal has no source units: {proposal['proposal_key']}")
    for unit_id in unit_ids:
        if unit_id not in source_units:
            raise CoreProposalError(
                f"proposal {proposal['proposal_key']} references unknown source unit {unit_id}"
            )
        if source_units[unit_id]["unit_id"] in NON_KNOWLEDGE_UNITS:
            raise CoreProposalError(
                f"proposal {proposal['proposal_key']} references non-knowledge unit {unit_id}"
            )
    return list(unit_ids)


def _relation_source_units(
    relation: dict[str, Any],
    default_source_ids: list[str],
    source_units: dict[str, dict[str, Any]],
) -> list[str]:
    unit_ids = relation.get("source_unit_ids") or default_source_ids
    for unit_id in unit_ids:
        if unit_id not in source_units:
            raise CoreProposalError(
                f"relation to {relation['to_id']} references unknown source unit {unit_id}"
            )
        if source_units[unit_id]["unit_id"] in NON_KNOWLEDGE_UNITS:
            raise CoreProposalError(
                f"relation to {relation['to_id']} references non-knowledge unit {unit_id}"
            )
    return list(unit_ids)


def _relation_id(
    proposal_key: str, relation: dict[str, Any], relation_index: int
) -> str:
    relation_type = relation["relation_type"].replace("_", "-")
    target = relation["to_id"].replace("_", "-")
    return f"rel-sdtmig34-core-{proposal_key}-{relation_type}-{target}-{relation_index}"


def _evidence_for_units(
    source_unit_ids: list[str], source_units: dict[str, dict[str, Any]]
) -> list[dict[str, str]]:
    evidence = []
    for unit_id in source_unit_ids:
        unit = source_units[unit_id]
        locator = unit["locator"]
        evidence.append(
            {
                "source_id": unit.get("source_id", "src-cdisc-sdtmig-3-4"),
                "artifact_id": locator["artifact_id"],
                "artifact_sha256": _artifact_sha_for_locator(locator),
                "locator_id": locator["locator_id"],
            }
        )
    return evidence


def _artifact_sha_for_locator(locator: dict[str, Any]) -> str:
    artifact_sha = _ARTIFACT_SHA_BY_ID.get(locator["artifact_id"])
    if artifact_sha is None:
        raise CoreProposalError(f"unknown artifact for locator {locator['locator_id']}")
    return artifact_sha


def _coverage_ledger(
    proposal_input: dict[str, Any], package: dict[str, Any]
) -> list[dict[str, Any]]:
    package_units = {unit["unit_id"]: unit for unit in package["units"]}
    coverage = []
    for unit in proposal_input["source_units"]:
        package_unit = package_units[unit["unit_id"]]
        if unit["unit_id"] in NON_KNOWLEDGE_UNITS:
            disposition = "non_knowledge"
            rationale = NON_KNOWLEDGE_UNITS[unit["unit_id"]]
        elif package_unit["processing_status"] == "deferred":
            disposition = "deferred"
            rationale = package_unit["processing_note"]
        else:
            disposition = "candidate"
            rationale = None
        coverage.append(
            {
                "unit_id": unit["unit_id"],
                "source_order": unit["source_order"],
                "disposition": disposition,
                "rationale": rationale,
                "proposal_ids": package_unit["statement_ids"],
            }
        )
    return coverage


def _blocking_issues(
    *, package: dict[str, Any], coverage: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    candidate_units = {
        entry["unit_id"] for entry in coverage if entry["disposition"] == "candidate"
    }
    unit_proposal_counts = {
        unit["unit_id"]: len(unit["statement_ids"]) for unit in package["units"]
    }
    for unit_id in sorted(candidate_units):
        if unit_proposal_counts.get(unit_id, 0) == 0:
            issues.append(
                {
                    "issue_id": f"issue-{unit_id}-no-proposal",
                    "severity": "blocking",
                    "message": "Candidate source unit has no linked proposal.",
                }
            )
    evidence_keys = [
        _evidence_key(statement) for statement in package["statements"]
    ]
    duplicates = [
        key for key, count in Counter(evidence_keys).items() if count > 1
    ]
    for index, key in enumerate(sorted(duplicates), start=1):
        issues.append(
            {
                "issue_id": f"issue-duplicate-evidence-{index}",
                "severity": "blocking",
                "message": f"Duplicate evidence identity: {key}",
            }
        )
    return issues


def _evidence_key(statement: dict[str, Any]) -> str:
    return "|".join(
        sorted(
            f"{item['source_id']}::{item['artifact_id']}::{item['locator_id']}"
            for item in statement["evidence"]
        )
    )


def build_quality_report(
    proposal_input: dict[str, Any],
    response: dict[str, Any],
    batch: dict[str, Any],
) -> dict[str, Any]:
    package = batch["extraction_package"]
    public_input = _public_proposal_input(proposal_input)
    coverage = batch["coverage"]
    blocking_issues = _blocking_issues(package=package, coverage=coverage)
    knowledge_counts = Counter(
        statement["knowledge_type"] for statement in package["statements"]
    )
    modality_counts = Counter(statement["modality"] for statement in package["statements"])
    evidence_keys = [_evidence_key(statement) for statement in package["statements"]]
    coverage_by_id = {entry["unit_id"]: entry for entry in coverage}

    return {
        "schema_version": "1.0.0",
        "extraction_id": "extract-sdtmig34-core-proposals-v1",
        "source_id": proposal_input["source_id"],
        "source_sha256": proposal_input["source_sha256"],
        "structure_map_id": proposal_input["structure_map_id"],
        "structure_map_sha256": proposal_input["structure_map_sha256"],
        "prompt_id": proposal_input["prompt_id"],
        "prompt_sha256": proposal_input["prompt_sha256"],
        "model_id": response["model_id"],
        "response_id": response["response_id"],
        "response_sha256": sha256_payload(response),
        "input_projection_sha256": sha256_payload(public_input),
        "batch_id": batch["batch_id"],
        "batch_sha256": sha256_payload(batch),
        "candidate_package_id": package["package_id"],
        "quality_summary": batch["quality_summary"],
        "semantic_quality": {
            "review_required_count": len(package["statements"]),
            "raw_source_text_committed": False,
            "statement_status_counts": dict(
                sorted(Counter(s["review_status"] for s in package["statements"]).items())
            ),
            "knowledge_type_counts": dict(sorted(knowledge_counts.items())),
            "modality_counts": dict(sorted(modality_counts.items())),
            "multi_source_proposal_count": sum(
                len(statement["evidence"]) > 1 for statement in package["statements"]
            ),
            "duplicate_evidence_key_count": len(evidence_keys) - len(set(evidence_keys)),
            "candidate_without_proposal_count": sum(
                entry["disposition"] == "candidate" and not entry["proposal_ids"]
                for entry in coverage
            ),
            "non_knowledge_with_rationale_count": sum(
                entry["disposition"] == "non_knowledge" and bool(entry["rationale"])
                for entry in coverage
            ),
        },
        "blocking_issues": blocking_issues,
        "coverage": [
            {
                "unit_id": entry["unit_id"],
                "source_order": entry["source_order"],
                "disposition": entry["disposition"],
                "proposal_ids": entry["proposal_ids"],
                "rationale": entry["rationale"],
            }
            for entry in coverage
        ],
        "input_projection": {
            "source_text_included": proposal_input["source_text_included"],
            "unit_total": len(proposal_input["source_units"]),
            "deep_structure_map_unit_count": len(proposal_input["source_units"]),
            "units": [
                {
                    "unit_id": unit["unit_id"],
                    "locator_id": unit["locator"]["locator_id"],
                    "artifact_id": unit["locator"]["artifact_id"],
                    "locator_type": unit["locator"]["locator_type"],
                    "physical_page": unit["locator"]["physical_page"],
                    "printed_page": unit["locator"]["printed_page"],
                    "section_path": unit["locator"]["section_path"],
                    "text_sha256": unit["text_sha256"],
                    "source_origin": unit["source_origin"],
                    "source_order": unit["source_order"],
                    "disposition": coverage_by_id[unit["unit_id"]]["disposition"],
                }
                for unit in proposal_input["source_units"]
            ],
        },
        "proposal_index": [
            {
                "statement_id": statement["statement_id"],
                "subject": statement["subject"],
                "knowledge_type": statement["knowledge_type"],
                "modality": statement["modality"],
                "review_status": statement["review_status"],
                "locator_ids": [
                    evidence["locator_id"] for evidence in statement["evidence"]
                ],
            }
            for statement in package["statements"]
        ],
        "gate_status": batch["quality_summary"]["gate_status"],
    }


def build_inbox_card(report: dict[str, Any], batch: dict[str, Any]) -> str:
    package = batch["extraction_package"]
    proposal_rows = "\n".join(
        "| {statement_id} | {subject} | {knowledge_type} | {modality} | {locators} |".format(
            statement_id=statement["statement_id"],
            subject=statement["subject"],
            knowledge_type=statement["knowledge_type"],
            modality=statement["modality"],
            locators=", ".join(item["locator_id"] for item in statement["evidence"]),
        )
        for statement in package["statements"]
    )
    coverage_summary = report["quality_summary"]
    record = {
        "id": "inbox-sdtmig34-core-proposal-batch",
        "type": "knowledge_proposal_batch",
        "title": "SDTMIG 3.4 Core Proposal Batch",
        "version": "0.1.0",
        "schema_version": "1.0.0",
        "content_status": "inbox",
        "approval_status": "proposed",
        "domains": ["SDTM", "data_standards"],
        "workflow_stages": ["sdtm_spec", "sdtm_programming"],
        "topics": ["sdtmig-3-4", "core", "proposal_batch", "p6-p3-c"],
        "aliases": ["SDTMIG 3.4 Core proposals"],
        "authority": "ai_inference",
        "applicability": {
            "therapeutic_areas": [],
            "trial_phases": [],
            "sponsor_ids": [],
            "study_ids": [],
            "conditions": ["not_approved", "p6-p3-c-small-batch"],
        },
        "sources": ["src-cdisc-sdtmig-3-4"],
        "owner": "Clinical Knowledge Governance",
        "created": "2026-07-15T00:00:00+08:00",
        "last_reviewed": None,
        "review_due": None,
        "supersedes": [],
        "superseded_by": None,
        "rights_status": "restricted",
        "allowed_uses": ["governance_review_only"],
        "storage_mode": "committed",
        "contract_compatibility": {
            "minimum": "1.0.0",
            "maximum_exclusive": "2.0.0",
        },
        "approval_receipt_id": None,
        "audit_reference": None,
        "summary": (
            "SDTMIG 3.4 Core 小批次原子知识候选；仅供 P6-P3-C 质量审阅，"
            "不是 approved 知识。"
        ),
        "proposal_batch_id": report["batch_id"],
        "proposal_report_id": report["extraction_id"],
    }
    body = f"""# SDTMIG 3.4 Core Proposal Batch

**状态：proposed / inbox。** 本卡是 P6-P3-C 的中文审阅入口，只保存候选摘要、locator 与治理状态；原始 PDF/XLSX 仍在受控 source package 中，不复制进 Obsidian。

## 本批次用途

- 验证 SDTMIG 3.4 Core 范围的 source unit → proposal → evidence locator 链路。
- 验证每个 source unit 在 coverage ledger 中只出现一次，并明确区分 `candidate` 与 `non_knowledge`。
- 供后续 P3-D 生成中文 ReviewPacket；本卡不得被 Runtime 当作 approved knowledge 调用。

## 质量摘要

- Source units：{coverage_summary["unit_total"]}
- Candidate units：{coverage_summary["candidate_unit_count"]}
- Non-knowledge units：{coverage_summary["non_knowledge_unit_count"]}
- Proposals：{coverage_summary["proposal_total"]}
- Gate：{coverage_summary["gate_status"]}
- Report：`clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/core-proposal-quality-report.json`
- Batch：`clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/derived/core-proposal-batch.json`
- 来源卡：[[60_Sources/Registry/CDISC SDTMIG 3.4]]

## 候选索引

| Proposal | Subject | Type | Modality | Locators |
|---|---|---|---|---|
{proposal_rows}

## 审阅要求

- 不得手工改写 `approval_status`。
- P3-D 之前不得移动到 `20_Knowledge/Standards/`。
- 后续 ReviewPacket 需要逐条确认 statement 语义、适用范围、条件、例外和 locator 是否忠实。

[[10_MOC/Sources-MOC|返回来源导航]]
"""
    return _render_markdown_card(record, body)


def _render_markdown_card(record: dict[str, Any], body: str) -> str:
    card_record = dict(record)
    body_text = body.strip()
    card_record["content_hash"] = _vault_content_hash(card_record, body_text)
    frontmatter = yaml.safe_dump(
        card_record, allow_unicode=True, sort_keys=False
    ).strip()
    return f"---\n{frontmatter}\n---\n\n{body_text}\n"


def _vault_content_hash(record: dict[str, Any], body: str) -> str:
    payload = {
        "frontmatter": {
            key: value for key, value in record.items() if key != "content_hash"
        },
        "body": body,
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def run_core_proposals(
    *,
    package_dir: str | Path = DEFAULT_PACKAGE,
    response_path: str | Path = DEFAULT_RESPONSE,
    prompt_path: str | Path = DEFAULT_PROMPT,
    include_source_text: bool = False,
) -> dict[str, Any]:
    proposal_input = build_core_proposal_input(
        package_dir=package_dir,
        prompt_path=prompt_path,
        include_source_text=include_source_text,
    )
    _prepare_artifact_lookup(proposal_input)
    response = load_candidate_response(
        response_path=response_path,
        proposal_input=proposal_input,
    )
    batch = build_proposal_batch(proposal_input, response)
    report = build_quality_report(proposal_input, response, batch)
    inbox_card = build_inbox_card(report, batch)
    return {
        "input": proposal_input,
        "response": response,
        "batch": batch,
        "report": report,
        "inbox_card": inbox_card,
    }


def _prepare_artifact_lookup(proposal_input: dict[str, Any]) -> None:
    _ARTIFACT_SHA_BY_ID.clear()
    _ARTIFACT_SHA_BY_ID.update(
        {
            artifact["artifact_id"]: artifact["artifact_sha256"]
            for artifact in proposal_input["artifacts"]
        }
    )


def _public_proposal_input(proposal_input: dict[str, Any]) -> dict[str, Any]:
    public = deepcopy(proposal_input)
    for unit in public["source_units"]:
        unit.pop("source_text", None)
        unit.pop("source_text_sha256", None)
    public["source_text_included"] = False
    return public


def _assert_unique(values: list[str], label: str) -> None:
    if len(set(values)) != len(values):
        raise CoreProposalError(f"duplicate {label} id")


def _assert_stable_key(value: str, label: str) -> None:
    if not _STABLE_KEY.fullmatch(value):
        raise CoreProposalError(f"{label} is not stable kebab-case: {value}")


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_json_bytes(payload))


def write_text(path: str | Path, payload: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload, encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--response", type=Path, default=DEFAULT_RESPONSE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--batch", type=Path, default=DEFAULT_BATCH)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--inbox-card", type=Path, default=DEFAULT_INBOX_CARD)
    parser.add_argument("--include-source-text", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    result = run_core_proposals(
        package_dir=args.package_dir,
        response_path=args.response,
        prompt_path=args.prompt,
        include_source_text=args.include_source_text,
    )
    if not args.no_write:
        write_json(args.input, result["input"])
        write_json(args.batch, result["batch"])
        write_json(args.report, result["report"])
        write_text(args.inbox_card, result["inbox_card"])

    report = result["report"]
    print(
        "Core proposal extraction "
        f"{report['gate_status']}: {report['quality_summary']['proposal_total']} "
        f"proposals from {report['quality_summary']['unit_total']} source units"
    )


if __name__ == "__main__":
    try:
        main()
    except (CoreProposalError, ProposalBatchContractError) as error:
        raise SystemExit(f"Core proposal extraction failed: {error}") from error
