"""P8 Application API draft contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "schemas" / "application" / "openapi.yaml"
PIPELINE_SCHEMA = ROOT / "schemas" / "pipeline" / "pipeline-contract.schema.json"
CONTRACT_BUNDLE = ROOT / "schemas" / "contract-bundle.json"

EXPECTED_PATHS = {
    "/api/v1/studies",
    "/api/v1/studies/{study_id}/status",
    "/api/v1/studies/{study_id}/poc-state",
    "/api/v1/studies/{study_id}/poc-runs",
    "/api/v1/studies/{study_id}/poc-runs/{run_id}",
    "/api/v1/studies/{study_id}/poc-runs/{run_id}/resume",
    "/api/v1/studies/{study_id}/runs",
    "/api/v1/studies/{study_id}/runs/{run_id}",
    "/api/v1/studies/{study_id}/runs/{run_id}/resume",
    "/api/v1/studies/{study_id}/events",
    "/api/v1/studies/{study_id}/artifacts",
    "/api/v1/studies/{study_id}/artifacts/{artifact_id}",
    "/api/v1/studies/{study_id}/reviews",
    "/api/v1/studies/{study_id}/reviews/{review_id}/decisions",
    "/api/v1/studies/{study_id}/context",
    "/api/v1/studies/{study_id}/provenance",
    "/api/v1/studies/{study_id}/audit",
}

POST_OPERATIONS = {
    ("post", "/api/v1/studies"),
    ("post", "/api/v1/studies/{study_id}/runs"),
    ("post", "/api/v1/studies/{study_id}/runs/{run_id}/resume"),
    ("post", "/api/v1/studies/{study_id}/reviews/{review_id}/decisions"),
}


def _load_openapi() -> dict[str, Any]:
    return yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))


def _operation(spec: dict[str, Any], method: str, path: str) -> dict[str, Any]:
    return spec["paths"][path][method]


def _parameter_refs(operation: dict[str, Any]) -> set[str]:
    return {parameter.get("$ref", "") for parameter in operation.get("parameters", [])}


def test_p8_application_openapi_is_draft_and_does_not_upgrade_released_bundle() -> None:
    spec = _load_openapi()
    bundle = json.loads(CONTRACT_BUNDLE.read_text(encoding="utf-8"))

    assert spec["openapi"] == "3.1.0"
    assert spec["x-contract-status"] == "draft"
    assert spec["x-contract-owner"] == "workflow_engine"
    assert spec["x-released-contract-bundle"] is False

    assert bundle["bundle_version"] == "1.1.0"
    assert "application/openapi.yaml" not in bundle["schemas"]


def test_p8_application_api_endpoint_surface_is_explicit_and_minimal() -> None:
    spec = _load_openapi()

    assert set(spec["paths"]) == EXPECTED_PATHS
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            assert operation["operationId"]
            assert operation["x-authority"]
            assert operation["x-writes"] == "none" or method == "post", path


def test_p8_application_post_operations_are_idempotent_and_cannot_promote_or_call_tools() -> None:
    spec = _load_openapi()

    for method, path in POST_OPERATIONS:
        operation = _operation(spec, method, path)
        assert "#/components/parameters/IdempotencyKey" in _parameter_refs(operation)
        forbidden = set(operation.get("x-forbidden-actions", []))
        assert forbidden
        assert "promote_artifact" in forbidden
        assert {"call_core_tool", "direct_core_tool_call"}.intersection(forbidden) or path.endswith("/decisions")

    decision_op = _operation(spec, "post", "/api/v1/studies/{study_id}/reviews/{review_id}/decisions")
    assert decision_op["x-writes"] == "decision_receipt_only"
    assert "write_confirmation" in set(decision_op["x-forbidden-actions"])
    assert "mutate_review_packet" in set(decision_op["x-forbidden-actions"])


def test_p8_application_stage_order_matches_engine_pipeline_contract() -> None:
    spec = _load_openapi()
    pipeline = json.loads(PIPELINE_SCHEMA.read_text(encoding="utf-8"))

    application_stage_order = spec["components"]["schemas"]["StudyStatusResponse"]["properties"]["stage_order"][
        "prefixItems"
    ]
    assert [item["const"] for item in application_stage_order] == pipeline["x-canonical-stage-order"]

    stage_enum = spec["components"]["schemas"]["PipelineStageId"]["enum"]
    assert stage_enum == pipeline["$defs"]["stage_id"]["enum"]


def test_p8_application_ui_contracts_map_to_existing_endpoints_and_payload_fields() -> None:
    spec = _load_openapi()
    existing = {
        f"{method.upper()} {path}"
        for path, methods in spec["paths"].items()
        for method in methods
    }

    ui_contracts = spec["x-ui-contracts"]
    assert set(ui_contracts) == {f"UI-0{index}" for index in range(1, 8)}
    for contract in ui_contracts.values():
        assert set(contract["endpoints"]).issubset(existing)
        assert contract["required_payload"]

    poc_contracts = spec["x-poc-workbench-contracts"]
    assert set(poc_contracts) == {f"UI-0{index}" for index in range(1, 8)}
    for contract in poc_contracts.values():
        assert set(contract["endpoints"]).issubset(existing)
        assert contract["required_payload"]


def test_p8_application_components_are_valid_json_schemas() -> None:
    spec = _load_openapi()

    for name, schema in spec["components"]["schemas"].items():
        Draft202012Validator.check_schema(schema), name


def test_p8_application_public_contract_does_not_expose_absolute_paths() -> None:
    spec_text = OPENAPI_PATH.read_text(encoding="utf-8")
    assert "absolute_path" not in spec_text
    assert "executable_path" not in spec_text

    registered = _load_openapi()["components"]["schemas"]["RegisteredFileRef"]
    relative_path = registered["properties"]["relative_path"]
    blocked_patterns = {item["pattern"] for item in relative_path["not"]["anyOf"]}
    assert "(^|/)\\.\\.(/|$)" in blocked_patterns
    assert "^[A-Za-z]:" in blocked_patterns
    assert "^/" in blocked_patterns
    assert "\\\\" in blocked_patterns
