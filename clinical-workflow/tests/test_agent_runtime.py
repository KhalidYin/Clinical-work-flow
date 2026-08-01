import asyncio
import subprocess
from types import SimpleNamespace

import pytest

from src.knowledge.models import ResolvedRule, RuleLayer, TEAEWindowRule
from src.runtime.agent_loop import (
    AgentAction,
    AgentRuntime,
    _load_mcp_tools,
    build_runtime_context_resolver,
)
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


def test_runtime_git_commit_is_scoped_to_current_study(tmp_path):
    repo = tmp_path / "platform"
    study = repo / "clinical-studies" / "STUDY-A"
    other_study = repo / "clinical-studies" / "STUDY-B"
    engine = repo / "clinical-workflow"
    wiki = repo / "clinical-llm-wiki"
    for directory in (study, other_study, engine, wiki):
        directory.mkdir(parents=True)
        (directory / "tracked.txt").write_text("baseline\n", encoding="utf-8")

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )

    git("init")
    git("config", "user.name", "Clinical Runtime Test")
    git("config", "user.email", "runtime-test@example.invalid")
    runtime = AgentRuntime(project_dir=study, git_auto_commit=True)
    git("add", "-A")
    git("commit", "-m", "baseline")

    (study / "tracked.txt").write_text("study change\n", encoding="utf-8")
    (study / "new.txt").write_text("new Study evidence\n", encoding="utf-8")
    (other_study / "tracked.txt").write_text("other Study change\n", encoding="utf-8")
    (engine / "tracked.txt").write_text("engine change\n", encoding="utf-8")
    (wiki / "tracked.txt").write_text("wiki change\n", encoding="utf-8")
    git("add", "clinical-llm-wiki/tracked.txt")

    runtime._git_commit(
        AgentAction(action_type="call_tool", description="Generate Study artifact"),
        {"status": "success"},
    )

    committed_paths = set(
        git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD")
        .stdout.strip()
        .splitlines()
    )
    assert committed_paths == {
        "clinical-studies/STUDY-A/new.txt",
        "clinical-studies/STUDY-A/tracked.txt",
    }
    assert git("status", "--porcelain", "--", "clinical-studies/STUDY-A").stdout == ""
    assert git("diff", "--cached", "--name-only").stdout.strip() == (
        "clinical-llm-wiki/tracked.txt"
    )
    remaining = git("status", "--porcelain").stdout
    assert "clinical-workflow/tracked.txt" in remaining
    assert "clinical-studies/STUDY-B/tracked.txt" in remaining


@pytest.mark.parametrize(
    "url",
    (
        "http://example.com:8788",
        "http://127.0.0.1:8788/api",
        "http://user@127.0.0.1:8788",
        "file:///tmp/wiki",
    ),
)
def test_runtime_context_factory_rejects_non_loopback_or_non_origin_urls(url):
    with pytest.raises(ValueError, match="loopback"):
        build_runtime_context_resolver(url)


def test_runtime_context_factory_uses_engine_bundle_lock():
    bridge = build_runtime_context_resolver("http://localhost:8788")
    resolver = bridge._knowledge_resolver

    assert resolver.bundle_version == "1.1.0"
    assert resolver.bundle_sha256 == (
        "72e5fed6cd37fdb82888e3a7b2310fe44fa0953a30eb579688a7c580f2b33e14"
    )


def test_runtime_refuses_to_auto_commit_platform_monorepo_root(tmp_path):
    repo = tmp_path / "platform"
    for module in ("clinical-workflow", "clinical-llm-wiki", "clinical-studies"):
        path = repo / module
        path.mkdir(parents=True)
        (path / "tracked.txt").write_text("baseline\n", encoding="utf-8")

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True, text=True
        )

    git("init")
    git("config", "user.name", "Clinical Runtime Test")
    git("config", "user.email", "runtime-test@example.invalid")
    git("add", "-A")
    git("commit", "-m", "baseline")
    baseline = git("rev-parse", "HEAD").stdout.strip()
    runtime = AgentRuntime(project_dir=repo, git_auto_commit=True)
    (repo / "clinical-workflow/tracked.txt").write_text(
        "must remain uncommitted\n", encoding="utf-8"
    )

    runtime._git_commit(
        AgentAction(action_type="call_tool", description="Invalid root action"),
        {"status": "success"},
    )

    assert git("rev-parse", "HEAD").stdout.strip() == baseline
    assert "clinical-workflow/tracked.txt" in git("status", "--porcelain").stdout
