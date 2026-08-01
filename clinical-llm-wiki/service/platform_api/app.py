"""FastAPI application for the P12 prerelease read boundary."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Callable, TypeVar

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    Query,
    Request,
    Response,
    Security,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.security import APIKeyCookie
from sqlalchemy.exc import SQLAlchemyError

from service.auth import (
    ActorContext,
    AuthorizationError,
    Permission,
    require_permission,
)
from service.auth.password_sessions import (
    AccountLockedError,
    AuthenticatedPrincipal,
    InvalidCredentialsError,
    PasswordChangeError,
    PasswordPolicyError,
    PasswordSessionService,
    SessionAuthenticationError,
    UserConflictError,
    UserManagementError,
    UserNotFoundError,
)
from service.governance import KnowledgeGovernanceService
from service.governance.service import (
    CandidateNotFoundError,
    DuplicateDecisionError,
    InvalidGovernanceTransitionError,
    RevisionNotFoundError,
    StaleRevisionError,
)
from service.knowledge import (
    AuthorConfirmationCommand,
    CandidateRevisionCommand,
    ReviewDecisionCommand,
)
from service.processing.ledger import (
    LedgerError,
    ProcessingLedgerPort,
    RetryNotAllowedError,
)
from service.sources import (
    DataBoundary,
    RegistrationConflictError,
    RightsClassification,
    RightsPolicy,
    SourceRegistrationCommand,
    SourceRegistrationError,
    SourceRegistryService,
    UnsupportedSourceMediaError,
)

from .contracts import (
    AuditEventCollectionData,
    AuditEventCollectionResponse,
    AuditEventData,
    AuditVersionData,
    AdminTemporaryPasswordData,
    AdminTemporaryPasswordResponse,
    AuthorConfirmationData,
    AuthorConfirmationRequest,
    AuthorConfirmationResponse,
    CandidateCollectionData,
    CandidateAdvisorySignalData,
    CandidateCollectionResponse,
    CandidateDetailData,
    CandidateDetailResponse,
    CandidateEvidenceData,
    CandidateRelationProposalData,
    CandidateRevisionData,
    CandidateRevisionRequest,
    CandidateRevisionResponse,
    CandidateSummaryData,
    CurrentReleaseData,
    CurrentReleaseResponse,
    CancelData,
    CancelResponse,
    ErrorData,
    ErrorResponse,
    HealthResponse,
    LoginRequest,
    ModelProfileCollectionData,
    ModelProfileCollectionResponse,
    ModelProfileData,
    ModelProfileRegistrationData,
    ModelProfileRegistrationRequest,
    ModelProfileRegistrationResponse,
    PlatformHealthData,
    PlatformUserData,
    PasswordChangeRequest,
    ObjectReferenceData,
    ProcessingAttemptData,
    ProcessingRunCollectionData,
    ProcessingRunCollectionResponse,
    ProcessingRunData,
    ProcessingRunResponse,
    ProcessingStepData,
    RelationEdgeData,
    RelationEvidenceData,
    RelationNodeData,
    RelationQueryData,
    RelationQueryResponse,
    ReviewDecisionData,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ResponseMeta,
    RetryData,
    RetryResponse,
    SessionData,
    SessionResponse,
    ServiceAccountCollectionData,
    ServiceAccountCollectionResponse,
    ServiceAccountData,
    SourceCollectionData,
    SourceCollectionResponse,
    SourceRegistrationData,
    SourceRegistrationResponse,
    SourceSummaryData,
    UserCollectionData,
    UserCollectionResponse,
    UserCreateRequest,
    UserStatusData,
    UserStatusRequest,
    UserStatusResponse,
)
from .repository import (
    ModelProfileConflictError,
    ModelProfileRecord,
    PlatformReadRepository,
    ProcessingRunRecord,
)


API_PREFIX = "/api/prerelease/v1"
MAX_SOURCE_BYTES = 64 * 1024 * 1024
_ResponseModel = TypeVar("_ResponseModel", bound=BaseModel)
SESSION_COOKIE_NAME = "clinical_knowledge_session"
_session_cookie = APIKeyCookie(
    name=SESSION_COOKIE_NAME,
    auto_error=False,
    scheme_name="sessionCookie",
)


@dataclass(frozen=True, slots=True)
class PlatformApiServices:
    """Explicit ports and capability flags required by the HTTP adapter."""

    repository: PlatformReadRepository
    password_sessions: PasswordSessionService
    organization_name: str
    allowed_browser_origins: frozenset[str]
    secure_session_cookie: bool
    object_store_available: bool = False
    semantic_index_available: bool = False
    source_registry: SourceRegistryService | None = None
    processing_ledger: ProcessingLedgerPort | None = None
    governance: KnowledgeGovernanceService | None = None


class PlatformApiError(RuntimeError):
    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _meta() -> ResponseMeta:
    return ResponseMeta(generated_at=_now())


def _dump(model: _ResponseModel) -> dict[str, object]:
    return model.model_dump(by_alias=True, mode="json")


def create_platform_app(services: PlatformApiServices) -> FastAPI:
    """Create the real prerelease API without mutating infrastructure."""

    app = FastAPI(
        title="Clinical Knowledge Application Platform API",
        version="prerelease-v1",
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )

    @app.middleware("http")
    async def enforce_browser_csrf(request: Request, call_next):
        if request.url.path.startswith(API_PREFIX) and request.method in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }:
            origin = request.headers.get("origin")
            marker = request.headers.get("x-csrf-protection")
            if origin not in services.allowed_browser_origins or marker != "1":
                response = ErrorResponse(
                    error=ErrorData(
                        code="csrf_rejected",
                        message="请求来源验证失败。",
                    ),
                    meta=_meta(),
                )
                return JSONResponse(status_code=403, content=_dump(response))
        return await call_next(request)

    @app.exception_handler(PlatformApiError)
    async def handle_platform_api_error(
        _request: Request,
        error: PlatformApiError,
    ) -> JSONResponse:
        response = ErrorResponse(
            error=ErrorData(code=error.code, message=error.message),
            meta=_meta(),
        )
        return JSONResponse(status_code=error.status_code, content=_dump(response))

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        _request: Request,
        _error: RequestValidationError,
    ) -> JSONResponse:
        response = ErrorResponse(
            error=ErrorData(
                code="invalid_request",
                message="The request payload failed validation.",
            ),
            meta=_meta(),
        )
        return JSONResponse(status_code=422, content=_dump(response))

    def get_principal(
        raw_session_id: Annotated[str | None, Security(_session_cookie)] = None,
    ) -> AuthenticatedPrincipal:
        try:
            return services.password_sessions.authenticate_session(raw_session_id or "")
        except SessionAuthenticationError as exc:
            raise PlatformApiError(
                status_code=401,
                code="authentication_required",
                message="需要登录。",
            ) from exc
        except SQLAlchemyError as exc:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="The authorization store is unavailable.",
            ) from exc

    def get_actor(
        principal: Annotated[AuthenticatedPrincipal, Depends(get_principal)],
    ) -> ActorContext:
        if principal.must_change_password:
            raise PlatformApiError(
                status_code=403,
                code="password_change_required",
                message="必须先修改密码。",
            )
        return principal.actor

    def permitted(permission: Permission) -> Callable[[ActorContext], ActorContext]:
        def dependency(actor: Annotated[ActorContext, Depends(get_actor)]) -> ActorContext:
            try:
                require_permission(actor, permission)
            except AuthorizationError as exc:
                raise PlatformApiError(
                    status_code=403,
                    code="permission_denied",
                    message="The current actor does not have this permission.",
                ) from exc
            return actor

        return dependency

    protected_responses = {
        401: {"model": ErrorResponse, "description": "Identity is missing or invalid."},
        403: {"model": ErrorResponse, "description": "Permission is denied."},
        503: {"model": ErrorResponse, "description": "A required service is unavailable."},
    }
    write_responses = {
        **protected_responses,
        409: {"model": ErrorResponse, "description": "A durable state conflict exists."},
        415: {"model": ErrorResponse, "description": "The source media is unsupported."},
        422: {"model": ErrorResponse, "description": "Source facts failed validation."},
    }

    @app.get(
        f"{API_PREFIX}/health",
        operation_id="getPlatformHealth",
        response_model=HealthResponse,
    )
    def get_health() -> HealthResponse:
        database_available = services.repository.database_available()
        object_store = "available" if services.object_store_available else "disabled"
        semantic_index = "available" if services.semantic_index_available else "disabled"
        overall = (
            "healthy"
            if database_available
            and services.object_store_available
            and services.semantic_index_available
            else "degraded"
        )
        return HealthResponse(
            data=PlatformHealthData(
                status=overall,
                api="available",
                database="available" if database_available else "degraded",
                object_store=object_store,
                semantic_index=semantic_index,
                checked_at=_now(),
            ),
            meta=_meta(),
        )

    def set_session_cookie(response: Response, raw_session_id: str) -> None:
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=raw_session_id,
            httponly=True,
            secure=services.secure_session_cookie,
            samesite="strict",
            path="/",
        )

    def session_response(principal: AuthenticatedPrincipal) -> SessionResponse:
        actor = principal.actor
        return SessionResponse(
            data=SessionData(
                actor_id=actor.actor_id,
                display_name=actor.display_name,
                roles=sorted(actor.roles, key=lambda role: role.value),
                organization=services.organization_name,
                permissions=sorted(
                    actor.permissions,
                    key=lambda permission: permission.value,
                ),
                must_change_password=principal.must_change_password,
                session_expires_at=principal.expires_at,
            ),
            meta=_meta(),
        )

    @app.post(
        f"{API_PREFIX}/auth/login",
        operation_id="login",
        response_model=SessionResponse,
    )
    def login(payload: LoginRequest, response: Response) -> SessionResponse:
        try:
            login_session = services.password_sessions.login(
                username=payload.username,
                password=payload.password.get_secret_value(),
            )
        except AccountLockedError as exc:
            raise PlatformApiError(
                status_code=423,
                code="account_locked",
                message="登录失败次数过多，请稍后重试。",
            ) from exc
        except (InvalidCredentialsError, PasswordPolicyError) as exc:
            raise PlatformApiError(
                status_code=401,
                code="invalid_credentials",
                message="用户名或密码错误。",
            ) from exc
        set_session_cookie(response, login_session.raw_session_id)
        return session_response(login_session)

    @app.post(
        f"{API_PREFIX}/auth/password/change",
        operation_id="changePassword",
        response_model=SessionResponse,
        responses=protected_responses,
    )
    def change_password(
        payload: PasswordChangeRequest,
        request: Request,
        response: Response,
        _principal: Annotated[AuthenticatedPrincipal, Depends(get_principal)],
    ) -> SessionResponse:
        try:
            replacement = services.password_sessions.change_password(
                raw_session_id=request.cookies.get(SESSION_COOKIE_NAME, ""),
                current_password=payload.current_password.get_secret_value(),
                new_password=payload.new_password.get_secret_value(),
            )
        except PasswordChangeError as exc:
            raise PlatformApiError(
                status_code=401,
                code="current_password_invalid",
                message="当前密码错误。",
            ) from exc
        except PasswordPolicyError as exc:
            raise PlatformApiError(
                status_code=422,
                code="password_policy_failed",
                message="新密码不符合安全要求。",
            ) from exc
        set_session_cookie(response, replacement.raw_session_id)
        return session_response(replacement)

    @app.post(
        f"{API_PREFIX}/auth/logout",
        operation_id="logout",
        status_code=204,
        responses=protected_responses,
    )
    def logout(
        request: Request,
        response: Response,
        _principal: Annotated[AuthenticatedPrincipal, Depends(get_principal)],
    ) -> None:
        services.password_sessions.logout(request.cookies.get(SESSION_COOKIE_NAME, ""))
        response.delete_cookie(
            key=SESSION_COOKIE_NAME,
            path="/",
            httponly=True,
            secure=services.secure_session_cookie,
            samesite="strict",
        )

    @app.get(
        f"{API_PREFIX}/session",
        operation_id="getSession",
        response_model=SessionResponse,
        responses=protected_responses,
    )
    def get_session(
        principal: Annotated[AuthenticatedPrincipal, Depends(get_principal)],
    ) -> SessionResponse:
        return session_response(principal)

    @app.get(
        f"{API_PREFIX}/releases/current",
        operation_id="getCurrentRelease",
        response_model=CurrentReleaseResponse,
        responses=protected_responses,
    )
    def get_current_release(
        _actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.QUERY_RELEASED)),
        ],
    ) -> CurrentReleaseResponse:
        try:
            release = services.repository.get_current_release()
        except SQLAlchemyError as exc:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="The release repository is unavailable.",
            ) from exc
        data = (
            CurrentReleaseData(
                release_id=release.release_id,
                version=release.version,
                status="released",
                index_version=release.index_version,
                released_at=release.released_at,
            )
            if release is not None
            else CurrentReleaseData(
                release_id=None,
                version=None,
                status="not_released",
                index_version=None,
                released_at=None,
            )
        )
        return CurrentReleaseResponse(data=data, meta=_meta())

    @app.get(
        f"{API_PREFIX}/sources",
        operation_id="listSources",
        response_model=SourceCollectionResponse,
        responses=protected_responses,
    )
    def list_sources(
        _actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.SOURCE_READ)),
        ],
    ) -> SourceCollectionResponse:
        try:
            records, warnings = services.repository.list_sources()
        except SQLAlchemyError as exc:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="The source repository is unavailable.",
            ) from exc
        items = [
            SourceSummaryData(
                source_id=record.source_id,
                title=record.title,
                version=record.version,
                media_type=record.media_type,
                rights=record.rights,
                status=record.status,
                source_hash=record.source_hash,
                updated_at=record.updated_at,
            )
            for record in records
        ]
        return SourceCollectionResponse(
            data=SourceCollectionData(
                items=items,
                total=len(items),
                partial=bool(warnings),
                warnings=list(warnings),
            ),
            meta=_meta(),
        )

    @app.post(
        f"{API_PREFIX}/sources",
        operation_id="registerSource",
        response_model=SourceRegistrationResponse,
        status_code=202,
        responses=write_responses,
    )
    async def register_source(
        actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.SOURCE_REGISTER)),
        ],
        idempotency_key: Annotated[
            str,
            Header(alias="Idempotency-Key", min_length=8, max_length=160),
        ],
        source_id: Annotated[str, Form(min_length=5, max_length=160)],
        title: Annotated[str, Form(min_length=1, max_length=500)],
        source_type: Annotated[str, Form(min_length=1, max_length=80)],
        version: Annotated[str, Form(min_length=1, max_length=120)],
        rights_classification: Annotated[str, Form()],
        storage_allowed: Annotated[bool, Form()],
        data_boundary: Annotated[str, Form()],
        media_type: Annotated[str, Form(min_length=1, max_length=255)],
        expected_sha256: Annotated[
            str,
            Form(pattern=r"^[0-9a-f]{64}$"),
        ],
        file: Annotated[UploadFile, File()],
    ) -> SourceRegistrationResponse:
        if services.source_registry is None:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="Source registration is not configured.",
            )
        content = bytearray()
        try:
            while chunk := await file.read(1024 * 1024):
                content.extend(chunk)
                if len(content) > MAX_SOURCE_BYTES:
                    raise PlatformApiError(
                        status_code=422,
                        code="invalid_source",
                        message="Source exceeds the prerelease upload limit.",
                    )
        finally:
            await file.close()
        try:
            command = SourceRegistrationCommand(
                source_id=source_id,
                title=title,
                source_type=source_type,
                version=version,
                rights=RightsPolicy(
                    classification=RightsClassification(rights_classification),
                    storage_allowed=storage_allowed,
                ),
                data_boundary=DataBoundary(data_boundary),
                media_type=media_type,
                expected_sha256=expected_sha256,
                idempotency_key=idempotency_key,
            )
            receipt = services.source_registry.register_and_start(
                actor=actor,
                command=command,
                content=bytes(content),
            )
        except RegistrationConflictError as exc:
            raise PlatformApiError(
                status_code=409,
                code="registration_conflict",
                message="The source version or idempotency key conflicts with existing facts.",
            ) from exc
        except UnsupportedSourceMediaError as exc:
            raise PlatformApiError(
                status_code=415,
                code="unsupported_media",
                message="The declared media type is unsupported or mismatched.",
            ) from exc
        except (SourceRegistrationError, ValueError) as exc:
            status_code = 503 if "processing run could not be started" in str(exc) else 422
            code = "service_unavailable" if status_code == 503 else "invalid_source"
            raise PlatformApiError(
                status_code=status_code,
                code=code,
                message=(
                    "The registered source could not start processing."
                    if status_code == 503
                    else "The source registration facts failed validation."
                ),
            ) from exc
        return SourceRegistrationResponse(
            data=SourceRegistrationData(
                source_id=receipt.source_id,
                source_version_id=receipt.source_version_id,
                run_id=receipt.run_id,
                status=receipt.status,
                original_object=ObjectReferenceData(
                    **receipt.original_object.model_dump(),
                    artifact_role="original",
                ),
            ),
            meta=_meta(),
        )

    @app.get(
        f"{API_PREFIX}/processing-runs",
        operation_id="listProcessingRuns",
        response_model=ProcessingRunCollectionResponse,
        responses=protected_responses,
    )
    def list_processing_runs(
        _actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.PROCESSING_READ)),
        ],
    ) -> ProcessingRunCollectionResponse:
        try:
            records, warnings = services.repository.list_processing_runs()
        except SQLAlchemyError as exc:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="The processing repository is unavailable.",
            ) from exc
        return ProcessingRunCollectionResponse(
            data=ProcessingRunCollectionData(
                items=[_processing_run_data(record) for record in records],
                total=len(records),
                partial=bool(warnings),
                warnings=list(warnings),
            ),
            meta=_meta(),
        )

    @app.get(
        f"{API_PREFIX}/processing-runs/{{run_id}}",
        operation_id="getProcessingRun",
        response_model=ProcessingRunResponse,
        responses={
            **protected_responses,
            404: {"model": ErrorResponse, "description": "The run does not exist."},
        },
    )
    def get_processing_run(
        run_id: str,
        _actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.PROCESSING_READ)),
        ],
    ) -> ProcessingRunResponse:
        try:
            record = services.repository.get_processing_run(run_id=run_id)
        except SQLAlchemyError as exc:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="The processing repository is unavailable.",
            ) from exc
        if record is None:
            raise PlatformApiError(
                status_code=404,
                code="run_not_found",
                message="The processing run does not exist.",
            )
        return ProcessingRunResponse(data=_processing_run_data(record), meta=_meta())

    @app.get(
        f"{API_PREFIX}/candidates",
        operation_id="listCandidates",
        response_model=CandidateCollectionResponse,
        responses=protected_responses,
    )
    def list_candidates(
        _actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.CANDIDATE_READ)),
        ],
    ) -> CandidateCollectionResponse:
        try:
            records, warnings = services.repository.list_candidates()
        except SQLAlchemyError as exc:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="The candidate repository is unavailable.",
            ) from exc
        return CandidateCollectionResponse(
            data=CandidateCollectionData(
                items=[
                    CandidateSummaryData(
                        candidate_id=record.candidate_id,
                        candidate_group_id=record.candidate_group_id,
                        run_id=record.run_id,
                        revision_number=record.revision_number,
                        status=record.status,
                        knowledge_type=record.knowledge_type,
                        claim=record.claim,
                        scope=record.scope,
                        applicability=record.applicability,
                        content_sha256=record.content_sha256,
                        evidence_count=record.evidence_count,
                        relation_proposal_count=record.relation_proposal_count,
                        author_actor_id=record.author_actor_id,
                        knowledge_revision_id=record.knowledge_revision_id,
                        review_status=record.review_status,
                    )
                    for record in records
                ],
                total=len(records),
                partial=bool(warnings),
                warnings=list(warnings),
            ),
            meta=_meta(),
        )

    @app.get(
        f"{API_PREFIX}/candidates/{{candidate_id}}",
        operation_id="getCandidate",
        response_model=CandidateDetailResponse,
        responses={
            **protected_responses,
            404: {"model": ErrorResponse, "description": "The candidate does not exist."},
        },
    )
    def get_candidate(
        candidate_id: str,
        _actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.CANDIDATE_READ)),
        ],
    ) -> CandidateDetailResponse:
        try:
            record = services.repository.get_candidate_detail(candidate_id=candidate_id)
        except SQLAlchemyError as exc:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="The candidate repository is unavailable.",
            ) from exc
        if record is None:
            raise PlatformApiError(
                status_code=404,
                code="candidate_not_found",
                message="The governed candidate does not exist.",
            )
        return CandidateDetailResponse(
            data=CandidateDetailData(
                candidate_id=record.candidate_id,
                candidate_group_id=record.candidate_group_id,
                run_id=record.run_id,
                revision_number=record.revision_number,
                status=record.status,
                knowledge_type=record.knowledge_type,
                claim=record.claim,
                scope=record.scope,
                applicability=record.applicability,
                content_sha256=record.content_sha256,
                evidence_count=record.evidence_count,
                relation_proposal_count=record.relation_proposal_count,
                author_actor_id=record.author_actor_id,
                knowledge_revision_id=record.knowledge_revision_id,
                review_status=record.review_status,
                parent_candidate_id=record.parent_candidate_id,
                conditions=list(record.conditions),
                exceptions=list(record.exceptions),
                evidence=[
                    CandidateEvidenceData(
                        evidence_id=item.evidence_id,
                        source_version_id=item.source_version_id,
                        locator=item.locator,
                        content=item.content,
                        content_sha256=item.content_sha256,
                        rights=item.rights,
                    )
                    for item in record.evidence
                ],
                relation_proposals=[
                    CandidateRelationProposalData(
                        relation_type=item.relation_type,
                        target_knowledge_unit_id=item.target_knowledge_unit_id,
                        evidence_ids=list(item.evidence_ids),
                        status=item.status,
                    )
                    for item in record.relation_proposals
                ],
                advisory_signals=[
                    CandidateAdvisorySignalData(
                        signal_type=item.signal_type,
                        description=item.description,
                        target_knowledge_unit_id=item.target_knowledge_unit_id,
                        evidence_ids=list(item.evidence_ids),
                    )
                    for item in record.advisory_signals
                ],
                origin_model_invocation_id=record.origin_model_invocation_id,
            ),
            meta=_meta(),
        )

    @app.post(
        f"{API_PREFIX}/candidates/{{candidate_id}}/revisions",
        operation_id="reviseCandidate",
        response_model=CandidateRevisionResponse,
        status_code=201,
        responses=write_responses,
    )
    def revise_candidate(
        candidate_id: str,
        request: CandidateRevisionRequest,
        actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.CANDIDATE_WRITE)),
        ],
    ) -> CandidateRevisionResponse:
        if services.governance is None:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="Knowledge governance is not configured.",
            )
        try:
            candidate = services.governance.revise_candidate(
                actor=actor,
                command=CandidateRevisionCommand(
                    candidate_id=candidate_id,
                    expected_revision_number=request.expected_revision_number,
                    expected_content_sha256=request.expected_content_sha256,
                    claim=request.claim,
                    scope=request.scope,
                    applicability=request.applicability,
                    conditions=request.conditions,
                    exceptions=request.exceptions,
                    idempotency_key=request.idempotency_key,
                ),
            )
        except Exception as exc:
            _raise_governance_api_error(exc)
        return CandidateRevisionResponse(
            data=CandidateRevisionData(
                candidate_id=candidate.candidate_id,
                parent_candidate_id=candidate.parent_candidate_id,
                revision_number=candidate.revision_number,
                content_sha256=candidate.content_sha256,
                status=candidate.status,
            ),
            meta=_meta(),
        )

    @app.post(
        f"{API_PREFIX}/candidates/{{candidate_id}}/author-confirmation",
        operation_id="confirmCandidateAuthor",
        response_model=AuthorConfirmationResponse,
        responses=write_responses,
    )
    def confirm_candidate_author(
        candidate_id: str,
        request: AuthorConfirmationRequest,
        actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.CANDIDATE_SUBMIT)),
        ],
    ) -> AuthorConfirmationResponse:
        if services.governance is None:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="Knowledge governance is not configured.",
            )
        try:
            receipt = services.governance.confirm_candidate(
                actor=actor,
                command=AuthorConfirmationCommand(
                    candidate_id=candidate_id,
                    expected_revision_number=request.expected_revision_number,
                    expected_content_sha256=request.expected_content_sha256,
                    idempotency_key=request.idempotency_key,
                ),
            )
        except Exception as exc:
            _raise_governance_api_error(exc)
        return AuthorConfirmationResponse(
            data=AuthorConfirmationData(
                candidate_id=receipt.candidate.candidate_id,
                candidate_status=receipt.candidate.status,
                knowledge_revision_id=receipt.revision.knowledge_revision_id,
                revision_status=receipt.revision.status,
                decision_id=receipt.decision_id,
            ),
            meta=_meta(),
        )

    @app.post(
        f"{API_PREFIX}/knowledge-revisions/{{revision_id}}/review-decision",
        operation_id="decideKnowledgeRevision",
        response_model=ReviewDecisionResponse,
        responses=write_responses,
    )
    def decide_knowledge_revision(
        revision_id: str,
        request: ReviewDecisionRequest,
        actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.REVIEW_DECIDE)),
        ],
    ) -> ReviewDecisionResponse:
        if services.governance is None:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="Knowledge governance is not configured.",
            )
        try:
            receipt = services.governance.review_revision(
                actor=actor,
                command=ReviewDecisionCommand(
                    candidate_id=request.candidate_id,
                    knowledge_revision_id=revision_id,
                    expected_revision_number=request.expected_revision_number,
                    expected_content_sha256=request.expected_content_sha256,
                    decision=request.decision,
                    idempotency_key=request.idempotency_key,
                    rationale=request.rationale,
                ),
            )
        except Exception as exc:
            _raise_governance_api_error(exc)
        return ReviewDecisionResponse(
            data=ReviewDecisionData(
                candidate_id=receipt.revision.candidate_id,
                knowledge_revision_id=receipt.revision.knowledge_revision_id,
                revision_status=receipt.revision.status,
                decision_id=receipt.decision_id,
            ),
            meta=_meta(),
        )

    @app.post(
        f"{API_PREFIX}/processing-runs/{{run_id}}/steps/{{step_id}}/retry",
        operation_id="retryProcessingStep",
        response_model=RetryResponse,
        status_code=202,
        responses=write_responses,
    )
    def retry_processing_step(
        run_id: str,
        step_id: str,
        actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.PROCESSING_RETRY)),
        ],
    ) -> RetryResponse:
        if services.processing_ledger is None:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="Processing control is not configured.",
            )
        try:
            attempt_id = services.processing_ledger.retry_step(
                actor=actor,
                run_id=run_id,
                step_id=step_id,
            )
        except RetryNotAllowedError as exc:
            raise PlatformApiError(
                status_code=409,
                code="retry_not_allowed",
                message="The latest step attempt cannot be retried.",
            ) from exc
        return RetryResponse(
            data=RetryData(
                run_id=run_id,
                step_id=step_id,
                attempt_id=attempt_id,
            ),
            meta=_meta(),
        )

    @app.post(
        f"{API_PREFIX}/processing-runs/{{run_id}}/cancel",
        operation_id="cancelProcessingRun",
        response_model=CancelResponse,
        status_code=202,
        responses=write_responses,
    )
    def cancel_processing_run(
        run_id: str,
        actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.PROCESSING_START)),
        ],
    ) -> CancelResponse:
        if services.processing_ledger is None:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="Processing control is not configured.",
            )
        try:
            services.processing_ledger.cancel_run(actor=actor, run_id=run_id)
        except LedgerError as exc:
            raise PlatformApiError(
                status_code=409,
                code="retry_not_allowed",
                message="The processing run cannot be cancelled.",
            ) from exc
        return CancelResponse(data=CancelData(run_id=run_id), meta=_meta())

    @app.get(
        f"{API_PREFIX}/relations/query",
        operation_id="queryRelations",
        response_model=RelationQueryResponse,
        responses=protected_responses,
    )
    def query_relations(
        _actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.CANDIDATE_READ)),
        ],
        node_id: Annotated[str | None, Query(max_length=160)] = None,
        q: Annotated[str | None, Query(max_length=240)] = None,
        depth: Annotated[int, Query(ge=0, le=8)] = 1,
    ) -> RelationQueryResponse:
        try:
            record = services.repository.query_relations(
                node_id=node_id,
                query=q,
                depth=depth,
            )
        except SQLAlchemyError as exc:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="The relation repository is unavailable.",
            ) from exc
        return RelationQueryResponse(
            data=RelationQueryData(
                root_node_id=record.root_node_id,
                requested_depth=record.requested_depth,
                applied_depth=record.applied_depth,
                nodes=[
                    RelationNodeData(
                        knowledge_unit_id=node.knowledge_unit_id,
                        stable_key=node.stable_key,
                        knowledge_type=node.knowledge_type,
                        knowledge_revision_id=node.knowledge_revision_id,
                        revision_number=node.revision_number,
                        status=node.status,
                        claim=node.claim,
                        release_ids=list(node.release_ids),
                    )
                    for node in record.nodes
                ],
                edges=[
                    RelationEdgeData(
                        relation_id=edge.relation_id,
                        source_knowledge_unit_id=edge.source_knowledge_unit_id,
                        target_knowledge_unit_id=edge.target_knowledge_unit_id,
                        relation_type=edge.relation_type,
                        status=edge.status,
                        evidence=[
                            RelationEvidenceData(
                                evidence_id=evidence.evidence_id,
                                source_version_id=evidence.source_version_id,
                                locator=evidence.locator,
                                content=evidence.content,
                                content_sha256=evidence.content_sha256,
                            )
                            for evidence in edge.evidence
                        ],
                    )
                    for edge in record.edges
                ],
                total_nodes=record.total_nodes,
                truncated=record.truncated,
                partial=bool(record.warnings),
                warnings=list(record.warnings),
            ),
            meta=_meta(),
        )

    @app.get(
        f"{API_PREFIX}/audit-events",
        operation_id="listAuditEvents",
        response_model=AuditEventCollectionResponse,
        responses=protected_responses,
    )
    def list_audit_events(
        _actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.AUDIT_READ)),
        ],
        actor: Annotated[str | None, Query(max_length=160)] = None,
        action: Annotated[str | None, Query(max_length=160)] = None,
        object_type: Annotated[str | None, Query(max_length=120)] = None,
        result: Annotated[str | None, Query(max_length=120)] = None,
        cursor: Annotated[str | None, Query(max_length=160)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
    ) -> AuditEventCollectionResponse:
        try:
            page = services.repository.list_audit_events(
                actor=actor,
                action=action,
                object_type=object_type,
                result=result,
                cursor=cursor,
                limit=limit,
            )
        except SQLAlchemyError as exc:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="The audit repository is unavailable.",
            ) from exc
        return AuditEventCollectionResponse(
            data=AuditEventCollectionData(
                items=[
                    AuditEventData(
                        audit_event_id=event.audit_event_id,
                        actor_id=event.actor_id,
                        action=event.action,
                        object_type=event.object_type,
                        object_id=event.object_id,
                        run_id=event.run_id,
                        before_version=(
                            AuditVersionData(
                                revision_number=event.before_version.revision_number,
                                content_sha256=event.before_version.content_sha256,
                            )
                            if event.before_version is not None
                            else None
                        ),
                        after_version=(
                            AuditVersionData(
                                revision_number=event.after_version.revision_number,
                                content_sha256=event.after_version.content_sha256,
                            )
                            if event.after_version is not None
                            else None
                        ),
                        result=event.result,
                        correlation_id=event.correlation_id,
                        created_at=event.created_at,
                    )
                    for event in page.items
                ],
                total=page.total,
                next_cursor=page.next_cursor,
                partial=bool(page.warnings),
                warnings=list(page.warnings),
            ),
            meta=_meta(),
        )

    @app.get(
        f"{API_PREFIX}/admin/users",
        operation_id="listPlatformUsers",
        response_model=UserCollectionResponse,
        responses=protected_responses,
    )
    def list_platform_users(
        _actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.ADMIN_READ)),
        ],
    ) -> UserCollectionResponse:
        try:
            records, warnings = services.repository.list_platform_users()
        except SQLAlchemyError as exc:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="The user repository is unavailable.",
            ) from exc
        items = [
            PlatformUserData(
                user_id=record.user_id,
                display_name=record.display_name,
                email=record.email,
                identity_source=record.identity_source,
                roles=list(record.roles),
                status=record.status,
                last_active_at=record.last_active_at,
            )
            for record in records
        ]
        return UserCollectionResponse(
            data=UserCollectionData(
                items=items,
                total=len(items),
                partial=bool(warnings),
                warnings=list(warnings),
            ),
            meta=_meta(),
        )

    @app.get(
        f"{API_PREFIX}/admin/service-accounts",
        operation_id="listServiceAccounts",
        response_model=ServiceAccountCollectionResponse,
        responses=protected_responses,
    )
    def list_service_accounts(
        _actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.ADMIN_READ)),
        ],
    ) -> ServiceAccountCollectionResponse:
        try:
            records, warnings = services.repository.list_service_accounts()
        except SQLAlchemyError as exc:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="服务账号仓库不可用。",
            ) from exc
        items = [
            ServiceAccountData(
                service_account_id=record.service_account_id,
                display_name=record.display_name,
                worker_pool=record.worker_pool,
                scopes=list(record.scopes),
                status=record.status,
            )
            for record in records
        ]
        return ServiceAccountCollectionResponse(
            data=ServiceAccountCollectionData(
                items=items,
                total=len(items),
                partial=bool(warnings),
                warnings=list(warnings),
            ),
            meta=_meta(),
        )

    @app.post(
        f"{API_PREFIX}/admin/users",
        operation_id="createPlatformUser",
        response_model=AdminTemporaryPasswordResponse,
        status_code=201,
        responses=write_responses,
    )
    def create_platform_user(
        payload: UserCreateRequest,
        actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.ADMIN_MANAGE_USERS)),
        ],
    ) -> AdminTemporaryPasswordResponse:
        try:
            created = services.password_sessions.create_user(
                actor=actor,
                username=payload.username,
                display_name=payload.display_name,
                email=payload.email,
                roles=tuple(payload.roles),
            )
        except UserConflictError as exc:
            raise PlatformApiError(
                status_code=409,
                code="user_conflict",
                message="用户名已存在。",
            ) from exc
        except UserManagementError as exc:
            raise PlatformApiError(
                status_code=422,
                code="user_management_invalid",
                message="用户资料不符合要求。",
            ) from exc
        return AdminTemporaryPasswordResponse(
            data=AdminTemporaryPasswordData(
                user_id=created.user_id,
                username=created.username,
                temporary_password=created.temporary_password,
            ),
            meta=_meta(),
        )

    @app.post(
        f"{API_PREFIX}/admin/users/{{user_id}}/password/reset",
        operation_id="resetPlatformUserPassword",
        response_model=AdminTemporaryPasswordResponse,
        responses=write_responses,
    )
    def reset_platform_user_password(
        user_id: str,
        actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.ADMIN_MANAGE_USERS)),
        ],
    ) -> AdminTemporaryPasswordResponse:
        try:
            reset = services.password_sessions.reset_user_password(
                actor=actor,
                user_id=user_id,
            )
        except UserNotFoundError as exc:
            raise PlatformApiError(
                status_code=404,
                code="user_not_found",
                message="用户不存在。",
            ) from exc
        return AdminTemporaryPasswordResponse(
            data=AdminTemporaryPasswordData(
                user_id=reset.user_id,
                username=None,
                temporary_password=reset.temporary_password,
            ),
            meta=_meta(),
        )

    @app.post(
        f"{API_PREFIX}/admin/users/{{user_id}}/status",
        operation_id="setPlatformUserStatus",
        response_model=UserStatusResponse,
        responses=write_responses,
    )
    def set_platform_user_status(
        user_id: str,
        payload: UserStatusRequest,
        actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.ADMIN_MANAGE_USERS)),
        ],
    ) -> UserStatusResponse:
        try:
            services.password_sessions.set_user_status(
                actor=actor,
                user_id=user_id,
                status=payload.status,
            )
        except UserNotFoundError as exc:
            raise PlatformApiError(
                status_code=404,
                code="user_not_found",
                message="用户不存在。",
            ) from exc
        except UserManagementError as exc:
            raise PlatformApiError(
                status_code=422,
                code="user_management_invalid",
                message="用户状态变更不符合要求。",
            ) from exc
        return UserStatusResponse(
            data=UserStatusData(user_id=user_id, status=payload.status),
            meta=_meta(),
        )

    @app.get(
        f"{API_PREFIX}/admin/model-profiles",
        operation_id="listModelProfiles",
        response_model=ModelProfileCollectionResponse,
        responses=protected_responses,
    )
    def list_model_profiles(
        _actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.ADMIN_READ)),
        ],
    ) -> ModelProfileCollectionResponse:
        try:
            records, warnings = services.repository.list_model_profiles()
        except SQLAlchemyError as exc:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="The model profile registry is unavailable.",
            ) from exc
        items = [_model_profile_data(record) for record in records]
        return ModelProfileCollectionResponse(
            data=ModelProfileCollectionData(
                items=items,
                total=len(items),
                partial=bool(warnings),
                warnings=list(warnings),
            ),
            meta=_meta(),
        )

    @app.post(
        f"{API_PREFIX}/admin/model-profiles",
        operation_id="registerModelProfile",
        response_model=ModelProfileRegistrationResponse,
        status_code=201,
        responses={
            **protected_responses,
            409: {"model": ErrorResponse, "description": "Immutable version conflict."},
            422: {"model": ErrorResponse, "description": "Configuration failed validation."},
        },
    )
    def register_model_profile(
        request: ModelProfileRegistrationRequest,
        actor: Annotated[
            ActorContext,
            Depends(permitted(Permission.ADMIN_MANAGE_SERVICE_ACCOUNTS)),
        ],
        correlation_id: Annotated[
            str | None,
            Header(alias="X-Correlation-ID", max_length=160),
        ] = None,
    ) -> ModelProfileRegistrationResponse:
        safe_correlation_id = correlation_id or f"model-profile:{request.profile_id}:{request.version}"
        try:
            record, created = services.repository.register_model_profile(
                profile_id=request.profile_id,
                version=request.version,
                provider=request.provider,
                model=request.model,
                deployment_class=request.deployment_class,
                secret_ref=request.secret_ref,
                endpoint_ref=request.endpoint_ref,
                allowed_data_boundaries=request.allowed_data_boundaries,
                capabilities=request.capabilities,
                timeout_seconds=request.timeout_seconds,
                max_output_tokens=request.max_output_tokens,
                cost_policy=request.cost_policy,
                actor_id=actor.actor_id,
                correlation_id=safe_correlation_id,
            )
        except ModelProfileConflictError as exc:
            raise PlatformApiError(
                status_code=409,
                code="model_profile_conflict",
                message="This model profile ID/version is already registered with different configuration.",
            ) from exc
        except SQLAlchemyError as exc:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="The model profile registry is unavailable.",
            ) from exc
        return ModelProfileRegistrationResponse(
            data=ModelProfileRegistrationData(
                profile=_model_profile_data(record),
                created=created,
            ),
            meta=_meta(),
        )

    return app


def _processing_run_data(record: ProcessingRunRecord) -> ProcessingRunData:
    return ProcessingRunData(
        run_id=record.run_id,
        source_version_id=record.source_version_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        original_artifact_count=record.original_artifact_count,
        derived_artifact_count=record.derived_artifact_count,
        evidence_count=record.evidence_count,
        steps=[
            ProcessingStepData(
                step_id=step.step_id,
                step_key=step.step_key,
                pool=step.pool,
                status=step.status,
                depends_on=list(step.depends_on),
                latest_attempt=ProcessingAttemptData(
                    attempt_id=step.latest_attempt.attempt_id,
                    attempt_number=step.latest_attempt.attempt_number,
                    status=step.latest_attempt.status,
                    error_type=step.latest_attempt.error_type,
                    checkpoint=step.latest_attempt.checkpoint,
                    artifact_count=step.latest_attempt.artifact_count,
                ),
            )
            for step in record.steps
        ],
    )


def _model_profile_data(record: ModelProfileRecord) -> ModelProfileData:
    return ModelProfileData(
        profile_id=record.profile_id,
        version=record.version,
        provider=record.provider,
        model=record.model,
        deployment_class=record.deployment_class,
        secret_ref=record.secret_ref,
        endpoint_ref=record.endpoint_ref,
        allowed_data_boundaries=list(record.allowed_data_boundaries),
        capabilities=list(record.capabilities),
        timeout_seconds=record.timeout_seconds,
        max_output_tokens=record.max_output_tokens,
        cost_policy=record.cost_policy,
        created_at=record.created_at,
    )


def _raise_governance_api_error(error: Exception) -> None:
    if isinstance(error, CandidateNotFoundError | RevisionNotFoundError):
        raise PlatformApiError(
            status_code=404,
            code="candidate_not_found",
            message="The governed candidate or revision does not exist.",
        ) from error
    if isinstance(error, StaleRevisionError):
        raise PlatformApiError(
            status_code=409,
            code="stale_revision",
            message="The candidate or revision changed before this decision.",
        ) from error
    if isinstance(error, DuplicateDecisionError):
        raise PlatformApiError(
            status_code=409,
            code="duplicate_decision",
            message="This governance decision was already submitted.",
        ) from error
    if isinstance(error, InvalidGovernanceTransitionError | AuthorizationError):
        raise PlatformApiError(
            status_code=409,
            code="invalid_governance_transition",
            message="The current governance state does not permit this decision.",
        ) from error
    if isinstance(error, SQLAlchemyError):
        raise PlatformApiError(
            status_code=503,
            code="service_unavailable",
            message="The governance repository is unavailable.",
        ) from error
    raise error
