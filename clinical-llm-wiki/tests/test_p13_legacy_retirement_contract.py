from __future__ import annotations

import json
from pathlib import Path

from service.db.base import Base


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent
CROSSWALK_PATH = ROOT / "tests/fixtures/migration/legacy-wiki-crosswalk.json"


def _crosswalk() -> dict[str, object]:
    return json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))


def test_crosswalk_records_completed_migration_and_retirement() -> None:
    crosswalk = _crosswalk()
    rules = crosswalk["asset_rules"]
    paths = [rule["path"] for rule in rules]

    assert len(paths) == len(set(paths))
    assert crosswalk["unresolved_assets"] == []
    assert {finding["id"] for finding in crosswalk["reported_findings"]} == set(range(1, 8))
    assert {
        "vault",
        "sources/accessions",
        "sources/packages",
        "snapshots",
        ".review_queue",
        "audit_trail.jsonl",
        "service/app.py",
        "service/repository.py",
        "service/resolver.py",
        "service/snapshot.py",
    } <= set(paths)
    for rule in rules:
        assert not (ROOT / rule["path"]).exists(), rule
        assert rule["disposition"] in {
            "migrate",
            "fixture_or_delete",
            "delete_after_migration",
            "delete_after_docs_sync",
        }
        assert rule["target"]

    vault_rule = next(rule for rule in rules if rule["path"] == "vault")
    assert vault_rule["governed_record_count"] == 104
    assert vault_rule["unique_governed_id_count"] == 104
    assert crosswalk["migration_execution"] == {
        "status": "verified",
        "migration_id": "p13-legacy-wiki-v1",
        "record_count": 104,
        "released_revision_count": 73,
        "unresolved_count": 0,
        "report_object_key": "migration/p13/legacy-wiki-migration-report-v1.json",
        "report_sha256": "70185891f053d61b9dda6651fb1b123c31c5ccc1dea8514fc9f2b87277f586cb",
        "release_id": "release-p13-legacy-wiki-v1",
        "release_manifest_sha256": "f46dc6008e959eea96baad65cd4039a6353de5e0eca92c53ac54831a10451422",
        "runtime_api": "/api/prerelease/v1/runtime-knowledge",
        "idempotent_replays_verified": 2,
    }
    assert crosswalk["retirement_execution"]["status"] == "verified"


def test_crosswalk_inventory_covers_runtime_references_and_old_plans() -> None:
    crosswalk = _crosswalk()

    assert {group["disposition"] for group in crosswalk["runtime_reference_groups"]} == {
        "replaced",
    }
    assert any(
        group["scope"] == "clinical-workflow/tests/test_adae_knowledge_workflow.py"
        for group in crosswalk["runtime_reference_groups"]
    )
    retired_plans = crosswalk["documentation_retirement"]
    assert len(retired_plans) == len(set(retired_plans)) == 13
    assert all(not (REPOSITORY_ROOT / path).exists() for path in retired_plans)


def test_current_product_runtime_has_no_legacy_wiki_dependency() -> None:
    runtime_roots = (
        REPOSITORY_ROOT / "clinical-workflow/src",
        ROOT / "service",
        ROOT / "frontend/src",
    )
    runtime_files = [
        ROOT / "compose.yaml",
    ]
    for runtime_root in runtime_roots:
        runtime_files.extend(
            path
            for path in runtime_root.rglob("*")
            if path.is_file()
            and "test" not in path.parts
            and path.suffix in {".py", ".ts", ".tsx", ".yaml", ".yml"}
        )

    forbidden = (
        "clinical-llm-wiki/vault",
        "clinical-llm-wiki/snapshots",
        "clinical-llm-wiki/sources/packages",
        "127.0.0.1:8787",
        "service.app",
        "service.main",
        "knowledgeLedgerBearerToken",
    )
    violations = {
        str(path.relative_to(REPOSITORY_ROOT)): marker
        for path in runtime_files
        for marker in forbidden
        if marker in path.read_text(encoding="utf-8")
    }
    assert violations == {}


def test_historical_trailing_lf_hash_is_documented_as_verify_only() -> None:
    crosswalk = _crosswalk()
    assert crosswalk["hash_algorithms"]["legacy_script_json"]["disposition"] == (
        "verify-only-never-rewrite"
    )
    assert crosswalk["hash_algorithms"]["schema_bundle"]["serialization"] == (
        "canonical_json"
    )


def test_workflow_regression_contract_freezes_rule_and_artifact_semantics() -> None:
    regression = _crosswalk()["workflow_regression"]

    assert regression["workflow_rule_ids"] == ["wp-adam-spec-baseline"]
    assert "pattern-treatment-emergent-ae" in regression["domain_rule_ids"]
    assert regression["study_rule_ids"] == ["study-decision-synth-onco-001-teae"]
    assert "byte-identical" in regression["required_outcome"]
    assert regression["must_pass_before_legacy_delete"] is True
    assert len(regression["known_baseline_defects"]) == 2


def test_password_and_browser_session_tables_are_frozen_before_implementation() -> None:
    credentials = Base.metadata.tables["user_credentials"]
    sessions = Base.metadata.tables["browser_sessions"]

    assert {
        "user_id",
        "username_normalized",
        "password_hash",
        "must_change_password",
        "failed_attempts",
        "locked_until",
        "password_changed_at",
    } <= set(credentials.columns.keys())
    assert {
        "session_id_hash",
        "user_id",
        "created_at",
        "last_seen_at",
        "expires_at",
        "revoked_at",
    } <= set(sessions.columns.keys())
    assert "password" not in credentials.columns.keys()
    assert "session_id" not in sessions.columns.keys()
