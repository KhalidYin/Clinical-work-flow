"""Contract and failure-mode tests for the generated Obsidian workflow map."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from scripts.content.generate_workflow_map import (
    OUTPUT,
    PIPELINE_SCHEMA,
    RELATION_DIRECTORY,
    STAGE_NOTES,
    VAULT,
    WorkflowMapError,
    generate_workflow_map,
    load_canonical_stage_order,
    load_relation_items,
    load_stage_notes,
)


GRAPH_FILTER = '(path:"10_MOC/Workflow-Relations" OR path:"30_Workflows/Stages")'
GRAPH_GROUPS = {
    'path:"10_MOC/Workflow-Relations"': 5011624,
    'path:"30_Workflows/Stages"': 16090392,
    'path:"20_Knowledge"': 5546571,
    'path:"40_Toolkit"': 11696546,
    'path:"50_Cases"': 14964566,
}


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


def test_stage_relation_projections_cover_governed_business_records() -> None:
    order = load_canonical_stage_order()
    notes = load_stage_notes(STAGE_NOTES, order)
    items = load_relation_items(VAULT, order)
    relation_files = sorted(RELATION_DIRECTORY.glob("*.md"))

    assert len(relation_files) == 10
    assert all(path.name != "README.md" for path in relation_files)
    assert sum(item.category == "knowledge" for item in items) == 44
    assert sum(item.category == "toolkit" for item in items) == 8
    assert sum(item.category == "case" for item in items) == 1

    for ordinal, stage_id in enumerate(order, start=1):
        relation = relation_files[ordinal - 1]
        assert relation.name.startswith(f"{ordinal:02d} ")
        text = relation.read_text(encoding="utf-8")
        note = notes[stage_id]
        assert f"[[{note.link}|{note.title}]]" in text
        for item in items:
            if stage_id in item.workflow_stages:
                assert f"[[{item.link}|{item.title}]]" in text
        if ordinal < len(order):
            next_link = relation_files[ordinal].relative_to(VAULT).with_suffix("").as_posix()
            assert f"[[{next_link}|" in text
        else:
            assert "下一阶段" not in text


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


def test_invalid_relation_stage_fails_before_replacing_outputs(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    stage_notes = vault / "30_Workflows" / "Stages"
    shutil.copytree(STAGE_NOTES, stage_notes)
    for relative_root in ("20_Knowledge", "40_Toolkit", "50_Cases"):
        shutil.copytree(VAULT / relative_root, vault / relative_root)
    card = vault / "20_Knowledge" / "Methods" / "Estimand Framework.md"
    card.write_text(
        card.read_text(encoding="utf-8").replace(
            "- protocol_analysis",
            "- invented_stage",
            1,
        ),
        encoding="utf-8",
    )
    output = vault / "10_MOC" / "Clinical-Workflow-Map.md"
    output.parent.mkdir(parents=True)
    output.write_text("last valid map\n", encoding="utf-8")

    with pytest.raises(WorkflowMapError, match="unknown stages"):
        generate_workflow_map(
            schema_path=PIPELINE_SCHEMA,
            stage_notes=stage_notes,
            output_path=output,
            vault=vault,
        )
    assert output.read_text(encoding="utf-8") == "last valid map\n"
    assert not (vault / "10_MOC" / "Workflow-Relations").exists()


def test_stable_navigation_entries_point_to_generated_map() -> None:
    for relative_path in (
        "HOME.md",
        "10_MOC/Workflow-MOC.md",
        "10_MOC/Stage-Traceability-MOC.md",
    ):
        text = (VAULT / relative_path).read_text(encoding="utf-8")
        assert "[[10_MOC/Clinical-Workflow-Map" in text

    assert "30_Workflows/Stages/" not in (VAULT / "HOME.md").read_text(
        encoding="utf-8"
    )
    assert "30_Workflows/Stages/" not in (
        VAULT / "10_MOC" / "Workflow-MOC.md"
    ).read_text(encoding="utf-8")


def test_default_global_graph_excludes_operational_noise() -> None:
    graph_path = VAULT / ".obsidian" / "graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    assert graph["search"] == GRAPH_FILTER
    assert graph["showAttachments"] is False
    assert graph["hideUnresolved"] is True
    assert graph["showOrphans"] is False
    assert graph["showArrow"] is True
    assert {
        group["query"]: group["color"]["rgb"] for group in graph["colorGroups"]
    } == GRAPH_GROUPS
