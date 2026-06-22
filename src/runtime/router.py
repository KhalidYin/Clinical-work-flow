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
from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════════════════════════
# Capability Registry — what each executor can do
# ═══════════════════════════════════════════════════════════════════


CAPABILITY_REGISTRY: dict[str, dict[str, Any]] = {
    "ProtocolSAPAgent": {
        "description": "Protocol analysis, SAP generation, CRF design",
        "capabilities": [
            "protocol_analysis",       # Extract endpoints, populations, methods
            "sap_generation",          # Generate SAP sections per ICH E9
            "endpoint_classification", # Primary/secondary/exploratory
            "estimands_derivation",    # ICH E9(R1) estimands framework
            "crf_pre_mapping",         # CRF → SDTM preliminary mapping
        ],
        "requires_inputs": ["protocol"],
        "produces_outputs": ["sap_draft", "endpoint_spec", "crf_mapping_recommendations"],
    },
    "DataStandardsAgent": {
        "description": "SDTM + ADaM specifications and programming",
        "capabilities": [
            "sdtm_spec_generation",    # Domain variable mapping per CDISC IG
            "sdtm_programming",        # SAS/R/Python SDTM code
            "adam_spec_generation",    # ADaM dataset derivation specs
            "adam_programming",        # SAS/R/Python ADaM code
            "ct_alignment",            # Controlled terminology checks
            "cdisc_validation",        # Pre-validation against CDISC rules
        ],
        "requires_inputs": ["protocol", "sap_draft"],
        "produces_outputs": ["sdtm_specs", "adam_specs", "sdtm_programs", "adam_programs"],
    },
    "TFLQCSubmissionAgent": {
        "description": "TFL shells, programming, QC, submission packaging",
        "capabilities": [
            "tfl_shell_generation",    # TFL shell catalog
            "tfl_programming",         # SAS/R/Python TFL code
            "qc_validation",           # Double programming QC
            "p21_triage",              # Pinnacle 21 finding triage
            "define_xml_generation",   # define.xml 2.0
            "submission_packaging",    # eCTD Module 5 structure
        ],
        "requires_inputs": ["adam_specs", "tfl_shells"],
        "produces_outputs": ["tfl_shells", "tfl_programs", "qc_report", "submission_package"],
    },
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
        results: list[RouteResult] = []

        files = context.get("files", {})
        pending = context.get("pending_reviews", [])

        # ── Stage 0: Protocol must exist ──
        protocol_files = [f for f in files.get("protocol", [])
                          if str(f).endswith((".pdf", ".docx", ".txt"))]
        if not protocol_files:
            results.append(RouteResult(
                executor="NONE",
                capability="none",
                confidence=1.0,
                reasoning="Protocol document not found. Cannot proceed.",
                prerequisites_met=False,
                missing_prerequisites=["protocol.pdf"],
            ))
            return results

        # ── Stage 1: Protocol analysis ──
        if not files.get("sdtm_specs"):
            results.append(RouteResult(
                executor="DataStandardsAgent",
                capability="sdtm_spec_generation",
                confidence=0.95,
                reasoning="No SDTM specs exist. Must generate from protocol and CRF data.",
                suggested_tools=["sdtm_spec_build"],
            ))

        # ── Stage 2: ADaM spec generation ──
        if files.get("sdtm_specs") and not files.get("adam_specs"):
            results.append(RouteResult(
                executor="DataStandardsAgent",
                capability="adam_spec_generation",
                confidence=0.90,
                reasoning="SDTM specs exist but no ADaM specs. Generate ADaM datasets.",
                suggested_tools=["adam_spec_build"],
            ))

        # ── Stage 3: TFL shells ──
        if files.get("adam_specs") and not files.get("tfl_shells"):
            results.append(RouteResult(
                executor="TFLQCSubmissionAgent",
                capability="tfl_shell_generation",
                confidence=0.90,
                reasoning="ADaM specs exist but no TFL shells. Generate TFL catalog.",
                suggested_tools=["tfl_shells_list"],
            ))

        # ── Stage 4: Programming ──
        if files.get("tfl_shells") and not files.get("programs"):
            # Check if TFL shells have been reviewed
            tfl_review_pending = any("tfl_shell" in r for r in pending)
            if tfl_review_pending:
                results.append(RouteResult(
                    executor="TFLQCSubmissionAgent",
                    capability="tfl_programming",
                    confidence=0.50,
                    reasoning="TFL shells exist but are pending human review. "
                              "Wait for approval before programming.",
                    prerequisites_met=False,
                    missing_prerequisites=["tfl_shell_human_approval"],
                ))
            else:
                results.append(RouteResult(
                    executor="TFLQCSubmissionAgent",
                    capability="tfl_programming",
                    confidence=0.85,
                    reasoning="TFL shells approved. Proceed to program generation.",
                    suggested_tools=["tfl_renderer"],
                ))

        # ── Stage 5: Done ──
        if not results:
            results.append(RouteResult(
                executor="NONE",
                capability="done",
                confidence=0.95,
                reasoning="All expected outputs exist. Workflow appears complete.",
            ))

        return results

    def best_route(self, intent: str,
                   context: dict[str, Any]) -> RouteResult | None:
        """Return the single best next action, or None if done."""
        routes = self.route(intent, context)
        if not routes:
            return None

        # Filter to routes with prerequisites met
        ready_routes = [r for r in routes if r.prerequisites_met]
        if not ready_routes:
            return routes[0]  # Return first blocker

        # Return highest confidence ready route
        return max(ready_routes, key=lambda r: r.confidence)

    def summarize_context(self, context: dict[str, Any]) -> str:
        """Human-readable summary of the current context for the agent."""
        files = context.get("files", {})
        pending = context.get("pending_reviews", [])

        parts = []

        # Protocol
        protocol_count = len(files.get("protocol", []))
        parts.append(f"Protocol: {'[OK]' if protocol_count > 0 else '[MISSING]'} "
                     f"({protocol_count} file(s))")

        # SDTM
        sdtm_count = len(files.get("sdtm_specs", []))
        parts.append(f"SDTM Specs: {'[OK]' if sdtm_count > 0 else '[---]'} "
                     f"({sdtm_count} domains)")

        # ADaM
        adam_count = len(files.get("adam_specs", []))
        parts.append(f"ADaM Specs: {'[OK]' if adam_count > 0 else '[---]'} "
                     f"({adam_count} datasets)")

        # TFL
        tfl_count = len(files.get("tfl_shells", []))
        parts.append(f"TFL Shells: {'[OK]' if tfl_count > 0 else '[---]'} "
                     f"({tfl_count} shells)")

        # Programs
        prog_count = len(files.get("programs", []))
        parts.append(f"Programs: {'[OK]' if prog_count > 0 else '[---]'} "
                     f"({prog_count} files)")

        # Pending
        parts.append(f"Pending Reviews: {len(pending)}")

        return " | ".join(parts)


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
