"""Environment-wired local entry point for the prerelease platform API."""

from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

import uvicorn

from service.auth.password_sessions import (
    Argon2idPasswordHasher,
    PasswordSessionService,
    SqlAlchemyPasswordSessionRepository,
)
from service.db.session import (
    create_database_engine,
    create_session_factory,
    database_url_from_environment,
)
from service.governance import (
    KnowledgeGovernanceService,
    SqlAlchemyGovernanceRepository,
)
from service.object_store import LocalObjectStore
from service.processing.ledger import PostgresProcessingLedger
from service.sources import SourceRegistryService, SqlAlchemySourceRegistryRepository

from .app import PlatformApiServices, create_platform_app
from .repository import SqlAlchemyPlatformRepository


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def create_environment_app():
    """Wire password sessions and the existing PostgreSQL product services."""

    engine = create_database_engine(database_url_from_environment())
    sessions = create_session_factory(engine)
    repository = SqlAlchemyPlatformRepository(sessions)
    password_sessions = PasswordSessionService(
        repository=SqlAlchemyPasswordSessionRepository(sessions),
        hasher=Argon2idPasswordHasher(),
    )
    object_store = LocalObjectStore(root=Path(_required_environment("KNOWLEDGE_OBJECT_STORE_ROOT")))
    ledger = PostgresProcessingLedger(sessions)
    return create_platform_app(
        PlatformApiServices(
            repository=repository,
            password_sessions=password_sessions,
            organization_name=os.environ.get(
                "KNOWLEDGE_ORGANIZATION_NAME",
                "临床知识平台",
            ),
            allowed_browser_origins=_browser_origins(),
            secure_session_cookie=_secure_session_cookie(),
            object_store_available=object_store.healthcheck(),
            source_registry=SourceRegistryService(
                repository=SqlAlchemySourceRegistryRepository(sessions),
                object_store=object_store,
                ledger=ledger,
            ),
            processing_ledger=ledger,
            governance=KnowledgeGovernanceService(
                repository=SqlAlchemyGovernanceRepository(sessions)
            ),
            object_store=object_store,
            runtime_consumer_credential_sha256=_runtime_consumer_credential_sha256(),
        )
    )


def _runtime_consumer_credential_sha256() -> str | None:
    secret = os.environ.get("KNOWLEDGE_RUNTIME_CONSUMER_SECRET")
    return sha256(secret.encode("utf-8")).hexdigest() if secret else None


def _browser_origins() -> frozenset[str]:
    configured = os.environ.get(
        "KNOWLEDGE_BROWSER_ORIGINS",
        "http://127.0.0.1:4173,http://localhost:4173",
    )
    origins = frozenset(item.strip().rstrip("/") for item in configured.split(",") if item.strip())
    if not origins:
        raise RuntimeError("KNOWLEDGE_BROWSER_ORIGINS requires at least one exact origin")
    for origin in origins:
        parsed = urlsplit(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path:
            raise RuntimeError("KNOWLEDGE_BROWSER_ORIGINS accepts exact HTTP(S) origins only")
    return origins


def _secure_session_cookie() -> bool:
    environment = os.environ.get("KNOWLEDGE_DEPLOYMENT_ENV", "local")
    configured = os.environ.get("KNOWLEDGE_SESSION_COOKIE_SECURE")
    secure = environment not in {"local", "test"} if configured is None else configured == "true"
    if environment not in {"local", "test"} and not secure:
        raise RuntimeError("non-local deployments require secure session cookies")
    return secure


def main() -> None:
    host = os.environ.get("KNOWLEDGE_API_HOST", "127.0.0.1")
    bind_scope = os.environ.get("KNOWLEDGE_API_BIND_SCOPE", "loopback")
    loopback = host in {"127.0.0.1", "localhost", "::1"}
    local_compose = bind_scope == "compose_local" and host == "0.0.0.0"
    if not loopback and not local_compose:
        raise RuntimeError(
            "prerelease API may bind only to loopback or explicit compose_local scope"
        )
    port = int(os.environ.get("KNOWLEDGE_API_PORT", "8788"))
    uvicorn.run(create_environment_app(), host=host, port=port)


if __name__ == "__main__":
    main()
