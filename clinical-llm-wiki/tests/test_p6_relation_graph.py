"""P6-P4 relation graph, reusable card, and query endpoint checks."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from scripts.content.sdtmig34_relation_graph import (
    AE_MAP_PATH,
    CARD_GROUPS,
    GRAPH_PATH,
    QUERY_INDEX_PATH,
    build_outputs,
    check_outputs,
)
from service.app import create_app
from service.config import WikiServiceConfig


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "sources" / "packages" / "src-cdisc-sdtmig-3-4"
CARD_IDS = {group["card_id"] for group in CARD_GROUPS}


def test_relation_graph_artifacts_are_rebuildable_and_closed() -> None:
    outputs = build_outputs()
    check_outputs(outputs)

    graph = outputs["graph"]
    query_index = outputs["query_index"]
    assigned_rule_ids = [
        statement["rule_id"]
        for text in outputs["cards"].values()
        for statement in _frontmatter(text)["statements"]
    ]

    assert graph["quality"]["approved_statement_count"] == 28
    assert graph["quality"]["reusable_card_count"] == 3
    assert graph["quality"]["dangling_relation_count"] == 0
    assert graph["quality"]["duplicate_statement_assignment_count"] == 0
    assert graph["quality"]["duplicate_general_rule_count"] == 0
    assert graph["quality"]["obsidian_locator_node_count"] == 0
    assert len(assigned_rule_ids) == len(set(assigned_rule_ids)) == 28
    assert {case["query_id"] for case in query_index["query_cases"]} == {
        "q-ae-domain-definition",
        "q-aeterm-required",
        "q-aeenrf-cross-reference",
        "q-reltype-many-erratum",
        "q-study-day-calculation",
    }


def test_ae_map_keeps_obsidian_graph_curated() -> None:
    text = AE_MAP_PATH.read_text(encoding="utf-8")
    assert "[[20_Knowledge/Standards/SDTMIG 3.4 Core Foundations" in text
    assert "[[20_Knowledge/Standards/SDTMIG 3.4 Core Variable Rules" in text
    assert "[[20_Knowledge/Standards/SDTMIG 3.4 AE Domain Rules" in text
    assert "[[loc-" not in text
    assert "[[unit-" not in text
    assert "README" not in text


def test_service_relation_query_returns_production_traces(tmp_path: Path) -> None:
    _copy_service_fixture(tmp_path)
    client = TestClient(
        create_app(
            WikiServiceConfig(
                vault_root=tmp_path,
                schemas_dir=tmp_path / "schemas" / "engine",
            )
        )
    )

    for card_id in CARD_IDS:
        card = client.get(f"/api/v1/items/{card_id}")
        assert card.status_code == 200
        assert card.json()["production_eligible"] is True

    aeterm = client.post(
        "/api/v1/relations/query",
        json={"query_id": "q-aeterm-required"},
    )
    assert aeterm.status_code == 200, aeterm.text
    assert [item["statement_id"] for item in aeterm.json()["items"]] == [
        "proposal-sdtmig34-gold-aeterm-required-v1"
    ]
    item = aeterm.json()["items"][0]
    assert item["card"]["id"] == "kr-sdtmig34-ae-domain-rules"
    assert "loc-sdtmig34-p137-aeterm-assumption" in item["locator_ids"]
    assert item["source_id"] == "src-cdisc-sdtmig-3-4"
    assert any(edge["relation_type"] == "supported_by" for edge in item["trace"])

    study_day = client.post("/api/v1/relations/query", json={"variable": "--DY"})
    assert study_day.status_code == 200, study_day.text
    assert {item["statement_id"] for item in study_day.json()["items"]} == {
        "proposal-sdtmig34-core-study-day-variable-purpose-v1",
        "proposal-sdtmig34-core-study-day-reference-and-limit-v1",
        "proposal-sdtmig34-core-study-day-calculation-method-v1",
    }

    erratum = client.post(
        "/api/v1/relations/query",
        json={"variable": "RELTYPE", "knowledge_type": "exception"},
    )
    assert erratum.status_code == 200, erratum.text
    assert [item["statement_id"] for item in erratum.json()["items"]] == [
        "proposal-sdtmig34-gold-erratum-lnkgrp-v1"
    ]


def _frontmatter(text: str) -> dict[str, object]:
    _, raw, _ = text.split("---", 2)
    import yaml

    payload = yaml.safe_load(raw)
    assert isinstance(payload, dict)
    return payload


def _copy_service_fixture(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "vault", tmp_path / "vault")
    shutil.copytree(ROOT / ".review_queue", tmp_path / ".review_queue")
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    shutil.copy2(ROOT / "audit_trail.jsonl", tmp_path / "audit_trail.jsonl")

    package = tmp_path / "sources" / "packages" / "src-cdisc-sdtmig-3-4"
    package.mkdir(parents=True)
    for path in (PACKAGE / "approved-proposal-release.json", GRAPH_PATH, QUERY_INDEX_PATH):
        shutil.copy2(path, package / path.name)

    assert json.loads((package / "relation-graph.json").read_text(encoding="utf-8"))[
        "quality"
    ]["dangling_relation_count"] == 0
