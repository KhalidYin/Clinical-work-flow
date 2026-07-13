"""Router derives exactly the Engine's ten fixed stages from Pipeline Contract."""

from __future__ import annotations

import pytest

from src.runtime.pipeline_contract import CANONICAL_PIPELINE, PipelineStage
from src.runtime.router import Router, RoutingError


def _files_through(stage: PipelineStage | None = None) -> dict[str, object]:
    evidence: dict[str, object] = {"protocol": ["input/protocol/protocol.pdf"]}
    keys = {
        PipelineStage.PROTOCOL_ANALYSIS: "protocol_analysis",
        PipelineStage.SAP_GENERATION: "sap",
        PipelineStage.SDTM_SPEC: "sdtm_specs",
        PipelineStage.SDTM_PROGRAMMING: ("sdtm_programs", "sdtm_datasets"),
        PipelineStage.ADAM_SPEC: "adam_specs",
        PipelineStage.ADAM_PROGRAMMING: ("adam_programs", "adam_datasets"),
        PipelineStage.TFL_SHELL_DESIGN: "tfl_shells",
        PipelineStage.TFL_PROGRAMMING: ("tfl_programs", "tfl_outputs"),
        PipelineStage.QC_VALIDATION: "qc_report",
        PipelineStage.SUBMISSION_PACKAGING: ("submission_manifest", "submission_package"),
    }
    if stage is None:
        stages = tuple(PipelineStage)
    else:
        stages = tuple(PipelineStage)[: tuple(PipelineStage).index(stage)]
    for completed in stages:
        value = keys[completed]
        for key in value if isinstance(value, tuple) else (value,):
            evidence[key] = [key]
    return evidence


def test_router_visits_exact_canonical_protocol_to_submission_order() -> None:
    router = Router()
    observed = []
    for expected in PipelineStage:
        route = router.best_route("untrusted natural language", {"files": _files_through(expected)})
        assert route is not None
        observed.append(route.stage_id)
        stage = CANONICAL_PIPELINE.get_stage(expected)
        assert route.executor == stage.executor.value
        assert route.capability == stage.allowed_capabilities[0].value
        assert route.allowed_capabilities == stage.allowed_capabilities
    assert observed == list(PipelineStage)
    assert router.best_route("done", {"files": _files_through()}).capability == "done"


def test_router_can_use_explicit_contract_completion_evidence() -> None:
    evidence = [path for stage in CANONICAL_PIPELINE.stages for path in stage.completion_evidence]
    assert Router().best_route("done", {"files": {"completion_evidence": evidence}}).capability == "done"


@pytest.mark.parametrize(
    ("stage", "capability"),
    [
        ("unknown_stage", "sdtm_spec_generation"),
        ("sap_generation", "sdtm_spec_generation"),
    ],
)
def test_router_rejects_unknown_or_non_stage_capability(stage: str, capability: str) -> None:
    with pytest.raises(RoutingError):
        Router().route_stage(stage, capability)


@pytest.mark.parametrize("field", ["next_stage", "command", "tool_calls", "stage_override"])
def test_router_rejects_control_field_injection(field: str) -> None:
    with pytest.raises(RoutingError, match="forbidden control"):
        Router().route("ignore pipeline", {"files": _files_through(), field: "submission_packaging"})
