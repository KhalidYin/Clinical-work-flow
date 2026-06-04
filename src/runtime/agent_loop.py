"""
Agent Runtime v3.0 — Dynamic decision loop.

Replaces the fixed 12-stage pipeline with an agent that dynamically
decides what to do next based on context and intent.

Core loop:
  1. ASSESS  — read project state from file system
  2. DECIDE  — agent chooses next action
  3. EXECUTE — call MCP tools or submit review packet
  4. REVIEW  — if human input needed, wait for decision receipt
  5. RECORD  — git commit + audit trail
  6. REPEAT  — until done or blocked

Design principles:
  - File system IS the state — no in-memory pipeline state
  - Agent decides next step — no predefined stage ordering
  - Human interaction via ReviewQueue protocol — no chat
  - Every action recorded in audit trail
  - Git as version control backbone
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .review_protocol import (
    ReviewPacket, ReviewFinding, DecisionReceipt,
    ReviewType, ReviewQueue, FindingCategory, Severity,
    Decision, Urgency, ReviewType,
    OUTPUT_FORMAT_SPECS,
    new_review_packet, make_finding_id,
)

# Reuse existing agent infrastructure
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.agents.base import (
    BaseAgent, AgentConfig, AgentContext,
    Confidence, AgentRole,
)
from src.agents.executors import (
    ProtocolSAPAgent, DataStandardsAgent, TFLQCSubmissionAgent,
    get_executor_for_stage,
)
from src.change_management.change_record import (
    ChangeRecord, FileChange, ChangeType, ImpactType,
)

logger = logging.getLogger(__name__)


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
    def from_project(cls, project_dir: str | Path) -> "LoopState":
        """Reconstruct state from what's on disk."""
        pd = Path(project_dir)
        queue = ReviewQueue(pd)
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
    review_packet: ReviewPacket | None = None
    executor: str | None = None  # which capability domain

    def to_log(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "description": self.description,
            "tool_name": self.tool_name,
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

    Replaces Orchestrator (v2.1). Instead of a 12-stage state machine,
    the agent dynamically decides what to do next.

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

    # Settings
    auto_execute: bool = True
    require_review_for_critical: bool = True
    git_auto_commit: bool = True
    max_iterations: int = 100

    def __post_init__(self) -> None:
        if isinstance(self.project_dir, str):
            self.project_dir = Path(self.project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)

        self.review_queue = ReviewQueue(self.project_dir)
        self.audit_log_path = self.project_dir / "audit_trail.jsonl"
        self.state = LoopState.from_project(self.project_dir)
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

        The agent dynamically routes based on intent + context —
        no fixed pipeline stages.
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
        outputs_dir = self.project_dir / "outputs"
        context: dict[str, Any] = {
            "intent": intent,
            "study_id": self.study_id,
            "trial_phase": self.trial_phase,
            "therapeutic_area": self.therapeutic_area,
            "iteration": self.state.iteration,

            # What exists on disk?
            "files": {
                "protocol": list((self.project_dir).glob("protocol*")),
                "sdtm_specs": (
                    list((outputs_dir / "sdtm_specs").glob("*"))
                    if (outputs_dir / "sdtm_specs").exists() else []
                ),
                "adam_specs": (
                    list((outputs_dir / "adam_specs").glob("*"))
                    if (outputs_dir / "adam_specs").exists() else []
                ),
                "tfl_shells": (
                    list((outputs_dir / "tfl_shells").glob("*"))
                    if (outputs_dir / "tfl_shells").exists() else []
                ),
                "programs": (
                    list((outputs_dir / "programs").glob("*"))
                    if (outputs_dir / "programs").exists() else []
                ),
            },

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
        """
        Agent decides what to do next.

        This is where the LLM call happens in production. For now,
        we implement a rule-based decision engine as the foundation
        that an LLM-powered router can build on.

        Decision logic (simplified for Phase 1):
        1. If no protocol exists → can't proceed
        2. If no SDTM specs → route to DataStandardsAgent for SDTM
        3. If SDTM specs exist but no ADaM → route for ADaM
        4. If ADaM specs exist but no TFL shells → route for TFL
        5. If TFL shells exist but no programs → route for programming
        6. If programs exist but no QC → route for QC
        7. If all done → signal done

        In Phase 2, this is replaced by an LLM call that reasons
        about the full context.
        """
        files = context["files"]
        pending = context["pending_reviews"]

        # --- Rule 0: nothing to work with ---
        protocol_files = [f for f in files["protocol"]
                          if f.suffix.lower() in (".pdf", ".docx", ".txt")]
        has_protocol = len(protocol_files) > 0

        if not has_protocol:
            return AgentAction(
                action_type="wait",
                description="No protocol document found. Place protocol.pdf in project directory.",
            )

        # --- Rule 1: need SDTM specs ---
        if len(files["sdtm_specs"]) == 0:
            return AgentAction(
                action_type="call_tool",
                description="Generate SDTM domain specifications",
                tool_name="sdtm_spec_build",
                tool_args={
                    "domain_codes": self._infer_domains(intent),
                    "trial_phase": self.trial_phase,
                    "therapeutic_area": self.therapeutic_area,
                },
                executor="DataStandardsAgent",
            )

        # --- Rule 2: SDTM done, need ADaM ---
        if len(files["adam_specs"]) == 0:
            return AgentAction(
                action_type="call_tool",
                description="Generate ADaM dataset specifications",
                tool_name="adam_spec_build",
                tool_args={
                    "datasets": self._infer_adam_datasets(intent),
                    "trial_phase": self.trial_phase,
                    "therapeutic_area": self.therapeutic_area,
                },
                executor="DataStandardsAgent",
            )

        # --- Rule 3: need TFL shells ---
        if len(files["tfl_shells"]) == 0:
            return AgentAction(
                action_type="call_tool",
                description="Generate TFL shell catalog",
                tool_name="tfl_shells_list",
                tool_args={
                    "trial_phase": self.trial_phase,
                    "therapeutic_area": self.therapeutic_area,
                },
                executor="TFLQCSubmissionAgent",
            )

        # --- Rule 4: TFL shells done, need programs ---
        if len(files["programs"]) == 0 and len(files["tfl_shells"]) > 0:
            # Before generating programs, submit TFL shells for review
            pending_shell_review = any(
                "tfl_shell" in r for r in pending
            )
            if not pending_shell_review:
                # Build a review packet for TFL shells
                packet = self._build_tfl_shell_review_packet(files)
                return AgentAction(
                    action_type="submit_review",
                    description="Submit TFL shells for human review before programming",
                    review_packet=packet,
                    executor="TFLQCSubmissionAgent",
                )

            return AgentAction(
                action_type="call_tool",
                description="Generate TFL programs from approved shells",
                tool_name="tfl_renderer",
                tool_args={"tfl_shells": [str(s) for s in files["tfl_shells"]]},
                executor="TFLQCSubmissionAgent",
            )

        # --- Rule 5: everything done ---
        return AgentAction(
            action_type="done",
            description="All outputs generated. Workflow complete.",
        )

    # ── Action Execution ───────────────────────────────────────

    async def _execute_action(self, action: AgentAction) -> dict[str, Any]:
        """Execute a single action."""
        result: dict[str, Any] = {
            "action": action.to_log(),
            "status": "executed",
        }

        if action.action_type == "call_tool" and action.tool_name:
            result.update(self._call_tool(action.tool_name,
                                          action.tool_args or {}))

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

    def _call_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Call a registered MCP tool."""
        if tool_name not in self.tool_registry:
            return {"status": "error", "error": f"Tool '{tool_name}' not registered"}

        try:
            tool_fn = self.tool_registry[tool_name]
            result = tool_fn(**args)
            return {"status": "success", "tool_result": result}
        except Exception as e:
            logger.exception(f"Tool '{tool_name}' failed")
            return {"status": "error", "error": str(e)}

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
            self.review_queue.archive_completed(decision.review_id)
            return decision

        return None

    def _apply_decisions(self, receipt: DecisionReceipt) -> None:
        """Apply human decisions to the project state."""
        for fd in receipt.decisions:
            if fd.decision == Decision.APPROVED:
                logger.info(f"  ✓ {fd.finding_id}: approved")
            elif fd.decision == Decision.MODIFIED:
                logger.info(f"  ✏ {fd.finding_id}: modified → '{fd.modified_value}'")
            elif fd.decision == Decision.REJECTED:
                logger.warning(f"  ✗ {fd.finding_id}: rejected — needs re-work")
                if fd.comment:
                    logger.warning(f"    Comment: {fd.comment}")

        # Record in change log
        self.state.change_log.append({
            "type": "human_decision",
            "review_id": receipt.review_id,
            "reviewer": receipt.reviewer,
            "summary": receipt.summary(),
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
        # JSONL audit log
        log_entry = {
            **action.to_log(),
            "result_status": result.get("status", "unknown"),
            "iteration": self.state.iteration,
        }
        if self.audit_log_path:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        # Git auto-commit
        if self.git_auto_commit:
            self._git_commit(action, result)

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
        from src.mcp_tools.sdtm_spec_builder import build_sdtm_spec
        from src.mcp_tools.adam_spec_builder import build_adam_spec
        from src.mcp_tools.cdisc_validator import validate_cdisc
        from src.mcp_tools.tfl_renderer import render_tfl

        runtime.register_tools({
            "sdtm_spec_build": build_sdtm_spec,
            "adam_spec_build": build_adam_spec,
            "cdisc_validate": validate_cdisc,
            "tfl_renderer": render_tfl,
        })
    except ImportError:
        logger.warning("MCP tools not fully available — running with empty tool registry")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    asyncio.run(main())
