from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json

from fastapi.testclient import TestClient

from service.object_store import InMemoryObjectStore
from service.platform_api.app import PlatformApiServices, create_platform_app
from service.platform_api.repository import CurrentReleaseRecord


SECRET = "p13-runtime-consumer-test-secret"


class _Repository:
    def __init__(self, release: CurrentReleaseRecord) -> None:
        self.release = release

    def database_available(self) -> bool:
        return True

    def get_current_release(self) -> CurrentReleaseRecord:
        return self.release


class _UnusedPasswordSessions:
    def authenticate_session(self, _raw: str):
        raise AssertionError("runtime machine endpoint must not use a human session")


def _client() -> TestClient:
    store = InMemoryObjectStore()
    manifest = {
        "schema_bundle": {"id": "engine", "version": "1.1.0", "sha256": "a" * 64},
        "runtime_snapshots": [],
    }
    raw = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    descriptor = store.put_bytes(
        "release/p13/runtime-manifest.json",
        raw,
        media_type="application/json",
    )
    release = CurrentReleaseRecord(
        release_id="release-p13",
        version="p13.1",
        status="released",
        index_version="index-p13",
        released_at=datetime.now(timezone.utc),
        manifest_object_key=descriptor.object_key,
        manifest_sha256=descriptor.sha256,
    )
    return TestClient(
        create_platform_app(
            PlatformApiServices(
                repository=_Repository(release),  # type: ignore[arg-type]
                password_sessions=_UnusedPasswordSessions(),  # type: ignore[arg-type]
                organization_name="测试",
                allowed_browser_origins=frozenset({"http://testserver"}),
                secure_session_cookie=False,
                object_store_available=True,
                object_store=store,
                runtime_consumer_credential_sha256=sha256(SECRET.encode("utf-8")).hexdigest(),
            )
        )
    )


def test_machine_credential_is_required_without_human_cookie_or_browser_csrf() -> None:
    client = _client()
    path = "/api/prerelease/v1/runtime-knowledge/version"

    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-Knowledge-Machine-Credential": "bad"}).status_code == 401

    response = client.get(path, headers={"X-Knowledge-Machine-Credential": SECRET})

    assert response.status_code == 200
    assert response.json() == {
        "bundle_id": "engine",
        "bundle_version": "1.1.0",
        "bundle_sha256": "a" * 64,
    }
    assert "clinical_knowledge_session" not in response.headers.get("set-cookie", "")
