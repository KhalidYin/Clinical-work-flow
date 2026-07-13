import asyncio

from src.runtime.agent_loop import AgentRuntime, _load_mcp_tools
from src.runtime.pipeline_contract import PipelineStage


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
        {"datasets": ["ADSL", "ADAE"], "trial_phase": "phase_iii"},
    )

    assert sdtm["status"] == "success"
    assert set(sdtm["tool_result"]) == {"DM", "AE"}
    assert adam["status"] == "success"
    assert set(adam["tool_result"]) == {"ADSL", "ADAE"}


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
