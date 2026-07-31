from __future__ import annotations

import inspect
from pathlib import Path

import yaml

from service.maintenance import backfill, legacy_migration
from service.processing import worker


ROOT = Path(__file__).resolve().parents[1]


def test_compose_keeps_one_codebase_three_pools_and_loopback_publication() -> None:
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert {"postgres", "migration", "api", "frontend"} <= set(services)
    worker_names = {"worker-document", "worker-enrichment", "worker-release"}
    assert worker_names <= set(services)
    assert "worker-enrichment-live" in services
    assert services["postgres"]["image"].startswith("pgvector/pgvector:")
    assert services["migration"]["command"] == ["alembic", "upgrade", "head"]
    assert services["api"]["ports"] == ["127.0.0.1:8788:8788"]
    assert services["frontend"]["ports"] == ["127.0.0.1:4173:80"]

    worker_builds = {str(services[name]["build"]) for name in worker_names}
    worker_images = {services[name]["image"] for name in worker_names}
    assert len(worker_builds) == len(worker_images) == 1
    for name, pool in (
        ("worker-document", "document"),
        ("worker-enrichment", "enrichment"),
        ("worker-release", "release"),
    ):
        assert services[name]["command"][-2:] == ["--pool", pool]
    # P2-B2 starts the two knowledge-production workers in the complete local demo.
    # Release remains separately gated until P3 authorizes release construction.
    assert "profiles" not in services["worker-document"]
    assert "profiles" not in services["worker-enrichment"]
    assert services["worker-release"]["profiles"] == ["release"]
    live_worker = services["worker-enrichment-live"]
    assert live_worker["profiles"] == ["live"]
    assert live_worker["restart"] == "no"
    assert live_worker["env_file"] == ["./.env.local"]
    assert "KNOWLEDGE_LIVE_RUN_ID" in live_worker["command"][-1]
    assert all("env_file" not in services[name] for name in ("api", "frontend"))

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert (
        "python -m pip install --retries 10 --resume-retries 20 --timeout 60 "
        '"litellm>=1.92,<2"'
        in dockerfile
    )
    assert "--mount=type=cache,target=/root/.cache/pip" in dockerfile
    assert live_worker["build"] == "."
    assert live_worker["image"] == "clinical-knowledge-platform:local"
    assert {".env", ".env.*", ".demo-runtime", "tmp"} <= set(dockerignore)

    serialized = (ROOT / "compose.yaml").read_text(encoding="utf-8").lower()
    assert all(component not in serialized for component in ("kafka", "redis", "neo4j"))


def test_ddl_backfill_and_legacy_migration_have_distinct_fail_closed_entrypoints() -> None:
    backfill_source = inspect.getsource(backfill)
    legacy_source = inspect.getsource(legacy_migration)

    assert "alembic" not in backfill_source.lower()
    assert "legacy" not in backfill.REGISTERED_BACKFILLS
    assert set(backfill.REGISTERED_BACKFILLS) == {"p2b1-evidence-ready"}
    assert "alembic" not in legacy_source.lower()
    assert backfill.main(["--list"]) == 0
    assert legacy_migration.main(["--list"]) == 0


def test_worker_module_exposes_one_pool_parameterized_entrypoint() -> None:
    signature = inspect.signature(worker.main)

    assert "argv" in signature.parameters
    assert worker.main(["--list-pools"]) == 0
