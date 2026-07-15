"""Controlled P7 AE execution adapter.

P7-P3 is intentionally narrow: it executes the synthetic AE MappingSpec through
one registered adapter and writes draft artifacts only after deterministic
schema, citation, action-policy, and validation gates pass.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .ae_mapping import build_ae_mapping_context, validate_ae_mapping_candidate
from src.runtime.action_policy import ActionOrigin, ActionRequest, require_authorized_action
from src.runtime.pipeline_contract import (
    CONTRACT_VERSION,
    CapabilityName,
    ExecutableName,
    PipelineStage,
)


AE_ADAPTER_ID = "p7_synthetic_ae_python_adapter_v1"
AE_OUTPUT_COLUMNS = (
    "STUDYID",
    "DOMAIN",
    "USUBJID",
    "AESEQ",
    "AETERM",
    "AESTDTC",
    "AEENDTC",
    "AESTDY",
    "AEENDY",
)


class AEExecutionError(RuntimeError):
    """The controlled AE adapter cannot produce a valid draft dataset."""


@dataclass(frozen=True, slots=True)
class AEExecutionArtifact:
    """Paths and hashes for a controlled P7-P3 AE execution."""

    status: str
    adapter_id: str
    context_sha256: str
    mapping_spec_sha256: str
    program_manifest_path: str
    validation_report_path: str
    execution_log_path: str
    provenance_path: str | None
    draft_dataset_path: str | None
    draft_dataset_sha256: str | None
    canonical_dataset_path: str | None
    applied_mapping_ids: tuple[str, ...]
    applied_rule_refs: tuple[str, ...]
    blocking_findings: tuple[str, ...]


def run_controlled_ae_execution(
    study_dir: str | Path,
    wiki_package_dir: str | Path,
    *,
    adapter_id: str = AE_ADAPTER_ID,
    extra_action_arguments: dict[str, Any] | None = None,
) -> AEExecutionArtifact:
    """Execute the P7 synthetic AE MappingSpec through a registered adapter.

    This function is the P3 runtime boundary.  It does not accept executable
    paths, shell commands, network options, or arbitrary programs.  The only
    accepted execution route is the repository Action Policy registration for
    `sdtm_program_runner` during `sdtm_programming`.
    """

    study = Path(study_dir)
    candidate = _read_json(study / "mapping-specs" / "ae-mapping-spec-success.json")
    schema = _read_json(study / "contracts" / "ae-mapping-spec.schema.json")
    context = build_ae_mapping_context(study, wiki_package_dir)
    validation = validate_ae_mapping_candidate(candidate, context, schema)
    _authorize_adapter(
        adapter_id,
        mapping_spec_id=validation.spec_id,
        extra_action_arguments=extra_action_arguments,
    )

    program = _program_manifest(adapter_id, candidate, context)
    rows = _execute_rows(study, candidate)
    report = _validate_rows(rows, study / "expected" / "sdtm" / "ae.csv")
    timestamp = datetime.now(timezone.utc).isoformat()
    output_root = study / "output" / "sdtm"
    program_path = output_root / "programs" / "ae_program_manifest.json"
    log_path = output_root / "logs" / "ae_execution_log.json"
    validation_path = output_root / "validation" / "ae_validation_report.json"

    if report["blocking_findings"]:
        _write_json(program_path, program)
        _write_json(validation_path, report)
        _write_json(
            log_path,
            {
                "status": "blocked",
                "adapter_id": adapter_id,
                "timestamp": timestamp,
                "reason": "blocking validation finding",
                "blocking_findings": report["blocking_findings"],
            },
        )
        return AEExecutionArtifact(
            status="blocked",
            adapter_id=adapter_id,
            context_sha256=context["context_sha256"],
            mapping_spec_sha256=validation.candidate_sha256,
            program_manifest_path=_relative(study, program_path),
            validation_report_path=_relative(study, validation_path),
            execution_log_path=_relative(study, log_path),
            provenance_path=None,
            draft_dataset_path=None,
            draft_dataset_sha256=None,
            canonical_dataset_path=None,
            applied_mapping_ids=tuple(item["mapping_id"] for item in candidate["mappings"]),
            applied_rule_refs=tuple(sorted({ref for item in candidate["mappings"] for ref in item["rule_refs"]})),
            blocking_findings=tuple(item["finding_id"] for item in report["blocking_findings"]),
        )

    dataset_path = output_root / "drafts" / "ae.csv"
    provenance_path = output_root / "drafts" / "ae.csv.provenance.json"
    _write_csv(dataset_path, rows, AE_OUTPUT_COLUMNS)
    dataset_sha256 = _sha256_file(dataset_path)
    program["output_dataset_sha256"] = dataset_sha256
    _write_json(program_path, program)
    _write_json(validation_path, report)
    _write_json(
        provenance_path,
        _provenance(
            study=study,
            adapter_id=adapter_id,
            context=context,
            candidate=candidate,
            mapping_spec_sha256=validation.candidate_sha256,
            dataset_path=dataset_path,
            dataset_sha256=dataset_sha256,
            program_path=program_path,
            validation_path=validation_path,
            timestamp=timestamp,
        ),
    )
    _write_json(
        log_path,
        {
            "status": "draft_written",
            "adapter_id": adapter_id,
            "timestamp": timestamp,
            "rows_written": len(rows),
            "draft_dataset_path": _relative(study, dataset_path),
            "draft_dataset_sha256": dataset_sha256,
            "canonical_dataset_path": None,
        },
    )
    return AEExecutionArtifact(
        status="draft_written",
        adapter_id=adapter_id,
        context_sha256=context["context_sha256"],
        mapping_spec_sha256=validation.candidate_sha256,
        program_manifest_path=_relative(study, program_path),
        validation_report_path=_relative(study, validation_path),
        execution_log_path=_relative(study, log_path),
        provenance_path=_relative(study, provenance_path),
        draft_dataset_path=_relative(study, dataset_path),
        draft_dataset_sha256=dataset_sha256,
        canonical_dataset_path=None,
        applied_mapping_ids=tuple(item["mapping_id"] for item in candidate["mappings"]),
        applied_rule_refs=tuple(sorted({ref for item in candidate["mappings"] for ref in item["rule_refs"]})),
        blocking_findings=(),
    )


def _authorize_adapter(
    adapter_id: str,
    *,
    mapping_spec_id: str,
    extra_action_arguments: dict[str, Any] | None = None,
) -> None:
    if adapter_id != AE_ADAPTER_ID:
        raise AEExecutionError(f"unregistered AE execution adapter: {adapter_id}")
    arguments: dict[str, Any] = {
        "adapter_id": adapter_id,
        "dataset": "AE",
        "mapping_spec_id": mapping_spec_id,
        "isolated_runtime": True,
        "network_access": False,
    }
    if extra_action_arguments:
        arguments.update(extra_action_arguments)
    try:
        request = ActionRequest(
            contract_version=CONTRACT_VERSION,
            origin=ActionOrigin.RUNTIME,
            stage_id=PipelineStage.SDTM_PROGRAMMING,
            capability=CapabilityName.SDTM_PROGRAMMING,
            executable_name=ExecutableName.SDTM_PROGRAM_RUNNER,
            arguments=arguments,
        )
        require_authorized_action(request)
    except Exception as exc:
        raise AEExecutionError(f"AE adapter action denied: {exc}") from exc


def _program_manifest(
    adapter_id: str,
    candidate: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "program_id": "ae-program-synth-ae-001-v1",
        "adapter_id": adapter_id,
        "language": "python",
        "stage_id": PipelineStage.SDTM_PROGRAMMING.value,
        "target_dataset": "AE",
        "mapping_spec_id": candidate["spec_id"],
        "context_sha256": context["context_sha256"],
        "arbitrary_command_allowed": False,
        "network_access": False,
        "canonical_output_allowed": False,
        "steps": [
            {
                "mapping_id": item["mapping_id"],
                "target_variable": item["target_variable"],
                "mapping_type": item["mapping_type"],
                "source_refs": item["source_refs"],
                "rule_refs": item["rule_refs"],
                "study_decision_refs": item.get("study_decision_refs", []),
                "adapter_operation": _adapter_operation(item),
            }
            for item in candidate["mappings"]
        ],
        "explicit_gaps": candidate["gaps"],
    }


def _adapter_operation(mapping: dict[str, Any]) -> str:
    operations = {
        "map-ae-studyid": "copy_project_study_id",
        "map-ae-domain": "set_constant_ae",
        "map-ae-usubjid": "validated_subject_identifier",
        "map-ae-aeseq": "sequence_by_source_order_within_usubjid",
        "map-ae-aeterm": "copy_verbatim_term",
        "map-ae-aestdtc": "copy_complete_iso_start_date",
        "map-ae-aeendtc": "copy_complete_iso_end_date_or_null",
        "map-ae-aestdy": "derive_study_day_from_rfstdtc",
        "map-ae-aeendy": "derive_end_study_day_from_rfstdtc_or_null",
    }
    try:
        return operations[mapping["mapping_id"]]
    except KeyError as exc:
        raise AEExecutionError(f"unsupported mapping operation: {mapping['mapping_id']}") from exc


def _execute_rows(study: Path, candidate: dict[str, Any]) -> list[dict[str, str]]:
    mapped = {item["target_variable"] for item in candidate["mappings"]}
    missing_columns = set(AE_OUTPUT_COLUMNS) - mapped
    if missing_columns:
        raise AEExecutionError(f"MappingSpec cannot produce required AE columns: {sorted(missing_columns)}")

    raw_rows = _read_csv(study / "input" / "raw" / "ae.csv")
    subject_rows = _read_csv(study / "input" / "raw" / "subject-reference.csv")
    subject_ref = {item["USUBJID"]: item for item in subject_rows}
    seq_by_subject: dict[str, int] = {}
    output = []
    for raw in raw_rows:
        usubjid = raw["subject_id"]
        if usubjid not in subject_ref:
            raise AEExecutionError(f"raw AE subject not found in subject-reference: {usubjid}")
        seq_by_subject[usubjid] = seq_by_subject.get(usubjid, 0) + 1
        rfstdtc = subject_ref[usubjid]["RFSTDTC"]
        output.append(
            {
                "STUDYID": subject_ref[usubjid]["STUDYID"],
                "DOMAIN": "AE",
                "USUBJID": usubjid,
                "AESEQ": str(seq_by_subject[usubjid]),
                "AETERM": raw["verbatim_term"],
                "AESTDTC": raw["start_date"],
                "AEENDTC": raw["end_date"],
                "AESTDY": _study_day(raw["start_date"], rfstdtc),
                "AEENDY": _study_day(raw["end_date"], rfstdtc) if raw["end_date"] else "",
            }
        )
    return output


def _validate_rows(rows: list[dict[str, str]], expected_path: Path) -> dict[str, Any]:
    findings = []
    expected = _read_csv(expected_path)
    if rows != expected:
        findings.append(
            {
                "finding_id": "VAL-AE-001",
                "severity": "critical",
                "category": "dataset_mismatch",
                "message": "Draft AE does not match P7-P1 expected SDTM AE baseline.",
                "expected_rows": len(expected),
                "actual_rows": len(rows),
            }
        )
    for index, row in enumerate(rows, start=1):
        for column in ("STUDYID", "DOMAIN", "USUBJID", "AESEQ", "AETERM", "AESTDTC"):
            if row[column] == "":
                findings.append(
                    {
                        "finding_id": f"VAL-AE-{index + 1:03d}",
                        "severity": "critical",
                        "category": "required_value_missing",
                        "message": f"{column} is required for P7 AE draft output.",
                        "row_number": index,
                        "variable": column,
                    }
                )
        if row["DOMAIN"] != "AE":
            findings.append(
                {
                    "finding_id": f"VAL-AE-DOMAIN-{index:03d}",
                    "severity": "critical",
                    "category": "domain_mismatch",
                    "message": "DOMAIN must be AE.",
                    "row_number": index,
                    "actual": row["DOMAIN"],
                }
            )
        if row["AEENDTC"] and row["AESTDTC"] > row["AEENDTC"]:
            findings.append(
                {
                    "finding_id": f"VAL-AE-DATE-{index:03d}",
                    "severity": "critical",
                    "category": "date_order",
                    "message": "AESTDTC must be <= AEENDTC when AEENDTC is present.",
                    "row_number": index,
                }
            )
    return {
        "validation_id": "ae-validation-synth-ae-001-v1",
        "target_dataset": "AE",
        "checks": [
            "column_set_matches_p7_contract",
            "required_values_present",
            "domain_constant_ae",
            "date_order",
            "matches_p7_expected_output",
        ],
        "blocking_findings": findings,
        "passed": not findings,
        "canonical_dataset_allowed": False,
    }


def _provenance(
    *,
    study: Path,
    adapter_id: str,
    context: dict[str, Any],
    candidate: dict[str, Any],
    mapping_spec_sha256: str,
    dataset_path: Path,
    dataset_sha256: str,
    program_path: Path,
    validation_path: Path,
    timestamp: str,
) -> dict[str, Any]:
    applied_rules = sorted({ref for item in candidate["mappings"] for ref in item["rule_refs"]})
    rule_evidence = {
        rule_id: context["knowledge"]["rules"][rule_id]["evidence"]
        for rule_id in applied_rules
    }
    return {
        "provenance_id": "ae-draft-provenance-synth-ae-001-v1",
        "created_at": timestamp,
        "stage_id": PipelineStage.SDTM_PROGRAMMING.value,
        "adapter_id": adapter_id,
        "target_dataset": "AE",
        "synthetic_only": True,
        "context_id": context["context_id"],
        "context_sha256": context["context_sha256"],
        "mapping_spec_id": candidate["spec_id"],
        "mapping_spec_sha256": mapping_spec_sha256,
        "draft_dataset_path": _relative(study, dataset_path),
        "draft_dataset_sha256": dataset_sha256,
        "canonical_dataset_path": None,
        "program_manifest_path": _relative(study, program_path),
        "program_manifest_sha256": _sha256_file(program_path),
        "validation_report_path": _relative(study, validation_path),
        "validation_report_sha256": _sha256_file(validation_path),
        "applied_mappings": [
            {
                "mapping_id": item["mapping_id"],
                "target_variable": item["target_variable"],
                "rule_refs": item["rule_refs"],
                "source_refs": item["source_refs"],
                "study_decision_refs": item.get("study_decision_refs", []),
            }
            for item in candidate["mappings"]
        ],
        "applied_rule_evidence": rule_evidence,
        "explicit_gaps": candidate["gaps"],
    }


def _study_day(value: str, rfstdtc: str) -> str:
    event_date = date.fromisoformat(value)
    reference = date.fromisoformat(rfstdtc)
    delta = (event_date - reference).days
    return str(delta + 1 if delta >= 0 else delta)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, str]], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()
