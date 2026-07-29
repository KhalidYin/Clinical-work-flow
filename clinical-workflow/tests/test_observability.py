from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.runtime.observability import (
    LocalJsonlTraceSink,
    ObservabilityDependencyError,
    ObservabilityPolicyError,
    TraceOperation,
    build_local_otel_exporter,
    hash_study_id,
    sanitize_trace_attributes,
)


def test_trace_attributes_are_allowlisted_and_redacted() -> None:
    study_hash = hash_study_id("SYNTH-E2E-001")

    sanitized = sanitize_trace_attributes(
        {
            "clinical.study_id_hash": study_hash,
            "clinical.run_id": "run-p11-001",
            "clinical.study_id": "SYNTH-E2E-001",
            "clinical.prompt": "raw clinical prompt",
            "authorization": "Bearer super-secret",
            "clinical.model.provider": "sk-live-secretvalue",
            "provider.extra": "must not expand the contract",
        }
    )

    assert sanitized == {
        "clinical.study_id_hash": study_hash,
        "clinical.run_id": "run-p11-001",
    }
    serialized = json.dumps(sanitized)
    assert "SYNTH-E2E-001" not in serialized
    assert "prompt" not in serialized
    assert "secret" not in serialized


def test_trace_sink_rejects_paths_outside_study(tmp_path: Path) -> None:
    with pytest.raises(
        ObservabilityPolicyError,
        match="must stay inside the study directory",
    ):
        LocalJsonlTraceSink(tmp_path / "study", Path("../outside.jsonl"))


def test_trace_sink_writes_only_redacted_local_jsonl(tmp_path: Path) -> None:
    study_dir = tmp_path / "study"
    sink = LocalJsonlTraceSink(study_dir)

    sink.append_record(
        trace_id="a" * 32,
        span_id="b" * 16,
        operation=TraceOperation.STAGE_VALIDATION,
        attributes={
            "clinical.study_id_hash": hash_study_id("SYNTH-E2E-001"),
            "clinical.stage_id": "sdtm_validation",
            "clinical.model.profile_id": "validator-primary",
            "clinical.prompt": "must never be stored",
            "clinical.tool.name": "deterministic-validator",
        },
        start_time_unix_nano=10,
        end_time_unix_nano=20,
    )

    assert sink.output_path.is_relative_to(study_dir.resolve())
    record = json.loads(sink.output_path.read_text(encoding="utf-8"))
    assert record["operation"] == "clinical.stage.validation"
    assert record["attributes"] == {
        "clinical.model.profile_id": "validator-primary",
        "clinical.stage_id": "sdtm_validation",
        "clinical.study_id_hash": hash_study_id("SYNTH-E2E-001"),
        "clinical.tool.name": "deterministic-validator",
    }
    assert "prompt" not in sink.output_path.read_text(encoding="utf-8")


def test_trace_sink_rejects_unregistered_operation(tmp_path: Path) -> None:
    sink = LocalJsonlTraceSink(tmp_path / "study")

    with pytest.raises(ObservabilityPolicyError, match="unsupported trace operation"):
        sink.append_record(
            trace_id="a" * 32,
            span_id="b" * 16,
            operation="provider.raw.request",
        )


def test_missing_optional_otel_dependency_has_clear_error(
    tmp_path: Path,
) -> None:
    try:
        import opentelemetry.sdk  # noqa: F401
    except ImportError:
        with pytest.raises(ObservabilityDependencyError, match="agents.*extra"):
            build_local_otel_exporter(LocalJsonlTraceSink(tmp_path / "study"))
    else:
        pytest.skip("OpenTelemetry SDK is installed in this environment")
