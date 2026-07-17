"""Three-language AE artifacts and controlled Python reference adapter for P9."""

from __future__ import annotations

from datetime import date, datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from src.agents.ae_metadata_poc import (
    AEMetadataPOCError,
    MAPPING_APPROVED_PATH,
    validate_mapping_spec,
)
from src.mcp_tools.edc_importer import parse_registered_edc_source
from src.runtime.action_policy import (
    ActionOrigin,
    ActionRequest,
    require_authorized_action,
)
from src.runtime.pipeline_contract import (
    CONTRACT_VERSION,
    CapabilityName,
    ExecutableName,
    PipelineStage,
)


ADAPTER_ID = "p9_metadata_ae_python_reference_v1"
PROGRAM_MANIFEST_PATH = "programs/edc_to_sdtm/program-manifest.json"
DRAFT_DATASET_PATH = "output/sdtm/drafts/ae.csv"
VALIDATION_PATH = "output/sdtm/validation/ae-reference-validation.json"
EXECUTION_LOG_PATH = "output/sdtm/logs/ae-reference-execution.json"
PROVENANCE_PATH = "output/sdtm/drafts/ae.csv.provenance.json"
TRACEABILITY_PATH = "output/sdtm/traceability/ae-draft-traceability.json"

ALLOWED_OPERATIONS = {
    "constant", "concat", "sequence_by_group", "copy_trim", "partial_date_iso"
}
MONTHS = {
    name: index for index, name in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"),
        start=1,
    )
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AEMetadataPOCError(f"Cannot read trusted JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise AEMetadataPOCError(f"JSON object expected: {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _header(language: str, spec: Mapping[str, Any]) -> str:
    marker = "#" if language in {"python", "r"} else "/*"
    suffix = "" if marker == "#" else " */"
    fields = [
        f"PROGRAM: SDTM AE {language.upper()} artifact",
        "PURPOSE: Apply the approved metadata-driven AE MappingSpec",
        f"MAPPING SPEC ID: {spec['spec_id']}",
        f"MAPPING SPEC SHA256: {spec['spec_sha256']}",
        f"SOURCE SHA256: {spec['source']['sha256']}",
        f"TARGET STANDARD: {spec['target_standard']['name']} {spec['target_standard']['version']}",
        "AI GENERATED: YES - HUMAN APPROVAL: RECORDED IN MAPPINGSPEC",
        "ARBITRARY COMMANDS: NOT ALLOWED",
    ]
    return "\n".join(f"{marker} {field}{suffix}" for field in fields) + "\n"


def _python_program(spec: Mapping[str, Any]) -> str:
    targets = [item["target_variable"] for item in spec["mappings"]]
    return _header("python", spec) + f'''\n"""Transparent launcher; execution is routed through the registered P9 adapter."""
from pathlib import Path
from src.codegen.ae_programs import run_python_reference

if __name__ == "__main__":
    # Study root is explicit; no command or script path is accepted by the adapter.
    run_python_reference(Path(__file__).resolve().parents[4])

# Mapping target order: {targets!r}
'''


def _r_expression(mapping: Mapping[str, Any], study_id: str) -> str:
    target = mapping["target_variable"]
    source = mapping["source_variables"]
    operation = mapping["operation"]
    if operation == "constant":
        return f'{target} = "{mapping["parameters"]["value"]}"'
    if operation == "concat":
        return f'{target} = paste0("{study_id}-", trimws(as.character({source[0]})))'
    if operation == "sequence_by_group":
        return f"{target} = row_number()"
    if operation == "copy_trim":
        return f"{target} = trimws(as.character({source[0]}))"
    if operation == "partial_date_iso":
        return f"{target} = p9_partial_date_iso({source[0]})"
    raise AEMetadataPOCError(f"Unknown controlled operation: {operation}")


def _r_program(spec: Mapping[str, Any]) -> str:
    expressions = ",\n    ".join(
        _r_expression(item, spec["study_id"]) for item in spec["mappings"]
    )
    targets = ", ".join(item["target_variable"] for item in spec["mappings"])
    return _header("r", spec) + f'''\n# Review artifact. R execution is outside the P9 reference-result boundary.
library(haven)
library(dplyr)

p9_partial_date_iso <- function(x) {{
  # Production implementation must preserve partial dates and is subject to R-side QC.
  trimws(as.character(x))
}}

raw <- read_sas("{spec['source']['relative_path']}")
ae <- raw %>%
  group_by(Subject) %>%
  arrange(RecordPosition, .by_group = TRUE) %>%
  mutate(
    {expressions}
  ) %>%
  ungroup() %>%
  select({targets})
'''


def _sas_expression(mapping: Mapping[str, Any], study_id: str) -> str:
    target = mapping["target_variable"]
    source = mapping["source_variables"]
    operation = mapping["operation"]
    if operation == "constant":
        return f'{target} = "{mapping["parameters"]["value"]}";'
    if operation == "concat":
        return f'{target} = cats("{study_id}-", strip(vvalue({source[0]})));'
    if operation == "sequence_by_group":
        return f"if first.Subject then {target}=1; else {target}+1;"
    if operation == "copy_trim":
        return f"{target} = strip(vvalue({source[0]}));"
    if operation == "partial_date_iso":
        return f"{target} = strip(vvalue({source[0]})); /* partial-date normalization pending SAS QC */"
    raise AEMetadataPOCError(f"Unknown controlled operation: {operation}")


def _sas_program(spec: Mapping[str, Any]) -> str:
    statements = "\n  ".join(
        _sas_expression(item, spec["study_id"]) for item in spec["mappings"]
    )
    keep = " ".join(item["target_variable"] for item in spec["mappings"])
    return _header("sas", spec) + f'''\n/* Review artifact only. SAS runtime is not configured in this POC. */
libname raw "<REGISTERED_STUDY_INPUT_LIBRARY>";
libname out "<REGISTERED_STUDY_OUTPUT_LIBRARY>";

proc sort data=raw.ae_source out=work.ae_source;
  by Subject RecordPosition;
run;

data out.ae;
  set work.ae_source;
  by Subject RecordPosition;
  length STUDYID DOMAIN USUBJID $200 AETERM $1000;
  {statements}
  keep {keep};
run;
'''


def generate_program_artifacts(study_dir: str | Path) -> dict[str, Any]:
    """Generate Python/R/SAS text from one approved MappingSpec."""
    study = Path(study_dir).resolve()
    spec_path = study / MAPPING_APPROVED_PATH
    spec = _read_json(spec_path)
    violations = validate_mapping_spec(spec)
    if violations or spec.get("status") != "approved":
        raise AEMetadataPOCError(
            f"Approved MappingSpec required: {violations[0] if violations else spec.get('status')}"
        )
    for mapping in spec["mappings"]:
        if mapping["operation"] not in ALLOWED_OPERATIONS:
            raise AEMetadataPOCError(f"Unknown controlled operation: {mapping['operation']}")
    program_root = study / "programs/edc_to_sdtm"
    paths = {
        "python": program_root / "python/build_ae.py",
        "r": program_root / "r/build_ae.R",
        "sas": program_root / "sas/build_ae.sas",
    }
    content = {
        "python": _python_program(spec),
        "r": _r_program(spec),
        "sas": _sas_program(spec),
    }
    for language, path in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content[language], encoding="utf-8")
    rule_refs = sorted({ref for item in spec["mappings"] for ref in item["rule_refs"]})
    manifest = {
        "schema_version": "1.0.0",
        "manifest_id": "ae-program-manifest-sample-ae-001-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mapping_spec_id": spec["spec_id"],
        "mapping_spec_sha256": spec["spec_sha256"],
        "source_sha256": spec["source"]["sha256"],
        "target_standard": spec["target_standard"],
        "rule_refs": rule_refs,
        "arbitrary_commands_allowed": False,
        "programs": [
            {
                "language": language,
                "path": _rel(study, path),
                "sha256": _sha256(path),
                "execution_status": (
                    "registered_reference_adapter" if language == "python" else "generated_not_executed"
                ),
            }
            for language, path in paths.items()
        ],
    }
    _write_json(study / PROGRAM_MANIFEST_PATH, manifest)
    return manifest


def _partial_date_iso(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.upper() in {"NAN", "NAT"}:
        return ""
    if re.fullmatch(r"\d{4}(-\d{2}){0,2}", text):
        return text
    parts = text.upper().split()
    if len(parts) != 3 or not re.fullmatch(r"\d{4}", parts[2]):
        raise AEMetadataPOCError("Unsupported source date shape; no value was guessed")
    year = int(parts[2])
    month = MONTHS.get(parts[1])
    if month is None:
        return f"{year:04d}"
    if parts[0].isdigit():
        day = int(parts[0])
        date(year, month, day)
        return f"{year:04d}-{month:02d}-{day:02d}"
    return f"{year:04d}-{month:02d}"


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.upper() in {"NAN", "NAT"} else text


def _execute_mapping(data: Any, spec: Mapping[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
    columns = [item["target_variable"] for item in spec["mappings"]]
    output: list[dict[str, str]] = []
    sequence: dict[str, int] = {}
    mappings = spec["mappings"]
    for _, source_row in data.iterrows():
        row: dict[str, str] = {}
        for mapping in mappings:
            operation = mapping["operation"]
            if operation not in ALLOWED_OPERATIONS:
                raise AEMetadataPOCError(f"Unknown controlled operation: {operation}")
            sources = mapping["source_variables"]
            missing = [name for name in sources if name not in data.columns]
            if missing:
                raise AEMetadataPOCError(f"Mapping source variable missing: {missing[0]}")
            target = mapping["target_variable"]
            if operation == "constant":
                value = str(mapping["parameters"]["value"])
            elif operation == "concat":
                source_value = _text(source_row[sources[0]])
                value = (
                    f"{mapping['parameters']['prefix']}"
                    f"{mapping['parameters']['separator']}{source_value}"
                ) if source_value else ""
            elif operation == "sequence_by_group":
                group = _text(source_row[mapping["parameters"]["group"]])
                if not group:
                    raise AEMetadataPOCError("Cannot derive AESEQ without subject identity")
                sequence[group] = sequence.get(group, 0) + 1
                value = str(sequence[group])
            elif operation == "copy_trim":
                value = _text(source_row[sources[0]])
            else:
                value = _partial_date_iso(source_row[sources[0]])
            row[target] = value
        output.append(row)
    return columns, output


def _validate_rows(columns: list[str], rows: list[dict[str, str]], expected_rows: int) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    required = ("STUDYID", "DOMAIN", "USUBJID", "AESEQ", "AETERM")
    if not set(required) <= set(columns):
        findings.append({
            "finding_id": "VAL-AE-COLUMNS",
            "check_code": "required_columns",
            "message": "Required POC columns absent",
            "affected_variables": sorted(set(required) - set(columns)),
        })
    if len(rows) != expected_rows:
        findings.append({
            "finding_id": "VAL-AE-ROWS",
            "check_code": "row_count",
            "message": "Source/output row count differs",
            "affected_variables": [],
        })
    keys = set()
    for index, row in enumerate(rows, start=1):
        for variable in required:
            if not row.get(variable):
                findings.append({
                    "finding_id": f"VAL-AE-REQ-{index}-{variable}",
                    "check_code": "required_value_empty",
                    "row_number": index,
                    "variable": variable,
                    "affected_variables": [variable],
                    "message": f"{variable} is empty",
                })
        key = (row.get("USUBJID"), row.get("AESEQ"))
        if key in keys:
            findings.append({
                "finding_id": f"VAL-AE-KEY-{index}",
                "check_code": "duplicate_key",
                "row_number": index,
                "affected_variables": ["USUBJID", "AESEQ"],
                "message": "Duplicate AE key",
            })
        keys.add(key)
        for variable in ("AESTDTC", "AEENDTC"):
            value = row.get(variable, "")
            if value and not re.fullmatch(r"\d{4}(-\d{2}){0,2}", value):
                findings.append({
                    "finding_id": f"VAL-AE-DATE-{index}-{variable}",
                    "check_code": "iso_partial_date_shape",
                    "row_number": index,
                    "variable": variable,
                    "affected_variables": [variable],
                    "message": "Date is not ISO 8601 partial/full shape",
                })
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for finding in findings:
        variables = finding.get("affected_variables") or ["dataset"]
        for variable in variables:
            key = (str(finding.get("check_code", "validation")), str(variable))
            item = grouped.setdefault(
                key,
                {
                    "check_code": key[0],
                    "variable": key[1],
                    "count": 0,
                    "row_count": len(rows),
                    "finding_ids": [],
                },
            )
            item["count"] += 1
            item["finding_ids"].append(finding["finding_id"])
    return {
        "validation_id": "ae-reference-validation-sample-ae-001-v1",
        "passed": not findings,
        "observed_row_count": len(rows),
        "expected_row_count": expected_rows,
        "checks": ["row_count", "required_values", "unique_key", "iso_partial_date_shape"],
        "blocking_findings": findings,
        "blocking_summary": list(grouped.values()),
        "full_sdtmig_conformance_claimed": False,
        "canonical_output_allowed": False,
    }


def run_python_reference(study_dir: str | Path) -> dict[str, Any]:
    """Run only the registered internal Python adapter; never execute generated text."""
    study = Path(study_dir).resolve()
    spec_path = study / MAPPING_APPROVED_PATH
    spec = _read_json(spec_path)
    violations = validate_mapping_spec(spec)
    if violations or spec.get("status") != "approved":
        raise AEMetadataPOCError("Valid approved MappingSpec required for reference execution")
    manifest = _read_json(study / PROGRAM_MANIFEST_PATH)
    if manifest.get("mapping_spec_sha256") != spec["spec_sha256"]:
        raise AEMetadataPOCError("Program manifest and approved MappingSpec hashes differ")
    for program in manifest.get("programs", []):
        path = study / program["path"]
        if not path.exists() or _sha256(path) != program["sha256"]:
            raise AEMetadataPOCError(f"Generated program hash drifted: {program.get('language')}")
    require_authorized_action(ActionRequest(
        contract_version=CONTRACT_VERSION,
        origin=ActionOrigin.RUNTIME,
        stage_id=PipelineStage.SDTM_PROGRAMMING,
        capability=CapabilityName.SDTM_PROGRAMMING,
        executable_name=ExecutableName.SDTM_PROGRAM_RUNNER,
        arguments={
            "adapter_id": ADAPTER_ID,
            "mapping_spec_id": spec["spec_id"],
            "mapping_spec_sha256": spec["spec_sha256"],
            "isolated_runtime": True,
            "network_access": False,
        },
    ))
    parsed = parse_registered_edc_source(
        spec["source"]["relative_path"],
        spec["source"]["format"],
        allowed_root=study,
        expected_sha256=spec["source"]["sha256"],
    )
    columns, rows = _execute_mapping(parsed.data, spec)
    validation = _validate_rows(columns, rows, len(parsed.data))
    validation_path = _write_json(study / VALIDATION_PATH, validation)
    timestamp = datetime.now(timezone.utc).isoformat()
    if validation["blocking_findings"]:
        _write_json(study / EXECUTION_LOG_PATH, {
            "status": "blocked", "adapter_id": ADAPTER_ID, "executed_at": timestamp,
            "blocking_findings": validation["blocking_findings"],
        })
        raise AEMetadataPOCError("Blocking AE reference validation finding")
    draft_path = study / DRAFT_DATASET_PATH
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    with draft_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    draft_sha = _sha256(draft_path)
    rule_evidence = {item["rule_id"]: item for item in spec["knowledge"]["rules"]}
    traceability = {
        "traceability_id": "ae-draft-traceability-sample-ae-001-v1",
        "source_sha256": spec["source"]["sha256"],
        "mapping_spec_id": spec["spec_id"],
        "mapping_spec_sha256": spec["spec_sha256"],
        "program_manifest_path": PROGRAM_MANIFEST_PATH,
        "program_manifest_sha256": _sha256(study / PROGRAM_MANIFEST_PATH),
        "draft_dataset_path": DRAFT_DATASET_PATH,
        "draft_dataset_sha256": draft_sha,
        "rule_evidence": rule_evidence,
        "explicit_gaps": spec["explicit_gaps"],
        "canonical_dataset_path": None,
    }
    traceability_path = _write_json(study / TRACEABILITY_PATH, traceability)
    provenance = {
        **traceability,
        "provenance_id": "ae-draft-provenance-sample-ae-001-v1",
        "adapter_id": ADAPTER_ID,
        "executed_at": timestamp,
        "validation_path": _rel(study, validation_path),
        "validation_sha256": _sha256(validation_path),
        "traceability_path": _rel(study, traceability_path),
        "traceability_sha256": _sha256(traceability_path),
    }
    _write_json(study / PROVENANCE_PATH, provenance)
    _write_json(study / EXECUTION_LOG_PATH, {
        "status": "draft_written", "adapter_id": ADAPTER_ID, "executed_at": timestamp,
        "row_count": len(rows), "column_count": len(columns),
        "draft_dataset_path": DRAFT_DATASET_PATH, "draft_dataset_sha256": draft_sha,
        "canonical_dataset_path": None,
    })
    return {
        "status": "draft_written",
        "draft_dataset_path": DRAFT_DATASET_PATH,
        "draft_dataset_sha256": draft_sha,
        "row_count": len(rows),
        "column_count": len(columns),
        "validation_path": VALIDATION_PATH,
        "provenance_path": PROVENANCE_PATH,
        "traceability_path": TRACEABILITY_PATH,
    }
