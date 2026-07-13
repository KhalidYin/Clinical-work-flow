"""Runtime/Knowledge boundary tests: fixed stages, exact locks and safe fallback."""

from __future__ import annotations

import json
import asyncio
import hashlib
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError

import pytest
import yaml

from src.knowledge.client import (
    HttpKnowledgeTransport,
    KnowledgeServiceContractError,
    KnowledgeServiceClient,
    KnowledgeServiceUnavailable,
)
from src.knowledge.compatibility import sha256_canonical_json
from src.knowledge.models import ProvenanceEntry, ResolvedRule, RuleLayer, RuntimeManifest
from src.knowledge.resolver import ContextResolutionError, KnowledgeContextResolver
from src.knowledge.snapshot import context_from_snapshots, load_locked_snapshot
from src.runtime.context_resolver import RuntimeContextError, RuntimeContextResolver
from src.runtime.agent_loop import AgentAction, AgentRuntime
from src.runtime.pipeline_contract import PipelineStage


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "contracts"
BUNDLE = json.loads((ROOT / "schemas" / "contract-bundle.json").read_text(encoding="utf-8"))


def _fixture(relative: str) -> dict[str, Any]:
    return json.loads((FIXTURES / relative).read_text(encoding="utf-8"))


def _snapshot(items: list[dict[str, Any]], snapshot_id: str) -> dict[str, Any]:
    content = {
        "schema_bundle": {"version": BUNDLE["bundle_version"], "sha256": BUNDLE["bundle_sha256"]},
        "items": items,
    }
    return {
        "snapshot_id": snapshot_id,
        "version": "1.0.0",
        "sha256": sha256_canonical_json(content),
        "created_at": "2026-07-13T00:00:00Z",
        **content,
    }


def _project_with_locks(tmp_path: Path) -> tuple[RuntimeManifest, dict[str, Any], dict[str, Any]]:
    playbook = _fixture("knowledge/workflow_playbook.json")
    domain = _fixture("knowledge/knowledge_item.json")
    workflow = _snapshot([playbook], "snapshot-workflow-runtime")
    domain_snapshot = _snapshot([domain], "snapshot-domain-runtime")
    workflow_path = tmp_path / "workflow" / "snapshots" / "workflow.json"
    domain_path = tmp_path / "knowledge" / "snapshots" / "domain.json"
    workflow_path.parent.mkdir(parents=True)
    domain_path.parent.mkdir(parents=True)
    workflow_path.write_text(json.dumps(workflow), encoding="utf-8")
    domain_path.write_text(json.dumps(domain_snapshot), encoding="utf-8")
    manifest = _fixture("study/runtime_manifest.json")
    manifest["workflow_knowledge"].update(
        {"snapshot_id": workflow["snapshot_id"], "sha256": workflow["sha256"], "fallback_path": "workflow/snapshots/workflow.json"}
    )
    manifest["domain_knowledge"].update(
        {"snapshot_id": domain_snapshot["snapshot_id"], "sha256": domain_snapshot["sha256"], "fallback_path": "knowledge/snapshots/domain.json"}
    )
    parsed = RuntimeManifest.model_validate(manifest)
    return parsed, workflow, domain_snapshot


class _OfflineTransport:
    def __call__(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        raise KnowledgeServiceUnavailable("offline")


class _StaticTransport:
    def __init__(self, context: Mapping[str, Any], *, wrong_version: bool = False) -> None:
        self.context = context
        self.calls: list[tuple[str, str, Mapping[str, Any] | None]] = []
        self.wrong_version = wrong_version

    def __call__(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        self.calls.append((method, path, payload))
        if path.endswith("/version"):
            return {
                "bundle_id": "clinical-workflow-contracts",
                "bundle_version": "9.0.0" if self.wrong_version else BUNDLE["bundle_version"],
                "bundle_sha256": BUNDLE["bundle_sha256"],
            }
        return self.context


def _client(transport: Any) -> KnowledgeServiceClient:
    return KnowledgeServiceClient(
        transport, bundle_version=BUNDLE["bundle_version"], bundle_sha256=BUNDLE["bundle_sha256"]
    )


def _resolver(transport: Any) -> KnowledgeContextResolver:
    return KnowledgeContextResolver(
        _client(transport), bundle_version=BUNDLE["bundle_version"], bundle_sha256=BUNDLE["bundle_sha256"],
        require_domain=True,
    )


def _context_raw(manifest: RuntimeManifest, workflow: dict[str, Any], domain: dict[str, Any]) -> dict[str, Any]:
    base = context_from_snapshots(
        manifest=manifest,
        stage="sdtm_spec",
        workflow_snapshot=load_locked_snapshot(
            _snapshot_root(workflow), manifest.workflow_knowledge,
            expected_bundle_version=BUNDLE["bundle_version"], expected_bundle_sha256=BUNDLE["bundle_sha256"],
        ),
        domain_snapshot=load_locked_snapshot(
            _snapshot_root(domain), manifest.domain_knowledge,
            expected_bundle_version=BUNDLE["bundle_version"], expected_bundle_sha256=BUNDLE["bundle_sha256"],
        ),
    )
    return base.model_dump(mode="json")


def _snapshot_root(snapshot: dict[str, Any]) -> Path:
    # The helper is replaced by the test below when it creates physical snapshots.
    # It is deliberately never used independently.
    raise AssertionError("snapshot root must be supplied by a test")


def _study_rule(rule_id: str, statement: str, *, priority: int = 600) -> ResolvedRule:
    decision_id = rule_id.replace("rule-", "decision-", 1)
    return ResolvedRule(
        rule_id=rule_id, layer=RuleLayer.STUDY, priority=priority, title="Study decision",
        statement=statement, source_ids=(decision_id,), source_version="1.0.0",
        source_sha256="6" * 64, approval_receipt_id="receipt-study-001",
    )


def _study_provenance(rule_id: str) -> ProvenanceEntry:
    decision_id = rule_id.replace("rule-", "decision-", 1)
    return ProvenanceEntry(
        provenance_id=f"prov-{decision_id}",
        object_id=decision_id,
        object_version="1.0.0",
        object_sha256="6" * 64,
        source_kind="study_decision",
        snapshot_id=None,
        audit_reference=f"knowledge/decisions/{decision_id}.json",
    )


def test_offline_resolution_uses_only_manifest_locked_snapshots(tmp_path: Path) -> None:
    manifest, _, _ = _project_with_locks(tmp_path)
    resolver = _resolver(_OfflineTransport())
    context = resolver.resolve(project_dir=tmp_path, manifest=manifest, stage=PipelineStage.SDTM_SPEC)
    assert context.executable is True
    assert context.stage.value == PipelineStage.SDTM_SPEC.value
    assert {entry.snapshot_id for entry in context.provenance if entry.snapshot_id} == {
        manifest.workflow_knowledge.snapshot_id,
        manifest.domain_knowledge.snapshot_id,
    }


def test_online_context_is_exactly_bound_to_manifest_and_fixed_stage(tmp_path: Path) -> None:
    manifest, _, _ = _project_with_locks(tmp_path)
    workflow = load_locked_snapshot(
        tmp_path, manifest.workflow_knowledge,
        expected_bundle_version=BUNDLE["bundle_version"], expected_bundle_sha256=BUNDLE["bundle_sha256"],
    )
    domain = load_locked_snapshot(
        tmp_path, manifest.domain_knowledge,
        expected_bundle_version=BUNDLE["bundle_version"], expected_bundle_sha256=BUNDLE["bundle_sha256"],
    )
    raw = context_from_snapshots(
        manifest=manifest, stage="sdtm_spec", workflow_snapshot=workflow, domain_snapshot=domain
    ).model_dump(mode="json")
    transport = _StaticTransport(raw)
    result = _resolver(transport).resolve(project_dir=tmp_path, manifest=manifest, stage="sdtm_spec")
    assert result.execution_context_sha256 == raw["execution_context_sha256"]
    runtime_request = transport.calls[-1][2]
    assert runtime_request is not None
    assert runtime_request["stage"] == "sdtm_spec"
    assert set(runtime_request) == {
        "study_id", "stage", "runtime_manifest", "schema_bundle", "require_workflow", "require_domain"
    }


def test_online_context_rejects_knowledge_provenance_outside_manifest_snapshot(
    tmp_path: Path,
) -> None:
    manifest, _, _ = _project_with_locks(tmp_path)
    workflow = load_locked_snapshot(
        tmp_path,
        manifest.workflow_knowledge,
        expected_bundle_version=BUNDLE["bundle_version"],
        expected_bundle_sha256=BUNDLE["bundle_sha256"],
    )
    domain = load_locked_snapshot(
        tmp_path,
        manifest.domain_knowledge,
        expected_bundle_version=BUNDLE["bundle_version"],
        expected_bundle_sha256=BUNDLE["bundle_sha256"],
    )
    raw = context_from_snapshots(
        manifest=manifest,
        stage="sdtm_spec",
        workflow_snapshot=workflow,
        domain_snapshot=domain,
    ).model_dump(mode="json")
    workflow_provenance = next(
        item for item in raw["provenance"] if item["source_kind"] == "workflow_knowledge"
    )
    workflow_provenance["snapshot_id"] = "snapshot-unlocked-current-index"
    raw["execution_context_sha256"] = sha256_canonical_json(
        {key: value for key, value in raw.items() if key != "execution_context_sha256"}
    )

    with pytest.raises(ContextResolutionError, match="snapshot"):
        _resolver(_StaticTransport(raw)).resolve(
            project_dir=tmp_path,
            manifest=manifest,
            stage="sdtm_spec",
        )


def test_reachable_schema_drift_does_not_silently_fallback(tmp_path: Path) -> None:
    manifest, _, _ = _project_with_locks(tmp_path)
    with pytest.raises(ContextResolutionError, match="contract"):
        _resolver(_StaticTransport({}, wrong_version=True)).resolve(
            project_dir=tmp_path, manifest=manifest, stage="sdtm_spec"
        )


@pytest.mark.parametrize("failure", ("missing", "corrupt"))
def test_offline_missing_or_corrupt_locked_snapshot_fails_closed(
    tmp_path: Path, failure: str
) -> None:
    manifest, _, _ = _project_with_locks(tmp_path)
    workflow_path = tmp_path / manifest.workflow_knowledge.fallback_path
    if failure == "missing":
        workflow_path.unlink()
    else:
        workflow_path.write_text('{"snapshot_id":"tampered"}', encoding="utf-8")

    with pytest.raises(ContextResolutionError, match="snapshot"):
        _resolver(_OfflineTransport()).resolve(
            project_dir=tmp_path, manifest=manifest, stage="sdtm_spec"
        )


def test_http_rejection_is_contract_error_not_offline_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject(*_: Any, **__: Any) -> None:
        raise HTTPError("http://127.0.0.1:8787/api/v1/version", 409, "conflict", {}, None)

    monkeypatch.setattr("src.knowledge.client.urlopen", reject)
    transport = HttpKnowledgeTransport("http://127.0.0.1:8787")
    with pytest.raises(KnowledgeServiceContractError, match="409"):
        transport("GET", "/api/v1/version")


def test_same_priority_study_rules_block_instead_of_silently_selecting_one(tmp_path: Path) -> None:
    manifest, _, _ = _project_with_locks(tmp_path)
    context = _resolver(_OfflineTransport()).resolve(
        project_dir=tmp_path,
        manifest=manifest,
        stage="sdtm_spec",
        study_rules=(
            _study_rule("rule-study-001", "Use coding convention A."),
            _study_rule("rule-study-002", "Use coding convention B."),
        ),
        study_provenance=(
            _study_provenance("rule-study-001"),
            _study_provenance("rule-study-002"),
        ),
    )
    assert context.executable is False
    assert context.conflicts[0].resolution is None


def test_study_rule_without_decision_provenance_is_rejected(tmp_path: Path) -> None:
    manifest, _, _ = _project_with_locks(tmp_path)

    with pytest.raises(ContextResolutionError, match="provenance"):
        _resolver(_OfflineTransport()).resolve(
            project_dir=tmp_path,
            manifest=manifest,
            stage="sdtm_spec",
            study_rules=(_study_rule("rule-study-001", "Use coding convention A."),),
        )


def test_snapshot_path_escape_and_bad_remote_control_field_fail_closed(tmp_path: Path) -> None:
    manifest, _, _ = _project_with_locks(tmp_path)
    unsafe = manifest.model_copy(
        update={"workflow_knowledge": manifest.workflow_knowledge.model_copy(update={"fallback_path": "../escape.json"})}
    )
    with pytest.raises(ContextResolutionError, match="snapshot"):
        _resolver(_OfflineTransport()).resolve(project_dir=tmp_path, manifest=unsafe, stage="sdtm_spec")

    workflow = load_locked_snapshot(tmp_path, manifest.workflow_knowledge, expected_bundle_version=BUNDLE["bundle_version"], expected_bundle_sha256=BUNDLE["bundle_sha256"])
    domain = load_locked_snapshot(tmp_path, manifest.domain_knowledge, expected_bundle_version=BUNDLE["bundle_version"], expected_bundle_sha256=BUNDLE["bundle_sha256"])
    raw = context_from_snapshots(manifest=manifest, stage="sdtm_spec", workflow_snapshot=workflow, domain_snapshot=domain).model_dump(mode="json")
    raw["command"] = "skip-stage"
    with pytest.raises(ContextResolutionError, match="control"):
        _resolver(_StaticTransport(raw)).resolve(project_dir=tmp_path, manifest=manifest, stage="sdtm_spec")


def test_runtime_context_bridge_uses_config_manifest_loader(tmp_path: Path) -> None:
    manifest, _, _ = _project_with_locks(tmp_path)
    (tmp_path / "runtime-manifest.yaml").write_text(yaml.safe_dump(manifest.model_dump(mode="json")), encoding="utf-8")
    bridge = RuntimeContextResolver(_resolver(_OfflineTransport()))
    assert bridge.resolve_for_stage(tmp_path, "sdtm_spec").study_id == "STUDY-001"
    with pytest.raises(RuntimeContextError):
        bridge.resolve_for_stage(tmp_path, "sdtm_spec", manifest_name="../runtime-manifest.yaml")


def test_agent_runtime_denies_unknown_tool_before_invoking_registry(tmp_path: Path) -> None:
    # The action is intentionally constructed outside the normal decision path
    # to model an injected Agent proposal. It must not reach the tool registry.
    called = False

    def hostile_tool(**_: Any) -> None:
        nonlocal called
        called = True

    runtime = AgentRuntime(project_dir=tmp_path, git_auto_commit=False)
    runtime.register_tools({"hostile_tool": hostile_tool})
    result = asyncio.run(
        runtime._execute_action(
            AgentAction(
                action_type="call_tool", description="Injected action", tool_name="hostile_tool",
                stage_id=PipelineStage.SDTM_SPEC, capability="sdtm_spec_generation",
            )
        )
    )
    assert result["status"] == "denied"
    assert called is False


def test_runtime_writes_manifest_locked_provenance_for_declared_artifact(tmp_path: Path) -> None:
    manifest, _, _ = _project_with_locks(tmp_path)
    (tmp_path / "runtime-manifest.yaml").write_text(
        yaml.safe_dump(manifest.model_dump(mode="json")), encoding="utf-8"
    )
    context = _resolver(_OfflineTransport()).resolve(
        project_dir=tmp_path, manifest=manifest, stage="sdtm_spec"
    )
    artifact = tmp_path / "output" / "sdtm" / "ae-spec.yaml"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("dataset: AE\n", encoding="utf-8")
    runtime = AgentRuntime(project_dir=tmp_path, git_auto_commit=False)
    runtime.execution_context = context
    runtime.state.iteration = 1
    action = AgentAction(
        action_type="call_tool",
        description="Build AE specification",
        tool_name="sdtm_spec_build",
        stage_id=PipelineStage.SDTM_SPEC,
        capability="sdtm_spec_generation",
        context_bundle_id=context.bundle_id,
        context_sha256=context.execution_context_sha256,
    )

    runtime._record_action(
        action,
        {"status": "success", "tool_result": {"artifact_paths": ["output/sdtm/ae-spec.yaml"]}},
    )

    sidecar = artifact.with_name("ae-spec.yaml.provenance.json")
    record = json.loads(sidecar.read_text(encoding="utf-8"))
    assert record["artifact_sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert record["pipeline_contract"] == manifest.pipeline_contract.model_dump(mode="json")
    assert {item["source_kind"] for item in record["knowledge_provenance"]} == {
        "workflow_knowledge", "domain_knowledge"
    }
    assert record["toolchain"]["registry_sha256"] == manifest.toolchain.registry_sha256
    assert record["context_sha256"] == context.execution_context_sha256


def test_artifact_provenance_rejects_path_escape(tmp_path: Path) -> None:
    manifest, _, _ = _project_with_locks(tmp_path)
    (tmp_path / "runtime-manifest.yaml").write_text(
        yaml.safe_dump(manifest.model_dump(mode="json")), encoding="utf-8"
    )
    context = _resolver(_OfflineTransport()).resolve(
        project_dir=tmp_path, manifest=manifest, stage="sdtm_spec"
    )
    outside = tmp_path.parent / "outside-artifact.txt"
    outside.write_text("outside", encoding="utf-8")
    runtime = AgentRuntime(project_dir=tmp_path, git_auto_commit=False)
    runtime.execution_context = context
    action = AgentAction(
        action_type="call_tool", description="Injected artifact", tool_name="sdtm_spec_build",
        stage_id=PipelineStage.SDTM_SPEC, capability="sdtm_spec_generation",
    )
    with pytest.raises(RuntimeContextError, match="inside the Study"):
        runtime._record_action(
            action, {"status": "success", "artifact_paths": [str(outside)]}
        )
