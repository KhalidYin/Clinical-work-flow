"""
MCP Tool: ADaM Spec Builder
Generates ADaM dataset specifications from SAP endpoint definitions and SDTM sources.
"""

from dataclasses import dataclass, field
from typing import Any


# ── ADaM dataset definitions ─────────────────────────────────────


@dataclass
class ADaMVariable:
    """A single variable in an ADaM dataset."""
    name: str
    label: str
    data_type: str  # Char, Num, Date
    length: int = 200
    source: str = ""  # Source dataset.variable or derivation
    derivation: str = ""  # Detailed derivation rule
    controlled_terms: list[str] = field(default_factory=list)
    significant_digits: int = 0  # For numeric variables
    display_format: str = ""  # SAS format
    core: str = "Req"  # Req, Perm, Cond


@dataclass
class ADaMDataset:
    """An ADaM dataset definition."""
    dataset_name: str  # ADSL, ADAE, ADTTE, ADLB, etc.
    label: str
    structure: str  # One record per subject, BDS, OCCDS
    predecessor: str  # Source SDTM domain(s)
    variables: list[ADaMVariable] = field(default_factory=list)
    derivation_summary: str = ""


# ── Standard ADaM dataset catalog ────────────────────────────────


def build_adsl_spec(trial_phase: str, therapeutic_area: str) -> ADaMDataset:
    """Build ADSL (Subject-Level Analysis Dataset) specification."""
    return ADaMDataset(
        dataset_name="ADSL",
        label="Subject-Level Analysis Dataset",
        structure="One record per subject",
        predecessor="DM",
        derivation_summary="Derived from SDTM.DM with population flags and baseline variables",
        variables=[
            ADaMVariable("STUDYID", "Study Identifier", "Char", 20, source="DM.STUDYID"),
            ADaMVariable("USUBJID", "Unique Subject Identifier", "Char", 50, source="DM.USUBJID",
                        core="Req"),
            ADaMVariable("SUBJID", "Subject Identifier for the Study", "Char", 50, source="DM.SUBJID"),
            ADaMVariable("SITEID", "Study Site Identifier", "Char", 20, source="DM.SITEID"),
            # ── Population flags ──
            ADaMVariable("FASFL", "Full Analysis Set Population Flag", "Char", 1,
                        derivation="Y if randomized and received >=1 dose of study drug; derived from DM.ACTARMCD, EX.EXSTDTC",
                        controlled_terms=["Y", "N"], core="Req"),
            ADaMVariable("SAFFL", "Safety Population Flag", "Char", 1,
                        derivation="Y if received >=1 dose of study drug; derived from EX domain",
                        controlled_terms=["Y", "N"], core="Req"),
            ADaMVariable("PPSFL", "Per-Protocol Set Population Flag", "Char", 1,
                        derivation="Y if completed study without major protocol deviations",
                        controlled_terms=["Y", "N"], core="Cond"),
            ADaMVariable("RANDFL", "Randomized Population Flag", "Char", 1,
                        derivation="Y if randomized (DM.ARMCD is not blank/not 'SCRNFAIL')",
                        controlled_terms=["Y", "N"], core="Req"),
            # ── Treatment ──
            ADaMVariable("TRT01P", "Planned Treatment for Period 01", "Char", 200,
                        source="DM.ARM", core="Req"),
            ADaMVariable("TRT01PN", "Planned Treatment for Period 01 (N)", "Num", 8,
                        source="DM.ARMCD", core="Req"),
            ADaMVariable("TRT01A", "Actual Treatment for Period 01", "Char", 200,
                        source="DM.ACTARM", core="Req"),
            ADaMVariable("TRT01AN", "Actual Treatment for Period 01 (N)", "Num", 8,
                        source="DM.ACTARMCD", core="Req"),
            # ── Demographics ──
            ADaMVariable("AGE", "Age", "Num", 8, source="DM.AGE", core="Req"),
            ADaMVariable("AGEU", "Age Units", "Char", 5, source="DM.AGEU", core="Req"),
            ADaMVariable("AGEGR1", "Pooled Age Group 1", "Char", 20,
                        derivation="Categorize AGE into groups: <65, >=65"),
            ADaMVariable("AGEGR1N", "Pooled Age Group 1 (N)", "Num", 8,
                        derivation="Numeric code for age group"),
            ADaMVariable("SEX", "Sex", "Char", 1, source="DM.SEX", core="Req"),
            ADaMVariable("RACE", "Race", "Char", 100, source="DM.RACE", core="Req"),
            ADaMVariable("RACEN", "Race (N)", "Num", 8,
                        derivation="Coded race (1=White, 2=Black, 3=Asian, 4=Other)"),
            ADaMVariable("ETHNIC", "Ethnicity", "Char", 50, source="DM.ETHNIC"),
            # ── Study dates ──
            ADaMVariable("RFSTDTC", "Subject Reference Start Date", "Date", 19,
                        source="DM.RFSTDTC", core="Req"),
            ADaMVariable("RFENDTC", "Subject Reference End Date", "Date", 19,
                        source="DM.RFENDTC"),
            ADaMVariable("RFXSTDTC", "Date/Time of First Study Treatment Exposure", "Date", 19,
                        derivation="MIN(EX.EXSTDTC)"),
            ADaMVariable("RFXENDTC", "Date/Time of Last Study Treatment Exposure", "Date", 19,
                        derivation="MAX(EX.EXENDTC)"),
            ADaMVariable("TRTSDT", "Date of First Exposure to Treatment", "Date", 9,
                        derivation="datepart(MIN(EX.EXSTDTC)) — numeric date", core="Req"),
            ADaMVariable("TRTEDT", "Date of Last Exposure to Treatment", "Date", 9,
                        derivation="datepart(MAX(EX.EXENDTC)) — numeric date"),
            ADaMVariable("TRTDURD", "Duration of Treatment (Days)", "Num", 8,
                        derivation="TRTEDT - TRTSDT + 1"),
            # ── Disposition ──
            ADaMVariable("DCDECOD", "Disposition Completion Status", "Char", 50,
                        derivation="DS.DSDECOD where DSCAT='DISPOSITION EVENT'"),
            ADaMVariable("EOSSTT", "End of Study Status", "Char", 50,
                        derivation="Derived from DS and survival follow-up"),
            # ── Stratification (Phase III specific) ──
            ADaMVariable("STRATA1", "Stratification Factor 1", "Char", 200),
            ADaMVariable("STRATA2", "Stratification Factor 2", "Char", 200),
            ADaMVariable("COUNTRY", "Country", "Char", 3, source="DM.COUNTRY"),
            ADaMVariable("DMDTC", "Date/Time of Collection", "Date", 19, source="DM.DMDTC"),
        ],
    )


def build_adae_spec() -> ADaMDataset:
    """Build ADAE (Adverse Events Analysis Dataset) specification."""
    return ADaMDataset(
        dataset_name="ADAE",
        label="Adverse Events Analysis Dataset",
        structure="One record per subject per AE (OCCDS)",
        predecessor="AE, ADSL",
        derivation_summary="Key derivations include TEAE flag, treatment period, toxicity grades, relatedness groupings",
        variables=[
            ADaMVariable("STUDYID", "Study Identifier", "Char", 20, source="AE.STUDYID"),
            ADaMVariable("USUBJID", "Unique Subject Identifier", "Char", 50, source="AE.USUBJID",
                        core="Req"),
            ADaMVariable("AESEQ", "Sequence Number", "Num", 8, source="AE.AESEQ", core="Req"),
            # ── AE dictionary terms ──
            ADaMVariable("AETERM", "Reported AE Term", "Char", 200, source="AE.AETERM"),
            ADaMVariable("AEDECOD", "Dictionary-Derived Term (PT)", "Char", 200, source="AE.AEDECOD",
                        core="Req"),
            ADaMVariable("AEBODSYS", "Body System or Organ Class", "Char", 200,
                        source="AE.AEBODSYS", core="Req"),
            ADaMVariable("AEHLT", "High Level Term", "Char", 200, source="AE.AEHLT"),
            ADaMVariable("AEHLGT", "High Level Group Term", "Char", 200, source="AE.AEHLGT"),
            # ── Severity / Seriousness ──
            ADaMVariable("AESEV", "Severity/Intensity", "Char", 8, source="AE.AESEV"),
            ADaMVariable("AESER", "Serious Event", "Char", 1, source="AE.AESER"),
            # ── Treatment-emergent flag ──
            ADaMVariable("TRTEMFL", "Treatment Emergent Analysis Flag", "Char", 1,
                        derivation="Y if AESTDTC >= TRTSDT and AESTDTC <= TRTEDT + 30 days; else N",
                        controlled_terms=["Y", "N"], core="Req"),
            # ── Analysis periods ──
            ADaMVariable("APERIOD", "Period", "Num", 8,
                        derivation="1=on-treatment, 2=post-treatment follow-up"),
            # ── Treatment ──
            ADaMVariable("TRTA", "Actual Treatment", "Char", 200, source="ADSL.TRT01A"),
            ADaMVariable("TRTAN", "Actual Treatment (N)", "Num", 8, source="ADSL.TRT01AN"),
            # ── Dates ──
            ADaMVariable("ASTDT", "Analysis Start Date", "Date", 9,
                        derivation="datepart(AE.AESTDTC)"),
            ADaMVariable("AENDT", "Analysis End Date", "Date", 9,
                        derivation="datepart(AE.AEENDTC)"),
            ADaMVariable("ASTDY", "Analysis Start Relative Day", "Num", 8,
                        derivation="ASTDT - TRTSDT + 1 if ASTDT >= TRTSDT"),
            ADaMVariable("AENDY", "Analysis End Relative Day", "Num", 8,
                        derivation="AENDT - TRTSDT + 1"),
            ADaMVariable("ADURN", "AE Duration (Days)", "Num", 8,
                        derivation="AENDT - ASTDT + 1"),
            ADaMVariable("ADURU", "AE Duration Units", "Char", 5, derivation="'DAYS'"),
            # ── Relatedness ──
            ADaMVariable("AREL", "Causality (Relatedness)", "Char", 1,
                        derivation="Y if AEREL in ('Related','Possibly Related','Probably Related')"),
            ADaMVariable("AERELN", "Causality Group (N)", "Num", 8,
                        derivation="1=Related, 2=Not Related"),
            # ── Outcome ──
            ADaMVariable("AEOUT", "Outcome of AE", "Char", 50, source="AE.AEOUT"),
            # ── Toxicity grade (oncology-specific) ──
            ADaMVariable("ATOXGR", "Analysis Toxicity Grade", "Char", 2,
                        derivation="NCI CTCAE v5.0 grade for this AE; derived from AE.AETOXGR",
                        core="Cond"),
            ADaMVariable("ATOXGRN", "Analysis Toxicity Grade (N)", "Num", 8,
                        derivation="Numeric toxicity grade: 1-5"),
            # ── Action taken ──
            ADaMVariable("AEACN", "Action Taken with Study Treatment", "Char", 50,
                        source="AE.AEACN"),
            ADaMVariable("AEACNOT1", "Action Taken Group 1", "Char", 50,
                        derivation="Grouped action codes"),
        ],
    )


def build_adtte_spec(trial_phase: str) -> ADaMDataset:
    """Build ADTTE (Time-to-Event Analysis Dataset) specification.

    Critical for oncology trials (OS, PFS, etc.) and any survival analyses.
    """
    return ADaMDataset(
        dataset_name="ADTTE",
        label="Time-to-Event Analysis Dataset",
        structure="One record per subject per parameter (BDS)",
        predecessor="ADSL, DS, AE, RS (RECIST), additional sources",
        derivation_summary="Key: CNSR (censoring flag), ADT (analysis time), PARAMCD",
        variables=[
            ADaMVariable("STUDYID", "Study Identifier", "Char", 20, source="ADSL.STUDYID"),
            ADaMVariable("USUBJID", "Unique Subject Identifier", "Char", 50, source="ADSL.USUBJID",
                        core="Req"),
            ADaMVariable("PARAMCD", "Parameter Code", "Char", 8, core="Req",
                        derivation="OS, PFS, PFS_IRC, TTR, DOR, DFS, EFS"),
            ADaMVariable("PARAM", "Parameter", "Char", 200, core="Req",
                        derivation="Overall Survival, Progression-Free Survival, Time to Response, Duration of Response, etc."),
            ADaMVariable("AVAL", "Analysis Value (Time to Event)", "Num", 8, core="Req",
                        derivation="Time from origin date to event/censor date in days"),
            ADaMVariable("CNSR", "Censoring Flag", "Num", 8, core="Req",
                        derivation="0=event, 1=censored; based on complex rules per PARAMCD"),
            ADaMVariable("EVNTDESC", "Event Description", "Char", 200,
                        derivation="Description of the event that occurred (or censoring reason)"),
            ADaMVariable("ADT", "Analysis Date", "Date", 9,
                        derivation="Date of event or censoring"),
            ADaMVariable("STARTDT", "Time to Event Origin Date", "Date", 9,
                        derivation="Randomization date (or first dose date per SAP)"),
            ADaMVariable("CNSRDT", "Censoring Date", "Date", 9,
                        derivation="Date of last known to be event-free"),
            # ── Stratification ──
            ADaMVariable("STRATA1", "Stratification Factor 1", "Char", 200),
            ADaMVariable("STRATA2", "Stratification Factor 2", "Char", 200),
            # ── Treatment ──
            ADaMVariable("TRTA", "Actual Treatment", "Char", 200, source="ADSL.TRT01A"),
            ADaMVariable("TRTAN", "Actual Treatment (N)", "Num", 8, source="ADSL.TRT01AN"),
            # ── Population ──
            ADaMVariable("FASFL", "FAS Population Flag", "Char", 1, source="ADSL.FASFL"),
        ],
    )


def generate_adam_spec(dataset_name: str, trial_phase: str = "phase_iii",
                       therapeutic_area: str = "non_oncology") -> dict[str, Any]:
    """
    Generate a complete ADaM dataset specification.

    This is the core function of the ADaM Spec Builder MCP tool.
    Reads SAP endpoint definitions and SDTM source metadata to produce
    a complete ADaM specification document.
    """
    builders = {
        "ADSL": build_adsl_spec,
        "ADAE": build_adae_spec,
        "ADTTE": lambda tp, ta: build_adtte_spec(tp),
    }

    builder = builders.get(dataset_name)
    if builder is None:
        raise ValueError(f"Unknown ADaM dataset: {dataset_name}. Known: {list(builders)}")

    if dataset_name == "ADSL":
        ds = builder(trial_phase, therapeutic_area)
    elif dataset_name == "ADTTE":
        ds = builder(trial_phase, therapeutic_area)
    elif dataset_name == "ADAE":
        ds = builder()
    else:
        ds = builder(trial_phase, therapeutic_area)

    return {
        "dataset": ds.dataset_name,
        "label": ds.label,
        "structure": ds.structure,
        "predecessor": ds.predecessor,
        "derivation_summary": ds.derivation_summary,
        "trial_phase": trial_phase,
        "therapeutic_area": therapeutic_area,
        "variables": [
            {
                "name": v.name,
                "label": v.label,
                "type": v.data_type,
                "length": v.length,
                "source": v.source,
                "derivation": v.derivation,
                "core": v.core,
                "controlled_terms": v.controlled_terms,
                "significant_digits": v.significant_digits,
            }
            for v in ds.variables
        ],
    }
