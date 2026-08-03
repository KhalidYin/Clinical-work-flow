"""One-time local administrator bootstrap configured by the Compose environment."""

from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Mapping

from service.auth.identity_authorization import (
    ActorContext,
    IdentitySource,
    PrincipalType,
    ProductRole,
    ROLE_PERMISSIONS,
)
from service.auth.password_sessions import (
    Argon2idPasswordHasher,
    PasswordSessionPolicy,
    PasswordSessionService,
    SqlAlchemyPasswordSessionRepository,
)
from service.db.session import (
    create_database_engine,
    create_session_factory,
    database_url_from_environment,
)


@dataclass(frozen=True, slots=True)
class AdminBootstrapConfig:
    username: str
    password: str
    display_name: str
    email: str
    minimum_password_length: int


def admin_bootstrap_config_from_environment(
    environment: Mapping[str, str],
) -> AdminBootstrapConfig:
    """Load fail-closed local bootstrap settings without logging their values."""

    required_names = (
        "KNOWLEDGE_ADMIN_USERNAME",
        "KNOWLEDGE_ADMIN_PASSWORD",
        "KNOWLEDGE_ADMIN_DISPLAY_NAME",
        "KNOWLEDGE_ADMIN_EMAIL",
    )
    values: dict[str, str] = {}
    for name in required_names:
        value = environment.get(name, "").strip()
        if not value:
            raise RuntimeError(f"缺少必需的管理员初始化环境变量：{name}")
        values[name] = value

    length_name = "KNOWLEDGE_ADMIN_INITIAL_PASSWORD_MIN_LENGTH"
    raw_minimum_length = environment.get(length_name, "12").strip()
    try:
        minimum_password_length = int(raw_minimum_length)
    except ValueError as exc:
        raise RuntimeError(f"{length_name} 必须是整数") from exc
    if not 8 <= minimum_password_length <= 128:
        raise RuntimeError(f"{length_name} 必须在 8 到 128 之间")

    return AdminBootstrapConfig(
        username=values["KNOWLEDGE_ADMIN_USERNAME"],
        password=values["KNOWLEDGE_ADMIN_PASSWORD"],
        display_name=values["KNOWLEDGE_ADMIN_DISPLAY_NAME"],
        email=values["KNOWLEDGE_ADMIN_EMAIL"],
        minimum_password_length=minimum_password_length,
    )


def bootstrap_local_admin(
    *,
    session_factory,
    username: str,
    password: str,
    display_name: str,
    email: str,
    minimum_password_length: int = 12,
) -> bool:
    """Create the first local administrator; never overwrite an existing credential."""

    repository = SqlAlchemyPasswordSessionRepository(session_factory)
    normalized = PasswordSessionService.normalize_username(username)
    if repository.find_credential(normalized) is not None:
        return False
    bootstrap_actor = ActorContext(
        actor_id="local-admin-bootstrap",
        display_name="本地管理员引导程序",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({ProductRole.PLATFORM_ADMIN}),
        permissions=ROLE_PERMISSIONS[ProductRole.PLATFORM_ADMIN],
        identity_source=IdentitySource.LOCAL_TEST,
    )
    service = PasswordSessionService(
        repository=repository,
        hasher=Argon2idPasswordHasher(),
        policy=PasswordSessionPolicy(minimum_password_length=minimum_password_length),
        temporary_password_factory=lambda: password,
    )
    service.create_user(
        actor=bootstrap_actor,
        username=normalized,
        display_name=display_name,
        email=email,
        roles=(ProductRole.PLATFORM_ADMIN,),
    )
    return True


def main(environment: Mapping[str, str] | None = None) -> None:
    config = admin_bootstrap_config_from_environment(
        environ if environment is None else environment
    )
    engine = create_database_engine(database_url_from_environment())
    try:
        created = bootstrap_local_admin(
            session_factory=create_session_factory(engine),
            username=config.username,
            password=config.password,
            display_name=config.display_name,
            email=config.email,
            minimum_password_length=config.minimum_password_length,
        )
    finally:
        engine.dispose()
    state = "已创建" if created else "已存在，未修改"
    print(
        f"本地管理员 {config.username} {state}；"
        "数据库仅保存 Argon2id 哈希，初始化程序未输出密码。"
    )


if __name__ == "__main__":
    main()
