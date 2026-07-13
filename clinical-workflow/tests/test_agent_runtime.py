import asyncio
from types import SimpleNamespace

import pytest

from src.knowledge.models import ResolvedRule, RuleLayer, TEAEWindowRule
from src.runtime.agent_loop import AgentAction, AgentRuntime, _load_mcp_tools
from src.runtime.context_resolver import RuntimeContextError
from src.runtime.pipeline_contract import PipelineStage


def _teae_rule() -> TEAEWindowRule:
    return TEAEWindowRule(
        end_offset_days=30,
        incomplete_event_date_policy="review_required",
        missing_treatment_date_policy="review_required",
        multiple_treatment_period_policy="review_required",
        pre_treatment_worsening_policy="include_if_worsened",
    )


def _study_teae_rule(rule_id: str = "rule-study-teae-window") -> ResolvedRule:
    return ResolvedRule(
        rule_id=rule_id,
        layer=RuleLayer.STUDY,
        priority=600,
        title="Approved Study TEAE window",
        statement="Display-only explanation; Runtime must not parse this text.",
        source_ids=("decision-study-teae-window",),
        source_version="1.0.0",
        source_sha256="6" * 64,
        approval_receipt_id="receipt-study-teae-window",
        structured_rule=_teae_rule(),
    )


def test_runtime_loads_server_tools(tmp_path):
    runtime = AgentRuntime(project_dir=tmp_path, git_auto_commit=False)

    _load_mcp_tools(runtime)

    assert "sdtm_spec_build" in runtime.tool_registry
    assert "triage_p21" in runtime.tool_registry
    assert "ctgov_search" in runtime.tool_registry


def test_runtime_expands_batch_sdtm_and_adam_tool_calls(tmp_path):
    runtime = AgentRuntime(project_dir=tmp_path, git_auto_commit=False)
    _load_mcp_tools(runtime)

    sdtm = runtime._call_tool(
        "sdtm_spec_build",
        {"domain_codes": ["DM", "AE"], "trial_phase": "phase_iii"},
    )
    adam = runtime._call_tool(
        "adam_spec_build",
        {
            "datasets": ["ADSL", "ADAE"],
            "trial_phase": "phase_iii",
            "dataset_rule_bindings": {
                "ADAE": {
                    "teae_rule": _teae_rule().model_dump(mode="json"),
                    "applied_rule_refs": ["rule-study-teae-window"],
                }
            },
        },
    )

    assert sdtm["status"] == "success"
    assert set(sdtm["tool_result"]) == {"DM", "AE"}
    assert adam["status"] == "success"
    assert set(adam["tool_result"]) == {"ADSL", "ADAE"}
    assert adam["applied_rule_refs"] == ["rule-study-teae-window"]


def test_runtime_projects_exactly_one_structured_study_teae_rule_to_adae():
    action = AgentAction(
        action_type="call_tool",
        description="Build ADAE",
        tool_name="adam_spec_build",
        tool_args={"datasets": ["ADSL", "ADAE"]},
        stage_id=PipelineStage.ADAM_SPEC,
    )

    AgentRuntime._project_governed_tool_args(
        action,
        SimpleNamespace(study_rules=(_study_teae_rule(),)),
    )

    binding = action.tool_args["dataset_rule_bindings"]["ADAE"]
    assert binding["teae_rule"] == _teae_rule().model_dump(mode="json")
    assert binding["applied_rule_refs"] == ["rule-study-teae-window"]


@pytest.mark.parametrize(
    "rules",
    [(), (_study_teae_rule("rule-study-teae-a"), _study_teae_rule("rule-study-teae-b"))],
)
def test_runtime_refuses_missing_or_ambiguous_structured_teae_rules(rules):
    action = AgentAction(
        action_type="call_tool",
        description="Build ADAE",
        tool_name="adam_spec_build",
        tool_args={"datasets": ["ADAE"]},
        stage_id=PipelineStage.ADAM_SPEC,
    )

    with pytest.raises(RuntimeContextError, match="exactly one"):
        AgentRuntime._project_governed_tool_args(
            action,
            SimpleNamespace(study_rules=rules),
        )


def test_runtime_reads_canonical_and_legacy_output_dirs(tmp_path):
    runtime = AgentRuntime(project_dir=tmp_path, git_auto_commit=False)
    (tmp_path / "protocol.pdf").write_text("protocol", encoding="utf-8")

    canonical = tmp_path / "output" / "sdtm" / "specs"
    legacy = tmp_path / "outputs" / "sdtm_specs"
    canonical.mkdir(parents=True)
    legacy.mkdir(parents=True)
    (canonical / "dm_spec.yaml").write_text("domain: DM", encoding="utf-8")
    (legacy / "ae_spec.yaml").write_text("domain: AE", encoding="utf-8")

    context = runtime._assess_context("generate specs")

    assert {path.name for path in context["files"]["sdtm_specs"]} == {
        "dm_spec.yaml",
        "ae_spec.yaml",
    }


def test_runtime_uses_router_for_all_ten_fixed_stages(tmp_path):
    runtime = AgentRuntime(project_dir=tmp_path, git_auto_commit=False)
    resources = [
        "ctgov_search", "sap_document_generator", "sdtm_spec_build", "sdtm_program_runner",
        "adam_spec_build", "adam_program_runner", "tfl_shells_list", "tfl_renderer",
        "qc_comparator", "submission_packager",
    ]
    runtime.register_tools({name: lambda **_: None for name in resources})
    protocol = tmp_path / "input" / "protocol" / "protocol.pdf"
    protocol.parent.mkdir(parents=True)
    protocol.write_text("protocol", encoding="utf-8")
    evidence = {
        PipelineStage.PROTOCOL_ANALYSIS: [tmp_path / "output" / "protocol" / "analysis.yaml"],
        PipelineStage.SAP_GENERATION: [tmp_path / "output" / "sap" / "sap.yaml"],
        PipelineStage.SDTM_SPEC: [tmp_path / "output" / "sdtm" / "specs" / "dm.yaml"],
        PipelineStage.SDTM_PROGRAMMING: [tmp_path / "output" / "sdtm" / "programs" / "run.sas", tmp_path / "output" / "sdtm" / "datasets" / "dm.xpt"],
        PipelineStage.ADAM_SPEC: [tmp_path / "output" / "adam" / "specs" / "adsl.yaml"],
        PipelineStage.ADAM_PROGRAMMING: [tmp_path / "output" / "adam" / "programs" / "run.sas", tmp_path / "output" / "adam" / "datasets" / "adsl.xpt"],
        PipelineStage.TFL_SHELL_DESIGN: [tmp_path / "output" / "tfl" / "shells" / "table.yaml"],
        PipelineStage.TFL_PROGRAMMING: [tmp_path / "output" / "tfl" / "programs" / "table.sas", tmp_path / "output" / "tfl" / "outputs" / "table.rtf"],
        PipelineStage.QC_VALIDATION: [tmp_path / "output" / "qc" / "qc_report.yaml"],
        PipelineStage.SUBMISSION_PACKAGING: [tmp_path / "output" / "submission" / "manifest.yaml", tmp_path / "output" / "submission" / "package" / "define.xml"],
    }
    observed = []
    for expected in PipelineStage:
        context = runtime._assess_context("generate AE outputs")
        action = asyncio.run(runtime._decide_next_action("generate AE outputs", context))
        observed.append(action.stage_id)
        AgentRuntime._authorize_action(action)
        for path in evidence[expected]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("evidence", encoding="utf-8")
    assert observed == list(PipelineStage)
    final_action = asyncio.run(runtime._decide_next_action("done", runtime._assess_context("done")))
    assert final_action.action_type == "done"


def test_runtime_waits_when_fixed_stage_has_no_registered_controlled_resource(tmp_path):
    runtime = AgentRuntime(project_dir=tmp_path, git_auto_commit=False)
    protocol = tmp_path / "input" / "protocol" / "protocol.pdf"
    protocol.parent.mkdir(parents=True)
    protocol.write_text("protocol", encoding="utf-8")
    action = asyncio.run(runtime._decide_next_action("analyze", runtime._assess_context("analyze")))
    assert action.action_type == "wait"
    assert action.stage_id is PipelineStage.PROTOCOL_ANALYSIS
