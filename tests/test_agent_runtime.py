from src.runtime.agent_loop import AgentRuntime, _load_mcp_tools


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
