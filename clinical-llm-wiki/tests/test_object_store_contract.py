from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from service.object_store import (
    InMemoryObjectStore,
    LocalObjectStore,
    ObjectConflictError,
    ObjectIntegrityError,
    ObjectNotFoundError,
    object_store_contract_json_schema,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("adapter_name", ["memory", "local"])
def test_object_store_adapters_share_immutable_hash_checked_semantics(
    adapter_name: str,
    tmp_path: Path,
) -> None:
    store = (
        InMemoryObjectStore()
        if adapter_name == "memory"
        else LocalObjectStore(root=tmp_path / "objects")
    )
    content = b"governed clinical source"
    expected_hash = sha256(content).hexdigest()

    descriptor = store.put_bytes(
        "sources/src-001/v1/source.pdf",
        content,
        media_type="application/pdf",
        expected_sha256=expected_hash,
    )

    assert descriptor.object_key == "sources/src-001/v1/source.pdf"
    assert descriptor.sha256 == expected_hash
    assert descriptor.size_bytes == len(content)
    assert descriptor.media_type == "application/pdf"
    assert store.head(descriptor.object_key) == descriptor
    assert store.get_bytes(descriptor.object_key) == content
    assert store.healthcheck() is True

    # Exact replay is idempotent; an object key can never be silently overwritten.
    assert store.put_bytes(
        descriptor.object_key,
        content,
        media_type="application/pdf",
        expected_sha256=expected_hash,
    ) == descriptor
    with pytest.raises(ObjectConflictError):
        store.put_bytes(
            descriptor.object_key,
            b"changed bytes",
            media_type="application/pdf",
        )

    store.delete(descriptor.object_key)
    with pytest.raises(ObjectNotFoundError):
        store.get_bytes(descriptor.object_key)


@pytest.mark.parametrize(
    "invalid_key",
    [
        "",
        "/absolute/source.pdf",
        "C:/clinical/source.pdf",
        "../outside.pdf",
        "sources/../../outside.pdf",
        r"sources\source.pdf",
        "s3://bucket/source.pdf",
        "https://objects.example/source.pdf",
    ],
)
def test_object_keys_reject_paths_and_provider_urls(
    invalid_key: str,
    tmp_path: Path,
) -> None:
    store = LocalObjectStore(root=tmp_path / "objects")

    with pytest.raises(ValueError, match="object_key"):
        store.put_bytes(invalid_key, b"content", media_type="application/pdf")


def test_hash_mismatch_leaves_no_visible_object(tmp_path: Path) -> None:
    store = LocalObjectStore(root=tmp_path / "objects")
    key = "sources/src-001/v1/source.pdf"

    with pytest.raises(ObjectIntegrityError):
        store.put_bytes(
            key,
            b"content",
            media_type="application/pdf",
            expected_sha256="0" * 64,
        )

    with pytest.raises(ObjectNotFoundError):
        store.head(key)
    assert not list((tmp_path / "objects").rglob("*.tmp"))


def test_checked_in_object_store_schema_matches_runtime_contract() -> None:
    checked_in = json.loads(
        (
            ROOT
            / "schemas"
            / "application"
            / "object-store.prerelease.schema.json"
        ).read_text(encoding="utf-8")
    )
    runtime = object_store_contract_json_schema()

    Draft202012Validator.check_schema(checked_in)
    assert checked_in == runtime
    descriptor_properties = checked_in["$defs"]["ObjectDescriptor"]["properties"]
    assert "absolute_path" not in descriptor_properties
    assert "provider_url" not in descriptor_properties
