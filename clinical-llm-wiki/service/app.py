"""FastAPI boundary for local structured knowledge resolution."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .config import WikiServiceConfig
from .contracts import ContractError, SchemaBundle
from .repository import Card, RepositoryError, VaultRepository
from .resolver import ResolutionError, resolve_runtime_context
from .snapshot import SnapshotError, create_snapshot


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QueryPayload(StrictPayload):
    query: str = ""
    type: str | None = None
    stage: str | None = None
    domain: str | None = None
    topic: str | None = None
    production_only: bool = False
    limit: int = Field(default=20, ge=1, le=100)


class RelationQueryPayload(StrictPayload):
    query_id: str | None = None
    statement_id: str | None = None
    domain: str | None = None
    variable: str | None = None
    knowledge_type: str | None = None
    production_only: bool = True
    limit: int = Field(default=20, ge=1, le=100)


class RuntimeRequest(StrictPayload):
    study_id: str
    stage: str
    runtime_manifest: dict[str, Any]
    schema_bundle: dict[str, str]
    require_workflow: bool = True
    require_domain: bool = False


class SnapshotPayload(StrictPayload):
    item_ids: list[str] | None = None
    snapshot_id: str | None = None
    version: str = "1.0.0"


class ProposalPayload(StrictPayload):
    record: dict[str, Any]
    body: str = ""


def create_app(config: WikiServiceConfig | None = None) -> FastAPI:
    settings = config or WikiServiceConfig.from_environment()
    bundle = SchemaBundle.load(settings.schemas_dir)
    repository = VaultRepository(settings.vault_root, bundle)
    repository.refresh()
    app = FastAPI(title="Clinical LLM Wiki Knowledge Service", version=bundle.version)
    app.state.config = settings
    app.state.bundle = bundle
    app.state.repository = repository

    @app.get("/api/v1/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "bind_host": settings.bind_host, "records": len(repository.cards)}

    @app.get("/api/v1/version")
    def version() -> dict[str, str]:
        return {"bundle_id": bundle.bundle_id, "bundle_version": bundle.version, "bundle_sha256": bundle.sha256}

    @app.get("/api/v1/items/{item_id}")
    def item(item_id: str) -> dict[str, Any]:
        card = repository.get(item_id)
        if card is None or card.record.get("type") in {"source_record", "figure_record"}:
            raise HTTPException(status_code=404, detail="knowledge item not found")
        return _card_response(card)

    @app.get("/api/v1/sources/{source_id}")
    def source(source_id: str) -> dict[str, Any]:
        card = repository.get(source_id)
        if card is None or card.record.get("type") != "source_record":
            raise HTTPException(status_code=404, detail="source record not found")
        return _card_response(card)

    @app.post("/api/v1/query")
    def query(payload: QueryPayload) -> dict[str, Any]:
        try:
            matches = repository.search(
                query=payload.query, record_type=payload.type, stage=payload.stage,
                domain=payload.domain, topic=payload.topic,
                production_only=payload.production_only, limit=payload.limit,
            )
        except RepositoryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"items": [_card_response(card, include_body=False) for card in matches], "count": len(matches)}

    @app.post("/api/v1/relations/query")
    def relation_query(payload: RelationQueryPayload) -> dict[str, Any]:
        try:
            result = _relation_query(repository, settings.vault_root, payload)
        except RepositoryError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return result

    @app.post("/api/v1/runtime-context/resolve")
    def runtime_context(payload: RuntimeRequest) -> dict[str, Any]:
        try:
            return resolve_runtime_context(repository, bundle, payload.model_dump())
        except (ContractError, ResolutionError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/snapshots", status_code=201)
    def snapshots(payload: SnapshotPayload) -> dict[str, Any]:
        try:
            return create_snapshot(repository, payload.model_dump(exclude_none=True))
        except SnapshotError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/proposals", status_code=201)
    def proposals(payload: ProposalPayload) -> dict[str, Any]:
        try:
            return _card_response(repository.create_proposal(payload.record, payload.body))
        except (ContractError, RepositoryError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/admin/refresh")
    def refresh(_: Request) -> dict[str, int]:
        # Local-only operational endpoint. It never changes governed cards.
        try:
            repository.refresh()
        except (ContractError, RepositoryError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"records": len(repository.cards)}

    return app


def _card_response(card: Card, *, include_body: bool = True) -> dict[str, Any]:
    response = {
        "record": card.record,
        "path": card.relative_path,
        "production_eligible": card.production_eligible,
        "eligibility_reasons": list(card.eligibility_reasons),
    }
    if include_body:
        response["body"] = card.body
    return response


def _relation_query(
    repository: VaultRepository, root: Any, payload: RelationQueryPayload
) -> dict[str, Any]:
    package = root / "sources" / "packages" / "src-cdisc-sdtmig-3-4"
    graph = _read_json_object(package / "relation-graph.json")
    index = _read_json_object(package / "query-index.json")
    release = _read_json_object(package / "approved-proposal-release.json")
    if index.get("graph_id") != graph.get("graph_id"):
        raise RepositoryError("relation query index does not match relation graph")
    if index.get("graph_sha256") != _script_style_sha256(graph):
        raise RepositoryError("relation graph hash mismatch")
    if graph.get("release_sha256") != _script_style_sha256(release):
        raise RepositoryError("approved proposal release hash mismatch")

    statements = {
        item["statement_id"]: item
        for item in release["extraction_package"]["statements"]
    }
    statement_nodes = {
        item["node_id"]: item
        for item in graph["nodes"]
        if item.get("node_type") == "statement"
    }
    matched_ids = _matched_relation_statement_ids(index, payload)
    items = []
    for statement_id in matched_ids:
        statement = statements.get(statement_id)
        node = statement_nodes.get(statement_id)
        if statement is None or node is None:
            raise RepositoryError(f"relation index references unknown statement: {statement_id}")
        card = repository.get(str(node["card_id"]))
        if card is None:
            raise RepositoryError(f"relation graph references missing card: {node['card_id']}")
        if payload.production_only and not card.production_eligible:
            continue
        items.append(_relation_item_response(statement, node, card, graph))
        if len(items) >= payload.limit:
            break
    return {
        "graph_id": graph["graph_id"],
        "index_id": index["index_id"],
        "count": len(items),
        "items": items,
    }


def _matched_relation_statement_ids(
    index: dict[str, Any], payload: RelationQueryPayload
) -> list[str]:
    if payload.query_id:
        cases = {
            item["query_id"]: item["expected_statement_ids"]
            for item in index["query_cases"]
        }
        if payload.query_id not in cases:
            raise RepositoryError(f"unknown relation query_id: {payload.query_id}")
        matched = set(cases[payload.query_id])
    else:
        pools: list[set[str]] = []
        if payload.statement_id:
            pools.append({payload.statement_id})
        if payload.domain:
            pools.append(set(index["domain_index"].get(payload.domain, [])))
        if payload.variable:
            pools.append(set(index["variable_index"].get(payload.variable, [])))
        if payload.knowledge_type:
            pools.append(set(index["knowledge_type_index"].get(payload.knowledge_type, [])))
        if not pools:
            matched = {
                statement_id
                for values in index["knowledge_type_index"].values()
                for statement_id in values
            }
        else:
            matched = set.intersection(*pools)
    return sorted(matched)


def _relation_item_response(
    statement: dict[str, Any],
    node: dict[str, Any],
    card: Card,
    graph: dict[str, Any],
) -> dict[str, Any]:
    statement_id = statement["statement_id"]
    edges = [
        edge
        for edge in graph["edges"]
        if edge["from_id"] == statement_id or edge["to_id"] == statement_id
    ]
    return {
        "statement_id": statement_id,
        "subject": statement["subject"],
        "statement": statement["statement"],
        "knowledge_type": statement["knowledge_type"],
        "modality": statement["modality"],
        "domains": node.get("domains", []),
        "variables": node.get("variables", []),
        "card": {
            "id": card.record["id"],
            "title": card.record["title"],
            "path": card.relative_path,
            "production_eligible": card.production_eligible,
        },
        "locator_ids": node.get("locator_ids", []),
        "source_id": graph["source_id"],
        "trace": [
            {
                "from_id": edge["from_id"],
                "relation_type": edge["relation_type"],
                "to_id": edge["to_id"],
                "evidence_locator_ids": edge.get("evidence_locator_ids", []),
            }
            for edge in edges
        ],
    }


def _read_json_object(path: Any) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RepositoryError(f"cannot read relation artifact {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RepositoryError(f"relation artifact must be a JSON object: {path}")
    return data


def _script_style_sha256(payload: Any) -> str:
    data = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest()
