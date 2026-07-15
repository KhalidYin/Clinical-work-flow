"""P5 vertical slice: locked Wiki + approved Study rule + ADAE review gate."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest
import yaml
from fastapi.testclient import TestClient

from src.knowledge.client import (
    KnowledgeServiceClient,
    KnowledgeServiceContractError,
    KnowledgeServiceUnavailable,
)
from src.knowledge.resolver import KnowledgeContextResolver
from src.knowledge.models import WorkflowStage
from src.knowledge.promotion import create_promotion_candidate
from src.knowledge.study_decisions import load_study_decisions
from src.runtime.agent_loop import (
    AgentRuntime,
    _load_mcp_tools,
    build_runtime_context_resolver,
)
from src.runtime.context_resolver import RuntimeContextError, RuntimeContextResolver
from src.runtime.pipeline_contract import PipelineStage
from src.runtime.review_protocol import Decision, DecisionReceipt, FindingDecision


ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = ROOT.parent
WIKI_ROOT = PLATFORM_ROOT / "clinical-llm-wiki"
FIXTURE = ROOT / "tests" / "fixtures" / "studies" / "adae-pilot"
if str(WIKI_ROOT) not in sys.path:
    sys.path.insert(0, str(WIKI_ROOT))

from service.app import create_app  # noqa: E402
from service.config import WikiServiceConfig  # noqa: E402


WORKFLOW_IDS = ("wp-adam-spec-baseline",)
DOMAIN_IDS = (
    "kr-adae-adverse-event-analysis",
    "pattern-adam-derivation-metadata",
    "pattern-analysis-dataset-traceability",
    "pattern-treatment-emergent-ae",
)


class _WikiTransport:
    def __init__(self, client: TestClient) -> None:
        self.client = client

    def __call__(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        response = self.client.request(method, path, json=payload)
        if response.status_code >= 400:
            raise KnowledgeServiceContractError(
                f"Wiki service rejected {path}: {response.status_code} {response.text}"
            )
        return response.json()


class _OfflineTransport:
    def __call__(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        raise KnowledgeServiceUnavailable(f"synthetic offline fixture: {method} {path}")


def _prepare_wiki(tmp_path: Path) -> tuple[TestClient, dict[str, Any], dict[str, Any]]:
    root = tmp_path / "wiki"
    shutil.copytree(WIKI_ROOT / "vault", root / "vault")
    shutil.copytree(WIKI_ROOT / ".review_queue", root / ".review_queue")
    shutil.copytree(WIKI_ROOT / "schemas" / "engine", root / "schemas")
    client = TestClient(create_app(WikiServiceConfig(vault_root=root, schemas_dir=root / "schemas")))
    workflow = client.post(
        "/api/v1/snapshots",
        json={
            "item_ids": list(WORKFLOW_IDS),
            "snapshot_id": "snapshot-workflow-synth-adae",
            "version": "1.0.0",
        },
    )
    domain = client.post(
        "/api/v1/snapshots",
        json={
            "item_ids": list(DOMAIN_IDS),
            "snapshot_id": "snapshot-domain-synth-adae",
            "version": "1.0.0",
        },
    )
    assert workflow.status_code == 201, workflow.text
    assert domain.status_code == 201, domain.text
    return client, workflow.json(), domain.json()


def _prepare_study(
    tmp_path: Path,
    workflow_snapshot: Mapping[str, Any],
    domain_snapshot: Mapping[str, Any],
    bundle: Mapping[str, Any],
    *,
    name: str,
) -> Path:
    study = tmp_path / name
    shutil.copytree(FIXTURE, study)
    manifest = yaml.safe_load((study / "runtime-manifest.yaml").read_text(encoding="utf-8"))
    manifest["schema_version"] = bundle["bundle_version"]
    for section, snapshot, fallback in (
        ("workflow_knowledge", workflow_snapshot, "workflow/snapshots/workflow.json"),
        ("domain_knowledge", domain_snapshot, "knowledge/snapshots/domain.json"),
    ):
        manifest[section].update({
            "snapshot_id": snapshot["snapshot_id"],
            "version": snapshot["version"],
            "sha256": snapshot["sha256"],
            "fallback_path": fallback,
        })
        path = study / fallback
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    (study / "runtime-manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    return study


def _resolver(transport: Any, bundle: Mapping[str, Any]) -> KnowledgeContextResolver:
    client = KnowledgeServiceClient(
        transport,
        bundle_version=bundle["bundle_version"],
        bundle_sha256=bundle["bundle_sha256"],
    )
    return KnowledgeContextResolver(
        client,
        bundle_version=bundle["bundle_version"],
        bundle_sha256=bundle["bundle_sha256"],
        require_domain=True,
    )


def _references(context: Any) -> dict[str, set[str]]:
    return {
        "workflow": {rule.rule_id for rule in context.workflow_rules},
        "domain": {rule.rule_id for rule in context.domain_rules},
        "study": {rule.rule_id for rule in context.study_rules},
        "provenance": {entry.object_id for entry in context.provenance},
    }


def _execute_adae_draft(
    study: Path, resolver: KnowledgeContextResolver
) -> tuple[AgentRuntime, dict[str, Any]]:
    runtime = AgentRuntime(
        project_dir=study,
        context_resolver=RuntimeContextResolver(resolver),
        git_auto_commit=False,
    )
    _load_mcp_tools(runtime)
    intent = "Generate ADAE safety and TEAE specifications"
    action = asyncio.run(runtime._decide_next_action(intent, runtime._assess_context(intent)))
    assert action.stage_id is PipelineStage.ADAM_SPEC
    runtime._bind_governed_context(action)
    result = asyncio.run(runtime._execute_action(action))
    runtime._record_action(action, result)
    return runtime, result


def test_adae_online_and_offline_use_identical_locked_references_and_artifact(
    tmp_path: Path,
) -> None:
    wiki, workflow, domain = _prepare_wiki(tmp_path)
    bundle = wiki.get("/api/v1/version").json()
    online_study = _prepare_study(
        tmp_path, workflow, domain, bundle, name="online-study"
    )
    offline_study = _prepare_study(
        tmp_path, workflow, domain, bundle, name="offline-study"
    )
    online_resolver = _resolver(_WikiTransport(wiki), bundle)
    offline_resolver = _resolver(_OfflineTransport(), bundle)

    online_context = RuntimeContextResolver(online_resolver).resolve_for_stage(
        online_study, PipelineStage.ADAM_SPEC
    )
    offline_context = RuntimeContextResolver(offline_resolver).resolve_for_stage(
        offline_study, PipelineStage.ADAM_SPEC
    )

    assert _references(online_context) == _references(offline_context)
    assert _references(online_context)["workflow"] == set(WORKFLOW_IDS)
    assert "study-decision-synth-onco-001-teae" in _references(online_context)["study"]

    _, online_result = _execute_adae_draft(online_study, online_resolver)
    _, offline_result = _execute_adae_draft(offline_study, offline_resolver)
    online_draft = online_study / "output" / "adam" / "drafts" / "adae-spec.yaml"
    offline_draft = offline_study / "output" / "adam" / "drafts" / "adae-spec.yaml"
    assert hashlib.sha256(online_draft.read_bytes()).hexdigest() == hashlib.sha256(
        offline_draft.read_bytes()
    ).hexdigest()
    assert online_result["applied_rule_refs"] == offline_result["applied_rule_refs"] == [
        "study-decision-synth-onco-001-teae"
    ]
    provenance = json.loads(
        online_draft.with_name("adae-spec.yaml.provenance.json").read_text(encoding="utf-8")
    )
    assert provenance["applied_rule_refs"] == online_result["applied_rule_refs"]
    assert "study_decision" in {
        item["source_kind"] for item in provenance["knowledge_provenance"]
    }


def test_cli_resolver_factory_reproduces_adae_from_locked_snapshots(tmp_path: Path) -> None:
    wiki, workflow, domain = _prepare_wiki(tmp_path)
    bundle = wiki.get("/api/v1/version").json()
    study = _prepare_study(tmp_path, workflow, domain, bundle, name="cli-offline-study")
    runtime = AgentRuntime(
        project_dir=study,
        context_resolver=build_runtime_context_resolver(
            "http://127.0.0.1:1", timeout_seconds=0.2, require_domain=True
        ),
        git_auto_commit=False,
    )
    _load_mcp_tools(runtime)
    intent = "Generate ADAE safety and TEAE specifications"
    action = asyncio.run(runtime._decide_next_action(intent, runtime._assess_context(intent)))

    runtime._bind_governed_context(action)
    result = asyncio.run(runtime._execute_action(action))

    assert result["status"] == "awaiting_human"
    assert (study / "output/adam/drafts/adae-spec.yaml").is_file()
    assert runtime.execution_context is not None
    assert runtime.execution_context.study_rules[0].rule_id == (
        "study-decision-synth-onco-001-teae"
    )


def test_adae_draft_is_not_pipeline_evidence_until_review_is_applied(
    tmp_path: Path,
) -> None:
    wiki, workflow, domain = _prepare_wiki(tmp_path)
    bundle = wiki.get("/api/v1/version").json()
    study = _prepare_study(tmp_path, workflow, domain, bundle, name="review-study")
    runtime, result = _execute_adae_draft(study, _resolver(_WikiTransport(wiki), bundle))

    canonical = study / "output" / "adam" / "specs" / "adae-spec.yaml"
    assert result["status"] == "awaiting_human"
    assert canonical.exists() is False
    assert runtime._scan_pipeline_evidence()["adam_specs"] == []
    packet = runtime.review_queue.load_packet(result["review_id"])
    assert packet is not None and packet.urgency.value == "blocking"
    assert "规范草稿" in packet.agent_summary
    assert all(any("\u4e00" <= char <= "\u9fff" for char in finding.title) for finding in packet.findings)
    assert all(any("\u4e00" <= char <= "\u9fff" for char in finding.rationale) for finding in packet.findings)
    receipt = DecisionReceipt(
        review_id=packet.review_id,
        reviewer="Synthetic Lead Statistical Programmer",
        reviewer_role="non_human_test_fixture",
        decisions=[
            FindingDecision(finding_id=finding.id, decision=Decision.APPROVED)
            for finding in packet.findings
        ],
    )
    runtime.review_queue.submit_decision(receipt)
    runtime._apply_decisions(receipt)

    assert canonical.is_file()
    assert runtime._scan_pipeline_evidence()["adam_specs"]
    final_provenance = json.loads(
        canonical.with_name("adae-spec.yaml.provenance.json").read_text(encoding="utf-8")
    )
    assert final_provenance["approved_by_review_id"] == packet.review_id
    assert final_provenance["approval_confirmation"]["failed"] == 0


def test_adae_missing_approved_study_rule_blocks_before_artifact_creation(
    tmp_path: Path,
) -> None:
    wiki, workflow, domain = _prepare_wiki(tmp_path)
    bundle = wiki.get("/api/v1/version").json()
    study = _prepare_study(tmp_path, workflow, domain, bundle, name="missing-rule-study")
    (study / "knowledge" / "decisions" / "teae-window.json").unlink()
    runtime = AgentRuntime(
        project_dir=study,
        context_resolver=RuntimeContextResolver(_resolver(_WikiTransport(wiki), bundle)),
        git_auto_commit=False,
    )
    _load_mcp_tools(runtime)
    intent = "Generate ADAE safety and TEAE specifications"
    action = asyncio.run(runtime._decide_next_action(intent, runtime._assess_context(intent)))

    with pytest.raises(RuntimeContextError, match="exactly one"):
        runtime._bind_governed_context(action)
    assert (study / "output" / "adam" / "drafts").exists() is False


def test_approved_study_rule_only_generates_a_local_unreviewed_promotion_candidate(
    tmp_path: Path,
) -> None:
    study = tmp_path / "promotion-study"
    shutil.copytree(FIXTURE, study)
    decision = load_study_decisions(
        study,
        study_id="SYNTH-ONCO-001",
        stage=WorkflowStage.ADAM_SPEC,
    )[0]

    artifact = create_promotion_candidate(study, decision)

    assert artifact.path.parent == (study / "knowledge" / "promotion_candidates").resolve()
    assert artifact.candidate.status == "proposed"
    assert artifact.candidate.deidentified is False
    assert artifact.candidate.eligible_for_wiki_proposal is False
    serialized = artifact.path.read_text(encoding="utf-8")
    assert "SYNTH-ONCO-001" not in serialized
    assert not any((WIKI_ROOT / "vault" / "70_Prior-Studies").rglob("*.json"))
