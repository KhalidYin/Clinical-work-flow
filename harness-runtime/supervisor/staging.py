"""H0-C staging security scanner.

Runs on the host, outside the container, and recomputes artifact hashes.
Six attack classes fail closed (TEST_GUIDE "目标 Harness Gate" item 9):
symlink, hardlink/reparse point, partial write markers, archive bombs,
size/file-count quota overflow, undeclared executable bits; media type is
sniffed from the file name and never trusted from the container.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from pydantic import Field

from contracts.manifest import ArtifactManifest, ArtifactManifestItem
from contracts.request import StrictContractModel


class StagingScanError(ValueError):
    """Staging content violated the security baseline; fail closed."""


class StagingLimits(StrictContractModel):
    max_total_bytes: int = Field(default=50 * 1024 * 1024, ge=1)
    max_files: int = Field(default=100, ge=1)
    allow_executable: bool = False


_PARTIAL_SUFFIXES = (".tmp", ".part", ".partial", ".swp")
_ARCHIVE_SUFFIXES = (
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".tar.gz",
    ".7z",
    ".rar",
    ".bz2",
    ".xz",
    ".tar.bz2",
    ".tar.xz",
)
_MEDIA_TYPES = {
    ".json": "application/json",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".md": "text/markdown",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
}


def _media_type(path: Path) -> str:
    lowered = path.name.lower()
    for suffix, media_type in _MEDIA_TYPES.items():
        if lowered.endswith(suffix):
            return media_type
    return "application/octet-stream"


def scan_staging(staging_dir: Path, limits: StagingLimits) -> ArtifactManifest:
    """Scan a host-side staging directory and return the recomputed manifest.

    Raises ``StagingScanError`` on the first violation (fail closed).
    """
    if not staging_dir.is_dir():
        raise StagingScanError(f"staging directory missing: {staging_dir}")
    root = staging_dir.resolve()
    items: list[ArtifactManifestItem] = []
    total_bytes = 0
    for path in sorted(staging_dir.rglob("*")):
        if path.is_symlink():
            raise StagingScanError(f"symlink rejected: {path.name}")
        if path.is_dir():
            continue
        stat = path.stat()
        if os.name != "nt" and stat.st_nlink > 1:
            raise StagingScanError(f"hardlink rejected: {path.name}")
        rel = path.relative_to(root).as_posix()
        lowered = rel.lower()
        if any(lowered.endswith(suffix) for suffix in _PARTIAL_SUFFIXES):
            raise StagingScanError(f"partial write marker rejected: {rel}")
        if any(lowered.endswith(suffix) for suffix in _ARCHIVE_SUFFIXES):
            raise StagingScanError(f"archive rejected (bomb guard): {rel}")
        if os.name != "nt" and (stat.st_mode & 0o111) and not limits.allow_executable:
            raise StagingScanError(f"undeclared executable bit rejected: {rel}")
        total_bytes += stat.st_size
        if total_bytes > limits.max_total_bytes:
            raise StagingScanError("total size quota exceeded")
        if len(items) >= limits.max_files:
            raise StagingScanError("file count quota exceeded")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        items.append(
            ArtifactManifestItem(
                key=rel,
                media_type=_media_type(path),
                size=stat.st_size,
                sha256=digest,
            )
        )
    return ArtifactManifest(items=tuple(items))
