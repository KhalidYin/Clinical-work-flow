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

from dataclasses import dataclass, field
from typing import Any
from pathlib import Path
import csv


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
