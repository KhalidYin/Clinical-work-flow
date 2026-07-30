"""FastAPI application for the P12 prerelease read boundary."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Callable, TypeVar

from fastapi import Depends, FastAPI, Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from service.auth import (
    ActorContext,
    AuthenticationError,
    AuthorizationError,
    IdentityProviderPort,
    Permission,
    require_permission,
    resolve_human_actor,
)

from .contracts import (
    CurrentReleaseData,
    CurrentReleaseResponse,
    ErrorData,
    ErrorResponse,
    HealthResponse,
    PlatformHealthData,
    PlatformUserData,
    ResponseMeta,
    SessionData,
    SessionResponse,
    SourceCollectionData,
    SourceCollectionResponse,
    SourceSummaryData,
    UserCollectionData,
    UserCollectionResponse,
)
from .repository import PlatformReadRepository


API_PREFIX = "/api/prerelease/v1"
_bearer = HTTPBearer(auto_error=False, scheme_name="bearerAuth")
_ResponseModel = TypeVar("_ResponseModel", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class PlatformApiServices:
    """Explicit ports and capability flags required by the HTTP adapter."""

    identity_provider: IdentityProviderPort
    repository: PlatformReadRepository
    organization_name: str
    object_store_available: bool = False
    semantic_index_available: bool = False


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

    def get_actor(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Security(_bearer),
        ] = None,
    ) -> ActorContext:
        if credentials is None:
            raise PlatformApiError(
                status_code=401,
                code="authentication_required",
                message="A bearer identity is required.",
            )
        try:
            identity = services.identity_provider.verify_bearer_token(credentials.credentials)
            return resolve_human_actor(identity, services.repository)
        except AuthenticationError as exc:
            raise PlatformApiError(
                status_code=401,
                code="invalid_identity",
                message="The supplied identity is not active or recognized.",
            ) from exc
        except SQLAlchemyError as exc:
            raise PlatformApiError(
                status_code=503,
                code="service_unavailable",
                message="The authorization store is unavailable.",
            ) from exc

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

    @app.get(
        f"{API_PREFIX}/session",
        operation_id="getSession",
        response_model=SessionResponse,
        responses=protected_responses,
    )
    def get_session(
        actor: Annotated[ActorContext, Depends(get_actor)],
    ) -> SessionResponse:
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
            ),
            meta=_meta(),
        )

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

    return app
