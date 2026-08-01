"""One-time local administrator bootstrap with password supplied through stdin."""

from __future__ import annotations

import argparse
import sys

from service.auth.identity_authorization import (
    ActorContext,
    IdentitySource,
    PrincipalType,
    ProductRole,
    ROLE_PERMISSIONS,
)
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


def bootstrap_local_admin(
    *,
    session_factory,
    username: str,
    password: str,
    display_name: str,
    email: str,
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


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="通过标准输入创建本地平台管理员")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--display-name", default="系统管理员")
    parser.add_argument("--email", default="admin@knowledge.local")
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    password = sys.stdin.readline().rstrip("\r\n")
    if not password:
        raise RuntimeError("必须通过标准输入提供初始管理员密码")
    engine = create_database_engine(database_url_from_environment())
    try:
        created = bootstrap_local_admin(
            session_factory=create_session_factory(engine),
            username=args.username,
            password=password,
            display_name=args.display_name,
            email=args.email,
        )
    finally:
        engine.dispose()
    state = "已创建" if created else "已存在，未修改"
    print(f"本地管理员 {args.username} {state}；密码未写入磁盘或日志。")


if __name__ == "__main__":
    main()
