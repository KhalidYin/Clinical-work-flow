"""Strict client for the Clinical LLM Wiki structured runtime endpoint.

The client deliberately has no free-form chat API.  The only production call is
the schema-locked ``runtime-context/resolve`` endpoint and its response remains
untrusted until the Engine validates it again.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class KnowledgeServiceError(RuntimeError):
    """Base class for Wiki service failures."""


class KnowledgeServiceUnavailable(KnowledgeServiceError):
    """The service could not be reached; a locked Study snapshot may be used."""


class KnowledgeServiceContractError(KnowledgeServiceError):
    """A reachable service returned an incompatible or malformed contract."""


class KnowledgeTransport(Protocol):
    def __call__(
        self, method: str, path: str, payload: Mapping[str, Any] | None = None
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class KnowledgeServiceVersion:
    bundle_id: str
    bundle_version: str
    bundle_sha256: str


class HttpKnowledgeTransport:
    """Small stdlib transport so the Engine does not acquire an HTTP SDK dependency."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 5.0) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("knowledge service URL must use HTTP(S)")
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def __call__(
        self, method: str, path: str, payload: Mapping[str, Any] | None = None
    ) -> Mapping[str, Any]:
        if not path.startswith("/api/v1/"):
            raise KnowledgeServiceContractError("unsupported Knowledge Service endpoint")
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(self._base_url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:  # nosec B310
                decoded = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            # HTTPError inherits URLError, so this branch must come first.  A
            # reachable service rejection is a contract/security failure and
            # must never be disguised as an offline snapshot fallback.
            raise KnowledgeServiceContractError(
                f"Knowledge Service rejected request: {exc.code}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise KnowledgeServiceUnavailable("Knowledge Service is unavailable") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise KnowledgeServiceContractError("Knowledge Service returned non-JSON data") from exc
        if not isinstance(decoded, dict):
            raise KnowledgeServiceContractError("Knowledge Service response must be an object")
        return decoded


class KnowledgeServiceClient:
    """Validate exact Schema bundle identity before every runtime resolution."""

    def __init__(
        self,
        transport: KnowledgeTransport | Callable[[str, str, Mapping[str, Any] | None], Mapping[str, Any]],
        *,
        bundle_version: str,
        bundle_sha256: str,
    ) -> None:
        self._transport = transport
        self._bundle_version = bundle_version
        self._bundle_sha256 = bundle_sha256

    @property
    def bundle_lock(self) -> dict[str, str]:
        return {"version": self._bundle_version, "sha256": self._bundle_sha256}

    def version(self) -> KnowledgeServiceVersion:
        response = self._call("GET", "/api/v1/version")
        try:
            version = KnowledgeServiceVersion(
                bundle_id=_required_string(response, "bundle_id"),
                bundle_version=_required_string(response, "bundle_version"),
                bundle_sha256=_required_string(response, "bundle_sha256"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise KnowledgeServiceContractError("invalid Knowledge Service version response") from exc
        if version.bundle_version != self._bundle_version or version.bundle_sha256 != self._bundle_sha256:
            raise KnowledgeServiceContractError("Knowledge Service Schema bundle lock differs from Engine")
        return version

    def resolve_runtime_context(
        self,
        *,
        study_id: str,
        stage: str,
        runtime_manifest: Mapping[str, Any],
        require_workflow: bool = True,
        require_domain: bool = False,
    ) -> Mapping[str, Any]:
        # This explicit mapping prevents callers from smuggling control fields into
        # the remote request.  The service repeats the rejection at its boundary.
        request = {
            "study_id": study_id,
            "stage": stage,
            "runtime_manifest": dict(runtime_manifest),
            "schema_bundle": self.bundle_lock,
            "require_workflow": require_workflow,
            "require_domain": require_domain,
        }
        self.version()
        return self._call("POST", "/api/v1/runtime-context/resolve", request)

    def _call(
        self, method: str, path: str, payload: Mapping[str, Any] | None = None
    ) -> Mapping[str, Any]:
        try:
            response = self._transport(method, path, payload)
        except KnowledgeServiceError:
            raise
        except Exception as exc:  # transport adapters must not leak ambiguity
            raise KnowledgeServiceUnavailable("Knowledge Service transport failed") from exc
        if not isinstance(response, Mapping):
            raise KnowledgeServiceContractError("Knowledge Service response must be a mapping")
        return response


def _required_string(value: Mapping[str, Any], key: str) -> str:
    item = value[key]
    if not isinstance(item, str) or not item:
        raise ValueError(key)
    return item
