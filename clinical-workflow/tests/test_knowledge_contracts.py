"""Contract, drift, negative, security, and compatibility tests for knowledge."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from src.knowledge.compatibility import (
    ContractCompatibilityError,
    assert_contract_compatible,
    is_version_compatible,
    parse_semver,
    schema_bundle_sha256,
    sha256_bytes,
    sha256_canonical_json,
    verify_sha256,
)
from src.knowledge.models import (
    CompatibilityRange,
    ApprovalStatus,
    CapabilityId,
    ContentStatus,
    ExecutionContext,
    FigureRecord,
    KnowledgeItem,
    RuntimeManifest,
    PdfStatus,
    SourceRecord,
    StudyDecision,
    WorkflowStage,
    WorkflowPlaybook,
    is_approval_status_transition_allowed,
    is_content_status_transition_allowed,
    is_pdf_status_transition_allowed,
)
from src.runtime.pipeline_contract import CapabilityName, PipelineStage


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "contracts"
SCHEMAS = ROOT / "schemas" / "knowledge"

CONTRACTS = (
    ("knowledge/knowledge_item.json", "knowledge-item.schema.json", KnowledgeItem),
    ("knowledge/workflow_playbook.json", "workflow-playbook.schema.json", WorkflowPlaybook),
    ("knowledge/source_record.json", "source.schema.json", SourceRecord),
    ("knowledge/figure_record.json", "figure.schema.json", FigureRecord),
    ("study/runtime_manifest.json", "runtime-manifest.schema.json", RuntimeManifest),
    ("study/execution_context.json", "execution-context.schema.json", ExecutionContext),
    ("study/study_decision.json", "study-decision.schema.json", StudyDecision),
)


def load_fixture(relative_path: str) -> dict[str, object]:
    return json.loads((FIXTURES / relative_path).read_text(encoding="utf-8"))


def load_schema(filename: str) -> dict[str, object]:
    return json.loads((SCHEMAS / filename).read_text(encoding="utf-8"))


def test_knowledge_and_pipeline_stage_enums_do_not_drift() -> None:
    assert [stage.value for stage in WorkflowStage] == [stage.value for stage in PipelineStage]
    assert [capability.value for capability in CapabilityId] == [
        capability.value for capability in CapabilityName
    ]


def test_cross_boundary_contracts_reject_unknown_capability() -> None:
    playbook = load_fixture("knowledge/workflow_playbook.json")
    playbook["capability_hints"] = ["unknown_capability"]
    with pytest.raises(ValidationError):
        WorkflowPlaybook.model_validate(playbook)

    manifest = load_fixture("study/runtime_manifest.json")
    manifest["toolchain"]["capabilities"] = ["unknown_capability"]
    with pytest.raises(ValidationError):
        RuntimeManifest.model_validate(manifest)


def test_shared_contract_bundle_is_complete_and_hash_locked() -> None:
    bundle = json.loads((ROOT / "schemas" / "contract-bundle.json").read_text(encoding="utf-8"))
    schema_paths = bundle["schemas"]
    assert schema_paths == sorted(schema_paths)
    assert bundle["bundle_version"] == "1.1.0"
    assert bundle["hash_algorithm"] == "sha256-canonical-json-v1"

    actual_paths = sorted(
        path.relative_to(ROOT / "schemas").as_posix()
        for path in (ROOT / "schemas").rglob("*.json")
        if path.name != "contract-bundle.json"
    )
    assert schema_paths == actual_paths
    assert schema_bundle_sha256(ROOT / "schemas", schema_paths) == bundle["bundle_sha256"]


@pytest.mark.parametrize(("fixture", "schema_file", "model"), CONTRACTS)
def test_positive_fixtures_match_models_and_json_schema(
    fixture: str,
    schema_file: str,
    model: type,
) -> None:
    data = load_fixture(fixture)
    validated = model.model_validate(data)

    Draft202012Validator(load_schema(schema_file)).validate(data)
    assert validated.model_dump(mode="json") == data


@pytest.mark.parametrize(("_fixture", "schema_file", "model"), CONTRACTS)
def test_checked_in_json_schema_has_no_model_drift(
    _fixture: str,
    schema_file: str,
    model: type,
) -> None:
    actual = load_schema(schema_file)
    schema_id = actual.pop("$id")
    schema_dialect = actual.pop("$schema")

    assert schema_dialect == "https://json-schema.org/draft/2020-12/schema"
    assert schema_id.startswith("https://clinical-workflow/schemas/knowledge/")
    assert actual == model.model_json_schema(mode="validation")


@pytest.mark.parametrize(("fixture", "_schema_file", "model"), CONTRACTS)
def test_every_contract_rejects_undeclared_fields(
    fixture: str,
    _schema_file: str,
    model: type,
) -> None:
    data = load_fixture(fixture)
    data["undeclared_field"] = "must fail"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        model.model_validate(data)


@pytest.mark.parametrize("field", ["command", "script_path", "next_stage", "skip_stage"])
def test_playbook_rejects_execution_control_fields_at_root(field: str) -> None:
    data = load_fixture("knowledge/workflow_playbook.json")
    data[field] = "dangerous"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WorkflowPlaybook.model_validate(data)
    assert list(Draft202012Validator(load_schema("workflow-playbook.schema.json")).iter_errors(data))


@pytest.mark.parametrize("field", ["command", "script_path", "next_stage", "skip_stage"])
def test_playbook_rejects_execution_control_fields_inside_steps(field: str) -> None:
    data = load_fixture("knowledge/workflow_playbook.json")
    steps = deepcopy(data["steps"])
    steps[0][field] = "dangerous"
    data["steps"] = steps

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        WorkflowPlaybook.model_validate(data)
    assert list(Draft202012Validator(load_schema("workflow-playbook.schema.json")).iter_errors(data))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("content_status", "published"),
        ("approval_status", "trusted"),
        ("workflow_stages", ["custom_stage"]),
    ],
)
def test_knowledge_item_rejects_unknown_state_or_stage(field: str, value: object) -> None:
    data = load_fixture("knowledge/knowledge_item.json")
    data[field] = value
    with pytest.raises(ValidationError):
        KnowledgeItem.model_validate(data)


def test_manual_approval_status_change_cannot_bypass_receipt_evidence() -> None:
    data = load_fixture("knowledge/knowledge_item.json")
    data.pop("approval_receipt_id")
    with pytest.raises(ValidationError, match="approved records require approval_receipt_id"):
        KnowledgeItem.model_validate(data)


def test_governance_and_pdf_state_transitions_are_explicit_and_linear() -> None:
    assert is_content_status_transition_allowed(ContentStatus.DRAFT, ContentStatus.REVIEWED)
    assert not is_content_status_transition_allowed(ContentStatus.DRAFT, ContentStatus.VERIFIED)
    assert is_approval_status_transition_allowed(
        ApprovalStatus.PROPOSED, ApprovalStatus.APPROVED
    )
    assert not is_approval_status_transition_allowed(
        ApprovalStatus.APPROVED, ApprovalStatus.PROPOSED
    )
    assert is_pdf_status_transition_allowed(PdfStatus.QUARANTINE, PdfStatus.INTEGRITY_VERIFIED)
    assert not is_pdf_status_transition_allowed(PdfStatus.QUARANTINE, PdfStatus.PARSED)


def test_production_eligibility_requires_both_states_rights_compatibility_and_freshness() -> None:
    approved = KnowledgeItem.model_validate(load_fixture("knowledge/knowledge_item.json"))
    decision = approved.production_eligibility(
        contract_version="1.5.0", as_of=date(2026, 7, 13)
    )
    assert decision.eligible is True
    assert decision.reasons == ()

    cases = (
        ("content_status", "reviewed", "content_not_verified"),
        ("approval_status", "rejected", "use_not_approved"),
        ("rights_status", "unknown", "rights_not_cleared_for_use"),
        ("storage_mode", "unknown", "storage_mode_unknown"),
        ("review_due", "2020-01-01", "review_overdue"),
    )
    for field, value, expected_reason in cases:
        data = load_fixture("knowledge/knowledge_item.json")
        data[field] = value
        if field == "approval_status":
            data["approval_receipt_id"] = None
        item = KnowledgeItem.model_validate(data)
        assert expected_reason in item.production_eligibility(
            contract_version="1.5.0", as_of=date(2026, 7, 13)
        ).reasons

    assert "contract_incompatible" in approved.production_eligibility(
        contract_version="2.0.0", as_of=date(2026, 7, 13)
    ).reasons


def test_source_and_figure_preserve_page_bbox_hash_rights_and_derivation() -> None:
    source = SourceRecord.model_validate(load_fixture("knowledge/source_record.json"))
    figure = FigureRecord.model_validate(load_fixture("knowledge/figure_record.json"))

    assert source.locators[0].physical_page == 4
    assert source.locators[0].printed_page == "2"
    assert source.locators[0].bbox == (10.0, 20.0, 100.0, 140.0)
    assert source.derivations[0].input_sha256 == source.original_sha256
    assert figure.locator.physical_page == 4
    assert figure.derivation.output_sha256 == figure.figure_sha256


def test_source_fails_closed_until_pdf_is_citation_ready() -> None:
    data = load_fixture("knowledge/source_record.json")
    data["pdf_status"] = "human_qa"
    source = SourceRecord.model_validate(data)

    reasons = source.production_eligibility(
        contract_version="1.0.0", as_of=date(2026, 7, 13)
    ).reasons
    assert "pdf_not_citation_ready" in reasons


@pytest.mark.parametrize(
    ("fixture", "model", "bad_id"),
    [
        ("knowledge/knowledge_item.json", KnowledgeItem, "source-wrong-prefix"),
        ("knowledge/workflow_playbook.json", WorkflowPlaybook, "kr-wrong-prefix"),
        ("knowledge/source_record.json", SourceRecord, "fig-wrong-prefix"),
        ("knowledge/figure_record.json", FigureRecord, "src-wrong-prefix"),
    ],
)
def test_core_knowledge_types_enforce_stable_id_namespaces(
    fixture: str, model: type, bad_id: str
) -> None:
    data = load_fixture(fixture)
    data["id"] = bad_id
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_invalid_bbox_and_incomplete_pdf_metadata_are_rejected() -> None:
    source = load_fixture("knowledge/source_record.json")
    source["locators"][0]["bbox"] = [10.0, 20.0, 5.0, 140.0]
    with pytest.raises(ValidationError, match="bbox must be non-negative"):
        SourceRecord.model_validate(source)

    source = load_fixture("knowledge/source_record.json")
    source.pop("pdf_status")
    with pytest.raises(ValidationError):
        SourceRecord.model_validate(source)


def test_execution_context_keeps_rule_layers_conflicts_missing_and_provenance() -> None:
    context = ExecutionContext.model_validate(load_fixture("study/execution_context.json"))
    assert context.workflow_rules[0].layer.value == "workflow"
    assert context.domain_rules[0].layer.value == "domain"
    assert context.study_rules[0].layer.value == "study"
    assert context.provenance[0].snapshot_id == "snapshot-workflow-001"


def test_execution_context_cannot_be_executable_with_unresolved_blockers() -> None:
    data = load_fixture("study/execution_context.json")
    data["conflicts"] = [
        {
            "conflict_id": "conflict-001",
            "rule_ids": ["rule-domain-001", "rule-study-001"],
            "reason": "The rules disagree.",
            "resolution": None,
        }
    ]
    data["missing_requirements"] = [
        {
            "requirement_id": "requirement-crf",
            "description": "CRF metadata is missing.",
            "blocking": True,
        }
    ]
    with pytest.raises(ValidationError, match="unresolved blockers"):
        ExecutionContext.model_validate(data)

    data["executable"] = False
    context = ExecutionContext.model_validate(data)
    assert context.executable is False
    assert context.conflicts and context.missing_requirements


def test_execution_context_rejects_rule_in_wrong_layer() -> None:
    data = load_fixture("study/execution_context.json")
    data["workflow_rules"][0]["layer"] = "study"
    with pytest.raises(ValidationError, match="wrong rule layer"):
        ExecutionContext.model_validate(data)


def test_runtime_manifest_locks_exact_versions_hashes_and_fail_closed_policies() -> None:
    manifest = RuntimeManifest.model_validate(load_fixture("study/runtime_manifest.json"))
    assert manifest.policies.live_upgrade == "forbidden"
    assert manifest.pipeline_contract.version == "1.0.0"

    data = load_fixture("study/runtime_manifest.json")
    data["policies"]["fallback"] = "latest_available"
    with pytest.raises(ValidationError):
        RuntimeManifest.model_validate(data)


def test_semver_precedence_and_half_open_compatibility() -> None:
    supported = CompatibilityRange(minimum="1.0.0", maximum_exclusive="2.0.0")
    assert parse_semver("1.0.0-alpha") < parse_semver("1.0.0")
    assert is_version_compatible("1.0.0", supported)
    assert is_version_compatible("1.99.0", supported)
    assert not is_version_compatible("2.0.0", supported)
    assert not is_version_compatible("latest", supported)
    with pytest.raises((ValidationError, ContractCompatibilityError)):
        CompatibilityRange(minimum="2.0.0", maximum_exclusive="1.0.0")


def test_hash_checks_are_deterministic_and_fail_closed() -> None:
    payload = b"contract"
    expected = sha256_bytes(payload)
    assert verify_sha256(payload, expected)
    assert not verify_sha256(payload, "not-a-hash")
    assert sha256_canonical_json({"b": 2, "a": 1}) == sha256_canonical_json(
        {"a": 1, "b": 2}
    )

    supported = CompatibilityRange(minimum="1.0.0", maximum_exclusive="2.0.0")
    assert_contract_compatible(
        version="1.0.0", supported=supported, payload=payload, expected_sha256=expected
    )
    with pytest.raises(ContractCompatibilityError, match="SHA-256"):
        assert_contract_compatible(
            version="1.0.0", supported=supported, payload=payload, expected_sha256="0" * 64
        )
    with pytest.raises(ContractCompatibilityError, match="outside the supported range"):
        assert_contract_compatible(
            version="2.0.0", supported=supported, payload=payload, expected_sha256=expected
        )
