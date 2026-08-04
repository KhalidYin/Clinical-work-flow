"""Human password authentication and opaque server-side browser sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from typing import Callable, Protocol
from unicodedata import normalize
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .identity_authorization import (
    ActorContext,
    IdentitySource,
    Permission,
    PrincipalType,
    ProductRole,
    ROLE_PERMISSIONS,
    require_permission,
)
from service.db.models import (
    AuditEvent,
    BrowserSession,
    PlatformUser,
    RoleBinding,
    UserCredential,
)


class PasswordSessionError(RuntimeError):
    """Base error for the human authentication boundary."""


class PasswordPolicyError(PasswordSessionError):
    """A password cannot be accepted by the local policy."""


class InvalidCredentialsError(PasswordSessionError):
    """The submitted username/password pair is invalid."""


class AccountLockedError(PasswordSessionError):
    """Authentication is temporarily blocked after repeated failures."""


class SessionAuthenticationError(PasswordSessionError):
    """The opaque browser session is missing, expired, or revoked."""


class PasswordChangeError(PasswordSessionError):
    """The current password cannot authorize a password change."""


class UserManagementError(PasswordSessionError):
    """A local user management operation cannot be completed."""


class UserConflictError(UserManagementError):
    """A username or user identifier already exists."""


class UserNotFoundError(UserManagementError):
    """The requested local user does not exist."""


@dataclass(frozen=True, slots=True)
class PasswordSessionPolicy:
    maximum_failed_attempts: int = 5
    lock_duration: timedelta = timedelta(minutes=15)
    session_lifetime: timedelta = timedelta(hours=8)
    session_idle_timeout: timedelta = timedelta(minutes=30)
    minimum_password_length: int = 12
    maximum_password_length: int = 128

    def __post_init__(self) -> None:
        if self.maximum_failed_attempts < 1:
            raise ValueError("maximum_failed_attempts must be positive")
        if min(
            self.lock_duration.total_seconds(),
            self.session_lifetime.total_seconds(),
            self.session_idle_timeout.total_seconds(),
        ) <= 0:
            raise ValueError("password/session durations must be positive")
        if not 1 <= self.minimum_password_length <= self.maximum_password_length:
            raise ValueError("password length bounds are invalid")


@dataclass(frozen=True, slots=True)
class PasswordCredentialRecord:
    user_id: str
    username_normalized: str
    password_hash: str
    must_change_password: bool
    failed_attempts: int
    locked_until: datetime | None
    status: str
    display_name: str
    roles: tuple[ProductRole, ...]


@dataclass(frozen=True, slots=True)
class StoredBrowserSession:
    session_id_hash: str
    user_id: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SessionLookupRecord:
    credential: PasswordCredentialRecord
    session: StoredBrowserSession


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    actor: ActorContext
    must_change_password: bool
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class NewBrowserSession(AuthenticatedPrincipal):
    raw_session_id: str


@dataclass(frozen=True, slots=True)
class AdminTemporaryPasswordResult:
    user_id: str
    username: str
    temporary_password: str


class PasswordHasherPort(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, encoded_hash: str, password: str) -> bool: ...


class PasswordSessionRepositoryPort(Protocol):
    def find_credential(self, username_normalized: str) -> PasswordCredentialRecord | None: ...

    def record_failed_login(
        self,
        *,
        user_id: str,
        failed_attempts: int,
        locked_until: datetime | None,
    ) -> None: ...

    def complete_login(
        self,
        *,
        user_id: str,
        authenticated_at: datetime,
        session: StoredBrowserSession,
    ) -> None: ...

    def resolve_session(
        self,
        *,
        session_id_hash: str,
        now: datetime,
    ) -> SessionLookupRecord | None: ...

    def touch_session(self, *, session_id_hash: str, last_seen_at: datetime) -> None: ...

    def revoke_session(self, *, session_id_hash: str, revoked_at: datetime) -> None: ...

    def complete_password_change(
        self,
        *,
        user_id: str,
        password_hash: str,
        changed_at: datetime,
        replacement_session: StoredBrowserSession,
    ) -> None: ...

    def create_local_user(
        self,
        *,
        user_id: str,
        username_normalized: str,
        display_name: str,
        email: str,
        roles: tuple[ProductRole, ...],
        password_hash: str,
        must_change_password: bool,
        created_at: datetime,
        actor_id: str,
    ) -> None: ...

    def reset_user_password(
        self,
        *,
        user_id: str,
        password_hash: str,
        changed_at: datetime,
        actor_id: str,
    ) -> None: ...

    def set_user_status(
        self,
        *,
        user_id: str,
        status: str,
        changed_at: datetime,
        actor_id: str,
    ) -> None: ...


class Argon2idPasswordHasher:
    """Argon2id wrapper with the frozen P13 minimum parameter set."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher(
            time_cost=2,
            memory_cost=19_456,
            parallelism=1,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, encoded_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(encoded_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False


class PasswordSessionService:
    """Authenticate humans while keeping all browser credentials opaque."""

    def __init__(
        self,
        *,
        repository: PasswordSessionRepositoryPort,
        hasher: PasswordHasherPort,
        policy: PasswordSessionPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        token_factory: Callable[[], str] | None = None,
        temporary_password_factory: Callable[[], str] | None = None,
        user_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository
        self._hasher = hasher
        self._policy = policy or PasswordSessionPolicy()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._token_factory = token_factory or (lambda: token_urlsafe(32))
        self._temporary_password_factory = temporary_password_factory or (
            lambda: token_urlsafe(18)
        )
        self._user_id_factory = user_id_factory or (lambda: f"usr-{uuid4().hex}")
        self._dummy_password_hash = hasher.hash("P13 dummy verification password only")

    def login(self, *, username: str, password: str) -> NewBrowserSession:
        self._validate_existing_password_shape(password)
        username_normalized = self.normalize_username(username)
        now = self._clock()
        credential = self._repository.find_credential(username_normalized)
        password_hash = (
            credential.password_hash if credential is not None else self._dummy_password_hash
        )
        password_matches = self._hasher.verify(password_hash, password)

        if credential is None or credential.status != "active":
            raise InvalidCredentialsError("用户名或密码错误。")
        if credential.locked_until is not None and credential.locked_until > now:
            raise AccountLockedError("登录失败次数过多，请稍后重试。")
        if not password_matches:
            failures = credential.failed_attempts + 1
            locked_until = (
                now + self._policy.lock_duration
                if failures >= self._policy.maximum_failed_attempts
                else None
            )
            self._repository.record_failed_login(
                user_id=credential.user_id,
                failed_attempts=failures,
                locked_until=locked_until,
            )
            if locked_until is not None:
                raise AccountLockedError("登录失败次数过多，请稍后重试。")
            raise InvalidCredentialsError("用户名或密码错误。")

        raw_session_id, stored_session = self._new_session(credential.user_id, now)
        self._repository.complete_login(
            user_id=credential.user_id,
            authenticated_at=now,
            session=stored_session,
        )
        return NewBrowserSession(
            actor=self._actor(credential),
            must_change_password=credential.must_change_password,
            expires_at=stored_session.expires_at,
            raw_session_id=raw_session_id,
        )

    def authenticate_session(self, raw_session_id: str) -> AuthenticatedPrincipal:
        if not raw_session_id:
            raise SessionAuthenticationError("会话无效或已过期。")
        now = self._clock()
        session_id_hash = self._session_hash(raw_session_id)
        lookup = self._repository.resolve_session(session_id_hash=session_id_hash, now=now)
        if lookup is None:
            raise SessionAuthenticationError("会话无效或已过期。")
        if (
            lookup.credential.status != "active"
            or now - lookup.session.last_seen_at > self._policy.session_idle_timeout
        ):
            self._repository.revoke_session(
                session_id_hash=session_id_hash,
                revoked_at=now,
            )
            raise SessionAuthenticationError("会话无效或已过期。")
        self._repository.touch_session(session_id_hash=session_id_hash, last_seen_at=now)
        return AuthenticatedPrincipal(
            actor=self._actor(lookup.credential),
            must_change_password=lookup.credential.must_change_password,
            expires_at=lookup.session.expires_at,
        )

    def logout(self, raw_session_id: str) -> None:
        if raw_session_id:
            self._repository.revoke_session(
                session_id_hash=self._session_hash(raw_session_id),
                revoked_at=self._clock(),
            )

    def change_password(
        self,
        *,
        raw_session_id: str,
        current_password: str,
        new_password: str,
    ) -> NewBrowserSession:
        self._validate_existing_password_shape(current_password)
        self._validate_password_shape(new_password)
        principal = self.authenticate_session(raw_session_id)
        now = self._clock()
        lookup = self._repository.resolve_session(
            session_id_hash=self._session_hash(raw_session_id),
            now=now,
        )
        if lookup is None or not self._hasher.verify(
            lookup.credential.password_hash,
            current_password,
        ):
            raise PasswordChangeError("当前密码错误。")
        if self._hasher.verify(lookup.credential.password_hash, new_password):
            raise PasswordPolicyError("新密码不能与当前密码相同。")

        raw_replacement, stored_replacement = self._new_session(
            lookup.credential.user_id,
            now,
        )
        self._repository.complete_password_change(
            user_id=lookup.credential.user_id,
            password_hash=self._hasher.hash(new_password),
            changed_at=now,
            replacement_session=stored_replacement,
        )
        return NewBrowserSession(
            actor=principal.actor,
            must_change_password=False,
            expires_at=stored_replacement.expires_at,
            raw_session_id=raw_replacement,
        )

    def create_user(
        self,
        *,
        actor: ActorContext,
        username: str,
        display_name: str,
        email: str,
        roles: tuple[ProductRole, ...],
        require_password_change: bool = True,
    ) -> AdminTemporaryPasswordResult:
        require_permission(actor, Permission.ADMIN_MANAGE_USERS)
        require_permission(actor, Permission.ADMIN_MANAGE_ROLES)
        try:
            username_normalized = self.normalize_username(username)
        except InvalidCredentialsError as exc:
            raise UserManagementError("用户名格式无效。") from exc
        if not display_name.strip() or len(display_name) > 240:
            raise UserManagementError("用户显示名称无效。")
        if not self._valid_email(email):
            raise UserManagementError("用户邮箱无效。")
        if not roles or ProductRole.SERVICE_ACCOUNT in roles or len(set(roles)) != len(roles):
            raise UserManagementError("用户角色无效。")
        temporary_password = self._temporary_password_factory()
        self._validate_password_shape(temporary_password)
        user_id = self._user_id_factory()
        self._repository.create_local_user(
            user_id=user_id,
            username_normalized=username_normalized,
            display_name=display_name.strip(),
            email=email.strip(),
            roles=roles,
            password_hash=self._hasher.hash(temporary_password),
            must_change_password=require_password_change,
            created_at=self._clock(),
            actor_id=actor.actor_id,
        )
        return AdminTemporaryPasswordResult(
            user_id=user_id,
            username=username_normalized,
            temporary_password=temporary_password,
        )

    def reset_user_password(
        self,
        *,
        actor: ActorContext,
        user_id: str,
    ) -> AdminTemporaryPasswordResult:
        require_permission(actor, Permission.ADMIN_MANAGE_USERS)
        temporary_password = self._temporary_password_factory()
        self._validate_password_shape(temporary_password)
        self._repository.reset_user_password(
            user_id=user_id,
            password_hash=self._hasher.hash(temporary_password),
            changed_at=self._clock(),
            actor_id=actor.actor_id,
        )
        return AdminTemporaryPasswordResult(
            user_id=user_id,
            username="",
            temporary_password=temporary_password,
        )

    def set_user_status(
        self,
        *,
        actor: ActorContext,
        user_id: str,
        status: str,
    ) -> None:
        require_permission(actor, Permission.ADMIN_MANAGE_USERS)
        if status not in {"active", "disabled"}:
            raise UserManagementError("用户状态无效。")
        if actor.actor_id == user_id and status == "disabled":
            raise UserManagementError("管理员不能禁用当前登录用户。")
        self._repository.set_user_status(
            user_id=user_id,
            status=status,
            changed_at=self._clock(),
            actor_id=actor.actor_id,
        )

    @staticmethod
    def normalize_username(username: str) -> str:
        value = normalize("NFKC", username).strip().casefold()
        if not value or len(value) > 160 or any(char.isspace() for char in value):
            raise InvalidCredentialsError("用户名或密码错误。")
        return value

    def _validate_password_shape(self, password: str) -> None:
        if (
            "\x00" in password
            or len(password) < self._policy.minimum_password_length
            or len(password) > self._policy.maximum_password_length
        ):
            raise PasswordPolicyError("密码长度或字符不符合安全要求。")

    def _validate_existing_password_shape(self, password: str) -> None:
        """Permit legacy/bootstrap hashes to authenticate so they can be upgraded."""

        if (
            not password
            or "\x00" in password
            or len(password) > self._policy.maximum_password_length
        ):
            raise PasswordPolicyError("密码长度或字符不符合安全要求。")

    @staticmethod
    def _valid_email(email: str) -> bool:
        value = email.strip()
        return (
            3 <= len(value) <= 320
            and "@" in value
            and not any(char.isspace() for char in value)
        )

    def _new_session(self, user_id: str, now: datetime) -> tuple[str, StoredBrowserSession]:
        raw_session_id = self._token_factory()
        stored = StoredBrowserSession(
            session_id_hash=self._session_hash(raw_session_id),
            user_id=user_id,
            created_at=now,
            last_seen_at=now,
            expires_at=now + self._policy.session_lifetime,
        )
        return raw_session_id, stored

    @staticmethod
    def _session_hash(raw_session_id: str) -> str:
        return sha256(raw_session_id.encode("utf-8")).hexdigest()

    @staticmethod
    def _actor(credential: PasswordCredentialRecord) -> ActorContext:
        permissions: set[Permission] = set()
        for role in credential.roles:
            permissions.update(ROLE_PERMISSIONS[role])
        return ActorContext(
            actor_id=credential.user_id,
            display_name=credential.display_name,
            principal_type=PrincipalType.HUMAN,
            roles=frozenset(credential.roles),
            permissions=frozenset(permissions),
            identity_source=IdentitySource.LOCAL_PASSWORD,
        )


class SqlAlchemyPasswordSessionRepository:
    """PostgreSQL adapter that never persists a raw browser session value."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def find_credential(self, username_normalized: str) -> PasswordCredentialRecord | None:
        with self._session_factory() as session:
            row = session.execute(
                select(UserCredential, PlatformUser)
                .join(PlatformUser, PlatformUser.user_id == UserCredential.user_id)
                .where(UserCredential.username_normalized == username_normalized)
            ).one_or_none()
            if row is None:
                return None
            credential, user = row
            return self._credential_record(session, credential, user)

    def record_failed_login(
        self,
        *,
        user_id: str,
        failed_attempts: int,
        locked_until: datetime | None,
    ) -> None:
        with self._session_factory.begin() as session:
            credential = session.get(UserCredential, user_id)
            if credential is None:
                return
            credential.failed_attempts = failed_attempts
            credential.locked_until = locked_until
            credential.updated_at = datetime.now(timezone.utc)

    def complete_login(
        self,
        *,
        user_id: str,
        authenticated_at: datetime,
        session: StoredBrowserSession,
    ) -> None:
        with self._session_factory.begin() as database:
            credential = database.get(UserCredential, user_id)
            user = database.get(PlatformUser, user_id)
            if credential is None or user is None:
                raise SessionAuthenticationError("用户凭据不存在。")
            credential.failed_attempts = 0
            credential.locked_until = None
            credential.updated_at = authenticated_at
            user.last_authenticated_at = authenticated_at
            user.updated_at = authenticated_at
            database.add(self._session_row(session))

    def resolve_session(
        self,
        *,
        session_id_hash: str,
        now: datetime,
    ) -> SessionLookupRecord | None:
        with self._session_factory() as database:
            row = database.execute(
                select(BrowserSession, UserCredential, PlatformUser)
                .join(UserCredential, UserCredential.user_id == BrowserSession.user_id)
                .join(PlatformUser, PlatformUser.user_id == BrowserSession.user_id)
                .where(
                    BrowserSession.session_id_hash == session_id_hash,
                    BrowserSession.revoked_at.is_(None),
                    BrowserSession.expires_at > now,
                )
            ).one_or_none()
            if row is None:
                return None
            stored, credential, user = row
            return SessionLookupRecord(
                credential=self._credential_record(database, credential, user),
                session=StoredBrowserSession(
                    session_id_hash=stored.session_id_hash,
                    user_id=stored.user_id,
                    created_at=stored.created_at,
                    last_seen_at=stored.last_seen_at,
                    expires_at=stored.expires_at,
                    revoked_at=stored.revoked_at,
                ),
            )

    def touch_session(self, *, session_id_hash: str, last_seen_at: datetime) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                update(BrowserSession)
                .where(
                    BrowserSession.session_id_hash == session_id_hash,
                    BrowserSession.revoked_at.is_(None),
                )
                .values(last_seen_at=last_seen_at)
            )

    def revoke_session(self, *, session_id_hash: str, revoked_at: datetime) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                update(BrowserSession)
                .where(
                    BrowserSession.session_id_hash == session_id_hash,
                    BrowserSession.revoked_at.is_(None),
                )
                .values(revoked_at=revoked_at)
            )

    def complete_password_change(
        self,
        *,
        user_id: str,
        password_hash: str,
        changed_at: datetime,
        replacement_session: StoredBrowserSession,
    ) -> None:
        with self._session_factory.begin() as session:
            credential = session.get(UserCredential, user_id)
            if credential is None:
                raise SessionAuthenticationError("用户凭据不存在。")
            credential.password_hash = password_hash
            credential.must_change_password = False
            credential.failed_attempts = 0
            credential.locked_until = None
            credential.password_changed_at = changed_at
            credential.updated_at = changed_at
            session.execute(
                update(BrowserSession)
                .where(
                    BrowserSession.user_id == user_id,
                    BrowserSession.revoked_at.is_(None),
                )
                .values(revoked_at=changed_at)
            )
            session.add(self._session_row(replacement_session))

    def create_local_user(
        self,
        *,
        user_id: str,
        username_normalized: str,
        display_name: str,
        email: str,
        roles: tuple[ProductRole, ...],
        password_hash: str,
        must_change_password: bool,
        created_at: datetime,
        actor_id: str,
    ) -> None:
        try:
            with self._session_factory.begin() as session:
                session.add(
                    PlatformUser(
                        user_id=user_id,
                        identity_source=IdentitySource.LOCAL_PASSWORD.value,
                        issuer="local://password",
                        subject=username_normalized,
                        display_name=display_name,
                        email=email,
                        status="active",
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
                session.flush()
                session.add(
                    UserCredential(
                        user_id=user_id,
                        username_normalized=username_normalized,
                        password_hash=password_hash,
                        must_change_password=must_change_password,
                        password_changed_at=created_at,
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
                for role in roles:
                    session.add(
                        RoleBinding(
                            user_id=user_id,
                            role=role.value,
                            granted_by_actor_id=actor_id,
                            created_at=created_at,
                        )
                    )
                self._add_user_audit(
                    session,
                    actor_id=actor_id,
                    action="platform_user.created",
                    user_id=user_id,
                    details={
                        "result": "active",
                        "roles": sorted(role.value for role in roles),
                    },
                    created_at=created_at,
                )
        except IntegrityError as exc:
            raise UserConflictError("用户名或用户标识已存在。") from exc

    def reset_user_password(
        self,
        *,
        user_id: str,
        password_hash: str,
        changed_at: datetime,
        actor_id: str,
    ) -> None:
        with self._session_factory.begin() as session:
            credential = session.get(UserCredential, user_id)
            if credential is None:
                raise UserNotFoundError("用户不存在。")
            credential.password_hash = password_hash
            credential.must_change_password = True
            credential.failed_attempts = 0
            credential.locked_until = None
            credential.password_changed_at = changed_at
            credential.updated_at = changed_at
            session.execute(
                update(BrowserSession)
                .where(
                    BrowserSession.user_id == user_id,
                    BrowserSession.revoked_at.is_(None),
                )
                .values(revoked_at=changed_at)
            )
            self._add_user_audit(
                session,
                actor_id=actor_id,
                action="platform_user.password_reset",
                user_id=user_id,
                details={"result": "must_change_password"},
                created_at=changed_at,
            )

    def set_user_status(
        self,
        *,
        user_id: str,
        status: str,
        changed_at: datetime,
        actor_id: str,
    ) -> None:
        with self._session_factory.begin() as session:
            user = session.get(PlatformUser, user_id)
            if user is None:
                raise UserNotFoundError("用户不存在。")
            user.status = status
            user.updated_at = changed_at
            if status == "disabled":
                session.execute(
                    update(BrowserSession)
                    .where(
                        BrowserSession.user_id == user_id,
                        BrowserSession.revoked_at.is_(None),
                    )
                    .values(revoked_at=changed_at)
                )
            self._add_user_audit(
                session,
                actor_id=actor_id,
                action=f"platform_user.{status}",
                user_id=user_id,
                details={"result": status},
                created_at=changed_at,
            )

    @staticmethod
    def _session_row(record: StoredBrowserSession) -> BrowserSession:
        return BrowserSession(
            session_id_hash=record.session_id_hash,
            user_id=record.user_id,
            created_at=record.created_at,
            last_seen_at=record.last_seen_at,
            expires_at=record.expires_at,
            revoked_at=record.revoked_at,
        )

    @staticmethod
    def _add_user_audit(
        session: Session,
        *,
        actor_id: str,
        action: str,
        user_id: str,
        details: dict[str, object],
        created_at: datetime,
    ) -> None:
        session.add(
            AuditEvent(
                audit_event_id=f"audit-{uuid4().hex}",
                actor_subject=actor_id,
                action=action,
                entity_type="platform_user",
                entity_id=user_id,
                details=details,
                created_at=created_at,
            )
        )

    @staticmethod
    def _credential_record(
        session: Session,
        credential: UserCredential,
        user: PlatformUser,
    ) -> PasswordCredentialRecord:
        roles = tuple(
            ProductRole(role)
            for role in session.scalars(
                select(RoleBinding.role)
                .where(RoleBinding.user_id == user.user_id)
                .order_by(RoleBinding.role)
            )
        )
        if not roles:
            raise SessionAuthenticationError("用户没有产品角色。")
        return PasswordCredentialRecord(
            user_id=user.user_id,
            username_normalized=credential.username_normalized,
            password_hash=credential.password_hash,
            must_change_password=credential.must_change_password,
            failed_attempts=credential.failed_attempts,
            locked_until=credential.locked_until,
            status=user.status,
            display_name=user.display_name,
            roles=roles,
        )
