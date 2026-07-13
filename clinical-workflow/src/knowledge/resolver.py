"""Resolve governed knowledge into a single Engine-owned ExecutionContext."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from pydantic import ValidationError

from src.runtime.pipeline_contract import CONTRACT_VERSION, CANONICAL_PIPELINE, PipelineStage

from .client import (
    KnowledgeServiceClient,
    KnowledgeServiceContractError,
    KnowledgeServiceUnavailable,
)
from .compatibility import sha256_canonical_json
from .models import (
    ContextConflict,
    ExecutionContext,
    ProvenanceEntry,
    ResolvedRule,
    RuleLayer,
    RuntimeManifest,
)
from .snapshot import SnapshotError, context_from_snapshots, load_locked_snapshot


class ContextResolutionError(RuntimeError):
    """The Engine cannot prove a usable context for this fixed pipeline stage."""


class KnowledgeContextResolver:
    """Online-first resolver with an exact, immutable Study snapshot fallback.

    Only connectivity failures are eligible for snapshot fallback.  A reachable
    service that returns a wrong bundle, bad schema, or hostile data blocks the
    run instead of being silently hidden by an older snapshot.
    """

    def __init__(
        self,
        client: KnowledgeServiceClient,
        *,
        bundle_version: str,
        bundle_sha256: str,
        require_domain: bool = False,
    ) -> None:
        self.client = client
        self.bundle_version = bundle_version
        self.bundle_sha256 = bundle_sha256
        self.require_domain = require_domain

    def resolve(
        self,
        *,
        project_dir: str | Path,
        manifest: RuntimeManifest | Mapping[str, Any],
        stage: PipelineStage | str,
        study_rules: Iterable[ResolvedRule | Mapping[str, Any]] = (),
        study_provenance: Iterable[ProvenanceEntry | Mapping[str, Any]] = (),
    ) -> ExecutionContext:
        active_manifest = _manifest(manifest)
        active_stage = _stage(stage)
        _validate_manifest_locks(active_manifest, self.bundle_version, self.bundle_sha256)
        normalized_study_rules = tuple(_study_rule(rule) for rule in study_rules)
        normalized_study_provenance = tuple(
            _study_provenance(item) for item in study_provenance
        )
        _validate_study_evidence(normalized_study_rules, normalized_study_provenance)
        try:
            raw = self.client.resolve_runtime_context(
                study_id=active_manifest.study_id,
                stage=active_stage.value,
                runtime_manifest=active_manifest.model_dump(mode="json"),
                require_workflow=True,
                require_domain=self.require_domain,
            )
        except KnowledgeServiceUnavailable:
            return self._resolve_from_snapshot(
                Path(project_dir), active_manifest, active_stage,
                normalized_study_rules, normalized_study_provenance,
            )
        except KnowledgeServiceContractError as exc:
            raise ContextResolutionError("online Knowledge Service contract cannot be trusted") from exc
        return _validate_online_context(
            raw,
            manifest=active_manifest,
            stage=active_stage,
            bundle_version=self.bundle_version,
            study_rules=normalized_study_rules,
            study_provenance=normalized_study_provenance,
        )

    def _resolve_from_snapshot(
        self,
        project_dir: Path,
        manifest: RuntimeManifest,
        stage: PipelineStage,
        study_rules: tuple[ResolvedRule, ...],
        study_provenance: tuple[ProvenanceEntry, ...],
    ) -> ExecutionContext:
        try:
            workflow = load_locked_snapshot(
                project_dir,
                manifest.workflow_knowledge,
                expected_bundle_version=self.bundle_version,
                expected_bundle_sha256=self.bundle_sha256,
            )
            domain = load_locked_snapshot(
                project_dir,
                manifest.domain_knowledge,
                expected_bundle_version=self.bundle_version,
                expected_bundle_sha256=self.bundle_sha256,
            )
            context = context_from_snapshots(
                manifest=manifest,
                stage=stage.value,
                workflow_snapshot=workflow,
                domain_snapshot=domain,
            )
        except (SnapshotError, ValidationError, ValueError) as exc:
            raise ContextResolutionError("Knowledge Service unavailable and locked snapshot is invalid") from exc
        return _merge_study_rules(context, study_rules, study_provenance)


def _manifest(value: RuntimeManifest | Mapping[str, Any]) -> RuntimeManifest:
    try:
        return value if isinstance(value, RuntimeManifest) else RuntimeManifest.model_validate(value)
    except ValidationError as exc:
        raise ContextResolutionError("runtime manifest is invalid") from exc


def _stage(value: PipelineStage | str) -> PipelineStage:
    try:
        stage = PipelineStage(value)
    except ValueError as exc:
        raise ContextResolutionError("unknown fixed pipeline stage") from exc
    # Canonical contract, not Wiki content, is the source of stage authority.
    CANONICAL_PIPELINE.get_stage(stage)
    return stage


def _validate_manifest_locks(
    manifest: RuntimeManifest, bundle_version: str, bundle_sha256: str
) -> None:
    if manifest.schema_version != bundle_version:
        raise ContextResolutionError("runtime manifest schema version differs from Engine bundle")
    if manifest.pipeline_contract.version != CONTRACT_VERSION:
        raise ContextResolutionError("runtime manifest does not lock the active Pipeline Contract version")
    for lock in (manifest.workflow_knowledge, manifest.domain_knowledge):
        if lock.contract_compatibility.minimum > bundle_version or (
            lock.contract_compatibility.maximum_exclusive <= bundle_version
        ):
            raise ContextResolutionError("knowledge snapshot compatibility range excludes Engine bundle")
    if len(bundle_sha256) != 64:
        raise ContextResolutionError("Engine Schema bundle hash is malformed")


def _validate_online_context(
    raw: Mapping[str, Any],
    *,
    manifest: RuntimeManifest,
    stage: PipelineStage,
    bundle_version: str,
    study_rules: tuple[ResolvedRule, ...],
    study_provenance: tuple[ProvenanceEntry, ...],
) -> ExecutionContext:
    _reject_control_fields(raw)
    try:
        context = ExecutionContext.model_validate(raw)
    except ValidationError as exc:
        raise ContextResolutionError("Knowledge Service response fails ExecutionContext schema") from exc
    if (
        context.schema_version != bundle_version
        or context.study_id != manifest.study_id
        or context.stage != stage
        or context.manifest_id != manifest.manifest_id
        or context.manifest_sha256 != manifest.manifest_sha256
        or context.pipeline_contract != manifest.pipeline_contract
    ):
        raise ContextResolutionError("online context differs from the locked Study manifest")
    expected_hash = _context_hash(context)
    if context.execution_context_sha256 != expected_hash:
        raise ContextResolutionError("online context content hash is invalid")
    _validate_online_snapshot_provenance(context, manifest)
    return _merge_study_rules(context, study_rules, study_provenance)


def _validate_online_snapshot_provenance(
    context: ExecutionContext,
    manifest: RuntimeManifest,
) -> None:
    expected = {
        "workflow_knowledge": manifest.workflow_knowledge.snapshot_id,
        "domain_knowledge": manifest.domain_knowledge.snapshot_id,
    }
    observed = {source_kind: 0 for source_kind in expected}
    for entry in context.provenance:
        if entry.source_kind not in expected:
            continue
        if entry.snapshot_id != expected[entry.source_kind]:
            raise ContextResolutionError(
                "online knowledge provenance differs from the manifest-locked snapshot"
            )
        observed[entry.source_kind] += 1
    if context.workflow_rules and observed["workflow_knowledge"] == 0:
        raise ContextResolutionError(
            "online workflow rules lack manifest-locked snapshot provenance"
        )
    if context.domain_rules and observed["domain_knowledge"] == 0:
        raise ContextResolutionError(
            "online domain rules lack manifest-locked snapshot provenance"
        )


def _merge_study_rules(
    context: ExecutionContext,
    study_rules: tuple[ResolvedRule, ...],
    study_provenance: tuple[ProvenanceEntry, ...],
) -> ExecutionContext:
    if not study_rules and not study_provenance:
        return context
    existing = tuple(context.study_rules) + study_rules
    conflicts = list(context.conflicts)
    by_priority: dict[int, list[ResolvedRule]] = {}
    for rule in existing:
        by_priority.setdefault(rule.priority, []).append(rule)
    for priority, rules in by_priority.items():
        statements = {rule.statement for rule in rules}
        if len(rules) > 1 and len(statements) > 1:
            conflicts.append(
                ContextConflict(
                    conflict_id=f"conflict-study-priority-{priority}",
                    rule_ids=tuple(rule.rule_id for rule in rules),
                    reason="Study rules with equal priority disagree and require human review.",
                    resolution=None,
                )
            )
    payload = context.model_dump(mode="json")
    payload["study_rules"] = [rule.model_dump(mode="json") for rule in existing]
    payload["provenance"] = [
        item.model_dump(mode="json")
        for item in (*context.provenance, *study_provenance)
    ]
    payload["conflicts"] = [conflict.model_dump(mode="json") for conflict in conflicts]
    payload["executable"] = not any(conflict.resolution is None for conflict in conflicts) and not any(
        item.blocking for item in context.missing_requirements
    )
    payload["execution_context_sha256"] = sha256_canonical_json(
        {key: value for key, value in payload.items() if key != "execution_context_sha256"}
    )
    return ExecutionContext.model_validate(payload)


def _study_rule(value: ResolvedRule | Mapping[str, Any]) -> ResolvedRule:
    try:
        rule = value if isinstance(value, ResolvedRule) else ResolvedRule.model_validate(value)
    except ValidationError as exc:
        raise ContextResolutionError("Study rule does not conform to the governed rule contract") from exc
    if rule.layer is not RuleLayer.STUDY:
        raise ContextResolutionError("only current-Study rules may be merged as Study overrides")
    return rule


def _study_provenance(
    value: ProvenanceEntry | Mapping[str, Any],
) -> ProvenanceEntry:
    try:
        entry = (
            value
            if isinstance(value, ProvenanceEntry)
            else ProvenanceEntry.model_validate(value)
        )
    except ValidationError as exc:
        raise ContextResolutionError(
            "Study provenance does not conform to the governed provenance contract"
        ) from exc
    if entry.source_kind != "study_decision" or entry.snapshot_id is not None:
        raise ContextResolutionError(
            "Study provenance must identify a current-Study decision without a snapshot"
        )
    return entry


def _validate_study_evidence(
    rules: tuple[ResolvedRule, ...],
    provenance: tuple[ProvenanceEntry, ...],
) -> None:
    if bool(rules) != bool(provenance) or len(rules) != len(provenance):
        raise ContextResolutionError(
            "every Study rule requires exactly one approved Study decision provenance entry"
        )
    remaining = list(provenance)
    for rule in rules:
        matches = [
            entry for entry in remaining
            if entry.object_id in rule.source_ids
            and entry.object_sha256 == rule.source_sha256
        ]
        if len(matches) != 1:
            raise ContextResolutionError(
                f"Study rule {rule.rule_id} is not bound to exactly one decision provenance entry"
            )
        remaining.remove(matches[0])


def _context_hash(context: ExecutionContext) -> str:
    payload = context.model_dump(mode="json")
    payload.pop("execution_context_sha256", None)
    return sha256_canonical_json(payload)


def _reject_control_fields(value: Mapping[str, Any]) -> None:
    forbidden = {"command", "commands", "next_stage", "stage_override", "capabilities", "tool_calls"}

    def visit(item: Any) -> bool:
        if isinstance(item, Mapping):
            if forbidden.intersection(item):
                return True
            return any(visit(child) for child in item.values())
        if isinstance(item, list):
            return any(visit(child) for child in item)
        return False

    if visit(value):
        raise ContextResolutionError("Knowledge Service response contains execution-control fields")
