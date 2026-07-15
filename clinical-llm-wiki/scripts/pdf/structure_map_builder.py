"""Build a deterministic full-document navigation map for one source package.

P2-B maps the whole PDF and companion workbook without extracting knowledge
statements. PDF outline destinations define the navigation spine, page table
geometry adds table boundaries, and non-empty workbook data rows provide the
Dataset -> Variable index. The large map is rebuildable local state under
``derived/``; only its compact count/hash report is intended for Git.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Callable, Iterable

import fitz

from scripts.pdf.source_pipeline import sha256_file
from scripts.pdf.structure_map_contract import (
    PDF_MEDIA_TYPE,
    XLSX_MEDIA_TYPE,
    canonical_structure_map_bytes,
    stable_locator_id,
    stable_page_id,
    stable_structure_map_id,
    stable_unit_id,
    structure_map_sha256,
    validate_structure_map,
)


BUILDER_VERSION = "1.0.0"
TABLE_MARKER = re.compile(
    r"^(?:"
    r"[A-Z][A-Z0-9]{1,7}\s+(?:[–-]\s+)?Specification(?:\s+-\s+Segment\s+\d+)?"
    r"|[a-z][a-z0-9]{1,7}\.xpt(?:\s*,.*)?"
    r"|Table\s+\d.*"
    r")$",
    re.IGNORECASE,
)
PRINTED_PAGE = re.compile(r"(?:^|\s)Page\s+(\d+)(?:\s|$)")
DOMAIN_SUFFIX = re.compile(r"\(([A-Z][A-Z0-9]{1,7})\)\s*$")


class StructureMapBuildError(RuntimeError):
    """Raised when source-package inputs cannot produce a closed map."""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise StructureMapBuildError(f"required input is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_text(value: str) -> str:
    return " ".join(value.split())


def _text_sha256(value: str) -> str:
    return hashlib.sha256(_normalized_text(value).encode("utf-8")).hexdigest()


def _row_sha256(row: list[Any]) -> str:
    payload = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _slug(value: str, *, fallback: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    normalized = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return normalized or fallback


def _identity_namespace(source_id: str) -> str:
    parts = source_id.removeprefix("src-").split("-")
    if "sdtmig" in parts:
        index = parts.index("sdtmig")
        version = "".join(part for part in parts[index + 1 :] if part.isdigit())
        return f"sdtmig{version}" if version else "sdtmig"
    return re.sub(r"[^a-z0-9]", "", source_id.removeprefix("src-").lower())


def _nonempty_row(row: list[Any]) -> bool:
    return any(value is not None and str(value).strip() for value in row)


def _row_mapping(headers: list[Any], row: list[Any]) -> dict[str, Any]:
    return {
        str(header).strip(): row[index] if index < len(row) else None
        for index, header in enumerate(headers)
        if header is not None and str(header).strip()
    }


def _artifact_records(source: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for artifact in source.get("artifacts", []):
        records.append(
            {
                "artifact_id": artifact["artifact_id"],
                "role": artifact["role"],
                "media_type": artifact["media_type"],
                "artifact_sha256": artifact["original_sha256"],
            }
        )
    if not records:
        records.append(
            {
                "artifact_id": source.get(
                    "primary_artifact_id",
                    f"artifact-{source['source_id'].removeprefix('src-')}-pdf",
                ),
                "role": "primary_citation",
                "media_type": PDF_MEDIA_TYPE,
                "artifact_sha256": source["original_sha256"],
            }
        )
    return sorted(records, key=lambda item: item["artifact_id"])


def _source_artifact(
    source: dict[str, Any], *, role: str | None = None, media_type: str | None = None
) -> dict[str, Any]:
    matches = [
        artifact
        for artifact in source.get("artifacts", [])
        if (role is None or artifact["role"] == role)
        and (media_type is None or artifact["media_type"] == media_type)
    ]
    if len(matches) != 1:
        raise StructureMapBuildError(
            f"expected one artifact for role={role!r}, media_type={media_type!r}; "
            f"found {len(matches)}"
        )
    return matches[0]


def _verify_inputs(
    package: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
    source = _read_json(package / "source-manifest.json")
    primary = _source_artifact(source, role="primary_citation")
    companion = _source_artifact(source, media_type=XLSX_MEDIA_TYPE)
    pdf_path = package / primary["original_relative_path"]
    xlsx_path = package / companion["original_relative_path"]
    if not pdf_path.is_file() or sha256_file(pdf_path) != primary["original_sha256"]:
        raise StructureMapBuildError("primary PDF is missing or differs from its manifest")
    if not xlsx_path.is_file() or sha256_file(xlsx_path) != companion["original_sha256"]:
        raise StructureMapBuildError("companion XLSX is missing or differs from its manifest")

    extraction = _read_json(package / "derived" / "extraction.json")
    workbook = _read_json(
        package / "derived" / "xlsx" / f"{companion['artifact_id']}.json"
    )
    if extraction.get("source_id") != source["source_id"] or extraction.get(
        "source_sha256"
    ) != primary["original_sha256"]:
        raise StructureMapBuildError("PDF derivative does not match the source manifest")
    if workbook.get("source_id") != source["source_id"] or workbook.get(
        "artifact_sha256"
    ) != companion["original_sha256"]:
        raise StructureMapBuildError("XLSX derivative does not match the source manifest")
    if len(extraction.get("pages", [])) != source["page_count"]:
        raise StructureMapBuildError("PDF derivative page count differs from the manifest")
    return source, extraction, workbook, pdf_path


def _unit(
    namespace: str,
    *,
    identity_key: str,
    artifact_id: str,
    parent_unit_id: str | None,
    unit_type: str,
    content_role: str,
    title: str | None,
    source_kind: str,
    outline_level: int | None,
    source_order: int,
    locator_ids: list[str],
    text_sha256: str,
    processing_status: str,
    processing_note: str | None = None,
) -> dict[str, Any]:
    return {
        "unit_id": stable_unit_id(namespace, identity_key),
        "identity_key": identity_key,
        "artifact_id": artifact_id,
        "parent_unit_id": parent_unit_id,
        "unit_type": unit_type,
        "content_role": content_role,
        "title": title,
        "source_kind": source_kind,
        "outline_level": outline_level,
        "source_order": source_order,
        "locator_ids": locator_ids,
        "text_sha256": text_sha256,
        "processing_status": processing_status,
        "processing_note": processing_note,
    }


def _pdf_locator(
    namespace: str,
    *,
    identity_key: str,
    artifact_id: str,
    physical_page: int,
    printed_page: str | None,
    section_path: list[str],
    bbox: Iterable[float],
    table_id: str | None = None,
) -> dict[str, Any]:
    return {
        "locator_id": stable_locator_id(namespace, identity_key),
        "identity_key": identity_key,
        "artifact_id": artifact_id,
        "locator_type": "pdf_region",
        "physical_page": physical_page,
        "printed_page": printed_page,
        "section_path": section_path,
        "bbox": [round(float(value), 3) for value in bbox],
        "sheet_name": None,
        "row_number": None,
        "table_id": table_id,
        "row_key": None,
    }


def _xlsx_locator(
    namespace: str,
    *,
    identity_key: str,
    artifact_id: str,
    sheet_name: str,
    row_number: int,
    row_key: str,
    section_path: list[str],
) -> dict[str, Any]:
    return {
        "locator_id": stable_locator_id(namespace, identity_key),
        "identity_key": identity_key,
        "artifact_id": artifact_id,
        "locator_type": "xlsx_row",
        "physical_page": None,
        "printed_page": None,
        "section_path": section_path,
        "bbox": None,
        "sheet_name": sheet_name,
        "row_number": row_number,
        "table_id": None,
        "row_key": row_key,
    }


def _sheet_by_name(workbook: dict[str, Any], name: str) -> dict[str, Any]:
    match = next(
        (sheet for sheet in workbook["sheets"] if sheet["name"].casefold() == name.casefold()),
        None,
    )
    if match is None:
        raise StructureMapBuildError(f"required workbook sheet is missing: {name}")
    return match


def _build_xlsx_index(
    source: dict[str, Any],
    workbook: dict[str, Any],
    namespace: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str], dict[str, int]]:
    artifact = _source_artifact(source, media_type=XLSX_MEDIA_TYPE)
    artifact_id = artifact["artifact_id"]
    units: list[dict[str, Any]] = []
    locators: list[dict[str, Any]] = []
    source_order = 0
    sheet_units: dict[str, str] = {}

    for sheet in workbook["sheets"]:
        rows = sheet.get("rows", [])
        if not rows:
            continue
        sheet_slug = _slug(sheet["name"], fallback=f"sheet-{source_order + 1}")
        identity_key = f"xlsx-sheet-{sheet_slug}"
        locator_key = f"xlsx-{sheet_slug}-header"
        locator = _xlsx_locator(
            namespace,
            identity_key=locator_key,
            artifact_id=artifact_id,
            sheet_name=sheet["name"],
            row_number=1,
            row_key="header",
            section_path=[sheet["name"]],
        )
        unit = _unit(
            namespace,
            identity_key=identity_key,
            artifact_id=artifact_id,
            parent_unit_id=None,
            unit_type="index",
            content_role="navigation",
            title=sheet["name"],
            source_kind="xlsx_sheet",
            outline_level=None,
            source_order=source_order,
            locator_ids=[locator["locator_id"]],
            text_sha256=_row_sha256(rows[0]),
            processing_status="navigation",
        )
        units.append(unit)
        locators.append(locator)
        sheet_units[sheet["name"].casefold()] = unit["unit_id"]
        source_order += 1

    datasets = _sheet_by_name(workbook, "Datasets")
    dataset_rows = datasets["rows"]
    if not dataset_rows:
        raise StructureMapBuildError("Datasets sheet has no header row")
    dataset_headers = dataset_rows[0]
    dataset_units: dict[str, str] = {}
    dataset_codes: set[str] = set()
    skipped_dataset_rows = 0
    for row_number, row in enumerate(dataset_rows[1:], start=2):
        if not _nonempty_row(row):
            skipped_dataset_rows += 1
            continue
        values = _row_mapping(dataset_headers, row)
        code = str(values.get("Dataset Name") or "").strip().upper()
        if not code:
            skipped_dataset_rows += 1
            continue
        identity_key = f"xlsx-dataset-{_slug(code, fallback=f'r{row_number:04d}')}"
        if code in dataset_units:
            identity_key = f"{identity_key}-r{row_number:04d}"
        locator_key = f"xlsx-datasets-r{row_number:04d}-{_slug(code, fallback='dataset')}"
        label = str(values.get("Dataset Label") or values.get("Description") or "").strip()
        title = f"{code} — {label}" if label else code
        locator = _xlsx_locator(
            namespace,
            identity_key=locator_key,
            artifact_id=artifact_id,
            sheet_name=datasets["name"],
            row_number=row_number,
            row_key=f"dataset|{code}",
            section_path=[datasets["name"], code],
        )
        unit = _unit(
            namespace,
            identity_key=identity_key,
            artifact_id=artifact_id,
            parent_unit_id=sheet_units[datasets["name"].casefold()],
            unit_type="dataset",
            content_role="metadata",
            title=title,
            source_kind="xlsx_row",
            outline_level=None,
            source_order=source_order,
            locator_ids=[locator["locator_id"]],
            text_sha256=_row_sha256(row),
            processing_status="candidate",
        )
        units.append(unit)
        locators.append(locator)
        dataset_units[code] = unit["unit_id"]
        dataset_codes.add(code)
        source_order += 1

    variables = _sheet_by_name(workbook, "Variables")
    variable_rows = variables["rows"]
    if not variable_rows:
        raise StructureMapBuildError("Variables sheet has no header row")
    variable_headers = variable_rows[0]
    variable_count = 0
    skipped_variable_rows = 0
    seen_variables: set[tuple[str, str]] = set()
    for row_number, row in enumerate(variable_rows[1:], start=2):
        if not _nonempty_row(row):
            skipped_variable_rows += 1
            continue
        values = _row_mapping(variable_headers, row)
        code = str(values.get("Dataset Name") or "").strip().upper()
        variable = str(values.get("Variable Name") or "").strip().upper()
        if not code or not variable:
            skipped_variable_rows += 1
            continue
        key = (code, variable)
        identity_key = (
            f"xlsx-variable-{_slug(code, fallback='dataset')}-"
            f"{_slug(variable, fallback=f'r{row_number:04d}')}"
        )
        if key in seen_variables:
            identity_key = f"{identity_key}-r{row_number:04d}"
        seen_variables.add(key)
        locator_key = (
            f"xlsx-variables-r{row_number:04d}-"
            f"{_slug(code, fallback='dataset')}-{_slug(variable, fallback='variable')}"
        )
        label = str(values.get("Variable Label") or "").strip()
        title = f"{code}.{variable} — {label}" if label else f"{code}.{variable}"
        locator = _xlsx_locator(
            namespace,
            identity_key=locator_key,
            artifact_id=artifact_id,
            sheet_name=variables["name"],
            row_number=row_number,
            row_key=f"variable|{code}|{variable}",
            section_path=[variables["name"], code, variable],
        )
        unit = _unit(
            namespace,
            identity_key=identity_key,
            artifact_id=artifact_id,
            parent_unit_id=dataset_units.get(
                code, sheet_units[variables["name"].casefold()]
            ),
            unit_type="variable_row",
            content_role="metadata",
            title=title,
            source_kind="xlsx_row",
            outline_level=None,
            source_order=source_order,
            locator_ids=[locator["locator_id"]],
            text_sha256=_row_sha256(row),
            processing_status="candidate",
        )
        units.append(unit)
        locators.append(locator)
        variable_count += 1
        source_order += 1

    counts = {
        "sheet_units": len(sheet_units),
        "dataset_rows": len(dataset_units),
        "variable_rows": variable_count,
        "skipped_dataset_rows": skipped_dataset_rows,
        "skipped_variable_rows": skipped_variable_rows,
    }
    return units, locators, dataset_codes, counts


def _outline_unit_type(
    title: str, level: int, dataset_codes: set[str]
) -> str:
    match = DOMAIN_SUFFIX.search(title)
    if match and match.group(1) in dataset_codes:
        return "domain"
    if "SUPPQUAL" in dataset_codes and re.search(
        r"Supplemental Qualifiers\s*\(SUPP--\)", title, re.IGNORECASE
    ):
        return "domain"
    if title.casefold() == "contents" or "implementation guide" in title.casefold():
        return "front_matter"
    if title.startswith("Appendix ") or title.startswith("10 Appendices"):
        return "appendix"
    return "chapter" if level == 1 else "section"


def _point_bbox(page: dict[str, Any], x: float, y: float) -> list[float]:
    width = float(page["width_points"])
    height = float(page["height_points"])
    x0 = max(0.0, min(width - 1.0, x if x >= 0 else 0.0))
    y0 = max(0.0, min(height - 1.0, y if y >= 0 else 0.0))
    return [round(x0, 3), round(y0, 3), round(width, 3), round(min(height, y0 + 24.0), 3)]


def _printed_page(page: dict[str, Any]) -> str | None:
    match = PRINTED_PAGE.search(page["text"])
    return match.group(1) if match else page.get("printed_page")


def _page_role(physical_page: int, first_body: int, first_appendix: int | None) -> str:
    if physical_page == 1:
        return "cover"
    if physical_page < first_body:
        return "contents"
    if first_appendix is not None and physical_page >= first_appendix:
        return "appendix"
    return "body"


def _build_pdf_outline(
    document: fitz.Document,
    source: dict[str, Any],
    extraction: dict[str, Any],
    namespace: str,
    dataset_codes: set[str],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, list[str]],
    dict[str, int],
]:
    artifact = _source_artifact(source, role="primary_citation")
    artifact_id = artifact["artifact_id"]
    outline = document.get_toc(simple=False)
    if not outline:
        raise StructureMapBuildError("primary PDF has no outline navigation")
    units: list[dict[str, Any]] = []
    locators: list[dict[str, Any]] = []
    path_by_unit: dict[str, list[str]] = {}
    starts_by_page: dict[int, list[tuple[float, str]]] = defaultdict(list)
    stack: list[tuple[int, str, list[str]]] = []
    source_order = 0

    first_outline_page = min(entry[2] for entry in outline)
    if first_outline_page > 1:
        page = extraction["pages"][0]
        identity_key = "pdf-front-matter"
        locator_key = "pdf-front-matter-p0001"
        locator = _pdf_locator(
            namespace,
            identity_key=locator_key,
            artifact_id=artifact_id,
            physical_page=1,
            printed_page=_printed_page(page),
            section_path=["Front matter"],
            bbox=[0.0, 0.0, page["width_points"], page["height_points"]],
        )
        unit = _unit(
            namespace,
            identity_key=identity_key,
            artifact_id=artifact_id,
            parent_unit_id=None,
            unit_type="front_matter",
            content_role="navigation",
            title="Front matter",
            source_kind="pdf_detected",
            outline_level=None,
            source_order=source_order,
            locator_ids=[locator["locator_id"]],
            text_sha256=_text_sha256(page["text"]),
            processing_status="navigation",
        )
        units.append(unit)
        locators.append(locator)
        path_by_unit[unit["unit_id"]] = ["Front matter"]
        starts_by_page[1].append((0.0, unit["unit_id"]))
        source_order += 1

    domain_units = 0
    appendix_pages: list[int] = []
    body_pages: list[int] = []
    for index, entry in enumerate(outline, start=1):
        level, title, physical_page, detail = entry
        if not 1 <= physical_page <= document.page_count:
            raise StructureMapBuildError(
                f"outline entry {index} targets invalid page {physical_page}"
            )
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent_unit_id = stack[-1][1] if stack else None
        parent_path = stack[-1][2] if stack else []
        section_path = [*parent_path, title]
        point = detail.get("to") if isinstance(detail, dict) else None
        x = float(getattr(point, "x", 0.0))
        y = float(getattr(point, "y", 0.0))
        page = extraction["pages"][physical_page - 1]
        slug = _slug(title, fallback=f"entry-{index:04d}")[:64]
        identity_key = f"pdf-outline-{index:04d}-{slug}"
        locator_key = f"pdf-outline-{index:04d}-p{physical_page:04d}"
        locator = _pdf_locator(
            namespace,
            identity_key=locator_key,
            artifact_id=artifact_id,
            physical_page=physical_page,
            printed_page=_printed_page(page),
            section_path=section_path,
            bbox=_point_bbox(page, x, y),
        )
        unit_type = _outline_unit_type(title, level, dataset_codes)
        if unit_type == "domain":
            domain_units += 1
        if unit_type == "appendix":
            appendix_pages.append(physical_page)
        if level == 1 and re.match(r"^1\s+", title):
            body_pages.append(physical_page)
        unit = _unit(
            namespace,
            identity_key=identity_key,
            artifact_id=artifact_id,
            parent_unit_id=parent_unit_id,
            unit_type=unit_type,
            content_role="navigation",
            title=title,
            source_kind="pdf_outline",
            outline_level=level,
            source_order=source_order,
            locator_ids=[locator["locator_id"]],
            text_sha256=_text_sha256(title),
            processing_status="navigation",
        )
        units.append(unit)
        locators.append(locator)
        path_by_unit[unit["unit_id"]] = section_path
        starts_by_page[physical_page].append((y, unit["unit_id"]))
        stack.append((level, unit["unit_id"], section_path))
        source_order += 1

    pages: list[dict[str, Any]] = []
    active_unit_id: str | None = None
    first_body = min(body_pages) if body_pages else first_outline_page
    first_appendix = min(appendix_pages) if appendix_pages else None
    for page in extraction["pages"]:
        physical_page = page["physical_page"]
        starts = sorted(starts_by_page.get(physical_page, []), key=lambda item: item[0])
        page_primary = active_unit_id
        if starts:
            first_y, first_unit_id = starts[0]
            if page_primary is None or first_y <= 144.0:
                page_primary = first_unit_id
            active_unit_id = starts[-1][1]
        if page_primary is None:
            raise StructureMapBuildError(
                f"physical page {physical_page} has no outline or front-matter assignment"
            )
        pages.append(
            {
                "page_id": stable_page_id(namespace, physical_page),
                "artifact_id": artifact_id,
                "physical_page": physical_page,
                "printed_page": _printed_page(page),
                "width_points": page["width_points"],
                "height_points": page["height_points"],
                "page_role": _page_role(physical_page, first_body, first_appendix),
                "primary_unit_id": page_primary,
                "text_sha256": _text_sha256(page["text"]),
                "processing_status": "navigation",
                "processing_note": None,
            }
        )

    counts = {
        "outline_entries": len(outline),
        "domain_units": domain_units,
        "front_matter_fallback_units": int(first_outline_page > 1),
    }
    return units, locators, pages, path_by_unit, counts


def _page_lines(page: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for word in page["words"]:
        groups[(word["block"], word["line"])].append(word)
    lines = []
    for words in groups.values():
        ordered = sorted(words, key=lambda item: (item["bbox"][0], item["word"]))
        bbox = [
            min(word["bbox"][0] for word in ordered),
            min(word["bbox"][1] for word in ordered),
            max(word["bbox"][2] for word in ordered),
            max(word["bbox"][3] for word in ordered),
        ]
        lines.append({"text": " ".join(word["text"] for word in ordered), "bbox": bbox})
    return sorted(lines, key=lambda item: (item["bbox"][1], item["bbox"][0]))


def _bbox_overlaps_or_follows(marker: list[float], table: list[float]) -> bool:
    horizontal_overlap = min(marker[2], table[2]) > max(marker[0], table[0])
    vertical_gap = table[1] - marker[3]
    return horizontal_overlap and -10.0 <= vertical_gap <= 180.0


def _table_text(page: fitz.Page, bbox: list[float]) -> str:
    words = [
        word[4]
        for word in page.get_text("words", sort=True)
        if word[0] >= bbox[0] - 1
        and word[1] >= bbox[1] - 1
        and word[2] <= bbox[2] + 1
        and word[3] <= bbox[3] + 1
    ]
    return " ".join(words)


def _build_pdf_tables(
    document: fitz.Document,
    source: dict[str, Any],
    extraction: dict[str, Any],
    namespace: str,
    pages: list[dict[str, Any]],
    path_by_unit: dict[str, list[str]],
    source_order_start: int,
    progress: Callable[[str], None] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    artifact_id = _source_artifact(source, role="primary_citation")["artifact_id"]
    units: list[dict[str, Any]] = []
    locators: list[dict[str, Any]] = []
    source_order = source_order_start
    geometry_count = 0
    marker_fallback_count = 0

    for page_index, page_record in enumerate(extraction["pages"], start=1):
        if progress and (page_index == 1 or page_index % 25 == 0 or page_index == document.page_count):
            progress(f"table scan {page_index}/{document.page_count}")
        pdf_page = document[page_index - 1]
        lines = _page_lines(page_record)
        markers = [line for line in lines if TABLE_MARKER.search(line["text"])]
        detected: list[dict[str, Any]] = []
        for table in pdf_page.find_tables().tables:
            bbox = [round(float(value), 3) for value in table.bbox]
            if table.row_count < 2 or table.col_count < 2:
                continue
            if bbox[2] - bbox[0] < 40 or bbox[3] - bbox[1] < 16:
                continue
            related = [
                marker for marker in markers if _bbox_overlaps_or_follows(marker["bbox"], bbox)
            ]
            title = related[0]["text"] if related else (
                f"PDF table p{page_index:04d} ({table.row_count}x{table.col_count})"
            )
            detected.append({"bbox": bbox, "title": title, "covered": related})

        parent_unit_id = pages[page_index - 1]["primary_unit_id"]
        parent_path = path_by_unit[parent_unit_id]
        covered_marker_ids = {id(marker) for item in detected for marker in item["covered"]}
        table_items = [
            ("geometry", index, item["bbox"], item["title"])
            for index, item in enumerate(detected, start=1)
        ]
        fallback_markers = [marker for marker in markers if id(marker) not in covered_marker_ids]
        table_items.extend(
            ("marker", index, marker["bbox"], marker["text"])
            for index, marker in enumerate(fallback_markers, start=1)
        )
        table_items.sort(key=lambda item: (item[2][1], item[2][0], item[0]))

        geometry_index = 0
        marker_index = 0
        for kind, _, bbox, title in table_items:
            if kind == "geometry":
                geometry_index += 1
                geometry_count += 1
                identity_key = f"pdf-table-p{page_index:04d}-g{geometry_index:02d}"
            else:
                marker_index += 1
                marker_fallback_count += 1
                identity_key = f"pdf-table-p{page_index:04d}-m{marker_index:02d}"
            locator_key = f"{identity_key}-boundary"
            unit_id = stable_unit_id(namespace, identity_key)
            locator = _pdf_locator(
                namespace,
                identity_key=locator_key,
                artifact_id=artifact_id,
                physical_page=page_index,
                printed_page=pages[page_index - 1]["printed_page"],
                section_path=[*parent_path, title],
                bbox=bbox,
                table_id=unit_id,
            )
            content_role = "metadata" if "specification" in title.casefold() else "other"
            unit = _unit(
                namespace,
                identity_key=identity_key,
                artifact_id=artifact_id,
                parent_unit_id=parent_unit_id,
                unit_type="table",
                content_role=content_role,
                title=title,
                source_kind="pdf_detected",
                outline_level=None,
                source_order=source_order,
                locator_ids=[locator["locator_id"]],
                text_sha256=_text_sha256(_table_text(pdf_page, bbox)),
                processing_status="context",
            )
            units.append(unit)
            locators.append(locator)
            path_by_unit[unit_id] = [*parent_path, title]
            source_order += 1

    return units, locators, {
        "geometry_table_boundaries": geometry_count,
        "marker_fallback_boundaries": marker_fallback_count,
        "table_boundaries": geometry_count + marker_fallback_count,
    }


def build_structure_map(
    package_dir: str | Path,
    *,
    progress: Callable[[str], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build and validate the deterministic P2-B structure map and summary."""

    package = Path(package_dir).resolve()
    source, extraction, workbook, pdf_path = _verify_inputs(package)
    namespace = _identity_namespace(source["source_id"])
    xlsx_units, xlsx_locators, dataset_codes, xlsx_counts = _build_xlsx_index(
        source, workbook, namespace
    )

    document = fitz.open(pdf_path)
    try:
        if document.page_count != source["page_count"]:
            raise StructureMapBuildError("PDF page count differs from the source manifest")
        pdf_units, pdf_locators, pages, path_by_unit, pdf_counts = _build_pdf_outline(
            document, source, extraction, namespace, dataset_codes
        )
        table_units, table_locators, table_counts = _build_pdf_tables(
            document,
            source,
            extraction,
            namespace,
            pages,
            path_by_unit,
            len(pdf_units),
            progress,
        )
    finally:
        document.close()

    payload = {
        "schema_version": "1.0.0",
        "structure_map_id": stable_structure_map_id(namespace),
        "source_id": source["source_id"],
        "source_sha256": source["original_sha256"],
        "identity_profile": {
            "profile_id": "source-anchor-v1",
            "namespace": namespace,
            "normalization_profile": "text-collapse-v1",
        },
        "artifacts": _artifact_records(source),
        "page_count": source["page_count"],
        "pages": pages,
        "units": [*pdf_units, *table_units, *xlsx_units],
        "locators": [*pdf_locators, *table_locators, *xlsx_locators],
        "references": [],
    }
    validate_structure_map(payload)

    unit_counts = Counter(unit["unit_type"] for unit in payload["units"])
    status_counts = Counter(unit["processing_status"] for unit in payload["units"])
    report = {
        "schema_version": "1.0.0",
        "builder_version": BUILDER_VERSION,
        "source_id": source["source_id"],
        "source_sha256": source["original_sha256"],
        "structure_map_id": payload["structure_map_id"],
        "structure_map_sha256": structure_map_sha256(payload),
        "coverage": {
            "physical_pages_expected": source["page_count"],
            "physical_pages_mapped": len(pages),
            "unexplained_pages": sum(
                page["primary_unit_id"] is None for page in pages
            ),
            **pdf_counts,
            **table_counts,
            **xlsx_counts,
        },
        "unit_counts": dict(sorted(unit_counts.items())),
        "processing_status_counts": dict(sorted(status_counts.items())),
        "locator_count": len(payload["locators"]),
        "reference_count": len(payload["references"]),
    }
    return payload, report


def write_structure_outputs(
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
    parser.add_argument(
        "--map-path",
        type=Path,
        help="Defaults to PACKAGE/derived/structure-map.json",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        help="Defaults to PACKAGE/structure-map-summary.json",
    )
    args = parser.parse_args()
    package = args.package_dir.resolve()
    payload, report = build_structure_map(package, progress=print)
    write_structure_outputs(
        payload,
        report,
        map_path=args.map_path or package / "derived" / "structure-map.json",
        report_path=args.report_path or package / "structure-map-summary.json",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
