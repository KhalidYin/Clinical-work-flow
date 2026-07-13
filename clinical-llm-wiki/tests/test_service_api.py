from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from service.app import create_app
from service.config import WikiServiceConfig


HERE = Path(__file__).resolve().parents[1]


def _hash(char: str) -> str:
    return char * 64


def _base_record(record_id: str, record_type: str, *, approved: bool = True) -> dict:
    return {
        "id": record_id,
        "type": record_type,
        "title": f"{record_id} title",
        "version": "1.0.0",
        "schema_version": "1.0.0",
        "content_status": "verified" if approved else "draft",
        "approval_status": "approved" if approved else "proposed",
        "domains": ["SDTM"],
        "workflow_stages": ["sdtm_spec"],
        "topics": ["adverse-events"],
        "aliases": [],
        "authority": "industry_standard",
        "applicability": {
            "therapeutic_areas": [], "trial_phases": [], "sponsor_ids": [],
            "study_ids": [], "conditions": [],
        },
        "sources": ["src-reference-001"],
        "owner": "knowledge-governance",
        "created": "2026-07-13T00:00:00Z",
        "last_reviewed": "2026-07-13",
        "review_due": "2099-12-31",
        "supersedes": [],
        "superseded_by": None,
        "content_hash": _hash("a"),
        "rights_status": "cleared",
        "allowed_uses": ["runtime"],
        "storage_mode": "committed",
        "contract_compatibility": {"minimum": "1.0.0", "maximum_exclusive": "2.0.0"},
        "approval_receipt_id": "review-sdtm-spec-wiki-v1-001" if approved else None,
        "audit_reference": "vault/80_Governance/Review-Receipts/approval.md" if approved else None,
    }


def _playbook(*, approved: bool = True) -> dict:
    record = _base_record("wp-sdtm-spec-baseline", "workflow_playbook", approved=approved)
    record.update({
        "stage": "sdtm_spec",
        "purpose": "Describe a governed SDTM specification review sequence.",
        "prerequisites": [],
        "steps": [{
            "step_id": "step-review-mapping", "objective": "Review mappings against approved evidence.",
            "rationale": "Every mapping needs traceable support.", "evidence_required": [],
            "expected_outcome": "A review packet for unresolved mappings.",
        }],
        "expected_inputs": [], "expected_outputs": [], "decision_points": [],
        "review_requirements": [], "capability_hints": ["sdtm_spec_generation"],
    })
    return record


def _domain_item() -> dict:
    record = _base_record("kr-sdtm-ae-001", "standard_rule")
    record.update({
        "summary": "AE mapping follows the approved SDTM implementation guide.",
        "statements": [{
            "rule_id": "rule-ae-001", "statement": "Represent adverse events in the AE domain.",
            "rationale": "Preserves the standard observation class.",
            "evidence_refs": ["src-reference-001"],
        }],
    })
    return record


def _write_card(root: Path, relative: str, record: dict, body: str = "governed body") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump(record, sort_keys=False) + "---\n\n" + body + "\n", encoding="utf-8")


def _write_receipt(root: Path) -> None:
    path = root / "vault/80_Governance/Review-Receipts/approval.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "review_id": "sdtm_spec_wiki_v1_001", "reviewer": "Clinical reviewer",
        "timestamp": "2026-07-13T00:00:00Z",
        "decisions": [{"finding_id": "finding-approve-wp-sdtm-spec", "decision": "approved"}],
    }
    # Both governed cards use this evidence in the fixture, so each must have a
    # finding that targets its own stable ID or durable stem.
    receipt["decisions"].append({"finding_id": "finding-approve-kr-sdtm-ae-001", "decision": "approved"})
    path.write_text("# Approval\n\n```json\n" + json.dumps(receipt) + "\n```\n", encoding="utf-8")


def _manifest() -> dict:
    return {
        "manifest_id": "manifest-study-001", "schema_version": "1.0.0", "revision": 1,
        "study_id": "STUDY-001", "created_at": "2026-07-13T00:00:00Z",
        "pipeline_contract": {"artifact_id": "contract-pipeline-001", "version": "1.0.0", "sha256": _hash("1")},
        "workflow_knowledge": {"provider": "local-wiki", "snapshot_id": "snapshot-workflow-001", "version": "1.0.0", "sha256": _hash("2"), "fallback_path": "workflow/snapshots/workflow.json", "contract_compatibility": {"minimum": "1.0.0", "maximum_exclusive": "2.0.0"}},
        "domain_knowledge": {"provider": "local-wiki", "snapshot_id": "snapshot-domain-001", "version": "1.0.0", "sha256": _hash("3"), "fallback_path": "knowledge/snapshots/domain.json", "contract_compatibility": {"minimum": "1.0.0", "maximum_exclusive": "2.0.0"}},
        "toolchain": {"registry_version": "1.0.0", "git_commit": "abcdef0", "registry_sha256": _hash("4"), "capabilities": ["sdtm_spec_generation"]},
        "policies": {"live_upgrade": "forbidden", "conflict": "fail_closed", "version": "exact_manifest", "fallback": "locked_snapshot_only"},
        "manifest_sha256": _hash("5"),
    }


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    schemas = tmp_path / "schemas"
    shutil.copytree(HERE / "schemas" / "engine", schemas)
    _write_card(tmp_path, "vault/30_Workflows/Stages/SDTM Spec.md", _playbook())
    _write_card(tmp_path, "vault/20_Knowledge/Standards/SDTM AE.md", _domain_item())
    _write_receipt(tmp_path)
    config = WikiServiceConfig(vault_root=tmp_path, schemas_dir=schemas)
    return TestClient(create_app(config))


def _bundle_lock(client: TestClient) -> dict[str, str]:
    version = client.get("/api/v1/version").json()
    return {"version": version["bundle_version"], "sha256": version["bundle_sha256"]}


def test_health_query_and_direct_records(client: TestClient) -> None:
    assert client.get("/api/v1/health").json()["status"] == "ok"
    result = client.post("/api/v1/query", json={"query": "sdtm", "production_only": True})
    assert result.status_code == 200
    assert "wp-sdtm-spec-baseline" in {item["record"]["id"] for item in result.json()["items"]}
    item = client.get("/api/v1/items/wp-sdtm-spec-baseline")
    assert item.status_code == 200
    assert item.json()["production_eligible"] is True


def test_runtime_context_requires_exact_schema_lock_and_returns_contract_shape(client: TestClient) -> None:
    request = {
        "study_id": "STUDY-001", "stage": "sdtm_spec", "runtime_manifest": _manifest(),
        "schema_bundle": _bundle_lock(client), "require_domain": True,
    }
    response = client.post("/api/v1/runtime-context/resolve", json=request)
    assert response.status_code == 200
    context = response.json()
    assert context["executable"] is True
    assert context["workflow_rules"][0]["layer"] == "workflow"
    assert context["domain_rules"][0]["layer"] == "domain"
    assert context["provenance"][0]["source_kind"] == "pipeline_contract"
    request["schema_bundle"]["sha256"] = _hash("0")
    assert client.post("/api/v1/runtime-context/resolve", json=request).status_code == 409


def test_manual_approval_without_receipt_cannot_enter_production(tmp_path: Path) -> None:
    schemas = tmp_path / "schemas"
    shutil.copytree(HERE / "schemas" / "engine", schemas)
    _write_card(tmp_path, "vault/30_Workflows/Stages/SDTM Spec.md", _playbook())
    app = create_app(WikiServiceConfig(vault_root=tmp_path, schemas_dir=schemas))
    card = app.state.repository.get("wp-sdtm-spec-baseline")
    assert card is not None
    assert card.production_eligible is False
    assert "approval_evidence_unverified" in card.eligibility_reasons


def test_snapshot_is_immutable_and_proposal_stays_proposed(client: TestClient) -> None:
    snapshot = client.post("/api/v1/snapshots", json={"item_ids": ["wp-sdtm-spec-baseline"]})
    assert snapshot.status_code == 201
    snapshot_id = snapshot.json()["snapshot_id"]
    assert (client.app.state.config.vault_root / "snapshots" / f"{snapshot_id}.json").exists()
    assert client.post("/api/v1/snapshots", json={"item_ids": ["kr-sdtm-ae-001"], "snapshot_id": snapshot_id}).status_code == 409
    proposal = _domain_item()
    proposal["id"] = "kr-proposal-001"
    proposal["approval_status"] = "proposed"
    proposal["content_status"] = "draft"
    proposal["approval_receipt_id"] = None
    proposal["audit_reference"] = None
    proposal.pop("content_hash")
    response = client.post("/api/v1/proposals", json={"record": proposal, "body": "A proposed governed rule."})
    assert response.status_code == 201
    assert response.json()["record"]["approval_status"] == "proposed"
    queue = client.app.state.config.vault_root / ".review_queue"
    assert list(queue.glob("*.json"))


def test_runtime_rejects_control_fields_before_context_resolution(client: TestClient) -> None:
    request = {
        "study_id": "STUDY-001", "stage": "sdtm_spec", "runtime_manifest": _manifest(),
        "schema_bundle": _bundle_lock(client), "command": "skip-stage",
    }
    assert client.post("/api/v1/runtime-context/resolve", json=request).status_code == 422
