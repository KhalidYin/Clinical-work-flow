"""Environment-wired local entry point for the prerelease platform API."""

from __future__ import annotations

from hashlib import sha256
import os
from pathlib import Path

import uvicorn

from service.auth import IdentityAssertion, LocalIdentityProvider
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
    """Wire the local identity adapter and existing PostgreSQL schema."""

    identity_mode = os.environ.get("KNOWLEDGE_IDENTITY_MODE", "local")
    if identity_mode != "local":
        raise RuntimeError("P1-D only wires local identity; provider-specific OIDC is not enabled")

    token = _required_environment("KNOWLEDGE_LOCAL_BEARER_TOKEN")
    subject = _required_environment("KNOWLEDGE_LOCAL_SUBJECT")
    display_name = _required_environment("KNOWLEDGE_LOCAL_DISPLAY_NAME")
    email = _required_environment("KNOWLEDGE_LOCAL_EMAIL")
    issuer = os.environ.get("KNOWLEDGE_LOCAL_ISSUER", "local://knowledge-platform")
    assertion_facts = f"local_test\n{issuer}\n{subject}\n{display_name}\n{email}"
    identity_provider = LocalIdentityProvider(
        environment="local",
        token_assertions={
            token: IdentityAssertion(
                identity_source="local_test",
                issuer=issuer,
                subject=subject,
                display_name=display_name,
                email=email,
                claims_sha256=sha256(assertion_facts.encode("utf-8")).hexdigest(),
            )
        },
    )
    engine = create_database_engine(database_url_from_environment())
    sessions = create_session_factory(engine)
    repository = SqlAlchemyPlatformRepository(sessions)
    object_store = LocalObjectStore(root=Path(_required_environment("KNOWLEDGE_OBJECT_STORE_ROOT")))
    ledger = PostgresProcessingLedger(sessions)
    return create_platform_app(
        PlatformApiServices(
            identity_provider=identity_provider,
            repository=repository,
            organization_name=os.environ.get(
                "KNOWLEDGE_ORGANIZATION_NAME",
                "Clinical Knowledge Platform",
            ),
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
        )
    )


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
