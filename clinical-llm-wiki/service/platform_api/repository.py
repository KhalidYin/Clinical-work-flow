"""Read models and PostgreSQL adapter for prerelease platform routes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from service.auth import PlatformUserGrant
from service.db.models import (
    PlatformUser,
    Release,
    RoleBinding,
    Source,
    SourceArtifact,
    SourceVersion,
)


@dataclass(frozen=True, slots=True)
class CurrentReleaseRecord:
    release_id: str
    version: str
    status: str
    index_version: str
    released_at: datetime | None


@dataclass(frozen=True, slots=True)
class SourceSummaryRecord:
    source_id: str
    title: str
    version: str
    media_type: str
    rights: str
    status: str
    source_hash: str
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PlatformUserRecord:
    user_id: str
    display_name: str
    email: str
    identity_source: str
    roles: tuple[str, ...]
    status: str
    last_active_at: datetime | None


class PlatformReadRepository(Protocol):
    def resolve_user(self, *, issuer: str, subject: str) -> PlatformUserGrant | None: ...

    def database_available(self) -> bool: ...

    def get_current_release(self) -> CurrentReleaseRecord | None: ...

    def list_sources(self) -> tuple[Sequence[SourceSummaryRecord], Sequence[str]]: ...

    def list_platform_users(
        self,
    ) -> tuple[Sequence[PlatformUserRecord], Sequence[str]]: ...


class SqlAlchemyPlatformRepository:
    """Read-only adapter over the canonical SQLAlchemy metadata."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def resolve_user(self, *, issuer: str, subject: str) -> PlatformUserGrant | None:
        with self._session_factory() as session:
            user = session.scalar(
                select(PlatformUser).where(
                    PlatformUser.issuer == issuer,
                    PlatformUser.subject == subject,
                )
            )
            if user is None:
                return None
            roles = tuple(
                session.scalars(
                    select(RoleBinding.role)
                    .where(RoleBinding.user_id == user.user_id)
                    .order_by(RoleBinding.role)
                )
            )
        if not roles:
            return None
        return PlatformUserGrant(
            user_id=user.user_id,
            identity_source=user.identity_source,
            issuer=user.issuer,
            subject=user.subject,
            display_name=user.display_name,
            email=user.email,
            status=user.status,
            roles=roles,
        )

    def database_available(self) -> bool:
        try:
            with self._session_factory() as session:
                session.execute(select(1)).scalar_one()
        except SQLAlchemyError:
            return False
        return True

    def get_current_release(self) -> CurrentReleaseRecord | None:
        with self._session_factory() as session:
            release = session.scalar(
                select(Release)
                .where(Release.status == "released")
                .order_by(Release.published_at.desc().nullslast(), Release.created_at.desc())
                .limit(1)
            )
        if release is None:
            return None
        return CurrentReleaseRecord(
            release_id=release.release_id,
            version=release.version,
            status="released",
            index_version=release.index_manifest_version,
            released_at=release.published_at,
        )

    def list_sources(self) -> tuple[list[SourceSummaryRecord], list[str]]:
        with self._session_factory() as session:
            sources = list(session.scalars(select(Source).order_by(Source.title, Source.source_id)))
            versions = list(
                session.scalars(
                    select(SourceVersion).order_by(
                        SourceVersion.source_id,
                        SourceVersion.created_at.desc(),
                    )
                )
            )
            artifacts = list(
                session.scalars(
                    select(SourceArtifact).order_by(
                        SourceArtifact.source_version_id,
                        SourceArtifact.created_at.desc(),
                    )
                )
            )

        version_by_source: dict[str, SourceVersion] = {}
        for version in versions:
            version_by_source.setdefault(version.source_id, version)
        artifact_by_version: dict[str, SourceArtifact] = {}
        for artifact in artifacts:
            artifact_by_version.setdefault(artifact.source_version_id, artifact)

        items: list[SourceSummaryRecord] = []
        warnings: list[str] = []
        for source in sources:
            version = version_by_source.get(source.source_id)
            artifact = (
                artifact_by_version.get(version.source_version_id) if version is not None else None
            )
            if version is None or artifact is None:
                warnings.append(f"source {source.source_id} has no complete version artifact")
                continue
            media_type = _media_type_label(artifact.media_type, artifact.object_key)
            rights = _rights_label(version.rights)
            status = _source_status_label(version.status)
            if media_type is None or rights is None or status is None:
                warnings.append(
                    f"source {source.source_id} has unsupported media, rights or status"
                )
                continue
            items.append(
                SourceSummaryRecord(
                    source_id=source.source_id,
                    title=source.title,
                    version=version.version,
                    media_type=media_type,
                    rights=rights,
                    status=status,
                    source_hash=version.sha256,
                    updated_at=version.created_at,
                )
            )
        return items, warnings

    def list_platform_users(self) -> tuple[list[PlatformUserRecord], list[str]]:
        with self._session_factory() as session:
            users = list(
                session.scalars(
                    select(PlatformUser).order_by(
                        PlatformUser.display_name,
                        PlatformUser.user_id,
                    )
                )
            )
            bindings = list(
                session.execute(
                    select(RoleBinding.user_id, RoleBinding.role).order_by(
                        RoleBinding.user_id,
                        RoleBinding.role,
                    )
                )
            )
        roles_by_user: dict[str, list[str]] = {}
        for user_id, role in bindings:
            roles_by_user.setdefault(user_id, []).append(role)

        items: list[PlatformUserRecord] = []
        warnings: list[str] = []
        for user in users:
            roles = tuple(roles_by_user.get(user.user_id, []))
            if not roles:
                warnings.append(f"user {user.user_id} has no product role")
                continue
            items.append(
                PlatformUserRecord(
                    user_id=user.user_id,
                    display_name=user.display_name,
                    email=user.email,
                    identity_source=user.identity_source,
                    roles=roles,
                    status=user.status,
                    last_active_at=user.last_authenticated_at,
                )
            )
        return items, warnings


def _media_type_label(media_type: str, object_key: str) -> str | None:
    normalized = media_type.lower()
    suffix = object_key.lower().rsplit(".", maxsplit=1)[-1]
    if normalized == "application/pdf" or suffix == "pdf":
        return "PDF"
    if normalized in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    } or suffix in {"docx", "doc"}:
        return "DOCX"
    if normalized in {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    } or suffix in {"xlsx", "xls"}:
        return "XLSX"
    if normalized in {"text/markdown", "text/plain"} or suffix in {"md", "markdown"}:
        return "Markdown"
    return None


def _rights_label(rights: object) -> str | None:
    if not isinstance(rights, dict):
        return None
    value = rights.get("status", rights.get("classification"))
    return value if value in {"licensed", "internal", "restricted"} else None


def _source_status_label(status: str) -> str | None:
    allowed = {
        "registered",
        "processing",
        "candidate",
        "approved",
        "released",
        "restricted",
        "disabled",
    }
    return status if status in allowed else None
