"""Fail-closed identity, RBAC, and worker-scope contracts owned by P12."""

from __future__ import annotations

from enum import Enum
from typing import Mapping, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictContractModel(BaseModel):
    """Reject unowned claims and freeze resolved authorization facts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class IdentitySource(str, Enum):
    LOCAL_TEST = "local_test"
    OIDC = "oidc"


class PrincipalType(str, Enum):
    HUMAN = "human"
    SERVICE_ACCOUNT = "service_account"


class GrantStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class ProductRole(str, Enum):
    PLATFORM_ADMIN = "platform_admin"
    KNOWLEDGE_CURATOR = "knowledge_curator"
    REVIEWER = "reviewer"
    RELEASE_MANAGER = "release_manager"
    CONSUMER = "consumer"
    SERVICE_ACCOUNT = "service_account"


class Permission(str, Enum):
    SOURCE_READ = "source:read"
    SOURCE_REGISTER = "source:register"
    SOURCE_UPLOAD = "source:upload"
    PROCESSING_READ = "processing:read"
    PROCESSING_START = "processing:start"
    PROCESSING_RETRY = "processing:retry"
    PROCESSING_EXECUTE = "processing:execute"
    OBJECT_READ = "object:read"
    OBJECT_WRITE_DERIVED = "object:write_derived"
    EVIDENCE_READ = "evidence:read"
    EVIDENCE_WRITE = "evidence:write"
    CANDIDATE_READ = "candidate:read"
    CANDIDATE_WRITE = "candidate:write"
    CANDIDATE_SUBMIT = "candidate:submit"
    RELATION_PROPOSE = "relation:propose"
    REVIEW_DECIDE = "review:decide"
    QUERY_RELEASED = "query:released"
    MODEL_INVOKE = "model:invoke"
    EVALUATION_RUN = "evaluation:run"
    INDEX_BUILD = "index:build"
    RELEASE_BUILD = "release:build"
    RELEASE_PUBLISH = "release:publish"
    ADMIN_READ = "admin:read"
    ADMIN_MANAGE_USERS = "admin:manage_users"
    ADMIN_MANAGE_ROLES = "admin:manage_roles"
    ADMIN_MANAGE_SERVICE_ACCOUNTS = "admin:manage_service_accounts"
    AUDIT_READ = "audit:read"


class WorkerPool(str, Enum):
    DOCUMENT = "document"
    ENRICHMENT = "enrichment"
    RELEASE = "release"


ROLE_PERMISSIONS: Mapping[ProductRole, frozenset[Permission]] = {
    ProductRole.PLATFORM_ADMIN: frozenset(
        {
            Permission.SOURCE_READ,
            Permission.PROCESSING_READ,
            Permission.EVIDENCE_READ,
            Permission.CANDIDATE_READ,
            Permission.QUERY_RELEASED,
            Permission.ADMIN_READ,
            Permission.ADMIN_MANAGE_USERS,
            Permission.ADMIN_MANAGE_ROLES,
            Permission.ADMIN_MANAGE_SERVICE_ACCOUNTS,
            Permission.AUDIT_READ,
        }
    ),
    ProductRole.KNOWLEDGE_CURATOR: frozenset(
        {
            Permission.SOURCE_READ,
            Permission.SOURCE_REGISTER,
            Permission.SOURCE_UPLOAD,
            Permission.PROCESSING_READ,
            Permission.PROCESSING_START,
            Permission.PROCESSING_RETRY,
            Permission.EVIDENCE_READ,
            Permission.CANDIDATE_READ,
            Permission.CANDIDATE_WRITE,
            Permission.CANDIDATE_SUBMIT,
            Permission.RELATION_PROPOSE,
            Permission.QUERY_RELEASED,
        }
    ),
    ProductRole.REVIEWER: frozenset(
        {
            Permission.SOURCE_READ,
            Permission.EVIDENCE_READ,
            Permission.CANDIDATE_READ,
            Permission.REVIEW_DECIDE,
            Permission.QUERY_RELEASED,
        }
    ),
    ProductRole.RELEASE_MANAGER: frozenset(
        {
            Permission.SOURCE_READ,
            Permission.EVIDENCE_READ,
            Permission.CANDIDATE_READ,
            Permission.QUERY_RELEASED,
            Permission.EVALUATION_RUN,
            Permission.RELEASE_BUILD,
            Permission.RELEASE_PUBLISH,
            Permission.AUDIT_READ,
        }
    ),
    ProductRole.CONSUMER: frozenset({Permission.QUERY_RELEASED}),
}


WORKER_POOL_PERMISSIONS: Mapping[WorkerPool, frozenset[Permission]] = {
    WorkerPool.DOCUMENT: frozenset(
        {
            Permission.SOURCE_READ,
            Permission.OBJECT_READ,
            Permission.OBJECT_WRITE_DERIVED,
            Permission.PROCESSING_EXECUTE,
            Permission.EVIDENCE_WRITE,
        }
    ),
    WorkerPool.ENRICHMENT: frozenset(
        {
            Permission.EVIDENCE_READ,
            Permission.MODEL_INVOKE,
            Permission.CANDIDATE_WRITE,
            Permission.RELATION_PROPOSE,
            Permission.PROCESSING_EXECUTE,
        }
    ),
    WorkerPool.RELEASE: frozenset(
        {
            Permission.EVIDENCE_READ,
            Permission.CANDIDATE_READ,
            Permission.EVALUATION_RUN,
            Permission.INDEX_BUILD,
            Permission.RELEASE_BUILD,
            Permission.OBJECT_WRITE_DERIVED,
            Permission.PROCESSING_EXECUTE,
        }
    ),
}


class AuthenticationError(RuntimeError):
    """An external identity cannot become an active internal actor."""


class AuthorizationError(PermissionError):
    """The internal actor lacks a product-owned permission."""


class SeparationOfDutiesError(AuthorizationError):
    """An otherwise-authorized actor violates a governance independence rule."""


class IdentityAssertion(StrictContractModel):
    """Verified authentication facts; product roles are deliberately absent."""

    identity_source: IdentitySource
    issuer: str = Field(min_length=1, max_length=500)
    subject: str = Field(min_length=1, max_length=500)
    display_name: str = Field(min_length=1, max_length=240)
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")
    claims_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PlatformUserGrant(StrictContractModel):
    """Internal user mapping and role bindings, never supplied by an IdP claim."""

    user_id: str = Field(min_length=1, max_length=160)
    identity_source: IdentitySource
    issuer: str = Field(min_length=1, max_length=500)
    subject: str = Field(min_length=1, max_length=500)
    display_name: str = Field(min_length=1, max_length=240)
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+$")
    status: GrantStatus
    roles: frozenset[ProductRole] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_human_roles(self) -> "PlatformUserGrant":
        if ProductRole.SERVICE_ACCOUNT in self.roles:
            raise ValueError("human user cannot receive the service_account role")
        return self


class ServiceAccountGrant(StrictContractModel):
    """Internal worker identity with a secret reference and bounded scopes."""

    service_account_id: str = Field(min_length=1, max_length=160)
    display_name: str = Field(min_length=1, max_length=240)
    worker_pool: WorkerPool
    scopes: frozenset[Permission] = Field(min_length=1)
    secret_ref: str = Field(pattern=r"^(env|secret)://[A-Za-z0-9_./-]+$")
    status: GrantStatus

    @model_validator(mode="after")
    def validate_scopes(self) -> "ServiceAccountGrant":
        allowed = WORKER_POOL_PERMISSIONS[self.worker_pool]
        disallowed = self.scopes - allowed
        if disallowed:
            names = ", ".join(sorted(permission.value for permission in disallowed))
            raise ValueError(
                f"scope(s) {names} not allowed for {self.worker_pool.value} worker"
            )
        return self


class ActorContext(StrictContractModel):
    """Resolved authorization facts consumed by services and repositories."""

    actor_id: str = Field(min_length=1, max_length=160)
    display_name: str = Field(min_length=1, max_length=240)
    principal_type: PrincipalType
    roles: frozenset[ProductRole] = Field(min_length=1)
    permissions: frozenset[Permission]
    identity_source: IdentitySource | None = None
    worker_pool: WorkerPool | None = None

    @model_validator(mode="after")
    def validate_principal_shape(self) -> "ActorContext":
        if self.principal_type is PrincipalType.HUMAN:
            if self.identity_source is None or self.worker_pool is not None:
                raise ValueError("human actor requires identity_source and no worker_pool")
            if ProductRole.SERVICE_ACCOUNT in self.roles:
                raise ValueError("human actor cannot use the service_account role")
        else:
            if self.identity_source is not None or self.worker_pool is None:
                raise ValueError("service account requires worker_pool and no identity_source")
            if self.roles != frozenset({ProductRole.SERVICE_ACCOUNT}):
                raise ValueError("service account must use only the service_account role")
        return self


class IdentityProviderPort(Protocol):
    def verify_bearer_token(self, token: str) -> IdentityAssertion:
        """Verify one bearer token and return authentication facts only."""


class AuthorizationGrantStorePort(Protocol):
    def resolve_user(self, *, issuer: str, subject: str) -> PlatformUserGrant | None:
        """Resolve external identity to product-owned role bindings."""


class LocalIdentityProvider:
    """Opaque-token adapter for explicit local/test use; it has no password flow."""

    def __init__(
        self,
        *,
        environment: str,
        token_assertions: Mapping[str, IdentityAssertion],
    ) -> None:
        if environment not in {"local", "test"}:
            raise ValueError("LocalIdentityProvider is allowed only in local or test")
        if not token_assertions:
            raise ValueError("LocalIdentityProvider requires at least one opaque token")
        if any(
            assertion.identity_source is not IdentitySource.LOCAL_TEST
            for assertion in token_assertions.values()
        ):
            raise ValueError("LocalIdentityProvider accepts only local_test assertions")
        self._token_assertions = dict(token_assertions)

    def verify_bearer_token(self, token: str) -> IdentityAssertion:
        assertion = self._token_assertions.get(token)
        if assertion is None:
            raise AuthenticationError("invalid bearer token")
        return assertion


class StaticAuthorizationGrantStore:
    """Deterministic local/test grant store; production uses a database adapter."""

    def __init__(self, *, users: Sequence[PlatformUserGrant]) -> None:
        self._users: dict[tuple[str, str], PlatformUserGrant] = {}
        for user in users:
            key = (user.issuer, user.subject)
            if key in self._users:
                raise ValueError(f"duplicate identity mapping: {user.issuer} {user.subject}")
            self._users[key] = user

    def resolve_user(self, *, issuer: str, subject: str) -> PlatformUserGrant | None:
        return self._users.get((issuer, subject))


def resolve_human_actor(
    identity: IdentityAssertion,
    grant_store: AuthorizationGrantStorePort,
) -> ActorContext:
    grant = grant_store.resolve_user(issuer=identity.issuer, subject=identity.subject)
    if grant is None:
        raise AuthenticationError("external identity is not mapped to a platform user")
    if grant.status is not GrantStatus.ACTIVE:
        raise AuthenticationError("platform user is disabled")
    if grant.identity_source is not identity.identity_source:
        raise AuthenticationError("identity source does not match the internal mapping")

    permissions: set[Permission] = set()
    for role in grant.roles:
        permissions.update(ROLE_PERMISSIONS[role])
    return ActorContext(
        actor_id=grant.user_id,
        display_name=grant.display_name,
        principal_type=PrincipalType.HUMAN,
        roles=grant.roles,
        permissions=frozenset(permissions),
        identity_source=grant.identity_source,
    )


def resolve_service_account_actor(grant: ServiceAccountGrant) -> ActorContext:
    if grant.status is not GrantStatus.ACTIVE:
        raise AuthenticationError("service account is disabled")
    return ActorContext(
        actor_id=grant.service_account_id,
        display_name=grant.display_name,
        principal_type=PrincipalType.SERVICE_ACCOUNT,
        roles=frozenset({ProductRole.SERVICE_ACCOUNT}),
        permissions=grant.scopes,
        worker_pool=grant.worker_pool,
    )


def require_permission(actor: ActorContext, permission: Permission) -> None:
    if permission not in actor.permissions:
        raise AuthorizationError(
            f"actor {actor.actor_id} lacks permission {permission.value}"
        )


def require_independent_review(actor: ActorContext, *, author_actor_id: str) -> None:
    require_permission(actor, Permission.REVIEW_DECIDE)
    if actor.actor_id == author_actor_id:
        raise SeparationOfDutiesError("reviewer cannot approve own candidate")


def identity_authorization_contract_json_schema() -> dict[str, object]:
    """Return the reviewable policy snapshot schema checked into the repository."""

    role_permissions = {
        role.value: sorted(permission.value for permission in permissions)
        for role, permissions in ROLE_PERMISSIONS.items()
    }
    worker_permissions = {
        pool.value: sorted(permission.value for permission in permissions)
        for pool, permissions in WORKER_POOL_PERMISSIONS.items()
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": (
            "https://clinical.example/schemas/"
            "identity-authorization.prerelease.schema.json"
        ),
        "title": "P12 Identity and Authorization Prerelease Policy",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "contract_version",
            "product_roles",
            "permissions",
            "role_permissions",
            "worker_pool_permissions",
        ],
        "properties": {
            "contract_version": {"const": "identity-authorization.prerelease.v1"},
            "product_roles": {
                "const": sorted(role.value for role in ProductRole),
            },
            "permissions": {
                "const": sorted(permission.value for permission in Permission),
            },
            "role_permissions": {"const": role_permissions},
            "worker_pool_permissions": {"const": worker_permissions},
        },
    }
