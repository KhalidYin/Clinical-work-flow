"""Provider-neutral binary authority for the Knowledge Application Platform."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator


_OBJECT_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


class ObjectStoreError(RuntimeError):
    """Base error for provider-neutral object operations."""


class ObjectNotFoundError(ObjectStoreError):
    """The requested object key is not visible in the store."""


class ObjectConflictError(ObjectStoreError):
    """An immutable key already points to different bytes or metadata."""


class ObjectIntegrityError(ObjectStoreError):
    """Object bytes do not match the declared SHA-256."""


class ObjectDescriptor(BaseModel):
    """Business-safe object identity; it contains no path or provider URL."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    object_key: str = Field(min_length=1, max_length=1024)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(ge=0)

    @field_validator("object_key")
    @classmethod
    def validate_object_key(cls, value: str) -> str:
        return validate_object_key(value)


@runtime_checkable
class ObjectStorePort(Protocol):
    """Replaceable binary authority used by business services."""

    def put_bytes(
        self,
        object_key: str,
        content: bytes,
        *,
        media_type: str,
        expected_sha256: str | None = None,
    ) -> ObjectDescriptor: ...

    def get_bytes(self, object_key: str) -> bytes: ...

    def head(self, object_key: str) -> ObjectDescriptor: ...

    def delete(self, object_key: str) -> None: ...

    def healthcheck(self) -> bool: ...


def validate_object_key(object_key: str) -> str:
    """Accept opaque POSIX-like keys while rejecting paths and provider URLs."""

    if (
        not object_key
        or not _OBJECT_KEY_PATTERN.fullmatch(object_key)
        or object_key.startswith("/")
        or "\\" in object_key
        or ":" in object_key
    ):
        raise ValueError("object_key must be a provider-neutral relative key")
    parts = object_key.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("object_key cannot contain empty or traversal segments")
    return object_key


class InMemoryObjectStore:
    """Deterministic adapter for unit tests and contract verification."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, ObjectDescriptor]] = {}

    def put_bytes(
        self,
        object_key: str,
        content: bytes,
        *,
        media_type: str,
        expected_sha256: str | None = None,
    ) -> ObjectDescriptor:
        descriptor = _descriptor(object_key, content, media_type, expected_sha256)
        existing = self._objects.get(descriptor.object_key)
        if existing is not None:
            if existing == (content, descriptor):
                return descriptor
            raise ObjectConflictError(f"object key already exists: {descriptor.object_key}")
        self._objects[descriptor.object_key] = (bytes(content), descriptor)
        return descriptor

    def get_bytes(self, object_key: str) -> bytes:
        validate_object_key(object_key)
        try:
            return bytes(self._objects[object_key][0])
        except KeyError as exc:
            raise ObjectNotFoundError(f"object not found: {object_key}") from exc

    def head(self, object_key: str) -> ObjectDescriptor:
        validate_object_key(object_key)
        try:
            return self._objects[object_key][1]
        except KeyError as exc:
            raise ObjectNotFoundError(f"object not found: {object_key}") from exc

    def delete(self, object_key: str) -> None:
        validate_object_key(object_key)
        if self._objects.pop(object_key, None) is None:
            raise ObjectNotFoundError(f"object not found: {object_key}")

    def healthcheck(self) -> bool:
        return True


class LocalObjectStore:
    """Safe local adapter for development; production S3 selection is deferred."""

    def __init__(self, *, root: Path) -> None:
        self._root = root.resolve()
        self._metadata_root = self._root / ".metadata"
        self._root.mkdir(parents=True, exist_ok=True)
        self._metadata_root.mkdir(parents=True, exist_ok=True)
        self._assert_within_root(self._metadata_root)

    def put_bytes(
        self,
        object_key: str,
        content: bytes,
        *,
        media_type: str,
        expected_sha256: str | None = None,
    ) -> ObjectDescriptor:
        descriptor = _descriptor(object_key, content, media_type, expected_sha256)
        target = self._target(descriptor.object_key)
        metadata_target = self._metadata_target(descriptor.object_key)
        if target.exists() or metadata_target.exists():
            try:
                existing = self.head(descriptor.object_key)
                existing_content = self.get_bytes(descriptor.object_key)
            except (ObjectNotFoundError, ObjectIntegrityError) as exc:
                raise ObjectConflictError(
                    f"object key has an incomplete existing write: {descriptor.object_key}"
                ) from exc
            if existing == descriptor and existing_content == content:
                return descriptor
            raise ObjectConflictError(f"object key already exists: {descriptor.object_key}")

        target.parent.mkdir(parents=True, exist_ok=True)
        self._assert_within_root(target)
        metadata = json.dumps(
            descriptor.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        data_temp = _write_temp(target.parent, content)
        metadata_temp = _write_temp(metadata_target.parent, metadata)
        metadata_linked = False
        try:
            # Hard links provide create-if-absent semantics across local worker processes.
            # Metadata is linked first; head() remains fail-closed until payload also exists.
            os.link(metadata_temp, metadata_target)
            metadata_linked = True
            os.link(data_temp, target)
        except FileExistsError as exc:
            if metadata_linked:
                metadata_target.unlink(missing_ok=True)
            raise ObjectConflictError(
                f"object key was claimed by another writer: {descriptor.object_key}"
            ) from exc
        except Exception:
            if metadata_linked:
                metadata_target.unlink(missing_ok=True)
            raise
        finally:
            Path(data_temp).unlink(missing_ok=True)
            Path(metadata_temp).unlink(missing_ok=True)
        return descriptor

    def get_bytes(self, object_key: str) -> bytes:
        descriptor = self.head(object_key)
        target = self._target(object_key)
        try:
            content = target.read_bytes()
        except FileNotFoundError as exc:
            raise ObjectNotFoundError(f"object not found: {object_key}") from exc
        actual = sha256(content).hexdigest()
        if actual != descriptor.sha256 or len(content) != descriptor.size_bytes:
            raise ObjectIntegrityError(f"stored object failed integrity check: {object_key}")
        return content

    def head(self, object_key: str) -> ObjectDescriptor:
        validate_object_key(object_key)
        metadata_target = self._metadata_target(object_key)
        target = self._target(object_key)
        if not metadata_target.is_file() or not target.is_file():
            raise ObjectNotFoundError(f"object not found: {object_key}")
        try:
            descriptor = ObjectDescriptor.model_validate_json(metadata_target.read_bytes())
        except (OSError, ValueError) as exc:
            raise ObjectIntegrityError(f"object metadata is invalid: {object_key}") from exc
        if descriptor.object_key != object_key:
            raise ObjectIntegrityError(f"object metadata key mismatch: {object_key}")
        return descriptor

    def delete(self, object_key: str) -> None:
        self.head(object_key)
        self._target(object_key).unlink()
        self._metadata_target(object_key).unlink(missing_ok=True)

    def healthcheck(self) -> bool:
        try:
            handle, temp_name = tempfile.mkstemp(prefix="health-", dir=self._metadata_root)
            os.close(handle)
            Path(temp_name).unlink(missing_ok=True)
        except OSError:
            return False
        return True

    def _target(self, object_key: str) -> Path:
        validate_object_key(object_key)
        target = self._root.joinpath(*object_key.split("/"))
        self._assert_within_root(target)
        return target

    def _metadata_target(self, object_key: str) -> Path:
        validate_object_key(object_key)
        digest = sha256(object_key.encode("utf-8")).hexdigest()
        target = self._metadata_root / f"{digest}.json"
        self._assert_within_root(target)
        return target

    def _assert_within_root(self, target: Path) -> None:
        try:
            target.resolve(strict=False).relative_to(self._root)
        except ValueError as exc:
            raise ValueError("object_key resolves outside the configured root") from exc


def _descriptor(
    object_key: str,
    content: bytes,
    media_type: str,
    expected_sha256: str | None,
) -> ObjectDescriptor:
    if not isinstance(content, bytes):
        raise TypeError("content must be bytes")
    digest = sha256(content).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ObjectIntegrityError("object bytes do not match expected_sha256")
    return ObjectDescriptor(
        object_key=object_key,
        sha256=digest,
        media_type=media_type,
        size_bytes=len(content),
    )


def _write_temp(directory: Path, content: bytes) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix="object-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
    return temp_name


def object_store_contract_json_schema() -> dict[str, object]:
    schema = TypeAdapter(ObjectDescriptor).json_schema(ref_template="#/$defs/{model}")
    definition = schema.copy()
    definition.pop("$defs", None)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://clinical.example/schemas/object-store.prerelease.schema.json",
        "title": "P12 Object Store Prerelease Contract",
        "$defs": {"ObjectDescriptor": definition},
        "$ref": "#/$defs/ObjectDescriptor",
    }


__all__ = [
    "InMemoryObjectStore",
    "LocalObjectStore",
    "ObjectConflictError",
    "ObjectDescriptor",
    "ObjectIntegrityError",
    "ObjectNotFoundError",
    "ObjectStoreError",
    "ObjectStorePort",
    "object_store_contract_json_schema",
    "validate_object_key",
]
