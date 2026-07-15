"""Build P6-P4 reusable SDTMIG 3.4 knowledge cards and typed relation graph.

The P3 approved proposal release remains the source of truth for atomic
statements.  This script projects that release into three reusable governed
knowledge cards, a machine relation graph, a deterministic query index, and a
small Obsidian curated map.  It never reads PDF/XLSX source text.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from scripts.content.extraction_contract import validate_extraction_package
from scripts.content.sdtmig34_core_proposals import canonical_json_bytes, sha256_payload
from scripts.content.sdtmig34_proposal_finalize import (
    APPROVAL_RECEIPT_ID,
    AUDIT_EVENT_ID,
    DEFAULT_RELEASE,
)


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "sources" / "packages" / "src-cdisc-sdtmig-3-4"
GRAPH_PATH = PACKAGE / "relation-graph.json"
QUERY_INDEX_PATH = PACKAGE / "query-index.json"
AE_MAP_PATH = ROOT / "vault" / "10_MOC" / "SDTMIG 3.4 AE Knowledge Map.md"
STANDARDS_MOC = ROOT / "vault" / "10_MOC" / "Standards-MOC.md"
SOURCES_MOC = ROOT / "vault" / "10_MOC" / "Sources-MOC.md"
RELEASE_CARD_LINK = "60_Sources/Registry/SDTMIG 3.4 Approved Proposal Release"
SOURCE_CARD_LINK = "60_Sources/Registry/CDISC SDTMIG 3.4"
GENERATED_AT = "2026-07-15T17:40:00+08:00"


class RelationGraphError(ValueError):
    """Raised when the P4 relation projection would become untrustworthy."""


CARD_GROUPS = [
    {
        "card_id": "kr-sdtmig34-core-foundations",
        "title": "SDTMIG 3.4 Core Foundations",
        "summary": (
            "SDTMIG 3.4 Core 基础规则，覆盖 observation、变量角色、domain/dataset "
            "结构、general observation classes、conformance 和 missing value 语境。"
        ),
        "topics": ["sdtmig-3-4", "core", "sdtm-foundations"],
        "workflow_stages": ["sdtm_spec", "sdtm_programming"],
        "statement_ids": [
            "proposal-sdtmig34-core-observation-framework-v1",
            "proposal-sdtmig34-core-identifier-variable-role-v1",
            "proposal-sdtmig34-core-topic-variable-role-v1",
            "proposal-sdtmig34-core-timing-variable-role-v1",
            "proposal-sdtmig34-core-qualifier-variable-role-v1",
            "proposal-sdtmig34-core-rule-variable-role-v1",
            "proposal-sdtmig34-core-domain-definition-v1",
            "proposal-sdtmig34-core-domain-code-consistency-v1",
            "proposal-sdtmig34-core-dataset-flat-file-structure-v1",
            "proposal-sdtmig34-core-general-observation-classes-v1",
            "proposal-sdtmig34-core-conformance-required-expected-columns-v1",
            "proposal-sdtmig34-core-missing-values-as-nulls-v1",
        ],
    },
    {
        "card_id": "kr-sdtmig34-core-variable-rules",
        "title": "SDTMIG 3.4 Core Variable Rules",
        "summary": (
            "SDTMIG 3.4 Core variable designation 与 study day 规则，覆盖 Required、"
            "Expected、Permissible、collected/absent data item 和 --DY 计算。"
        ),
        "topics": ["sdtmig-3-4", "core", "variable-rules", "study-day"],
        "workflow_stages": ["sdtm_spec", "sdtm_programming"],
        "statement_ids": [
            "proposal-sdtmig34-core-core-required-variable-v1",
            "proposal-sdtmig34-core-core-expected-variable-v1",
            "proposal-sdtmig34-core-core-permissible-variable-v1",
            "proposal-sdtmig34-core-permissible-generally-not-used-v1",
            "proposal-sdtmig34-core-permissible-include-when-data-item-exists-v1",
            "proposal-sdtmig34-core-permissible-omit-when-data-item-absent-v1",
            "proposal-sdtmig34-core-study-day-variable-purpose-v1",
            "proposal-sdtmig34-core-study-day-reference-and-limit-v1",
            "proposal-sdtmig34-core-study-day-calculation-method-v1",
        ],
    },
    {
        "card_id": "kr-sdtmig34-ae-domain-rules",
        "title": "SDTMIG 3.4 AE Domain Rules",
        "summary": (
            "SDTMIG 3.4 Events/AE 深度范围规则，覆盖 AE domain definition、"
            "AE dataset structure、AETERM、AEENRF、Example 1 和 RELTYPE=MANY erratum。"
        ),
        "topics": ["sdtmig-3-4", "events", "adverse-events", "ae-domain"],
        "workflow_stages": ["sdtm_spec", "sdtm_programming"],
        "statement_ids": [
            "proposal-sdtmig34-gold-events-class-guidance-v1",
            "proposal-sdtmig34-gold-ae-definition-v1",
            "proposal-sdtmig34-gold-ae-structure-v1",
            "proposal-sdtmig34-gold-aeterm-required-v1",
            "proposal-sdtmig34-gold-ae-example1-v1",
            "proposal-sdtmig34-gold-aeenrf-crossref-v1",
            "proposal-sdtmig34-gold-erratum-lnkgrp-v1",
        ],
    },
]

QUERY_CASES = [
    {
        "query_id": "q-ae-domain-definition",
        "question": "AE domain definition",
        "filters": {"domain": "AE", "knowledge_type": "definition"},
        "expected_statement_ids": ["proposal-sdtmig34-gold-ae-definition-v1"],
    },
    {
        "query_id": "q-aeterm-required",
        "question": "AE.AETERM required rule",
        "filters": {"domain": "AE", "variable": "AETERM"},
        "expected_statement_ids": ["proposal-sdtmig34-gold-aeterm-required-v1"],
    },
    {
        "query_id": "q-aeenrf-cross-reference",
        "question": "AE.AEENRF cross-reference",
        "filters": {"domain": "AE", "variable": "AEENRF"},
        "expected_statement_ids": ["proposal-sdtmig34-gold-aeenrf-crossref-v1"],
    },
    {
        "query_id": "q-reltype-many-erratum",
        "question": "RELTYPE=MANY IDVAR erratum",
        "filters": {"variable": "RELTYPE", "knowledge_type": "exception"},
        "expected_statement_ids": ["proposal-sdtmig34-gold-erratum-lnkgrp-v1"],
    },
    {
        "query_id": "q-study-day-calculation",
        "question": "--DY study day calculation",
        "filters": {"variable": "--DY"},
        "expected_statement_ids": [
            "proposal-sdtmig34-core-study-day-variable-purpose-v1",
            "proposal-sdtmig34-core-study-day-reference-and-limit-v1",
            "proposal-sdtmig34-core-study-day-calculation-method-v1",
        ],
    },
]


def _read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RelationGraphError(f"JSON artifact must be an object: {path}")
    return payload


def _vault_content_hash(record: dict[str, Any], body: str) -> str:
    payload = {
        "frontmatter": {
            key: value for key, value in record.items() if key != "content_hash"
        },
        "body": body.strip(),
    }
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _render_markdown(record: dict[str, Any], body: str) -> str:
    rendered = dict(record)
    rendered["content_hash"] = _vault_content_hash(rendered, body)
    frontmatter = yaml.safe_dump(rendered, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{frontmatter}\n---\n\n{body.strip()}\n"


def _statement_indexes(package: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    statements = {item["statement_id"]: item for item in package["statements"]}
    units = {item["unit_id"]: item for item in package["units"]}
    if len(statements) != len(package["statements"]):
        raise RelationGraphError("duplicate statement id in release package")
    return statements, units


def _validate_card_groups(statements: dict[str, Any]) -> dict[str, str]:
    assigned: dict[str, str] = {}
    for group in CARD_GROUPS:
        for statement_id in group["statement_ids"]:
            if statement_id not in statements:
                raise RelationGraphError(f"card group references unknown statement: {statement_id}")
            if statement_id in assigned:
                raise RelationGraphError(
                    f"statement assigned to multiple cards: {statement_id}"
                )
            assigned[statement_id] = group["card_id"]
    if set(assigned) != set(statements):
        missing = sorted(set(statements) - set(assigned))
        raise RelationGraphError(f"approved statements not assigned to a reusable card: {missing}")
    return assigned


def _locator_ids(statement: dict[str, Any]) -> list[str]:
    return [item["locator_id"] for item in statement["evidence"]]


def _statement_domains(statement: dict[str, Any]) -> list[str]:
    domains = list(statement["scope"]["domains"])
    if statement["statement_id"].startswith("proposal-sdtmig34-gold-ae"):
        domains = sorted(set(domains) | {"AE"})
    return domains


def _add_node(nodes: dict[str, dict[str, Any]], node_id: str, **fields: Any) -> None:
    existing = nodes.get(node_id)
    payload = {"node_id": node_id, **fields}
    if existing is not None:
        if existing != payload:
            raise RelationGraphError(f"conflicting graph node: {node_id}")
        return
    nodes[node_id] = payload


def _add_edge(edges: dict[str, dict[str, Any]], edge_id: str, **fields: Any) -> None:
    payload = {"edge_id": edge_id, **fields}
    existing = edges.get(edge_id)
    if existing is not None:
        if existing != payload:
            raise RelationGraphError(f"conflicting graph edge: {edge_id}")
        return
    edges[edge_id] = payload


def build_relation_graph(release: dict[str, Any]) -> dict[str, Any]:
    package = release["extraction_package"]
    validate_extraction_package(package)
    statements, units = _statement_indexes(package)
    statement_to_card = _validate_card_groups(statements)
    known_relation_targets = set(statements) | set(units)

    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    _add_node(
        nodes,
        package["source_id"],
        node_type="source",
        label="CDISC SDTMIG 3.4",
        source_sha256=package["source_sha256"],
    )

    for group in CARD_GROUPS:
        _add_node(
            nodes,
            group["card_id"],
            node_type="knowledge_card",
            label=group["title"],
            workflow_stages=group["workflow_stages"],
        )

    for statement in statements.values():
        statement_id = statement["statement_id"]
        domains = _statement_domains(statement)
        variables = statement["scope"]["variables"]
        _add_node(
            nodes,
            statement_id,
            node_type="statement",
            label=statement["subject"],
            knowledge_type=statement["knowledge_type"],
            modality=statement["modality"],
            card_id=statement_to_card[statement_id],
            domains=domains,
            variables=variables,
            locator_ids=_locator_ids(statement),
        )
        _add_edge(
            edges,
            f"edge-{statement_to_card[statement_id]}-contains-{statement_id}",
            from_id=statement_to_card[statement_id],
            to_id=statement_id,
            relation_type="contains",
            evidence_locator_ids=_locator_ids(statement),
        )
        for locator_id in _locator_ids(statement):
            _add_node(nodes, locator_id, node_type="locator", label=locator_id)
            _add_edge(
                edges,
                f"edge-{statement_id}-supported-by-{locator_id}",
                from_id=statement_id,
                to_id=locator_id,
                relation_type="supported_by",
                evidence_locator_ids=[locator_id],
            )
            _add_edge(
                edges,
                f"edge-{locator_id}-from-{package['source_id']}",
                from_id=locator_id,
                to_id=package["source_id"],
                relation_type="from_source",
                evidence_locator_ids=[locator_id],
            )
        for domain in domains:
            domain_id = f"domain-{domain.lower()}"
            _add_node(nodes, domain_id, node_type="domain", label=domain)
            _add_edge(
                edges,
                f"edge-{domain_id}-has-rule-{statement_id}",
                from_id=domain_id,
                to_id=statement_id,
                relation_type="has_rule",
                evidence_locator_ids=_locator_ids(statement),
            )
        for variable in variables:
            variable_id = "variable-" + variable.lower().replace("--", "xx").replace(".", "-")
            _add_node(nodes, variable_id, node_type="variable", label=variable)
            _add_edge(
                edges,
                f"edge-{variable_id}-has-rule-{statement_id}",
                from_id=variable_id,
                to_id=statement_id,
                relation_type="has_rule",
                evidence_locator_ids=_locator_ids(statement),
            )
        if statement["knowledge_type"] == "example":
            _add_edge(
                edges,
                f"edge-domain-ae-illustrated-by-{statement_id}",
                from_id="domain-ae",
                to_id=statement_id,
                relation_type="illustrated_by",
                evidence_locator_ids=_locator_ids(statement),
            )
        if statement["knowledge_type"] == "exception":
            _add_edge(
                edges,
                f"edge-{statement_id}-qualifies-exception-scope",
                from_id=statement_id,
                to_id="external-sdtmig34-errata",
                relation_type="exception_to",
                evidence_locator_ids=_locator_ids(statement),
            )

    dangling_relations = []
    for relation in package["relations"]:
        if relation["from_id"] not in statements:
            dangling_relations.append(relation["relation_id"])
            continue
        target_kind = relation["target_kind"]
        target_id = relation["to_id"]
        if target_kind in {"statement", "source_unit"} and target_id not in known_relation_targets:
            dangling_relations.append(relation["relation_id"])
            continue
        if target_kind in {"topic", "external_dependency"}:
            _add_node(
                nodes,
                target_id,
                node_type=target_kind,
                label=target_id,
                explicit_external=target_kind == "external_dependency",
            )
        _add_edge(
            edges,
            f"edge-{relation['relation_id']}",
            from_id=relation["from_id"],
            to_id=target_id,
            relation_type=relation["relation_type"],
            evidence_locator_ids=[item["locator_id"] for item in relation["evidence"]],
        )

    duplicate_subjects = {
        subject: count
        for subject, count in Counter(
            (item["subject"], item["knowledge_type"], tuple(_statement_domains(item)))
            for item in statements.values()
        ).items()
        if count > 1
    }
    graph = {
        "schema_version": "1.0.0",
        "graph_id": "graph-sdtmig34-core-events-ae-v1",
        "generated_at": GENERATED_AT,
        "release_id": release["release_id"],
        "release_sha256": sha256_payload(release),
        "approval_receipt_id": APPROVAL_RECEIPT_ID,
        "source_id": package["source_id"],
        "nodes": sorted(nodes.values(), key=lambda item: item["node_id"]),
        "edges": sorted(edges.values(), key=lambda item: item["edge_id"]),
        "quality": {
            "approved_statement_count": len(statements),
            "reusable_card_count": len(CARD_GROUPS),
            "duplicate_statement_assignment_count": 0,
            "duplicate_general_rule_count": len(duplicate_subjects),
            "dangling_relation_count": len(dangling_relations),
            "dangling_relation_ids": sorted(dangling_relations),
            "locator_node_count": sum(1 for node in nodes.values() if node["node_type"] == "locator"),
            "obsidian_locator_node_count": 0,
        },
    }
    if dangling_relations:
        raise RelationGraphError("typed relation closure failed: " + ", ".join(dangling_relations))
    if duplicate_subjects:
        raise RelationGraphError(f"duplicate reusable rule subjects: {duplicate_subjects}")
    return graph


def build_query_index(release: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    package = release["extraction_package"]
    statements = {item["statement_id"]: item for item in package["statements"]}
    domain_index: dict[str, list[str]] = defaultdict(list)
    variable_index: dict[str, list[str]] = defaultdict(list)
    type_index: dict[str, list[str]] = defaultdict(list)
    locator_index: dict[str, list[str]] = defaultdict(list)

    for statement in statements.values():
        statement_id = statement["statement_id"]
        for domain in _statement_domains(statement):
            domain_index[domain].append(statement_id)
        for variable in statement["scope"]["variables"]:
            variable_index[variable].append(statement_id)
        type_index[statement["knowledge_type"]].append(statement_id)
        for locator_id in _locator_ids(statement):
            locator_index[locator_id].append(statement_id)

    resolved_cases = []
    for case in QUERY_CASES:
        for statement_id in case["expected_statement_ids"]:
            if statement_id not in statements:
                raise RelationGraphError(f"query case references unknown statement: {statement_id}")
        resolved_cases.append(
            {
                **case,
                "locator_ids": sorted(
                    {
                        locator_id
                        for statement_id in case["expected_statement_ids"]
                        for locator_id in _locator_ids(statements[statement_id])
                    }
                ),
                "card_ids": sorted(
                    {
                        node["card_id"]
                        for node in graph["nodes"]
                        if node["node_type"] == "statement"
                        and node["node_id"] in case["expected_statement_ids"]
                    }
                ),
            }
        )

    return {
        "schema_version": "1.0.0",
        "index_id": "query-index-sdtmig34-core-events-ae-v1",
        "generated_at": GENERATED_AT,
        "graph_id": graph["graph_id"],
        "graph_sha256": sha256_payload(graph),
        "domain_index": {key: sorted(value) for key, value in sorted(domain_index.items())},
        "variable_index": {key: sorted(value) for key, value in sorted(variable_index.items())},
        "knowledge_type_index": {key: sorted(value) for key, value in sorted(type_index.items())},
        "locator_index": {key: sorted(value) for key, value in sorted(locator_index.items())},
        "query_cases": resolved_cases,
    }


def _card_record(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": group["card_id"],
        "type": "standard_rule",
        "title": group["title"],
        "version": "1.0.0",
        "schema_version": "1.0.0",
        "content_status": "verified",
        "approval_status": "approved",
        "domains": ["sdtm", "data_standards"],
        "workflow_stages": group["workflow_stages"],
        "topics": group["topics"],
        "aliases": [],
        "authority": "industry_standard",
        "applicability": {
            "therapeutic_areas": [],
            "trial_phases": [],
            "sponsor_ids": [],
            "study_ids": [],
            "conditions": [],
        },
        "sources": ["src-cdisc-sdtmig-3-4"],
        "owner": "clinical-knowledge-governance",
        "created": GENERATED_AT,
        "last_reviewed": "2026-07-15",
        "review_due": "2027-07-15",
        "supersedes": [],
        "superseded_by": None,
        "content_hash": "0" * 64,
        "rights_status": "restricted",
        "allowed_uses": ["runtime", "reference"],
        "storage_mode": "committed",
        "contract_compatibility": {"minimum": "1.0.0", "maximum_exclusive": "2.0.0"},
        "approval_receipt_id": APPROVAL_RECEIPT_ID,
        "audit_reference": AUDIT_EVENT_ID,
        "summary": group["summary"],
        "statements": [],
    }


def build_knowledge_cards(release: dict[str, Any], graph: dict[str, Any]) -> dict[Path, str]:
    statements = {item["statement_id"]: item for item in release["extraction_package"]["statements"]}
    outputs: dict[Path, str] = {}
    for group in CARD_GROUPS:
        record = _card_record(group)
        rows = []
        for statement_id in group["statement_ids"]:
            statement = statements[statement_id]
            locators = ", ".join(_locator_ids(statement))
            rows.append(
                "| {rule_id} | {subject} | {kind} | {modality} | {locators} |".format(
                    rule_id=statement_id,
                    subject=statement["subject"],
                    kind=statement["knowledge_type"],
                    modality=statement["modality"],
                    locators=locators,
                )
            )
            record["statements"].append(
                {
                    "rule_id": statement_id,
                    "statement": statement["statement"],
                    "rationale": (
                        "P6-P3-E 人工批准的 SDTMIG 3.4 proposal；"
                        "精确 locator 与 typed relation 由 P4 relation graph 承载。"
                    ),
                    "evidence_refs": ["src-cdisc-sdtmig-3-4"],
                }
            )
        body = f"""# {group["title"]}

## 适用边界

本卡由 P6-P4 从 approved proposal release 生成，作为复用层知识正文；原子 locator、typed relation 和查询路径保存在 `clinical-llm-wiki/sources/packages/src-cdisc-sdtmig-3-4/relation-graph.json` 与 `query-index.json`。

## 批准与来源

- 批准：`{APPROVAL_RECEIPT_ID}`
- 审计事件：`{AUDIT_EVENT_ID}`
- 来源：[[{SOURCE_CARD_LINK}|CDISC SDTMIG 3.4]]
- Release：[[{RELEASE_CARD_LINK}|SDTMIG 3.4 Approved Proposal Release]]

## 已批准规则

| Rule | Subject | Type | Modality | Locators |
|---|---|---|---|---|
{chr(10).join(rows)}

## 查询入口

参见 [[10_MOC/SDTMIG 3.4 AE Knowledge Map|SDTMIG 3.4 AE Knowledge Map]]。
"""
        filename = group["title"] + ".md"
        outputs[ROOT / "vault" / "20_Knowledge" / "Standards" / filename] = _render_markdown(
            record, body
        )

    statement_card_ids = {
        node["node_id"]: node["card_id"]
        for node in graph["nodes"]
        if node["node_type"] == "statement"
    }
    if set(statement_card_ids) != set(statements):
        raise RelationGraphError("knowledge cards do not cover all statements")
    return outputs


def build_ae_map(graph: dict[str, Any], query_index: dict[str, Any]) -> str:
    ae_cases = "\n".join(
        "- `{query_id}`：{question} → {statements}；locators={locators}".format(
            query_id=case["query_id"],
            question=case["question"],
            statements=", ".join(case["expected_statement_ids"]),
            locators=", ".join(case["locator_ids"]),
        )
        for case in query_index["query_cases"]
    )
    cards = "\n".join(
        f"- [[20_Knowledge/Standards/{group['title']}|{group['title']}]]"
        for group in CARD_GROUPS
    )
    return f"""---
id: moc-sdtmig34-ae-knowledge-map
type: navigation
title: SDTMIG 3.4 AE Knowledge Map
---

# SDTMIG 3.4 AE Knowledge Map

本页是 P6-P4 的人工策展视图，只展示高价值主题与复用卡，不把 28 条原子 statement、locator 或 XLSX row 展开成 Obsidian 节点。

## 来源与 release

- [[{SOURCE_CARD_LINK}|CDISC SDTMIG 3.4]]
- [[{RELEASE_CARD_LINK}|SDTMIG 3.4 Approved Proposal Release]]

## 复用知识卡

{cards}

## 机器查询路径

{ae_cases}

## 图谱质量

- Approved statements：{graph["quality"]["approved_statement_count"]}
- Reusable cards：{graph["quality"]["reusable_card_count"]}
- Dangling relations：{graph["quality"]["dangling_relation_count"]}
- Obsidian locator nodes：{graph["quality"]["obsidian_locator_node_count"]}

[[10_MOC/Sources-MOC|返回来源导航]]
"""


def _upsert_section(text: str, heading: str, section: str) -> str:
    if section in text:
        return text
    marker = f"\n## {heading}\n"
    if marker not in text:
        raise RelationGraphError(f"MOC section not found: {heading}")
    insert_at = text.index(marker) + len(marker)
    return text[:insert_at] + "\n" + section.strip() + "\n" + text[insert_at:]


def update_mocs() -> None:
    standards = STANDARDS_MOC.read_text(encoding="utf-8")
    standards_section = """
### SDTMIG 3.4 深度范围

- [[20_Knowledge/Standards/SDTMIG 3.4 Core Foundations]]
- [[20_Knowledge/Standards/SDTMIG 3.4 Core Variable Rules]]
- [[20_Knowledge/Standards/SDTMIG 3.4 AE Domain Rules]]
- [[10_MOC/SDTMIG 3.4 AE Knowledge Map|SDTMIG 3.4 AE Knowledge Map]]
"""
    STANDARDS_MOC.write_text(
        _upsert_section(standards, "SDTM", standards_section),
        encoding="utf-8",
        newline="\n",
    )

    sources = SOURCES_MOC.read_text(encoding="utf-8")
    if "SDTMIG 3.4 AE Knowledge Map" not in sources:
        sources = sources.replace(
            "- [[60_Sources/Registry/SDTMIG 3.4 Approved Proposal Release|SDTMIG 3.4 Core/Events/AE 已批准 proposal release]]",
            "- [[60_Sources/Registry/SDTMIG 3.4 Approved Proposal Release|SDTMIG 3.4 Core/Events/AE 已批准 proposal release]]\n"
            "- [[10_MOC/SDTMIG 3.4 AE Knowledge Map|SDTMIG 3.4 AE Knowledge Map]]",
        )
    SOURCES_MOC.write_text(sources, encoding="utf-8", newline="\n")


def build_outputs() -> dict[str, Any]:
    release = _read_json(DEFAULT_RELEASE)
    graph = build_relation_graph(release)
    query_index = build_query_index(release, graph)
    cards = build_knowledge_cards(release, graph)
    ae_map = build_ae_map(graph, query_index)
    return {
        "release": release,
        "graph": graph,
        "query_index": query_index,
        "cards": cards,
        "ae_map": ae_map,
    }


def write_outputs(outputs: dict[str, Any]) -> None:
    GRAPH_PATH.write_bytes(canonical_json_bytes(outputs["graph"]))
    QUERY_INDEX_PATH.write_bytes(canonical_json_bytes(outputs["query_index"]))
    for path, text in outputs["cards"].items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    AE_MAP_PATH.write_text(outputs["ae_map"], encoding="utf-8", newline="\n")
    update_mocs()


def _assert_file_matches(path: Path, expected: bytes | str) -> None:
    if not path.is_file():
        raise RelationGraphError(f"expected generated file is missing: {path}")
    if isinstance(expected, bytes):
        actual = path.read_bytes()
    else:
        actual = path.read_text(encoding="utf-8")
    if actual != expected:
        raise RelationGraphError(f"generated artifact is stale: {path}")


def check_outputs(outputs: dict[str, Any]) -> None:
    _assert_file_matches(GRAPH_PATH, canonical_json_bytes(outputs["graph"]))
    _assert_file_matches(QUERY_INDEX_PATH, canonical_json_bytes(outputs["query_index"]))
    for path, text in outputs["cards"].items():
        _assert_file_matches(path, text)
    _assert_file_matches(AE_MAP_PATH, outputs["ae_map"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = build_outputs()
    if args.check:
        check_outputs(outputs)
    else:
        write_outputs(outputs)
    print(
        json.dumps(
            {
                "statements": outputs["graph"]["quality"]["approved_statement_count"],
                "cards": outputs["graph"]["quality"]["reusable_card_count"],
                "edges": len(outputs["graph"]["edges"]),
                "queries": len(outputs["query_index"]["query_cases"]),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RelationGraphError as error:
        raise SystemExit(f"SDTMIG 3.4 relation graph failed: {error}") from error
