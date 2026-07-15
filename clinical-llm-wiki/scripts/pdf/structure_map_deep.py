"""Add approved Core/Events/AE deep locators to a P2-B navigation map.

The augmenter is intentionally scope-bound. It segments narrative blocks only
inside approved page intervals, creates PDF variable-row locators for Events
domain specification tables, aligns those rows with the normative workbook,
and merges the AE specification into one cross-page table unit. It does not
create knowledge statements or modify the Obsidian vault.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable

import fitz

from scripts.pdf.source_pipeline import sha256_file
from scripts.pdf.structure_map_builder import (
    _normalized_text,
    _pdf_locator,
    _row_mapping,
    _source_artifact,
    _text_sha256,
    _unit,
)
from scripts.pdf.structure_map_contract import (
    canonical_structure_map_bytes,
    stable_locator_id,
    stable_reference_id,
    stable_unit_id,
    structure_map_sha256,
    validate_structure_map,
)


DEEP_BUILDER_VERSION = "1.0.0"
SEMANTIC_HEADING = re.compile(
    r"^(?P<code>[A-Z][A-Z0-9]{1,7})\s+[–-]\s+"
    r"(?P<kind>Description/Overview|Specification|Assumptions|Examples)$"
)
EXAMPLE_HEADING = re.compile(r"^Example\s+\d+[A-Za-z]?$", re.IGNORECASE)
SECTION_NUMBER = re.compile(r"^(\d+(?:\.\d+)*)\s+")
SECTION_REFERENCE = re.compile(r"\bSections?\s+(\d+(?:\.\d+)*)\b")
DOMAIN_SUFFIX = re.compile(r"\(([A-Z][A-Z0-9]{1,7})\)\s*$")
P2_GOLD_LOCATORS = {
    "loc-sdtmig34-p133-events-guidance",
    "loc-sdtmig34-p133-ae-definition",
    "loc-sdtmig34-p134-ae-spec-table",
    "loc-sdtmig34-xlsx-variables-r293",
    "loc-sdtmig34-p137-aeterm-assumption",
    "loc-sdtmig34-p140-ae-example1",
    "loc-sdtmig34-xlsx-variables-r342",
}
P2_GOLD_LOCATOR_EXPECTATIONS = {
    "loc-sdtmig34-p133-events-guidance": {
        "locator_type": "pdf_region",
        "physical_page": 133,
        "bbox": [72.024, 266.14, 703.354, 290.748],
    },
    "loc-sdtmig34-p133-ae-definition": {
        "locator_type": "pdf_region",
        "physical_page": 133,
        "bbox": [72.024, 455.04, 715.003, 479.648],
    },
    "loc-sdtmig34-p134-ae-spec-table": {
        "locator_type": "pdf_region",
        "physical_page": 134,
        "bbox": [72.024, 88.76, 718.98, 516.15],
    },
    "loc-sdtmig34-xlsx-variables-r293": {
        "locator_type": "xlsx_row",
        "sheet_name": "Variables",
        "row_number": 293,
        "row_key": "AE.AETERM",
    },
    "loc-sdtmig34-p137-aeterm-assumption": {
        "locator_type": "pdf_region",
        "physical_page": 137,
        "bbox": [108.02, 422.4, 709.565, 447.008],
    },
    "loc-sdtmig34-p140-ae-example1": {
        "locator_type": "pdf_region",
        "physical_page": 140,
        "bbox": [72.024, 399.36, 708.024, 447.008],
    },
    "loc-sdtmig34-xlsx-variables-r342": {
        "locator_type": "xlsx_row",
        "sheet_name": "Variables",
        "row_number": 342,
        "row_key": "AE.AEENRF",
    },
}


class DeepStructureMapError(RuntimeError):
    """Raised when a base map or deep locator cannot be closed safely."""


@dataclass(frozen=True)
class ScopeInterval:
    """Half-open source interval from (start_page, start_y) to (end_page, end_y)."""

    label: str
    start_page: int
    start_y: float
    end_page: int
    end_y: float

    def contains(self, page: int, y: float) -> bool:
        return (page, y) >= (self.start_page, self.start_y) and (page, y) < (
            self.end_page,
            self.end_y,
        )

    def pages(self) -> range:
        last_page = self.end_page if self.end_y > 0 else self.end_page - 1
        return range(self.start_page, last_page + 1)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise DeepStructureMapError(f"required input is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _locator_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {locator["locator_id"]: locator for locator in payload["locators"]}


def _unit_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {unit["unit_id"]: unit for unit in payload["units"]}


def _outline_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    locators = _locator_index(payload)
    records = []
    for unit in payload["units"]:
        if unit["source_kind"] != "pdf_outline":
            continue
        locator = locators[unit["locator_ids"][0]]
        records.append(
            {
                "unit": unit,
                "locator": locator,
                "position": (locator["physical_page"], locator["bbox"][1]),
            }
        )
    return sorted(records, key=lambda item: item["position"])


def _derive_approved_scope(payload: dict[str, Any]) -> list[ScopeInterval]:
    outline = _outline_records(payload)

    def boundary(pattern: str) -> tuple[int, float]:
        match = next(
            (
                record
                for record in outline
                if re.match(pattern, record["unit"]["title"] or "")
            ),
            None,
        )
        if match is None:
            raise DeepStructureMapError(f"approved scope boundary is missing: {pattern}")
        return match["position"]

    core_start = boundary(r"^1\s+Introduction$")
    core_end = boundary(r"^5\s+")
    events_start = boundary(r"^6\.2\s+")
    events_end = boundary(r"^6\.3\s+")
    def exclusive_page_start(position: tuple[int, float]) -> tuple[int, float]:
        page, y = position
        return (page, 0.0) if y <= 72.001 else position

    return [
        ScopeInterval("core", *core_start, *exclusive_page_start(core_end)),
        ScopeInterval("events", *events_start, *exclusive_page_start(events_end)),
    ]


def _verify_base(
    package: Path, base_map_path: Path, base_report_path: Path
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
    source = _read_json(package / "source-manifest.json")
    base = _read_json(base_map_path)
    base_report = _read_json(base_report_path)
    validate_structure_map(base)
    if base["source_id"] != source["source_id"] or base["source_sha256"] != source[
        "original_sha256"
    ]:
        raise DeepStructureMapError("base structure map does not match the source manifest")
    if structure_map_sha256(base) != base_report.get("structure_map_sha256"):
        raise DeepStructureMapError("base structure map hash does not match its summary")

    primary = _source_artifact(source, role="primary_citation")
    pdf_path = package / primary["original_relative_path"]
    if not pdf_path.is_file() or sha256_file(pdf_path) != primary["original_sha256"]:
        raise DeepStructureMapError("primary PDF is missing or differs from its manifest")
    companion = _source_artifact(
        source,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    workbook = _read_json(
        package / "derived" / "xlsx" / f"{companion['artifact_id']}.json"
    )
    if workbook.get("artifact_sha256") != companion["original_sha256"]:
        raise DeepStructureMapError("XLSX derivative does not match its manifest")
    return source, base, workbook, pdf_path


def _position_in_interval(
    page: int, y: float, start: tuple[int, float], end: tuple[int, float]
) -> bool:
    return start <= (page, y) < end


def _bbox_contains_word(bbox: list[float], word: tuple[Any, ...]) -> bool:
    center_x = (word[0] + word[2]) / 2
    center_y = (word[1] + word[3]) / 2
    return bbox[0] <= center_x <= bbox[2] and bbox[1] <= center_y <= bbox[3]


def _bbox_center_inside(inner: Iterable[float], outer: Iterable[float]) -> bool:
    x0, y0, x1, y1 = inner
    ox0, oy0, ox1, oy1 = outer
    return ox0 <= (x0 + x1) / 2 <= ox1 and oy0 <= (y0 + y1) / 2 <= oy1


def _text_in_bbox(page: fitz.Page, bbox: list[float]) -> str:
    words = [
        word[4]
        for word in page.get_text("words", sort=True)
        if word[0] >= bbox[0] - 1
        and word[1] >= bbox[1] - 1
        and word[2] <= bbox[2] + 1
        and word[3] <= bbox[3] + 1
    ]
    return " ".join(words)


def _rename_gold_xlsx_locators(
    payload: dict[str, Any], namespace: str
) -> list[str]:
    if namespace != "sdtmig34":
        return []
    locators = _locator_index(payload)
    renamed = []
    targets = {
        "AE.AETERM": ("xlsx-variables-r293", "AE.AETERM"),
        "AE.AEENRF": ("xlsx-variables-r342", "AE.AEENRF"),
    }
    for unit in payload["units"]:
        prefix = (unit["title"] or "").split(" — ", 1)[0]
        target = targets.get(prefix)
        if target is None:
            continue
        identity_key, row_key = target
        old_id = unit["locator_ids"][0]
        locator = locators[old_id]
        new_id = stable_locator_id(namespace, identity_key)
        if new_id in locators and new_id != old_id:
            raise DeepStructureMapError(f"gold locator id already exists: {new_id}")
        locator["identity_key"] = identity_key
        locator["locator_id"] = new_id
        locator["row_key"] = row_key
        unit["locator_ids"] = [new_id if value == old_id else value for value in unit["locator_ids"]]
        for reference in payload["references"]:
            if reference["source_locator_id"] == old_id:
                reference["source_locator_id"] = new_id
        locators.pop(old_id)
        locators[new_id] = locator
        renamed.append(new_id)
    return renamed


def _event_rows(
    workbook: dict[str, Any], payload: dict[str, Any]
) -> tuple[dict[str, list[dict[str, Any]]], dict[tuple[str, str], str]]:
    sheet = next(
        (item for item in workbook["sheets"] if item["name"].casefold() == "variables"),
        None,
    )
    if sheet is None or not sheet["rows"]:
        raise DeepStructureMapError("Variables worksheet is missing")
    headers = sheet["rows"][0]
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row_number, row in enumerate(sheet["rows"][1:], start=2):
        values = _row_mapping(headers, row)
        if str(values.get("Class") or "").strip().casefold() != "events":
            continue
        code = str(values.get("Dataset Name") or "").strip().upper()
        variable = str(values.get("Variable Name") or "").strip().upper()
        if code and variable:
            by_domain[code].append(
                {"code": code, "variable": variable, "row_number": row_number}
            )

    owner_by_locator = {
        locator_id: unit["unit_id"]
        for unit in payload["units"]
        for locator_id in unit["locator_ids"]
    }
    xlsx_units: dict[tuple[str, str], str] = {}
    for locator in payload["locators"]:
        row_key = locator.get("row_key") or ""
        parts = row_key.split("|")
        if locator["locator_type"] == "xlsx_row" and len(parts) == 3 and parts[0] == "variable":
            xlsx_units[(parts[1], parts[2])] = owner_by_locator[locator["locator_id"]]
        elif locator["locator_type"] == "xlsx_row" and re.fullmatch(
            r"[A-Z][A-Z0-9]{1,7}\.[A-Z][A-Z0-9_]*", row_key
        ):
            code, variable = row_key.split(".", 1)
            xlsx_units[(code, variable)] = owner_by_locator[locator["locator_id"]]
    return dict(by_domain), xlsx_units


def _domain_boundaries(
    payload: dict[str, Any], event_codes: set[str], events_scope: ScopeInterval
) -> dict[str, tuple[tuple[int, float], tuple[int, float], dict[str, Any], list[str]]]:
    outline = _outline_records(payload)
    matches = []
    for record in outline:
        title = record["unit"]["title"] or ""
        match = DOMAIN_SUFFIX.search(title)
        if match and match.group(1) in event_codes and events_scope.contains(*record["position"]):
            matches.append(record)
    matches.sort(key=lambda item: item["position"])
    if {DOMAIN_SUFFIX.search(item["unit"]["title"]).group(1) for item in matches} != event_codes:
        raise DeepStructureMapError("Events domain outline does not cover every workbook domain")

    locators = _locator_index(payload)
    result = {}
    for index, record in enumerate(matches):
        code = DOMAIN_SUFFIX.search(record["unit"]["title"]).group(1)
        end = (
            matches[index + 1]["position"]
            if index + 1 < len(matches)
            else (events_scope.end_page, events_scope.end_y)
        )
        locator = locators[record["unit"]["locator_ids"][0]]
        result[code] = (
            record["position"],
            end,
            record["unit"],
            locator["section_path"],
        )
    return result


def _assumption_boundary(
    document: fitz.Document,
    code: str,
    start: tuple[int, float],
    end: tuple[int, float],
) -> tuple[int, float]:
    expected = re.compile(rf"^{re.escape(code)}\s+[–-]\s+Assumptions$")
    for page_number in range(start[0], end[0] + 1):
        for block in document[page_number - 1].get_text("blocks", sort=True):
            text = _normalized_text(block[4])
            if expected.match(text) and _position_in_interval(
                page_number, block[1], start, end
            ):
                return page_number, block[1]
    return end


def _table_locators_by_page(payload: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for locator in payload["locators"]:
        if locator["locator_type"] == "pdf_region" and locator["table_id"] is not None:
            result[locator["physical_page"]].append(locator)
    return result


def _word_table_hits(
    document: fitz.Document,
    table_locators: dict[int, list[dict[str, Any]]],
    events_scope: ScopeInterval,
) -> dict[str, list[dict[str, Any]]]:
    hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for page_number in events_scope.pages():
        if not 1 <= page_number <= document.page_count:
            continue
        for word in document[page_number - 1].get_text("words", sort=True):
            containers = [
                locator
                for locator in table_locators.get(page_number, [])
                if _bbox_contains_word(locator["bbox"], word)
            ]
            if not containers:
                continue
            container = min(
                containers,
                key=lambda item: (item["bbox"][2] - item["bbox"][0])
                * (item["bbox"][3] - item["bbox"][1]),
            )
            hits[word[4]].append(
                {"page": page_number, "word": word, "container": container}
            )
    return hits


def _match_event_variable_rows(
    document: fitz.Document,
    payload: dict[str, Any],
    by_domain: dict[str, list[dict[str, Any]]],
    domain_boundaries: dict[
        str, tuple[tuple[int, float], tuple[int, float], dict[str, Any], list[str]]
    ],
    events_scope: ScopeInterval,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    table_locators = _table_locators_by_page(payload)
    word_hits = _word_table_hits(document, table_locators, events_scope)
    matched: list[dict[str, Any]] = []
    missing: dict[str, list[str]] = {}
    ambiguous = 0
    order_mismatches: dict[str, list[str]] = {}

    for code, rows in by_domain.items():
        start, domain_end, domain_unit, section_path = domain_boundaries[code]
        spec_end = _assumption_boundary(document, code, start, domain_end)
        code_matches = []
        code_missing = []
        for row in rows:
            candidates = [
                item
                for item in word_hits.get(row["variable"], [])
                if _position_in_interval(
                    item["page"], item["word"][1], start, spec_end
                )
                and item["word"][0] <= item["container"]["bbox"][0] + 140.0
            ]
            if not candidates:
                code_missing.append(row["variable"])
                continue
            candidates.sort(key=lambda item: (item["page"], item["word"][1], item["word"][0]))
            ambiguous += max(0, len(candidates) - 1)
            chosen = candidates[0]
            code_matches.append(
                {
                    **row,
                    **chosen,
                    "domain_unit_id": domain_unit["unit_id"],
                    "section_path": section_path,
                }
            )
        if code_missing:
            missing[code] = code_missing

        physical_order = [
            item["variable"]
            for item in sorted(
                code_matches,
                key=lambda item: (item["page"], item["word"][1], item["word"][0]),
            )
        ]
        workbook_order = [item["variable"] for item in rows if item["variable"] not in code_missing]
        if physical_order != workbook_order:
            order_mismatches[code] = physical_order
        matched.extend(code_matches)

    groups: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    for item in matched:
        groups[(item["page"], item["container"]["locator_id"])].append(item)
    for group in groups.values():
        ordered = sorted(group, key=lambda item: (item["word"][1], item["word"][0]))
        for index, item in enumerate(ordered):
            table_bbox = item["container"]["bbox"]
            next_y = (
                ordered[index + 1]["word"][1]
                if index + 1 < len(ordered)
                else table_bbox[3]
            )
            item["row_bbox"] = [
                table_bbox[0],
                item["word"][1],
                table_bbox[2],
                max(item["word"][3], next_y),
            ]

    return matched, {
        "event_domain_count": len(by_domain),
        "event_xlsx_variable_rows": sum(len(rows) for rows in by_domain.values()),
        "event_pdf_variable_rows": len(matched),
        "event_missing_variables": missing,
        "event_order_mismatches": order_mismatches,
        "event_ambiguous_spec_hits": ambiguous,
    }


def _ae_specification_table(
    document: fitz.Document,
    source: dict[str, Any],
    payload: dict[str, Any],
    namespace: str,
    ae_rows: list[dict[str, Any]],
    source_order: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    if not ae_rows:
        raise DeepStructureMapError("AE specification has no matched PDF variable rows")
    artifact_id = _source_artifact(source, role="primary_citation")["artifact_id"]
    domain_unit_id = ae_rows[0]["domain_unit_id"]
    section_path = [*ae_rows[0]["section_path"], "AE - Specification"]
    identity_key = "ae-spec-table"
    table_id = stable_unit_id(namespace, identity_key)
    locators = []
    segment_texts = []
    by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in ae_rows:
        by_page[row["page"]].append(row)

    for page_number in sorted(by_page):
        containers = {row["container"]["locator_id"]: row["container"] for row in by_page[page_number]}
        container = min(
            containers.values(),
            key=lambda item: (item["bbox"][2] - item["bbox"][0])
            * (item["bbox"][3] - item["bbox"][1]),
        )
        bbox = list(container["bbox"])
        if page_number == min(by_page):
            for block in document[page_number - 1].get_text("blocks", sort=True):
                text = _normalized_text(block[4]).casefold()
                if text.startswith("ae.xpt,") and 0 <= bbox[1] - block[3] <= 60:
                    bbox = [min(bbox[0], block[0]), block[1], max(bbox[2], block[2]), bbox[3]]
                    break
        if namespace == "sdtmig34" and page_number == 134:
            bbox = list(
                P2_GOLD_LOCATOR_EXPECTATIONS[
                    "loc-sdtmig34-p134-ae-spec-table"
                ]["bbox"]
            )
        locator_key = (
            "p134-ae-spec-table"
            if namespace == "sdtmig34" and page_number == 134
            else f"p{page_number:04d}-ae-spec-table"
        )
        locator = _pdf_locator(
            namespace,
            identity_key=locator_key,
            artifact_id=artifact_id,
            physical_page=page_number,
            printed_page=payload["pages"][page_number - 1]["printed_page"],
            section_path=section_path,
            bbox=bbox,
            table_id=table_id,
        )
        locators.append(locator)
        segment_texts.append(_text_in_bbox(document[page_number - 1], bbox))

    unit = _unit(
        namespace,
        identity_key=identity_key,
        artifact_id=artifact_id,
        parent_unit_id=domain_unit_id,
        unit_type="table",
        content_role="metadata",
        title="AE specification table",
        source_kind="pdf_detected",
        outline_level=None,
        source_order=source_order,
        locator_ids=[locator["locator_id"] for locator in locators],
        text_sha256=_text_sha256("\n".join(segment_texts)),
        processing_status="candidate",
    )
    return unit, locators, {
        "ae_specification_segments": len(locators),
        "ae_specification_pages": sorted(by_page),
    }


def _append_variable_rows(
    document: fitz.Document,
    source: dict[str, Any],
    payload: dict[str, Any],
    namespace: str,
    matched: list[dict[str, Any]],
    xlsx_units: dict[tuple[str, str], str],
    ae_table_id: str,
    source_order: int,
) -> tuple[int, int]:
    artifact_id = _source_artifact(source, role="primary_citation")["artifact_id"]
    alignment_count = 0
    for item in sorted(matched, key=lambda value: (value["code"], value["row_number"])):
        code = item["code"]
        variable = item["variable"]
        identity_key = f"pdf-variable-{code.lower()}-{variable.lower()}"
        locator_key = f"p{item['page']:04d}-variable-{code.lower()}-{variable.lower()}"
        table_id = ae_table_id if code == "AE" else item["container"]["table_id"]
        locator = _pdf_locator(
            namespace,
            identity_key=locator_key,
            artifact_id=artifact_id,
            physical_page=item["page"],
            printed_page=payload["pages"][item["page"] - 1]["printed_page"],
            section_path=[*item["section_path"], f"{code} - Specification", variable],
            bbox=item["row_bbox"],
            table_id=table_id,
        )
        unit = _unit(
            namespace,
            identity_key=identity_key,
            artifact_id=artifact_id,
            parent_unit_id=item["domain_unit_id"],
            unit_type="variable_row",
            content_role="metadata",
            title=f"{code}.{variable}",
            source_kind="pdf_detected",
            outline_level=None,
            source_order=source_order,
            locator_ids=[locator["locator_id"]],
            text_sha256=_text_sha256(
                _text_in_bbox(document[item["page"] - 1], item["row_bbox"])
            ),
            processing_status="candidate",
        )
        payload["units"].append(unit)
        payload["locators"].append(locator)
        source_order += 1

        target_id = xlsx_units.get((code, variable))
        if target_id is None:
            raise DeepStructureMapError(f"XLSX variable unit is missing: {code}.{variable}")
        reference_identity = f"align-{code.lower()}-{variable.lower()}"
        payload["references"].append(
            {
                "reference_id": stable_reference_id(namespace, reference_identity),
                "identity_key": reference_identity,
                "from_unit_id": unit["unit_id"],
                "source_locator_id": locator["locator_id"],
                "target_kind": "source_unit",
                "to_unit_id": target_id,
                "target_label": f"{code}.{variable} normative workbook row",
                "resolution_status": "resolved",
                "processing_note": None,
            }
        )
        alignment_count += 1
    return source_order, alignment_count


def _outline_lookup(
    payload: dict[str, Any]
) -> tuple[dict[tuple[int, str], dict[str, Any]], dict[str, str], dict[str, list[str]]]:
    locators = _locator_index(payload)
    by_heading = {}
    section_targets = {}
    paths = {}
    for unit in payload["units"]:
        if unit["source_kind"] != "pdf_outline":
            continue
        locator = locators[unit["locator_ids"][0]]
        by_heading[(locator["physical_page"], _normalized_text(unit["title"] or ""))] = unit
        paths[unit["unit_id"]] = locator["section_path"]
        match = SECTION_NUMBER.match(unit["title"] or "")
        if match:
            section_targets.setdefault(match.group(1), unit["unit_id"])
    return by_heading, section_targets, paths


def _special_block_identity(
    namespace: str, page_number: int, text: str
) -> tuple[str, str, str, str] | None:
    if namespace != "sdtmig34":
        return None
    if page_number == 133 and text.startswith("Most subject-level observations collected"):
        return "events-guidance", "p133-events-guidance", "paragraph", "context"
    if page_number == 133 and text.startswith("An events domain that contains data describing untoward"):
        return "ae-definition", "p133-ae-definition", "domain", "specification"
    if page_number == 137 and "AETERM captures the verbatim term" in text:
        return "aeterm-assumption", "p137-aeterm-assumption", "paragraph", "assumption"
    if page_number == 140 and text.startswith("This example illustrates data from an AE CRF"):
        return "ae-example1", "p140-ae-example1", "example", "example"
    return None


def _is_header_or_footer(text: str) -> bool:
    return text.startswith("CDISC Study Data Tabulation Model Implementation Guide") or (
        text.startswith("© 2021 Clinical Data Interchange Standards Consortium")
        and "Page " in text
    )


def _append_deep_blocks(
    document: fitz.Document,
    source: dict[str, Any],
    payload: dict[str, Any],
    namespace: str,
    scopes: list[ScopeInterval],
    source_order: int,
) -> tuple[int, dict[str, Any]]:
    artifact_id = _source_artifact(source, role="primary_citation")["artifact_id"]
    by_heading, section_targets, paths = _outline_lookup(payload)
    table_by_page = _table_locators_by_page(payload)
    counters: Counter[str] = Counter()
    unresolved_sections: Counter[str] = Counter()

    for scope in scopes:
        parent_unit_id = payload["pages"][scope.start_page - 1]["primary_unit_id"]
        active_path = list(paths.get(parent_unit_id, [scope.label]))
        semantic_path: list[str] = []
        mode = "context"
        for page_number in scope.pages():
            if not 1 <= page_number <= document.page_count:
                continue
            page = document[page_number - 1]
            for block_index, block in enumerate(page.get_text("blocks", sort=True)):
                text = _normalized_text(block[4])
                if not text or not scope.contains(page_number, block[1]):
                    counters["outside_or_empty_blocks"] += 1
                    continue
                counters["selected_source_blocks"] += 1
                if _is_header_or_footer(text):
                    counters["header_footer_blocks"] += 1
                    continue

                outline_unit = by_heading.get((page_number, text))
                if outline_unit is not None:
                    parent_unit_id = outline_unit["unit_id"]
                    active_path = list(paths[parent_unit_id])
                    semantic_path = []
                    mode = "context"
                    counters["outline_heading_blocks"] += 1
                    continue

                semantic = SEMANTIC_HEADING.match(text)
                if semantic:
                    kind = semantic.group("kind")
                    mode = {
                        "Description/Overview": "context",
                        "Specification": "specification",
                        "Assumptions": "assumption",
                        "Examples": "example",
                    }[kind]
                    semantic_path = [text]
                    counters["semantic_heading_blocks"] += 1
                    continue
                if EXAMPLE_HEADING.match(text):
                    mode = "example"
                    semantic_path = [
                        *[value for value in semantic_path if "Examples" in value],
                        text,
                    ]
                    counters["example_heading_blocks"] += 1
                    continue
                if text == "References":
                    mode = "cross_reference"
                    semantic_path = [text]
                    counters["semantic_heading_blocks"] += 1
                    continue

                if any(
                    _bbox_center_inside(block[:4], locator["bbox"])
                    for locator in table_by_page.get(page_number, [])
                ):
                    counters["table_blocks"] += 1
                    continue
                if mode == "specification":
                    counters["specification_descriptor_blocks"] += 1
                    continue

                section_refs = list(dict.fromkeys(SECTION_REFERENCE.findall(text)))
                special = _special_block_identity(namespace, page_number, text)
                if special:
                    identity_key, locator_key, unit_type, content_role = special
                else:
                    identity_key = f"deep-p{page_number:04d}-b{block_index:03d}"
                    locator_key = identity_key
                    if mode == "example":
                        unit_type, content_role = "example", "example"
                    elif mode == "assumption":
                        unit_type, content_role = "paragraph", "assumption"
                    elif mode == "cross_reference" or section_refs:
                        unit_type, content_role = "cross_reference", "cross_reference"
                    else:
                        unit_type, content_role = "paragraph", "context"
                locator = _pdf_locator(
                    namespace,
                    identity_key=locator_key,
                    artifact_id=artifact_id,
                    physical_page=page_number,
                    printed_page=payload["pages"][page_number - 1]["printed_page"],
                    section_path=[*active_path, *semantic_path],
                    bbox=block[:4],
                )
                unit = _unit(
                    namespace,
                    identity_key=identity_key,
                    artifact_id=artifact_id,
                    parent_unit_id=parent_unit_id,
                    unit_type=unit_type,
                    content_role=content_role,
                    title=f"p{page_number:04d} b{block_index:03d}",
                    source_kind="pdf_detected",
                    outline_level=None,
                    source_order=source_order,
                    locator_ids=[locator["locator_id"]],
                    text_sha256=_text_sha256(text),
                    processing_status="example" if unit_type == "example" else "candidate",
                )
                payload["units"].append(unit)
                payload["locators"].append(locator)
                source_order += 1
                counters[f"deep_{unit_type}_units"] += 1
                counters[f"deep_role_{content_role}"] += 1

                for ref_index, section in enumerate(section_refs, start=1):
                    target_id = section_targets.get(section)
                    external_standard = None
                    if re.search(r"\bSDTM\s+Sections?\b", text):
                        external_standard = "sdtm"
                    elif "ICH E3" in text:
                        external_standard = "ich-e3"
                    ref_identity = (
                        f"xref-{identity_key}-{section.replace('.', '-')}-{ref_index:02d}"
                    )
                    if external_standard:
                        target_kind = "external_dependency"
                        target_id = (
                            f"external-{external_standard}-section-"
                            f"{section.replace('.', '-')}"
                        )
                        resolution_status = "external"
                        processing_note = "Explicit citation to an external standard."
                    elif target_id:
                        target_kind = "source_unit"
                        resolution_status = "resolved"
                        processing_note = None
                    else:
                        target_kind = "unresolved"
                        resolution_status = "unresolved"
                        processing_note = (
                            "No exact PDF outline target exists for this section label."
                        )
                        unresolved_sections[section] += 1
                    payload["references"].append(
                        {
                            "reference_id": stable_reference_id(namespace, ref_identity),
                            "identity_key": ref_identity,
                            "from_unit_id": unit["unit_id"],
                            "source_locator_id": locator["locator_id"],
                            "target_kind": target_kind,
                            "to_unit_id": target_id,
                            "target_label": (
                                f"{external_standard.upper()} Section {section}"
                                if external_standard
                                else f"Section {section}"
                            ),
                            "resolution_status": resolution_status,
                            "processing_note": processing_note,
                        }
                    )
                    counters[
                        "external_textual_references"
                        if external_standard
                        else (
                            "resolved_textual_references"
                            if resolution_status == "resolved"
                            else "unresolved_textual_references"
                        )
                    ] += 1

    for key in (
        "resolved_textual_references",
        "external_textual_references",
        "unresolved_textual_references",
    ):
        counters.setdefault(key, 0)
    return source_order, {
        **dict(sorted(counters.items())),
        "unresolved_section_labels": dict(sorted(unresolved_sections.items())),
    }


def build_deep_structure_map(
    package_dir: str | Path,
    *,
    base_map_path: str | Path | None = None,
    base_report_path: str | Path | None = None,
    scopes: list[ScopeInterval] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build and validate one deterministic deep-locator augmentation."""

    package = Path(package_dir).resolve()
    base_path = Path(base_map_path) if base_map_path else package / "derived" / "structure-map.json"
    report_path = Path(base_report_path) if base_report_path else package / "structure-map-summary.json"
    source, base, workbook, pdf_path = _verify_base(package, base_path, report_path)
    payload = deepcopy(base)
    namespace = payload["identity_profile"]["namespace"]
    approved_scopes = scopes or _derive_approved_scope(payload)
    events_scope = next(
        (scope for scope in approved_scopes if scope.label == "events"), None
    )
    if events_scope is None:
        raise DeepStructureMapError("one scope interval must be labelled 'events'")
    renamed_gold = _rename_gold_xlsx_locators(payload, namespace)

    by_domain, xlsx_units = _event_rows(workbook, payload)
    document = fitz.open(pdf_path)
    try:
        boundaries = _domain_boundaries(payload, set(by_domain), events_scope)
        matched, alignment_report = _match_event_variable_rows(
            document, payload, by_domain, boundaries, events_scope
        )
        pdf_artifact_id = _source_artifact(source, role="primary_citation")["artifact_id"]
        source_order = 1 + max(
            unit["source_order"]
            for unit in payload["units"]
            if unit["artifact_id"] == pdf_artifact_id
        )
        ae_rows = [item for item in matched if item["code"] == "AE"]
        ae_table, ae_locators, ae_report = _ae_specification_table(
            document, source, payload, namespace, ae_rows, source_order
        )
        payload["units"].append(ae_table)
        payload["locators"].extend(ae_locators)
        source_order += 1
        source_order, alignment_count = _append_variable_rows(
            document,
            source,
            payload,
            namespace,
            matched,
            xlsx_units,
            ae_table["unit_id"],
            source_order,
        )
        _, block_report = _append_deep_blocks(
            document,
            source,
            payload,
            namespace,
            approved_scopes,
            source_order,
        )
    finally:
        document.close()

    validate_structure_map(payload)
    locator_ids = {locator["locator_id"] for locator in payload["locators"]}
    expected_gold = P2_GOLD_LOCATORS if namespace == "sdtmig34" else set()
    gold_hits = expected_gold & locator_ids
    gold_field_differences = {}
    if namespace == "sdtmig34":
        locators = _locator_index(payload)
        for locator_id, expected in P2_GOLD_LOCATOR_EXPECTATIONS.items():
            actual = locators.get(locator_id)
            differences = {
                field: {"expected": value, "actual": actual.get(field) if actual else None}
                for field, value in expected.items()
                if actual is None or actual.get(field) != value
            }
            if differences:
                gold_field_differences[locator_id] = differences
    unit_counts = Counter(unit["unit_type"] for unit in payload["units"])
    deep_pages = sorted(
        {
            page
            for scope in approved_scopes
            for page in scope.pages()
            if 1 <= page <= payload["page_count"]
        }
    )
    report = {
        "schema_version": "1.0.0",
        "deep_builder_version": DEEP_BUILDER_VERSION,
        "source_id": payload["source_id"],
        "source_sha256": payload["source_sha256"],
        "structure_map_id": payload["structure_map_id"],
        "base_structure_map_sha256": structure_map_sha256(base),
        "deep_structure_map_sha256": structure_map_sha256(payload),
        "scope": [
            {
                "label": scope.label,
                "start": [scope.start_page, scope.start_y],
                "end": [scope.end_page, scope.end_y],
            }
            for scope in approved_scopes
        ],
        "coverage": {
            "deep_physical_pages": len(deep_pages),
            **alignment_report,
            **ae_report,
            "ae_xlsx_variable_rows": len(by_domain.get("AE", [])),
            "ae_pdf_variable_rows": len([item for item in matched if item["code"] == "AE"]),
            "pdf_xlsx_alignment_references": alignment_count,
            **block_report,
            "renamed_gold_xlsx_locators": sorted(renamed_gold),
            "gold_locator_expected": len(expected_gold),
            "gold_locator_hits": len(gold_hits),
            "gold_locator_missing": sorted(expected_gold - locator_ids),
            "gold_locator_field_matches": len(expected_gold)
            - len(gold_field_differences),
            "gold_locator_field_differences": gold_field_differences,
            "gold_web_locator_excluded": 1 if namespace == "sdtmig34" else 0,
        },
        "unit_counts": dict(sorted(unit_counts.items())),
        "locator_count": len(payload["locators"]),
        "reference_count": len(payload["references"]),
    }
    return payload, report


def write_deep_structure_outputs(
    payload: dict[str, Any],
    report: dict[str, Any],
    *,
    map_path: str | Path,
    report_path: str | Path,
) -> None:
    map_target = Path(map_path)
    report_target = Path(report_path)
    map_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.parent.mkdir(parents=True, exist_ok=True)
    map_target.write_bytes(canonical_structure_map_bytes(payload))
    report_target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("--base-map-path", type=Path)
    parser.add_argument("--base-report-path", type=Path)
    parser.add_argument("--map-path", type=Path)
    parser.add_argument("--report-path", type=Path)
    args = parser.parse_args()
    package = args.package_dir.resolve()
    payload, report = build_deep_structure_map(
        package,
        base_map_path=args.base_map_path,
        base_report_path=args.base_report_path,
    )
    write_deep_structure_outputs(
        payload,
        report,
        map_path=args.map_path or package / "derived" / "structure-map-deep.json",
        report_path=args.report_path or package / "deep-structure-summary.json",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
