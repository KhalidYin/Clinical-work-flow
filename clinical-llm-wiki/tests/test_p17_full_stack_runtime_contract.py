"""Deployment contract for the isolated P17 full-stack browser POC."""

from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_p17_browser_runtime_is_isolated_offline_and_fixture_gated() -> None:
    compose = yaml.safe_load((ROOT / "compose.p17-poc.yaml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert set(services) == {"postgres", "fixture", "api", "frontend"}
    assert services["postgres"]["environment"]["POSTGRES_DB"] == ("clinical_p17_full_stack")
    assert "/proc/1/cmdline" in services["postgres"]["healthcheck"]["test"][1]
    assert services["fixture"]["depends_on"]["postgres"]["condition"] == ("service_healthy")
    assert services["fixture"]["command"][0:3] == [
        "python",
        "scripts/p17_full_stack_fixture.py",
        "prepare",
    ]
    assert services["fixture"]["environment"]["P17_FIXTURE_CONTAINER_MODE"] == "true"
    assert services["api"]["depends_on"]["fixture"]["condition"] == (
        "service_completed_successfully"
    )
    assert services["api"]["environment"]["KNOWLEDGE_BROWSER_ORIGINS"] == (
        "http://127.0.0.1:${P17_POC_FRONTEND_PORT:-4183},"
        "http://localhost:${P17_POC_FRONTEND_PORT:-4183}"
    )
    assert services["api"]["ports"] == ["127.0.0.1:${P17_POC_API_PORT:-8798}:8788"]
    assert services["frontend"]["ports"] == ["127.0.0.1:${P17_POC_FRONTEND_PORT:-4183}:80"]
    serialized = (ROOT / "compose.p17-poc.yaml").read_text(encoding="utf-8")
    assert "worker-enrichment" not in serialized
    assert "worker-document" not in serialized
    assert "worker-release" not in serialized
    assert "KNOWLEDGE_ENRICHMENT_PROVIDER_MODE" not in serialized


def test_p17_runtime_entry_has_bounded_lifecycle_commands() -> None:
    content = (ROOT / "scripts" / "p17-full-stack-poc.ps1").read_text(encoding="utf-8")

    assert "clinical-p17-poc" in content
    for action in ("start", "build", "verify", "stop"):
        assert f'"{action}"' in content
    assert "compose.p17-poc.yaml" in content
    assert "P17_POC_POSTGRES_PASSWORD" in content
    assert "P17_POC_RUNTIME_CONSUMER_SECRET" in content
    assert "KNOWLEDGE_ADMIN_PASSWORD" not in content


def test_default_compose_remains_free_of_p17_fixture_data() -> None:
    content = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "p17_full_stack" not in content
    assert "p17-full-stack" not in content
