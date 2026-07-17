"""FastAPI adapter for the P8 local Application API."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Body, FastAPI, Header, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .service import ApplicationApiConfig, ApplicationApiError, ApplicationApiService


def create_app(config: ApplicationApiConfig | None = None) -> FastAPI:
    """Create the loopback Application API app.

    P8-P3 exposes read-only study/artifact/context views plus write-limited
    run-request and Review Protocol decision routes.  Write routes only persist
    Runtime request files, events, or DecisionReceipt files.
    """

    app = FastAPI(
        title="Clinical Workflow Application API",
        version="0.1.0-draft",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    service = ApplicationApiService(config or _default_config())
    app.state.application_api_service = service
    console_static_dir = Path(__file__).resolve().parents[1] / "study_console" / "static"

    @app.exception_handler(ApplicationApiError)
    async def application_api_error_handler(
        _request: Request,
        exc: ApplicationApiError,
    ) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.as_response())

    @app.get("/console", include_in_schema=False)
    def study_console_redirect() -> RedirectResponse:
        return RedirectResponse(url="/console/")

    @app.get("/api/v1/studies")
    def list_studies() -> dict:
        return service.list_studies()

    @app.get("/api/v1/studies/{study_id}/status")
    def get_study_status(study_id: str) -> dict:
        return service.get_status(study_id)

    @app.get("/api/v1/studies/{study_id}/poc-state")
    def get_poc_state(study_id: str) -> dict:
        return service.get_poc_state(study_id)

    @app.post("/api/v1/studies/{study_id}/poc-runs", status_code=status.HTTP_202_ACCEPTED)
    def start_poc_run(
        study_id: str,
        request: dict = Body(...),
    ) -> dict:
        return service.start_poc_run(study_id, request)

    @app.get("/api/v1/studies/{study_id}/poc-runs/{run_id}")
    def get_poc_run(study_id: str, run_id: str) -> dict:
        return service.get_poc_run(study_id, run_id)

    @app.post(
        "/api/v1/studies/{study_id}/poc-runs/{run_id}/resume",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def resume_poc_run(
        study_id: str,
        run_id: str,
        request: dict = Body(...),
    ) -> dict:
        return service.resume_poc_run(study_id, run_id, request)

    @app.post("/api/v1/studies/{study_id}/runs", status_code=status.HTTP_202_ACCEPTED)
    def start_run(
        study_id: str,
        request: dict = Body(...),
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
    ) -> dict:
        return service.start_run(study_id, request, idempotency_key=idempotency_key)

    @app.get("/api/v1/studies/{study_id}/runs/{run_id}")
    def get_run(study_id: str, run_id: str) -> dict:
        return service.get_run(study_id, run_id)

    @app.post(
        "/api/v1/studies/{study_id}/runs/{run_id}/resume",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def resume_run(
        study_id: str,
        run_id: str,
        request: dict = Body(...),
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
    ) -> dict:
        return service.resume_run(study_id, run_id, request, idempotency_key=idempotency_key)

    @app.get("/api/v1/studies/{study_id}/events")
    def list_events(study_id: str, cursor: str | None = Query(default=None)) -> dict:
        return service.list_events(study_id, cursor=cursor)

    @app.get("/api/v1/studies/{study_id}/artifacts")
    def list_artifacts(study_id: str) -> dict:
        return service.list_artifacts(study_id)

    @app.get("/api/v1/studies/{study_id}/artifacts/{artifact_id}")
    def get_artifact(study_id: str, artifact_id: str) -> dict:
        return service.get_artifact(study_id, artifact_id)

    @app.get("/api/v1/studies/{study_id}/reviews")
    def list_reviews(study_id: str) -> dict:
        return service.list_reviews(study_id)

    @app.post(
        "/api/v1/studies/{study_id}/reviews/{review_id}/decisions",
        status_code=status.HTTP_201_CREATED,
    )
    def submit_review_decision(
        study_id: str,
        review_id: str,
        request: dict = Body(...),
        idempotency_key: str = Header(..., alias="Idempotency-Key"),
    ) -> dict:
        return service.submit_review_decision(
            study_id,
            review_id,
            request,
            idempotency_key=idempotency_key,
        )

    @app.get("/api/v1/studies/{study_id}/context")
    def get_context(study_id: str) -> dict:
        return service.get_context(study_id)

    @app.get("/api/v1/studies/{study_id}/provenance")
    def get_provenance(study_id: str) -> dict:
        return service.get_provenance(study_id)

    @app.get("/api/v1/studies/{study_id}/audit")
    def get_audit(study_id: str, cursor: str | None = Query(default=None)) -> dict:
        return service.get_audit(study_id, cursor=cursor)

    if console_static_dir.exists():
        app.mount(
            "/console",
            StaticFiles(directory=console_static_dir, html=True),
            name="study-console",
        )

    return app


def _default_config() -> ApplicationApiConfig:
    studies_root = os.environ.get("CLINICAL_STUDIES_ROOT")
    if studies_root:
        return ApplicationApiConfig(container_roots={"clinical-studies": Path(studies_root)})
    return ApplicationApiConfig.for_platform_root(Path.cwd().parent)
