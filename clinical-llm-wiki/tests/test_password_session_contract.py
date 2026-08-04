from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from importlib import import_module
from typing import Any

import pytest

from service.auth import ProductRole


NOW = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)


def _contract():
    try:
        return import_module("service.auth.password_sessions")
    except ModuleNotFoundError as exc:
        pytest.fail(f"P13 P2 密码与会话合同尚未实现：{exc}")


class FakePasswordRepository:
    def __init__(self, contract: Any, password_hash: str) -> None:
        self.contract = contract
        self.credential = contract.PasswordCredentialRecord(
            user_id="usr-admin",
            username_normalized="admin",
            password_hash=password_hash,
            must_change_password=True,
            failed_attempts=0,
            locked_until=None,
            status="active",
            display_name="平台管理员",
            roles=(ProductRole.PLATFORM_ADMIN,),
        )
        self.sessions: dict[str, Any] = {}
        self.created_users: list[dict[str, Any]] = []
        self.admin_events: list[tuple[str, str]] = []

    def find_credential(self, username_normalized: str):
        if username_normalized != self.credential.username_normalized:
            return None
        return self.credential

    def record_failed_login(self, *, user_id: str, failed_attempts: int, locked_until):
        assert user_id == self.credential.user_id
        self.credential = replace(
            self.credential,
            failed_attempts=failed_attempts,
            locked_until=locked_until,
        )

    def complete_login(self, *, user_id: str, authenticated_at, session):
        assert user_id == self.credential.user_id
        self.credential = replace(
            self.credential,
            failed_attempts=0,
            locked_until=None,
        )
        self.sessions[session.session_id_hash] = session

    def resolve_session(self, *, session_id_hash: str, now):
        session = self.sessions.get(session_id_hash)
        if session is None or session.revoked_at is not None or session.expires_at <= now:
            return None
        return self.contract.SessionLookupRecord(
            credential=self.credential,
            session=session,
        )

    def touch_session(self, *, session_id_hash: str, last_seen_at):
        self.sessions[session_id_hash] = replace(
            self.sessions[session_id_hash],
            last_seen_at=last_seen_at,
        )

    def revoke_session(self, *, session_id_hash: str, revoked_at):
        session = self.sessions.get(session_id_hash)
        if session is not None:
            self.sessions[session_id_hash] = replace(session, revoked_at=revoked_at)

    def complete_password_change(
        self,
        *,
        user_id: str,
        password_hash: str,
        changed_at,
        replacement_session,
    ):
        assert user_id == self.credential.user_id
        self.credential = replace(
            self.credential,
            password_hash=password_hash,
            must_change_password=False,
            failed_attempts=0,
            locked_until=None,
        )
        self.sessions = {
            key: replace(value, revoked_at=changed_at)
            for key, value in self.sessions.items()
        }
        self.sessions[replacement_session.session_id_hash] = replacement_session

    def create_local_user(self, **facts):
        self.created_users.append(facts)
        self.admin_events.append(("created", facts["user_id"]))

    def reset_user_password(self, *, user_id, password_hash, changed_at, actor_id):
        del password_hash, changed_at
        self.admin_events.append(("password_reset", f"{actor_id}:{user_id}"))

    def set_user_status(self, *, user_id, status, changed_at, actor_id):
        del changed_at
        self.admin_events.append((status, f"{actor_id}:{user_id}"))


def _service(*, password: str = "Correct horse battery staple 2026!"):
    contract = _contract()
    hasher = contract.Argon2idPasswordHasher()
    repository = FakePasswordRepository(contract, hasher.hash(password))
    tokens = iter(["raw-session-one", "raw-session-two", "raw-session-three"])
    service = contract.PasswordSessionService(
        repository=repository,
        hasher=hasher,
        policy=contract.PasswordSessionPolicy(
            maximum_failed_attempts=5,
            lock_duration=timedelta(minutes=15),
            session_lifetime=timedelta(hours=8),
            session_idle_timeout=timedelta(minutes=30),
        ),
        clock=lambda: NOW,
        token_factory=lambda: next(tokens),
    )
    return contract, repository, service


def test_argon2id_hash_never_contains_plaintext_and_meets_frozen_parameters() -> None:
    contract = _contract()
    hasher = contract.Argon2idPasswordHasher()
    password = "Correct horse battery staple 2026!"

    encoded = hasher.hash(password)

    assert encoded.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert password not in encoded
    assert hasher.verify(encoded, password) is True
    assert hasher.verify(encoded, "wrong password") is False


def test_login_normalizes_username_and_persists_only_session_sha256() -> None:
    contract, repository, service = _service()

    result = service.login(
        username="  ADMIN  ",
        password="Correct horse battery staple 2026!",
    )

    expected_hash = sha256(b"raw-session-one").hexdigest()
    assert result.raw_session_id == "raw-session-one"
    assert set(repository.sessions) == {expected_hash}
    assert "raw-session-one" not in repr(repository.sessions)
    assert result.actor.actor_id == "usr-admin"
    assert result.must_change_password is True
    assert result.expires_at == NOW + timedelta(hours=8)


def test_login_allows_an_existing_short_password_to_be_upgraded() -> None:
    contract, _, service = _service(password="legacy12")

    login = service.login(username="admin", password="legacy12")
    replacement = service.change_password(
        raw_session_id=login.raw_session_id,
        current_password="legacy12",
        new_password="A replacement password meeting policy 2026!",
    )

    assert login.must_change_password is True
    assert service.authenticate_session(replacement.raw_session_id).must_change_password is False


def test_unknown_and_wrong_password_share_the_same_public_error() -> None:
    contract, _, service = _service()

    for username, password in (
        ("missing", "anything long enough"),
        ("admin", "wrong password value"),
    ):
        with pytest.raises(contract.InvalidCredentialsError, match="用户名或密码错误"):
            service.login(username=username, password=password)


def test_fifth_failure_locks_account_without_exposing_password() -> None:
    contract, repository, service = _service()

    for _ in range(4):
        with pytest.raises(contract.InvalidCredentialsError):
            service.login(username="admin", password="wrong password value")

    with pytest.raises(contract.AccountLockedError, match="稍后重试"):
        service.login(username="admin", password="wrong password value")

    assert repository.credential.failed_attempts == 5
    assert repository.credential.locked_until == NOW + timedelta(minutes=15)
    assert "wrong password value" not in repr(repository.credential)


def test_session_authentication_is_idle_bounded_and_logout_revokes_server_state() -> None:
    contract, repository, service = _service()
    login = service.login(
        username="admin",
        password="Correct horse battery staple 2026!",
    )

    principal = service.authenticate_session(login.raw_session_id)

    assert principal.actor.actor_id == "usr-admin"
    assert principal.must_change_password is True
    session_hash = sha256(login.raw_session_id.encode("utf-8")).hexdigest()
    assert repository.sessions[session_hash].last_seen_at == NOW

    service.logout(login.raw_session_id)
    with pytest.raises(contract.SessionAuthenticationError, match="会话无效或已过期"):
        service.authenticate_session(login.raw_session_id)


def test_password_change_verifies_current_password_revokes_old_session_and_replaces_it() -> None:
    contract, _, service = _service()
    login = service.login(
        username="admin",
        password="Correct horse battery staple 2026!",
    )

    replacement = service.change_password(
        raw_session_id=login.raw_session_id,
        current_password="Correct horse battery staple 2026!",
        new_password="A new secure clinical passphrase 2026!",
    )

    with pytest.raises(contract.SessionAuthenticationError):
        service.authenticate_session(login.raw_session_id)
    assert service.authenticate_session(replacement.raw_session_id).must_change_password is False
    assert service.login(
        username="admin",
        password="A new secure clinical passphrase 2026!",
    ).actor.actor_id == "usr-admin"


def test_admin_user_management_returns_temporary_password_once_and_never_persists_it() -> None:
    contract, repository, service = _service()
    actor = service.login(username="admin", password="Correct horse battery staple 2026!").actor

    created = service.create_user(
        actor=actor,
        username="  Reviewer.One ",
        display_name="审核员一",
        email="reviewer.one@example.test",
        roles=(ProductRole.REVIEWER,),
    )

    assert created.username == "reviewer.one"
    assert 12 <= len(created.temporary_password) <= 128
    stored = repository.created_users[0]
    assert stored["username_normalized"] == "reviewer.one"
    assert stored["password_hash"].startswith("$argon2id$")
    assert created.temporary_password not in repr(stored)
    assert stored["must_change_password"] is True


def test_admin_create_rejects_invalid_username_as_managed_input_error() -> None:
    contract, _, service = _service()
    actor = service.login(username="admin", password="Correct horse battery staple 2026!").actor

    with pytest.raises(contract.UserManagementError, match="用户名"):
        service.create_user(
            actor=actor,
            username="bad username",
            display_name="无效用户",
            email="invalid@example.test",
            roles=(ProductRole.REVIEWER,),
        )


def test_admin_reset_and_disable_are_auditable_without_using_human_password_for_workers() -> None:
    _, repository, service = _service()
    actor = service.login(username="admin", password="Correct horse battery staple 2026!").actor

    reset = service.reset_user_password(actor=actor, user_id="usr-reviewer")
    service.set_user_status(actor=actor, user_id="usr-reviewer", status="disabled")

    assert 12 <= len(reset.temporary_password) <= 128
    assert repository.admin_events == [
        ("password_reset", "usr-admin:usr-reviewer"),
        ("disabled", "usr-admin:usr-reviewer"),
    ]
    assert "service_account" not in repr(repository.created_users)


@pytest.mark.parametrize(
    "password",
    ["", "x" * 129, "contains-null\x00password"],
)
def test_login_rejects_empty_oversized_and_nul_password_inputs(password: str) -> None:
    contract, _, service = _service()

    with pytest.raises(contract.PasswordPolicyError):
        service.login(username="admin", password=password)


@pytest.mark.parametrize(
    "password",
    ["short", "x" * 129, "contains-null\x00password"],
)
def test_password_change_rejects_unsafe_new_password(password: str) -> None:
    contract, _, service = _service()
    login = service.login(
        username="admin",
        password="Correct horse battery staple 2026!",
    )

    with pytest.raises(contract.PasswordPolicyError):
        service.change_password(
            raw_session_id=login.raw_session_id,
            current_password="Correct horse battery staple 2026!",
            new_password=password,
        )
