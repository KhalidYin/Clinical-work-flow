"""P16/P3 contracts for the generic explicit CONNECT gateway."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
import pytest


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
POLICY_ROOT = ROOT / "egress" / "model-deepseek-v1"


def test_gateway_manifest_locks_verified_image_license_and_config_hash() -> None:
    manifest = json.loads(
        (POLICY_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    config = (POLICY_ROOT / "squid.conf").read_bytes()

    assert manifest == {
        "policy_id": "model-deepseek-v1",
        "gateway_identity": "canonical-ubuntu-squid-6.14-0ubuntu0.24.04.2",
        "source": "https://hub.docker.com/r/ubuntu/squid",
        "license": "GPL-2.0-or-later",
        "image_ref": (
            "ubuntu/squid:6.6-24.04_edge@sha256:"
            "8a3baed477e2c282ab8aa5edad442f69873246964f225c5c2ae8364b6610963c"
        ),
        "platform": "linux/amd64",
        "proxy_url": "http://harness-egress-deepseek:3128",
        "allowed_endpoints": ["api.deepseek.com:443"],
        "config_sha256": hashlib.sha256(config).hexdigest(),
    }


def test_gateway_config_is_connect_only_without_tls_interception_or_cache() -> None:
    config = (POLICY_ROOT / "squid.conf").read_text(encoding="utf-8")

    assert "acl allowed_endpoint dstdomain -n api.deepseek.com" in config
    assert "acl allowed_tls_port port 443" in config
    assert "http_access allow CONNECT allowed_tls_port allowed_endpoint" in config
    assert "http_access deny all" in config
    assert "cache deny all" in config
    assert "pinger_enable off" in config
    assert "ssl_bump" not in config.lower()
    assert "https_port" not in config.lower()
    for cidr in (
        "10.0.0.0/8",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    ):
        assert cidr in config


def test_compose_gateway_is_only_dual_homed_service_and_client_is_internal() -> None:
    compose = yaml.safe_load(
        (PROJECT_ROOT / "clinical-llm-wiki" / "compose.harness.yaml").read_text(
            encoding="utf-8"
        )
    )
    services = compose["services"]
    networks = compose["networks"]
    gateway = services["harness-egress-deepseek"]

    assert gateway["image"] == (
        "ubuntu/squid:6.6-24.04_edge@sha256:"
        "8a3baed477e2c282ab8aa5edad442f69873246964f225c5c2ae8364b6610963c"
    )
    assert gateway["platform"] == "linux/amd64"
    assert gateway["networks"] == [
        "harness-deepseek-client",
        "harness-egress-uplink",
    ]
    assert gateway["read_only"] is True
    assert gateway["user"] == "13:13"
    assert gateway["entrypoint"] == ["/usr/sbin/squid"]
    assert gateway["command"] == [
        "-f",
        "/etc/squid/squid.conf",
        "-NYC",
    ]
    assert gateway["healthcheck"]["test"] == [
        "CMD",
        "/bin/bash",
        "-c",
        (
            "exec 3<>/dev/tcp/127.0.0.1/3128; "
            "printf 'CONNECT health.invalid:443 HTTP/1.1\\r\\n"
            "Host: health.invalid:443\\r\\n\\r\\n' >&3; "
            "IFS= read -r line <&3; "
            "[[ $$line == $$'HTTP/1.1 403 Forbidden\\r' ]]"
        ),
    ]
    assert gateway["cap_drop"] == ["ALL"]
    assert gateway["security_opt"] == ["no-new-privileges:true"]
    assert "ports" not in gateway
    assert networks["harness-deepseek-client"] == {
        "internal": True,
        "name": (
            "${HARNESS_DEEPSEEK_CLIENT_NETWORK_NAME:-"
            "clinical-harness-deepseek-client}"
        ),
    }
    assert networks["harness-egress-uplink"].get("internal", False) is False

    dual_homed = {
        name
        for name, service in services.items()
        if {
            "harness-deepseek-client",
            "harness-egress-uplink",
        }.issubset(set(service.get("networks", [])))
    }
    assert dual_homed == {"harness-egress-deepseek"}
    assert "harness-deepseek-client" not in services["worker-enrichment"]["networks"]
    assert "harness-egress-uplink" not in services["worker-enrichment"]["networks"]
    assert "harness-egress-uplink" not in services["harness-supervisor"]["networks"]
    assert services["harness-supervisor"]["depends_on"][
        "harness-egress-deepseek"
    ] == {"condition": "service_healthy"}


def test_runtime_loader_verifies_config_hash_and_internal_network() -> None:
    from supervisor.egress_gateway import load_network_runtime_binding

    class Runtime:
        def __init__(self) -> None:
            self.names: list[str] = []

        def require_internal_network(self, name: str) -> str:
            self.names.append(name)
            return "e" * 64

    runtime = Runtime()
    binding = load_network_runtime_binding(
        manifest_path=POLICY_ROOT / "manifest.json",
        network_name="clinical-harness-deepseek-client",
        runtime=runtime,
    )

    assert binding.policy_id == "model-deepseek-v1"
    assert binding.internal_network_id == "e" * 64
    assert binding.proxy_url == "http://harness-egress-deepseek:3128"
    assert runtime.names == ["clinical-harness-deepseek-client"]


def test_runtime_loader_fails_closed_on_gateway_config_drift(tmp_path: Path) -> None:
    from supervisor.egress_gateway import load_network_runtime_binding

    manifest = json.loads(
        (POLICY_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    (tmp_path / "squid.conf").write_text(
        "http_access allow all\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="gateway config identity mismatch"):
        load_network_runtime_binding(
            manifest_path=tmp_path / "manifest.json",
            network_name="clinical-harness-deepseek-client",
            runtime=object(),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("proxy_url", "http://untrusted-proxy:3128"),
        ("gateway_identity", "unreviewed-gateway"),
        (
            "image_ref",
            "ubuntu/squid:other@sha256:" + "a" * 64,
        ),
    ],
)
def test_runtime_loader_rejects_gateway_identity_drift(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    from supervisor.egress_gateway import load_network_runtime_binding

    manifest = json.loads(
        (POLICY_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    manifest[field] = value
    (tmp_path / "manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    (tmp_path / "squid.conf").write_bytes((POLICY_ROOT / "squid.conf").read_bytes())

    with pytest.raises(RuntimeError, match="gateway manifest policy is invalid"):
        load_network_runtime_binding(
            manifest_path=tmp_path / "manifest.json",
            network_name="clinical-harness-deepseek-client",
            runtime=object(),
        )


def test_network_runtime_binding_rejects_malformed_proxy_port_cleanly() -> None:
    from supervisor.network_policy import NetworkRuntimeBinding

    with pytest.raises(ValueError, match="gateway proxy URL is invalid"):
        NetworkRuntimeBinding(
            policy_id="model-deepseek-v1",
            internal_network_id="e" * 64,
            proxy_url="http://harness-egress-deepseek:not-a-port",
            gateway_identity="canonical-ubuntu-squid-6.14-0ubuntu0.24.04.2",
            gateway_config_sha256="f" * 64,
        )
