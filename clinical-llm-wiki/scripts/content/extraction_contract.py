"""Validation helpers for Wiki-internal source extraction packages.

The JSON Schema guarantees field shape.  This module adds the small set of
referential checks JSON Schema cannot express: locator evidence, statement
membership, and typed-relation closure.  Runtime consumers do not load raw
extraction packages; they continue to use the Engine-owned public contracts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = ROOT / "schemas" / "extraction" / "knowledge-extraction.schema.json"


class ExtractionContractError(ValueError):
    """Raised when a parsed source package is structurally or referentially invalid."""


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_extraction_package(
    payload: dict[str, Any], *, schema_path: str | Path = DEFAULT_SCHEMA
) -> None:
    """Validate one extraction package and fail closed on dangling references."""

    schema = _load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.path) or "<root>"
        raise ExtractionContractError(f"schema validation failed at {location}: {first.message}")

    source_id = payload["source_id"]
    source_sha256 = payload["source_sha256"]
    artifacts = {artifact["artifact_id"]: artifact for artifact in payload["artifacts"]}
    units = {unit["unit_id"]: unit for unit in payload["units"]}
    statements = {statement["statement_id"]: statement for statement in payload["statements"]}
    relations = {relation["relation_id"]: relation for relation in payload["relations"]}
    locators = {
        unit["locator"]["locator_id"]: unit["locator"] for unit in units.values()
    }

    if len(artifacts) != len(payload["artifacts"]):
        raise ExtractionContractError("duplicate artifact id")
    if len(units) != len(payload["units"]):
        raise ExtractionContractError("duplicate source unit id")
    if len(statements) != len(payload["statements"]):
        raise ExtractionContractError("duplicate statement id")
    if len(relations) != len(payload["relations"]):
        raise ExtractionContractError("duplicate relation id")
    if len(locators) != len(units):
        raise ExtractionContractError("duplicate locator id")
    primary_artifacts = [
        artifact for artifact in artifacts.values() if artifact["role"] == "primary_citation"
    ]
    if len(primary_artifacts) != 1:
        raise ExtractionContractError("exactly one primary_citation artifact is required")
    if primary_artifacts[0]["artifact_sha256"] != source_sha256:
        raise ExtractionContractError("source_sha256 must match the primary citation artifact")

    for unit in units.values():
        parent_id = unit["parent_unit_id"]
        if parent_id is not None and parent_id not in units:
            raise ExtractionContractError(
                f"source unit {unit['unit_id']} has dangling parent {parent_id}"
            )
        for statement_id in unit["statement_ids"]:
            if statement_id not in statements:
                raise ExtractionContractError(
                    f"source unit {unit['unit_id']} references missing statement {statement_id}"
                )
        locator = unit["locator"]
        if locator["artifact_id"] not in artifacts:
            raise ExtractionContractError(
                f"locator {locator['locator_id']} references missing artifact {locator['artifact_id']}"
            )

    for statement in statements.values():
        for evidence in statement["evidence"]:
            _validate_evidence(evidence, source_id, artifacts, locators)
        for relation_id in statement["relation_ids"]:
            if relation_id not in relations:
                raise ExtractionContractError(
                    f"statement {statement['statement_id']} references missing relation {relation_id}"
                )

    known_internal_ids = set(units) | set(statements)
    for relation in relations.values():
        if relation["from_id"] not in known_internal_ids:
            raise ExtractionContractError(
                f"relation {relation['relation_id']} has dangling from_id {relation['from_id']}"
            )
        if (
            relation["target_kind"] in {"statement", "source_unit"}
            and relation["to_id"] not in known_internal_ids
        ):
            raise ExtractionContractError(
                f"relation {relation['relation_id']} has dangling to_id {relation['to_id']}"
            )
        for evidence in relation["evidence"]:
            _validate_evidence(evidence, source_id, artifacts, locators)


def _validate_evidence(
    evidence: dict[str, Any],
    source_id: str,
    artifacts: dict[str, dict[str, Any]],
    locators: dict[str, dict[str, Any]],
) -> None:
    if evidence["source_id"] != source_id:
        raise ExtractionContractError("evidence source_id does not match extraction package")
    artifact = artifacts.get(evidence["artifact_id"])
    if artifact is None:
        raise ExtractionContractError(
            f"evidence references missing artifact {evidence['artifact_id']}"
        )
    if evidence["artifact_sha256"] != artifact["artifact_sha256"]:
        raise ExtractionContractError("evidence artifact_sha256 does not match artifact identity")
    if evidence["locator_id"] not in locators:
        raise ExtractionContractError(
            f"evidence references missing locator {evidence['locator_id']}"
        )
    if locators[evidence["locator_id"]]["artifact_id"] != evidence["artifact_id"]:
        raise ExtractionContractError("evidence artifact_id does not match locator artifact")
