from __future__ import annotations

import json
from pathlib import Path

import pytest

from service.app import _script_style_sha256
from service.contracts import canonical_json_sha256
from service.db.base import Base
from service.maintenance import legacy_migration
from service.repository import parse_markdown_card


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent
CROSSWALK_PATH = ROOT / "tests/fixtures/migration/legacy-wiki-crosswalk.json"


def _crosswalk() -> dict[str, object]:
    return json.loads(CROSSWALK_PATH.read_text(encoding="utf-8"))


def test_crosswalk_classifies_every_declared_legacy_root_once() -> None:
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
        assert (ROOT / rule["path"]).exists(), rule
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


def test_crosswalk_inventory_covers_runtime_references_and_old_plans() -> None:
    crosswalk = _crosswalk()

    assert {group["disposition"] for group in crosswalk["runtime_reference_groups"]} == {
        "replace_in_p4",
        "replace_in_p5",
    }
    assert any(
        group["scope"] == "clinical-workflow/tests/test_adae_knowledge_workflow.py"
        for group in crosswalk["runtime_reference_groups"]
    )
    retired_plans = crosswalk["documentation_retirement"]
    assert len(retired_plans) == len(set(retired_plans)) == 13
    assert all((REPOSITORY_ROOT / path).is_file() for path in retired_plans)


def test_crosswalk_governed_inventory_matches_current_vault_without_duplicate_ids() -> None:
    vault_rule = next(
        rule for rule in _crosswalk()["asset_rules"] if rule["path"] == "vault"
    )
    governed_ids: list[str] = []

    for path in sorted((ROOT / "vault").rglob("*.md")):
        if not path.read_text(encoding="utf-8").startswith("---"):
            continue
        metadata, _ = parse_markdown_card(ROOT / "vault", path)
        if metadata.get("id") and metadata.get("type"):
            governed_ids.append(str(metadata["id"]))

    assert len(governed_ids) == vault_rule["governed_record_count"]
    assert len(set(governed_ids)) == vault_rule["unique_governed_id_count"]


def test_historical_trailing_lf_hash_is_explicitly_not_canonical_json() -> None:
    payload = {"b": 2, "a": 1}
    crosswalk = _crosswalk()

    assert _script_style_sha256(payload) != canonical_json_sha256(payload)
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


def test_legacy_migration_scanner_rejects_malformed_governed_yaml(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    governed = vault / "20_Knowledge/Standards/broken.md"
    governed.parent.mkdir(parents=True)
    governed.write_text("---\nid: broken\ntype: [standard_rule\n---\n", encoding="utf-8")

    with pytest.raises(legacy_migration.LegacyMigrationError, match="broken.md"):
        legacy_migration.scan_legacy_vault(vault)
