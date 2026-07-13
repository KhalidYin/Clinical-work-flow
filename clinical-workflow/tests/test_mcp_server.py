import pytest

from src.knowledge.models import TEAEWindowRule
from src.mcp_tools.adam_spec_builder import generate_adam_spec
from src.mcp_tools.server import (
    AUXILIARY_TOOL_NAMES,
    CORE_TOOL_NAMES,
    TOOLS,
    handle_tool_call,
)


def _teae_rule() -> dict:
    return {
        "rule_type": "teae_window",
        "target_dataset": "ADAE",
        "target_variable": "TRTEMFL",
        "event_start_date": "ADAE.ASTDT",
        "treatment_start_date": "ADSL.TRTSDT",
        "treatment_end_date": "ADSL.TRTEDT",
        "start_offset_days": 0,
        "end_offset_days": 30,
        "lower_bound_inclusive": True,
        "upper_bound_inclusive": True,
        "incomplete_event_date_policy": "review_required",
        "missing_treatment_date_policy": "review_required",
        "multiple_treatment_period_policy": "review_required",
        "pre_treatment_worsening_policy": "include_if_worsened",
    }


def test_tool_manifest_matches_core_and_auxiliary_groups():
    tool_names = [tool["name"] for tool in TOOLS]

    assert tool_names == [*AUXILIARY_TOOL_NAMES[:1], *CORE_TOOL_NAMES, *AUXILIARY_TOOL_NAMES[1:]]


def test_adam_tool_manifest_declares_structured_teae_inputs():
    tool = next(item for item in TOOLS if item["name"] == "adam_spec_build")

    assert "teae_rule" in tool["parameters"]
    assert "applied_rule_refs" in tool["parameters"]


def test_every_manifest_tool_has_handler():
    for tool in TOOLS:
        if tool["name"] == "edc_import":
            result = handle_tool_call(tool["name"], {"manifest_path": "default"})
            assert result["manifest"]["domain_count"] > 0
            continue

        if tool["name"] == "sdtm_spec_build":
            result = handle_tool_call(tool["name"], {"domain_code": "DM"})
        elif tool["name"] == "adam_spec_build":
            result = handle_tool_call(tool["name"], {"dataset_name": "ADSL"})
        elif tool["name"] == "tfl_shells_list":
            result = handle_tool_call(tool["name"], {})
        elif tool["name"] == "cdisc_validate":
            result = handle_tool_call(
                tool["name"],
                {"type": "sdtm", "domain_or_dataset": "AE", "data": {}},
            )
        elif tool["name"] == "define_xml_build":
            result = handle_tool_call(
                tool["name"],
                {"dataset_name": "ADSL", "variables": [{"name": "USUBJID"}]},
            )
        elif tool["name"] == "triage_p21":
            result = handle_tool_call(tool["name"], {"findings": []})
        else:
            # CTGov helpers hit network, so handler existence is covered by unknown-tool test.
            continue

        assert isinstance(result, dict)


def test_unknown_tool_reports_available_handlers():
    with pytest.raises(ValueError, match="Unknown tool"):
        handle_tool_call("missing_tool", {})


def test_adae_requires_structured_teae_rule_and_rule_references():
    with pytest.raises(ValueError, match="teae_rule"):
        handle_tool_call("adam_spec_build", {"dataset_name": "ADAE"})

    with pytest.raises(ValueError, match="applied_rule_refs"):
        handle_tool_call(
            "adam_spec_build",
            {"dataset_name": "ADAE", "teae_rule": _teae_rule()},
        )


def test_structured_teae_rule_is_projected_deterministically_without_statement_parsing():
    arguments = {
        "dataset_name": "ADAE",
        "teae_rule": _teae_rule(),
        "applied_rule_refs": [
            "kr-teae-safety-window@1.0.0",
            "study-decision-synth-onco-001-teae@1.0.0",
        ],
    }

    first = handle_tool_call("adam_spec_build", arguments)
    second = handle_tool_call("adam_spec_build", arguments)
    trtemfl = next(item for item in first["variables"] if item["name"] == "TRTEMFL")

    assert first == second
    assert trtemfl["derivation"] == (
        "Y if ADAE.ASTDT >= ADSL.TRTSDT and "
        "ADAE.ASTDT <= ADSL.TRTEDT + 30 days; else N. "
        "Incomplete event date: review required. "
        "Missing treatment date: review required. "
        "Multiple treatment periods: review required. "
        "Pre-treatment worsening: include if worsened."
    )
    assert first["applied_rule_refs"] == arguments["applied_rule_refs"]
    assert first["study_rule_inputs"] == {"teae_window": _teae_rule()}


def test_adam_builder_accepts_validated_teae_rule_model():
    rule = TEAEWindowRule.model_validate(_teae_rule())

    result = generate_adam_spec(
        "ADAE",
        teae_rule=rule,
        applied_rule_refs=("study-decision-synth-onco-001-teae@1.0.0",),
    )

    assert result["study_rule_inputs"] == {"teae_window": _teae_rule()}


def test_adae_rejects_natural_language_statement_as_an_execution_parameter():
    invalid_rule = {**_teae_rule(), "statement": "Use a different safety window."}

    with pytest.raises(ValueError, match="statement"):
        generate_adam_spec(
            "ADAE",
            teae_rule=invalid_rule,
            applied_rule_refs=("study-decision-synth-onco-001-teae@1.0.0",),
        )


@pytest.mark.parametrize(
    ("dataset_name", "extra_arguments"),
    [
        ("ADSL", {"teae_rule": _teae_rule()}),
        ("ADTTE", {"applied_rule_refs": ["kr-teae-safety-window@1.0.0"]}),
    ],
)
def test_non_adae_dataset_rejects_teae_inputs(dataset_name, extra_arguments):
    with pytest.raises(ValueError, match="only valid for ADAE"):
        handle_tool_call(
            "adam_spec_build",
            {"dataset_name": dataset_name, **extra_arguments},
        )


@pytest.mark.parametrize("dataset_name", ["ADSL", "ADTTE"])
def test_non_adae_datasets_preserve_existing_builder_behavior(dataset_name):
    result = handle_tool_call("adam_spec_build", {"dataset_name": dataset_name})

    assert result["dataset"] == dataset_name
    assert result["variables"]
    assert result["applied_rule_refs"] == []
    assert result["study_rule_inputs"] == {}
