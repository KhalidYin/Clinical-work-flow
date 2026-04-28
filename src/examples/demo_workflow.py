"""
Demo: Full clinical stat programming workflow executed through the orchestrator.

Usage: python -m src.examples.demo_workflow
"""

import asyncio
from src.workflow.state_machine import (
    WorkflowState, Stage, TrialPhase, TherapeuticArea,
    HUMAN_GATES, AI_AUTO_STAGES, ApprovalStatus,
)
from src.workflow.orchestrator import Orchestrator, OrchestratorConfig, STAGE_ASSIGNMENT
from src.mcp_tools.sdtm_spec_builder import STANDARD_DOMAINS, generate_sdtm_spec
from src.mcp_tools.adam_spec_builder import generate_adam_spec
from src.mcp_tools.tfl_renderer import get_tfl_shells
from src.mcp_tools.cdisc_validator import validate_sdtm, validate_adam, triage_pinnacle21_findings
from src.skills.definitions import get_skill, ALL_SKILLS
from src.knowledge.clinical_standards import (
    CDISC_KNOWLEDGE, PHASE_KNOWLEDGE, TA_KNOWLEDGE, AI_PROMPT_TEMPLATES,
)


def print_stage_header(stage: Stage, state: WorkflowState):
    """Print a formatted stage header."""
    width = 70
    print(f"\n{'='*width}")
    print(f"  STAGE: {stage.value.upper()}")
    print(f"  Study: {state.study_id} | Phase: {state.trial_phase.value} | TA: {state.therapeutic_area.value}")
    gate = HUMAN_GATES.get(stage)
    if gate:
        print(f"  Human Gate: YES — {gate.description[:60]}...")
    elif stage in AI_AUTO_STAGES:
        print(f"  Human Gate: NO  — AI-auto stage")
    else:
        print(f"  Human Gate: NO")
    print(f"{'='*width}")


def demo_sdtm_generation(state: WorkflowState):
    """Demonstrate SDTM spec generation for a Phase III oncology trial."""
    print_stage_header(Stage.SDTM_SPEC, state)

    # Show what domains would be generated
    oncology_domains = ["DM", "AE", "CM", "LB", "VS", "EX", "DS"]
    for domain_code in oncology_domains:
        domain = STANDARD_DOMAINS.get(domain_code)
        spec = generate_sdtm_spec(domain_code, [], domain)
        req_vars = sum(1 for v in spec["variables"] if v.get("mandatory"))
        print(f"  {domain_code:4s}  {spec['name']:30s}  "
              f"Class: {spec['class']:20s}  Variables: {len(spec['variables']):3d} (Req: {req_vars})")

    # Run CDISC validation
    print(f"\n  --- CDISC Pre-Validation ---")
    findings = validate_sdtm("AE", None)
    triage = triage_pinnacle21_findings(findings)
    print(f"  Total findings: {triage['total_findings']}")
    print(f"  Auto-resolved:  {triage['auto_resolved']}")
    print(f"  Needs review:   {triage['needs_human_review']}")
    for f in triage["review_queue"][:3]:
        print(f"    [{f['severity']}] {f['rule_id']}: {f['message'][:80]}")


def demo_adam_generation(state: WorkflowState):
    """Demonstrate ADaM spec generation."""
    print_stage_header(Stage.ADAM_SPEC, state)

    datasets = ["ADSL", "ADAE", "ADTTE"]
    if state.therapeutic_area == TherapeuticArea.ONCOLOGY:
        datasets.append("ADTR")

    for ds_name in datasets:
        try:
            spec = generate_adam_spec(ds_name, state.trial_phase.value, state.therapeutic_area.value)
            print(f"  {ds_name:6s}  {spec['label']:40s}  "
                  f"Variables: {len(spec['variables']):3d}  "
                  f"Source: {spec['predecessor']}")
        except ValueError as e:
            print(f"  {ds_name:6s}  [SKIPPED] — {e}")

    # Run CDISC validation
    print(f"\n  --- ADaM Compliance Check ---")
    findings = validate_adam("ADAE", None)
    triage = triage_pinnacle21_findings(findings)
    print(f"  Findings: {triage['total_findings']} "
          f"(Errors: {triage['triage_summary']['errors']}, "
          f"Warnings: {triage['triage_summary']['warnings']})")


def demo_tfl_generation(state: WorkflowState):
    """Demonstrate TFL shell generation."""
    print_stage_header(Stage.TFL_SHELL, state)

    shells = get_tfl_shells(state.trial_phase.value, state.therapeutic_area.value)
    tables = [s for s in shells if s.tfl_type.value == "table"]
    figures = [s for s in shells if s.tfl_type.value == "figure"]
    listings = [s for s in shells if s.tfl_type.value == "listing"]

    print(f"\n  TFL Catalog: {len(shells)} total")
    print(f"    Tables:   {len(tables)}")
    print(f"    Figures:  {len(figures)}")
    print(f"    Listings: {len(listings)}")

    print(f"\n  --- Table Shells ---")
    for t in tables[:4]:
        print(f"    {t.tfl_id:12s} {t.title[:60]}")

    if state.therapeutic_area == TherapeuticArea.ONCOLOGY:
        print(f"\n  --- Oncology-Specific TFLs ---")
        for s in shells[len(tables) + len(figures):]:
            if s.tfl_id.startswith("F14.2."):
                print(f"    {s.tfl_id:12s} {s.title[:60]}")

    print(f"\n  --- Listings ---")
    for l in listings:
        print(f"    {l.tfl_id:12s} {l.title[:60]}  |  Source: {l.source_dataset}")


def demo_human_gate_flow(state: WorkflowState):
    """Demonstrate the human-in-the-loop approval flow."""
    print("\n" + "="*70)
    print("  HUMAN-IN-THE-LOOP GATES")
    print("="*70)

    gates_sequence = [
        Stage.SAP, Stage.SDTM_SPEC, Stage.ADAM_SPEC,
        Stage.TFL_SHELL, Stage.QC_VALIDATION, Stage.SUBMISSION,
    ]

    print(f"\n  {'Gate Stage':20s} {'Reviewers':30s} {'Checklist Items':>15s} {'Status':>12s}")
    print(f"  {'-'*20} {'-'*30} {'-'*15} {'-'*12}")
    for stage in gates_sequence:
        gate = HUMAN_GATES.get(stage)
        if gate:
            reviewers = ", ".join(gate.reviewers[:2])
            print(f"  {stage.value:20s} {reviewers:30s} {len(gate.checklist):>15d} {gate.status.value:>12s}")

    # Simulate an approval
    sap_gate = HUMAN_GATES[Stage.SAP]
    sap_gate.approve("Dr. Li (Lead Biostatistician)", "SAP looks complete. Proceed to SDTM.")
    print(f"\n  [APPROVED] {Stage.SAP.value} by {sap_gate.signed_by}")
    print(f"  Status: {sap_gate.status.value}")


def demo_knowledge_base():
    """Demonstrate the knowledge base."""

    print("\n" + "="*70)
    print("  KNOWLEDGE BASE SUMMARY")
    print("="*70)

    # CDISC standards
    print(f"\n  CDISC Standards: {len(CDISC_KNOWLEDGE)} loaded")
    for code, standard in CDISC_KNOWLEDGE.items():
        print(f"    {code:30s} {standard.version}")

    # Regulatory guidance
    print(f"\n  Regulatory Guidance:")
    for org, guides in [("FDA", ["TCG", "eCTD", "21_CFR_11"]),
                        ("ICH", ["E3", "E6", "E9", "E9_R1", "E10"]),
                        ("NMPA (China)", ["data_submission", "statistical_guidelines"])]:
        print(f"    {org}: {', '.join(guides)}")

    # Phase knowledge
    print(f"\n  Phase-Specific Configurations:")
    for phase, info in PHASE_KNOWLEDGE.items():
        print(f"    {phase}: {info['sample_size_range']:15s} | "
              f"TFLs: {info['tfl_volume']:12s} | "
              f"Focus: {info['primary_focus'][:40]}...")

    # TA knowledge
    print(f"\n  Therapeutic Area Specializations:")
    for ta, info in TA_KNOWLEDGE.items():
        print(f"    {ta}:")
        print(f"      Key endpoints: {', '.join(info['key_endpoints'][:5])}")
        if "specialized_adam" in info:
            print(f"      Specialized ADaM: {', '.join(info['specialized_adam'].keys())}")
        if "key_figures" in info:
            print(f"      Key figures: {', '.join(f.split('(')[0].strip() for f in info['key_figures'][:3])}")
        print(f"      Dictionary: {info.get('dictionary', 'MedDRA')}")


def demo_ai_prompts():
    """Show AI prompt templates for each workflow stage."""
    print("\n" + "="*70)
    print("  AI PROMPT TEMPLATES")
    print("="*70)

    for name, template in AI_PROMPT_TEMPLATES.items():
        print(f"\n  [{name}]")
        print(f"    System: {template['system'][:100]}...")
        print(f"    Output: {template['output_format'][:100]}...")


def demo_end_to_end(state: WorkflowState):
    """Demonstrate a full end-to-end clinical workflow pipeline."""

    print("\n" + "#"*70)
    print("#  CLINICAL STATISTICAL PROGRAMMING AI WORKFLOW")
    print("#  End-to-End Pipeline Demonstration")
    print(f"#")
    print(f"#  Study:         {state.study_id}")
    print(f"#  Phase:         {state.trial_phase.value.upper()}")
    print(f"#  Area:          {state.therapeutic_area.value.upper()}")
    print(f"#  Starting from: {state.current_stage.value.upper()}")
    print("#"*70)

    demo_knowledge_base()

    # Walk through the pipeline
    for stage in Stage.sequence():
        if stage == Stage.PROTOCOL:
            print(f"\n  [Protocol] Protocol analysis would be performed by ProtocolAnalyzer Agent")
            print(f"    → Extracts endpoints, populations, methods → feeds to SAP")
            continue

        if stage == Stage.SAP:
            print(f"\n  [SAP] Statistical Analysis Plan")
            print(f"    → Agent: SAPBuilder generates draft from protocol analysis")
            print(f"    → Skill: sap-review interactive review triggers here")
            continue

        if stage in (Stage.CRF_DESIGN, Stage.DATA_COLLECTION):
            continue  # Skip for demo

        if stage == Stage.SDTM_SPEC:
            demo_sdtm_generation(state)

        if stage == Stage.ADAM_SPEC:
            demo_adam_generation(state)

        if stage == Stage.TFL_SHELL:
            demo_tfl_generation(state)

        if stage in (Stage.SDTM_PROGRAMMING, Stage.ADAM_PROGRAMMING):
            print(f"\n  [{stage.value}] AI-auto programming stage — Agent executes autonomously")
            continue

        if stage == Stage.TFL_PROGRAMMING:
            print(f"\n  [{stage.value}] TFL programming — Agent generates RTF/PDF outputs")
            continue

        if stage == Stage.QC_VALIDATION:
            print(f"\n  [{stage.value}] Double programming QC + P21 validation")
            continue

        if stage == Stage.SUBMISSION:
            print(f"\n  [{stage.value}] define.xml + ADRG + SDRG + eCTD packaging")
            continue

    demo_human_gate_flow(state)
    demo_ai_prompts()

    print("\n" + "#"*70)
    print("#  PIPELINE DEMO COMPLETE")
    print(f"#  6 Human-in-the-loop gates")
    print(f"#  4 AI Agents: Protocol Analyzer, SDTM Mapper, ADaM Builder, TFL Generator")
    print(f"#  4 Claude Skills: sap-review, domain-review, tfl-qc, adrg-draft")
    print(f"#  6 MCP Tools: sdtm-spec-builder, adam-spec-builder, tfl-shells-list,")
    print(f"#              cdisc-validate, define-xml-build, triage-p21")
    print("#"*70)


def main():
    """Run the full workflow demo."""
    state = WorkflowState(
        protocol_id="PROT-ONC-301",
        trial_phase=TrialPhase.PHASE_III,
        therapeutic_area=TherapeuticArea.ONCOLOGY,
    )
    demo_end_to_end(state)


if __name__ == "__main__":
    main()
