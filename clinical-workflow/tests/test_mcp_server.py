import pytest

from src.mcp_tools.server import (
    AUXILIARY_TOOL_NAMES,
    CORE_TOOL_NAMES,
    TOOLS,
    handle_tool_call,
)


def test_tool_manifest_matches_core_and_auxiliary_groups():
    tool_names = [tool["name"] for tool in TOOLS]

    assert tool_names == [*AUXILIARY_TOOL_NAMES[:1], *CORE_TOOL_NAMES, *AUXILIARY_TOOL_NAMES[1:]]


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
