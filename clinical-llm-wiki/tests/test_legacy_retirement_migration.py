from __future__ import annotations

import json
from pathlib import Path

import pytest

from service.maintenance.legacy_migration import (
    LegacyMigrationError,
    build_migration_plan,
    build_runtime_release_manifest,
    canonical_json_bytes,
    scan_legacy_vault,
    write_immutable_report,
)
from service.object_store import InMemoryObjectStore, ObjectConflictError
from service.published_knowledge import (
    PublishedKnowledgeError,
    resolve_published_runtime_context,
)


ROOT = Path(__file__).resolve().parents[1]


def test_scanner_is_fail_closed_and_preserves_governed_identity(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    card = vault / "20_Knowledge" / "rule.md"
    card.parent.mkdir(parents=True)
    card.write_text(
        "---\nid: rule-one\ntype: standard_rule\nversion: 1.2.0\n"
        "approval_status: approved\ncontent_hash: " + "a" * 64 + "\n---\n正文\n",
        encoding="utf-8",
    )
    (vault / "Index.md").write_text("# 导航\n", encoding="utf-8")

    records = scan_legacy_vault(vault)

    assert len(records) == 1
    assert records[0].legacy_id == "rule-one"
    assert records[0].version == "1.2.0"
    assert records[0].body == "正文"
    assert records[0].source_path == "20_Knowledge/rule.md"

    card.write_text("---\nid: broken\ntype: [standard_rule\n---\n", encoding="utf-8")
    with pytest.raises(LegacyMigrationError, match="rule.md"):
        scan_legacy_vault(vault)


def test_migration_plan_covers_every_governed_record_and_is_deterministic() -> None:
    first = build_migration_plan(ROOT)
    second = build_migration_plan(ROOT)

    assert first == second
    assert len(first.records) == 104
    assert len({item.legacy_id for item in first.records}) == 104
    assert all(item.knowledge_unit_id == item.legacy_id for item in first.records)
    assert all(item.source_sha256 and item.target_content_sha256 for item in first.records)
    assert first.unresolved_assets == ()
    assert first.report_sha256 == second.report_sha256


def test_immutable_report_is_idempotent_and_refuses_key_reuse() -> None:
    plan = build_migration_plan(ROOT)
    store = InMemoryObjectStore()

    first = write_immutable_report(plan, store)
    second = write_immutable_report(plan, store)

    assert first == second
    assert first.sha256 == plan.report_sha256
    report = json.loads(store.get_bytes(first.object_key))
    assert report["record_count"] == 104
    assert report["unresolved_assets"] == []

    with pytest.raises(ObjectConflictError):
        store.put_bytes(first.object_key, b"different", media_type="application/json")


def test_report_uses_one_canonical_json_algorithm_without_trailing_newline() -> None:
    assert canonical_json_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}'


def test_runtime_release_manifest_contains_frozen_adae_regression_ids() -> None:
    release = build_runtime_release_manifest(ROOT)
    workflow, domain = release["runtime_snapshots"]

    assert {item["id"] for item in workflow["items"]} >= {"wp-adam-spec-baseline"}
    assert {item["id"] for item in domain["items"]} >= {
        "kr-adae-adverse-event-analysis",
        "pattern-adam-derivation-metadata",
        "pattern-analysis-dataset-traceability",
        "pattern-treatment-emergent-ae",
    }
    assert workflow["sha256"] == __import__("hashlib").sha256(
        canonical_json_bytes(
            {"schema_bundle": workflow["schema_bundle"], "items": workflow["items"]}
        )
    ).hexdigest()


def _snapshot(snapshot_id: str, items: list[dict[str, object]]) -> dict[str, object]:
    bundle = {"version": "1.1.0", "sha256": "a" * 64}
    digest = __import__("hashlib").sha256(
        canonical_json_bytes({"schema_bundle": bundle, "items": items})
    ).hexdigest()
    return {
        "snapshot_id": snapshot_id,
        "version": "1.0.0",
        "sha256": digest,
        "schema_bundle": bundle,
        "items": items,
    }


def test_published_release_adapter_resolves_only_manifest_locked_snapshots() -> None:
    workflow = _snapshot(
        "snapshot-workflow",
        [
            {
                "id": "wp-adam-spec-baseline",
                "type": "workflow_playbook",
                "title": "ADaM 规范",
                "version": "1.0.0",
                "content_hash": "b" * 64,
                "approval_receipt_id": "review-001",
                "audit_reference": "audit-001",
                "sources": ["src-adamig"],
                "workflow_stages": ["adam_spec"],
                "applicability": {"study_ids": [], "conditions": []},
                "purpose": "生成规范。",
                "steps": [{"objective": "定义派生。"}],
            }
        ],
    )
    domain = _snapshot(
        "snapshot-domain",
        [
            {
                "id": "kr-adae",
                "type": "standard_rule",
                "title": "ADAE",
                "version": "1.0.0",
                "content_hash": "c" * 64,
                "approval_receipt_id": "review-002",
                "audit_reference": "audit-002",
                "workflow_stages": ["adam_spec"],
                "applicability": {"study_ids": [], "conditions": []},
                "statements": [
                    {
                        "rule_id": "rule-adae",
                        "statement": "记录 ADAE 规则。",
                        "evidence_refs": ["src-adamig"],
                    }
                ],
            }
        ],
    )
    release = {
        "schema_bundle": {"id": "engine", "version": "1.1.0", "sha256": "a" * 64},
        "runtime_snapshots": [workflow, domain],
    }
    runtime_manifest = {
        "manifest_id": "manifest-1",
        "manifest_sha256": "d" * 64,
        "study_id": "STUDY-1",
        "pipeline_contract": {
            "artifact_id": "pipeline",
            "version": "1.0.0",
            "sha256": "e" * 64,
        },
        "workflow_knowledge": {
            "snapshot_id": workflow["snapshot_id"],
            "version": workflow["version"],
            "sha256": workflow["sha256"],
        },
        "domain_knowledge": {
            "snapshot_id": domain["snapshot_id"],
            "version": domain["version"],
            "sha256": domain["sha256"],
        },
    }
    request = {
        "study_id": "STUDY-1",
        "stage": "adam_spec",
        "runtime_manifest": runtime_manifest,
        "schema_bundle": {"version": "1.1.0", "sha256": "a" * 64},
        "require_workflow": True,
        "require_domain": True,
    }

    result = resolve_published_runtime_context(release, request)

    assert [item["rule_id"] for item in result["workflow_rules"]] == [
        "wp-adam-spec-baseline"
    ]
    assert [item["rule_id"] for item in result["domain_rules"]] == ["rule-adae"]
    assert result["executable"] is True

    request["runtime_manifest"]["domain_knowledge"]["sha256"] = "f" * 64
    with pytest.raises(PublishedKnowledgeError, match="lock mismatch"):
        resolve_published_runtime_context(release, request)
