"""
Clinical Workflow Knowledge Base.
Contains CDISC standards, regulatory guidance, and domain-specific knowledge.
"""

from dataclasses import dataclass
from typing import Any


# ── CDISC Standards Reference ─────────────────────────────────────


@dataclass
class CDISCStandard:
    name: str
    version: str
    description: str
    key_concepts: list[str]
    url: str = ""


CDISC_KNOWLEDGE: dict[str, CDISCStandard] = {
    "sdtm": CDISCStandard(
        name="Study Data Tabulation Model (SDTM)",
        version="v2.0 / SDTMIG v3.4",
        description="Model for organizing and formatting clinical trial data for regulatory submission",
        key_concepts=[
            "Domains: DM, AE, CM, LB, VS, EX, DS, MH, EG, PE, QS, etc.",
            "Variable classes: Identifier, Topic, Timing, Qualifier (Grouping, Result, Synonym, Record)",
            "Core variable designations: Req (Required), Exp (Expected), Perm (Permissible)",
            "SUPPQUAL for non-standard variables that cannot be represented in parent domain",
            "RELREC for relationships across domains (e.g., AE → LB for lab-related AEs)",
            "Trial Design domains: TA (Trial Arms), TE (Trial Elements), TV (Trial Visits)",
            "XPT v5 transport file format for FDA submissions",
        ],
    ),
    "adam": CDISCStandard(
        name="Analysis Data Model (ADaM)",
        version="v2.1 / ADaMIG v1.3",
        description="Model for creating analysis-ready datasets from SDTM data",
        key_concepts=[
            "ADSL: Subject-Level Analysis Dataset — one row per subject, population flags, baseline",
            "BDS: Basic Data Structure — one row per subject per parameter per analysis timepoint",
            "OCCDS: Occurrence Data Structure — for events (ADAE uses ADaM OCCDS)",
            "PARAM/PARAMCD: Parameter name and code (for BDS datasets)",
            "AVAL/AVALC: Analysis value (numeric/character)",
            "ADT/ADY: Analysis date / Analysis relative day",
            "ABLFL: Baseline record flag",
            "DTYPE: Derivation type (LOCF, WOCF, AVERAGE, etc.)",
            "ANLxxFL: Analysis record flag (select which record to use in analysis)",
            "ALLxxFL: All records flag",
        ],
    ),
    "define_xml": CDISCStandard(
        name="Define-XML",
        version="v2.0",
        description="Machine-readable metadata describing SDTM and ADaM datasets for regulatory submission",
        key_concepts=[
            "ItemGroupDef: Dataset-level metadata (domain/dataset name, structure, keys)",
            "ItemDef: Variable-level metadata (name, label, type, length, origin, codelist)",
            "CodeList: Controlled terminology definitions with coded values",
            "ValueLevelDef: Value-level metadata where variable meaning depends on another variable's value",
            "MethodDef: Computational methods for derived variables",
            "CommentDef: Comments on specific items",
            "Must validate against CDISC define.xml schema",
        ],
    ),
    "controlled_terminology": CDISCStandard(
        name="Controlled Terminology",
        version="NCI Thesaurus / CDISC CT (quarterly updates)",
        description="Standardized code lists for all CDISC variables",
        key_concepts=[
            "NCI Thesaurus codes for all standard terms",
            "CDISC CT packages published quarterly",
            "Sponsor-defined terms can extend but not contradict standard terms",
            "SYNONYM qualifier for non-standard synonyms of CT terms",
            "SEX: M, F, U (Unknown), UNDIFFERENTIATED",
            "AESEV: MILD, MODERATE, SEVERE",
            "AEOUT: various outcome codes",
        ],
    ),
}

# ── Regulatory Guidance ────────────────────────────────────────────


REGULATORY_GUIDANCE: dict[str, dict[str, str]] = {
    "FDA": {
        "TCG": "Study Data Technical Conformance Guide — FDA expectations for electronic submissions",
        "eCTD": "Electronic Common Technical Document — submission format specification",
        "21_CFR_11": "Electronic records / electronic signatures requirements",
    },
    "ICH": {
        "E3": "Structure and content of Clinical Study Reports (CSR)",
        "E6": "Good Clinical Practice (GCP) — data integrity and quality",
        "E9": "Statistical principles for clinical trials",
        "E9_R1": "Estimands and sensitivity analysis in clinical trials (addendum to E9)",
        "E10": "Choice of control group in clinical trials",
    },
    "NMPA_China": {
        "data_submission": "NMPA now requires CDISC-compliant electronic submissions for new drug applications",
        "statistical_guidelines": "NMPA Statistical Guidelines for Clinical Trials (similar to ICH E9)",
    },
}

# ── Phase-specific Knowledge ────────────────────────────────────────


PHASE_KNOWLEDGE: dict[str, dict[str, Any]] = {
    "phase_i": {
        "primary_focus": "Safety, tolerability, pharmacokinetics (PK), pharmacodynamics (PD)",
        "sample_size_range": "20-80 subjects",
        "tfl_volume": "20-50 TFLs",
        "cdisc_rigor": "Optional/light — full SDTM/ADaM may not be required",
        "special_tools": ["Phoenix WinNonlin", "NONMEM"],
        "key_analyses": [
            "PK parameters (Cmax, AUC, Tmax, t1/2)",
            "Dose proportionality",
            "Food effect (if applicable)",
            "QT/QTc interval analysis",
        ],
        "timeline": "Days to weeks from DBL to TFL delivery",
    },
    "phase_ii": {
        "primary_focus": "Dose-finding, proof-of-concept, preliminary efficacy",
        "sample_size_range": "100-300 subjects",
        "tfl_volume": "50-150 TFLs",
        "cdisc_rigor": "Moderate — many Phase II studies now included in regulatory packages",
        "key_analyses": [
            "Dose-response modeling (MCP-Mod)",
            "Proof-of-concept efficacy comparison",
            "Dose selection decision support",
            "Subgroup analyses for dose optimization",
        ],
        "timeline": "Weeks to months",
    },
    "phase_iii": {
        "primary_focus": "Confirmatory efficacy, comprehensive safety database",
        "sample_size_range": "300-3,000+ subjects",
        "tfl_volume": "200-500+ TFLs",
        "cdisc_rigor": "Full CDISC compliance required for regulatory submission",
        "key_analyses": [
            "Primary endpoint confirmatory analysis",
            "Key secondary endpoints (hierarchical testing)",
            "Comprehensive safety (TEAE, SAE, labs, vitals, ECG)",
            "Subgroup analyses",
            "Sensitivity analyses",
            "ISS/ISE (Integrated Summary of Safety/Efficacy) pooling across studies",
        ],
        "timeline": "6-18 months from DBL to submission",
    },
}

# ── Therapeutic Area-specific Knowledge ────────────────────────────


TA_KNOWLEDGE: dict[str, dict[str, Any]] = {
    "oncology": {
        "key_endpoints": ["OS", "PFS", "ORR", "DOR", "DCR", "TTR"],
        "response_criteria": "RECIST 1.1 (solid tumors) / iRECIST / Lugano (lymphoma) / RANO (CNS)",
        "specialized_adam": {
            "ADTR": "Tumor Response — visit-level tumor assessments with derived BOR, ORR",
            "ADTTE": "Time-to-Event — critical: OS, PFS with complex censoring rules",
        },
        "key_figures": [
            "Kaplan-Meier curves (OS, PFS) with at-risk table",
            "Waterfall plot (best percent change in tumor size)",
            "Swimmer plot (treatment duration + response + events)",
            "Spider plot (longitudinal tumor burden)",
            "Forest plot (subgroup hazard ratios)",
        ],
        "safety_specifics": [
            "NCI CTCAE v5.0 toxicity grading",
            "Treatment-emergent AE flagging for complex regimens",
            "Prior/concomitant anti-cancer therapy capture",
            "IRC (Independent Review Committee) reconciliation",
        ],
        "dictionary": "MedDRA (Medical Dictionary for Regulatory Activities)",
    },
    "non_oncology": {
        "key_endpoints": "Varies by indication: change from baseline, responder analysis, time-to-event",
        "common_areas": {
            "cardiovascular": ["MACE", "blood pressure", "lipid panels", "QT/QTc"],
            "diabetes": ["HbA1c change", "fasting plasma glucose", "hypoglycemic events"],
            "respiratory": ["FEV1 change", "exacerbation rate", "SGRQ score"],
            "dermatology": ["PASI", "IGA", "DLQI"],
            "neuroscience": ["ADAS-Cog", "CDR-SB", "MMSE (Alzheimer's)", "UPDRS (Parkinson's)"],
        },
        "safety_specifics": [
            "Lab parameters, ECG, vital signs more central",
            "Patient-reported outcomes (PROs) common: SF-36, EQ-5D",
        ],
    },
}

# ── AI Prompt Templates for Each Stage ─────────────────────────────


AI_PROMPT_TEMPLATES: dict[str, dict[str, str]] = {
    "sdtm_mapping": {
        "system": "You are an expert CDISC SDTM programmer. Given the following raw data structure and CRF annotations, produce the SDTM domain mapping specification.",
        "output_format": "For each variable: SDTM variable name, source CRF field, transformation rule, controlled terminology check.",
    },
    "adam_derivation": {
        "system": "You are an expert ADaM programmer. Given the SAP endpoint definitions and SDTM source data, derive the ADaM dataset specification.",
        "output_format": "For each ADaM variable: name, label, type, source (SDTM.variable), derivation logic, analysis flag rules.",
    },
    "tfl_programming": {
        "system": "You are an expert TFL programmer. Given the TFL shell and ADaM data specification, write the TFL generation code.",
        "output_format": "SAS/R/Python code with: data selection, sorting, analysis procedure, output generation (RTF/PDF), footnote insertion.",
    },
    "sap_review": {
        "system": "You are an expert clinical biostatistician. Review this SAP against the protocol and ICH E9 guidelines.",
        "output_format": "Section-by-section review with: issue severity (Critical/Major/Minor), description, suggested fix.",
    },
    "qc_discrepancy": {
        "system": "You are an expert QC programmer. Two independent programs produced different results for the same TFL. Analyze the code differences and determine the correct result based on the SAP.",
        "output_format": "Discrepancy location, root cause analysis (spec interpretation, coding error, data issue), recommended resolution.",
    },
}

# ── Dataset Traceability Matrix Template ──────────────────────────


TRACEABILITY_TEMPLATE: dict[str, str] = {
    "columns": [
        "CRF Page / Field",
        "SDTM Domain / Variable",
        "ADaM Dataset / Variable",
        "TFL ID / Column",
    ],
    "description": (
        "End-to-end traceability from eCRF source data through SDTM and ADaM "
        "to the final TFL outputs submitted to regulators."
    ),
}
