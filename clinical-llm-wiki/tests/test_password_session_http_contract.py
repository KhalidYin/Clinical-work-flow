from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

from service.auth import ProductRole
from service.auth.password_sessions import (
    Argon2idPasswordHasher,
    PasswordCredentialRecord,
    PasswordSessionPolicy,
    PasswordSessionService,
    SessionLookupRecord,
)
from service.platform_api.app import API_PREFIX, PlatformApiServices, create_platform_app
from service.platform_api.main import _browser_origins, _secure_session_cookie


NOW = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)
ORIGIN = "http://knowledge.test"
PASSWORD = "Correct horse battery staple 2026!"


class HttpContractRepository:
    def __init__(self) -> None:
        self.hasher = Argon2idPasswordHasher()
        self.credential = PasswordCredentialRecord(
            user_id="usr-admin",
            username_normalized="admin",
            password_hash=self.hasher.hash(PASSWORD),
            must_change_password=True,
            failed_attempts=0,
            locked_until=None,
            status="active",
            display_name="平台管理员",
            roles=(ProductRole.PLATFORM_ADMIN,),
        )
        self.sessions = {}
        self.created_users = []
        self.admin_events = []

    def database_available(self):
        return True

    def list_sources(self):
        return [], []

    def find_credential(self, username_normalized):
        return self.credential if username_normalized == "admin" else None

    def record_failed_login(self, *, failed_attempts, locked_until, **_):
        self.credential = replace(
            self.credential,
            failed_attempts=failed_attempts,
            locked_until=locked_until,
        )

    def complete_login(self, *, authenticated_at, session, **_):
        del authenticated_at
        self.credential = replace(
            self.credential,
            failed_attempts=0,
            locked_until=None,
        )
        self.sessions[session.session_id_hash] = session

    def resolve_session(self, *, session_id_hash, now):
        session = self.sessions.get(session_id_hash)
        if session is None or session.revoked_at is not None or session.expires_at <= now:
            return None
        return SessionLookupRecord(credential=self.credential, session=session)

    def touch_session(self, *, session_id_hash, last_seen_at):
        self.sessions[session_id_hash] = replace(
            self.sessions[session_id_hash],
            last_seen_at=last_seen_at,
        )

    def revoke_session(self, *, session_id_hash, revoked_at):
        if session_id_hash in self.sessions:
            self.sessions[session_id_hash] = replace(
                self.sessions[session_id_hash],
                revoked_at=revoked_at,
            )

    def complete_password_change(
        self,
        *,
        password_hash,
        changed_at,
        replacement_session,
        **_,
    ):
        self.credential = replace(
            self.credential,
            password_hash=password_hash,
            must_change_password=False,
        )
        self.sessions = {
            key: replace(value, revoked_at=changed_at)
            for key, value in self.sessions.items()
        }
        self.sessions[replacement_session.session_id_hash] = replacement_session

    def create_local_user(self, **facts):
        self.created_users.append(facts)

    def reset_user_password(self, *, user_id, actor_id, **_):
        self.admin_events.append(("password_reset", actor_id, user_id))

    def set_user_status(self, *, user_id, status, actor_id, **_):
        self.admin_events.append((status, actor_id, user_id))


def _client() -> tuple[TestClient, HttpContractRepository]:
    repository = HttpContractRepository()
    counter = iter(["browser-session-one", "browser-session-two", "browser-session-three"])
    sessions = PasswordSessionService(
        repository=repository,
        hasher=repository.hasher,
        policy=PasswordSessionPolicy(),
        clock=lambda: NOW,
        token_factory=lambda: next(counter),
    )
    app = create_platform_app(
        PlatformApiServices(
            repository=repository,
            password_sessions=sessions,
            organization_name="临床知识实验室",
            allowed_browser_origins=frozenset({ORIGIN}),
            secure_session_cookie=False,
        )
    )
    return TestClient(app, base_url=ORIGIN), repository


def _unsafe_headers(origin: str = ORIGIN) -> dict[str, str]:
    return {"Origin": origin, "X-CSRF-Protection": "1"}


def _login(client: TestClient):
    return client.post(
        f"{API_PREFIX}/auth/login",
        headers=_unsafe_headers(),
        json={"username": "admin", "password": PASSWORD},
    )


def test_human_bearer_is_rejected_and_missing_cookie_is_chinese_401() -> None:
    client, _ = _client()

    response = client.get(
        f"{API_PREFIX}/session",
        headers={"Authorization": "Bearer obsolete-human-token"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "authentication_required",
        "message": "需要登录。",
    }
    assert "bearer" not in response.text.lower()


def test_login_sets_only_httponly_strict_cookie_and_returns_no_session_value() -> None:
    client, repository = _client()

    response = _login(client)

    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "clinical_knowledge_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/" in cookie
    assert "secure" not in cookie
    payload = response.json()
    assert payload["data"]["mustChangePassword"] is True
    assert all(
        name not in response.text.lower()
        for name in ("raw_session", "session_id", "token", "password_hash")
    )
    assert len(repository.sessions) == 1


def test_forced_password_change_blocks_business_routes_but_not_session() -> None:
    client, _ = _client()
    assert _login(client).status_code == 200

    session = client.get(f"{API_PREFIX}/session")
    sources = client.get(f"{API_PREFIX}/sources")

    assert session.status_code == 200
    assert session.json()["data"]["mustChangePassword"] is True
    assert sources.status_code == 403
    assert sources.json()["error"]["code"] == "password_change_required"


def test_unsafe_routes_fail_closed_without_allowed_origin_and_custom_header() -> None:
    client, _ = _client()

    missing = client.post(
        f"{API_PREFIX}/auth/login",
        json={"username": "admin", "password": PASSWORD},
    )
    hostile = client.post(
        f"{API_PREFIX}/auth/login",
        headers=_unsafe_headers("https://hostile.example"),
        json={"username": "admin", "password": PASSWORD},
    )

    assert missing.status_code == hostile.status_code == 403
    assert missing.json()["error"]["code"] == "csrf_rejected"
    assert hostile.json()["error"]["code"] == "csrf_rejected"


def test_password_change_rotates_cookie_and_logout_revokes_server_session() -> None:
    client, repository = _client()
    first = _login(client)
    first_cookie = first.headers["set-cookie"]

    changed = client.post(
        f"{API_PREFIX}/auth/password/change",
        headers=_unsafe_headers(),
        json={
            "currentPassword": PASSWORD,
            "newPassword": "A new secure clinical passphrase 2026!",
        },
    )

    assert changed.status_code == 200
    assert changed.json()["data"]["mustChangePassword"] is False
    assert changed.headers["set-cookie"] != first_cookie
    assert sum(row.revoked_at is None for row in repository.sessions.values()) == 1
    assert client.get(f"{API_PREFIX}/sources").status_code == 200

    logged_out = client.post(f"{API_PREFIX}/auth/logout", headers=_unsafe_headers())
    assert logged_out.status_code == 204
    assert "max-age=0" in logged_out.headers["set-cookie"].lower()
    assert client.get(f"{API_PREFIX}/session").status_code == 401


def test_admin_creates_resets_and_disables_user_without_persisting_temporary_password() -> None:
    client, repository = _client()
    assert _login(client).status_code == 200
    assert client.post(
        f"{API_PREFIX}/auth/password/change",
        headers=_unsafe_headers(),
        json={
            "currentPassword": PASSWORD,
            "newPassword": "A new secure clinical passphrase 2026!",
        },
    ).status_code == 200

    created = client.post(
        f"{API_PREFIX}/admin/users",
        headers=_unsafe_headers(),
        json={
            "username": "reviewer.one",
            "displayName": "审核员一",
            "email": "reviewer.one@example.test",
            "roles": ["reviewer"],
        },
    )

    assert created.status_code == 201
    data = created.json()["data"]
    assert data["username"] == "reviewer.one"
    assert data["mustChangePassword"] is True
    assert 12 <= len(data["temporaryPassword"]) <= 128
    assert data["temporaryPassword"] not in repr(repository.created_users)

    reset = client.post(
        f"{API_PREFIX}/admin/users/{data['userId']}/password/reset",
        headers=_unsafe_headers(),
    )
    disabled = client.post(
        f"{API_PREFIX}/admin/users/{data['userId']}/status",
        headers=_unsafe_headers(),
        json={"status": "disabled"},
    )

    assert reset.status_code == 200
    assert disabled.status_code == 200
    assert repository.admin_events == [
        ("password_reset", "usr-admin", data["userId"]),
        ("disabled", "usr-admin", data["userId"]),
    ]


def test_non_local_environment_requires_secure_cookie_and_exact_origins(
    monkeypatch,
) -> None:
    monkeypatch.setenv("KNOWLEDGE_DEPLOYMENT_ENV", "production")
    monkeypatch.setenv("KNOWLEDGE_SESSION_COOKIE_SECURE", "false")
    with pytest.raises(RuntimeError, match="secure session cookies"):
        _secure_session_cookie()

    monkeypatch.setenv("KNOWLEDGE_SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("KNOWLEDGE_BROWSER_ORIGINS", "https://knowledge.example.test")
    assert _secure_session_cookie() is True
    assert _browser_origins() == frozenset({"https://knowledge.example.test"})

    monkeypatch.setenv("KNOWLEDGE_BROWSER_ORIGINS", "https://knowledge.example.test/path")
    with pytest.raises(RuntimeError, match="exact HTTP"):
        _browser_origins()
