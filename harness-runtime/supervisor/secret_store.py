"""Supervisor-owned ephemeral secret storage primitives."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
from threading import Lock
from uuid import uuid4


P16_EPHEMERAL_SECRET_NAMES = frozenset({"deepseek-api-key"})


class SecretCleanupError(RuntimeError):
    """Sanitized evidence that ephemeral Attempt material could not be removed."""


def _remove_tree(directory: Path) -> None:
    for path in directory.rglob("*"):
        if path.is_file() and not path.is_symlink():
            path.chmod(0o600)
    shutil.rmtree(directory)


class AttemptSecretMaterializer:
    """Own per-Attempt auth files inside the ephemeral secret filesystem."""

    def __init__(self, *, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def materialize(
        self,
        *,
        attempt_id: str,
        request_sha256: str,
        provider: str,
        secret: str,
    ) -> Path:
        with self._lock:
            directory = self._attempt_directory(attempt_id, request_sha256)
            if directory.exists():
                _remove_tree(directory)
            directory.mkdir(mode=0o700)
            auth_path = directory / "opencode-auth.json"
            auth_path.write_text(
                json.dumps({provider: {"type": "api", "key": secret}}),
                encoding="utf-8",
            )
            auth_path.chmod(0o444)
            return auth_path

    def cleanup(self, attempt_id: str, request_sha256: str) -> None:
        with self._lock:
            directory = self._attempt_directory(attempt_id, request_sha256)
            if directory.exists():
                try:
                    _remove_tree(directory)
                except OSError:
                    raise SecretCleanupError(
                        "attempt secret cleanup failed"
                    ) from None

    @contextmanager
    def auth_file(
        self,
        *,
        attempt_id: str,
        request_sha256: str,
        provider: str,
        secret: str,
    ) -> Iterator[Path]:
        try:
            auth_path = self.materialize(
                attempt_id=attempt_id,
                request_sha256=request_sha256,
                provider=provider,
                secret=secret,
            )
            yield auth_path
        finally:
            self.cleanup(attempt_id, request_sha256)

    def _attempt_directory(self, attempt_id: str, request_sha256: str) -> Path:
        identity = hashlib.sha256(
            f"{attempt_id}\0{request_sha256}".encode("utf-8")
        ).hexdigest()
        return self._root / f"attempt-{identity}"


class TmpfsSecretStore:
    """Store only explicitly registered opaque secrets under a private root."""

    def __init__(
        self,
        *,
        root: Path,
        allowed_names: frozenset[str],
        clear_on_start: bool,
    ) -> None:
        self._root = root
        self._allowed_names = allowed_names
        self._root.mkdir(parents=True, exist_ok=True)
        if clear_on_start:
            try:
                for child in self._root.iterdir():
                    if child.is_symlink():
                        child.unlink()
                    elif child.is_file():
                        child.chmod(0o600)
                        child.unlink()
                    elif child.is_dir():
                        _remove_tree(child)
            except OSError:
                raise SecretCleanupError(
                    "ephemeral secret store reset failed"
                ) from None

    def inject(self, name: str, value: str) -> None:
        if name not in self._allowed_names:
            raise ValueError("secret name is not allowed")
        if not value:
            raise ValueError("secret value must not be empty")
        temporary = self._root / f".{name}.{uuid4().hex}.tmp"
        target = self._root / name
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
                stream.write(value)
            temporary.chmod(0o600)
            temporary.replace(target)
            target.chmod(0o600)
        finally:
            if temporary.exists():
                temporary.unlink()

    def resolve(self, reference: str) -> str:
        scheme, separator, name = reference.partition("://")
        if separator != "://" or scheme != "secret" or name not in self._allowed_names:
            raise ValueError("secret reference is not allowed")
        try:
            return (self._root / name).read_text(encoding="utf-8")
        except OSError:
            raise ValueError("required secret is unavailable") from None
