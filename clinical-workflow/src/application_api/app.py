"""FastAPI adapter for the read-only P8 Application API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from .service import ApplicationApiConfig, ApplicationApiError, ApplicationApiService


def create_app(config: ApplicationApiConfig | None = None) -> FastAPI:
    """Create the loopback Application API app.

    P8-P2 only exposes read-only routes.  Write routes from the P8-P1 OpenAPI
    draft intentionally remain unimplemented until P8-P3.
    """

    app = FastAPI(
        title="Clinical Workflow Application API",
        version="0.1.0-draft",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    service = ApplicationApiService(config or ApplicationApiConfig.for_platform_root(Path.cwd().parent))
    app.state.application_api_service = service

    @app.exception_handler(ApplicationApiError)
    async def application_api_error_handler(
        _request: Request,
        exc: ApplicationApiError,
    ) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.as_response())

    @app.get("/api/v1/studies")
    def list_studies() -> dict:
        return service.list_studies()

    @app.get("/api/v1/studies/{study_id}/status")
    def get_study_status(study_id: str) -> dict:
        return service.get_status(study_id)

    @app.get("/api/v1/studies/{study_id}/artifacts")
    def list_artifacts(study_id: str) -> dict:
        return service.list_artifacts(study_id)

    @app.get("/api/v1/studies/{study_id}/artifacts/{artifact_id}")
    def get_artifact(study_id: str, artifact_id: str) -> dict:
        return service.get_artifact(study_id, artifact_id)

    @app.get("/api/v1/studies/{study_id}/context")
    def get_context(study_id: str) -> dict:
        return service.get_context(study_id)

    @app.get("/api/v1/studies/{study_id}/provenance")
    def get_provenance(study_id: str) -> dict:
        return service.get_provenance(study_id)

    @app.get("/api/v1/studies/{study_id}/audit")
    def get_audit(study_id: str, cursor: str | None = Query(default=None)) -> dict:
        return service.get_audit(study_id, cursor=cursor)

    return app
