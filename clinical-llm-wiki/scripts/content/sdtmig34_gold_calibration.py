"""P6-P3-B Gold calibration for SDTMIG 3.4 proposal extraction.

The calibration path keeps the model boundary narrow: the replayed model
response proposes semantics only.  This module projects source units from the
approved deep structure map and companion release accession, injects closed
evidence, builds a proposed-only Proposal Batch, and scores it against the
human-approved Gold Set.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from scripts.content.extraction_contract import validate_extraction_package
from scripts.content.proposal_batch_contract import (
    ProposalBatchContractError,
    score_gold_proposals,
    validate_proposal_batch,
)
from scripts.pdf.structure_map_contract import (
    project_locator_to_p1,
    structure_map_sha256,
    validate_structure_map,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKAGE = ROOT / "sources" / "packages" / "src-cdisc-sdtmig-3-4"
DEFAULT_GOLD = ROOT / "tests" / "fixtures" / "knowledge" / "sdtmig34-gold-set.json"
DEFAULT_RESPONSE = (
    ROOT / "tests" / "fixtures" / "knowledge" / "sdtmig34-gold-proposal-response-v1.json"
)
DEFAULT_PROMPT = ROOT / "scripts" / "content" / "prompts" / "sdtmig34_atomic_proposal_v1.md"
DEFAULT_RELEASE = ROOT / "sources" / "accessions" / "cdisc-sdtmig-3-4-release.json"
DEFAULT_REPORT = DEFAULT_PACKAGE / "gold-proposal-calibration-report.json"
DEFAULT_BATCH = DEFAULT_PACKAGE / "derived" / "gold-proposal-batch.json"
DEFAULT_INPUT = DEFAULT_PACKAGE / "derived" / "gold-calibration-input.json"

RELEASE_ARTIFACT_ID = "artifact-cdisc-sdtmig-3-4-release-accession"
WEB_ERRATA_UNIT_ID = "unit-sdtmig34-web-errata-section15"
WEB_ERRATA_LOCATOR_ID = "loc-sdtmig34-web-errata-section15"
PROMPT_ID = "prompt-sdtmig34-atomic-proposal-v1"
RUN_ID = "run-sdtmig34-gold-calibration-v1"
BATCH_ID = "batch-sdtmig34-gold-calibration-v1"
PACKAGE_ID = "pkg-sdtmig34-gold-calibration-v1"

_STABLE_KEY = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class GoldCalibrationError(ValueError):
    """Raised when the Gold calibration path cannot be trusted."""


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


def build_gold_calibration_input(
    *,
    package_dir: str | Path = DEFAULT_PACKAGE,
    gold_path: str | Path = DEFAULT_GOLD,
    prompt_path: str | Path = DEFAULT_PROMPT,
    release_path: str | Path = DEFAULT_RELEASE,
    include_source_text: bool = False,
) -> dict[str, Any]:
    """Project the Gold scope from approved source structures, not from answers."""

    package = Path(package_dir)
    source = load_json(package / "source-manifest.json")
    summary = load_json(package / "deep-structure-summary.json")
    deep_map = load_json(package / "derived" / "structure-map-deep.json")
    release = load_json(release_path)
    gold = load_json(gold_path)
    validate_structure_map(deep_map)
    validate_extraction_package(gold)

    actual_map_hash = structure_map_sha256(deep_map)
    if actual_map_hash != summary["deep_structure_map_sha256"]:
        raise GoldCalibrationError("deep structure map hash differs from summary")
    if deep_map["source_id"] != source["source_id"]:
        raise GoldCalibrationError("deep structure map source_id differs from manifest")
    if deep_map["source_sha256"] != source["original_sha256"]:
        raise GoldCalibrationError("deep structure map source_sha256 differs from manifest")

    artifacts = _artifact_identities(source, release_path, gold)
    units = _project_scope_units(
        gold=gold,
        deep_map=deep_map,
        release=release,
        include_source_text=include_source_text,
        package=package,
        source=source,
    )
    prompt_hash = sha256_file(prompt_path)
    payload = {
        "schema_version": "1.0.0",
        "input_id": "input-sdtmig34-gold-calibration-v1",
        "source_id": source["source_id"],
        "source_sha256": source["original_sha256"],
        "structure_map_id": deep_map["structure_map_id"],
        "structure_map_sha256": actual_map_hash,
        "gold_package_id": gold["package_id"],
        "prompt_id": PROMPT_ID,
        "prompt_sha256": prompt_hash,
        "source_text_included": include_source_text,
        "artifacts": artifacts,
        "source_units": units,
    }
    _assert_unique([unit["unit_id"] for unit in units], "source unit")
    _assert_unique([unit["locator"]["locator_id"] for unit in units], "locator")
    return payload


def _artifact_identities(
    source: dict[str, Any], release_path: str | Path, gold: dict[str, Any]
) -> list[dict[str, Any]]:
    gold_artifacts = {artifact["artifact_id"]: artifact for artifact in gold["artifacts"]}
    artifacts = [
        {
            "artifact_id": artifact["artifact_id"],
            "role": artifact["role"],
            "media_type": artifact["media_type"],
            "artifact_sha256": artifact["original_sha256"],
        }
        for artifact in source["artifacts"]
    ]
    release_sha = sha256_file(release_path)
    artifacts.append(
        {
            "artifact_id": RELEASE_ARTIFACT_ID,
            "role": "companion_evidence",
            "media_type": "application/json",
            "artifact_sha256": release_sha,
        }
    )
    for artifact in artifacts:
        gold_artifact = gold_artifacts.get(artifact["artifact_id"])
        if gold_artifact is None:
            raise GoldCalibrationError(
                f"Gold Set is missing artifact {artifact['artifact_id']}"
            )
        if gold_artifact["artifact_sha256"] != artifact["artifact_sha256"]:
            raise GoldCalibrationError(
                f"artifact hash differs from Gold Set: {artifact['artifact_id']}"
            )
    return sorted(artifacts, key=lambda item: item["artifact_id"])


def _project_scope_units(
    *,
    gold: dict[str, Any],
    deep_map: dict[str, Any],
    release: dict[str, Any],
    include_source_text: bool,
    package: Path,
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    owner_by_locator = {
        locator_id: unit
        for unit in deep_map["units"]
        for locator_id in unit["locator_ids"]
    }
    locator_by_id = {locator["locator_id"]: locator for locator in deep_map["locators"]}
    projected: list[dict[str, Any]] = []

    for source_order, gold_unit in enumerate(gold["units"]):
        locator_id = gold_unit["locator"]["locator_id"]
        if locator_id == WEB_ERRATA_LOCATOR_ID:
            unit = _web_errata_source_unit(release, source_order)
        else:
            owner = owner_by_locator.get(locator_id)
            if owner is None:
                raise GoldCalibrationError(
                    f"Gold locator is absent from deep map: {locator_id}"
                )
            locator = locator_by_id[locator_id]
            unit = {
                "unit_id": owner["unit_id"],
                "parent_unit_id": owner.get("parent_unit_id"),
                "unit_type": owner["unit_type"],
                "title": owner.get("title"),
                "text_sha256": owner["text_sha256"],
                "locator": project_locator_to_p1(locator),
                "processing_status": _processing_status(owner),
                "processing_note": _processing_note(owner),
                "source_origin": "deep_structure_map",
                "source_order": source_order,
            }
        projected.append(unit)

    selected_ids = {unit["unit_id"] for unit in projected}
    for unit in projected:
        if unit["parent_unit_id"] not in selected_ids:
            unit["parent_unit_id"] = None

    if include_source_text:
        _attach_source_text(projected, package=package, source=source, release=release)
    return projected


def _processing_status(owner: dict[str, Any]) -> str:
    if owner["unit_type"] == "example" or owner.get("content_role") == "example":
        return "example"
    return "candidate"


def _processing_note(owner: dict[str, Any]) -> str | None:
    if owner["unit_type"] == "example" or owner.get("content_role") == "example":
        return "Calibration example source unit; do not promote to a universal requirement."
    return None


def _web_errata_source_unit(release: dict[str, Any], source_order: int) -> dict[str, Any]:
    text = _release_errata_claim_text(release)
    return {
        "unit_id": WEB_ERRATA_UNIT_ID,
        "parent_unit_id": None,
        "unit_type": "erratum",
        "title": "SDTMIG 3.4 release errata Section 1.5",
        "text_sha256": sha256_text(text),
        "locator": {
            "locator_id": WEB_ERRATA_LOCATOR_ID,
            "artifact_id": RELEASE_ARTIFACT_ID,
            "locator_type": "web_section",
            "physical_page": None,
            "printed_page": None,
            "section_path": [
                "Errata",
                "SDTMIG v3.4",
                "Section 1.5 - Known Issues",
            ],
            "bbox": None,
            "sheet_name": None,
            "row_number": None,
            "table_id": None,
            "row_key": None,
        },
        "processing_status": "candidate",
        "processing_note": "Companion erratum; it qualifies the release evidence without modifying PDF bytes.",
        "source_origin": "release_accession",
        "source_order": source_order,
    }


def _release_errata_claim_text(release: dict[str, Any]) -> str:
    entries = [
        f"{item['section']}: {item['claim']}"
        for item in release["locators"]
        if item["section"] in {"Errata - SDTMIG v3.4", "Known Issues"}
    ]
    if not entries:
        raise GoldCalibrationError("release accession has no errata or known-issue claim")
    return " | ".join(entries)


def _attach_source_text(
    units: list[dict[str, Any]],
    *,
    package: Path,
    source: dict[str, Any],
    release: dict[str, Any],
) -> None:
    import fitz
    from openpyxl import load_workbook

    artifacts = {artifact["artifact_id"]: artifact for artifact in source["artifacts"]}
    pdf_artifact = next(
        artifact for artifact in source["artifacts"] if artifact["role"] == "primary_citation"
    )
    xlsx_artifact = next(
        artifact
        for artifact in source["artifacts"]
        if artifact["media_type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    pdf = fitz.open(package / pdf_artifact["original_relative_path"])
    workbook = load_workbook(
        package / xlsx_artifact["original_relative_path"],
        read_only=True,
        data_only=False,
    )
    try:
        for unit in units:
            locator = unit["locator"]
            artifact = artifacts.get(locator["artifact_id"])
            if locator["locator_type"] == "pdf_region":
                source_text = _pdf_text(pdf, locator, unit["unit_type"])
            elif locator["locator_type"] == "xlsx_row":
                source_text = _xlsx_row_text(workbook, locator)
            elif locator["locator_type"] == "web_section":
                source_text = _release_errata_claim_text(release)
            else:
                raise GoldCalibrationError(
                    f"unsupported locator type: {locator['locator_type']}"
                )
            if artifact is not None and artifact["original_sha256"] != locator.get(
                "artifact_sha256", artifact["original_sha256"]
            ):
                raise GoldCalibrationError("artifact hash drift while reading source text")
            unit["source_text"] = normalized_text(source_text)
            unit["source_text_sha256"] = sha256_text(source_text)
    finally:
        workbook.close()
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


def _xlsx_row_text(workbook: Any, locator: dict[str, Any]) -> str:
    row = [cell.value for cell in workbook[locator["sheet_name"]][locator["row_number"]]]
    return json.dumps(row, ensure_ascii=False, separators=(",", ":"))


def load_candidate_response(
    *,
    response_path: str | Path = DEFAULT_RESPONSE,
    calibration_input: dict[str, Any],
) -> dict[str, Any]:
    response = load_json(response_path)
    if response["schema_version"] != "1.0.0":
        raise GoldCalibrationError("unsupported response schema_version")
    for field in ("source_id", "source_sha256", "prompt_id", "prompt_sha256"):
        if response[field] != calibration_input[field]:
            raise GoldCalibrationError(f"response {field} differs from calibration input")
    if response["prompt_id"] != PROMPT_ID:
        raise GoldCalibrationError("response prompt_id is not the frozen P3-B prompt")
    _assert_unique([item["proposal_key"] for item in response["proposals"]], "proposal")
    for proposal in response["proposals"]:
        _assert_stable_key(proposal["proposal_key"], "proposal_key")
    return response


def build_proposal_batch(
    calibration_input: dict[str, Any],
    response: dict[str, Any],
    gold_package: dict[str, Any],
    *,
    require_gold_pass: bool = True,
) -> dict[str, Any]:
    _prepare_artifact_lookup(calibration_input)
    package = _candidate_package(calibration_input, response)
    gold_evaluation = score_gold_proposals(package, gold_package)
    batch = {
        "schema_version": "1.0.0",
        "batch_id": BATCH_ID,
        "source_id": calibration_input["source_id"],
        "source_sha256": calibration_input["source_sha256"],
        "structure_map_id": calibration_input["structure_map_id"],
        "structure_map_sha256": calibration_input["structure_map_sha256"],
        "scope": {
            "scope_id": "scope-sdtmig34-gold-calibration-v1",
            "description": "P3-B Gold calibration only; no approved knowledge is produced.",
            "unit_ids": [unit["unit_id"] for unit in calibration_input["source_units"]],
        },
        "generation": {
            "method": "llm_assisted",
            "run_id": RUN_ID,
            "prompt_id": calibration_input["prompt_id"],
            "prompt_sha256": calibration_input["prompt_sha256"],
            "model_id": response["model_id"],
        },
        "extraction_package": package,
        "coverage": _coverage_ledger(calibration_input, package),
        "quality_summary": {
            "unit_total": len(calibration_input["source_units"]),
            "candidate_unit_count": len(calibration_input["source_units"]),
            "non_knowledge_unit_count": 0,
            "deferred_unit_count": 0,
            "proposal_total": len(package["statements"]),
            "blocking_issue_count": 0,
            "gate_status": "pass",
        },
        "gold_evaluation": gold_evaluation,
    }
    validate_proposal_batch(
        batch,
        expected_source_sha256=calibration_input["source_sha256"],
        expected_structure_map_sha256=calibration_input["structure_map_sha256"],
    )
    if require_gold_pass and gold_evaluation["gate_status"] != "pass":
        raise GoldCalibrationError("Gold calibration did not pass the expansion gate")
    return batch


def _candidate_package(
    calibration_input: dict[str, Any], response: dict[str, Any]
) -> dict[str, Any]:
    units = [
        _package_source_unit(unit)
        for unit in sorted(
            calibration_input["source_units"], key=lambda item: item["source_order"]
        )
    ]
    units_by_id = {unit["unit_id"]: unit for unit in units}
    source_units = {
        unit["unit_id"]: unit for unit in calibration_input["source_units"]
    }
    statements: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []

    for proposal in response["proposals"]:
        source_unit_ids = _proposal_source_units(proposal, source_units)
        proposal_id = f"proposal-sdtmig34-gold-{proposal['proposal_key']}-v1"
        relation_ids = []
        for relation_index, relation in enumerate(proposal["relations"], start=1):
            relation_source_ids = _relation_source_units(relation, source_unit_ids, source_units)
            relation_id = _relation_id(proposal["proposal_key"], relation, relation_index)
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
        "source_id": calibration_input["source_id"],
        "source_sha256": calibration_input["source_sha256"],
        "artifacts": calibration_input["artifacts"],
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
    unit_ids = proposal["source_unit_ids"]
    if not unit_ids:
        raise GoldCalibrationError(f"proposal has no source units: {proposal['proposal_key']}")
    for unit_id in unit_ids:
        if unit_id not in source_units:
            raise GoldCalibrationError(
                f"proposal {proposal['proposal_key']} references unknown source unit {unit_id}"
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
            raise GoldCalibrationError(
                f"relation to {relation['to_id']} references unknown source unit {unit_id}"
            )
    return list(unit_ids)


def _relation_id(proposal_key: str, relation: dict[str, Any], relation_index: int) -> str:
    relation_type = relation["relation_type"].replace("_", "-")
    target = relation["to_id"].replace("_", "-")
    return f"rel-sdtmig34-gold-{proposal_key}-{relation_type}-{target}-{relation_index}"


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
                "artifact_sha256": _artifact_sha_for_locator(locator, source_units),
                "locator_id": locator["locator_id"],
            }
        )
    return evidence


def _artifact_sha_for_locator(
    locator: dict[str, Any], source_units: dict[str, dict[str, Any]]
) -> str:
    for unit in source_units.values():
        for artifact in unit.get("_artifacts", []):
            if artifact["artifact_id"] == locator["artifact_id"]:
                return artifact["artifact_sha256"]
    # Filled by _with_artifact_refs before evidence construction.
    artifact = _ARTIFACT_SHA_BY_ID.get(locator["artifact_id"])
    if artifact is None:
        raise GoldCalibrationError(f"unknown artifact for locator {locator['locator_id']}")
    return artifact


_ARTIFACT_SHA_BY_ID: dict[str, str] = {}


def _coverage_ledger(
    calibration_input: dict[str, Any], package: dict[str, Any]
) -> list[dict[str, Any]]:
    package_units = {unit["unit_id"]: unit for unit in package["units"]}
    return [
        {
            "unit_id": unit["unit_id"],
            "source_order": unit["source_order"],
            "disposition": "candidate",
            "rationale": None,
            "proposal_ids": package_units[unit["unit_id"]]["statement_ids"],
        }
        for unit in calibration_input["source_units"]
    ]


def build_calibration_report(
    calibration_input: dict[str, Any],
    response: dict[str, Any],
    batch: dict[str, Any],
    gold_package: dict[str, Any],
) -> dict[str, Any]:
    candidate_by_id = {
        statement["statement_id"]: statement
        for statement in batch["extraction_package"]["statements"]
    }
    gold_by_id = {
        statement["statement_id"]: statement for statement in gold_package["statements"]
    }
    text_differences = []
    for comparison in batch["gold_evaluation"]["comparisons"]:
        if comparison["text_exact"] is not False:
            continue
        candidate = candidate_by_id[comparison["candidate_statement_id"]]
        expected = gold_by_id[comparison["expected_statement_id"]]
        text_differences.append(
            {
                "expected_statement_id": expected["statement_id"],
                "candidate_statement_id": candidate["statement_id"],
                "expected_statement": expected["statement"],
                "candidate_statement": candidate["statement"],
                "review_required": True,
            }
        )

    public_input = _public_calibration_input(calibration_input)
    return {
        "schema_version": "1.0.0",
        "calibration_id": "calibration-sdtmig34-gold-v1",
        "source_id": calibration_input["source_id"],
        "source_sha256": calibration_input["source_sha256"],
        "structure_map_id": calibration_input["structure_map_id"],
        "structure_map_sha256": calibration_input["structure_map_sha256"],
        "prompt_id": calibration_input["prompt_id"],
        "prompt_sha256": calibration_input["prompt_sha256"],
        "model_id": response["model_id"],
        "response_id": response["response_id"],
        "response_sha256": sha256_payload(response),
        "input_projection_sha256": sha256_payload(public_input),
        "batch_id": batch["batch_id"],
        "batch_sha256": sha256_payload(batch),
        "candidate_package_id": batch["extraction_package"]["package_id"],
        "quality_summary": batch["quality_summary"],
        "gold_evaluation": batch["gold_evaluation"],
        "text_differences": text_differences,
        "input_projection": {
            "source_text_included": calibration_input["source_text_included"],
            "unit_total": len(calibration_input["source_units"]),
            "deep_structure_map_unit_count": sum(
                unit["source_origin"] == "deep_structure_map"
                for unit in calibration_input["source_units"]
            ),
            "release_accession_unit_count": sum(
                unit["source_origin"] == "release_accession"
                for unit in calibration_input["source_units"]
            ),
            "units": [
                {
                    "unit_id": unit["unit_id"],
                    "locator_id": unit["locator"]["locator_id"],
                    "artifact_id": unit["locator"]["artifact_id"],
                    "locator_type": unit["locator"]["locator_type"],
                    "text_sha256": unit["text_sha256"],
                    "source_origin": unit["source_origin"],
                    "source_order": unit["source_order"],
                }
                for unit in calibration_input["source_units"]
            ],
        },
        "gate_status": batch["gold_evaluation"]["gate_status"],
    }


def run_gold_calibration(
    *,
    package_dir: str | Path = DEFAULT_PACKAGE,
    gold_path: str | Path = DEFAULT_GOLD,
    response_path: str | Path = DEFAULT_RESPONSE,
    prompt_path: str | Path = DEFAULT_PROMPT,
    release_path: str | Path = DEFAULT_RELEASE,
    include_source_text: bool = False,
    require_gold_pass: bool = True,
) -> dict[str, dict[str, Any]]:
    calibration_input = build_gold_calibration_input(
        package_dir=package_dir,
        gold_path=gold_path,
        prompt_path=prompt_path,
        release_path=release_path,
        include_source_text=include_source_text,
    )
    _prepare_artifact_lookup(calibration_input)
    response = load_candidate_response(
        response_path=response_path,
        calibration_input=calibration_input,
    )
    gold_package = load_json(gold_path)
    batch = build_proposal_batch(
        calibration_input,
        response,
        gold_package,
        require_gold_pass=require_gold_pass,
    )
    report = build_calibration_report(calibration_input, response, batch, gold_package)
    return {"input": calibration_input, "batch": batch, "report": report}


def _prepare_artifact_lookup(calibration_input: dict[str, Any]) -> None:
    _ARTIFACT_SHA_BY_ID.clear()
    _ARTIFACT_SHA_BY_ID.update(
        {
            artifact["artifact_id"]: artifact["artifact_sha256"]
            for artifact in calibration_input["artifacts"]
        }
    )


def _public_calibration_input(calibration_input: dict[str, Any]) -> dict[str, Any]:
    public = deepcopy(calibration_input)
    for unit in public["source_units"]:
        unit.pop("source_text", None)
        unit.pop("source_text_sha256", None)
    public["source_text_included"] = False
    return public


def _assert_unique(values: list[str], label: str) -> None:
    if len(set(values)) != len(values):
        raise GoldCalibrationError(f"duplicate {label} id")


def _assert_stable_key(value: str, label: str) -> None:
    if not _STABLE_KEY.fullmatch(value):
        raise GoldCalibrationError(f"{label} is not stable kebab-case: {value}")


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_json_bytes(payload))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--response", type=Path, default=DEFAULT_RESPONSE)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--batch", type=Path, default=DEFAULT_BATCH)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--include-source-text", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--allow-failing-gold", action="store_true")
    args = parser.parse_args()

    result = run_gold_calibration(
        package_dir=args.package_dir,
        gold_path=args.gold,
        response_path=args.response,
        prompt_path=args.prompt,
        release_path=args.release,
        include_source_text=args.include_source_text,
        require_gold_pass=not args.allow_failing_gold,
    )
    if not args.no_write:
        write_json(args.report, result["report"])
        write_json(args.batch, result["batch"])
        write_json(args.input, result["input"])
    report = result["report"]
    evaluation = report["gold_evaluation"]
    print(
        "Gold calibration "
        f"{report['gate_status']}: "
        f"{evaluation['structural_match_count']}/{evaluation['expected_total']} "
        "structural matches, "
        f"{evaluation['missing_count']} missing, "
        f"{evaluation['unexpected_count']} unexpected"
    )


if __name__ == "__main__":
    try:
        main()
    except (GoldCalibrationError, ProposalBatchContractError) as error:
        raise SystemExit(f"ERROR: {error}") from error
