"""Narrow authenticated HTTP boundary for Harness execution.

The service is intentionally not a Docker API proxy. Product workers submit a
versioned Attempt contract; later phases compile that contract into the fixed
container policy owned by this service.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from secrets import compare_digest
from threading import Lock
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from contracts.receipt import ExecutionReceipt

from .service_contracts import (
    SupervisorAttemptRequest,
    SupervisorAttemptResult,
    SupervisorAttemptStatus,
    canonical_sha256,
)
from .journal import AttemptJournalRecord, FileAttemptJournal
from .lifecycle import FileAttemptResultStore


_AUTHENTICATION_DETAIL = {
    "code": "machine_authentication_required",
    "message": "valid supervisor machine credential required",
}
_TERMINAL_STATES = {"succeeded", "failed", "cancelled", "timed_out", "orphaned"}


def create_supervisor_app(
    *,
    machine_token: str,
    allowed_spec_sha256: frozenset[str],
    dispatch: Callable[[SupervisorAttemptRequest], None],
    cancel_attempt: Callable[[str, str], ExecutionReceipt] | None = None,
    recover_orphan: Callable[[str, str], ExecutionReceipt] | None = None,
    journal: FileAttemptJournal | None = None,
    result_store: FileAttemptResultStore | None = None,
    clock: Callable[[], datetime] | None = None,
    lease_seconds: int = 30,
) -> FastAPI:
    """Build the internal Supervisor API with one machine credential."""

    if not machine_token:
        raise ValueError("machine_token must not be empty")
    if lease_seconds < 1:
        raise ValueError("lease_seconds must be positive")

    app = FastAPI(title="Clinical Harness Supervisor", docs_url=None, redoc_url=None)
    attempts: dict[str, SupervisorAttemptStatus] = {}
    attempts_lock = Lock()
    now = clock or (lambda: datetime.now(timezone.utc))

    def journal_status(record: AttemptJournalRecord) -> SupervisorAttemptStatus:
        return SupervisorAttemptStatus(
            attempt_id=record.attempt_id,
            request_sha256=record.request_sha256,
            state=record.state,
            receipt=record.receipt,
        )

    def get_status(attempt_id: str) -> SupervisorAttemptStatus | None:
        if journal is not None:
            record = journal.get(attempt_id)
            return journal_status(record) if record is not None else None
        return attempts.get(attempt_id)

    if journal is not None and recover_orphan is not None:
        for active_record in journal.list_active():
            orphan_receipt = recover_orphan(
                active_record.attempt_id,
                active_record.request_sha256,
            )
            if result_store is not None:
                result_store.put(
                    attempt_id=active_record.attempt_id,
                    request_sha256=active_record.request_sha256,
                    output_bundle=None,
                )
            journal.complete(
                active_record.attempt_id,
                state="orphaned",
                receipt=orphan_receipt,
            )

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
            existing = get_status(payload.attempt_id)
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
            if journal is not None:
                record = journal.create(
                    attempt_id=payload.attempt_id,
                    request_sha256=request_sha256,
                    lease_expires_at=now() + timedelta(seconds=lease_seconds),
                )
                accepted = journal_status(record)
            else:
                attempts[payload.attempt_id] = accepted
            dispatch(payload)
            return accepted

    @app.get("/v1/attempts/{attempt_id}", response_model=SupervisorAttemptStatus)
    def get_attempt_status(
        attempt_id: str,
        _machine: None = Depends(require_machine),
    ) -> SupervisorAttemptStatus:
        with attempts_lock:
            attempt = get_status(attempt_id)
        if attempt is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "attempt_not_found", "message": "attempt does not exist"},
            )
        return attempt

    @app.post(
        "/v1/attempts/{attempt_id}/heartbeat",
        response_model=SupervisorAttemptStatus,
    )
    def heartbeat_attempt(
        attempt_id: str,
        _machine: None = Depends(require_machine),
    ) -> SupervisorAttemptStatus:
        if journal is None:
            attempt = get_status(attempt_id)
            if attempt is None:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "attempt_not_found", "message": "attempt does not exist"},
                )
            return attempt
        try:
            with attempts_lock:
                record = journal.heartbeat(
                    attempt_id,
                    now=now(),
                    lease_seconds=lease_seconds,
                )
        except KeyError:
            raise HTTPException(
                status_code=404,
                detail={"code": "attempt_not_found", "message": "attempt does not exist"},
            ) from None
        return journal_status(record)

    @app.post(
        "/v1/attempts/{attempt_id}/cancel",
        response_model=SupervisorAttemptStatus,
    )
    def cancel_managed_attempt(
        attempt_id: str,
        _machine: None = Depends(require_machine),
    ) -> SupervisorAttemptStatus:
        with attempts_lock:
            current = get_status(attempt_id)
            if current is None:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "attempt_not_found", "message": "attempt does not exist"},
                )
            if current.state in _TERMINAL_STATES:
                return current
            if cancel_attempt is None:
                raise HTTPException(
                    status_code=503,
                    detail={"code": "cancel_unavailable", "message": "cancel is unavailable"},
                )
            receipt = cancel_attempt(attempt_id, current.request_sha256)
            if journal is not None:
                if result_store is not None:
                    result_store.put(
                        attempt_id=attempt_id,
                        request_sha256=current.request_sha256,
                        output_bundle=None,
                    )
                record = journal.complete(
                    attempt_id,
                    state="cancelled",
                    receipt=receipt,
                )
                return journal_status(record)
            cancelled = current.model_copy(
                update={"state": "cancelled", "receipt": receipt}
            )
            attempts[attempt_id] = cancelled
            return cancelled

    @app.get(
        "/v1/attempts/{attempt_id}/result",
        response_model=SupervisorAttemptResult,
    )
    def get_attempt_result(
        attempt_id: str,
        _machine: None = Depends(require_machine),
    ) -> SupervisorAttemptResult:
        current = get_status(attempt_id)
        if current is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "attempt_not_found", "message": "attempt does not exist"},
            )
        if current.state not in _TERMINAL_STATES:
            raise HTTPException(
                status_code=409,
                detail={"code": "result_not_ready", "message": "attempt is not terminal"},
            )
        stored = result_store.get(attempt_id) if result_store is not None else None
        if current.receipt is None or stored is None:
            raise HTTPException(
                status_code=500,
                detail={"code": "result_missing", "message": "terminal result is unavailable"},
            )
        if stored.request_sha256 != current.request_sha256:
            raise HTTPException(
                status_code=500,
                detail={"code": "result_hash_mismatch", "message": "terminal result hash mismatch"},
            )
        return SupervisorAttemptResult(
            attempt_id=attempt_id,
            request_sha256=current.request_sha256,
            receipt=current.receipt,
            output_sha256=stored.output_sha256,
            output_bundle=stored.output_bundle,
        )

    return app
