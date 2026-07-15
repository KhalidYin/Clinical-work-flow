"""AE MappingSpec context assembly and deterministic candidate gate.

P7-P2 deliberately stops before program generation.  This module prepares one
bounded LLM input package and verifies that a proposed MappingSpec only cites
rules, gaps, source fields, and Study-context references present in that package.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import ValidationError
from jsonschema import Draft202012Validator


class AEMappingContextError(ValueError):
    """The locked Wiki/Study context cannot support an AE MappingSpec request."""


class AEMappingCandidateError(ValueError):
    """The candidate MappingSpec is not closed over the provided context."""


@dataclass(frozen=True, slots=True)
class AEMappingValidation:
    """A schema-valid, context-closed AE MappingSpec candidate."""

    spec_id: str
    context_sha256: str
    candidate_sha256: str
    mapped_variables: tuple[str, ...]
    gap_variables: tuple[str, ...]
    rule_ref_count: int
    gap_ref_count: int


def build_ae_mapping_context(study_dir: str | Path, wiki_package_dir: str | Path) -> dict[str, Any]:
    """Build the single P7-P2 AE knowledge/query context package.

    The package is intentionally compact: it contains Study fields, approved
    SDTMIG 3.4 statements with exact evidence locators, and explicit P6 gaps.
    It never includes raw Vault Markdown, original PDF text, or executable
    commands.
    """

    study = Path(study_dir)
    package = Path(wiki_package_dir)
    approved_release = _read_json(package / "approved-proposal-release.json")
    citation_bundle = _read_json(package / "ae-citation-bundle.json")
    query_benchmark = _read_json(package / "query-benchmark.json")
    manifest = _read_json(study / "fixture-manifest.json")
    project = yaml.safe_load((study / "project.yaml").read_text(encoding="utf-8"))
    crf = _read_json(study / "input" / "crf" / "ae-crf-fields.json")
    study_context = _read_json(study / "input" / "study-context" / "approved-context.json")

    if manifest.get("synthetic_only") is not True or project.get("synthetic_only") is not True:
        raise AEMappingContextError("P7 AE pilot context requires synthetic-only fixtures")
    if manifest["p6_inputs"]["citation_bundle_id"] != citation_bundle["bundle_id"]:
        raise AEMappingContextError("fixture citation bundle lock does not match P6 bundle")
    if manifest["p6_inputs"]["query_benchmark_id"] != query_benchmark["benchmark_id"]:
        raise AEMappingContextError("fixture query benchmark lock does not match P6 benchmark")

    source_files = _source_files(study, manifest)
    raw_fields = _csv_columns(study / "input" / "raw" / "ae.csv")
    subject_fields = _csv_columns(study / "input" / "raw" / "subject-reference.csv")
    edc_fields = _csv_rows(study / "input" / "edc" / "data-dictionary.csv")
    allowed_source_refs = _allowed_source_refs(
        project=project,
        crf_fields=crf["fields"],
        edc_rows=edc_fields,
        raw_fields=raw_fields,
        subject_fields=subject_fields,
        study_context_refs=study_context["approved_context_refs"],
    )

    rules = _approved_rules(approved_release)
    gaps = {
        gap["gap_id"]: {
            "gap_id": gap["gap_id"],
            "topic": gap["topic"],
            "status": gap["status"],
            "handling": gap["handling"],
        }
        for gap in citation_bundle["coverage_gaps"]
    }

    context = {
        "context_id": "ae-mapping-context-synth-ae-001-v1",
        "schema_version": "0.1.0-draft",
        "synthetic_only": True,
        "query": {
            "task": "build_sdtm_dataset",
            "dataset": "AE",
            "stage": "sdtm_spec",
            "filters": {
                "domain": "AE",
                "implementation_guide": "SDTMIG-3.4",
                "include_core_rules": True,
                "include_explicit_gaps": True,
            },
        },
        "p6_context": {
            "snapshot_id": manifest["p6_inputs"]["snapshot_id"],
            "citation_bundle_id": citation_bundle["bundle_id"],
            "query_benchmark_id": query_benchmark["benchmark_id"],
        },
        "study": {
            "study_id": project["study_id"],
            "standards": project["standards"],
            "source_files": source_files,
            "crf_fields": [
                {
                    "field_id": field["field_id"],
                    "raw_column": field["raw_column"],
                    "required": field["required"],
                    "p7_p1_status": field.get("p7_p1_status", "available"),
                }
                for field in crf["fields"]
            ],
            "raw_fields": sorted(raw_fields),
            "subject_reference_fields": sorted(subject_fields),
            "allowed_source_refs": sorted(allowed_source_refs),
            "study_context_refs": {
                ref["ref_id"]: {
                    "ref_id": ref["ref_id"],
                    "status": ref["status"],
                    "source_path": ref["source_path"],
                }
                for ref in study_context["approved_context_refs"]
            },
        },
        "knowledge": {
            "rules": rules,
            "gaps": gaps,
        },
    }
    context["context_sha256"] = _sha256_json(
        {key: value for key, value in context.items() if key != "context_sha256"}
    )
    return context


def validate_ae_mapping_candidate(
    candidate: dict[str, Any],
    context: dict[str, Any],
    schema: dict[str, Any],
) -> AEMappingValidation:
    """Validate one MappingSpec candidate against the P7-P2 context package."""

    try:
        Draft202012Validator(schema).validate(candidate)
    except ValidationError as exc:
        if list(exc.path)[:1] == ["p6_context"]:
            raise AEMappingCandidateError(
                f"candidate P6 locks failed schema validation: {exc.message}"
            ) from exc
        raise AEMappingCandidateError(f"candidate schema validation failed: {exc.message}") from exc
    if candidate["synthetic_only"] is not True:
        raise AEMappingCandidateError("candidate must remain synthetic-only in P7")
    if candidate["target_dataset"] != context["query"]["dataset"]:
        raise AEMappingCandidateError("candidate target_dataset does not match query context")
    if candidate["p6_context"] != context["p6_context"]:
        raise AEMappingCandidateError("candidate P6 locks do not match context")

    allowed_rule_ids = set(context["knowledge"]["rules"])
    allowed_gap_ids = set(context["knowledge"]["gaps"])
    allowed_source_refs = set(context["study"]["allowed_source_refs"])
    allowed_study_refs = set(context["study"]["study_context_refs"])
    target_status = {item["name"]: item["status"] for item in candidate["target_variables"]}

    rule_refs: set[str] = set()
    for mapping in candidate["mappings"]:
        if target_status.get(mapping["target_variable"]) != "mapped":
            raise AEMappingCandidateError(
                f"mapping targets a non-mapped variable: {mapping['target_variable']}"
            )
        missing_sources = set(mapping["source_refs"]) - allowed_source_refs
        if missing_sources:
            raise AEMappingCandidateError(
                f"mapping references source fields outside context: {sorted(missing_sources)}"
            )
        missing_rules = set(mapping["rule_refs"]) - allowed_rule_ids
        if missing_rules:
            raise AEMappingCandidateError(
                f"mapping references rules outside context: {sorted(missing_rules)}"
            )
        missing_study_refs = set(mapping.get("study_decision_refs", [])) - allowed_study_refs
        if missing_study_refs:
            raise AEMappingCandidateError(
                "mapping references Study context outside context: "
                f"{sorted(missing_study_refs)}"
            )
        rule_refs.update(mapping["rule_refs"])

    gap_variables = []
    for gap in candidate["gaps"]:
        target = gap["target_variable"]
        if target_status.get(target) != "explicit_gap":
            raise AEMappingCandidateError(f"gap target is not marked explicit_gap: {target}")
        if gap["source_gap_id"] not in allowed_gap_ids:
            raise AEMappingCandidateError(
                f"gap references P6 gap outside context: {gap['source_gap_id']}"
            )
        if gap["blocking"] is not True:
            raise AEMappingCandidateError(f"clinical gap must be blocking in P7-P2: {target}")
        gap_variables.append(target)

    mapped_variables = [mapping["target_variable"] for mapping in candidate["mappings"]]
    if set(mapped_variables) & set(gap_variables):
        raise AEMappingCandidateError("a variable cannot be both mapped and a gap")

    return AEMappingValidation(
        spec_id=candidate["spec_id"],
        context_sha256=context["context_sha256"],
        candidate_sha256=_sha256_json(candidate),
        mapped_variables=tuple(sorted(mapped_variables)),
        gap_variables=tuple(sorted(gap_variables)),
        rule_ref_count=len(rule_refs),
        gap_ref_count=len({gap["source_gap_id"] for gap in candidate["gaps"]}),
    )


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AEMappingContextError(f"JSON object expected: {path}")
    return payload


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _csv_columns(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        return set(next(reader))


def _source_files(study: Path, manifest: dict[str, Any]) -> dict[str, dict[str, str]]:
    files = {}
    for entry in manifest["source_files"]:
        path = study / entry["path"]
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != entry["sha256"]:
            raise AEMappingContextError(f"source file hash drifted: {entry['path']}")
        files[entry["path"]] = {"path": entry["path"], "sha256": entry["sha256"]}
    return files


def _allowed_source_refs(
    *,
    project: dict[str, Any],
    crf_fields: list[dict[str, Any]],
    edc_rows: list[dict[str, str]],
    raw_fields: set[str],
    subject_fields: set[str],
    study_context_refs: list[dict[str, Any]],
) -> set[str]:
    refs = {"target_dataset"}
    refs.update(f"project.yaml#{key}" for key in project)
    refs.update(f"input/crf/ae-crf-fields.json#{field['field_id']}" for field in crf_fields)
    refs.update(f"input/crf/ae-crf-fields.json#{field['raw_column']}" for field in crf_fields)
    refs.update(f"input/edc/data-dictionary.csv#{row['field_id']}" for row in edc_rows)
    refs.update(f"input/edc/data-dictionary.csv#{row['raw_column']}" for row in edc_rows)
    refs.update(f"input/raw/ae.csv#{field}" for field in raw_fields)
    refs.update(f"input/raw/subject-reference.csv#{field}" for field in subject_fields)
    refs.update(
        f"input/study-context/approved-context.json#{ref['ref_id']}"
        for ref in study_context_refs
    )
    return refs


def _approved_rules(approved_release: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rules = {}
    for statement in approved_release["extraction_package"]["statements"]:
        if statement["review_status"] != "approved":
            continue
        evidence = []
        for item in statement["evidence"]:
            evidence.append(
                {
                    "source_id": item["source_id"],
                    "artifact_id": item["artifact_id"],
                    "locator_id": item["locator_id"],
                    "artifact_sha256": item["artifact_sha256"],
                }
            )
        rules[statement["statement_id"]] = {
            "statement_id": statement["statement_id"],
            "subject": statement["subject"],
            "knowledge_type": statement["knowledge_type"],
            "modality": statement["modality"],
            "scope": statement["scope"],
            "statement": statement["statement"],
            "evidence": evidence,
        }
    if not rules:
        raise AEMappingContextError("approved release contains no approved rules")
    return rules


def _sha256_json(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
