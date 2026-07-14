"""Contract and failure-mode tests for the generated Obsidian workflow map."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from scripts.content.generate_workflow_map import (
    OUTPUT,
    PIPELINE_SCHEMA,
    STAGE_NOTES,
    VAULT,
    WorkflowMapError,
    generate_workflow_map,
    load_canonical_stage_order,
    load_stage_notes,
)


def test_committed_workflow_map_matches_engine_contract_and_stage_notes() -> None:
    order = load_canonical_stage_order()
    notes = load_stage_notes(STAGE_NOTES, order)
    text = OUTPUT.read_text(encoding="utf-8")

    assert generate_workflow_map(check=True) == 10
    assert text.count(" --> ") == 9
    positions = [text.index(f"`{stage_id}`") for stage_id in order]
    assert positions == sorted(positions)
    for stage_id in order:
        note = notes[stage_id]
        assert f"[[{note.link}|{note.title}]]" in text
        assert (VAULT / f"{note.link}.md").is_file()


def test_stale_map_is_detected_without_being_rewritten(tmp_path: Path) -> None:
    output = tmp_path / "Clinical-Workflow-Map.md"
    output.write_text("existing map\n", encoding="utf-8")

    with pytest.raises(WorkflowMapError, match="stale"):
        generate_workflow_map(output_path=output, check=True)

    assert output.read_text(encoding="utf-8") == "existing map\n"


@pytest.mark.parametrize("failure", ["missing", "duplicate", "unknown"])
def test_invalid_stage_notes_fail_before_replacing_map(
    tmp_path: Path,
    failure: str,
) -> None:
    vault = tmp_path / "vault"
    stage_notes = vault / "30_Workflows" / "Stages"
    shutil.copytree(STAGE_NOTES, stage_notes)
    output = vault / "10_MOC" / "Clinical-Workflow-Map.md"
    output.parent.mkdir(parents=True)
    output.write_text("last valid map\n", encoding="utf-8")

    if failure == "missing":
        (stage_notes / "Protocol Analysis.md").unlink()
    elif failure == "duplicate":
        shutil.copy2(stage_notes / "Protocol Analysis.md", stage_notes / "Duplicate.md")
    else:
        path = stage_notes / "Protocol Analysis.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "- protocol_analysis",
                "- invented_stage",
                1,
            ),
            encoding="utf-8",
        )

    with pytest.raises(WorkflowMapError):
        generate_workflow_map(
            schema_path=PIPELINE_SCHEMA,
            stage_notes=stage_notes,
            output_path=output,
            vault=vault,
        )
    assert output.read_text(encoding="utf-8") == "last valid map\n"


def test_schema_dependency_drift_fails_closed(tmp_path: Path) -> None:
    schema = json.loads(PIPELINE_SCHEMA.read_text(encoding="utf-8"))
    schema["properties"]["stages"]["prefixItems"][1]["allOf"][1]["properties"][
        "depends_on"
    ]["const"] = []
    schema_path = tmp_path / "pipeline-contract.schema.json"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")

    with pytest.raises(WorkflowMapError, match="conflicts"):
        load_canonical_stage_order(schema_path)
