from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from src.knowledge.evolution import KnowledgeCandidate, KnowledgeEvolutionReceipt
from src.runtime.validation_policy import FailureDiagnosis, GateDecision
from src.runtime.workflow_run_state import WorkflowRunState


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT / "src" / "runtime" / "contracts" / "p11"
CONTRACTS = (
    ("failure-diagnosis.schema.json", FailureDiagnosis),
    ("validation-gate-decision.schema.json", GateDecision),
    ("knowledge-candidate.schema.json", KnowledgeCandidate),
    ("knowledge-evolution-receipt.schema.json", KnowledgeEvolutionReceipt),
    ("workflow-run-state.schema.json", WorkflowRunState),
)


@pytest.mark.parametrize(("filename", "model"), CONTRACTS)
def test_checked_in_p11_prerelease_schema_matches_model(
    filename: str,
    model: type,
) -> None:
    checked_in = json.loads((CONTRACT_ROOT / filename).read_text(encoding="utf-8"))
    schema_id = checked_in.pop("$id")
    dialect = checked_in.pop("$schema")

    assert dialect == "https://json-schema.org/draft/2020-12/schema"
    assert schema_id.startswith(
        "https://clinical-ai-workflow.local/schemas/prerelease/p11/"
    )
    Draft202012Validator.check_schema(checked_in)
    assert checked_in == model.model_json_schema(mode="validation")


def test_p11_prerelease_contracts_do_not_mutate_released_bundle() -> None:
    bundle = json.loads(
        (ROOT / "schemas" / "contract-bundle.json").read_text(encoding="utf-8")
    )
    assert bundle["bundle_version"] == "1.1.0"
    assert all("p11" not in path for path in bundle["schemas"])
    assert not (ROOT / "schemas" / "agent-execution").exists()
