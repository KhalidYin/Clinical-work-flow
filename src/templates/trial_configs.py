"""
Trial template configurations for Phase I, II, III and Oncology/Non-Oncology.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrialTemplate:
    """A pre-configured trial template that adjusts AI behavior."""
    name: str
    trial_phase: str
    therapeutic_area: str
    domains: list[str]
    adam_datasets: list[str]
    mandatory_tfls: list[str]
    special_analyses: list[str]
    ai_instructions: dict[str, str] = field(default_factory=dict)


PHASE_I_ONCOLOGY = TrialTemplate(
    name="Phase I Oncology (First-in-Human)",
    trial_phase="phase_i",
    therapeutic_area="oncology",
    domains=["DM", "AE", "CM", "LB", "VS", "EX", "DS"],
    adam_datasets=["ADSL", "ADAE", "ADLB", "ADTTE"],
    mandatory_tfls=[
        "T14.1.1 Subject Disposition",
        "T14.1.2 Demographics",
        "T14.3.1 TEAE Overview",
        "T14.3.2 TEAEs by SOC/PT",
        "L16.2.1 Disposition Listing",
        "L16.2.4 AE Listing",
    ],
    special_analyses=[
        "DLT (Dose-Limiting Toxicity) evaluation",
        "PK parameter summary (Cmax, AUC, Tmax, t1/2)",
        "MTD/MAD determination support",
    ],
    ai_instructions={
        "sdtm_priority": "Focus on AE, EX (dose escalation cohorts), and LB (safety labs)",
        "adam_priority": "Derive DLT flags, cohort assignment, cumulative dose",
        "tfl_priority": "Rapid turnaround — minimize TFL count, focus on safety",
        "qc_intensity": "Standard QC (not full double programming)",
    },
)

PHASE_III_ONCOLOGY = TrialTemplate(
    name="Phase III Oncology (Pivotal)",
    trial_phase="phase_iii",
    therapeutic_area="oncology",
    domains=["DM", "AE", "CM", "LB", "VS", "EX", "DS", "MH", "EG", "QS"],
    adam_datasets=["ADSL", "ADAE", "ADTTE", "ADTR", "ADLB", "ADVS", "ADCM"],
    mandatory_tfls=[
        "T14.1.1 Disposition",
        "T14.1.2 Demographics & Baseline",
        "T14.2.1 Primary Efficacy (OS/PFS)",
        "T14.2.2 Key Secondary Endpoints",
        "T14.2.3 ORR per RECIST 1.1",
        "F14.2.1 K-M Plot of OS",
        "F14.2.2 K-M Plot of PFS",
        "F14.2.3 Waterfall Plot",
        "F14.2.4 Swimmer Plot",
        "T14.3.1 TEAE Overview",
        "T14.3.2 TEAEs by SOC/PT",
        "T14.3.3 Serious TEAEs",
        "L16.2.1 Disposition Listing",
        "L16.2.4 AE Listing",
        "L16.2.6 SAE Listing",
    ],
    special_analyses=[
        "OS/PFS primary analysis (stratified log-rank, Cox PH)",
        "Subgroup forest plots",
        "RECIST 1.1 response analysis (BOR, ORR, DOR)",
        "IRC vs Investigator assessment sensitivity",
        "IDMC interim analysis at 50% and 70% events",
        "CTCAE toxicity grade shift tables",
        "Prior anti-cancer therapy subgroup analyses",
    ],
    ai_instructions={
        "sdtm_priority": "Full CDISC compliance — all domains, full SUPPQUAL, RELREC for cross-domain relationships",
        "adam_priority": "ADTTE censoring rules per SAP — check each PARAMCD. ADTR derive BOR per RECIST 1.1 algorithm. Population flags must be precise.",
        "tfl_priority": "Program to submission quality. Every number must be independently reproducible.",
        "qc_intensity": "Full double programming for all pivotal TFLs. Pinnacle 21 strict mode with 0 errors.",
    },
)

PHASE_III_NON_ONCOLOGY = TrialTemplate(
    name="Phase III Non-Oncology (Pivotal)",
    trial_phase="phase_iii",
    therapeutic_area="non_oncology",
    domains=["DM", "AE", "CM", "LB", "VS", "EX", "DS", "MH", "EG", "QS"],
    adam_datasets=["ADSL", "ADAE", "ADLB", "ADVS", "ADEF"],
    mandatory_tfls=[
        "T14.1.1 Disposition",
        "T14.1.2 Demographics & Baseline",
        "T14.2.1 Primary Efficacy Endpoint",
        "T14.2.2 Key Secondary Endpoints",
        "F14.2.1 Forest Plot of Subgroup Analysis",
        "T14.3.1 TEAE Overview",
        "T14.3.2 TEAEs by SOC/PT",
        "L16.2.1 Disposition Listing",
        "L16.2.4 AE Listing",
    ],
    special_analyses=[
        "Primary endpoint: MMRM / ANCOVA change from baseline",
        "Multiple imputation sensitivity for missing data",
        "Multiplicity adjustment (hierarchical gatekeeping)",
        "Responder analysis",
    ],
    ai_instructions={
        "sdtm_priority": "Full CDISC compliance — ensure findings domains (LB, VS, EG) are complete",
        "adam_priority": "BDS structure for efficacy endpoints. ABLFL for baseline. Multiple analysis flags (ANL01FL for MMRM, ANL02FL for ANCOVA).",
        "tfl_priority": "Consistent formatting across 200+ TFLs. Cross-table population count consistency is critical.",
        "qc_intensity": "Full double programming for pivotal TFLs. Pinnacle 21 for all ADaM datasets.",
    },
)


ALL_TEMPLATES: dict[str, TrialTemplate] = {
    "phase_i_oncology": PHASE_I_ONCOLOGY,
    "phase_iii_oncology": PHASE_III_ONCOLOGY,
    "phase_iii_non_oncology": PHASE_III_NON_ONCOLOGY,
}


def get_template(trial_phase: str, therapeutic_area: str) -> TrialTemplate | None:
    key = f"{trial_phase}_{therapeutic_area}"
    return ALL_TEMPLATES.get(key)
