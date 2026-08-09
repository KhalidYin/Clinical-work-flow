"""Narrow authenticated HTTP boundary for Harness execution.

The service is intentionally not a Docker API proxy. Product workers submit a
versioned Attempt contract; later phases compile that contract into the fixed
container policy owned by this service.
"""

from __future__ import annotations

from collections.abc import Callable
from secrets import compare_digest
from threading import Lock
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .service_contracts import (
    SupervisorAttemptRequest,
    SupervisorAttemptStatus,
    canonical_sha256,
)


_AUTHENTICATION_DETAIL = {
    "code": "machine_authentication_required",
    "message": "valid supervisor machine credential required",
}


def create_supervisor_app(
    *,
    machine_token: str,
    allowed_spec_sha256: frozenset[str],
    dispatch: Callable[[SupervisorAttemptRequest], None],
) -> FastAPI:
    """Build the internal Supervisor API with one machine credential."""

    if not machine_token:
        raise ValueError("machine_token must not be empty")

    app = FastAPI(title="Clinical Harness Supervisor", docs_url=None, redoc_url=None)
    attempts: dict[str, SupervisorAttemptStatus] = {}
    attempts_lock = Lock()

    @app.exception_handler(RequestValidationError)
    async def invalid_request_contract(
        _request: Request,
        _error: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "invalid_request_contract",
                    "message": "attempt request does not match the supervisor contract",
                }
            },
        )

    def require_machine(
        authorization: Annotated[str | None, Header()] = None,
    ) -> None:
        scheme, _, presented = (authorization or "").partition(" ")
        valid = scheme == "Bearer" and compare_digest(presented, machine_token)
        if not valid:
            raise HTTPException(status_code=401, detail=_AUTHENTICATION_DETAIL)

    @app.post(
        "/v1/attempts",
        response_model=SupervisorAttemptStatus,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def submit_attempt(
        payload: SupervisorAttemptRequest,
        _machine: None = Depends(require_machine),
    ) -> SupervisorAttemptStatus:
        if payload.spec_sha256 not in allowed_spec_sha256:
            raise HTTPException(
                status_code=403,
                detail={"code": "spec_not_allowed", "message": "spec hash is not allowed"},
            )

        if canonical_sha256(payload.input_bundle) != payload.input_sha256:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "input_hash_mismatch",
                    "message": "input_sha256 does not match input_bundle",
                },
            )

        request_sha256 = payload.request_sha256()
        with attempts_lock:
            existing = attempts.get(payload.attempt_id)
            if existing is not None:
                if existing.request_sha256 != request_sha256:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "attempt_conflict",
                            "message": "attempt_id already has a different request hash",
                        },
                    )
                return existing

            accepted = SupervisorAttemptStatus(
                attempt_id=payload.attempt_id,
                request_sha256=request_sha256,
                state="accepted",
            )
            attempts[payload.attempt_id] = accepted
            dispatch(payload)
            return accepted

    @app.get("/v1/attempts/{attempt_id}", response_model=SupervisorAttemptStatus)
    def get_attempt_status(
        attempt_id: str,
        _machine: None = Depends(require_machine),
    ) -> SupervisorAttemptStatus:
        with attempts_lock:
            attempt = attempts.get(attempt_id)
        if attempt is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "attempt_not_found", "message": "attempt does not exist"},
            )
        return attempt

    return app
