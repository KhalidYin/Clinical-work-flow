"""Deterministic minimum-information preflight for one target artifact.

The planner classifies evidence; it does not call an LLM, map source variables,
execute code, or advance the canonical pipeline.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from enum import StrEnum
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ConfigDict, Field
import yaml

from src.knowledge.compatibility import sha256_canonical_json
from src.knowledge.models import StudyDecision
from src.mcp_tools.edc_importer import validate_source_metadata_artifact


PLAN_SCHEMA_PATH = Path(__file__).resolve().parent / "contracts" / (
    "minimum-information-plan.schema.json"
)
PLANNER_VERSION = "1.0.0"
TARGET_ARTIFACT = "sdtm_ae_dataset"


class MinimumInformationError(ValueError):
    """Planner input or output cannot be trusted."""


class RequirementClass(StrEnum):
    REQUIRED = "required"
    CONDITIONAL = "conditional"
    OPTIONAL = "optional"


class RequirementStatus(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    INVALID = "invalid"
    NOT_REQUIRED = "not_required"


class ExecutionEligibility(StrEnum):
    BLOCKED = "blocked"
    DRAFT_ALLOWED = "draft_allowed"
    CANONICAL_CANDIDATE = "canonical_candidate"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RequirementAssessment(StrictModel):
    requirement_id: str
    classification: RequirementClass
    status: RequirementStatus
    blocking: bool
    affects_variables: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reason: str


class EvidenceItem(StrictModel):
    evidence_id: str
    evidence_type: str
    status: str
    reference: str
    sha256: str | None = None


class ExplicitGap(StrictModel):
    gap_id: str
    category: str
    description: str
    blocking: bool
    affects_variables: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    required_action: str


class WikiQueryRequirement(StrictModel):
    query_id: str
    purpose: str
    scope: str
    terms: tuple[str, ...]
    required_for_variables: tuple[str, ...]
    snapshot_id: str | None = None


class ReviewRequirement(StrictModel):
    review_id: str
    review_type: str
    reason: str
    blocking_before: str


class MinimumInformationPlan(StrictModel):
    schema_version: str = "1.0.0"
    plan_id: str
    planner_version: str = PLANNER_VERSION
    generated_at: str
    study_id: str
    target_artifact: str = TARGET_ARTIFACT
    target_standard: str
    target_standard_version: str
    source_metadata_artifact_id: str | None = None
    required: tuple[RequirementAssessment, ...]
    conditional: tuple[RequirementAssessment, ...]
    optional: tuple[RequirementAssessment, ...]
    available_evidence: tuple[EvidenceItem, ...]
    producible_variables: tuple[str, ...]
    blocked_variables: tuple[str, ...]
    explicit_gaps: tuple[ExplicitGap, ...]
    required_wiki_queries: tuple[WikiQueryRequirement, ...]
    required_reviews: tuple[ReviewRequirement, ...]
    execution_eligibility: ExecutionEligibility
    creates_stage_completion_evidence: bool = False
    plan_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class TargetStandardLock(StrictModel):
    standard: str
    version: str
    locked: bool
    reference: str


class KnowledgeAvailability(StrictModel):
    available: bool
    snapshot_id: str | None = None
    version: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    reference: str
    reason: str | None = None


AE_SOURCE_CANDIDATES: dict[str, tuple[str, ...]] = {
    "STUDYID": ("STUDYID",),
    "USUBJID": ("USUBJID", "SUBJID", "SUBJECT", "SUBJECTID"),
    "AETERM": ("AETERM", "AE_TERM", "AE_START_TERM"),
    "AESTDTC": ("AESTDTC", "AESTDAT", "AE_START_DATE"),
    "AEENDTC": ("AEENDTC", "AEENDAT", "AE_END_DATE"),
    "AESEV": ("AESEV_STD", "AESEV", "SEVERITY_TEXT"),
    "AESER": ("AESER_STD", "DER_AESER_STD", "AESER", "SERIOUS_FLAG"),
    "AEREL": ("AEREL_STD", "AEREL", "RELATIONSHIP_TEXT"),
    "AEACN": ("AEACN_STD", "AEACN", "ACTION_TAKEN"),
    "AEOUT": ("AEOUT_STD", "AEOUT", "OUTCOME_TEXT"),
    "AEDECOD": ("AEDECOD", "AETERM_PT"),
    "AEBODSYS": ("AEBODSYS", "AETERM_SOC"),
    "AESOC": ("AESOC", "AETERM_SOC"),
}
CONTROLLED_TARGETS = ("AESEV", "AESER", "AEREL", "AEACN", "AEOUT")
CODING_TARGETS = ("AEDECOD", "AEBODSYS", "AESOC")
DAY_TARGETS = ("AESTDY", "AEENDY")
REQUIRED_AE_CORE = ("STUDYID", "DOMAIN", "USUBJID", "AESEQ", "AETERM")
ALL_AE_TARGETS = tuple(
    dict.fromkeys(
        (*REQUIRED_AE_CORE, "AESTDTC", "AEENDTC", *CONTROLLED_TARGETS, *CODING_TARGETS, *DAY_TARGETS)
    )
)


def _requirement(
    requirement_id: str,
    classification: RequirementClass,
    status: RequirementStatus,
    *,
    blocking: bool,
    reason: str,
    affects_variables: Iterable[str] = (),
    evidence_refs: Iterable[str] = (),
) -> RequirementAssessment:
    return RequirementAssessment(
        requirement_id=requirement_id,
        classification=classification,
        status=status,
        blocking=blocking,
        reason=reason,
        affects_variables=tuple(affects_variables),
        evidence_refs=tuple(evidence_refs),
    )


def _inventory_sources(inventory: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    sources = inventory.get("sources")
    if not isinstance(sources, list) or not all(isinstance(item, Mapping) for item in sources):
        return []
    return sources


def _source_for_role(
    sources: Iterable[Mapping[str, Any]],
    role: str,
    available_paths: set[str],
) -> Mapping[str, Any] | None:
    for source in sources:
        path = source.get("path")
        if source.get("role") == role and isinstance(path, str) and path in available_paths:
            return source
    return None


def _metadata_names(source_metadata: Mapping[str, Any]) -> dict[str, str]:
    variables = source_metadata.get("variables")
    if not isinstance(variables, list):
        return {}
    names: dict[str, str] = {}
    for variable in variables:
        if isinstance(variable, Mapping) and isinstance(variable.get("name"), str):
            name = str(variable["name"])
            names[name.upper()] = name
    return names


def _present_candidate(names: Mapping[str, str], target: str) -> str | None:
    for candidate in AE_SOURCE_CANDIDATES.get(target, ()):
        if candidate in names:
            return names[candidate]
    return None


def _gap(
    gap_id: str,
    category: str,
    description: str,
    *,
    blocking: bool,
    affects_variables: Iterable[str],
    evidence_refs: Iterable[str],
    required_action: str,
) -> ExplicitGap:
    return ExplicitGap(
        gap_id=gap_id,
        category=category,
        description=description,
        blocking=blocking,
        affects_variables=tuple(affects_variables),
        evidence_refs=tuple(evidence_refs),
        required_action=required_action,
    )


def _finalize_plan(payload: dict[str, Any]) -> MinimumInformationPlan:
    hash_payload = json.loads(json.dumps(payload, ensure_ascii=False))
    payload["plan_sha256"] = sha256_canonical_json(hash_payload)
    plan = MinimumInformationPlan.model_validate(payload)
    errors = validate_minimum_information_plan(plan.model_dump(mode="json"))
    if errors:
        raise MinimumInformationError(f"Minimum Information Plan schema invalid: {errors}")
    return plan


def validate_minimum_information_plan(plan: Mapping[str, Any]) -> list[str]:
    schema = json.loads(PLAN_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(plan), key=lambda error: list(error.path))
    violations = [
        f"{'/'.join(str(item) for item in error.path) or '$'}: {error.message}"
        for error in errors
    ]
    if not violations:
        hash_payload = dict(plan)
        declared_hash = hash_payload.pop("plan_sha256", None)
        if declared_hash != sha256_canonical_json(hash_payload):
            violations.append("plan_sha256: content hash mismatch")
    return violations


def plan_minimum_information(
    *,
    study_id: str,
    source_inventory: Mapping[str, Any],
    source_metadata: Mapping[str, Any] | None,
    target_standard: TargetStandardLock,
    knowledge: KnowledgeAvailability,
    available_source_paths: Iterable[str],
    approved_study_decisions: Iterable[StudyDecision] = (),
    generated_at: str | None = None,
) -> MinimumInformationPlan:
    """Classify evidence for SDTM AE without generating mappings or code."""
    if not study_id.strip():
        raise MinimumInformationError("study_id is required")

    available_paths = set(available_source_paths)
    sources = _inventory_sources(source_inventory)
    raw_source = _source_for_role(sources, "ae_source_data", available_paths)
    metadata_valid = False
    metadata_matches_raw = False
    metadata_errors: list[str] = []
    names: dict[str, str] = {}
    metadata_id: str | None = None
    if source_metadata is not None:
        metadata_errors = validate_source_metadata_artifact(dict(source_metadata))
        metadata_valid = not metadata_errors
        if metadata_valid:
            names = _metadata_names(source_metadata)
            metadata_id = str(source_metadata.get("artifact_id"))
            metadata_source = source_metadata.get("source", {})
            metadata_matches_raw = bool(
                raw_source
                and metadata_source.get("relative_path") == raw_source.get("path")
                and metadata_source.get("sha256") == raw_source.get("sha256")
            )

    required: list[RequirementAssessment] = []
    conditional: list[RequirementAssessment] = []
    optional: list[RequirementAssessment] = []
    evidence: list[EvidenceItem] = []
    gaps: list[ExplicitGap] = []
    producible: set[str] = set()

    raw_available = raw_source is not None
    required.append(_requirement(
        "ae_raw_dataset",
        RequirementClass.REQUIRED,
        RequirementStatus.AVAILABLE if raw_available else RequirementStatus.MISSING,
        blocking=not raw_available,
        affects_variables=ALL_AE_TARGETS,
        evidence_refs=(str(raw_source.get("path")),) if raw_source else (),
        reason=(
            "Registered AE raw source is available"
            if raw_available
            else "No available source with role ae_source_data"
        ),
    ))
    if raw_source:
        evidence.append(EvidenceItem(
            evidence_id="evidence-ae-raw-source",
            evidence_type="registered_source",
            status="available",
            reference=str(raw_source["path"]),
            sha256=str(raw_source.get("sha256")) if raw_source.get("sha256") else None,
        ))

    metadata_status = (
        RequirementStatus.AVAILABLE
        if metadata_valid and metadata_matches_raw
        else RequirementStatus.INVALID if source_metadata is not None else RequirementStatus.MISSING
    )
    required.append(_requirement(
        "source_metadata",
        RequirementClass.REQUIRED,
        metadata_status,
        blocking=metadata_status is not RequirementStatus.AVAILABLE,
        affects_variables=ALL_AE_TARGETS,
        evidence_refs=("work/derived/edc/source-metadata.json",) if source_metadata else (),
        reason=(
            "Source Metadata schema and raw source identity are valid"
            if metadata_status is RequirementStatus.AVAILABLE
            else "; ".join(metadata_errors) or "Source Metadata does not match registered raw source"
        ),
    ))
    if metadata_valid:
        evidence.append(EvidenceItem(
            evidence_id="evidence-source-metadata",
            evidence_type="source_metadata",
            status="available" if metadata_matches_raw else "identity_mismatch",
            reference="work/derived/edc/source-metadata.json",
            sha256=str(source_metadata["source"]["sha256"]),
        ))

    standard_available = target_standard.locked and bool(target_standard.version)
    required.append(_requirement(
        "target_standard",
        RequirementClass.REQUIRED,
        RequirementStatus.AVAILABLE if standard_available else RequirementStatus.MISSING,
        blocking=not standard_available,
        affects_variables=ALL_AE_TARGETS,
        evidence_refs=(target_standard.reference,),
        reason=(
            f"{target_standard.standard} {target_standard.version} is locked"
            if standard_available
            else "Target standard/version is not locked"
        ),
    ))
    knowledge_available = knowledge.available and bool(knowledge.snapshot_id and knowledge.sha256)
    required.append(_requirement(
        "governed_knowledge_snapshot",
        RequirementClass.REQUIRED,
        RequirementStatus.AVAILABLE if knowledge_available else RequirementStatus.MISSING,
        blocking=not knowledge_available,
        affects_variables=ALL_AE_TARGETS,
        evidence_refs=(knowledge.reference,),
        reason=(
            "Locked governed Wiki snapshot is available"
            if knowledge_available
            else knowledge.reason or "Locked governed Wiki snapshot is unavailable"
        ),
    ))
    if knowledge_available:
        evidence.append(EvidenceItem(
            evidence_id="evidence-governed-knowledge",
            evidence_type="knowledge_snapshot",
            status="available",
            reference=knowledge.reference,
            sha256=knowledge.sha256,
        ))

    subject_source = _present_candidate(names, "USUBJID")
    subject_available = metadata_status is RequirementStatus.AVAILABLE and subject_source is not None
    required.append(_requirement(
        "subject_identity",
        RequirementClass.REQUIRED,
        RequirementStatus.AVAILABLE if subject_available else RequirementStatus.MISSING,
        blocking=not subject_available,
        affects_variables=("USUBJID", "AESEQ"),
        evidence_refs=(f"source-metadata#variables/{subject_source}",) if subject_source else (),
        reason=(
            "A registered subject-identity source candidate is present; derivation remains reviewable"
            if subject_available
            else "No approved subject-identity source candidate is available"
        ),
    ))

    reference_source = _source_for_role(sources, "reference_date_source", available_paths)
    conditional.append(_requirement(
        "reference_date_source",
        RequirementClass.CONDITIONAL,
        RequirementStatus.AVAILABLE if reference_source else RequirementStatus.MISSING,
        blocking=False,
        affects_variables=DAY_TARGETS,
        evidence_refs=(str(reference_source["path"]),) if reference_source else (),
        reason=(
            "Reference-date source is available for study-day candidates"
            if reference_source
            else "Reference date is absent; only AESTDY/AEENDY are blocked"
        ),
    ))

    coding_candidates = {
        target: _present_candidate(names, target) for target in CODING_TARGETS
    }
    coding_available = all(coding_candidates.values())
    conditional.append(_requirement(
        "meddra_coding_source",
        RequirementClass.CONDITIONAL,
        RequirementStatus.AVAILABLE if coding_available else RequirementStatus.MISSING,
        blocking=False,
        affects_variables=CODING_TARGETS,
        evidence_refs=tuple(
            f"source-metadata#variables/{name}" for name in coding_candidates.values() if name
        ),
        reason=(
            "Raw metadata contains PT/SOC coding candidates; dictionary/version still require Mapping review"
            if coding_available
            else "MedDRA/coding source fields are incomplete"
        ),
    ))

    crf_source = _source_for_role(sources, "crf_metadata", available_paths)
    required_source_targets = ("STUDYID", "AETERM")
    ambiguous_core = [target for target in required_source_targets if not _present_candidate(names, target)]
    crf_required = bool(ambiguous_core)
    conditional.append(_requirement(
        "crf_metadata",
        RequirementClass.CONDITIONAL,
        (
            RequirementStatus.AVAILABLE
            if crf_source
            else RequirementStatus.MISSING if crf_required else RequirementStatus.NOT_REQUIRED
        ),
        blocking=crf_required and crf_source is None,
        affects_variables=tuple(ambiguous_core),
        evidence_refs=(str(crf_source["path"]),) if crf_source else (),
        reason=(
            "CRF metadata is available as supporting evidence"
            if crf_source
            else "Raw labels/names cover required source semantics; CRF is not a global prerequisite"
            if not crf_required
            else "Required raw semantics are unresolved and no CRF metadata is available"
        ),
    ))

    for role, requirement_id in (
        ("study_design_context", "protocol_context"),
        ("analysis_context", "sap_context"),
    ):
        source = _source_for_role(sources, role, available_paths)
        optional.append(_requirement(
            requirement_id,
            RequirementClass.OPTIONAL,
            RequirementStatus.AVAILABLE if source else RequirementStatus.MISSING,
            blocking=False,
            evidence_refs=(str(source["path"]),) if source else (),
            reason=(
                f"Optional {role} is available"
                if source
                else f"Optional {role} is absent and does not block base SDTM AE"
            ),
        ))

    if metadata_status is RequirementStatus.AVAILABLE:
        for target in ("STUDYID", "AETERM", "AESTDTC", "AEENDTC", *CONTROLLED_TARGETS):
            if _present_candidate(names, target):
                producible.add(target)
        if subject_available:
            producible.update(("USUBJID", "AESEQ"))
        producible.add("DOMAIN")
        if coding_available:
            producible.update(CODING_TARGETS)
        if reference_source and "AESTDTC" in producible:
            producible.add("AESTDY")
        if reference_source and "AEENDTC" in producible:
            producible.add("AEENDY")

    value_label_status = (
        source_metadata.get("metadata_availability", {}).get("value_labels", {}).get("status")
        if source_metadata
        else None
    )
    controlled_present = tuple(target for target in CONTROLLED_TARGETS if target in producible)
    if controlled_present and value_label_status != "available":
        gaps.append(_gap(
            "gap-controlled-value-labels",
            "source_metadata",
            "Source file does not provide resolvable value-label mappings for controlled fields",
            blocking=False,
            affects_variables=controlled_present,
            evidence_refs=("source-metadata#metadata_availability/value_labels",),
            required_action="Use governed CT plus Mapping Review; do not infer labels from observed values",
        ))
    if not reference_source:
        gaps.append(_gap(
            "gap-reference-date",
            "conditional_source",
            "Reference date source is unavailable",
            blocking=False,
            affects_variables=DAY_TARGETS,
            evidence_refs=("source-inventory#target_artifact_profiles/sdtm_ae_dataset",),
            required_action="Keep AESTDY/AEENDY blocked or provide an approved reference-date source",
        ))
    if not coding_available:
        gaps.append(_gap(
            "gap-meddra-coding",
            "conditional_source",
            "MedDRA/coding source evidence is incomplete",
            blocking=False,
            affects_variables=CODING_TARGETS,
            evidence_refs=("source-metadata#variables",),
            required_action="Keep coded variables blocked or provide approved coding metadata",
        ))
    if crf_required and crf_source is None:
        gaps.append(_gap(
            "gap-crf-semantics",
            "conditional_source",
            "CRF metadata is required to resolve missing source semantics",
            blocking=True,
            affects_variables=ambiguous_core,
            evidence_refs=("source-metadata#variables",),
            required_action="Provide CRF metadata or an approved Study decision with equivalent evidence",
        ))
    if metadata_status is not RequirementStatus.AVAILABLE:
        gaps.append(_gap(
            "gap-source-metadata",
            "required_source",
            "Source Metadata is missing, invalid, or does not match the registered raw source",
            blocking=True,
            affects_variables=ALL_AE_TARGETS,
            evidence_refs=("work/derived/edc/source-metadata.json",),
            required_action="Re-run the registered source parser and close the Parser/Derived Gate",
        ))
    if not knowledge_available:
        gaps.append(_gap(
            "gap-governed-knowledge",
            "required_knowledge",
            knowledge.reason or "Locked governed knowledge is unavailable",
            blocking=True,
            affects_variables=ALL_AE_TARGETS,
            evidence_refs=(knowledge.reference,),
            required_action="Restore the exact locked Wiki snapshot before Mapping context construction",
        ))

    approved_decisions = tuple(approved_study_decisions)
    for index, decision in enumerate(approved_decisions, start=1):
        evidence.append(EvidenceItem(
            evidence_id=f"evidence-study-decision-{index}",
            evidence_type="approved_study_decision",
            status="available",
            reference=decision.decision_id,
            sha256=decision.content_sha256,
        ))

    blocked_variables = tuple(variable for variable in ALL_AE_TARGETS if variable not in producible)
    blocking_requirements = [item for item in required if item.blocking]
    blocking_gaps = [item for item in gaps if item.blocking]
    core_ready = set(REQUIRED_AE_CORE).issubset(producible)
    eligibility = (
        ExecutionEligibility.DRAFT_ALLOWED
        if core_ready and not blocking_requirements and not blocking_gaps
        else ExecutionEligibility.BLOCKED
    )
    wiki_queries = (
        WikiQueryRequirement(
            query_id="wiki-query-ae-domain",
            purpose="Load approved SDTMIG 3.4 AE structure and assumptions",
            scope="sdtm/events/ae",
            terms=("AE", "AETERM", "one record per adverse event per subject"),
            required_for_variables=REQUIRED_AE_CORE,
            snapshot_id=knowledge.snapshot_id,
        ),
        WikiQueryRequirement(
            query_id="wiki-query-ae-controlled-terms",
            purpose="Load governed terminology constraints without inferring raw value labels",
            scope="sdtm/controlled-terminology/ae",
            terms=CONTROLLED_TARGETS,
            required_for_variables=controlled_present,
            snapshot_id=knowledge.snapshot_id,
        ),
        WikiQueryRequirement(
            query_id="wiki-query-study-day",
            purpose="Load approved --DY calculation rule when reference dates are available",
            scope="sdtm/core/study-day",
            terms=("AESTDY", "AEENDY", "RFSTDTC"),
            required_for_variables=tuple(variable for variable in DAY_TARGETS if variable in producible),
            snapshot_id=knowledge.snapshot_id,
        ),
    )
    reviews = (
        ReviewRequirement(
            review_id="source_intake_parser_ae_v1_001",
            review_type="source_intake",
            reason="Confirm parser evidence and retain unavailable metadata as explicit gaps",
            blocking_before="mapping_context",
        ),
        ReviewRequirement(
            review_id="sdtm_spec_ae_v1_001",
            review_type="sdtm_spec",
            reason="Approve source-to-target mappings and every evidence-dependent gap decision",
            blocking_before="program_generation",
        ),
    )
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "plan_id": f"minimum-information-{study_id.lower()}-sdtm-ae-v1",
        "planner_version": PLANNER_VERSION,
        "generated_at": generated_at,
        "study_id": study_id,
        "target_artifact": TARGET_ARTIFACT,
        "target_standard": target_standard.standard,
        "target_standard_version": target_standard.version,
        "source_metadata_artifact_id": metadata_id,
        "required": [item.model_dump(mode="json") for item in required],
        "conditional": [item.model_dump(mode="json") for item in conditional],
        "optional": [item.model_dump(mode="json") for item in optional],
        "available_evidence": [item.model_dump(mode="json") for item in evidence],
        "producible_variables": tuple(variable for variable in ALL_AE_TARGETS if variable in producible),
        "blocked_variables": blocked_variables,
        "explicit_gaps": [item.model_dump(mode="json") for item in gaps],
        "required_wiki_queries": [item.model_dump(mode="json") for item in wiki_queries],
        "required_reviews": [item.model_dump(mode="json") for item in reviews],
        "execution_eligibility": eligibility.value,
        "creates_stage_completion_evidence": False,
    }
    return _finalize_plan(payload)


def verify_knowledge_snapshot(
    path: str | Path,
    *,
    expected_snapshot_id: str,
    expected_version: str,
    expected_sha256: str,
    reference: str | None = None,
) -> KnowledgeAvailability:
    stable_reference = reference or f"knowledge-snapshot:{expected_snapshot_id}@{expected_version}"
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        bundle = raw["schema_bundle"]
        items = raw["items"]
        content_hash = sha256_canonical_json({"schema_bundle": bundle, "items": items})
        valid = (
            raw.get("snapshot_id") == expected_snapshot_id
            and raw.get("version") == expected_version
            and raw.get("sha256") == expected_sha256
            and content_hash == expected_sha256
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        valid = False
    return KnowledgeAvailability(
        available=valid,
        snapshot_id=expected_snapshot_id if valid else None,
        version=expected_version if valid else None,
        sha256=expected_sha256 if valid else None,
        reference=stable_reference,
        reason=None if valid else "Knowledge snapshot identity/content hash cannot be verified",
    )


def plan_from_study(
    study_root: str | Path,
    *,
    knowledge_snapshot_path: str | Path,
    output_path: str | Path = "work/derived/plans/minimum-information-sdtm-ae.json",
    generated_at: str | None = None,
) -> MinimumInformationPlan:
    root = Path(study_root).resolve(strict=True)
    try:
        inventory = yaml.safe_load((root / "source-inventory.yaml").read_text(encoding="utf-8"))
        project = yaml.safe_load((root / "project.yaml").read_text(encoding="utf-8"))
        manifest = yaml.safe_load((root / "runtime-manifest.draft.yaml").read_text(encoding="utf-8"))
        source_metadata = json.loads(
            (root / "work/derived/edc/source-metadata.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise MinimumInformationError("Study planner inputs cannot be read") from exc
    if not all(isinstance(value, dict) for value in (inventory, project, manifest, source_metadata)):
        raise MinimumInformationError("Study planner inputs must be object documents")

    source_paths = {
        str(source["path"])
        for source in _inventory_sources(inventory)
        if isinstance(source.get("path"), str) and (root / str(source["path"])).is_file()
    }
    knowledge_lock = manifest.get("domain_knowledge", {})
    knowledge = verify_knowledge_snapshot(
        knowledge_snapshot_path,
        expected_snapshot_id=str(knowledge_lock.get("snapshot_id", "")),
        expected_version=str(knowledge_lock.get("version", "")),
        expected_sha256=str(knowledge_lock.get("sha256", "")),
        reference=(
            f"locked-knowledge/snapshots/{knowledge_lock.get('snapshot_id', '')}.json"
        ),
    )
    plan = plan_minimum_information(
        study_id=str(project.get("study_id", "")),
        source_inventory=inventory,
        source_metadata=source_metadata,
        target_standard=TargetStandardLock(
            standard="SDTMIG",
            version=str(project.get("standards", {}).get("sdtmig_version", "")),
            locked=knowledge.available,
            reference="runtime-manifest.draft.yaml#domain_knowledge",
        ),
        knowledge=knowledge,
        available_source_paths=source_paths,
        generated_at=generated_at,
    )
    requested = Path(output_path)
    destination = (root / requested).resolve() if not requested.is_absolute() else requested.resolve()
    if root not in (destination, *destination.parents):
        raise MinimumInformationError("Plan output path must stay inside the Study root")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return plan


def _main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic SDTM AE minimum-information plan")
    parser.add_argument("--study-root", required=True)
    parser.add_argument("--knowledge-snapshot", required=True)
    parser.add_argument(
        "--output",
        default="work/derived/plans/minimum-information-sdtm-ae.json",
    )
    args = parser.parse_args()
    plan = plan_from_study(
        args.study_root,
        knowledge_snapshot_path=args.knowledge_snapshot,
        output_path=args.output,
    )
    print(json.dumps({
        "plan_id": plan.plan_id,
        "execution_eligibility": plan.execution_eligibility,
        "producible_variables": list(plan.producible_variables),
        "blocked_variables": list(plan.blocked_variables),
        "explicit_gaps": [gap.gap_id for gap in plan.explicit_gaps],
        "creates_stage_completion_evidence": plan.creates_stage_completion_evidence,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
