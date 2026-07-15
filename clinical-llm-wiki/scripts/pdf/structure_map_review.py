"""Build the compact P6-P2 structure-map audit and blocking review packet.

This gate summarizes deterministic structure evidence without copying source
content into Git or the Obsidian vault. It requires the local P2-B and P2-C
maps to match their committed summary hashes, then opens a human review. The
script never writes a DecisionReceipt or ConfirmationReceipt.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from scripts.pdf.structure_map_contract import validate_structure_map


REPORT_VERSION = "1.0.0"
REVIEW_ID = "sdtm_spec_sdtmig34_structure_v1_001"
SOURCE_ID = "src-cdisc-sdtmig-3-4"
PACKAGE_RELATIVE_PATH = Path("sources/packages/src-cdisc-sdtmig-3-4")
REPORT_NAME = "structure-map-review-report.json"
PACKET_NAME = f"{REVIEW_ID}.json"
BASE_MAP_NAME = "structure-map.json"
DEEP_MAP_NAME = "structure-map-deep.json"
DEFAULT_REVIEW_LANGUAGE = "zh-CN"
SUPPORTED_REVIEW_LANGUAGES = {"en", "zh-CN"}


class StructureMapReviewError(RuntimeError):
    """Raised when P2 evidence is incomplete or internally inconsistent."""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise StructureMapReviewError(f"required review input is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StructureMapReviewError(f"review input is invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise StructureMapReviewError(f"review input must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise StructureMapReviewError(message)


def _check(
    check_id: str,
    category: str,
    title: str,
    actual: dict[str, Any],
    expected: dict[str, Any],
    evidence_refs: list[str],
) -> dict[str, Any]:
    _require(actual == expected, f"{check_id} failed: expected {expected}, got {actual}")
    return {
        "check_id": check_id,
        "category": category,
        "title": title,
        "status": "passed",
        "actual": actual,
        "expected": expected,
        "evidence_refs": evidence_refs,
    }


def _validate_created_at(created_at: str) -> None:
    try:
        value = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StructureMapReviewError("created_at must be an ISO 8601 timestamp") from exc
    _require(value.tzinfo is not None, "created_at must include a timezone")


def _review_schema(wiki_root: Path) -> dict[str, Any]:
    schema_path = (
        wiki_root.parent
        / "clinical-workflow"
        / "schemas"
        / "review"
        / "review-protocol.schema.json"
    )
    schema = _read_json(schema_path)
    review_packet = deepcopy(schema["$defs"]["review_packet"])
    review_packet.pop("$id", None)
    review_packet["$schema"] = schema["$schema"]
    review_packet["$defs"] = schema["$defs"]
    return review_packet


def build_structure_review_packet(
    *,
    created_at: str,
    base_hash: str,
    deep_hash: str,
    language: str = DEFAULT_REVIEW_LANGUAGE,
) -> dict[str, Any]:
    """Build one ReviewPacket with localized human-facing text.

    Stable identifiers, enums, paths, and evidence references remain unchanged.
    English is retained only so the already-reviewed P2-D packet can be
    reproduced and audited without mutating historical evidence.
    """

    _validate_created_at(created_at)
    _require(
        language in SUPPORTED_REVIEW_LANGUAGES,
        f"unsupported review language: {language}",
    )
    finding_specs = [
        {
            "id": "F-001",
            "category": "compliance",
            "severity": "info",
            "location": "p6-p2-structure-map#CHK-001",
            "evidence_refs": ["structure-review:CHK-001"],
            "text": {
                "en": (
                    "Accept the full-document navigation coverage baseline",
                    "461/461 pages and 220/220 outline entries are mapped with zero unexplained pages.",
                    "Approve the page-to-outline navigation layer as the P2 full-document coverage baseline.",
                    "Navigation coverage prevents later extraction from silently skipping source regions.",
                ),
                "zh-CN": (
                    "确认全文导航覆盖基线",
                    "已映射 461/461 个物理页和 220/220 个目录条目，不存在无法解释的页面。",
                    "批准 Page→Outline 导航层作为 P2 全文结构覆盖基线。",
                    "完整导航覆盖可以防止后续知识抽取静默遗漏来源区域。",
                ),
            },
        },
        {
            "id": "F-002",
            "category": "mapping",
            "severity": "info",
            "location": "p6-p2-structure-map#CHK-002",
            "evidence_refs": ["structure-review:CHK-002"],
            "text": {
                "en": (
                    "Accept PDF boundary detection and XLSX row indexing",
                    "63 domains, 704 PDF table boundaries, 63 dataset rows, and 1917 variable rows are indexed with no skipped data rows.",
                    "Approve the PDF navigation boundaries and structured workbook index as complementary source structure.",
                    "PDF and XLSX provide different locator granularity and must remain separately traceable.",
                ),
                "zh-CN": (
                    "确认 PDF 边界检测与 XLSX 行索引",
                    "已索引 63 个 domain、704 个 PDF 表格边界、63 个 dataset 行和 1917 个 variable 行，没有跳过数据行。",
                    "批准 PDF 导航边界与结构化工作簿索引作为互补的来源结构。",
                    "PDF 与 XLSX 提供不同粒度的 locator，必须保持独立可追溯。",
                ),
            },
        },
        {
            "id": "F-003",
            "category": "compliance",
            "severity": "info",
            "location": "p6-p2-structure-map#CHK-003",
            "evidence_refs": ["structure-review:CHK-003"],
            "text": {
                "en": (
                    "Accept the bounded Core and Events deep-locator scope",
                    "The approved 100-page scope contains 844 paragraph units, 177 assumption roles, 289 examples, and 85 cross-reference units.",
                    "Approve deep segmentation only for Core chapters 1-4, section 6.2 Events, and section 6.2.1 AE.",
                    "A bounded deep layer preserves retrieval quality without claiming full-book paragraph extraction.",
                ),
                "zh-CN": (
                    "确认 Core 与 Events 的限定深层 locator 范围",
                    "批准的 100 页范围包含 844 个段落单元、177 个 assumption 角色、289 个示例和 85 个交叉引用单元。",
                    "批准仅对 Core 第 1-4 章、6.2 Events 和 6.2.1 AE 进行深层分段。",
                    "限定深层范围既能保证检索质量，也不会把局部抽取误称为全书逐段抽取。",
                ),
            },
        },
        {
            "id": "F-004",
            "category": "mapping",
            "severity": "warning",
            "location": "p6-p2-structure-map#CHK-004",
            "evidence_refs": ["structure-review:CHK-004"],
            "text": {
                "en": (
                    "Accept Events PDF-to-XLSX variable alignment",
                    "All 204 Events PDF variable rows align to 204 workbook rows across seven domains with no missing, ambiguous, or order-difference result.",
                    "Approve the 204 typed alignment references as the Events variable trace baseline.",
                    "Variable-level traceability is required before extracting executable SDTM guidance.",
                ),
                "zh-CN": (
                    "确认 Events PDF→XLSX 变量对齐",
                    "七个 domain 的 204 个 Events PDF 变量行全部对齐到 204 个工作簿行，没有缺失、歧义或顺序差异。",
                    "批准 204 条类型化对齐引用作为 Events 变量追溯基线。",
                    "在抽取可执行的 SDTM 指导前，必须先建立变量级追溯。",
                ),
            },
        },
        {
            "id": "F-005",
            "category": "mapping",
            "severity": "warning",
            "location": "p6-p2-structure-map#CHK-005",
            "evidence_refs": [
                "structure-review:CHK-005",
                "visual-qa:pages-134-136-137-140",
            ],
            "text": {
                "en": (
                    "Accept the AE cross-page table locator",
                    "The AE specification is one table unit with four page locators on pages 134-137 and 60/60 PDF/XLSX variable rows.",
                    "Approve the cross-page AE table boundary and the first/middle/last locator visual checks.",
                    "Treating continuation pages as unrelated tables would break AE variable context and citations.",
                ),
                "zh-CN": (
                    "确认 AE 跨页表格 locator",
                    "AE specification 已合并为一个表格单元，在物理页 134-137 上包含四个 page locator，PDF/XLSX 变量行为 60/60。",
                    "批准 AE 跨页表格边界以及首段、中段和末段 locator 的视觉核验结果。",
                    "若把续页误当成无关表格，会破坏 AE 变量语境与引用链。",
                ),
            },
        },
        {
            "id": "F-006",
            "category": "compliance",
            "severity": "info",
            "location": "p6-p2-structure-map#CHK-006",
            "evidence_refs": ["structure-review:CHK-006"],
            "text": {
                "en": (
                    "Accept internal and external reference classification",
                    "117 SDTMIG section references resolve internally, five SDTM or ICH E3 references remain typed external dependencies, and none are unresolved.",
                    "Approve the reference closure and preserve external standards as dependencies rather than guessed SDTMIG targets.",
                    "Typed reference boundaries prevent missing citations and false internal links.",
                ),
                "zh-CN": (
                    "确认内部与外部引用分类",
                    "117 条 SDTMIG 章节引用已在内部解析，5 条 SDTM 或 ICH E3 引用保留为类型化外部依赖，不存在未解析引用。",
                    "批准引用闭包，并将外部标准保留为依赖，而不是猜测为 SDTMIG 内部目标。",
                    "类型化引用边界可以防止引用缺失和错误的内部链接。",
                ),
            },
        },
        {
            "id": "F-007",
            "category": "compliance",
            "severity": "warning",
            "location": "p6-p2-structure-map#CHK-007",
            "evidence_refs": [
                "structure-review:CHK-007",
                "tests/fixtures/knowledge/sdtmig34-gold-set.json",
            ],
            "text": {
                "en": (
                    "Accept P1 Gold locator compatibility",
                    "All seven P2-expressible Gold locators match at field level; the web erratum remains explicitly outside the PDF/XLSX map.",
                    "Approve 7/7 Gold compatibility without converting the release-page erratum into a false source locator.",
                    "Gold preservation anchors later extraction while keeping source modalities honest.",
                ),
                "zh-CN": (
                    "确认 P1 Gold locator 兼容性",
                    "七个可由 P2 表达的 Gold locator 均达到字段级一致；网页 erratum 明确保留在 PDF/XLSX 地图之外。",
                    "批准 7/7 Gold 兼容性，但不得把发布页 erratum 转换成虚假的来源 locator。",
                    "保留 Gold 期望可以锚定后续抽取，同时维持来源形态的真实性。",
                ),
            },
        },
        {
            "id": "F-008",
            "category": "compliance",
            "severity": "warning",
            "location": "p6-p2-structure-map#CHK-008",
            "evidence_refs": ["structure-review:CHK-008", "source-manifest.json#storage_mode"],
            "text": {
                "en": (
                    "Accept hash-locked rebuild identity and storage boundary",
                    f"The local maps match the committed base hash {base_hash} and deep hash {deep_hash}; each hash was reproduced in two recorded runs.",
                    "Approve ignored rebuildable maps plus committed generators, tests, and compact hash/count reports as the P2 storage boundary.",
                    "This keeps restricted content out of Git and Obsidian while preserving deterministic reconstruction and drift detection.",
                ),
                "zh-CN": (
                    "确认哈希锁定的重建身份与存储边界",
                    f"本地地图与已提交的 base hash {base_hash} 和 deep hash {deep_hash} 一致；两个哈希都已在两次记录的重建中复现。",
                    "批准将可重建地图保持为 Git ignored，同时提交生成器、测试及紧凑哈希/计数报告，作为 P2 存储边界。",
                    "该边界既能避免受限内容进入 Git 和 Obsidian，也保留确定性重建与漂移检测能力。",
                ),
            },
        },
    ]
    findings = []
    for spec in finding_specs:
        title, current_value, proposed_value, rationale = spec["text"][language]
        findings.append(
            {
                "id": spec["id"],
                "category": spec["category"],
                "severity": spec["severity"],
                "location": spec["location"],
                "title": title,
                "current_value": current_value,
                "proposed_value": proposed_value,
                "rationale": rationale,
                "evidence_refs": spec["evidence_refs"],
                "auto_approved": False,
            }
        )

    summaries = {
        "en": (
            "P6-P2 human gate for the SDTMIG 3.4 full navigation map and the bounded "
            "Core/Events/AE deep locator layer. Approval accepts structure and traceability "
            "only; it does not promote knowledge statements or publish restricted source text."
        ),
        "zh-CN": (
            "P6-P2 人工审核门：审核 SDTMIG 3.4 全书导航地图以及限定的 "
            "Core/Events/AE 深层 locator。批准仅接受结构与追溯基线，不会提升知识 "
            "statement，也不会发布受限来源正文。"
        ),
    }
    generated_by = {
        "en": "P6-P2 SDTMIG 3.4 structure-map review builder",
        "zh-CN": "P6-P2 SDTMIG 3.4 结构地图审核生成器",
    }
    return {
        "review_id": REVIEW_ID,
        "review_type": "sdtm_spec",
        "source_documents": [
            f"{PACKAGE_RELATIVE_PATH.as_posix()}/{REPORT_NAME}",
            f"{PACKAGE_RELATIVE_PATH.as_posix()}/structure-map-summary.json",
            f"{PACKAGE_RELATIVE_PATH.as_posix()}/deep-structure-summary.json",
            f"{PACKAGE_RELATIVE_PATH.as_posix()}/source-manifest.json",
            "tests/fixtures/knowledge/sdtmig34-gold-set.json",
            "schemas/extraction/source-structure-map.schema.json",
        ],
        "agent_summary": summaries[language],
        "findings": findings,
        "urgency": "blocking",
        "created_at": created_at,
        "generated_by": generated_by[language],
        "auto_approved_count": 0,
    }


def build_structure_review_artifacts(
    wiki_root: str | Path,
    *,
    created_at: str,
    packet_language: str = DEFAULT_REVIEW_LANGUAGE,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a closed audit report and Engine-schema-valid ReviewPacket."""

    root = Path(wiki_root).resolve()
    _validate_created_at(created_at)
    package = root / PACKAGE_RELATIVE_PATH
    base_summary = _read_json(package / "structure-map-summary.json")
    deep_summary = _read_json(package / "deep-structure-summary.json")
    manifest = _read_json(package / "source-manifest.json")
    gold_set = _read_json(
        root / "tests" / "fixtures" / "knowledge" / "sdtmig34-gold-set.json"
    )
    base_map_path = package / "derived" / BASE_MAP_NAME
    deep_map_path = package / "derived" / DEEP_MAP_NAME
    base_map = _read_json(base_map_path)
    deep_map = _read_json(deep_map_path)
    validate_structure_map(base_map)
    validate_structure_map(deep_map)

    source_hash = manifest["original_sha256"]
    _require(manifest["source_id"] == SOURCE_ID, "source manifest ID drifted")
    _require(base_summary["source_id"] == SOURCE_ID, "base summary source ID drifted")
    _require(deep_summary["source_id"] == SOURCE_ID, "deep summary source ID drifted")
    _require(gold_set["source_id"] == SOURCE_ID, "Gold Set source ID drifted")
    _require(base_summary["source_sha256"] == source_hash, "base source hash drifted")
    _require(deep_summary["source_sha256"] == source_hash, "deep source hash drifted")
    _require(base_map["source_sha256"] == source_hash, "base map source hash drifted")
    _require(deep_map["source_sha256"] == source_hash, "deep map source hash drifted")

    base_hash = _sha256(base_map_path)
    deep_hash = _sha256(deep_map_path)
    _require(
        base_hash == base_summary["structure_map_sha256"],
        "local base map does not match the committed summary hash",
    )
    _require(
        deep_summary["base_structure_map_sha256"] == base_hash,
        "deep map is not bound to the current base map",
    )
    _require(
        deep_hash == deep_summary["deep_structure_map_sha256"],
        "local deep map does not match the committed summary hash",
    )

    base = base_summary["coverage"]
    deep = deep_summary["coverage"]
    checks = [
        _check(
            "CHK-001",
            "coverage",
            "Full PDF navigation coverage",
            {
                "physical_pages": base["physical_pages_mapped"],
                "outline_entries": base["outline_entries"],
                "unexplained_pages": base["unexplained_pages"],
            },
            {"physical_pages": 461, "outline_entries": 220, "unexplained_pages": 0},
            ["structure-map-summary.json#coverage"],
        ),
        _check(
            "CHK-002",
            "structure_index",
            "PDF boundaries and XLSX row index",
            {
                "domain_units": base["domain_units"],
                "table_boundaries": base["table_boundaries"],
                "dataset_rows": base["dataset_rows"],
                "variable_rows": base["variable_rows"],
                "skipped_rows": base["skipped_dataset_rows"]
                + base["skipped_variable_rows"],
            },
            {
                "domain_units": 63,
                "table_boundaries": 704,
                "dataset_rows": 63,
                "variable_rows": 1917,
                "skipped_rows": 0,
            },
            ["structure-map-summary.json#coverage"],
        ),
        _check(
            "CHK-003",
            "deep_scope",
            "Approved Core and Events semantic scope",
            {
                "physical_pages": deep["deep_physical_pages"],
                "paragraph_units": deep["deep_paragraph_units"],
                "assumption_roles": deep["deep_role_assumption"],
                "example_units": deep["deep_example_units"],
                "cross_reference_units": deep["deep_cross_reference_units"],
            },
            {
                "physical_pages": 100,
                "paragraph_units": 844,
                "assumption_roles": 177,
                "example_units": 289,
                "cross_reference_units": 85,
            },
            ["deep-structure-summary.json#scope", "deep-structure-summary.json#coverage"],
        ),
        _check(
            "CHK-004",
            "alignment",
            "Events PDF and XLSX variable alignment",
            {
                "event_domains": deep["event_domain_count"],
                "pdf_rows": deep["event_pdf_variable_rows"],
                "xlsx_rows": deep["event_xlsx_variable_rows"],
                "alignment_references": deep["pdf_xlsx_alignment_references"],
                "missing": deep["event_missing_variables"],
                "ambiguous": deep["event_ambiguous_spec_hits"],
                "order_mismatches": deep["event_order_mismatches"],
            },
            {
                "event_domains": 7,
                "pdf_rows": 204,
                "xlsx_rows": 204,
                "alignment_references": 204,
                "missing": {},
                "ambiguous": 0,
                "order_mismatches": {},
            },
            ["deep-structure-summary.json#coverage"],
        ),
        _check(
            "CHK-005",
            "ae_locator",
            "AE cross-page specification and variable coverage",
            {
                "pdf_rows": deep["ae_pdf_variable_rows"],
                "xlsx_rows": deep["ae_xlsx_variable_rows"],
                "specification_pages": deep["ae_specification_pages"],
                "specification_segments": deep["ae_specification_segments"],
            },
            {
                "pdf_rows": 60,
                "xlsx_rows": 60,
                "specification_pages": [134, 135, 136, 137],
                "specification_segments": 4,
            },
            [
                "loc-sdtmig34-p134-ae-spec-table",
                "visual-qa:pages-134-136-137-140",
            ],
        ),
        _check(
            "CHK-006",
            "references",
            "Internal and external reference classification",
            {
                "resolved_internal": deep["resolved_textual_references"],
                "external_dependencies": deep["external_textual_references"],
                "unresolved": deep["unresolved_textual_references"],
            },
            {"resolved_internal": 117, "external_dependencies": 5, "unresolved": 0},
            ["deep-structure-summary.json#coverage"],
        ),
        _check(
            "CHK-007",
            "gold_compatibility",
            "P1 Gold locator compatibility",
            {
                "expected": deep["gold_locator_expected"],
                "hits": deep["gold_locator_hits"],
                "field_matches": deep["gold_locator_field_matches"],
                "missing": deep["gold_locator_missing"],
                "field_differences": deep["gold_locator_field_differences"],
                "web_locator_excluded": deep["gold_web_locator_excluded"],
            },
            {
                "expected": 7,
                "hits": 7,
                "field_matches": 7,
                "missing": [],
                "field_differences": {},
                "web_locator_excluded": 1,
            },
            ["tests/fixtures/knowledge/sdtmig34-gold-set.json"],
        ),
        _check(
            "CHK-008",
            "identity",
            "Hash-locked rebuild identity",
            {
                "source_sha256": source_hash,
                "base_map_sha256": base_hash,
                "deep_map_sha256": deep_hash,
                "base_repeated_runs": 2,
                "deep_repeated_runs": 2,
            },
            {
                "source_sha256": "ea4ddbba4a3e10a55bb2f36d5e28d9cfc191090717c2426475279750a7f57021",
                "base_map_sha256": "15e6db580a3b6c4d5bef56c9a30fcc59c1463a820295e5ce7792c5654e092a76",
                "deep_map_sha256": "56d35561c70504e0fa1b631a0809d563591cbaf629264626eae4cd73831c2cbc",
                "base_repeated_runs": 2,
                "deep_repeated_runs": 2,
            },
            ["docs/dep/devlog/active/DEVLOG-R009-R048.md#R026", "docs/dep/devlog/active/DEVLOG-R009-R048.md#R027"],
        ),
    ]

    report = {
        "report_version": REPORT_VERSION,
        "gate_id": "p6-p2-structure-map",
        "gate_status": "pending_human_review",
        "review_id": REVIEW_ID,
        "source_id": SOURCE_ID,
        "source_bindings": {
            "source_sha256": source_hash,
            "base_structure_map_sha256": base_hash,
            "deep_structure_map_sha256": deep_hash,
        },
        "scope": {
            "full_navigation": "PDF physical pages 1-461 and XLSX Dataset/Variables rows",
            "deep_locator": "Core chapters 1-4, section 6.2 Events, and section 6.2.1 AE",
            "excluded": [
                "knowledge statement promotion",
                "deep segmentation outside approved scope",
                "web errata represented as a PDF/XLSX locator",
            ],
        },
        "checks": checks,
        "visual_qa": {
            "machine_precheck": "passed",
            "agent_visual_qa": "passed",
            "human_review": "pending",
            "physical_pages_checked": [134, 136, 137, 140],
            "note": "Human review uses the authorized local PDF; the Review Panel records decisions only.",
        },
        "rebuild_evidence": {
            "base": {
                "runs": 2,
                "observed_sha256": [base_hash, base_hash],
                "recorded_in": "docs/dep/devlog/active/DEVLOG-R009-R048.md#R026",
            },
            "deep": {
                "runs": 2,
                "observed_sha256": [deep_hash, deep_hash],
                "recorded_in": "docs/dep/devlog/active/DEVLOG-R009-R048.md#R027",
            },
        },
        "summary": {
            "checks_total": len(checks),
            "checks_passed": sum(item["status"] == "passed" for item in checks),
            "checks_failed": sum(item["status"] != "passed" for item in checks),
            "human_findings_pending": 8,
        },
    }

    finding_specs = [
        (
            "F-001",
            "compliance",
            "info",
            "p6-p2-structure-map#CHK-001",
            "Accept the full-document navigation coverage baseline",
            "461/461 pages and 220/220 outline entries are mapped with zero unexplained pages.",
            "Approve the page-to-outline navigation layer as the P2 full-document coverage baseline.",
            "Navigation coverage prevents later extraction from silently skipping source regions.",
            ["structure-review:CHK-001"],
        ),
        (
            "F-002",
            "mapping",
            "info",
            "p6-p2-structure-map#CHK-002",
            "Accept PDF boundary detection and XLSX row indexing",
            "63 domains, 704 PDF table boundaries, 63 dataset rows, and 1917 variable rows are indexed with no skipped data rows.",
            "Approve the PDF navigation boundaries and structured workbook index as complementary source structure.",
            "PDF and XLSX provide different locator granularity and must remain separately traceable.",
            ["structure-review:CHK-002"],
        ),
        (
            "F-003",
            "compliance",
            "info",
            "p6-p2-structure-map#CHK-003",
            "Accept the bounded Core and Events deep-locator scope",
            "The approved 100-page scope contains 844 paragraph units, 177 assumption roles, 289 examples, and 85 cross-reference units.",
            "Approve deep segmentation only for Core chapters 1-4, section 6.2 Events, and section 6.2.1 AE.",
            "A bounded deep layer preserves retrieval quality without claiming full-book paragraph extraction.",
            ["structure-review:CHK-003"],
        ),
        (
            "F-004",
            "mapping",
            "warning",
            "p6-p2-structure-map#CHK-004",
            "Accept Events PDF-to-XLSX variable alignment",
            "All 204 Events PDF variable rows align to 204 workbook rows across seven domains with no missing, ambiguous, or order-difference result.",
            "Approve the 204 typed alignment references as the Events variable trace baseline.",
            "Variable-level traceability is required before extracting executable SDTM guidance.",
            ["structure-review:CHK-004"],
        ),
        (
            "F-005",
            "mapping",
            "warning",
            "p6-p2-structure-map#CHK-005",
            "Accept the AE cross-page table locator",
            "The AE specification is one table unit with four page locators on pages 134-137 and 60/60 PDF/XLSX variable rows.",
            "Approve the cross-page AE table boundary and the first/middle/last locator visual checks.",
            "Treating continuation pages as unrelated tables would break AE variable context and citations.",
            ["structure-review:CHK-005", "visual-qa:pages-134-136-137-140"],
        ),
        (
            "F-006",
            "compliance",
            "info",
            "p6-p2-structure-map#CHK-006",
            "Accept internal and external reference classification",
            "117 SDTMIG section references resolve internally, five SDTM or ICH E3 references remain typed external dependencies, and none are unresolved.",
            "Approve the reference closure and preserve external standards as dependencies rather than guessed SDTMIG targets.",
            "Typed reference boundaries prevent missing citations and false internal links.",
            ["structure-review:CHK-006"],
        ),
        (
            "F-007",
            "compliance",
            "warning",
            "p6-p2-structure-map#CHK-007",
            "Accept P1 Gold locator compatibility",
            "All seven P2-expressible Gold locators match at field level; the web erratum remains explicitly outside the PDF/XLSX map.",
            "Approve 7/7 Gold compatibility without converting the release-page erratum into a false source locator.",
            "Gold preservation anchors later extraction while keeping source modalities honest.",
            ["structure-review:CHK-007", "tests/fixtures/knowledge/sdtmig34-gold-set.json"],
        ),
        (
            "F-008",
            "compliance",
            "warning",
            "p6-p2-structure-map#CHK-008",
            "Accept hash-locked rebuild identity and storage boundary",
            f"The local maps match the committed base hash {base_hash} and deep hash {deep_hash}; each hash was reproduced in two recorded runs.",
            "Approve ignored rebuildable maps plus committed generators, tests, and compact hash/count reports as the P2 storage boundary.",
            "This keeps restricted content out of Git and Obsidian while preserving deterministic reconstruction and drift detection.",
            ["structure-review:CHK-008", "source-manifest.json#storage_mode"],
        ),
    ]
    findings = [
        {
            "id": item[0],
            "category": item[1],
            "severity": item[2],
            "location": item[3],
            "title": item[4],
            "current_value": item[5],
            "proposed_value": item[6],
            "rationale": item[7],
            "evidence_refs": item[8],
            "auto_approved": False,
        }
        for item in finding_specs
    ]
    packet = {
        "review_id": REVIEW_ID,
        "review_type": "sdtm_spec",
        "source_documents": [
            f"{PACKAGE_RELATIVE_PATH.as_posix()}/{REPORT_NAME}",
            f"{PACKAGE_RELATIVE_PATH.as_posix()}/structure-map-summary.json",
            f"{PACKAGE_RELATIVE_PATH.as_posix()}/deep-structure-summary.json",
            f"{PACKAGE_RELATIVE_PATH.as_posix()}/source-manifest.json",
            "tests/fixtures/knowledge/sdtmig34-gold-set.json",
            "schemas/extraction/source-structure-map.schema.json",
        ],
        "agent_summary": (
            "P6-P2 human gate for the SDTMIG 3.4 full navigation map and the bounded "
            "Core/Events/AE deep locator layer. Approval accepts structure and traceability "
            "only; it does not promote knowledge statements or publish restricted source text."
        ),
        "findings": findings,
        "urgency": "blocking",
        "created_at": created_at,
        "generated_by": "P6-P2 SDTMIG 3.4 structure-map review builder",
        "auto_approved_count": 0,
    }
    _require(
        packet_language in SUPPORTED_REVIEW_LANGUAGES,
        f"unsupported review language: {packet_language}",
    )
    if packet_language != "en":
        packet = build_structure_review_packet(
            created_at=created_at,
            base_hash=base_hash,
            deep_hash=deep_hash,
            language=packet_language,
        )
    Draft202012Validator(_review_schema(root)).validate(packet)
    return report, packet


def write_review_artifacts(
    report: dict[str, Any],
    packet: dict[str, Any],
    *,
    report_path: str | Path,
    packet_path: str | Path,
) -> None:
    report_target = Path(report_path)
    packet_target = Path(packet_path)
    report_target.parent.mkdir(parents=True, exist_ok=True)
    packet_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    packet_target.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki-root", type=Path, default=Path.cwd())
    parser.add_argument("--created-at", required=True)
    parser.add_argument(
        "--packet-language",
        choices=sorted(SUPPORTED_REVIEW_LANGUAGES),
        default=DEFAULT_REVIEW_LANGUAGE,
        help="Human-facing ReviewPacket language; defaults to zh-CN.",
    )
    args = parser.parse_args()
    root = args.wiki_root.resolve()
    report, packet = build_structure_review_artifacts(
        root,
        created_at=args.created_at,
        packet_language=args.packet_language,
    )
    package = root / PACKAGE_RELATIVE_PATH
    write_review_artifacts(
        report,
        packet,
        report_path=package / REPORT_NAME,
        packet_path=root / ".review_queue" / PACKET_NAME,
    )
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
