"""Load approved Study decisions and project them into an ExecutionContext."""

from __future__ import annotations

import hmac
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import ValidationError

from src.runtime.review_protocol import (
    CONFIRMATION_RECEIPT_SCHEMA,
    DECISION_RECEIPT_SCHEMA,
    REVIEW_PACKET_SCHEMA,
)

from .compatibility import sha256_bytes, sha256_canonical_json
from .models import (
    ProvenanceEntry,
    ResolvedRule,
    RuleLayer,
    StudyDecision,
    WorkflowStage,
)


class StudyDecisionError(ValueError):
    """A Study decision or its approval chain cannot be trusted."""


def load_study_decisions(
    project_dir: str | Path,
    *,
    study_id: str,
    stage: WorkflowStage,
) -> tuple[StudyDecision, ...]:
    """Load all approved decisions for one Study stage in stable file order."""

    project_root = Path(project_dir).resolve()
    decisions_root = (project_root / "knowledge" / "decisions").resolve()
    if not decisions_root.exists():
        return ()
    if not decisions_root.is_dir():
        raise StudyDecisionError("Study knowledge/decisions must be a directory")

    decisions: list[StudyDecision] = []
    seen_ids: set[str] = set()
    for path in sorted(decisions_root.rglob("*.json")):
        decision = _load_study_decision_file(project_root, decisions_root, path)
        if decision.study_id != study_id:
            raise StudyDecisionError(
                f"Study decision {decision.decision_id!r} has study_id "
                f"{decision.study_id!r}, expected {study_id!r}"
            )
        if decision.decision_id in seen_ids:
            raise StudyDecisionError(f"duplicate Study decision_id: {decision.decision_id}")
        seen_ids.add(decision.decision_id)
        if decision.stage is stage:
            decisions.append(decision)
    return tuple(decisions)


def load_study_decision(
    *,
    project_dir: str | Path,
    decision_path: str | Path,
    expected_study_id: str,
    expected_stage: WorkflowStage,
) -> StudyDecision:
    """Load one explicitly named decision, enforcing its Study and Stage scope."""

    project_root = Path(project_dir).resolve()
    decisions_root = (project_root / "knowledge" / "decisions").resolve()
    candidate = Path(decision_path)
    candidate = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
    decision = _load_study_decision_file(project_root, decisions_root, candidate)
    if decision.study_id != expected_study_id:
        raise StudyDecisionError(
            f"Study decision study_id {decision.study_id!r} does not match "
            f"{expected_study_id!r}"
        )
    if decision.stage is not expected_stage:
        raise StudyDecisionError(
            f"Study decision stage {decision.stage.value!r} does not match "
            f"{expected_stage.value!r}"
        )
    return decision


def project_study_decision(
    decision: StudyDecision,
) -> tuple[ResolvedRule, ProvenanceEntry]:
    """Project a validated Study decision without parsing its prose statement."""

    source_ids = tuple(dict.fromkeys((decision.decision_id, *decision.source_ids)))
    rule = ResolvedRule(
        rule_id=decision.decision_id,
        layer=RuleLayer.STUDY,
        priority=decision.priority,
        title=decision.title,
        statement=decision.statement,
        source_ids=source_ids,
        source_version=decision.version,
        source_sha256=decision.content_sha256,
        approval_receipt_id=decision.approval_evidence.review_id,
        structured_rule=decision.structured_rule,
    )
    provenance = ProvenanceEntry(
        provenance_id=f"prov-{decision.decision_id}",
        object_id=decision.decision_id,
        object_version=decision.version,
        object_sha256=decision.content_sha256,
        source_kind="study_decision",
        audit_reference=decision.approval_evidence.confirmation_path,
    )
    return rule, provenance


def _load_study_decision_file(
    project_root: Path,
    decisions_root: Path,
    decision_path: Path,
) -> StudyDecision:
    resolved = decision_path.resolve()
    if decisions_root not in resolved.parents or resolved.suffix.lower() != ".json":
        raise StudyDecisionError(
            "Study decisions may only be loaded from project/knowledge/decisions JSON files"
        )
    if not resolved.is_file():
        raise StudyDecisionError(f"Study decision file does not exist: {decision_path}")
    raw = _read_json(resolved, "Study decision")
    try:
        decision = StudyDecision.model_validate(raw)
    except ValidationError as exc:
        raise StudyDecisionError(f"Study decision contract validation failed: {exc}") from exc

    content_payload = decision.model_dump(
        mode="json",
        exclude={"approval_evidence", "content_sha256"},
    )
    actual_content_sha256 = sha256_canonical_json(content_payload)
    if not hmac.compare_digest(actual_content_sha256, decision.content_sha256):
        raise StudyDecisionError("Study decision content_sha256 is missing or mismatched")

    _validate_approval_evidence(project_root, decision)
    return decision


def _validate_approval_evidence(project_root: Path, decision: StudyDecision) -> None:
    evidence = decision.approval_evidence
    packet = _read_hash_locked_artifact(
        project_root,
        label="packet",
        relative_path=evidence.packet_path,
        expected_sha256=evidence.packet_sha256,
    )
    receipt = _read_hash_locked_artifact(
        project_root,
        label="decision receipt",
        relative_path=evidence.decision_path,
        expected_sha256=evidence.decision_sha256,
    )
    confirmation = _read_hash_locked_artifact(
        project_root,
        label="confirmation",
        relative_path=evidence.confirmation_path,
        expected_sha256=evidence.confirmation_sha256,
    )

    _validate_review_artifact_schema("packet", REVIEW_PACKET_SCHEMA, packet)
    _validate_review_artifact_schema("decision receipt", DECISION_RECEIPT_SCHEMA, receipt)
    _validate_review_artifact_schema(
        "confirmation", CONFIRMATION_RECEIPT_SCHEMA, confirmation
    )

    review_ids = {
        evidence.review_id,
        packet.get("review_id"),
        receipt.get("review_id"),
        confirmation.get("review_id"),
    }
    if len(review_ids) != 1:
        raise StudyDecisionError(
            "packet, decision receipt, confirmation, and evidence review_id must match"
        )

    finding = _unique_by_id(packet["findings"], "id", evidence.finding_id, "packet finding")
    finding_decision = _unique_by_id(
        receipt["decisions"], "finding_id", evidence.finding_id, "finding decision"
    )
    result = _unique_by_id(
        confirmation["results"], "finding_id", evidence.finding_id, "confirmation result"
    )
    required_refs = {
        f"study-decision:{decision.decision_id}",
        f"sha256:{decision.content_sha256}",
    }
    if not required_refs.issubset(set(finding["evidence_refs"])):
        raise StudyDecisionError(
            "packet finding evidence_refs must contain the exact Study decision id and hash"
        )
    if finding_decision["decision"] != "approved":
        raise StudyDecisionError("Study decision finding must have an approved decision")
    if result["original_decision"] != "approved":
        raise StudyDecisionError("confirmation must reference the approved finding decision")
    if result["application_status"] != "applied":
        raise StudyDecisionError("approved Study decision finding must be confirmed as applied")


def _read_hash_locked_artifact(
    project_root: Path,
    *,
    label: str,
    relative_path: str,
    expected_sha256: str,
) -> dict[str, Any]:
    requested = Path(relative_path)
    if requested.is_absolute():
        raise StudyDecisionError(f"{label} path must stay inside the Study project")
    path = (project_root / requested).resolve()
    if project_root not in path.parents:
        raise StudyDecisionError(f"{label} path must stay inside the Study project")
    if not path.is_file():
        raise StudyDecisionError(f"{label} artifact does not exist: {relative_path}")
    payload = path.read_bytes()
    if not hmac.compare_digest(sha256_bytes(payload), expected_sha256):
        raise StudyDecisionError(f"{label} SHA-256 is missing or mismatched")
    return _parse_json_bytes(payload, label)


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise StudyDecisionError(f"cannot read {label}: {exc}") from exc
    return _parse_json_bytes(payload, label)


def _parse_json_bytes(payload: bytes, label: str) -> dict[str, Any]:
    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StudyDecisionError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(data, dict):
        raise StudyDecisionError(f"{label} root must be an object")
    return data


def _validate_review_artifact_schema(
    label: str,
    schema: dict[str, Any],
    data: dict[str, Any],
) -> None:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
    if errors:
        raise StudyDecisionError(f"{label} schema validation failed: {errors[0].message}")


def _unique_by_id(
    items: list[dict[str, Any]],
    id_field: str,
    expected_id: str,
    label: str,
) -> dict[str, Any]:
    matches = [item for item in items if item.get(id_field) == expected_id]
    if len(matches) != 1:
        raise StudyDecisionError(
            f"{label} must contain exactly one matching finding_id {expected_id!r}"
        )
    return matches[0]
