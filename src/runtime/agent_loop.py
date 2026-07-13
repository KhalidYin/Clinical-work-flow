"""
Agent Runtime v3.0 — fixed pipeline with dynamic review strategy.

Replaces the old in-memory 12-stage state machine with a runtime that
derives progress from the file system and advances through the fixed
clinical dependency order.

Core loop:
  1. ASSESS  — read project state from file system
  2. DECIDE  — choose next fixed-pipeline action from file state
  3. EXECUTE — call MCP tools or submit review packet
  4. REVIEW  — if human input needed, wait for decision receipt
  5. RECORD  — git commit + audit trail
  6. REPEAT  — until done or blocked

Design principles:
  - File system IS the state — no in-memory pipeline state
  - Fixed clinical ordering; dynamic behavior is review, knowledge loading, and recovery
  - Human interaction via ReviewQueue protocol — no chat
  - Every action recorded in audit trail
  - Git as version control backbone
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.config import load_runtime_manifest
from src.config.project import ProjectConfig, load_project_config, resolve_project_path

from .decision_application import DecisionApplicationError, apply_decision_receipt
from .action_policy import DEFAULT_ACTION_POLICY, ActionRequest, ActionPolicyError, require_authorized_action
from .context_resolver import RuntimeContextError, RuntimeContextResolver
from .pipeline_contract import CONTRACT_VERSION, CapabilityName, ExecutableName, PipelineStage, ToolName
from .router import Router, RoutingError
from .review_protocol import (
    ReviewPacket, ReviewFinding, DecisionReceipt,
    ReviewQueue, FindingCategory, Severity,
    Urgency, ReviewType,
    OUTPUT_FORMAT_SPECS,
    new_review_packet, make_finding_id,
)

# Reuse existing agent infrastructure
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.agents.base import (
    BaseAgent, AgentConfig, AgentContext,
    AgentRole,
)
from src.agents.executors import (
    ProtocolSAPAgent, DataStandardsAgent, TFLQCSubmissionAgent,
)

logger = logging.getLogger(__name__)


def _artifact_paths(result: dict[str, Any]) -> tuple[str, ...]:
    """Extract the explicit artifact path contract from a tool result."""
    values: Any = result.get("artifact_paths")
    tool_result = result.get("tool_result")
    if values is None and isinstance(tool_result, dict):
        values = tool_result.get("artifact_paths")
    if values is None:
        return ()
    if not isinstance(values, list) or not all(isinstance(item, str) and item for item in values):
        raise RuntimeContextError("artifact_paths must be a list of non-empty paths")
    return tuple(values)


# ═══════════════════════════════════════════════════════════════════
# Agent Loop State — persisted to file system
# ═══════════════════════════════════════════════════════════════════


@dataclass
class LoopState:
    """
    The agent loop's view of the project.

    This is reconstructed from the file system on every iteration —
    no in-memory pipeline state that can drift from reality.
    """
    project_dir: Path
    study_id: str = ""
    trial_phase: str = "phase_iii"
    therapeutic_area: str = "non_oncology"

    # What's been done (discovered from file system)
    completed_actions: list[dict[str, Any]] = field(default_factory=list)
    current_action: dict[str, Any] | None = None

    # Review queue state
    pending_reviews: list[str] = field(default_factory=list)
    blocking_review: str | None = None

    # Audit
    change_log: list[dict[str, Any]] = field(default_factory=list)
    iteration: int = 0

    def snapshot(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "trial_phase": self.trial_phase,
            "therapeutic_area": self.therapeutic_area,
            "iteration": self.iteration,
            "completed_actions_count": len(self.completed_actions),
            "pending_reviews": self.pending_reviews,
            "blocking_review": self.blocking_review,
            "changes_tracked": len(self.change_log),
            "snapshot_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def from_project(
        cls,
        project_dir: str | Path,
        queue_dir: str | Path | None = None,
    ) -> "LoopState":
        """Reconstruct state from what's on disk."""
        pd = Path(project_dir)
        queue = ReviewQueue(pd, queue_dir=queue_dir)
        stats = queue.queue_stats()
        return cls(
            project_dir=pd,
            pending_reviews=stats["pending_reviews"],
            blocking_review=(
                stats["pending_reviews"][0] if stats["blocking_present"] else None
            ),
        )


# ═══════════════════════════════════════════════════════════════════
# Action Types — what the agent can decide to do
# ═══════════════════════════════════════════════════════════════════


@dataclass
class AgentAction:
    """One atomic action the agent decides to take."""
    action_type: str  # "call_tool" | "submit_review" | "wait" | "done"
    description: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    stage_id: PipelineStage | None = None
    capability: CapabilityName | None = None
    executable_name: ExecutableName | None = None
    context_bundle_id: str | None = None
    context_sha256: str | None = None
    review_packet: ReviewPacket | None = None
    executor: str | None = None  # which capability domain

    def to_log(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "description": self.description,
            "tool_name": self.tool_name,
            "executable_name": self.executable_name,
            "stage_id": self.stage_id,
            "capability": self.capability,
            "context_bundle_id": self.context_bundle_id,
            "context_sha256": self.context_sha256,
            "executor": self.executor,
            "review_id": self.review_packet.review_id if self.review_packet else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════
# Agent Runtime — the core loop
# ═══════════════════════════════════════════════════════════════════


@dataclass
class AgentRuntime:
    """
    v3.0 Agent Runtime.

    Replaces Orchestrator (v2.1). Instead of a persisted 12-stage state
    machine, the runtime infers the next fixed-pipeline stage from files.

    Usage:
        runtime = AgentRuntime(project_dir="./project")
        runtime.register_tools(mcp_tool_registry)
        await runtime.run("Generate SDTM specs for Phase III NSCLC trial")
    """

    project_dir: Path
    study_id: str = ""
    trial_phase: str = "phase_iii"
    therapeutic_area: str = "non_oncology"

    # Capability domains (executor agents from v2.1, repurposed)
    executors: dict[str, BaseAgent] = field(default_factory=dict)

    # MCP tool registry — deterministic operations
    tool_registry: dict[str, Callable] = field(default_factory=dict)

    # Review protocol
    review_queue: ReviewQueue | None = None

    # Runtime state
    state: LoopState | None = None
    audit_log_path: Path | None = None
    context_resolver: RuntimeContextResolver | None = None
    execution_context: Any | None = field(default=None, init=False)
    router: Router = field(default_factory=Router, init=False)

    # Settings
    auto_execute: bool = True
    require_review_for_critical: bool = True
    git_auto_commit: bool = True
    max_iterations: int = 100
    project_config: ProjectConfig | None = field(default=None, init=False)
    input_dir: Path | None = field(default=None, init=False)
    output_dir: Path | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if isinstance(self.project_dir, str):
            self.project_dir = Path(self.project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)

        self.project_config = load_project_config(self.project_dir, required=False)
        if self.project_config:
            self.study_id = self.project_config.study_id
            self.trial_phase = self.project_config.trial_phase
            self.therapeutic_area = self.project_config.therapeutic_area
            self.input_dir = resolve_project_path(
                self.project_dir, self.project_config.paths.input_dir
            )
            self.output_dir = resolve_project_path(
                self.project_dir, self.project_config.paths.output_dir
            )
            review_queue_dir = self.project_config.paths.review_queue_dir
            self.audit_log_path = resolve_project_path(
                self.project_dir, self.project_config.paths.audit_log
            )
        else:
            self.input_dir = self.project_dir / "input"
            self.output_dir = self.project_dir / "output"
            review_queue_dir = ".review_queue"
            self.audit_log_path = self.project_dir / "audit_trail.jsonl"

        self.review_queue = ReviewQueue(self.project_dir, queue_dir=review_queue_dir)
        self.state = LoopState.from_project(self.project_dir, queue_dir=review_queue_dir)
        self.state.study_id = self.study_id
        self.state.trial_phase = self.trial_phase
        self.state.therapeutic_area = self.therapeutic_area

        # Initialize executor capability domains
        context = AgentContext(
            study_id=self.study_id,
            tool_registry=self.tool_registry,
        )
        self.executors = {
            "ProtocolSAPAgent": ProtocolSAPAgent(
                AgentConfig(name="ProtocolSAPAgent", role=AgentRole.MAIN,
                            model="claude-opus-4-7"),
                context,
            ),
            "DataStandardsAgent": DataStandardsAgent(
                AgentConfig(name="DataStandardsAgent", role=AgentRole.MAIN,
                            model="claude-opus-4-7"),
                context,
            ),
            "TFLQCSubmissionAgent": TFLQCSubmissionAgent(
                AgentConfig(name="TFLQCSubmissionAgent", role=AgentRole.MAIN,
                            model="claude-opus-4-7"),
                context,
            ),
        }

    # ── Main Loop ──────────────────────────────────────────────

    async def run(self, intent: str) -> dict[str, Any]:
        """
        Execute the agent loop until done or blocked.

        The runtime follows the fixed clinical dependency pipeline and
        dynamically decides whether review is needed.
        """
        logger.info(f"AgentRuntime starting: intent='{intent[:80]}...'")
        self.state.iteration = 0

        while self.state.iteration < self.max_iterations:
            self.state.iteration += 1
            logger.info(f"--- Iteration {self.state.iteration} ---")

            # 1. ASSESS — what's the current state?
            context = self._assess_context(intent)

            # 2. CHECK BLOCKERS — anything preventing progress?
            blocker = self._check_blockers()
            if blocker:
                logger.info(f"Blocked: {blocker}")
                return {"status": "blocked", "reason": blocker,
                        "iteration": self.state.iteration}

            # 3. DECIDE — what should we do next?
            action = await self._decide_next_action(intent, context)

            # The Engine chooses a fixed Stage before it resolves any knowledge.
            # A Wiki can explain that Stage but cannot control the pipeline.
            try:
                self._bind_governed_context(action)
            except RuntimeContextError as exc:
                return {
                    "status": "blocked",
                    "reason": f"governed runtime context unavailable: {exc}",
                    "iteration": self.state.iteration,
                }

            # 4. EXECUTE — do it
            result = await self._execute_action(action)

            # 5. RECORD — audit trail + git
            self._record_action(action, result)

            # 6. CHECK DONE
            if action.action_type == "done":
                logger.info("Agent signaled done")
                return {"status": "complete",
                        "iterations": self.state.iteration,
                        "actions": len(self.state.completed_actions),
                        "state": self.state.snapshot()}

            # 7. CHECK PENDING REVIEWS
            if self.state.blocking_review:
                decision = await self._handle_pending_review()
                if decision:
                    self._apply_decisions(decision)
                    self.state.blocking_review = None

        return {"status": "max_iterations_reached",
                "iterations": self.state.iteration}

    # ── Context Assessment ─────────────────────────────────────

    def _assess_context(self, intent: str) -> dict[str, Any]:
        """
        Build a context snapshot from the file system.

        This is what the agent "sees" when deciding what to do next.
        """
        context: dict[str, Any] = {
            "intent": intent,
            "study_id": self.study_id,
            "trial_phase": self.trial_phase,
            "therapeutic_area": self.therapeutic_area,
            "iteration": self.state.iteration,
            "project_config": (
                self.project_config.to_runtime_context() if self.project_config else None
            ),

            # What exists on disk?
            "files": self._scan_pipeline_evidence(),

            # What reviews are pending?
            "pending_reviews": self.state.pending_reviews,
            "blocking_review": self.state.blocking_review,

            # What actions have been done?
            "completed_actions": [
                a.get("description", "") for a in self.state.completed_actions[-10:]
            ],

            # Available tools
            "available_tools": list(self.tool_registry.keys()),

            # Output format requirements — every document must conform
            "output_format_specs": OUTPUT_FORMAT_SPECS,
        }
        return context

    def _scan_pipeline_evidence(self) -> dict[str, list[Path]]:
        """Collect only canonical contract evidence, with narrow legacy fallback."""
        output = self.output_dir or self.project_dir / "output"
        input_root = self.input_dir or self.project_dir / "input"
        protocol_dir = input_root / "protocol"
        protocol = (
            sorted(path for path in protocol_dir.rglob("*") if path.is_file())
            if protocol_dir.exists()
            else []
        )
        if not protocol:  # migration-only compatibility; never search arbitrary parent paths
            protocol = sorted(path for path in self.project_dir.glob("protocol*") if path.is_file())
        return {
            "protocol": protocol,
            "protocol_analysis": self._collect_exact(output / "protocol" / "analysis.yaml"),
            "sap": self._collect_exact(output / "sap" / "sap.yaml"),
            "sdtm_specs": self._collect_output_files(("sdtm", "specs"), ("sdtm_specs",)),
            "sdtm_programs": self._collect_output_files(("sdtm", "programs"), ()),
            "sdtm_datasets": self._collect_output_files(("sdtm", "datasets"), ()),
            "adam_specs": self._collect_output_files(("adam", "specs"), ("adam_specs",)),
            "adam_programs": self._collect_output_files(("adam", "programs"), ()),
            "adam_datasets": self._collect_output_files(("adam", "datasets"), ()),
            "tfl_shells": self._collect_output_files(("tfl", "shells"), ("tfl_shells",)),
            "tfl_programs": self._collect_output_files(("tfl", "programs"), ()),
            "tfl_outputs": self._collect_output_files(("tfl", "outputs"), ()),
            "qc_report": self._collect_exact(output / "qc" / "qc_report.yaml"),
            "submission_manifest": self._collect_exact(output / "submission" / "manifest.yaml"),
            "submission_package": self._collect_output_files(("submission", "package"), ()),
        }

    @staticmethod
    def _collect_exact(path: Path) -> list[Path]:
        return [path] if path.is_file() else []

    def _collect_output_files(self, canonical_parts: tuple[str, ...],
                              legacy_parts: tuple[str, ...]) -> list[Path]:
        """Read canonical output/ paths and legacy outputs/ paths during migration."""
        files: list[Path] = []
        roots = [(self.output_dir or self.project_dir / "output", canonical_parts)]
        if legacy_parts:
            roots.append((self.project_dir / "outputs", legacy_parts))
        for root, parts in roots:
            path = root.joinpath(*parts)
            if path.exists():
                files.extend(sorted(path.glob("*")))
        return files

    # ── Blocker Detection ──────────────────────────────────────

    def _check_blockers(self) -> str | None:
        """Check for conditions that prevent progress."""
        # Blocking review awaiting human
        if self.state.blocking_review:
            return f"Blocking review pending: {self.state.blocking_review}"

        # Check for unrecoverable errors in previous actions
        for action in self.state.completed_actions[-5:]:
            if action.get("status") == "error_unrecoverable":
                return f"Unrecoverable error: {action.get('error', 'unknown')}"

        return None

    # ── Decision Engine ────────────────────────────────────────

    async def _decide_next_action(self, intent: str,
                                  context: dict[str, Any]) -> AgentAction:
        """Choose only the Router's first incomplete contract stage."""
        try:
            route = self.router.best_route(intent, context)
        except RoutingError as exc:
            return AgentAction(action_type="wait", description=f"Unsafe routing context: {exc}")
        if route is None or route.capability == "done":
            return AgentAction(action_type="done", description="All ten pipeline stages are complete.")
        if not route.prerequisites_met:
            return AgentAction(
                action_type="wait",
                description=(
                    f"{route.stage_id.value if route.stage_id else 'Pipeline'} requires: "
                    + ", ".join(route.missing_prerequisites)
                ),
                stage_id=route.stage_id,
            )
        return self._action_for_route(route, intent)

    def _action_for_route(self, route: Any, intent: str) -> AgentAction:
        """Bind a fixed-stage route to one registered, policy-controlled resource."""
        if route.stage_id is None:
            return AgentAction(action_type="wait", description="Router did not return a pipeline stage.")
        stage = route.stage_id
        tool_args = self._route_arguments(stage, intent)
        for tool in route.suggested_tools:
            if tool in self.tool_registry:
                registration = DEFAULT_ACTION_POLICY.tool(ToolName(tool))
                return AgentAction(
                    action_type="call_tool", description=f"Execute {stage.value}", tool_name=tool,
                    tool_args=tool_args, stage_id=stage, capability=registration.capability,
                    executor=route.executor,
                )
        for executable in route.suggested_executables:
            if executable in self.tool_registry:
                registration = DEFAULT_ACTION_POLICY.executable(ExecutableName(executable))
                return AgentAction(
                    action_type="call_tool", description=f"Execute {stage.value}",
                    executable_name=ExecutableName(executable), tool_args=tool_args,
                    stage_id=stage, capability=registration.capability, executor=route.executor,
                )
        return AgentAction(
            action_type="wait",
            description=f"No registered controlled resource is available for fixed stage {stage.value}.",
            stage_id=stage,
            capability=CapabilityName(route.capability),
            executor=route.executor,
        )

    def _route_arguments(self, stage: PipelineStage, intent: str) -> dict[str, Any]:
        if stage is PipelineStage.SDTM_SPEC:
            return {"domain_codes": self._infer_domains(intent), "trial_phase": self.trial_phase,
                    "therapeutic_area": self.therapeutic_area}
        if stage is PipelineStage.ADAM_SPEC:
            return {"datasets": self._infer_adam_datasets(intent), "trial_phase": self.trial_phase,
                    "therapeutic_area": self.therapeutic_area}
        if stage is PipelineStage.TFL_SHELL_DESIGN:
            return {"trial_phase": self.trial_phase, "therapeutic_area": self.therapeutic_area}
        return {}

    # ── Action Execution ───────────────────────────────────────

    async def _execute_action(self, action: AgentAction) -> dict[str, Any]:
        """Execute a single action."""
        result: dict[str, Any] = {
            "action": action.to_log(),
            "status": "executed",
        }

        if action.action_type == "call_tool":
            try:
                self._authorize_action(action)
            except (ActionPolicyError, ValueError) as exc:
                result.update({"status": "denied", "error": str(exc)})
            else:
                resource_name = action.tool_name or action.executable_name
                if resource_name is None:
                    result.update({"status": "denied", "error": "action has no controlled resource"})
                else:
                    result.update(self._call_tool(str(resource_name), action.tool_args or {}))

        elif action.action_type == "submit_review" and action.review_packet:
            filepath = self.review_queue.submit_packet(action.review_packet)
            result["review_id"] = action.review_packet.review_id
            result["review_file"] = str(filepath)

            if action.review_packet.urgency == Urgency.BLOCKING:
                self.state.blocking_review = action.review_packet.review_id
                self.state.pending_reviews.append(action.review_packet.review_id)
                result["blocking"] = True
                result["status"] = "awaiting_human"

        elif action.action_type == "wait":
            result["status"] = "waiting"
            result["reason"] = action.description

        elif action.action_type == "done":
            result["status"] = "complete"

        self.state.completed_actions.append(result)
        self.state.current_action = result
        return result

    # ── Tool Calling ───────────────────────────────────────────

    def _bind_governed_context(self, action: AgentAction) -> None:
        """Resolve a manifest-locked context only after Engine Stage selection."""
        if self.context_resolver is None or action.action_type != "call_tool":
            return
        if action.stage_id is None:
            raise RuntimeContextError("runtime action lacks a fixed pipeline stage")
        context = self.context_resolver.resolve_for_stage(self.project_dir, action.stage_id)
        if not context.executable:
            raise RuntimeContextError("resolved execution context is not executable")
        self.execution_context = context
        action.context_bundle_id = context.bundle_id
        action.context_sha256 = context.execution_context_sha256

    @staticmethod
    def _authorize_action(action: AgentAction) -> None:
        if action.stage_id is None or action.capability is None:
            raise ActionPolicyError("runtime action must declare a fixed stage and capability")
        request = ActionRequest(
            contract_version=CONTRACT_VERSION,
            origin="runtime",
            stage_id=action.stage_id,
            capability=action.capability,
            tool_name=ToolName(action.tool_name) if action.tool_name else None,
            executable_name=(
                ExecutableName(action.executable_name) if action.executable_name else None
            ),
            arguments=action.tool_args or {},
        )
        require_authorized_action(request)

    def _call_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Call a registered MCP tool."""
        if tool_name not in self.tool_registry:
            return {"status": "error", "error": f"Tool '{tool_name}' not registered"}

        if tool_name == "sdtm_spec_build" and "domain_codes" in args:
            return self._call_tool_batch(tool_name, args, "domain_codes", "domain_code")

        if tool_name == "adam_spec_build" and "datasets" in args:
            return self._call_tool_batch(tool_name, args, "datasets", "dataset_name")

        try:
            tool_fn = self.tool_registry[tool_name]
            result = tool_fn(**args)
            return {"status": "success", "tool_result": result}
        except Exception as e:
            logger.exception(f"Tool '{tool_name}' failed")
            return {"status": "error", "error": str(e)}

    def _call_tool_batch(self, tool_name: str, args: dict[str, Any],
                         plural_key: str, singular_key: str) -> dict[str, Any]:
        """Expand a runtime batch request into deterministic single-tool calls."""
        values = args.get(plural_key, [])
        results: dict[str, Any] = {}
        errors: dict[str, str] = {}

        for value in values:
            single_args = {k: v for k, v in args.items() if k != plural_key}
            single_args[singular_key] = value
            single = self._call_tool(tool_name, single_args)
            if single.get("status") == "success":
                results[value] = single.get("tool_result")
            else:
                errors[value] = single.get("error", "unknown error")

        return {
            "status": "error" if errors else "success",
            "tool_result": results,
            "errors": errors,
        }

    # ── Review Handling ────────────────────────────────────────

    async def _handle_pending_review(self) -> DecisionReceipt | None:
        """Check for and process pending human review decisions."""
        if not self.state.blocking_review:
            return None

        # Poll for decision
        decision = self.review_queue.check_decision(self.state.blocking_review)
        if decision:
            logger.info(
                f"Decision received for {decision.review_id}: "
                f"{decision.approved_count()} approved, "
                f"{decision.rejected_count()} rejected, "
                f"{decision.modified_count()} modified"
            )
            return decision

        return None

    def _apply_decisions(self, receipt: DecisionReceipt) -> None:
        """Apply human decisions, write confirmation, then archive review files."""
        packet = self.review_queue.load_packet(receipt.review_id)
        if packet is None:
            logger.error("Cannot apply decisions; ReviewPacket not found: %s", receipt.review_id)
            self.state.change_log.append({
                "type": "human_decision_application_failed",
                "review_id": receipt.review_id,
                "error": "ReviewPacket not found",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return

        try:
            confirmation = apply_decision_receipt(
                project_dir=self.project_dir,
                review_queue_dir=self.review_queue.queue_dir,
                packet=packet,
                receipt=receipt,
                generated_by="AgentRuntime",
            )
        except DecisionApplicationError as exc:
            logger.error("Decision application failed for %s: %s", receipt.review_id, exc)
            self.state.change_log.append({
                "type": "human_decision_application_failed",
                "review_id": receipt.review_id,
                "error": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return

        for result in confirmation.results:
            logger.info(
                "  %s: %s",
                result.finding_id,
                result.application_status.value,
            )

        self.review_queue.archive_completed(receipt.review_id)

        # Record in change log
        self.state.change_log.append({
            "type": "human_decision",
            "review_id": receipt.review_id,
            "reviewer": receipt.reviewer,
            "summary": receipt.summary(),
            "application_summary": confirmation.summary(),
            "timestamp": receipt.timestamp,
        })

    # ── Review Packet Builders ─────────────────────────────────

    def _build_tfl_shell_review_packet(self,
                                       files: dict[str, Any]) -> ReviewPacket:
        """Build a review packet for TFL shell approval."""
        findings = []
        for i, shell_path in enumerate(files["tfl_shells"]):
            findings.append(ReviewFinding(
                id=make_finding_id(i),
                category=FindingCategory.FORMATTING,
                severity=Severity.WARNING,
                location=str(shell_path),
                title=f"TFL Shell: {shell_path.stem}",
                current_value="Generated shell",
                proposed_value="Review and approve shell specification",
                rationale="TFL shells must be reviewed before programming begins",
                evidence_refs=["SAP Section 14", "ICH E3"],
            ))

        return new_review_packet(
            review_type=ReviewType.TFL_SHELL,
            source_documents=[str(p) for p in files["tfl_shells"]],
            agent_summary=(
                f"Generated {len(files['tfl_shells'])} TFL shells based on "
                f"Phase {self.trial_phase} {self.therapeutic_area} configuration. "
                f"Please review all shells before programming begins."
            ),
            generated_by="TFLQCSubmissionAgent (claude-opus-4-7)",
            findings=findings,
            urgency=Urgency.BLOCKING,
            domain_or_dataset="tfl_shells",
        )

    # ── Domain Inference ───────────────────────────────────────

    def _infer_domains(self, intent: str) -> list[str]:
        """Infer which SDTM domains are needed from the intent."""
        intent_lower = intent.lower()

        domains = ["DM"]  # Always needed

        # Safety domains
        if any(kw in intent_lower for kw in ["ae", "adverse", "safety", "teae"]):
            domains.append("AE")
        if any(kw in intent_lower for kw in ["cm", "concomitant", "medication"]):
            domains.append("CM")

        # Lab/vitals
        if any(kw in intent_lower for kw in ["lb", "lab", "laboratory"]):
            domains.append("LB")
        if any(kw in intent_lower for kw in ["vs", "vital", "sign"]):
            domains.append("VS")

        # Exposure/dosing
        if any(kw in intent_lower for kw in ["ex", "exposure", "dose"]):
            domains.append("EX")

        # Disposition
        if any(kw in intent_lower for kw in ["ds", "disposition", "discon"]):
            domains.append("DS")

        # Medical history
        if any(kw in intent_lower for kw in ["mh", "history", "medical"]):
            domains.append("MH")

        # Oncology-specific
        if any(kw in intent_lower for kw in ["oncology", "tumor", "recist", "nsclc"]):
            domains.extend(["TU", "TR", "RS"])

        # ECG
        if any(kw in intent_lower for kw in ["eg", "ecg", "electrocardiogram"]):
            domains.append("EG")

        # Questionnaires
        if any(kw in intent_lower for kw in ["qs", "questionnaire", "qol"]):
            domains.append("QS")

        logger.info(f"Inferred domains from intent: {domains}")
        return domains

    def _infer_adam_datasets(self, intent: str) -> list[str]:
        """Infer which ADaM datasets are needed."""
        intent_lower = intent.lower()

        datasets = ["ADSL"]  # Always needed

        if any(kw in intent_lower for kw in ["ae", "adverse", "safety", "teae"]):
            datasets.append("ADAE")
        if any(kw in intent_lower for kw in ["tte", "survival", "os", "pfs", "km"]):
            datasets.append("ADTTE")
        if any(kw in intent_lower for kw in ["lb", "lab", "laboratory"]):
            datasets.append("ADLB")
        if any(kw in intent_lower for kw in ["vs", "vital"]):
            datasets.append("ADVS")
        if any(kw in intent_lower for kw in ["oncology", "tumor", "recist"]):
            datasets.append("ADTR")
        if any(kw in intent_lower for kw in ["cm", "medication"]):
            datasets.append("ADCM")

        logger.info(f"Inferred ADaM datasets from intent: {datasets}")
        return datasets

    # ── Audit & Recording ──────────────────────────────────────

    def _record_action(self, action: AgentAction,
                       result: dict[str, Any]) -> None:
        """Record action to audit trail and git."""
        provenance_files = self._write_artifact_provenance(action, result)
        # JSONL audit log
        log_entry = {
            **action.to_log(),
            "result_status": result.get("status", "unknown"),
            "artifact_provenance": provenance_files,
            "iteration": self.state.iteration,
        }
        if self.audit_log_path:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        # Git auto-commit
        if self.git_auto_commit:
            self._git_commit(action, result)

    def _write_artifact_provenance(
        self, action: AgentAction, result: dict[str, Any]
    ) -> list[str]:
        """Write immutable provenance sidecars for tool-declared output artifacts.

        Deterministic tools declare created files through ``artifact_paths`` in
        their result.  A declared path is a contract: it must be an existing
        Study-local file and it receives a sidecar before the action is audited.
        """
        candidates = _artifact_paths(result)
        if not candidates:
            return []
        if self.execution_context is None:
            raise RuntimeContextError(
                "artifact provenance requires a manifest-locked execution context"
            )
        manifest = load_runtime_manifest(self.project_dir, required=True)
        if manifest is None:  # pragma: no cover - required=True is the contract
            raise RuntimeContextError("artifact provenance requires runtime-manifest.yaml")

        root = self.project_dir.resolve()
        context = self.execution_context
        written: list[str] = []
        for candidate in candidates:
            artifact = (root / candidate).resolve() if not Path(candidate).is_absolute() else Path(candidate).resolve()
            try:
                relative = artifact.relative_to(root)
            except ValueError as exc:
                raise RuntimeContextError("artifact path must stay inside the Study") from exc
            if not artifact.is_file():
                raise RuntimeContextError(f"declared artifact does not exist: {relative.as_posix()}")

            knowledge = [
                item.model_dump(mode="json")
                for item in context.provenance
                if item.source_kind in {"workflow_knowledge", "domain_knowledge"}
            ]
            payload = {
                "artifact_path": relative.as_posix(),
                "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "stage": action.stage_id.value if action.stage_id else None,
                "capability": action.capability.value if hasattr(action.capability, "value") else action.capability,
                "resource": action.tool_name or action.executable_name,
                "pipeline_contract": context.pipeline_contract.model_dump(mode="json"),
                "knowledge_provenance": knowledge,
                "toolchain": manifest.toolchain.model_dump(mode="json"),
                "manifest_id": manifest.manifest_id,
                "manifest_sha256": manifest.manifest_sha256,
                "context_bundle_id": context.bundle_id,
                "context_sha256": context.execution_context_sha256,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            sidecar = artifact.with_name(f"{artifact.name}.provenance.json")
            sidecar.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            written.append(sidecar.relative_to(root).as_posix())
        return written

    def _git_commit(self, action: AgentAction,
                    result: dict[str, Any]) -> None:
        """Auto-commit changes to git."""
        try:
            repo_root = self._find_git_root()
            if not repo_root:
                return

            status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, cwd=str(repo_root),
            )
            if not status.stdout.strip():
                return  # Nothing to commit

            msg = (
                f"[agent] {action.description[:50]}\n\n"
                f"Action: {action.action_type}\n"
                f"Iteration: {self.state.iteration}\n"
                f"Review ID: {action.review_packet.review_id if action.review_packet else 'N/A'}"
            )
            subprocess.run(
                ["git", "add", "-A"],
                capture_output=True, cwd=str(repo_root),
            )
            subprocess.run(
                ["git", "commit", "-m", msg],
                capture_output=True, cwd=str(repo_root),
            )
            logger.info(f"Git commit: {msg.split(chr(10))[0]}")
        except Exception:
            logger.debug("Git commit skipped (not a git repo or git not available)")

    def _find_git_root(self) -> Path | None:
        """Find git repository root."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, cwd=str(self.project_dir),
            )
            if result.returncode == 0:
                return Path(result.stdout.strip())
        except Exception:
            pass
        return None

    # ── Tool Registration ──────────────────────────────────────

    def register_tool(self, name: str, fn: Callable) -> None:
        """Register an MCP tool."""
        self.tool_registry[name] = fn
        for executor in self.executors.values():
            executor.context.tool_registry = self.tool_registry

    def register_tools(self, tools: dict[str, Callable]) -> None:
        """Register multiple MCP tools."""
        for name, fn in tools.items():
            self.register_tool(name, fn)

    # ── Status ─────────────────────────────────────────────────

    def status_report(self) -> dict[str, Any]:
        return {
            "study_id": self.study_id,
            "trial_phase": self.trial_phase,
            "therapeutic_area": self.therapeutic_area,
            "project_config_loaded": self.project_config is not None,
            "iteration": self.state.iteration if self.state else 0,
            "executors": list(self.executors.keys()),
            "tools_registered": len(self.tool_registry),
            "review_queue": (
                self.review_queue.queue_stats() if self.review_queue else {}
            ),
            "pending_reviews": (
                self.state.pending_reviews if self.state else []
            ),
            "completed_actions": (
                len(self.state.completed_actions) if self.state else 0
            ),
            "audit_log": str(self.audit_log_path) if self.audit_log_path else "N/A",
        }


# ═══════════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════════


async def main() -> None:
    """CLI entry point: python -m src.runtime.agent_loop"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Clinical Agent Runtime v3.0",
    )
    parser.add_argument(
        "--project-dir", default="./project",
        help="Project directory (file system as state)",
    )
    parser.add_argument(
        "--study-id", default="STUDY-001",
        help="Study identifier",
    )
    parser.add_argument(
        "--trial-phase", default="phase_iii",
        choices=["phase_i", "phase_ii", "phase_iii"],
    )
    parser.add_argument(
        "--therapeutic-area", default="non_oncology",
        choices=["oncology", "non_oncology"],
    )
    parser.add_argument(
        "--no-auto-execute", action="store_true",
        help="Disable automatic execution",
    )
    parser.add_argument(
        "--no-git-commit", action="store_true",
        help="Disable automatic git commits",
    )
    parser.add_argument(
        "intent", nargs="?", default="",
        help="Natural language intent, e.g. 'Generate SDTM specs for Phase III NSCLC'",
    )

    args = parser.parse_args()

    runtime = AgentRuntime(
        project_dir=args.project_dir,
        study_id=args.study_id,
        trial_phase=args.trial_phase,
        therapeutic_area=args.therapeutic_area,
        auto_execute=not args.no_auto_execute,
        git_auto_commit=not args.no_git_commit,
    )

    # Load MCP tools
    _load_mcp_tools(runtime)

    # Print status
    print("╔══════════════════════════════════════════════════════╗")
    print("║  Clinical Agent Runtime v3.0                        ║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  Project:     {args.project_dir}")
    print(f"║  Study ID:    {args.study_id}")
    print(f"║  Phase:       {args.trial_phase}")
    print(f"║  TA:          {args.therapeutic_area}")
    print(f"║  Tools:       {len(runtime.tool_registry)} registered")
    print(f"║  Git:         {'enabled' if runtime.git_auto_commit else 'disabled'}")
    print("╚══════════════════════════════════════════════════════╝")

    if not args.intent:
        intent = input("\n> What should the agent do? ")
    else:
        intent = args.intent
        print(f"\n> {intent}")

    result = await runtime.run(intent)

    print("\n── Result ──")
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    print(f"\nAudit trail: {runtime.audit_log_path}")
    print(f"Review queue: {runtime.review_queue.queue_dir}")


def _load_mcp_tools(runtime: AgentRuntime) -> None:
    """Load MCP tools from the tools package."""
    try:
        from src.mcp_tools.server import (
            AUXILIARY_TOOL_NAMES,
            CORE_TOOL_NAMES,
            handle_tool_call,
        )

        def make_tool(tool_name: str) -> Callable[..., dict[str, Any]]:
            return lambda **kwargs: handle_tool_call(tool_name, kwargs)

        runtime.register_tools({
            name: make_tool(name)
            for name in [*CORE_TOOL_NAMES, *AUXILIARY_TOOL_NAMES]
        })
    except ImportError:
        logger.warning("MCP tools not fully available — running with empty tool registry")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(main())
