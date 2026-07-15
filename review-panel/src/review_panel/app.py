from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from review_panel.config import ReviewPanelConfig
from review_panel.decision_service import DecisionService
from review_panel.errors import ReviewPanelServiceError
from review_panel.queue_registry import QueueRegistry
from review_panel.repository import ReviewRepository
from review_panel.schema_loader import ReviewSchemaLoader
from review_panel.source_service import SourceService


def create_app(repo_root: str | Path | None = None) -> FastAPI:
    config = ReviewPanelConfig.from_repo_root(repo_root)
    schema = ReviewSchemaLoader(config.schema_path).load()
    registry = QueueRegistry(config)
    repository = ReviewRepository(config=config, registry=registry, schema=schema)
    source_service = SourceService(repository)
    decision_service = DecisionService(repository)

    app = FastAPI(title="Clinical Review Panel", version="0.1.0")

    @app.exception_handler(ReviewPanelServiceError)
    async def service_error_handler(
        _request: Any,
        exc: ReviewPanelServiceError,
    ) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.to_dict()})

    @app.get("/api/v1/health")
    def health() -> dict[str, Any]:
        return repository.health()

    @app.get("/api/v1/reviews")
    def list_reviews() -> dict[str, Any]:
        return repository.list_reviews()

    @app.get("/api/v1/reviews/{queue_id}/{review_id}")
    def review_detail(queue_id: str, review_id: str) -> dict[str, Any]:
        return repository.get_detail(queue_id, review_id)

    @app.get("/api/v1/reviews/{queue_id}/{review_id}/sources/{source_index}")
    def source_preview(queue_id: str, review_id: str, source_index: int) -> dict[str, object]:
        return source_service.preview_source(queue_id, review_id, source_index)

    @app.post("/api/v1/reviews/{queue_id}/{review_id}/decisions")
    def submit_decision(queue_id: str, review_id: str, body: dict[str, Any]) -> dict[str, Any]:
        return decision_service.submit_decision(queue_id, review_id, body)

    @app.get("/")
    def root() -> dict[str, str]:
        raise HTTPException(status_code=404, detail="Static Review Panel UI is delivered in P3.")

    return app

