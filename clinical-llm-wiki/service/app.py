"""FastAPI boundary for local structured knowledge resolution."""

from __future__ import annotations

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
