"""
EDC Importer — 从 EDC 系统导入原始临床数据。

支持的格式:
  · CSV (标准 EDC 导出)
  · SAS7BDAT (SAS 原生格式)
  · XPT (SAS Transport v5)
  · Excel (数据字典)

设计约束:
  · 确定性, 纯函数
  · 不修改原始数据
  · 生成完整的导入报告 (行数, 变量数, 缺失率)
  · 输出标准化为内部数据帧格式
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


SOURCE_METADATA_SCHEMA_PATH = (
    Path(__file__).resolve().parent / "contracts" / "source-metadata.schema.json"
)
PARSER_NAME = "clinical-workflow-edc-importer"
PARSER_VERSION = "1.0.0"


class SourceParseError(ValueError):
    """受控来源不能安全解析或不满足登记合同时抛出。"""


@dataclass
class ParsedEDCSource:
    """解析器内部双产物；DataFrame 不作为跨阶段合同。"""

    data: Any
    source_metadata: dict[str, Any]
    data_profile: dict[str, Any]
    validation_report: dict[str, Any]


@dataclass
class ImportResult:
    """EDC 数据导入结果"""
    domain: str                    # 逻辑域名 (dm, ae, cm, ...)
    source_file: str               # 源文件路径
    output_format: str             # "csv" | "sas7bdat" | "xpt"
    rows_imported: int = 0
    variables_found: int = 0
    missing_rate_pct: float = 0.0
    date_variables: list[str] = field(default_factory=list)
    code_variables: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class EDCManifest:
    """
    EDC 数据清单 — 描述哪些 EDC 表单对应哪些 SDTM 域。

    这是 aCRF (annotated CRF) 的机器可读版本。
    """
    study_id: str
    edc_system: str = "Medidata Rave"  # "Medidata Rave" | "Oracle InForm" | "Veeva CDMS"
    export_date: str = ""
    export_format: str = "csv"          # "csv" | "sas7bdat" | "xpt"
    domains: list[dict] = field(default_factory=list)
    # [{domain: "DM", source_file: "dm.csv", source_form: "DEMOG",
    #   variable_map: {raw: sdtm, ...}, ...]
    data_dictionary_path: str = ""


# ── EDC → SDTM Manifest 模板 ───────────────────────────────────


STANDARD_MANIFEST: EDCManifest = EDCManifest(
    study_id="STUDY-XXXXXX",
    edc_system="Medidata Rave",
    export_format="csv",
    domains=[
        {
            "domain": "DM",
            "source_file": "input/edc/dm.csv",
            "source_form": "DEMOG",
            "description": "Subject Demographics",
            "expected_variables": [
                "STUDYID", "SITEID", "SUBJID", "RFSTDTC", "RFENDTC",
                "BRTHDTC", "AGE", "AGEU", "SEX", "RACE", "ETHNIC",
                "ARMCD", "ARM", "ACTARMCD", "ACTARM", "COUNTRY",
            ],
            "required_variables": ["STUDYID", "SUBJID", "RFSTDTC"],
            "date_variables": ["RFSTDTC", "RFENDTC", "BRTHDTC"],
            "code_variables": ["SEX", "RACE", "ETHNIC", "COUNTRY"],
        },
        {
            "domain": "AE",
            "source_file": "input/edc/ae.csv",
            "source_form": "AE_FORM",
            "description": "Adverse Events",
            "expected_variables": [
                "STUDYID", "SUBJID", "AETERM", "AEMODIFY",
                "AELLT", "AELLTCD", "AEDECOD", "AEPTCD",
                "AEHLT", "AEHLTCD", "AEHLGT", "AEHLGTCD",
                "AEBODSYS", "AESOC", "AESEV", "AESER",
                "AEACN", "AEREL", "AEOUT",
                "AESTDTC", "AEENDTC",
            ],
            "required_variables": ["STUDYID", "SUBJID", "AETERM", "AESTDTC"],
            "date_variables": ["AESTDTC", "AEENDTC"],
            "code_variables": ["AESEV", "AESER", "AEREL", "AEOUT", "AEACN"],
        },
        {
            "domain": "CM",
            "source_file": "input/edc/cm.csv",
            "source_form": "CM_FORM",
            "description": "Concomitant / Prior Medications",
            "expected_variables": [
                "STUDYID", "SUBJID", "CMTRT", "CMMODIFY", "CMDECOD",
                "CMCAT", "CMSCAT", "CMINDC", "CMDOSE", "CMDOSU",
                "CMDOSFRQ", "CMROUTE", "CMSTDTC", "CMENDTC",
            ],
            "required_variables": ["STUDYID", "SUBJID", "CMTRT"],
            "date_variables": ["CMSTDTC", "CMENDTC"],
            "code_variables": ["CMCAT", "CMSCAT", "CMROUTE"],
        },
        {
            "domain": "LB",
            "source_file": "input/edc/lb.csv",
            "source_form": "LAB_FORM",
            "description": "Laboratory Test Results",
            "expected_variables": [
                "STUDYID", "SUBJID", "LBTESTCD", "LBTEST", "LBCAT",
                "LBORRES", "LBORRESU", "LBORNRLO", "LBORNRHI",
                "LBSTRESC", "LBSTRESN", "LBSTRESU",
                "LBSTNRLO", "LBSTNRHI", "LBNRIND",
                "LBBLFL", "VISITNUM", "VISIT", "VISITDY", "LBDTC",
            ],
            "required_variables": ["STUDYID", "SUBJID", "LBTESTCD", "LBDTC"],
            "date_variables": ["LBDTC"],
            "code_variables": ["LBTESTCD", "LBCAT", "LBNRIND", "LBBLFL"],
        },
        {
            "domain": "VS",
            "source_file": "input/edc/vs.csv",
            "source_form": "VS_FORM",
            "description": "Vital Signs",
            "expected_variables": [
                "STUDYID", "SUBJID", "VSTESTCD", "VSTEST",
                "VSORRES", "VSORRESU", "VSSTRESC", "VSSTRESN", "VSSTRESU",
                "VSBLFL", "VISITNUM", "VISIT", "VSDTC",
            ],
            "required_variables": ["STUDYID", "SUBJID", "VSTESTCD", "VSDTC"],
            "date_variables": ["VSDTC"],
            "code_variables": ["VSTESTCD", "VSBLFL"],
        },
        {
            "domain": "EX",
            "source_file": "input/edc/ex.csv",
            "source_form": "EX_FORM",
            "description": "Exposure (Study Drug Administration)",
            "expected_variables": [
                "STUDYID", "SUBJID", "EXTRT", "EXDOSE", "EXDOSU",
                "EXDOSFRQ", "EXROUTE", "EXSTDTC", "EXENDTC",
            ],
            "required_variables": ["STUDYID", "SUBJID", "EXTRT", "EXSTDTC"],
            "date_variables": ["EXSTDTC", "EXENDTC"],
            "code_variables": ["EXDOSU", "EXDOSFRQ", "EXROUTE"],
        },
        {
            "domain": "DS",
            "source_file": "input/edc/ds.csv",
            "source_form": "DS_FORM",
            "description": "Disposition",
            "expected_variables": [
                "STUDYID", "SUBJID", "DSTERM", "DSDECOD",
                "DSCAT", "DSSTDTC",
            ],
            "required_variables": ["STUDYID", "SUBJID", "DSTERM"],
            "date_variables": ["DSSTDTC"],
            "code_variables": ["DSCAT"],
        },
    ],
    data_dictionary_path="input/edc/data_dictionary.xlsx",
)


# ── EDC Import Functions ────────────────────────────────────────


def import_edc_data(manifest: EDCManifest) -> list[ImportResult]:
    """
    导入 EDC 数据 — 读取所有域, 返回导入报告。

    这是 EDC Importer MCP 工具的核心函数。
    不修改数据, 只读取和报告。
    """
    results: list[ImportResult] = []

    for domain_cfg in manifest.domains:
        domain = domain_cfg["domain"]
        source_file = domain_cfg["source_file"]

        result = ImportResult(
            domain=domain,
            source_file=source_file,
            output_format=manifest.export_format,
        )

        # 读取并验证
        try:
            data = read_edc_file(source_file, manifest.export_format)
            result.rows_imported = len(data)
            result.variables_found = len(data[0]) if data else 0

            # 检查必需变量
            headers = list(data[0].keys()) if data else []
            missing_required = [
                v for v in domain_cfg.get("required_variables", [])
                if v not in headers
            ]
            if missing_required:
                result.errors.append(
                    f"Missing required variables: {missing_required}"
                )

            # 检查日期格式
            for dv in domain_cfg.get("date_variables", []):
                if dv in headers:
                    result.date_variables.append(dv)

            # 统计缺失率
            total_cells = result.rows_imported * result.variables_found
            if total_cells > 0:
                missing_cells = sum(
                    1 for row in data
                    for v in row.values()
                    if v is None or v == "" or v == "."
                )
                result.missing_rate_pct = round(missing_cells / total_cells * 100, 2)

        except FileNotFoundError:
            result.errors.append(f"Source file not found: {source_file}")
        except Exception as e:
            result.errors.append(f"Import error: {e}")

        if result.errors:
            result.warnings.append(f"Domain {domain} has {len(result.errors)} errors")
        else:
            result.warnings.append(f"Domain {domain} imported successfully")

        results.append(result)

    return results


def read_edc_file(filepath: str, fmt: str) -> list[dict]:
    """
    读取 EDC 导出文件。

    支持:
      · CSV (带 header)
      · SAS7BDAT (通过 pyreadstat)
      · XPT (通过 pyreadstat)
    """
    path = Path(filepath)

    if fmt == "csv" or path.suffix == ".csv":
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            return list(reader)

    elif fmt in ("sas7bdat", "xpt"):
        try:
            import pyreadstat
            df, meta = pyreadstat.read_sas7bdat(str(path)) if fmt == "sas7bdat" \
                else pyreadstat.read_xport(str(path))
            return df.to_dict("records")
        except ImportError:
            raise ImportError(
                "pyreadstat is required for SAS/XPT import. "
                "Install: pip install pyreadstat"
            )

    raise ValueError(f"Unsupported format: {fmt}. Use 'csv', 'sas7bdat', or 'xpt'")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_inside_root(
    candidate: str | Path,
    allowed_root: str | Path,
    *,
    must_exist: bool = True,
) -> tuple[Path, Path]:
    root = Path(allowed_root).resolve(strict=True)
    requested = Path(candidate)
    resolved = (root / requested).resolve(strict=must_exist) if not requested.is_absolute() else (
        requested.resolve(strict=must_exist)
    )
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SourceParseError("Source path is outside the registered study root") from exc
    return root, resolved


def _status_value(value: str | None, unavailable_reason: str) -> dict[str, Any]:
    if value is None or value == "":
        return {"status": "unavailable", "value": None, "reason": unavailable_reason}
    return {"status": "available", "value": str(value), "reason": None}


def _availability(
    available_count: int,
    total_count: int,
    unavailable_reason: str,
) -> dict[str, Any]:
    status = "available" if total_count > 0 and available_count == total_count else "unavailable"
    reason = None if status == "available" else unavailable_reason
    return {
        "status": status,
        "available_count": available_count,
        "total_count": total_count,
        "reason": reason,
    }


def _provenance(
    *,
    artifact_id: str,
    source_relative_path: str,
    source_format: str,
    source_sha256: str,
    generated_at: str,
    library_versions: dict[str, str],
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "generated_at": generated_at,
        "source": {
            "relative_path": source_relative_path,
            "format": source_format,
            "sha256": source_sha256,
        },
        "parser": {
            "name": PARSER_NAME,
            "version": PARSER_VERSION,
            "python_version": platform.python_version(),
            "library_versions": library_versions,
        },
    }


def _load_source_dataframe(
    source_path: Path,
    source_format: str,
    catalog_path: Path | None,
) -> tuple[Any, Any, dict[str, str]]:
    import pandas as pd

    libraries = {"pandas": pd.__version__}
    if source_format == "csv":
        try:
            return pd.read_csv(source_path), None, libraries
        except Exception as exc:
            raise SourceParseError(f"Unable to parse registered CSV source: {exc}") from exc

    if source_format not in {"sas7bdat", "xpt"}:
        raise SourceParseError(
            f"Unsupported registered source format: {source_format}. "
            "Use csv, sas7bdat, or xpt."
        )

    try:
        import pyreadstat
    except ImportError as exc:
        raise SourceParseError(
            "pyreadstat is required for registered SAS/XPT sources"
        ) from exc

    libraries["pyreadstat"] = pyreadstat.__version__
    try:
        if source_format == "sas7bdat":
            dataframe, metadata = pyreadstat.read_sas7bdat(
                str(source_path),
                catalog_file=str(catalog_path) if catalog_path else None,
                formats_as_category=False,
            )
        else:
            dataframe, metadata = pyreadstat.read_xport(str(source_path))
    except Exception as exc:
        raise SourceParseError(
            f"Unable to parse registered {source_format.upper()} source: {exc}"
        ) from exc
    return dataframe, metadata, libraries


def _sas_variables(metadata: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    names = list(metadata.column_names or [])
    labels = list(metadata.column_labels or [])
    formats = dict(metadata.original_variable_types or {})
    storage_types = dict(metadata.readstat_variable_types or {})
    widths = dict(metadata.variable_storage_width or {})
    variable_to_label = dict(metadata.variable_to_label or {})
    value_label_sets = dict(metadata.value_labels or {})
    variable_value_labels = dict(metadata.variable_value_labels or {})

    variables: list[dict[str, Any]] = []
    label_count = 0
    format_count = 0
    value_label_count = 0
    for ordinal, name in enumerate(names, start=1):
        label = labels[ordinal - 1] if ordinal - 1 < len(labels) else None
        source_format = formats.get(name)
        label_set = variable_to_label.get(name)
        mapping = variable_value_labels.get(name) or (
            value_label_sets.get(label_set, {}) if label_set else {}
        )
        normalized_mapping = {str(key): str(value) for key, value in mapping.items()}
        if label:
            label_count += 1
        if source_format:
            format_count += 1
        if normalized_mapping:
            value_label_count += 1

        variables.append({
            "ordinal": ordinal,
            "name": name,
            "logical_type": storage_types.get(name, "unknown"),
            "source_storage_type": storage_types.get(name),
            "storage_width": widths.get(name),
            "column_label": _status_value(label, "SAS column label is not present"),
            "source_format": _status_value(source_format, "SAS format is not exposed"),
            "source_informat": _status_value(
                None,
                "pyreadstat does not expose SAS informats from this dataset",
            ),
            "value_labels": {
                "status": "available" if normalized_mapping else "unavailable",
                "label_set": label_set if normalized_mapping else None,
                "mapping": normalized_mapping,
                "reason": (
                    None
                    if normalized_mapping
                    else "No resolvable value-label mapping is embedded or supplied by catalog"
                ),
            },
        })

    availability = {
        "column_labels": _availability(
            label_count,
            len(names),
            "One or more SAS column labels are absent",
        ),
        "formats": _availability(
            format_count,
            len(names),
            "One or more SAS formats are not exposed",
        ),
        "informats": _availability(
            0,
            len(names),
            "pyreadstat does not expose SAS informats from this dataset",
        ),
        "value_labels": _availability(
            value_label_count,
            len(names),
            "No resolvable value-label mapping is embedded or supplied by catalog",
        ),
    }
    return variables, availability


def _csv_variables(dataframe: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    variables = []
    for ordinal, name in enumerate(dataframe.columns, start=1):
        variables.append({
            "ordinal": ordinal,
            "name": str(name),
            "logical_type": str(dataframe[name].dtype),
            "source_storage_type": str(dataframe[name].dtype),
            "storage_width": None,
            "column_label": _status_value(None, "CSV has no native column-label metadata"),
            "source_format": _status_value(None, "CSV has no native SAS format metadata"),
            "source_informat": _status_value(None, "CSV has no native SAS informat metadata"),
            "value_labels": {
                "status": "unavailable",
                "label_set": None,
                "mapping": {},
                "reason": "CSV has no native value-label catalog metadata",
            },
        })
    count = len(variables)
    return variables, {
        "column_labels": _availability(0, count, "CSV has no native column-label metadata"),
        "formats": _availability(0, count, "CSV has no native SAS format metadata"),
        "informats": _availability(0, count, "CSV has no native SAS informat metadata"),
        "value_labels": _availability(0, count, "CSV has no native value-label metadata"),
    }


def validate_source_metadata_artifact(artifact: dict[str, Any]) -> list[str]:
    schema = json.loads(SOURCE_METADATA_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda error: list(error.path))
    return [f"{'/'.join(str(item) for item in error.path) or '$'}: {error.message}" for error in errors]


def parse_registered_edc_source(
    filepath: str | Path,
    fmt: str,
    *,
    allowed_root: str | Path,
    expected_sha256: str,
    catalog_file: str | Path | None = None,
    generated_at: str | None = None,
) -> ParsedEDCSource:
    """读取已登记来源，并同时保留数据与稳定的 metadata 合同。"""
    root, source_path = _resolve_inside_root(filepath, allowed_root)
    source_format = fmt.lower().lstrip(".")
    expected_suffix = {"csv": ".csv", "sas7bdat": ".sas7bdat", "xpt": ".xpt"}
    if source_format not in expected_suffix:
        raise SourceParseError(f"Unsupported registered source format: {source_format}")
    if source_path.suffix.lower() != expected_suffix[source_format]:
        raise SourceParseError("Registered source format does not match the file extension")

    actual_sha256 = _sha256(source_path)
    if actual_sha256.lower() != expected_sha256.lower():
        raise SourceParseError(
            f"Source SHA-256 mismatch: expected {expected_sha256.lower()}, "
            f"got {actual_sha256.lower()}"
        )

    catalog_path: Path | None = None
    catalog_status = "not_supplied"
    catalog_reason = "No external SAS format catalog was registered"
    if catalog_file is not None:
        _, candidate = _resolve_inside_root(catalog_file, root, must_exist=False)
        if candidate.exists() and candidate.is_file():
            catalog_path = candidate
            catalog_status = "available"
            catalog_reason = None
        else:
            catalog_status = "unavailable"
            catalog_reason = "Registered external SAS format catalog is missing"

    dataframe, metadata, library_versions = _load_source_dataframe(
        source_path,
        source_format,
        catalog_path,
    )
    if metadata is None:
        variables, availability = _csv_variables(dataframe)
        dataset_metadata = {
            "row_count": int(len(dataframe)),
            "column_count": int(len(dataframe.columns)),
            "file_label": None,
            "file_encoding": "utf-8-sig",
            "file_format": "csv",
            "table_name": None,
        }
    else:
        variables, availability = _sas_variables(metadata)
        dataset_metadata = {
            "row_count": int(len(dataframe)),
            "column_count": int(len(dataframe.columns)),
            "file_label": metadata.file_label,
            "file_encoding": metadata.file_encoding,
            "file_format": metadata.file_format or source_format,
            "table_name": metadata.table_name,
        }

    availability["external_format_catalog"] = {
        "status": catalog_status,
        "available_count": 1 if catalog_status == "available" else 0,
        "total_count": 1,
        "reason": catalog_reason,
    }
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    relative_path = source_path.relative_to(root).as_posix()
    artifact_id = f"source-metadata-{actual_sha256[:12]}"
    provenance = _provenance(
        artifact_id=artifact_id,
        source_relative_path=relative_path,
        source_format=source_format,
        source_sha256=actual_sha256,
        generated_at=generated_at,
        library_versions=library_versions,
    )
    source_metadata = {
        "schema_version": "1.0.0",
        "artifact_type": "source_metadata",
        **provenance,
        "source": {
            **provenance["source"],
            "size_bytes": source_path.stat().st_size,
        },
        "dataset": dataset_metadata,
        "metadata_availability": availability,
        "variables": variables,
    }

    total_cells = int(dataframe.shape[0] * dataframe.shape[1])
    missing_by_variable = dataframe.isna().sum()
    missing_cells = int(missing_by_variable.sum())
    data_profile = {
        "schema_version": "1.0.0",
        "artifact_type": "source_data_profile",
        **provenance,
        "row_count": int(dataframe.shape[0]),
        "column_count": int(dataframe.shape[1]),
        "total_cells": total_cells,
        "missing_cells": missing_cells,
        "missing_rate_pct": round(missing_cells / total_cells * 100, 4) if total_cells else 0.0,
        "variables": [
            {
                "name": str(name),
                "missing_count": int(missing_by_variable[name]),
                "missing_rate_pct": (
                    round(int(missing_by_variable[name]) / len(dataframe) * 100, 4)
                    if len(dataframe)
                    else 0.0
                ),
            }
            for name in dataframe.columns
        ],
    }
    schema_errors = validate_source_metadata_artifact(source_metadata)
    validation_report = {
        "schema_version": "1.0.0",
        "artifact_type": "source_parser_validation",
        **provenance,
        "valid": not schema_errors,
        "checks": {
            "source_path_inside_study_root": "passed",
            "source_sha256_matches_inventory": "passed",
            "source_metadata_schema": "passed" if not schema_errors else "failed",
        },
        "schema_errors": schema_errors,
        "gaps": [
            {
                "metadata": name,
                "status": details["status"],
                "reason": details["reason"],
            }
            for name, details in availability.items()
            if details["status"] != "available"
        ],
    }
    return ParsedEDCSource(
        data=dataframe,
        source_metadata=source_metadata,
        data_profile=data_profile,
        validation_report=validation_report,
    )


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser_review_packet(
    parsed: ParsedEDCSource,
    *,
    source_documents: list[str],
    created_at: str | None = None,
) -> dict[str, Any]:
    """生成实际 Workflow 使用的中文 Parser/Derived Human-loop 包。"""
    from src.runtime.review_protocol import (
        ConsensusRule,
        FindingCategory,
        ReviewerAssignment,
        ReviewFinding,
        ReviewPacket,
        ReviewType,
        Severity,
        TimeoutConfig,
        Urgency,
    )

    metadata = parsed.source_metadata
    validation = parsed.validation_report
    dataset = metadata["dataset"]
    gaps = validation["gaps"]
    findings = [
        ReviewFinding(
            id="F-001",
            category=FindingCategory.COMPLIANCE,
            severity=Severity.CRITICAL,
            location="work/derived/edc/source-metadata.json",
            title="确认 SAS/EDC 来源元数据解析结果",
            current_value=(
                f"来源 {metadata['source']['relative_path']} 的 SHA-256 已匹配；"
                f"解析得到 {dataset['row_count']} 行、{dataset['column_count']} 列，"
                f"Source Metadata Schema 校验为"
                f"{'通过' if validation['valid'] else '失败'}。"
            ),
            proposed_value=(
                "批准该 Source Metadata Artifact 进入后续 Minimum Information Planner；"
                "本次批准不代表确认任何 SDTM 映射或 canonical 数据集。"
            ),
            rationale=(
                "Parser/Derived Gate 只确认来源 hash、字段结构、标签/格式可得性和解析完整性，"
                "后续映射仍需独立证据与审核。"
            ),
            evidence_refs=source_documents,
            auto_approved=False,
        )
    ]
    if gaps:
        gap_text = "；".join(
            f"{gap['metadata']}={gap['status']}（{gap['reason']}）" for gap in gaps
        )
        findings.append(
            ReviewFinding(
                id="F-002",
                category=FindingCategory.MAPPING,
                severity=Severity.WARNING,
                location="work/derived/edc/source-parser-validation.json#gaps",
                title="确认缺失元数据保持为显式 Gap",
                current_value=gap_text,
                proposed_value=(
                    "保留这些 unavailable/not_supplied 状态；禁止根据数据值猜测 value labels、"
                    "informat 或外部 catalog 内容。"
                ),
                rationale=(
                    "缺失元数据只应降低相关变量的映射证据强度，由 Planner/Mapping Review 决定"
                    "受影响范围，不能在解析阶段补造语义。"
                ),
                evidence_refs=[
                    "work/derived/edc/source-metadata.json#metadata_availability",
                    "work/derived/edc/source-parser-validation.json#gaps",
                ],
                auto_approved=False,
            )
        )

    packet = ReviewPacket(
        review_id="source_intake_parser_ae_v1_001",
        review_type=ReviewType.SOURCE_INTAKE,
        source_documents=source_documents,
        agent_summary=(
            "Parser/Derived 审核：已按登记 hash 读取 SAS7BDAT/CSV，并生成字段元数据、"
            "缺失概况和本地 preview。请确认解析证据及显式 gap；本审核不确认 SDTM 映射。"
        ),
        findings=findings,
        urgency=Urgency.BLOCKING,
        created_at=created_at or metadata["generated_at"],
        generated_by="clinical-workflow-edc-importer",
        auto_approved_count=0,
        required_reviewers=[
            ReviewerAssignment(role="clinical_programmer"),
            ReviewerAssignment(role="data_manager"),
        ],
        consensus_rule=ConsensusRule.ALL_MUST_APPROVE,
        timeout_config=TimeoutConfig(
            reminder_hours=24,
            escalation_hours=72,
            stale_hours=168,
        ),
    )
    return packet.to_dict()


def write_source_parse_artifacts(
    parsed: ParsedEDCSource,
    *,
    study_root: str | Path,
    output_dir: str | Path,
    review_queue: str | Path | None = None,
    preview_rows: int = 5,
) -> dict[str, str]:
    """将受控 parser 产物写入 Study；preview 是本地、非 canonical 证据。"""
    root, target_dir = _resolve_inside_root(output_dir, study_root, must_exist=False)
    target_dir.mkdir(parents=True, exist_ok=True)
    if preview_rows < 0 or preview_rows > 20:
        raise SourceParseError("preview_rows must be between 0 and 20")

    metadata_path = target_dir / "source-metadata.json"
    profile_path = target_dir / "source-data-profile.json"
    preview_path = target_dir / "source-preview.local.csv"
    preview_manifest_path = target_dir / "source-preview-manifest.json"
    validation_path = target_dir / "source-parser-validation.json"

    _write_json(metadata_path, parsed.source_metadata)
    _write_json(profile_path, parsed.data_profile)
    parsed.data.head(preview_rows).to_csv(preview_path, index=False, encoding="utf-8")

    provenance = {
        key: parsed.source_metadata[key]
        for key in ("artifact_id", "generated_at", "source", "parser")
    }
    preview_manifest = {
        "schema_version": "1.0.0",
        "artifact_type": "source_preview_manifest",
        **provenance,
        "preview": {
            "relative_path": preview_path.relative_to(root).as_posix(),
            "sha256": _sha256(preview_path),
            "row_count": min(preview_rows, len(parsed.data)),
            "column_count": len(parsed.data.columns),
            "storage_policy": "local_untracked_noncanonical",
        },
    }
    _write_json(preview_manifest_path, preview_manifest)

    validation = json.loads(json.dumps(parsed.validation_report))
    validation["derived_artifacts"] = {
        "source_metadata": {
            "relative_path": metadata_path.relative_to(root).as_posix(),
            "sha256": _sha256(metadata_path),
        },
        "data_profile": {
            "relative_path": profile_path.relative_to(root).as_posix(),
            "sha256": _sha256(profile_path),
        },
        "preview_manifest": {
            "relative_path": preview_manifest_path.relative_to(root).as_posix(),
            "sha256": _sha256(preview_manifest_path),
        },
    }
    _write_json(validation_path, validation)

    paths = {
        "source_metadata": metadata_path.relative_to(root).as_posix(),
        "data_profile": profile_path.relative_to(root).as_posix(),
        "preview": preview_path.relative_to(root).as_posix(),
        "preview_manifest": preview_manifest_path.relative_to(root).as_posix(),
        "validation": validation_path.relative_to(root).as_posix(),
    }
    if review_queue is not None:
        _, queue_dir = _resolve_inside_root(review_queue, root, must_exist=False)
        queue_dir.mkdir(parents=True, exist_ok=True)
        packet_path = queue_dir / "source_intake_parser_ae_v1_001.json"
        packet = build_parser_review_packet(
            parsed,
            source_documents=[
                "source-inventory.yaml",
                paths["source_metadata"],
                paths["data_profile"],
                paths["preview_manifest"],
                paths["validation"],
            ],
        )
        _write_json(packet_path, packet)
        paths["review_packet"] = packet_path.relative_to(root).as_posix()
    return paths


def _main() -> int:
    parser = argparse.ArgumentParser(description="Parse one registered EDC/SAS source")
    parser.add_argument("--study-root", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--format", required=True, choices=["csv", "sas7bdat", "xpt"])
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--catalog-file")
    parser.add_argument("--output-dir", default="work/derived/edc")
    parser.add_argument("--review-queue", default=".review_queue")
    parser.add_argument("--preview-rows", type=int, default=5)
    args = parser.parse_args()

    parsed = parse_registered_edc_source(
        args.source,
        args.format,
        allowed_root=args.study_root,
        expected_sha256=args.expected_sha256,
        catalog_file=args.catalog_file,
    )
    paths = write_source_parse_artifacts(
        parsed,
        study_root=args.study_root,
        output_dir=args.output_dir,
        review_queue=args.review_queue,
        preview_rows=args.preview_rows,
    )
    summary = {
        "valid": parsed.validation_report["valid"],
        "artifact_id": parsed.source_metadata["artifact_id"],
        "rows": parsed.source_metadata["dataset"]["row_count"],
        "columns": parsed.source_metadata["dataset"]["column_count"],
        "gaps": [gap["metadata"] for gap in parsed.validation_report["gaps"]],
        "artifacts": paths,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def validate_edc_import(results: list[ImportResult]) -> dict[str, Any]:
    """
    验证 EDC 导入完整性。

    返回:
      { valid: bool, summary: str, domain_reports: [...] }
    """
    all_ok = True
    domain_reports = []

    for r in results:
        ok = len(r.errors) == 0
        all_ok = all_ok and ok
        domain_reports.append({
            "domain": r.domain,
            "status": "OK" if ok else "ERROR",
            "rows": r.rows_imported,
            "variables": r.variables_found,
            "missing_rate_pct": r.missing_rate_pct,
            "errors": r.errors,
        })

    return {
        "valid": all_ok,
        "summary": f"{sum(1 for d in domain_reports if d['status'] == 'OK')}/"
                   f"{len(domain_reports)} domains imported successfully, "
                   f"{sum(1 for d in domain_reports if d['status'] == 'ERROR')} with errors",
        "domain_reports": domain_reports,
    }


def generate_import_report(results: list[ImportResult],
                            manifest: EDCManifest) -> str:
    """生成人类可读的导入报告"""
    lines = [
        "EDC Data Import Report",
        "=" * 60,
        f"Study:        {manifest.study_id}",
        f"EDC System:   {manifest.edc_system}",
        f"Export Date:  {manifest.export_date or 'N/A'}",
        f"Export Format: {manifest.export_format}",
        "",
        "Domain  Source File          Rows    Vars  Missing%  Status",
        "-" * 60,
    ]

    for r in results:
        status = "OK" if len(r.errors) == 0 else f"ERROR: {len(r.errors)} errors"
        lines.append(
            f"{r.domain:7s} {r.source_file:22s} {r.rows_imported:6d} "
            f"{r.variables_found:5d}  {r.missing_rate_pct:6.1f}%  {status}"
        )
        for err in r.errors:
            lines.append(f"         ⚠ {err}")

    lines.append("-" * 60)
    total_rows = sum(r.rows_imported for r in results)
    lines.append(f"Total: {len(results)} domains, {total_rows} records imported")

    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(_main())
