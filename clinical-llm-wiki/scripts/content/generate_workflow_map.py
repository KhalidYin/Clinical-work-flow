"""Generate the Obsidian workflow map from the Engine pipeline contract.

The Engine schema owns stage IDs, ordering, and dependencies.  Stage playbooks
provide human-facing Wiki destinations.  This script validates both complete
inputs before replacing the generated Markdown, so a partial contract or Vault
cannot silently become a second workflow authority.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from service.repository import RepositoryError, parse_markdown_card


WIKI_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = WIKI_ROOT.parent
VAULT = WIKI_ROOT / "vault"
PIPELINE_SCHEMA = (
    REPOSITORY_ROOT
    / "clinical-workflow"
    / "schemas"
    / "pipeline"
    / "pipeline-contract.schema.json"
)
STAGE_NOTES = VAULT / "30_Workflows" / "Stages"
OUTPUT = VAULT / "10_MOC" / "Clinical-Workflow-Map.md"
RELATION_DIRECTORY = VAULT / "10_MOC" / "Workflow-Relations"

_RELATION_ROOTS = {
    "knowledge": Path("20_Knowledge"),
    "toolkit": Path("40_Toolkit"),
    "case": Path("50_Cases"),
}
_RELATION_HEADINGS = {
    "knowledge": "领域知识",
    "toolkit": "工具与交付物",
    "case": "案例",
}

_ACRONYMS = {
    "adam": "ADaM",
    "qc": "QC",
    "sap": "SAP",
    "sdtm": "SDTM",
    "tfl": "TFL",
}


class WorkflowMapError(RuntimeError):
    """Raised when the contract or Wiki cannot produce a complete map."""


@dataclass(frozen=True, slots=True)
class StageNote:
    stage_id: str
    title: str
    link: str


@dataclass(frozen=True, slots=True)
class RelationItem:
    category: str
    title: str
    link: str
    workflow_stages: tuple[str, ...]


def _read_schema(schema_path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = schema_path.read_bytes()
        schema = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowMapError(f"cannot read pipeline schema {schema_path}: {exc}") from exc
    if not isinstance(schema, dict):
        raise WorkflowMapError("pipeline schema must be a JSON object")
    return schema, raw


def load_canonical_stage_order(schema_path: Path = PIPELINE_SCHEMA) -> tuple[str, ...]:
    """Load and cross-check the canonical linear stage sequence from Engine Schema."""
    schema, _ = _read_schema(schema_path)
    raw_order = schema.get("x-canonical-stage-order")
    if (
        not isinstance(raw_order, list)
        or not raw_order
        or not all(isinstance(item, str) and item for item in raw_order)
    ):
        raise WorkflowMapError("x-canonical-stage-order must be a non-empty string array")
    order = tuple(raw_order)
    if len(order) != len(set(order)):
        raise WorkflowMapError("x-canonical-stage-order contains duplicate stage IDs")

    stages_schema = schema.get("properties", {}).get("stages", {})
    prefix_items = stages_schema.get("prefixItems")
    if not isinstance(prefix_items, list) or len(prefix_items) != len(order):
        raise WorkflowMapError("pipeline prefixItems must match the canonical stage order")
    if stages_schema.get("minItems") != len(order) or stages_schema.get("maxItems") != len(order):
        raise WorkflowMapError("pipeline stage bounds must match the canonical stage order")

    for index, (stage_id, item) in enumerate(zip(order, prefix_items, strict=True), start=1):
        try:
            properties = item["allOf"][1]["properties"]
            ordinal = properties["ordinal"]["const"]
            prefix_stage_id = properties["stage_id"]["const"]
            dependencies = properties["depends_on"]["const"]
        except (KeyError, IndexError, TypeError) as exc:
            raise WorkflowMapError(f"invalid pipeline prefix item for {stage_id}") from exc
        expected_dependencies = [] if index == 1 else [order[index - 2]]
        if ordinal != index or prefix_stage_id != stage_id or dependencies != expected_dependencies:
            raise WorkflowMapError(
                f"pipeline prefix item {index} conflicts with canonical stage {stage_id}"
            )

    stage_enum = schema.get("$defs", {}).get("stage_id", {}).get("enum")
    if stage_enum != list(order):
        raise WorkflowMapError("stage_id enum must exactly match the canonical stage order")
    return order


def _display_name(stage_id: str) -> str:
    return " ".join(_ACRONYMS.get(part, part.capitalize()) for part in stage_id.split("_"))


def load_stage_notes(
    stage_notes: Path,
    stage_order: tuple[str, ...],
    *,
    vault: Path = VAULT,
) -> dict[str, StageNote]:
    """Match every canonical stage to exactly one Wiki Stage Playbook."""
    if not stage_notes.is_dir():
        raise WorkflowMapError(f"stage note directory does not exist: {stage_notes}")
    expected = set(stage_order)
    discovered: dict[str, StageNote] = {}
    for path in sorted(stage_notes.glob("*.md")):
        try:
            metadata, _ = parse_markdown_card(vault, path)
        except RepositoryError as exc:
            raise WorkflowMapError(f"cannot parse stage note {path}: {exc}") from exc
        raw_stages = metadata.get("workflow_stages")
        if not isinstance(raw_stages, list) or len(raw_stages) != 1:
            raise WorkflowMapError(
                f"stage note {path.name} must declare exactly one workflow_stages value"
            )
        stage_id = raw_stages[0]
        if not isinstance(stage_id, str) or stage_id not in expected:
            raise WorkflowMapError(f"stage note {path.name} declares unknown stage {stage_id!r}")
        if stage_id in discovered:
            raise WorkflowMapError(f"multiple stage notes declare {stage_id}")
        title = metadata.get("title")
        if not isinstance(title, str) or not title.strip():
            raise WorkflowMapError(f"stage note {path.name} has no title")
        try:
            link_path = path.relative_to(vault).with_suffix("").as_posix()
        except ValueError as exc:
            raise WorkflowMapError(f"stage note must stay inside the Vault: {path}") from exc
        discovered[stage_id] = StageNote(stage_id, title.strip(), link_path)

    missing = [stage_id for stage_id in stage_order if stage_id not in discovered]
    if missing:
        raise WorkflowMapError("missing stage notes: " + ", ".join(missing))
    return discovered


def load_relation_items(
    vault: Path,
    stage_order: tuple[str, ...],
) -> tuple[RelationItem, ...]:
    """Load governed business records that declare canonical workflow stages."""
    expected_stages = set(stage_order)
    items: list[RelationItem] = []
    for category, relative_root in _RELATION_ROOTS.items():
        root = vault / relative_root
        if not root.is_dir():
            raise WorkflowMapError(f"relation source directory does not exist: {root}")
        for path in sorted(root.rglob("*.md")):
            if path.name == "README.md":
                continue
            try:
                metadata, _ = parse_markdown_card(vault, path)
            except RepositoryError as exc:
                raise WorkflowMapError(f"cannot parse relation source {path}: {exc}") from exc
            raw_stages = metadata.get("workflow_stages")
            if not isinstance(raw_stages, list) or not raw_stages:
                raise WorkflowMapError(
                    f"relation source {path.name} must declare workflow_stages"
                )
            if (
                not all(isinstance(stage_id, str) for stage_id in raw_stages)
                or len(raw_stages) != len(set(raw_stages))
            ):
                raise WorkflowMapError(
                    f"relation source {path.name} has invalid workflow_stages"
                )
            unknown = [stage_id for stage_id in raw_stages if stage_id not in expected_stages]
            if unknown:
                raise WorkflowMapError(
                    f"relation source {path.name} declares unknown stages: "
                    + ", ".join(unknown)
                )
            title = metadata.get("title")
            if not isinstance(title, str) or not title.strip():
                raise WorkflowMapError(f"relation source {path.name} has no title")
            if "|" in title or "]]" in title:
                raise WorkflowMapError(
                    f"relation source {path.name} title cannot be used as a Wiki Link alias"
                )
            try:
                link = path.relative_to(vault).with_suffix("").as_posix()
            except ValueError as exc:
                raise WorkflowMapError(
                    f"relation source must stay inside the Vault: {path}"
                ) from exc
            items.append(
                RelationItem(
                    category=category,
                    title=title.strip(),
                    link=link,
                    workflow_stages=tuple(raw_stages),
                )
            )
    return tuple(sorted(items, key=lambda item: (item.category, item.title.casefold(), item.link)))


def _relation_link(ordinal: int, stage_id: str) -> str:
    return f"10_MOC/Workflow-Relations/{ordinal:02d} {_display_name(stage_id)}"


def render_stage_relation(
    *,
    ordinal: int,
    stage_id: str,
    stage_order: tuple[str, ...],
    stage_note: StageNote,
    relation_items: tuple[RelationItem, ...],
    contract_sha256: str,
) -> str:
    """Render one stage-specific graph projection without changing governed cards."""
    display_name = _display_name(stage_id)
    lines = [
        "---",
        f"id: relation-{stage_id.replace('_', '-')}",
        "type: navigation",
        f"title: {ordinal:02d} {display_name} 关系视图",
        f"stage_id: {stage_id}",
        "generated_by: scripts.content.generate_workflow_map",
        "generated_from: workflow_stages + Engine Pipeline Contract",
        f"contract_sha256: {contract_sha256}",
        "---",
        "",
        "<!-- AUTO-GENERATED STAGE RELATION: do not edit by hand. -->",
        "",
        f"# {ordinal:02d} {display_name} 关系视图",
        "",
        "> [!info] 图谱投影",
        "> 本页把受治理卡片的 `workflow_stages` 属性投影为 Obsidian Wiki Links。",
        "> 它只服务导航和图谱展示，不改变知识正文、批准状态或 Runtime Context。",
        "",
        "## 工作流主干",
        "",
        f"- Stage Playbook：[[{stage_note.link}|{stage_note.title}]]",
    ]
    if ordinal < len(stage_order):
        next_stage = stage_order[ordinal]
        lines.append(
            f"- 下一阶段：[[{_relation_link(ordinal + 1, next_stage)}|"
            f"{ordinal + 1:02d} {_display_name(next_stage)} 关系视图]]"
        )

    for category in _RELATION_ROOTS:
        matched = [
            item
            for item in relation_items
            if item.category == category and stage_id in item.workflow_stages
        ]
        lines.extend(["", f"## {_RELATION_HEADINGS[category]}（{len(matched)}）", ""])
        if not matched:
            lines.append("- 当前无已投影条目。")
            continue
        lines.extend(f"- [[{item.link}|{item.title}]]" for item in matched)

    lines.extend(
        [
            "",
            "## 导航",
            "",
            "- [[10_MOC/Clinical-Workflow-Map|返回十阶段地图]]",
            "- [[HOME|返回首页]]",
            "",
        ]
    )
    return "\n".join(lines)


def render_stage_relations(
    stage_order: tuple[str, ...],
    stage_notes: dict[str, StageNote],
    relation_items: tuple[RelationItem, ...],
    *,
    contract_sha256: str,
) -> dict[str, str]:
    """Render all canonical relation projections keyed by relative filename."""
    return {
        f"{ordinal:02d} {_display_name(stage_id)}.md": render_stage_relation(
            ordinal=ordinal,
            stage_id=stage_id,
            stage_order=stage_order,
            stage_note=stage_notes[stage_id],
            relation_items=relation_items,
            contract_sha256=contract_sha256,
        )
        for ordinal, stage_id in enumerate(stage_order, start=1)
    }


def render_workflow_map(
    stage_order: tuple[str, ...],
    stage_notes: dict[str, StageNote],
    *,
    source_sha256: str,
) -> str:
    """Render deterministic Obsidian Markdown after all inputs are validated."""
    lines = [
        "---",
        "id: moc-clinical-workflow-map",
        "type: navigation",
        "title: Clinical Workflow 十阶段地图",
        "generated_by: scripts.content.generate_workflow_map",
        "generated_from: clinical-workflow/schemas/pipeline/pipeline-contract.schema.json",
        f"source_sha256: {source_sha256}",
        "---",
        "",
        "<!-- AUTO-GENERATED: run `python -m scripts.content.generate_workflow_map`. -->",
        "",
        "# Clinical Workflow 十阶段地图",
        "",
        "> [!important] 控制权威",
        "> Engine Pipeline Contract 决定阶段 ID、固定顺序与依赖；本页只是 Obsidian 可视化投影。",
        "> 阶段的执行方法由链接的 Wiki Playbook 解释，当前 Study 决策仍保存在 Study 工作区。",
        "",
        "## 固定管线",
        "",
        "```mermaid",
        "flowchart TD",
    ]
    node_ids: list[str] = []
    for ordinal, stage_id in enumerate(stage_order, start=1):
        node_id = f"S{ordinal:02d}"
        node_ids.append(node_id)
        lines.append(
            f'    {node_id}["{ordinal}. {_display_name(stage_id)}<br/>{stage_id}"]'
        )
    for origin, destination in zip(node_ids[:-1], node_ids[1:], strict=True):
        lines.append(f"    {origin} --> {destination}")
    lines.extend(
        [
            "```",
            "",
            "## 阶段知识入口",
            "",
            "| # | Stage ID | 固定阶段 | Wiki Playbook |",
            "|---:|----------|----------|---------------|",
        ]
    )
    for ordinal, stage_id in enumerate(stage_order, start=1):
        note = stage_notes[stage_id]
        lines.append(
            f"| {ordinal} | `{stage_id}` | {_display_name(stage_id)} | "
            f"[[{note.link}|{note.title}]] |"
        )
    lines.extend(
        [
            "",
            "## 相关导航",
            "",
            "- [[10_MOC/Workflow-Relations/01 Protocol Analysis|逐阶段关系图入口]]",
            "- [[10_MOC/Workflow-MOC|十阶段工作流导航]]",
            "- [[10_MOC/Stage-Traceability-MOC|十阶段纵向追溯导航]]",
            "- [[HOME|返回首页]]",
            "",
        ]
    )
    return "\n".join(lines)


def generate_workflow_map(
    *,
    schema_path: Path = PIPELINE_SCHEMA,
    stage_notes: Path = STAGE_NOTES,
    output_path: Path = OUTPUT,
    vault: Path = VAULT,
    relation_directory: Path | None = None,
    check: bool = False,
) -> int:
    """Write or verify the workflow map and stage relation projections."""
    order = load_canonical_stage_order(schema_path)
    notes = load_stage_notes(stage_notes, order, vault=vault)
    relation_items = load_relation_items(vault, order)
    _, raw_schema = _read_schema(schema_path)
    source_sha256 = hashlib.sha256(raw_schema).hexdigest()
    expected_map = render_workflow_map(
        order,
        notes,
        source_sha256=source_sha256,
    )
    relation_directory = relation_directory or (
        vault / "10_MOC" / "Workflow-Relations"
    )
    relation_outputs = render_stage_relations(
        order,
        notes,
        relation_items,
        contract_sha256=source_sha256,
    )

    expected_outputs = {output_path: expected_map}
    expected_outputs.update(
        {relation_directory / filename: text for filename, text in relation_outputs.items()}
    )
    stale = [
        path
        for path, expected in expected_outputs.items()
        if not path.exists()
        or path.read_text(encoding="utf-8").replace("\r\n", "\n") != expected
    ]
    existing_relations = (
        set(relation_directory.glob("*.md")) if relation_directory.is_dir() else set()
    )
    expected_relations = {path for path in expected_outputs if path.parent == relation_directory}
    unexpected_relations = existing_relations - expected_relations
    if not stale and not unexpected_relations:
        return len(order)
    if check:
        affected = sorted(
            path.as_posix() for path in [*stale, *unexpected_relations]
        )
        raise WorkflowMapError("generated workflow graph is stale: " + ", ".join(affected))

    for path in unexpected_relations:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise WorkflowMapError(f"cannot inspect stale relation note {path}: {exc}") from exc
        if "<!-- AUTO-GENERATED STAGE RELATION:" not in content:
            raise WorkflowMapError(
                f"refusing to remove non-generated note from relation directory: {path}"
            )

    temporary_outputs: dict[Path, Path] = {}
    try:
        for path, expected in expected_outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.tmp")
            temporary.write_text(expected, encoding="utf-8")
            temporary_outputs[path] = temporary
        for path, temporary in temporary_outputs.items():
            temporary.replace(path)
        for path in unexpected_relations:
            path.unlink()
    except OSError as exc:
        for temporary in temporary_outputs.values():
            temporary.unlink(missing_ok=True)
        raise WorkflowMapError(f"cannot replace generated workflow graph: {exc}") from exc
    return len(order)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the generated map is stale")
    args = parser.parse_args()
    count = generate_workflow_map(check=args.check)
    action = "verified" if args.check else "generated"
    print(f"Workflow graph {action}: {count} canonical stages and relation projections")


if __name__ == "__main__":
    main()
