"""
Pipeline Router v3.0 — context-aware fixed-stage routing.

Replaces the old persisted STAGE_EXECUTOR_MAP with a router that:
  1. Analyzes intent + project context
  2. Selects the next capability domain in the fixed clinical order
  3. Returns a ranked list of actions

Phase 1: Rule-based (this implementation)
Phase 2: LLM-powered (Claude API call with context + schema)

The router helps infer the next action, but it does not permit arbitrary
reordering of the Protocol → SDTM → ADaM → TFL dependency chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .pipeline_contract import CANONICAL_PIPELINE, CapabilityName, PipelineStage


# ═══════════════════════════════════════════════════════════════════
# Capability Registry — what each executor can do
# ═══════════════════════════════════════════════════════════════════


CAPABILITY_REGISTRY: dict[str, dict[str, Any]] = {
    executor.value: {
        "capabilities": [
            capability.value
            for stage in CANONICAL_PIPELINE.stages
            if stage.executor is executor
            for capability in stage.allowed_capabilities
        ],
        "stages": [stage.stage_id.value for stage in CANONICAL_PIPELINE.stages if stage.executor is executor],
    }
    for executor in {stage.executor for stage in CANONICAL_PIPELINE.stages}
}


# ═══════════════════════════════════════════════════════════════════
# Router
# ═══════════════════════════════════════════════════════════════════


@dataclass
class RouteResult:
    """Result of routing decision."""
    executor: str
    capability: str
    confidence: float  # 0.0 — 1.0
    reasoning: str
    suggested_tools: list[str] = field(default_factory=list)
    prerequisites_met: bool = True
    missing_prerequisites: list[str] = field(default_factory=list)
    stage_id: PipelineStage | None = None
    allowed_capabilities: tuple[CapabilityName, ...] = ()
    suggested_executables: list[str] = field(default_factory=list)


class RoutingError(ValueError):
    """Untrusted routing context attempted to change the Engine pipeline."""


@dataclass
class Router:
    """
    Context-aware capability router.

    Phase 1 (current): Rule-based.
      - Analyzes file system state
      - Matches against capability registry
      - Returns ranked route results

    Phase 2 (future): LLM-powered.
      - Sends full context to Claude
      - Claude reasons about what to do next
      - Returns structured RouteResult via JSON Schema
    """

    capability_registry: dict[str, dict[str, Any]] = field(
        default_factory=lambda: CAPABILITY_REGISTRY.copy()
    )

    def route(self, intent: str,
              context: dict[str, Any]) -> list[RouteResult]:
        """
        Given intent and project context, return ordered list of
        what should be done next.
        """
        _validate_context(context)
        files = context.get("files", {})
        if not isinstance(files, Mapping):
            raise RoutingError("routing context.files must be a mapping")

        stage = self.current_stage(files)
        if stage is None:
            return [
                RouteResult(
                    executor="NONE", capability="done", confidence=1.0,
                    reasoning="All canonical pipeline completion evidence exists.",
                )
            ]
        stage_contract = CANONICAL_PIPELINE.get_stage(stage)
        missing = _missing_initial_inputs(stage, files)
        return [
            RouteResult(
                executor=stage_contract.executor.value,
                capability=stage_contract.allowed_capabilities[0].value,
                confidence=1.0 if not missing else 0.0,
                reasoning=(
                    f"Fixed pipeline stage {stage.value} is the first stage without "
                    "complete canonical evidence."
                ),
                suggested_tools=[item.value for item in stage_contract.allowed_tools],
                suggested_executables=[item.value for item in stage_contract.allowed_executables],
                prerequisites_met=not missing,
                missing_prerequisites=missing,
                stage_id=stage,
                allowed_capabilities=stage_contract.allowed_capabilities,
            )
        ]

    @staticmethod
    def current_stage(files: Mapping[str, Any]) -> PipelineStage | None:
        """Return the first incomplete one of exactly the ten contract stages."""
        for stage in CANONICAL_PIPELINE.stages:
            if not _stage_complete(stage.stage_id, files):
                return stage.stage_id
        return None

    def route_stage(
        self, stage_id: PipelineStage | str, capability: CapabilityName | str
    ) -> RouteResult:
        """Validate a proposed action against the Engine-owned stage contract."""
        try:
            stage = PipelineStage(stage_id)
            selected_capability = CapabilityName(capability)
        except ValueError as exc:
            raise RoutingError("unknown pipeline stage or capability") from exc
        contract = CANONICAL_PIPELINE.get_stage(stage)
        if selected_capability not in contract.allowed_capabilities:
            raise RoutingError("capability is not allowed during the fixed pipeline stage")
        return RouteResult(
            executor=contract.executor.value,
            capability=selected_capability.value,
            confidence=1.0,
            reasoning="Validated against the canonical Pipeline Contract.",
            suggested_tools=[item.value for item in contract.allowed_tools],
            suggested_executables=[item.value for item in contract.allowed_executables],
            stage_id=stage,
            allowed_capabilities=contract.allowed_capabilities,
        )

    def best_route(self, intent: str,
                   context: dict[str, Any]) -> RouteResult | None:
        """Return the single best next action, or None if done."""
        routes = self.route(intent, context)
        if not routes:
            return None

        return routes[0]

    def summarize_context(self, context: dict[str, Any]) -> str:
        """Human-readable summary of the current context for the agent."""
        files = context.get("files", {})
        pending = context.get("pending_reviews", [])

        parts = []

        _validate_context(context)
        if not isinstance(files, Mapping):
            raise RoutingError("routing context.files must be a mapping")
        stage = self.current_stage(files)
        parts.append(f"Current fixed stage: {stage.value if stage else 'complete'}")
        parts.append(f"Pending Reviews: {len(pending)}")
        return " | ".join(parts)


_STAGE_EVIDENCE_KEYS: dict[PipelineStage, tuple[tuple[str, ...], ...]] = {
    PipelineStage.PROTOCOL_ANALYSIS: (("protocol_analysis",),),
    PipelineStage.SAP_GENERATION: (("sap", "sap_draft"),),
    PipelineStage.SDTM_SPEC: (("sdtm_specs",),),
    PipelineStage.SDTM_PROGRAMMING: (("sdtm_programs",), ("sdtm_datasets",)),
    PipelineStage.ADAM_SPEC: (("adam_specs",),),
    PipelineStage.ADAM_PROGRAMMING: (("adam_programs",), ("adam_datasets",)),
    PipelineStage.TFL_SHELL_DESIGN: (("tfl_shells",),),
    PipelineStage.TFL_PROGRAMMING: (("tfl_programs",), ("tfl_outputs",)),
    PipelineStage.QC_VALIDATION: (("qc_report",),),
    PipelineStage.SUBMISSION_PACKAGING: (("submission_manifest",), ("submission_package",)),
}


def _stage_complete(stage: PipelineStage, files: Mapping[str, Any]) -> bool:
    evidence = files.get("completion_evidence")
    contract = CANONICAL_PIPELINE.get_stage(stage)
    if isinstance(evidence, (list, tuple, set)):
        normalized = {str(item).replace("\\", "/") for item in evidence}
        return all(path in normalized for path in contract.completion_evidence)
    return all(any(_has_value(files.get(key)) for key in alternatives) for alternatives in _STAGE_EVIDENCE_KEYS[stage])


def _missing_initial_inputs(stage: PipelineStage, files: Mapping[str, Any]) -> list[str]:
    if stage is PipelineStage.PROTOCOL_ANALYSIS and not _has_value(files.get("protocol")):
        return ["protocol"]
    return []


def _has_value(value: Any) -> bool:
    return bool(value) if not isinstance(value, str) else bool(value.strip())


def _validate_context(context: Mapping[str, Any]) -> None:
    forbidden = {"command", "commands", "next_stage", "skip_stage", "stage_override", "tool_calls"}

    def visit(value: Any) -> bool:
        if isinstance(value, Mapping):
            return bool(forbidden.intersection(value)) or any(visit(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(visit(item) for item in value)
        return False

    if visit(context):
        raise RoutingError("routing context contains forbidden control fields")


# ═══════════════════════════════════════════════════════════════════
# Intent Parser — extract structured info from natural language
# ═══════════════════════════════════════════════════════════════════


def parse_intent(intent: str) -> dict[str, Any]:
    """
    Parse a natural-language intent into structured fields.

    Simple keyword-based parser for Phase 1.
    Phase 2 replaces with Claude API call returning structured schema.
    """
    intent_lower = intent.lower()

    parsed: dict[str, Any] = {
        "raw": intent,
        "action": None,
        "domains": [],
        "datasets": [],
        "trial_phase": None,
        "therapeutic_area": None,
    }

    # Detect action
    if any(kw in intent_lower for kw in ["sdtm", "domain", "mapping"]):
        parsed["action"] = "generate_sdtm_specs"
    elif any(kw in intent_lower for kw in ["adam", "analysis dataset"]):
        parsed["action"] = "generate_adam_specs"
    elif any(kw in intent_lower for kw in ["tfl", "shell", "table", "figure", "listing"]):
        parsed["action"] = "generate_tfl_shells"
    elif any(kw in intent_lower for kw in ["program", "code", "sas", "r ", "python"]):
        parsed["action"] = "generate_programs"
    elif any(kw in intent_lower for kw in ["qc", "validate", "quality"]):
        parsed["action"] = "run_qc"
    elif any(kw in intent_lower for kw in ["submit", "submission", "ectd", "package"]):
        parsed["action"] = "prepare_submission"
    elif any(kw in intent_lower for kw in ["protocol", "sap", "analyze"]):
        parsed["action"] = "analyze_protocol"
    else:
        parsed["action"] = "full_workflow"  # Do everything

    # Detect domains
    domain_map = {
        "ae": "AE", "adverse": "AE",
        "cm": "CM", "concomitant": "CM", "medication": "CM",
        "lb": "LB", "lab": "LB",
        "vs": "VS", "vital": "VS",
        "ex": "EX", "exposure": "EX",
        "ds": "DS", "disposition": "DS",
        "mh": "MH", "history": "MH",
        "eg": "EG", "ecg": "EG",
        "qs": "QS", "questionnaire": "QS",
        "tu": "TU", "tr": "TR", "rs": "RS", "tumor": "TU",
    }
    parsed["domains"] = list(set(
        code for kw, code in domain_map.items() if kw in intent_lower
    ))

    # Detect datasets
    dataset_map = {
        "adsl": "ADSL", "adae": "ADAE", "adtte": "ADTTE",
        "adlb": "ADLB", "advs": "ADVS", "adtr": "ADTR",
        "adcm": "ADCM",
    }
    parsed["datasets"] = list(set(
        code for kw, code in dataset_map.items() if kw in intent_lower
    ))

    # Detect phase — match longer patterns first
    if "phase iii" in intent_lower or "phase 3" in intent_lower:
        parsed["trial_phase"] = "phase_iii"
    elif "phase ii" in intent_lower or "phase 2" in intent_lower:
        parsed["trial_phase"] = "phase_ii"
    elif "phase i" in intent_lower or "phase 1" in intent_lower:
        parsed["trial_phase"] = "phase_i"

    # Detect TA
    if any(kw in intent_lower for kw in ["oncology", "nsclc", "tumor", "cancer",
                                          "recist", "os ", "pfs", "solid tumor"]):
        parsed["therapeutic_area"] = "oncology"

    return parsed
