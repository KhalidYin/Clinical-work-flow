"""Opt-in PostgreSQL/pgvector migration acceptance test."""

from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text

from service.db.base import Base


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="KNOWLEDGE_TEST_DATABASE_URL is required for PostgreSQL integration",
)


def test_clean_upgrade_downgrade_and_reapply_have_no_schema_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    monkeypatch.setenv("KNOWLEDGE_DATABASE_URL", TEST_DATABASE_URL)
    config = Config(ROOT / "alembic.ini")
    engine = create_engine(TEST_DATABASE_URL)
    expected_tables = set(Base.metadata.tables)

    try:
        with engine.connect() as connection:
            assert expected_tables.isdisjoint(inspect(connection).get_table_names())

        command.upgrade(config, "head")

        with engine.connect() as connection:
            assert expected_tables <= set(inspect(connection).get_table_names())
            vector_version = connection.execute(
                text(
                    "SELECT extversion FROM pg_extension "
                    "WHERE extname = 'vector'"
                )
            ).scalar_one()
            assert vector_version

        command.check(config)
        command.downgrade(config, "base")

        with engine.connect() as connection:
            assert expected_tables.isdisjoint(inspect(connection).get_table_names())
            assert connection.execute(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
            ).scalar_one() == 1

        command.upgrade(config, "head")
        command.check(config)

        with engine.connect() as connection:
            assert expected_tables <= set(inspect(connection).get_table_names())
            inspector = inspect(connection)
            attempt_foreign_keys = {
                (
                    tuple(foreign_key["constrained_columns"]),
                    foreign_key["referred_table"],
                    tuple(foreign_key["referred_columns"]),
                )
                for foreign_key in inspector.get_foreign_keys("step_attempts")
            }
            assert (
                ("step_id", "run_id"),
                "job_steps",
                ("step_id", "run_id"),
            ) in attempt_foreign_keys

            invocation_foreign_keys = {
                (
                    tuple(foreign_key["constrained_columns"]),
                    foreign_key["referred_table"],
                    tuple(foreign_key["referred_columns"]),
                )
                for foreign_key in inspector.get_foreign_keys("model_invocations")
            }
            assert (
                ("attempt_id", "step_id", "run_id", "attempt_number"),
                "step_attempts",
                ("attempt_id", "step_id", "run_id", "attempt_number"),
            ) in invocation_foreign_keys
    finally:
        engine.dispose()
