from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
import pytest
from sqlalchemy.exc import OperationalError
import yaml

from service.auth import (
    IdentityAssertion,
    LocalIdentityProvider,
    PlatformUserGrant,
)


ROOT = Path(__file__).resolve().parents[1]
API_PREFIX = "/api/prerelease/v1"


def _platform_modules():
    try:
        app_module = import_module("service.platform_api.app")
        contracts_module = import_module("service.platform_api.contracts")
        repository_module = import_module("service.platform_api.repository")
    except ModuleNotFoundError as exc:
        pytest.fail(f"P1-D platform API is not implemented: {exc}")
    return app_module, contracts_module, repository_module


class FakePlatformRepository:
    def __init__(self, repository_module: Any) -> None:
        now = datetime(2026, 7, 30, 3, 0, tzinfo=timezone.utc)
        self._grants: dict[tuple[str, str], PlatformUserGrant] = {}
        self.sources = [
            repository_module.SourceSummaryRecord(
                source_id="src-sdtmig-34",
                title="Study Data Tabulation Model Implementation Guide",
                version="3.4",
                media_type="PDF",
                rights="licensed",
                status="registered",
                source_hash="a" * 64,
                updated_at=now,
            )
        ]
        self.users: list[Any] = []
        self.release = repository_module.CurrentReleaseRecord(
            release_id="rel-001",
            version="2026.07-p1d",
            status="released",
            index_version="idx-001",
            released_at=now,
        )
        self.database_is_available = True
        self.source_read_fails = False

    def add_grant(self, grant: PlatformUserGrant) -> None:
        self._grants[(grant.issuer, grant.subject)] = grant

    def resolve_user(self, *, issuer: str, subject: str) -> PlatformUserGrant | None:
        return self._grants.get((issuer, subject))

    def database_available(self) -> bool:
        return self.database_is_available

    def get_current_release(self):
        return self.release

    def list_sources(self):
        if self.source_read_fails:
            raise OperationalError("SELECT", {}, RuntimeError("database unavailable"))
        return self.sources, []

    def list_platform_users(self):
        return self.users, []


def _identity(subject: str, display_name: str) -> IdentityAssertion:
    return IdentityAssertion(
        identity_source="local_test",
        issuer="local://p1d-tests",
        subject=subject,
        display_name=display_name,
        email=f"{subject}@example.test",
        claims_sha256=sha256(subject.encode("utf-8")).hexdigest(),
    )


def _grant(subject: str, display_name: str, role: str, *, status: str = "active"):
    return PlatformUserGrant(
        user_id=f"usr-{subject}",
        identity_source="local_test",
        issuer="local://p1d-tests",
        subject=subject,
        display_name=display_name,
        email=f"{subject}@example.test",
        status=status,
        roles=[role],
    )


@pytest.fixture()
def api_client():
    app_module, _, repository_module = _platform_modules()
    assertions = {
        "admin-token": _identity("admin", "Platform Admin"),
        "curator-token": _identity("curator", "Knowledge Curator"),
        "consumer-token": _identity("consumer", "Knowledge Consumer"),
        "disabled-token": _identity("disabled", "Disabled User"),
        "unmapped-token": _identity("unmapped", "Unmapped User"),
    }
    identity_provider = LocalIdentityProvider(
        environment="test",
        token_assertions=assertions,
    )
    repository = FakePlatformRepository(repository_module)
    grants = [
        _grant("admin", "Platform Admin", "platform_admin"),
        _grant("curator", "Knowledge Curator", "knowledge_curator"),
        _grant("consumer", "Knowledge Consumer", "consumer"),
        _grant("disabled", "Disabled User", "consumer", status="disabled"),
    ]
    for grant in grants:
        repository.add_grant(grant)
        repository.users.append(
            repository_module.PlatformUserRecord(
                user_id=grant.user_id,
                display_name=grant.display_name,
                email=grant.email,
                identity_source=grant.identity_source.value,
                roles=tuple(sorted(role.value for role in grant.roles)),
                status=grant.status.value,
                last_active_at=None,
            )
        )
    services = app_module.PlatformApiServices(
        identity_provider=identity_provider,
        repository=repository,
        organization_name="Clinical Knowledge Lab",
        object_store_available=False,
        semantic_index_available=False,
    )
    return TestClient(app_module.create_platform_app(services)), repository


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_is_public_and_reports_unimplemented_capabilities(api_client) -> None:
    client, _ = api_client

    response = client.get(f"{API_PREFIX}/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["fixture"] is False
    assert payload["data"]["status"] == "degraded"
    assert payload["data"]["api"] == "available"
    assert payload["data"]["database"] == "available"
    assert payload["data"]["objectStore"] == "disabled"
    assert payload["data"]["semanticIndex"] == "disabled"


def test_health_reports_database_failure_without_exposing_an_exception(api_client) -> None:
    client, repository = api_client
    repository.database_is_available = False

    response = client.get(f"{API_PREFIX}/health")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "degraded"
    assert response.json()["data"]["database"] == "degraded"


@pytest.mark.parametrize(
    ("token", "expected_code"),
    [
        (None, "authentication_required"),
        ("unknown-token", "invalid_identity"),
        ("unmapped-token", "invalid_identity"),
        ("disabled-token", "invalid_identity"),
    ],
)
def test_session_fails_closed_for_missing_invalid_unmapped_or_disabled_identity(
    api_client,
    token: str | None,
    expected_code: str,
) -> None:
    client, _ = api_client
    headers = _auth(token) if token else {}

    response = client.get(f"{API_PREFIX}/session", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == expected_code
    assert "unknown-token" not in response.text


def test_session_returns_internal_actor_roles_and_never_identity_claims(api_client) -> None:
    client, _ = api_client

    response = client.get(f"{API_PREFIX}/session", headers=_auth("admin-token"))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["actorId"] == "usr-admin"
    assert data["principalType"] == "human"
    assert data["roles"] == ["platform_admin"]
    assert "admin:read" in data["permissions"]
    assert "review:decide" not in data["permissions"]
    assert {"issuer", "subject", "claims", "token", "secret"}.isdisjoint(data)


def test_backend_permissions_protect_sources_release_and_admin(api_client) -> None:
    client, _ = api_client

    assert client.get(f"{API_PREFIX}/sources", headers=_auth("admin-token")).status_code == 200
    assert client.get(f"{API_PREFIX}/admin/users", headers=_auth("admin-token")).status_code == 200
    assert (
        client.get(
            f"{API_PREFIX}/releases/current",
            headers=_auth("consumer-token"),
        ).status_code
        == 200
    )
    assert client.get(f"{API_PREFIX}/sources", headers=_auth("consumer-token")).status_code == 403
    assert (
        client.get(f"{API_PREFIX}/admin/users", headers=_auth("curator-token")).status_code == 403
    )


def test_repository_failure_is_a_sanitized_service_unavailable_response(api_client) -> None:
    client, repository = api_client
    repository.source_read_fails = True

    response = client.get(f"{API_PREFIX}/sources", headers=_auth("admin-token"))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert "SELECT" not in response.text


def test_real_read_routes_return_database_views_not_fixtures_or_secrets(api_client) -> None:
    client, _ = api_client

    sources = client.get(f"{API_PREFIX}/sources", headers=_auth("admin-token")).json()
    users = client.get(f"{API_PREFIX}/admin/users", headers=_auth("admin-token")).json()
    release = client.get(
        f"{API_PREFIX}/releases/current",
        headers=_auth("admin-token"),
    ).json()

    assert sources["meta"]["fixture"] is False
    assert sources["data"]["items"][0]["sourceId"] == "src-sdtmig-34"
    assert sources["data"]["items"][0]["sourceHash"] == "a" * 64
    assert release["data"]["releaseId"] == "rel-001"
    assert users["data"]["items"][0]["identitySource"] == "local_test"
    assert users["data"]["items"][0]["roles"] == ["platform_admin"]
    assert all(
        {"issuer", "subject", "secretRef", "password", "accessToken"}.isdisjoint(item)
        for item in users["data"]["items"]
    )


def _openapi_component_schema(spec: dict[str, Any], name: str) -> dict[str, Any]:
    definitions = deepcopy(spec["components"]["schemas"])

    def rewrite(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    item.replace("#/components/schemas/", "#/$defs/")
                    if key == "$ref" and isinstance(item, str)
                    else rewrite(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        return value

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": rewrite(definitions),
        "$ref": f"#/$defs/{name}",
    }


def test_checked_in_openapi_matches_runtime_paths_roles_and_responses(api_client) -> None:
    client, _ = api_client
    spec = yaml.safe_load(
        (ROOT / "schemas" / "application" / "knowledge-api.prerelease.yaml").read_text(
            encoding="utf-8"
        )
    )
    runtime_spec = client.app.openapi()
    runtime_paths = {path for path in runtime_spec["paths"] if path.startswith(API_PREFIX)}
    checked_paths = {f"{API_PREFIX}{path}" for path in spec["paths"]}

    assert (
        runtime_paths
        == checked_paths
        == {
            f"{API_PREFIX}/session",
            f"{API_PREFIX}/health",
            f"{API_PREFIX}/releases/current",
            f"{API_PREFIX}/sources",
            f"{API_PREFIX}/admin/users",
        }
    )
    assert spec["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"
    assert spec["components"]["schemas"]["HumanRole"]["enum"] == [
        "platform_admin",
        "knowledge_curator",
        "reviewer",
        "release_manager",
        "consumer",
    ]
    assert spec["components"]["schemas"]["IdentitySource"]["enum"] == [
        "local_test",
        "oidc",
    ]
    assert runtime_spec["paths"][f"{API_PREFIX}/health"]["get"].get("security") is None
    assert runtime_spec["paths"][f"{API_PREFIX}/session"]["get"]["security"] == [{"bearerAuth": []}]

    response_cases = [
        ("HealthResponse", client.get(f"{API_PREFIX}/health")),
        (
            "SessionResponse",
            client.get(f"{API_PREFIX}/session", headers=_auth("admin-token")),
        ),
        (
            "CurrentReleaseResponse",
            client.get(f"{API_PREFIX}/releases/current", headers=_auth("admin-token")),
        ),
        (
            "SourceCollectionResponse",
            client.get(f"{API_PREFIX}/sources", headers=_auth("admin-token")),
        ),
        (
            "UserCollectionResponse",
            client.get(f"{API_PREFIX}/admin/users", headers=_auth("admin-token")),
        ),
    ]
    for component_name, response in response_cases:
        assert response.status_code == 200
        Draft202012Validator(_openapi_component_schema(spec, component_name)).validate(
            response.json()
        )


def test_api_dtos_are_pydantic_models_separate_from_sqlalchemy_metadata() -> None:
    _, contracts_module, _ = _platform_modules()

    assert contracts_module.SessionResponse.__module__ == "service.platform_api.contracts"
    assert not hasattr(contracts_module.SessionResponse, "__table__")
