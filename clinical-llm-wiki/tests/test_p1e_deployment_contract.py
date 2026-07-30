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
        assert services[name]["profiles"] == ["workers"]
        assert services[name]["command"][-2:] == ["--pool", pool]

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
