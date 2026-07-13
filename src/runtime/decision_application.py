"""Apply human DecisionReceipt files to structured review artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from .review_protocol import (
    Decision,
    DecisionReceipt,
    FindingDecision,
    RejectionReason,
    ReviewFinding,
    ReviewPacket,
    ReviewType,
    validate_decision_receipt_schema,
    validate_review_packet_schema,
)


SUPPORTED_YAML_REVIEW_TYPES = {
    ReviewType.SDTM_SPEC,
    ReviewType.ADAM_SPEC,
    ReviewType.TFL_SHELL,
}


class DecisionApplicationError(ValueError):
    """Raised when a DecisionReceipt cannot be applied safely."""


class ApplicationStatus(StrEnum):
    """Status values accepted by CONFIRMATION_RECEIPT_SCHEMA."""

    APPLIED = "applied"
    APPLIED_WITH_ADJUSTMENT = "applied_with_adjustment"
    FAILED = "failed"


@dataclass
class ApplicationResult:
    """Result of applying a single FindingDecision."""

    finding_id: str
    original_decision: Decision
    application_status: ApplicationStatus
    actual_value: str | None = None
    adjustment_note: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "finding_id": self.finding_id,
            "original_decision": self.original_decision.value,
            "application_status": self.application_status.value,
        }
        if self.actual_value is not None:
            data["actual_value"] = self.actual_value
        if self.adjustment_note is not None:
            data["adjustment_note"] = self.adjustment_note
        if self.error_message is not None:
            data["error_message"] = self.error_message
        return data


@dataclass
class ConfirmationReceipt:
    """Agent confirmation that a DecisionReceipt was processed."""

    review_id: str
    results: list[ApplicationResult]
    applied_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    generated_by: str = "AgentRuntime"

    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.results),
            "applied": sum(
                1 for result in self.results
                if result.application_status == ApplicationStatus.APPLIED
            ),
            "adjusted": sum(
                1 for result in self.results
                if result.application_status == ApplicationStatus.APPLIED_WITH_ADJUSTMENT
            ),
            "failed": sum(
                1 for result in self.results
                if result.application_status == ApplicationStatus.FAILED
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "applied_at": self.applied_at,
            "generated_by": self.generated_by,
            "results": [result.to_dict() for result in self.results],
            "summary": self.summary(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


@dataclass
class ReworkDirective:
    """Structured instruction for rejected findings that require agent rework."""

    finding_id: str
    location: str
    rejection_reason: RejectionReason
    current_value: str
    proposed_value: str
    human_correction: str | None = None
    reference: str | None = None
    comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "finding_id": self.finding_id,
            "location": self.location,
            "rejection_reason": self.rejection_reason.value,
            "current_value": self.current_value,
            "proposed_value": self.proposed_value,
        }
        if self.human_correction:
            data["human_correction"] = self.human_correction
        if self.reference:
            data["reference"] = self.reference
        if self.comment:
            data["comment"] = self.comment
        return data


def apply_decision_receipt(
    *,
    project_dir: str | Path,
    review_queue_dir: str | Path,
    packet: ReviewPacket,
    receipt: DecisionReceipt,
    generated_by: str = "AgentRuntime",
) -> ConfirmationReceipt:
    """Apply a DecisionReceipt and write confirmation/rework files."""

    project_path = Path(project_dir)
    queue_path = _resolve_queue_path(project_path, review_queue_dir)
    queue_path.mkdir(parents=True, exist_ok=True)

    # Keep the domain-specific coverage error actionable before the generic
    # schema error (an empty receipt is structurally invalid and incomplete).
    _validate_receipt_coverage(packet, receipt)
    packet_violations = validate_review_packet_schema(packet.to_dict())
    if packet_violations:
        raise DecisionApplicationError(f"ReviewPacket schema validation failed: {packet_violations}")
    receipt_violations = validate_decision_receipt_schema(receipt.to_dict())
    if receipt_violations:
        raise DecisionApplicationError(
            f"DecisionReceipt schema validation failed: {receipt_violations}"
        )

    findings = {finding.id: finding for finding in packet.findings}
    rework_directives: list[ReworkDirective] = []
    results: list[ApplicationResult] = []

    for decision in receipt.decisions:
        finding = findings[decision.finding_id]
        if decision.decision == Decision.REJECTED:
            directive = _build_rework_directive(finding, decision)
            rework_directives.append(directive)
            results.append(
                ApplicationResult(
                    finding_id=finding.id,
                    original_decision=decision.decision,
                    application_status=ApplicationStatus.APPLIED_WITH_ADJUSTMENT,
                    actual_value=finding.current_value,
                    adjustment_note="Rework directive created instead of modifying artifact.",
                )
            )
            continue

        results.append(_apply_artifact_decision(project_path, packet, finding, decision))

    if rework_directives:
        _write_rework_directives(queue_path, packet.review_id, rework_directives)

    confirmation = ConfirmationReceipt(
        review_id=packet.review_id,
        results=results,
        generated_by=generated_by,
    )
    _write_confirmation(queue_path, confirmation)
    _write_review_audit(project_path, queue_path, confirmation)
    return confirmation


def _validate_receipt_coverage(packet: ReviewPacket, receipt: DecisionReceipt) -> None:
    if receipt.review_id != packet.review_id:
        raise DecisionApplicationError("DecisionReceipt.review_id must match ReviewPacket.review_id")

    finding_ids = {finding.id for finding in packet.findings}
    required_ids = {finding.id for finding in packet.findings if not finding.auto_approved}
    seen_ids = {decision.finding_id for decision in receipt.decisions}

    unknown_ids = sorted(seen_ids - finding_ids)
    if unknown_ids:
        raise DecisionApplicationError(f"DecisionReceipt contains unknown finding_id: {unknown_ids}")

    missing_ids = sorted(required_ids - seen_ids)
    if missing_ids:
        raise DecisionApplicationError(
            f"DecisionReceipt missing decisions for findings: {missing_ids}"
        )


def _apply_artifact_decision(
    project_dir: Path,
    packet: ReviewPacket,
    finding: ReviewFinding,
    decision: FindingDecision,
) -> ApplicationResult:
    if packet.review_type not in SUPPORTED_YAML_REVIEW_TYPES:
        return ApplicationResult(
            finding_id=finding.id,
            original_decision=decision.decision,
            application_status=ApplicationStatus.FAILED,
            error_message=f"Unsupported review_type for artifact application: {packet.review_type.value}",
        )

    try:
        artifact_path, value_path = _parse_yaml_location(project_dir, finding.location)
        data = _load_yaml_document(artifact_path)
        value = (
            finding.proposed_value
            if decision.decision == Decision.APPROVED
            else decision.modified_value
        )
        if value is None:
            raise DecisionApplicationError("modified decision requires modified_value")

        _set_path_value(data, value_path, value)
        _write_yaml_document(artifact_path, data)
        return ApplicationResult(
            finding_id=finding.id,
            original_decision=decision.decision,
            application_status=ApplicationStatus.APPLIED,
            actual_value=str(value),
        )
    except DecisionApplicationError as exc:
        return ApplicationResult(
            finding_id=finding.id,
            original_decision=decision.decision,
            application_status=ApplicationStatus.FAILED,
            error_message=str(exc),
        )


def _build_rework_directive(
    finding: ReviewFinding,
    decision: FindingDecision,
) -> ReworkDirective:
    reason = decision.rejection_reason or RejectionReason.OTHER
    return ReworkDirective(
        finding_id=finding.id,
        location=finding.location,
        rejection_reason=reason,
        current_value=finding.current_value,
        proposed_value=finding.proposed_value,
        human_correction=decision.human_correction,
        reference=decision.reference,
        comment=decision.comment,
    )


def _resolve_queue_path(project_dir: Path, review_queue_dir: str | Path) -> Path:
    queue_path = Path(review_queue_dir)
    return queue_path if queue_path.is_absolute() else project_dir / queue_path


def _parse_yaml_location(project_dir: Path, location: str) -> tuple[Path, str]:
    file_part: str
    value_path: str
    if "#" in location:
        file_part, value_path = location.split("#", 1)
    elif "::" in location:
        file_part, value_path = location.split("::", 1)
    else:
        match = re.match(r"^(.*\.ya?ml):(.*)$", location, flags=re.IGNORECASE)
        if not match:
            raise DecisionApplicationError(
                "YAML artifact location must use '<path>.yaml#field.path'"
            )
        file_part, value_path = match.group(1), match.group(2)

    if not value_path:
        raise DecisionApplicationError("YAML artifact location is missing a field path")

    artifact_path = (project_dir / file_part).resolve()
    project_root = project_dir.resolve()
    if project_root not in [artifact_path, *artifact_path.parents]:
        raise DecisionApplicationError("YAML artifact path must stay inside the project directory")
    if artifact_path.suffix.lower() not in {".yaml", ".yml"}:
        raise DecisionApplicationError("Decision application only supports YAML artifacts")
    if not artifact_path.exists():
        raise DecisionApplicationError(f"YAML artifact does not exist: {file_part}")
    return artifact_path, value_path


def _load_yaml_document(path: Path) -> Any:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DecisionApplicationError(f"Invalid YAML artifact: {path.name}") from exc
    if data is None:
        return {}
    if not isinstance(data, (dict, list)):
        raise DecisionApplicationError("YAML artifact root must be an object or array")
    return data


def _write_yaml_document(path: Path, data: Any) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _set_path_value(data: Any, value_path: str, value: str) -> None:
    segments = _parse_value_path(value_path)
    if not segments:
        raise DecisionApplicationError("YAML field path must not be empty")

    current = data
    for segment in segments[:-1]:
        current = _descend(current, segment)
    _assign(current, segments[-1], value)


def _parse_value_path(value_path: str) -> list[str | int]:
    segments: list[str | int] = []
    for part in value_path.split("."):
        if not part:
            raise DecisionApplicationError("YAML field path contains an empty segment")
        segments.extend(_parse_value_path_part(part))
    return segments


def _parse_value_path_part(part: str) -> list[str | int]:
    segments: list[str | int] = []
    key_chars: list[str] = []
    index = 0

    while index < len(part):
        char = part[index]
        if char == "[":
            if key_chars:
                segments.append("".join(key_chars))
                key_chars = []
            close_index = part.find("]", index)
            if close_index == -1:
                raise DecisionApplicationError(f"Invalid YAML field path segment: {part}")
            raw_index = part[index + 1:close_index]
            if not raw_index.isdigit():
                raise DecisionApplicationError(f"Invalid YAML list index in field path: {part}")
            segments.append(int(raw_index))
            index = close_index + 1
            continue
        if char == "]":
            raise DecisionApplicationError(f"Invalid YAML field path segment: {part}")
        key_chars.append(char)
        index += 1

    if key_chars:
        segments.append("".join(key_chars))
    if not segments:
        raise DecisionApplicationError(f"Invalid YAML field path segment: {part}")
    return segments


def _descend(current: Any, segment: str | int) -> Any:
    if isinstance(segment, int):
        if not isinstance(current, list) or segment >= len(current):
            raise DecisionApplicationError(f"YAML list index does not exist: {segment}")
        return current[segment]

    if not isinstance(current, dict) or segment not in current:
        raise DecisionApplicationError(f"YAML object key does not exist: {segment}")
    return current[segment]


def _assign(current: Any, segment: str | int, value: str) -> None:
    if isinstance(segment, int):
        if not isinstance(current, list) or segment >= len(current):
            raise DecisionApplicationError(f"YAML list index does not exist: {segment}")
        current[segment] = value
        return

    if not isinstance(current, dict):
        raise DecisionApplicationError(f"Cannot assign YAML object key on {type(current).__name__}")
    current[segment] = value


def _write_rework_directives(
    queue_dir: Path,
    review_id: str,
    directives: list[ReworkDirective],
) -> Path:
    path = queue_dir / f"{review_id}_rework.json"
    data = {
        "review_id": review_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "directives": [directive.to_dict() for directive in directives],
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _write_confirmation(
    queue_dir: Path,
    confirmation: ConfirmationReceipt,
) -> Path:
    path = queue_dir / f"{confirmation.review_id}_confirmation.json"
    path.write_text(confirmation.to_json(), encoding="utf-8")
    return path


def _write_review_audit(
    project_dir: Path,
    queue_path: Path,
    confirmation: ConfirmationReceipt,
) -> None:
    """Append application provenance without making a queue the state authority."""

    scope = "study"
    marker = queue_path / ".queue_scope.json"
    if marker.exists():
        try:
            scope = json.loads(marker.read_text(encoding="utf-8")).get("scope", scope)
        except json.JSONDecodeError:
            scope = "unknown"
    event = {
        "event": "decision_applied",
        "review_id": confirmation.review_id,
        "queue_scope": scope,
        "queue_path": str(queue_path),
        "confirmation_path": str(queue_path / f"{confirmation.review_id}_confirmation.json"),
        "application_summary": confirmation.summary(),
        "generated_by": confirmation.generated_by,
        "timestamp": confirmation.applied_at,
    }
    with (project_dir / "audit_trail.jsonl").open("a", encoding="utf-8") as audit:
        audit.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
