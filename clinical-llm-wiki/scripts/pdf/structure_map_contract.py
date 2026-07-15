"""Validation and canonical identity helpers for source structure maps.

The structure map is a Wiki-internal, rebuildable navigation artifact. It is
deliberately separate from the P1 knowledge-extraction ``SourceUnit`` model:
pages, PDF outline nodes, cross-page tables, and workbook rows exist before a
knowledge statement is proposed. Evidence-bearing locators retain the P1
field shape so P3 can project selected regions without inventing a second
locator vocabulary.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = ROOT / "schemas" / "extraction" / "source-structure-map.schema.json"
PDF_MEDIA_TYPE = "application/pdf"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
P1_LOCATOR_FIELDS = (
    "locator_id",
    "artifact_id",
    "locator_type",
    "physical_page",
    "printed_page",
    "section_path",
    "bbox",
    "sheet_name",
    "row_number",
    "table_id",
    "row_key",
)
_IDENTITY_KEY = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_NAMESPACE = re.compile(r"^[a-z][a-z0-9]*$")


class StructureMapContractError(ValueError):
    """Raised when a structure map is not deterministic or referentially closed."""


def stable_structure_map_id(namespace: str) -> str:
    return f"structure-map-{_validated_namespace(namespace)}"


def stable_page_id(namespace: str, physical_page: int) -> str:
    if physical_page < 1:
        raise ValueError("physical_page must be positive")
    return f"page-{_validated_namespace(namespace)}-p{physical_page:04d}"


def stable_unit_id(namespace: str, identity_key: str) -> str:
    return _stable_anchored_id("unit", namespace, identity_key)


def stable_locator_id(namespace: str, identity_key: str) -> str:
    return _stable_anchored_id("loc", namespace, identity_key)


def stable_reference_id(namespace: str, identity_key: str) -> str:
    return _stable_anchored_id("ref", namespace, identity_key)


def _stable_anchored_id(prefix: str, namespace: str, identity_key: str) -> str:
    if not _IDENTITY_KEY.fullmatch(identity_key):
        raise ValueError(f"identity_key is not canonical: {identity_key}")
    return f"{prefix}-{_validated_namespace(namespace)}-{identity_key}"


def _validated_namespace(namespace: str) -> str:
    if not _NAMESPACE.fullmatch(namespace):
        raise ValueError(f"identity namespace is not canonical: {namespace}")
    return namespace


def canonical_structure_map_bytes(payload: dict[str, Any]) -> bytes:
    """Return canonical JSON bytes; timestamps are forbidden by the Schema."""

    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def structure_map_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_structure_map_bytes(payload)).hexdigest()


def project_locator_to_p1(locator: dict[str, Any]) -> dict[str, Any]:
    """Drop P2 identity metadata while preserving the approved P1 locator shape."""

    missing = [field for field in P1_LOCATOR_FIELDS if field not in locator]
    if missing:
        raise StructureMapContractError(
            f"locator cannot project to P1; missing fields: {', '.join(missing)}"
        )
    return {field: locator[field] for field in P1_LOCATOR_FIELDS}


def validate_structure_map(
    payload: dict[str, Any], *, schema_path: str | Path = DEFAULT_SCHEMA
) -> None:
    """Validate Schema shape, stable identities, coverage, and reference closure."""

    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda item: list(item.path),
    )
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.path) or "<root>"
        raise StructureMapContractError(
            f"schema validation failed at {location}: {first.message}"
        )

    namespace = payload["identity_profile"]["namespace"]
    if payload["structure_map_id"] != stable_structure_map_id(namespace):
        raise StructureMapContractError("structure_map_id does not match identity profile")

    artifacts = _unique_index(payload["artifacts"], "artifact_id", "artifact")
    pages = _unique_index(payload["pages"], "page_id", "page")
    units = _unique_index(payload["units"], "unit_id", "unit")
    locators = _unique_index(payload["locators"], "locator_id", "locator")
    references = _unique_index(payload["references"], "reference_id", "reference")

    primary = [item for item in artifacts.values() if item["role"] == "primary_citation"]
    if len(primary) != 1:
        raise StructureMapContractError("exactly one primary_citation artifact is required")
    primary_artifact = primary[0]
    if primary_artifact["media_type"] != PDF_MEDIA_TYPE:
        raise StructureMapContractError("primary_citation artifact must be a PDF")
    if primary_artifact["artifact_sha256"] != payload["source_sha256"]:
        raise StructureMapContractError(
            "source_sha256 must match the primary citation artifact"
        )

    _validate_pages(payload, namespace, artifacts, pages, units, primary_artifact)
    _validate_units(namespace, artifacts, units, locators)
    _validate_locators(namespace, artifacts, pages, units, locators)
    _validate_references(namespace, units, locators, references)


def _unique_index(
    records: list[dict[str, Any]], key: str, label: str
) -> dict[str, dict[str, Any]]:
    indexed = {record[key]: record for record in records}
    if len(indexed) != len(records):
        raise StructureMapContractError(f"duplicate {label} id")
    return indexed


def _validate_pages(
    payload: dict[str, Any],
    namespace: str,
    artifacts: dict[str, dict[str, Any]],
    pages: dict[str, dict[str, Any]],
    units: dict[str, dict[str, Any]],
    primary_artifact: dict[str, Any],
) -> None:
    if payload["page_count"] != len(pages):
        raise StructureMapContractError("page_count does not match page assignments")
    physical_pages = [page["physical_page"] for page in payload["pages"]]
    expected_pages = list(range(1, payload["page_count"] + 1))
    if physical_pages != expected_pages:
        raise StructureMapContractError(
            "page assignments must be unique, contiguous, and in physical order"
        )

    for page in pages.values():
        if page["page_id"] != stable_page_id(namespace, page["physical_page"]):
            raise StructureMapContractError(
                f"page id is not stable for physical page {page['physical_page']}"
            )
        artifact = artifacts.get(page["artifact_id"])
        if artifact is None:
            raise StructureMapContractError(
                f"page {page['page_id']} references missing artifact"
            )
        if artifact["artifact_id"] != primary_artifact["artifact_id"]:
            raise StructureMapContractError("page assignments must use the primary PDF")
        primary_unit_id = page["primary_unit_id"]
        if primary_unit_id is None:
            if page["page_role"] != "blank" and page["processing_status"] != "deferred":
                raise StructureMapContractError(
                    f"page {page['page_id']} lacks a primary unit without explanation"
                )
        else:
            unit = units.get(primary_unit_id)
            if unit is None:
                raise StructureMapContractError(
                    f"page {page['page_id']} references missing primary unit"
                )
            if unit["artifact_id"] != page["artifact_id"]:
                raise StructureMapContractError(
                    f"page {page['page_id']} and primary unit use different artifacts"
                )


def _validate_units(
    namespace: str,
    artifacts: dict[str, dict[str, Any]],
    units: dict[str, dict[str, Any]],
    locators: dict[str, dict[str, Any]],
) -> None:
    source_orders: set[tuple[str, int]] = set()
    locator_owners: dict[str, str] = {}
    for unit in units.values():
        expected_id = stable_unit_id(namespace, unit["identity_key"])
        if unit["unit_id"] != expected_id:
            raise StructureMapContractError(f"unit id is not stable: {unit['unit_id']}")
        if unit["artifact_id"] not in artifacts:
            raise StructureMapContractError(
                f"unit {unit['unit_id']} references missing artifact"
            )
        order_key = (unit["artifact_id"], unit["source_order"])
        if order_key in source_orders:
            raise StructureMapContractError("duplicate source_order within artifact")
        source_orders.add(order_key)

        parent_id = unit["parent_unit_id"]
        if parent_id is not None:
            parent = units.get(parent_id)
            if parent is None:
                raise StructureMapContractError(
                    f"unit {unit['unit_id']} has dangling parent {parent_id}"
                )
            if parent["artifact_id"] != unit["artifact_id"]:
                raise StructureMapContractError("unit parent cannot cross artifacts")

        for locator_id in unit["locator_ids"]:
            locator = locators.get(locator_id)
            if locator is None:
                raise StructureMapContractError(
                    f"unit {unit['unit_id']} references missing locator {locator_id}"
                )
            if locator["artifact_id"] != unit["artifact_id"]:
                raise StructureMapContractError("unit and locator use different artifacts")
            if locator_id in locator_owners:
                raise StructureMapContractError(
                    f"locator {locator_id} belongs to multiple structure units"
                )
            locator_owners[locator_id] = unit["unit_id"]

    for unit_id in units:
        visited: set[str] = set()
        cursor: str | None = unit_id
        while cursor is not None:
            if cursor in visited:
                raise StructureMapContractError(f"unit parent cycle detected at {unit_id}")
            visited.add(cursor)
            cursor = units[cursor]["parent_unit_id"]


def _validate_locators(
    namespace: str,
    artifacts: dict[str, dict[str, Any]],
    pages: dict[str, dict[str, Any]],
    units: dict[str, dict[str, Any]],
    locators: dict[str, dict[str, Any]],
) -> None:
    pages_by_number = {page["physical_page"]: page for page in pages.values()}
    for locator in locators.values():
        expected_id = stable_locator_id(namespace, locator["identity_key"])
        if locator["locator_id"] != expected_id:
            raise StructureMapContractError(
                f"locator id is not stable: {locator['locator_id']}"
            )
        artifact = artifacts.get(locator["artifact_id"])
        if artifact is None:
            raise StructureMapContractError(
                f"locator {locator['locator_id']} references missing artifact"
            )
        if locator["locator_type"] == "pdf_region":
            if artifact["media_type"] != PDF_MEDIA_TYPE:
                raise StructureMapContractError("pdf locator must reference a PDF artifact")
            page = pages_by_number.get(locator["physical_page"])
            if page is None:
                raise StructureMapContractError("pdf locator page is outside page coverage")
            x0, y0, x1, y1 = locator["bbox"]
            if x0 >= x1 or y0 >= y1:
                raise StructureMapContractError("pdf locator bbox is reversed or empty")
            if x1 > page["width_points"] or y1 > page["height_points"]:
                raise StructureMapContractError("pdf locator bbox exceeds page bounds")
        elif artifact["media_type"] != XLSX_MEDIA_TYPE:
            raise StructureMapContractError("xlsx locator must reference an XLSX artifact")

        table_id = locator["table_id"]
        if table_id is not None:
            table = units.get(table_id)
            if table is None or table["unit_type"] != "table":
                raise StructureMapContractError(
                    f"locator {locator['locator_id']} has dangling table_id"
                )
            if table["artifact_id"] != locator["artifact_id"]:
                raise StructureMapContractError("locator table owner uses another artifact")

    for table in (unit for unit in units.values() if unit["unit_type"] == "table"):
        table_locators = [locators[locator_id] for locator_id in table["locator_ids"]]
        if any(locator["table_id"] != table["unit_id"] for locator in table_locators):
            raise StructureMapContractError(
                f"table locator does not point to its owner: {table['unit_id']}"
            )
        pdf_pages = [
            locator["physical_page"]
            for locator in table_locators
            if locator["locator_type"] == "pdf_region"
        ]
        if len(pdf_pages) > 1:
            expected = list(range(pdf_pages[0], pdf_pages[0] + len(pdf_pages)))
            if pdf_pages != expected:
                raise StructureMapContractError(
                    f"cross-page table segments are not contiguous: {table['unit_id']}"
                )


def _validate_references(
    namespace: str,
    units: dict[str, dict[str, Any]],
    locators: dict[str, dict[str, Any]],
    references: dict[str, dict[str, Any]],
) -> None:
    for reference in references.values():
        expected_id = stable_reference_id(namespace, reference["identity_key"])
        if reference["reference_id"] != expected_id:
            raise StructureMapContractError(
                f"reference id is not stable: {reference['reference_id']}"
            )
        source = units.get(reference["from_unit_id"])
        if source is None:
            raise StructureMapContractError("reference has dangling from_unit_id")
        locator_id = reference["source_locator_id"]
        if locator_id not in locators or locator_id not in source["locator_ids"]:
            raise StructureMapContractError(
                "reference source_locator_id is not owned by from_unit_id"
            )

        status = reference["resolution_status"]
        target_kind = reference["target_kind"]
        target_id = reference["to_unit_id"]
        if status == "resolved":
            if target_kind != "source_unit" or target_id not in units:
                raise StructureMapContractError("resolved reference has dangling target")
        elif status == "external":
            if target_kind != "external_dependency" or target_id is None:
                raise StructureMapContractError(
                    "external reference requires an external dependency id"
                )
        elif target_kind != "unresolved" or target_id is not None:
            raise StructureMapContractError(
                "unresolved reference must not claim a resolved target"
            )
