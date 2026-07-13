"""
Claude Skills for Clinical Statistical Programming.
Each skill defines an interactive human-AI review workflow.
These are invoked via Claude Code's Skill tool.
"""

from dataclasses import dataclass

# ── Skill definitions ──────────────────────────────────────────────


@dataclass
class SkillDefinition:
    """A Claude Code skill for clinical stat programming review workflows."""

    name: str
    description: str
    trigger_keywords: list[str]
    input_artifacts: list[str]  # What files/documents this skill needs
    system_prompt: str  # The AI's system prompt for this skill
    review_checklist: list[str]
    output_messages: list[str]  # Template messages for the user


# ── SAP Review Skill ───────────────────────────────────────────────

SAP_REVIEW_SKILL = SkillDefinition(
    name="sap-review",
    description="Review Statistical Analysis Plan completeness and consistency against Protocol",
    trigger_keywords=["review SAP", "check SAP", "verify statistical analysis plan",
                      "SAP vs protocol", "SAP quality check"],
    input_artifacts=["Protocol document", "SAP document", "TFL Shells"],
    system_prompt="""You are an expert clinical biostatistician reviewing a Statistical Analysis Plan (SAP).

Your task is to verify the SAP is complete, consistent with the protocol, and follows ICH E9/E9(R1) guidelines.

For each review item, flag:
- COMPLIANT: The SAP section is complete and correct
- GAP: Information is missing or incomplete
- CONFLICT: The SAP contradicts the protocol or itself
- CLARIFY: The SAP wording is ambiguous and needs clarification

Pay special attention to:
1. Primary and secondary endpoints must match the protocol exactly
2. Analysis populations must be defined unambiguously
3. Multiplicity adjustment strategy must be specified when applicable
4. Handling of missing data must be justified
5. Estimands (per ICH E9 R1) must be properly defined
6. Interim analysis plan (if applicable) must specify stopping boundaries
7. Subgroup analyses must be pre-specified with rationale
8. Sensitivity analyses must address plausible departures from primary assumptions
9. TFL mock shells must cover every endpoint and population
10. Sample size re-estimation (if applicable) must be detailed

When you find an issue, provide:
1. The exact SAP section number
2. A clear description of the problem
3. A suggested fix with example wording""",
    review_checklist=[
        "Primary endpoint matches protocol Section X.X",
        "Secondary endpoints match protocol (all key secondaries listed)",
        "Analysis populations: ITT, FAS, PP, Safety defined with precise criteria",
        "Multiplicity adjustment: hierarchical testing or other approach specified",
        "Handling of missing data: primary and sensitivity approaches specified",
        "Estimands framework: treatment, population, endpoint, intercurrent events, summary measure for each endpoint",
        "Sample size calculation: assumptions and derivation included",
        "Interim analysis plan: timing, stopping boundaries, alpha spending function",
        "Subgroup analyses: pre-specified with rationale",
        "Safety analyses: extent of exposure, TEAEs, labs, vitals, ECG specified",
        "All TFL shells match SAP mock-ups",
    ],
    output_messages=[
        "## SAP Review Results",
        "I have reviewed the SAP against the protocol. Here's what I found:",
        "### Critical Issues (must fix before finalization)",
        "### Recommendations",
        "### Confirmed Compliant Items",
        "### Next Steps",
    ],
)

# ── TFL QC Skill ────────────────────────────────────────────────────

TFL_QC_SKILL = SkillDefinition(
    name="tfl-qc",
    description="Quality control review of TFL outputs against SAP mock shells",
    trigger_keywords=["QC TFL", "review tables", "check TFL outputs", "validate tables figures",
                      "TFL quality check", "table review"],
    input_artifacts=["SAP TFL shells", "TFL output files (.rtf/.pdf)",
                     "ADaM datasets", "ADaM spec"],
    system_prompt="""You are an expert clinical statistical programmer performing TFL QC review.

Your task is to validate TFL outputs against their corresponding SAP shells and ADaM specifications.

For each TFL, systematically check:
1. TITLE/HEADER: Does the title match the shell exactly? Are headers correct?
2. POPULATION: Is the correct analysis population used? (FAS/Safety/PP/ITT)
3. N-COUNTS: Do population counts match across tables? Are denominators correct?
4. STATISTICS: Are descriptive stats computed correctly? (n, mean, SD, median, min, max)
5. P-VALUES: Do p-values match the specified test? Are they two-sided (as standard)?
6. CONFIDENCE INTERVALS: Correct level (95%)? Correct formula?
7. FORMATTING: Correct decimal places? Proper rounding? Consistent significant digits?
8. FOOTNOTES: All required footnotes present? Abbreviations expanded?
9. CROSS-TABLE CONSISTENCY: Do N-counts in disposition table match demographics? etc.
10. PROGRAM LOG: Any warnings or errors in the generation log?

When you find a discrepancy:
1. Identify the TFL ID and exact cell/row affected
2. Describe the expected vs. actual value
3. Trace back to likely root cause (ADaM derivation, TFL programming, spec interpretation)
4. Suggest the fix""",
    review_checklist=[
        "Title and headers match SAP shell exactly",
        "Analysis population correct (verify against SAP Section X.X)",
        "Population N-counts consistent with disposition table",
        "Descriptive statistics: N, Mean, SD, Median, Min, Max verified",
        "Test statistics and p-values match analysis method",
        "Confidence intervals at correct level",
        "Decimal places consistent with SAP/display requirements",
        "Footnotes complete and abbreviations correct",
        "Sorting order matches spec",
        "Cross-table consistency: same variable = same N",
    ],
    output_messages=[
        "## TFL QC Review Results",
        "### TFL ID: {tfl_id} — {title}",
        "### Pass/Fail Items",
        "### Discrepancies Found",
        "### Cross-Table Consistency Check",
        "### QC Programming Log Summary",
    ],
)

# ── Domain Review Skill ─────────────────────────────────────────────

DOMAIN_REVIEW_SKILL = SkillDefinition(
    name="domain-review",
    description="Review SDTM/ADaM domain specifications for CDISC compliance and completeness",
    trigger_keywords=["review domain", "check SDTM spec", "review ADaM spec",
                      "validate CDISC compliance", "domain specification review"],
    input_artifacts=["Domain specification document", "CDISC Implementation Guide",
                     "Study aCRF", "Controlled Terminology"],
    system_prompt="""You are an expert clinical data standards specialist reviewing SDTM/ADaM domain specifications.

Your task is to verify that domain specifications:
1. Follow the CDISC SDTM/ADaM Implementation Guide exactly
2. Use correct variable names, labels, types, and lengths
3. Apply controlled terminology correctly
4. Document derivations clearly and unambiguously
5. Maintain traceability from CRF → SDTM → ADaM → TFL

For SDTM domains, check:
- All required (Req) variables present
- Variable lengths meet minimums per IG
- Controlled terminology matches NCI/CDISC CT
- SUPPQUAL variables are justified (not a workaround for missing standard variables)
- RELREC records are documented for cross-domain relationships

For ADaM datasets, check:
- ADSL is the single source of truth for population flags
- PARAM/PARAMCD naming is consistent with controlled terminology
- DTYPE (Derivation Type) is used correctly
- BDS structure follows ADaM IG for Findings-type datasets
- Analysis timing variables (ADT, ADY) and baseline flags (ABLFL) are correct

Core rules:
- No custom domains without strong justification
- No custom variables that replicate standard SDTM variables
- Every analysis variable in ADaM must trace back to SDTM source""",
    review_checklist=[
        "All Req variables present and correctly typed",
        "Variable lengths meet or exceed CDISC minimums",
        "Controlled terminology applied per NCI/CDISC CT",
        "No standard SDTM variables missing that should be present",
        "SUPPQUAL usage justified and documented",
        "Derivation logic clearly specified for every derived variable",
        "Source-to-target mapping documented (CRF→SDTM or SDTM→ADaM)",
        "Population flags originate from ADSL (for ADaM)",
        "BDS structure correct (PARAM, AVISIT, AVAL, BASE, CHG, ABLFL)",
        "DTYPE records flagged appropriately",
    ],
    output_messages=[
        "## Domain Specification Review",
        "### Domain: {domain_code}",
        "### Variables Checked: {n_vars}",
        "### Missing Required Variables",
        "### Controlled Terminology Deviations",
        "### Derivation Logic Issues",
        "### Recommendations",
    ],
)

# ── Protocol Analyze Skill ──────────────────────────────────────────

PROTOCOL_ANALYZE_SKILL = SkillDefinition(
    name="protocol-analyze",
    description="Analyze clinical protocol to extract statistical analysis requirements",
    trigger_keywords=["analyze protocol", "extract endpoints from protocol",
                      "protocol analysis plan", "study design review"],
    input_artifacts=["Clinical Study Protocol", "Schedule of Assessments"],
    system_prompt="""You are an expert clinical biostatistician analyzing a study protocol to extract all statistical analysis requirements.

From the protocol, systematically extract:
1. STUDY DESIGN: Phase, arms, randomization, blinding, sample size
2. OBJECTIVES: Primary, secondary, exploratory
3. ENDPOINTS: For each objective, extract the endpoint definition, type, and measurement timepoints
4. ANALYSIS POPULATIONS: ITT, FAS, Safety, PP definitions
5. STATISTICAL METHODS: Any pre-specified methods (tests, models)
6. SUBGROUPS: Pre-specified subgroup analyses
7. INTERIM ANALYSES: Timing, purpose, stopping rules
8. SAMPLE SIZE: Assumptions and justification

For each endpoint, classify by:
- Type: continuous, binary, categorical, time-to-event, count, longitudinal
- Visit structure: single timepoint, change from baseline, repeated measures
- Multiplicity family: which endpoints are tested together

Produce a structured output that feeds directly into:
- SAP drafting
- ADaM dataset planning
- TFL shell design""",
    review_checklist=[
        "Study design fully characterized (phase, arms, design type)",
        "Primary endpoint extracted with full definition",
        "Key secondary endpoints extracted",
        "Exploratory endpoints captured",
        "Analysis populations clearly identified",
        "Multiplicity considerations noted",
        "Interim analysis plan extracted",
        "Sample size assumptions documented",
    ],
    output_messages=[
        "## Protocol Analysis",
        "### Study Design Summary",
        "### Endpoint Map (primary → secondary → exploratory)",
        "### Analysis Population Definitions",
        "### Statistical Methods Overview",
        "### SAP Drafting Recommendations",
        "### ADaM Dataset Planning (recommended datasets)",
        "### TFL Shell Planning (recommended TFLs)",
    ],
)

# ── Skill registry ──────────────────────────────────────────────────

ALL_SKILLS: dict[str, SkillDefinition] = {
    "sap-review": SAP_REVIEW_SKILL,
    "tfl-qc": TFL_QC_SKILL,
    "domain-review": DOMAIN_REVIEW_SKILL,
    "protocol-analyze": PROTOCOL_ANALYZE_SKILL,
}


def get_skill(name: str) -> SkillDefinition | None:
    return ALL_SKILLS.get(name)
