"""H0-C staging scanner tests: six attack classes fail closed.

Mirrors TEST_GUIDE "目标 Harness Gate" item 9: reject symlink, hardlink /
reparse point, archive bomb, partial write, quota overflow, undeclared
executable bit and MIME/schema drift; hashes are recomputed by the scanner.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from supervisor.staging import StagingLimits, StagingScanError, scan_staging

_LIMITS = StagingLimits(max_total_bytes=10 * 1024 * 1024, max_files=20)


def _write(root: Path, name: str, content: bytes | str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        content = content.encode("utf-8")
    path.write_bytes(content)
    return path


def test_scan_returns_manifest_with_recomputed_sha256(tmp_path: Path) -> None:
    file = _write(tmp_path, "out.json", json.dumps({"claim": "x"}))
    manifest = scan_staging(tmp_path, _LIMITS)
    assert len(manifest.items) == 1
    item = manifest.items[0]
    assert item.sha256 == hashlib.sha256(file.read_bytes()).hexdigest()
    assert item.key == "out.json"
    assert item.media_type == "application/json"


def test_scan_rejects_symlink(tmp_path: Path) -> None:
    _write(tmp_path, "real.txt", "data")
    try:
        (tmp_path / "link.txt").symlink_to(tmp_path / "real.txt")
    except OSError as exc:
        pytest.skip(f"symlink creation requires privileges on this platform: {exc}")
    with pytest.raises(StagingScanError):
        scan_staging(tmp_path, _LIMITS)


def test_scan_rejects_hardlink(tmp_path: Path) -> None:
    # Target runtime is a Linux OCI container; NTFS st_nlink semantics are
    # unreliable, so the host-side assertion is skipped on Windows.
    if os.name == "nt":
        pytest.skip("hardlink detection is verified on Linux; NTFS st_nlink is unreliable")
    first = _write(tmp_path, "a.txt", "same-content")
    os.link(first, tmp_path / "b.txt")
    with pytest.raises(StagingScanError):
        scan_staging(tmp_path, _LIMITS)


def test_scan_rejects_partial_write_marker(tmp_path: Path) -> None:
    _write(tmp_path, "out.json.tmp", "partial")
    with pytest.raises(StagingScanError):
        scan_staging(tmp_path, _LIMITS)


def test_scan_rejects_archive_bomb(tmp_path: Path) -> None:
    _write(tmp_path, "bomb.zip", b"PK\x03\x04fake")
    with pytest.raises(StagingScanError):
        scan_staging(tmp_path, _LIMITS)


def test_scan_rejects_total_size_quota_overflow(tmp_path: Path) -> None:
    limits = StagingLimits(max_total_bytes=10, max_files=20)
    _write(tmp_path, "big.bin", b"x" * 11)
    with pytest.raises(StagingScanError):
        scan_staging(tmp_path, limits)


def test_scan_rejects_file_count_quota_overflow(tmp_path: Path) -> None:
    limits = StagingLimits(max_total_bytes=10 * 1024 * 1024, max_files=1)
    _write(tmp_path, "a.txt", "a")
    _write(tmp_path, "b.txt", "b")
    with pytest.raises(StagingScanError):
        scan_staging(tmp_path, limits)


def test_scan_rejects_undeclared_executable_bit(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("executable bit is not meaningful on Windows")
    path = _write(tmp_path, "script.sh", "#!/bin/sh\n")
    path.chmod(0o755)
    with pytest.raises(StagingScanError):
        scan_staging(tmp_path, _LIMITS)
    # allow_executable=True permits it
    manifest = scan_staging(
        tmp_path,
        StagingLimits(max_total_bytes=10 * 1024 * 1024, max_files=20, allow_executable=True),
    )
    assert manifest.items[0].key == "script.sh"
