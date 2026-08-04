from __future__ import annotations

from io import StringIO
import importlib
from pathlib import Path
import tomllib

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import Column, Constraint, ForeignKeyConstraint

from service.db.base import Base
from service.auth import identity_authorization
from service.processing import model_provider


ROOT = Path(__file__).resolve().parents[1]


def test_database_runtime_dependencies_are_explicit() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = project["project"]["dependencies"]

    assert "SQLAlchemy>=2.0,<3" in dependencies
    assert "psycopg[binary]>=3.2,<4" in dependencies
    assert "alembic>=1.17,<2" in dependencies
    assert "pgvector>=0.4,<1" in dependencies
    assert project["build-system"]["build-backend"] == "setuptools.build_meta"
    assert project["tool"]["setuptools"]["packages"]["find"]["include"] == [
        "service*",
        "scripts*",
    ]


def test_canonical_metadata_owns_the_p2a_database_tables() -> None:
    assert set(Base.metadata.tables) == {
        "audit_events",
        "browser_sessions",
        "candidate_evidence",
        "candidate_relation_proposals",
        "evidence",
        "evaluation_runs",
        "index_manifests",
        "job_steps",
        "knowledge_candidates",
        "knowledge_relations",
        "knowledge_revisions",
        "knowledge_units",
        "model_invocations",
        "model_profiles",
        "object_write_intents",
        "platform_users",
        "processing_runs",
        "prompt_profiles",
        "release_items",
        "releases",
        "relation_proposal_evidence",
        "review_decisions",
        "role_bindings",
        "service_accounts",
        "source_artifacts",
        "source_versions",
        "sources",
        "step_attempts",
        "user_credentials",
    }


def test_ledger_and_model_tables_preserve_the_frozen_p1_b0_contract() -> None:
    attempt_columns = set(Base.metadata.tables["step_attempts"].columns.keys())
    assert set(model_provider.StepAttemptContext.model_fields) <= attempt_columns

    model_profile_columns = set(Base.metadata.tables["model_profiles"].columns.keys())
    assert set(model_provider.ModelProfile.model_fields) <= model_profile_columns

    prompt_profile_columns = set(Base.metadata.tables["prompt_profiles"].columns.keys())
    assert {
        *model_provider.PromptProfile.model_fields,
        "output_schema_sha256",
    } <= prompt_profile_columns

    invocation_columns = set(Base.metadata.tables["model_invocations"].columns.keys())
    assert {
        "invocation_id",
        "created_at",
        "run_id",
        "step_id",
        "attempt_id",
        "attempt_number",
        "previous_attempt_id",
        "status",
        "model_profile_id",
        "model_profile_version",
        "provider",
        "model",
        "prompt_profile_id",
        "prompt_profile_version",
        "output_schema_sha256",
        "data_boundary",
        "input_sha256",
        "output_sha256",
        "provider_request_id",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cost_usd",
        "latency_ms",
        "output",
        "error_type",
        "error_message",
    } <= invocation_columns


def test_p2b1_governance_tables_preserve_revision_and_decision_identity() -> None:
    candidate_columns = set(Base.metadata.tables["knowledge_candidates"].columns.keys())
    assert {
        "candidate_id",
        "candidate_group_id",
        "parent_candidate_id",
        "revision_number",
        "content_sha256",
        "author_actor_id",
        "advisory_signals",
        "origin_model_invocation_id",
    } <= candidate_columns

    revision_columns = set(Base.metadata.tables["knowledge_revisions"].columns.keys())
    assert "author_actor_id" in revision_columns

    decision_columns = set(Base.metadata.tables["review_decisions"].columns.keys())
    assert {
        "candidate_revision_number",
        "content_sha256",
        "idempotency_key",
    } <= decision_columns

    proposal_columns = set(Base.metadata.tables["candidate_relation_proposals"].columns.keys())
    assert {
        "proposal_id",
        "candidate_id",
        "relation_type",
        "target_knowledge_unit_id",
        "status",
    } <= proposal_columns
    assert set(Base.metadata.tables["relation_proposal_evidence"].columns.keys()) == {
        "proposal_id",
        "evidence_id",
    }


def test_canonical_schema_keeps_secrets_paths_and_other_products_out() -> None:
    all_columns = {
        column.name for table in Base.metadata.tables.values() for column in table.columns
    }

    assert {
        "api_key",
        "access_token",
        "secret_value",
        "absolute_path",
        "provider_url",
        "study_id",
        "workflow_id",
        "agent_id",
        "project_memory_id",
    }.isdisjoint(all_columns)
    assert set(Base.metadata.tables["source_artifacts"].columns.keys()) >= {
        "parent_artifact_id",
        "object_key",
        "parser_profile_version",
        "sha256",
        "media_type",
        "size_bytes",
        "status",
    }
    assert set(Base.metadata.tables["evidence"].columns.keys()) >= {
        "derived_artifact_id",
        "source_sha256",
        "parser_profile_version",
    }
    assert "secret_ref" in Base.metadata.tables["model_profiles"].columns
    assert "secret_ref" in Base.metadata.tables["service_accounts"].columns


def test_identity_authorization_tables_preserve_p1_c_contract() -> None:
    platform_user_columns = set(Base.metadata.tables["platform_users"].columns.keys())
    assert {
        "user_id",
        "identity_source",
        "issuer",
        "subject",
        "display_name",
        "email",
        "status",
        "last_authenticated_at",
    } <= platform_user_columns

    role_binding_columns = set(Base.metadata.tables["role_bindings"].columns.keys())
    assert {"user_id", "role", "granted_by_actor_id", "created_at"} <= role_binding_columns

    service_account_columns = set(Base.metadata.tables["service_accounts"].columns.keys())
    assert {
        "service_account_id",
        "display_name",
        "worker_pool",
        "scopes",
        "secret_ref",
        "status",
        "created_by_actor_id",
    } <= service_account_columns
    assert {
        "secret_value",
        "client_secret",
        "access_token",
        "password",
    }.isdisjoint(service_account_columns)
    assert {
        role.value
        for role in identity_authorization.ProductRole
        if role is not identity_authorization.ProductRole.SERVICE_ACCOUNT
    } == {
        "platform_admin",
        "knowledge_curator",
        "reviewer",
        "release_manager",
        "consumer",
    }


def test_ledger_context_uses_composite_foreign_keys() -> None:
    attempt_fks = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in Base.metadata.tables["step_attempts"].constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert (
        ("step_id", "run_id"),
        ("job_steps.step_id", "job_steps.run_id"),
    ) in attempt_fks

    invocation_fks = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in Base.metadata.tables["model_invocations"].constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert (
        ("attempt_id", "step_id", "run_id", "attempt_number"),
        (
            "step_attempts.attempt_id",
            "step_attempts.step_id",
            "step_attempts.run_id",
            "step_attempts.attempt_number",
        ),
    ) in invocation_fks


def test_sync_database_session_accepts_only_the_psycopg_postgres_dialect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_module = importlib.import_module("service.db.session")

    monkeypatch.setenv(
        "KNOWLEDGE_DATABASE_URL",
        "postgresql+psycopg://knowledge:example@localhost/knowledge",
    )
    assert session_module.database_url_from_environment().startswith("postgresql+psycopg://")

    engine = session_module.create_database_engine(
        "postgresql+psycopg://knowledge:example@localhost/knowledge"
    )
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"

    factory = session_module.create_session_factory(engine)
    assert factory.kw["expire_on_commit"] is False

    with pytest.raises(ValueError, match=r"postgresql\+psycopg"):
        session_module.create_database_engine("sqlite:///knowledge.db")

    monkeypatch.delenv("KNOWLEDGE_DATABASE_URL")
    with pytest.raises(RuntimeError, match="KNOWLEDGE_DATABASE_URL"):
        session_module.database_url_from_environment()


def test_alembic_has_linear_reviewable_revisions(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Config(ROOT / "alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == [script.get_current_head()]
    head = script.get_revision(script.get_current_head())
    assert head is not None
    assert head.revision == "20260801_0008"
    assert head.down_revision == "20260731_0007"
    initial = script.get_revision("20260730_0001")
    assert initial is not None
    assert initial.down_revision is None

    monkeypatch.setenv(
        "KNOWLEDGE_DATABASE_URL",
        "postgresql+psycopg://knowledge:example@localhost/knowledge",
    )
    output = StringIO()
    config.output_buffer = output
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()

    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    for table_name in Base.metadata.tables:
        assert f"CREATE TABLE {table_name}" in sql


def test_linear_revision_columns_match_canonical_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = Config(ROOT / "alembic.ini")
    script = ScriptDirectory.from_config(config)
    revisions = list(reversed(list(script.walk_revisions(base="base", head="heads"))))
    assert [revision.revision for revision in revisions] == [
        "20260730_0001",
        "20260730_0002",
        "20260730_0003",
        "20260730_0004",
        "20260730_0005",
        "20260730_0006",
        "20260731_0007",
        "20260801_0008",
    ]

    class MigrationRecorder:
        def __init__(self) -> None:
            self.tables: dict[str, set[str]] = {}
            self.constraints: dict[str, set[str]] = {}
            self.indexes: dict[str, set[str]] = {}
            self.executed: list[str] = []
            self.dropped: list[str] = []

        @staticmethod
        def f(name: str) -> str:
            return name

        def execute(self, statement: str) -> None:
            self.executed.append(statement)

        def create_table(self, name: str, *elements: object) -> None:
            self.tables[name] = {
                element.name for element in elements if isinstance(element, Column)
            }
            self.constraints[name] = {
                str(element.name) for element in elements if isinstance(element, Constraint)
            }

        def create_index(
            self,
            name: str,
            table_name: str,
            columns: list[str],
            *,
            unique: bool,
            **kwargs: object,
        ) -> None:
            del columns, unique, kwargs
            self.indexes.setdefault(table_name, set()).add(name)

        def create_check_constraint(
            self,
            name: str,
            table_name: str,
            condition: str,
        ) -> None:
            del condition
            self.constraints.setdefault(table_name, set()).add(name)

        def create_unique_constraint(
            self,
            name: str,
            table_name: str,
            columns: list[str],
        ) -> None:
            del columns
            self.constraints.setdefault(table_name, set()).add(name)

        def create_foreign_key(
            self,
            name: str,
            source_table: str,
            referent_table: str,
            local_cols: list[str],
            remote_cols: list[str],
            **kwargs: object,
        ) -> None:
            del referent_table, local_cols, remote_cols, kwargs
            self.constraints.setdefault(source_table, set()).add(name)

        def add_column(self, table_name: str, column: Column) -> None:
            self.tables.setdefault(table_name, set()).add(column.name)

        def alter_column(
            self,
            table_name: str,
            column_name: str,
            **kwargs: object,
        ) -> None:
            del table_name, column_name, kwargs

        def drop_constraint(
            self,
            name: str,
            table_name: str,
            *,
            type_: str,
        ) -> None:
            del name, table_name, type_

        def drop_index(self, name: str, *, table_name: str) -> None:
            del name, table_name

        def drop_column(self, table_name: str, column_name: str) -> None:
            del table_name, column_name

        def drop_table(self, name: str) -> None:
            self.dropped.append(name)

    recorder = MigrationRecorder()
    for revision in revisions:
        monkeypatch.setattr(revision.module, "op", recorder)
        revision.module.upgrade()

    assert recorder.executed == ["CREATE EXTENSION IF NOT EXISTS vector"]
    assert set(recorder.tables) == set(Base.metadata.tables)
    for table_name, table in Base.metadata.tables.items():
        assert recorder.tables[table_name] == set(table.columns.keys())
        assert recorder.constraints[table_name] == {
            str(constraint.name) for constraint in table.constraints
        }
        assert recorder.indexes.get(table_name, set()) == {
            str(index.name) for index in table.indexes
        }

    for revision in reversed(revisions):
        revision.module.downgrade()
    assert set(recorder.dropped) == set(Base.metadata.tables)
    assert len(recorder.dropped) == len(set(recorder.dropped))


def test_application_never_creates_or_mutates_schema_at_runtime() -> None:
    runtime_sources = [
        path for path in (ROOT / "service").rglob("*.py") if "migrations" not in path.parts
    ]
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in runtime_sources)

    assert ".create_all(" not in source_text
    assert ".drop_all(" not in source_text
