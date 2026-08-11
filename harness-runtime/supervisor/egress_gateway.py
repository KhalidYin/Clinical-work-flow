"""Load a hash-locked gateway policy into the trusted runtime boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from supervisor.network_policy import NetworkRuntimeBinding


_IMAGE_REF = (
    "ubuntu/squid:6.6-24.04_edge@sha256:"
    "8a3baed477e2c282ab8aa5edad442f69873246964f225c5c2ae8364b6610963c"
)
_GATEWAY_IDENTITY = "canonical-ubuntu-squid-6.14-0ubuntu0.24.04.2"
_PROXY_URL = "http://harness-egress-deepseek:3128"
_MANIFEST_FIELDS = frozenset(
    {
        "policy_id",
        "gateway_identity",
        "source",
        "license",
        "image_ref",
        "platform",
        "proxy_url",
        "allowed_endpoints",
        "config_sha256",
    }
)


def load_network_runtime_binding(
    *,
    manifest_path: Path,
    network_name: str,
    runtime: Any,
) -> NetworkRuntimeBinding:
    """Verify local policy identity and resolve its Docker-internal network."""

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise RuntimeError("gateway manifest is unavailable") from None
    if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_FIELDS:
        raise RuntimeError("gateway manifest contract is invalid")
    if (
        manifest.get("policy_id") != "model-deepseek-v1"
        or manifest.get("allowed_endpoints") != ["api.deepseek.com:443"]
        or manifest.get("platform") != "linux/amd64"
        or manifest.get("license") != "GPL-2.0-or-later"
        or manifest.get("source") != "https://hub.docker.com/r/ubuntu/squid"
        or manifest.get("image_ref") != _IMAGE_REF
        or manifest.get("gateway_identity") != _GATEWAY_IDENTITY
        or manifest.get("proxy_url") != _PROXY_URL
    ):
        raise RuntimeError("gateway manifest policy is invalid")
    try:
        config = manifest_path.with_name("squid.conf").read_bytes()
    except OSError:
        raise RuntimeError("gateway config is unavailable") from None
    if hashlib.sha256(config).hexdigest() != manifest.get("config_sha256"):
        raise RuntimeError("gateway config identity mismatch")

    require_internal_network = getattr(runtime, "require_internal_network", None)
    if not callable(require_internal_network):
        raise RuntimeError("container runtime cannot verify the gateway network")
    network_id = require_internal_network(network_name)
    return NetworkRuntimeBinding(
        policy_id=manifest["policy_id"],
        internal_network_id=network_id,
        proxy_url=manifest["proxy_url"],
        gateway_identity=manifest["gateway_identity"],
        gateway_config_sha256=manifest["config_sha256"],
    )
