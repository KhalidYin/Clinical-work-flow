"""Real Docker P16/P3 allow, deny, and proxy-bypass gate."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest


ROOT = Path(__file__).resolve().parents[1]
POLICY_ROOT = ROOT / "egress" / "model-deepseek-v1"
GATEWAY_IMAGE = (
    "ubuntu/squid:6.6-24.04_edge@sha256:"
    "8a3baed477e2c282ab8aa5edad442f69873246964f225c5c2ae8364b6610963c"
)
CLIENT_IMAGE = (
    "python:3.11-slim@sha256:"
    "db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93"
)


@pytest.mark.integration
def test_real_gateway_allows_exact_authority_and_blocks_bypass(
    tmp_path: Path,
) -> None:
    docker = pytest.importorskip("docker")
    try:
        client = docker.from_env()
        client.ping()
        client.images.get(GATEWAY_IMAGE)
        client.images.get(CLIENT_IMAGE)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"pinned gateway test images or Docker unavailable: {exc}")

    # Production blocks private destinations. This test-only copy removes that
    # one rule so a local target can exercise the exact CONNECT allow path.
    production_config = (POLICY_ROOT / "squid.conf").read_text(encoding="utf-8")
    test_config = production_config.replace(
        "http_access deny blocked_destination",
        "# test-only local target: production keeps the private-destination deny",
    )
    assert test_config != production_config
    config_path = tmp_path / "squid.conf"
    config_path.write_text(test_config, encoding="utf-8")

    suffix = uuid4().hex[:12]
    labels = {"clinical.p16.test": suffix}
    client_network = client.networks.create(
        f"clinical-p16-client-{suffix}",
        driver="bridge",
        internal=True,
        labels=labels,
    )
    uplink_network = client.networks.create(
        f"clinical-p16-uplink-{suffix}",
        driver="bridge",
        internal=False,
        labels=labels,
    )
    containers = []
    try:
        target = client.containers.create(
            CLIENT_IMAGE,
            command=[
                "python",
                "-u",
                "-c",
                (
                    "import socket\n"
                    "server=socket.socket()\n"
                    "server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)\n"
                    "server.bind(('0.0.0.0',443))\n"
                    "server.listen()\n"
                    "while True:\n"
                    " conn,_=server.accept()\n"
                    " try:\n"
                    "  data=conn.recv(32)\n"
                    "  conn.sendall(b'LOCAL_OK' if data==b'PING' else b'BAD')\n"
                    " finally:\n"
                    "  conn.close()\n"
                ),
            ],
            network_mode=uplink_network.name,
            labels=labels,
        )
        containers.append(target)
        uplink_network.disconnect(target)
        uplink_network.connect(target, aliases=["api.deepseek.com"])
        target.start()
        target.reload()
        target_ip = target.attrs["NetworkSettings"]["Networks"][
            uplink_network.name
        ]["IPAddress"]

        gateway = client.containers.create(
            GATEWAY_IMAGE,
            command=["-f", "/etc/squid/squid.conf", "-NYC"],
            entrypoint=["/usr/sbin/squid"],
            user="13:13",
            network_mode=client_network.name,
            read_only=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            tmpfs={
                "/tmp": "rw,noexec,nosuid,size=16m",
                "/run": "rw,noexec,nosuid,size=4m",
                "/var/log/squid": "rw,noexec,nosuid,size=16m",
                "/var/spool/squid": "rw,noexec,nosuid,size=16m",
            },
            volumes={
                str(config_path): {
                    "bind": "/etc/squid/squid.conf",
                    "mode": "ro",
                }
            },
            labels=labels,
        )
        containers.append(gateway)
        client_network.disconnect(gateway)
        client_network.connect(
            gateway,
            aliases=["harness-egress-deepseek"],
        )
        uplink_network.connect(gateway)
        gateway.start()

        probe_script = r"""
import json
import os
import socket
import time

GATEWAY = ("harness-egress-deepseek", 3128)
TARGET_IP = os.environ["TARGET_IP"]

def connect(authority):
    last = None
    for _ in range(40):
        try:
            stream = socket.create_connection(GATEWAY, 1)
            break
        except OSError as exc:
            last = exc
            time.sleep(0.1)
    else:
        raise last
    stream.settimeout(2)
    request = (
        f"CONNECT {authority} HTTP/1.1\r\n"
        f"Host: {authority}\r\n\r\n"
    ).encode("ascii")
    stream.sendall(request)
    response = b""
    while b"\r\n\r\n" not in response:
        response += stream.recv(4096)
    status = int(response.split(b" ", 2)[1])
    return stream, status

allowed, allowed_status = connect("api.deepseek.com:443")
allowed.sendall(b"PING")
tunnel_response = allowed.recv(32).decode("ascii")
allowed.close()

wrong_host, wrong_host_status = connect("not-allowed.invalid:443")
wrong_host.close()
raw_ip, raw_ip_status = connect(f"{TARGET_IP}:443")
raw_ip.close()
wrong_port, wrong_port_status = connect("api.deepseek.com:8443")
wrong_port.close()

direct_succeeded = False
try:
    direct = socket.create_connection((TARGET_IP, 443), 1)
    direct_succeeded = True
    direct.close()
except OSError:
    pass

print(json.dumps({
    "allowed_status": allowed_status,
    "tunnel_response": tunnel_response,
    "wrong_host_status": wrong_host_status,
    "raw_ip_status": raw_ip_status,
    "wrong_port_status": wrong_port_status,
    "direct_succeeded": direct_succeeded,
}, sort_keys=True))
"""
        probe = client.containers.run(
            CLIENT_IMAGE,
            command=["python", "-c", probe_script],
            network=client_network.name,
            environment={"TARGET_IP": target_ip},
            labels=labels,
            remove=False,
            detach=True,
        )
        containers.append(probe)
        result = probe.wait(timeout=30)
        output = probe.logs().decode("utf-8").strip()

        assert result["StatusCode"] == 0, output
        assert json.loads(output) == {
            "allowed_status": 200,
            "direct_succeeded": False,
            "raw_ip_status": 403,
            "tunnel_response": "LOCAL_OK",
            "wrong_host_status": 403,
            "wrong_port_status": 403,
        }
        gateway.reload()
        probe.reload()
        assert set(gateway.attrs["NetworkSettings"]["Networks"]) == {
            client_network.name,
            uplink_network.name,
        }
        assert set(probe.attrs["NetworkSettings"]["Networks"]) == {
            client_network.name
        }
        assert gateway.attrs["HostConfig"]["ReadonlyRootfs"] is True
        assert gateway.attrs["HostConfig"]["CapDrop"] == ["ALL"]
        assert gateway.attrs["NetworkSettings"]["Ports"] == {"3128/tcp": None}
        logs = gateway.logs().decode("utf-8", errors="replace")
        assert "FATAL" not in logs
        assert "synthetic-secret-marker" not in logs
    finally:
        for container in reversed(containers):
            try:
                container.remove(force=True)
            except Exception:
                pass
        for network in (client_network, uplink_network):
            try:
                network.remove()
            except Exception:
                pass
