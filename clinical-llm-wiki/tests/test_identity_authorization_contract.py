from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]


def _auth_contract():
    try:
        return import_module("service.auth.identity_authorization")
    except ModuleNotFoundError as exc:
        pytest.fail(f"P1-C identity and authorization contract is not implemented: {exc}")


def _identity(contract, *, subject: str = "subject-reviewer"):
    return contract.IdentityAssertion(
        identity_source="oidc",
        issuer="https://identity.example.test",
        subject=subject,
        display_name="Independent Reviewer",
        email="reviewer@example.test",
        claims_sha256="a" * 64,
    )


def _user_grant(contract, *, user_id: str, subject: str, roles: list[str]):
    return contract.PlatformUserGrant(
        user_id=user_id,
        identity_source="oidc",
        issuer="https://identity.example.test",
        subject=subject,
        display_name=user_id,
        email=f"{user_id}@example.test",
        status="active",
        roles=roles,
    )


def test_product_roles_and_permissions_are_internal_and_fail_closed() -> None:
    contract = _auth_contract()

    assert {role.value for role in contract.ProductRole} == {
        "platform_admin",
        "knowledge_curator",
        "reviewer",
        "release_manager",
        "consumer",
        "service_account",
    }
    assert set(contract.ROLE_PERMISSIONS) == {
        contract.ProductRole.PLATFORM_ADMIN,
        contract.ProductRole.KNOWLEDGE_CURATOR,
        contract.ProductRole.REVIEWER,
        contract.ProductRole.RELEASE_MANAGER,
        contract.ProductRole.CONSUMER,
    }
    assert contract.Permission.REVIEW_DECIDE not in contract.ROLE_PERMISSIONS[
        contract.ProductRole.PLATFORM_ADMIN
    ]
    assert contract.Permission.RELEASE_PUBLISH not in contract.ROLE_PERMISSIONS[
        contract.ProductRole.PLATFORM_ADMIN
    ]


@pytest.mark.parametrize(
    ("role", "allowed", "denied"),
    [
        ("platform_admin", "admin:manage_roles", "review:decide"),
        ("knowledge_curator", "candidate:submit", "release:publish"),
        ("reviewer", "review:decide", "candidate:write"),
        ("release_manager", "release:publish", "review:decide"),
        ("consumer", "query:released", "source:read"),
    ],
)
def test_human_role_permission_matrix_preserves_governance_boundaries(
    role: str,
    allowed: str,
    denied: str,
) -> None:
    contract = _auth_contract()
    identity = _identity(contract, subject=f"subject-{role}")
    grant = _user_grant(
        contract,
        user_id=f"usr-{role}",
        subject=identity.subject,
        roles=[role],
    )
    actor = contract.resolve_human_actor(
        identity,
        contract.StaticAuthorizationGrantStore(users=[grant]),
    )

    contract.require_permission(actor, contract.Permission(allowed))
    with pytest.raises(contract.AuthorizationError, match=denied):
        contract.require_permission(actor, contract.Permission(denied))


def test_identity_assertion_cannot_carry_product_roles_or_permissions() -> None:
    contract = _auth_contract()

    assertion = _identity(contract)
    assert "roles" not in type(assertion).model_fields
    assert "permissions" not in type(assertion).model_fields

    with pytest.raises(ValidationError, match="roles"):
        contract.IdentityAssertion(
            identity_source="oidc",
            issuer="https://identity.example.test",
            subject="subject-admin",
            display_name="Claimed Admin",
            email="claimed-admin@example.test",
            claims_sha256="b" * 64,
            roles=["platform_admin"],
        )


def test_local_identity_adapter_is_explicitly_non_production_and_has_no_password_flow() -> None:
    contract = _auth_contract()
    assertion = contract.IdentityAssertion(
        identity_source="local_test",
        issuer="local://p12-tests",
        subject="local-reviewer",
        display_name="Local Reviewer",
        email="local-reviewer@example.test",
        claims_sha256="c" * 64,
    )
    provider = contract.LocalIdentityProvider(
        environment="test",
        token_assertions={"opaque-test-token": assertion},
    )

    assert provider.verify_bearer_token("opaque-test-token") == assertion
    with pytest.raises(contract.AuthenticationError, match="invalid bearer token"):
        provider.verify_bearer_token("unknown-token")
    with pytest.raises(ValueError, match="local or test"):
        contract.LocalIdentityProvider(
            environment="production",
            token_assertions={"opaque-test-token": assertion},
        )
    assert not hasattr(provider, "verify_password")


def test_oidc_identity_resolves_only_through_internal_role_bindings() -> None:
    contract = _auth_contract()
    identity = _identity(contract)
    reviewer = _user_grant(
        contract,
        user_id="usr-reviewer",
        subject=identity.subject,
        roles=["reviewer"],
    )
    store = contract.StaticAuthorizationGrantStore(users=[reviewer])

    actor = contract.resolve_human_actor(identity, store)

    assert actor.actor_id == "usr-reviewer"
    assert actor.roles == frozenset({contract.ProductRole.REVIEWER})
    assert contract.Permission.REVIEW_DECIDE in actor.permissions
    assert contract.Permission.RELEASE_PUBLISH not in actor.permissions

    disabled = reviewer.model_copy(update={"status": "disabled"})
    disabled_store = contract.StaticAuthorizationGrantStore(users=[disabled])
    with pytest.raises(contract.AuthenticationError, match="disabled"):
        contract.resolve_human_actor(identity, disabled_store)


def test_author_confirmation_and_independent_review_are_separate_duties() -> None:
    contract = _auth_contract()
    reviewer_identity = _identity(contract)
    reviewer = _user_grant(
        contract,
        user_id="usr-reviewer",
        subject=reviewer_identity.subject,
        roles=["reviewer"],
    )
    reviewer_actor = contract.resolve_human_actor(
        reviewer_identity,
        contract.StaticAuthorizationGrantStore(users=[reviewer]),
    )

    contract.require_independent_review(
        reviewer_actor,
        author_actor_id="usr-author",
    )
    with pytest.raises(contract.SeparationOfDutiesError, match="own candidate"):
        contract.require_independent_review(
            reviewer_actor,
            author_actor_id="usr-reviewer",
        )

    author_identity = _identity(contract, subject="subject-author")
    author = _user_grant(
        contract,
        user_id="usr-author",
        subject=author_identity.subject,
        roles=["knowledge_curator"],
    )
    author_actor = contract.resolve_human_actor(
        author_identity,
        contract.StaticAuthorizationGrantStore(users=[author]),
    )
    with pytest.raises(contract.AuthorizationError, match="review:decide"):
        contract.require_independent_review(author_actor, author_actor_id="usr-other")


@pytest.mark.parametrize(
    ("pool", "required_scope"),
    [
        ("document", "evidence:write"),
        ("enrichment", "model:invoke"),
        ("release", "release:build"),
    ],
)
def test_worker_service_accounts_have_bounded_pool_scopes(
    pool: str,
    required_scope: str,
) -> None:
    contract = _auth_contract()
    allowed_scopes = contract.WORKER_POOL_PERMISSIONS[contract.WorkerPool(pool)]
    account = contract.ServiceAccountGrant(
        service_account_id=f"svc-{pool}",
        display_name=f"{pool.title()} Worker",
        worker_pool=pool,
        scopes=sorted(permission.value for permission in allowed_scopes),
        secret_ref=f"env://P12_{pool.upper()}_WORKER_TOKEN",
        status="active",
    )

    actor = contract.resolve_service_account_actor(account)

    contract.require_permission(actor, contract.Permission(required_scope))
    assert actor.roles == frozenset({contract.ProductRole.SERVICE_ACCOUNT})
    assert contract.Permission.REVIEW_DECIDE not in actor.permissions
    assert contract.Permission.RELEASE_PUBLISH not in actor.permissions
    assert contract.Permission.ADMIN_MANAGE_ROLES not in actor.permissions


def test_worker_cannot_request_cross_pool_or_governance_scope() -> None:
    contract = _auth_contract()

    with pytest.raises(ValidationError, match="not allowed for document worker"):
        contract.ServiceAccountGrant(
            service_account_id="svc-document",
            display_name="Document Worker",
            worker_pool="document",
            scopes=["evidence:write", "model:invoke"],
            secret_ref="env://P12_DOCUMENT_WORKER_TOKEN",
            status="active",
        )

    with pytest.raises(ValidationError, match="not allowed for release worker"):
        contract.ServiceAccountGrant(
            service_account_id="svc-release",
            display_name="Release Worker",
            worker_pool="release",
            scopes=["release:build", "release:publish"],
            secret_ref="env://P12_RELEASE_WORKER_TOKEN",
            status="active",
        )


def test_service_account_contract_stores_references_never_credentials() -> None:
    contract = _auth_contract()

    assert {
        "secret_value",
        "client_secret",
        "access_token",
        "password",
    }.isdisjoint(contract.ServiceAccountGrant.model_fields)
    with pytest.raises(ValidationError, match="secret_ref"):
        contract.ServiceAccountGrant(
            service_account_id="svc-document",
            display_name="Document Worker",
            worker_pool="document",
            scopes=["evidence:write"],
            secret_ref="literal-secret",
            status="active",
        )


def test_checked_in_identity_authorization_schema_matches_runtime_contract() -> None:
    contract = _auth_contract()
    checked_in = json.loads(
        (
            ROOT
            / "schemas"
            / "application"
            / "identity-authorization.prerelease.schema.json"
        ).read_text(encoding="utf-8")
    )
    runtime = contract.identity_authorization_contract_json_schema()

    Draft202012Validator.check_schema(checked_in)
    assert checked_in == runtime
