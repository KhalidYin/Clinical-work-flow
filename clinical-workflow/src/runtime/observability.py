"""Local-only, redacted OpenTelemetry boundary for the P11 prerelease runtime.

The runtime may be imported without the optional OpenTelemetry dependencies.
Only ``configure_local_otel_provider`` loads the SDK.  Exported span attributes
are fail-closed: unknown keys and values that resemble credentials are never
written to the study-local JSONL trace file.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any


class ObservabilityPolicyError(ValueError):
    """Trace data or its output location violates the local redaction policy."""


class ObservabilityDependencyError(RuntimeError):
    """Optional OpenTelemetry dependencies are unavailable."""


class TraceOperation(StrEnum):
    STAGE_PRODUCTION = "clinical.stage.production"
    STAGE_VALIDATION = "clinical.stage.validation"
    TOOL_EXECUTE = "clinical.tool.execute"
    REVIEW_WAIT = "clinical.review.wait"
    KNOWLEDGE_RESOLVE = "clinical.knowledge.resolve"
    KNOWLEDGE_EVOLVE = "clinical.knowledge.evolve"


ALLOWED_TRACE_ATTRIBUTES = frozenset(
    {
        "clinical.agent.role",
        "clinical.audit_id",
        "clinical.error.type",
        "clinical.failure.category",
        "clinical.gate.disposition",
        "clinical.model.deployment_id",
        "clinical.model.profile_id",
        "clinical.model.provider",
        "clinical.review_id",
        "clinical.rework.attempt",
        "clinical.run_id",
        "clinical.snapshot_id",
        "clinical.stage_id",
        "clinical.status",
        "clinical.study_id_hash",
        "clinical.tool.name",
    }
)

_SENSITIVE_KEY_FRAGMENTS = (
    "api_key",
    "authorization",
    "cookie",
    "password",
    "patient",
    "prompt",
    "raw_data",
    "secret",
    "subject",
    "token",
)
_SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(?:api[_-]?key|password|secret|token)\s*[:=]"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
)
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_MAX_ATTRIBUTE_STRING_LENGTH = 256
_MAX_ATTRIBUTE_SEQUENCE_LENGTH = 32


def hash_study_id(study_id: str) -> str:
    """Return a stable, irreversible study identifier for trace attributes."""

    normalized = study_id.strip()
    if not normalized:
        raise ObservabilityPolicyError("study_id must not be empty")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sanitize_trace_attributes(
    attributes: Mapping[str, Any] | None,
) -> dict[str, bool | int | float | str | tuple[bool | int | float | str, ...]]:
    """Keep only known non-sensitive scalar attributes.

    Unknown or sensitive-looking fields are dropped instead of being partially
    serialized.  This prevents new providers and tools from silently expanding
    the trace data surface.
    """

    sanitized: dict[
        str, bool | int | float | str | tuple[bool | int | float | str, ...]
    ] = {}
    for key, value in (attributes or {}).items():
        normalized_key = str(key).strip()
        lowered_key = normalized_key.lower()
        if (
            normalized_key not in ALLOWED_TRACE_ATTRIBUTES
            or any(fragment in lowered_key for fragment in _SENSITIVE_KEY_FRAGMENTS)
        ):
            continue
        normalized_value = _sanitize_attribute_value(value)
        if normalized_value is None:
            continue
        if normalized_key == "clinical.study_id_hash" and (
            not isinstance(normalized_value, str)
            or _HEX_64.fullmatch(normalized_value) is None
        ):
            continue
        sanitized[normalized_key] = normalized_value
    return sanitized


def _sanitize_attribute_value(
    value: Any,
) -> bool | int | float | str | tuple[bool | int | float | str, ...] | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized or _looks_sensitive(normalized):
            return None
        return normalized[:_MAX_ATTRIBUTE_STRING_LENGTH]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        if len(value) > _MAX_ATTRIBUTE_SEQUENCE_LENGTH:
            return None
        items: list[bool | int | float | str] = []
        for item in value:
            normalized_item = _sanitize_attribute_value(item)
            if normalized_item is None or isinstance(normalized_item, tuple):
                return None
            items.append(normalized_item)
        return tuple(items)
    return None


def _looks_sensitive(value: str) -> bool:
    return any(pattern.search(value) is not None for pattern in _SENSITIVE_VALUE_PATTERNS)


class LocalJsonlTraceSink:
    """Append redacted span records to a file contained by one study root."""

    def __init__(
        self,
        study_dir: Path,
        output_relative_path: Path = Path(".runtime/telemetry/traces.jsonl"),
    ) -> None:
        root = study_dir.resolve()
        if output_relative_path.is_absolute():
            raise ObservabilityPolicyError("trace output path must be relative")
        output = (root / output_relative_path).resolve()
        try:
            output.relative_to(root)
        except ValueError as exc:
            raise ObservabilityPolicyError(
                "trace output path must stay inside the study directory"
            ) from exc
        self.study_dir = root
        self.output_path = output

    def append_record(
        self,
        *,
        trace_id: str,
        span_id: str,
        operation: str,
        attributes: Mapping[str, Any] | None = None,
        start_time_unix_nano: int | None = None,
        end_time_unix_nano: int | None = None,
    ) -> None:
        try:
            normalized_operation = TraceOperation(operation).value
        except ValueError as exc:
            raise ObservabilityPolicyError(
                f"unsupported trace operation: {operation}"
            ) from exc
        if re.fullmatch(r"[0-9a-f]{32}", trace_id) is None:
            raise ObservabilityPolicyError("trace_id must be 32 lowercase hex characters")
        if re.fullmatch(r"[0-9a-f]{16}", span_id) is None:
            raise ObservabilityPolicyError("span_id must be 16 lowercase hex characters")
        if (
            start_time_unix_nano is not None
            and end_time_unix_nano is not None
            and end_time_unix_nano < start_time_unix_nano
        ):
            raise ObservabilityPolicyError("span end time cannot precede start time")

        record = {
            "trace_id": trace_id,
            "span_id": span_id,
            "operation": normalized_operation,
            "attributes": sanitize_trace_attributes(attributes),
            "start_time_unix_nano": start_time_unix_nano,
            "end_time_unix_nano": end_time_unix_nano,
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("a", encoding="utf-8") as trace_file:
            trace_file.write(
                json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            )


def build_local_otel_exporter(sink: LocalJsonlTraceSink) -> object:
    """Build an SDK SpanExporter without importing OpenTelemetry at module load."""

    try:
        from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
    except ImportError as exc:
        raise ObservabilityDependencyError(
            "OpenTelemetry SDK is not installed; install the 'agents' extra"
        ) from exc

    class _RedactingJsonlSpanExporter(SpanExporter):
        def export(self, spans: Sequence[Any]) -> Any:
            try:
                for span in spans:
                    context = span.get_span_context()
                    sink.append_record(
                        trace_id=f"{context.trace_id:032x}",
                        span_id=f"{context.span_id:016x}",
                        operation=span.name,
                        attributes=span.attributes,
                        start_time_unix_nano=span.start_time,
                        end_time_unix_nano=span.end_time,
                    )
            except (OSError, ObservabilityPolicyError, TypeError, ValueError):
                return SpanExportResult.FAILURE
            return SpanExportResult.SUCCESS

        def shutdown(self) -> None:
            return None

    return _RedactingJsonlSpanExporter()


def configure_local_otel_provider(
    *,
    study_dir: Path,
    service_name: str = "clinical-workflow",
    output_relative_path: Path = Path(".runtime/telemetry/traces.jsonl"),
) -> object:
    """Return a local TracerProvider with one redacting JSONL exporter."""

    try:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    except ImportError as exc:
        raise ObservabilityDependencyError(
            "OpenTelemetry SDK is not installed; install the 'agents' extra"
        ) from exc
    normalized_service_name = service_name.strip()
    if not normalized_service_name or _looks_sensitive(normalized_service_name):
        raise ObservabilityPolicyError("service_name is empty or sensitive")

    sink = LocalJsonlTraceSink(
        study_dir=study_dir,
        output_relative_path=output_relative_path,
    )
    provider = TracerProvider(
        resource=Resource.create({"service.name": normalized_service_name})
    )
    provider.add_span_processor(SimpleSpanProcessor(build_local_otel_exporter(sink)))
    return provider
