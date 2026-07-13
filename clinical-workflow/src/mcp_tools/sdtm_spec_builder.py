"""
MCP Tool: SDTM Spec Builder
Converts raw clinical data mapping into SDTM domain specifications.
"""

from dataclasses import dataclass, field
from typing import Any

# ── SDTM Domain definitions ──────────────────────────────────────

@dataclass
class SDTMVariable:
    """A single variable in an SDTM domain."""
    name: str
    label: str
    data_type: str  # Char, Num, Date, etc.
    length: int = 200
    mandatory: bool = False
    controlled_terms: list[str] = field(default_factory=list)
    derivation: str = ""  # Derivation logic
    source_crf: str = ""  # Source CRF field
    comments: str = ""


@dataclass
class SDTMDomain:
    """An SDTM domain (DM, AE, CM, LB, VS, etc.)."""
    domain_code: str  # 2-char code
    domain_name: str  # Full name
    domain_class: str  # Interventions, Events, Findings, Special Purpose
    description: str
    variables: list[SDTMVariable] = field(default_factory=list)
    supmap: list[dict[str, str]] = field(default_factory=list)  # SUPPQUAL mappings

    @property
    def key_variables(self) -> list[SDTMVariable]:
        """Required identifier variables: STUDYID, DOMAIN, USUBJID, --SEQ."""
        key_names = {"STUDYID", "DOMAIN", "USUBJID", f"{self.domain_code}SEQ"}
        return [v for v in self.variables if v.name in key_names]


# ── Standard SDTM Domain catalog ─────────────────────────────────

STANDARD_DOMAINS: dict[str, SDTMDomain] = {
    "DM": SDTMDomain(
        domain_code="DM", domain_name="Demographics",
        domain_class="Special Purpose",
        description="Subject-level demographics and population flags",
        variables=[
            SDTMVariable("STUDYID", "Study Identifier", "Char", 20, mandatory=True),
            SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, mandatory=True),
            SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 50, mandatory=True),
            SDTMVariable("SUBJID", "Subject Identifier for the Study", "Char", 50),
            SDTMVariable("RFSTDTC", "Subject Reference Start Date/Time", "Date", 19),
            SDTMVariable("RFENDTC", "Subject Reference End Date/Time", "Date", 19),
            SDTMVariable("SITEID", "Study Site Identifier", "Char", 20),
            SDTMVariable("BRTHDTC", "Date/Time of Birth", "Date", 19),
            SDTMVariable("AGE", "Age", "Num", 8),
            SDTMVariable("AGEU", "Age Units", "Char", 5, controlled_terms=["YEARS"]),
            SDTMVariable("SEX", "Sex", "Char", 1, controlled_terms=["M", "F"]),
            SDTMVariable("RACE", "Race", "Char", 100),
            SDTMVariable("ETHNIC", "Ethnicity", "Char", 50),
            SDTMVariable("ARMCD", "Planned Arm Code", "Char", 20),
            SDTMVariable("ARM", "Description of Planned Arm", "Char", 200),
            SDTMVariable("ACTARMCD", "Actual Arm Code", "Char", 20),
            SDTMVariable("ACTARM", "Description of Actual Arm", "Char", 200),
            SDTMVariable("COUNTRY", "Country", "Char", 3, controlled_terms=["USA", "CHN", "JPN"]),
        ],
    ),
    "AE": SDTMDomain(
        domain_code="AE", domain_name="Adverse Events",
        domain_class="Events",
        description="Adverse event records per subject per event",
        variables=[
            SDTMVariable("STUDYID", "Study Identifier", "Char", 20, mandatory=True),
            SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, mandatory=True),
            SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 50, mandatory=True),
            SDTMVariable("AESEQ", "Sequence Number", "Num", 8, mandatory=True),
            SDTMVariable("AETERM", "Reported Term for the Adverse Event", "Char", 200),
            SDTMVariable("AEMODIFY", "Modified Reported Term", "Char", 200),
            SDTMVariable("AELLT", "Lowest Level Term", "Char", 200),
            SDTMVariable("AELLTCD", "Lowest Level Term Code", "Num", 8),
            SDTMVariable("AEDECOD", "Dictionary-Derived Term", "Char", 200),
            SDTMVariable("AEPTCD", "Preferred Term Code", "Num", 8),
            SDTMVariable("AEHLT", "High Level Term", "Char", 200),
            SDTMVariable("AEHLTCD", "High Level Term Code", "Num", 8),
            SDTMVariable("AEHLGT", "High Level Group Term", "Char", 200),
            SDTMVariable("AEHLGTCD", "High Level Group Term Code", "Num", 8),
            SDTMVariable("AEBODSYS", "Body System or Organ Class", "Char", 200),
            SDTMVariable("AESOC", "Primary System Organ Class", "Char", 200),
            SDTMVariable("AESEV", "Severity/Intensity", "Char", 8,
                         controlled_terms=["MILD", "MODERATE", "SEVERE"]),
            SDTMVariable("AESER", "Serious Event", "Char", 1, controlled_terms=["Y", "N"]),
            SDTMVariable("AEACN", "Action Taken with Study Treatment", "Char", 50),
            SDTMVariable("AEREL", "Causality", "Char", 50),
            SDTMVariable("AEOUT", "Outcome of Adverse Event", "Char", 50,
                         controlled_terms=["RECOVERED/RESOLVED", "RECOVERING/RESOLVING",
                                          "NOT RECOVERED/NOT RESOLVED", "FATAL", "UNKNOWN"]),
            SDTMVariable("AESTDTC", "Start Date/Time of AE", "Date", 19),
            SDTMVariable("AEENDTC", "End Date/Time of AE", "Date", 19),
            SDTMVariable("AESTDY", "Study Day of Start of AE", "Num", 8),
            SDTMVariable("AEENDY", "Study Day of End of AE", "Num", 8),
        ],
    ),
    "CM": SDTMDomain(
        domain_code="CM", domain_name="Concomitant Medications",
        domain_class="Interventions",
        description="Concomitant and prior medication records",
        variables=[
            SDTMVariable("STUDYID", "Study Identifier", "Char", 20, mandatory=True),
            SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, mandatory=True),
            SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 50, mandatory=True),
            SDTMVariable("CMSEQ", "Sequence Number", "Num", 8, mandatory=True),
            SDTMVariable("CMTRT", "Reported Name of Drug, Med, or Therapy", "Char", 200),
            SDTMVariable("CMMODIFY", "Modified Reported Name", "Char", 200),
            SDTMVariable("CMDECOD", "Standardized Medication Name", "Char", 200),
            SDTMVariable("CMCAT", "Category of Medication", "Char", 50),
            SDTMVariable("CMSCAT", "Subcategory of Medication", "Char", 50),
            SDTMVariable("CMINDC", "Indication", "Char", 200),
            SDTMVariable("CMDOSE", "Dose per Administration", "Num", 8),
            SDTMVariable("CMDOSU", "Dose Units", "Char", 20),
            SDTMVariable("CMDOSFRQ", "Dosing Frequency per Interval", "Char", 50),
            SDTMVariable("CMROUTE", "Route of Administration", "Char", 50),
            SDTMVariable("CMSTDTC", "Start Date/Time of Medication", "Date", 19),
            SDTMVariable("CMENDTC", "End Date/Time of Medication", "Date", 19),
            SDTMVariable("CMSTDY", "Study Day of Start of Medication", "Num", 8),
            SDTMVariable("CMENDY", "Study Day of End of Medication", "Num", 8),
        ],
    ),
    "LB": SDTMDomain(
        domain_code="LB", domain_name="Laboratory Test Results",
        domain_class="Findings",
        description="Lab test results per subject per visit per test",
        variables=[
            SDTMVariable("STUDYID", "Study Identifier", "Char", 20, mandatory=True),
            SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, mandatory=True),
            SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 50, mandatory=True),
            SDTMVariable("LBSEQ", "Sequence Number", "Num", 8, mandatory=True),
            SDTMVariable("LBTESTCD", "Lab Test or Examination Short Name", "Char", 8),
            SDTMVariable("LBTEST", "Lab Test or Examination Name", "Char", 40),
            SDTMVariable("LBCAT", "Category for Lab Test", "Char", 50),
            SDTMVariable("LBORRES", "Result or Finding in Original Units", "Char", 200),
            SDTMVariable("LBORRESU", "Original Units", "Char", 20),
            SDTMVariable("LBORNRLO", "Reference Range Lower Limit-Orig Unit", "Char", 20),
            SDTMVariable("LBORNRHI", "Reference Range Upper Limit-Orig Unit", "Char", 20),
            SDTMVariable("LBSTRESC", "Character Result/Finding in Std Format", "Char", 200),
            SDTMVariable("LBSTRESN", "Numeric Result/Finding in Standard Units", "Num", 8),
            SDTMVariable("LBSTRESU", "Standard Units", "Char", 20),
            SDTMVariable("LBSTNRLO", "Reference Range Lower Limit-Std Units", "Num", 8),
            SDTMVariable("LBSTNRHI", "Reference Range Upper Limit-Std Units", "Num", 8),
            SDTMVariable("LBNRIND", "Reference Range Indicator", "Char", 20,
                         controlled_terms=["LOW", "NORMAL", "HIGH", "ABNORMAL"]),
            SDTMVariable("LBBLFL", "Baseline Flag", "Char", 1, controlled_terms=["Y"]),
            SDTMVariable("VISITNUM", "Visit Number", "Num", 3),
            SDTMVariable("VISIT", "Visit Name", "Char", 100),
            SDTMVariable("VISITDY", "Planned Study Day of Visit", "Num", 8),
            SDTMVariable("LBDTC", "Date/Time of Specimen Collection", "Date", 19),
            SDTMVariable("LBDY", "Study Day of Specimen Collection", "Num", 8),
        ],
    ),
    "VS": SDTMDomain(
        domain_code="VS", domain_name="Vital Signs",
        domain_class="Findings",
        description="Vital signs measurements per subject per visit",
        variables=[
            SDTMVariable("STUDYID", "Study Identifier", "Char", 20, mandatory=True),
            SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, mandatory=True),
            SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 50, mandatory=True),
            SDTMVariable("VSSEQ", "Sequence Number", "Num", 8, mandatory=True),
            SDTMVariable("VSTESTCD", "Vital Signs Test Short Name", "Char", 8),
            SDTMVariable("VSTEST", "Vital Signs Test Name", "Char", 40),
            SDTMVariable("VSORRES", "Result or Finding in Original Units", "Char", 200),
            SDTMVariable("VSORRESU", "Original Units", "Char", 20),
            SDTMVariable("VSSTRESC", "Character Result/Finding in Std Format", "Char", 200),
            SDTMVariable("VSSTRESN", "Numeric Result/Finding in Standard Units", "Num", 8),
            SDTMVariable("VSSTRESU", "Standard Units", "Char", 20),
            SDTMVariable("VSBLFL", "Baseline Flag", "Char", 1, controlled_terms=["Y"]),
            SDTMVariable("VISITNUM", "Visit Number", "Num", 3),
            SDTMVariable("VISIT", "Visit Name", "Char", 100),
            SDTMVariable("VSDTC", "Date/Time of Vital Signs", "Date", 19),
            SDTMVariable("VSDY", "Study Day of Vital Signs", "Num", 8),
        ],
    ),
    "EX": SDTMDomain(
        domain_code="EX", domain_name="Exposure",
        domain_class="Interventions",
        description="Study treatment exposure records",
        variables=[
            SDTMVariable("STUDYID", "Study Identifier", "Char", 20, mandatory=True),
            SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, mandatory=True),
            SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 50, mandatory=True),
            SDTMVariable("EXSEQ", "Sequence Number", "Num", 8, mandatory=True),
            SDTMVariable("EXTRT", "Name of Treatment", "Char", 200),
            SDTMVariable("EXDOSE", "Dose per Administration", "Num", 8),
            SDTMVariable("EXDOSU", "Dose Units", "Char", 20),
            SDTMVariable("EXDOSFRQ", "Dosing Frequency", "Char", 50),
            SDTMVariable("EXROUTE", "Route of Administration", "Char", 50),
            SDTMVariable("EXSTDTC", "Start Date/Time of Treatment", "Date", 19),
            SDTMVariable("EXENDTC", "End Date/Time of Treatment", "Date", 19),
            SDTMVariable("EXSTDY", "Study Day of Start of Treatment", "Num", 8),
            SDTMVariable("EXENDY", "Study Day of End of Treatment", "Num", 8),
        ],
    ),
    "DS": SDTMDomain(
        domain_code="DS", domain_name="Disposition",
        domain_class="Events",
        description="Subject disposition (screening, randomization, completion, discontinuation)",
        variables=[
            SDTMVariable("STUDYID", "Study Identifier", "Char", 20, mandatory=True),
            SDTMVariable("DOMAIN", "Domain Abbreviation", "Char", 2, mandatory=True),
            SDTMVariable("USUBJID", "Unique Subject Identifier", "Char", 50, mandatory=True),
            SDTMVariable("DSSEQ", "Sequence Number", "Num", 8, mandatory=True),
            SDTMVariable("DSTERM", "Reported Term for the Disposition Event", "Char", 200),
            SDTMVariable("DSDECOD", "Standardized Disposition Term", "Char", 200),
            SDTMVariable("DSCAT", "Category for Disposition", "Char", 50),
            SDTMVariable("DSSTDTC", "Start Date/Time of Disposition", "Date", 19),
        ],
    ),
}

# ── CRF to SDTM mapping logic ────────────────────────────────────


@dataclass
class CRF2SDTMMapping:
    """Maps a single CRF field to an SDTM variable."""
    crf_page: str
    crf_field: str
    sdtm_domain: str
    sdtm_variable: str
    transformation: str = ""  # Direct copy, format change, code mapping, etc.
    rule: str = ""  # Detailed mapping rule


def generate_sdtm_spec(
    domain_code: str,
    crf_mappings: list[CRF2SDTMMapping],
    domain: SDTMDomain | None = None,
) -> dict[str, Any]:
    """
    Generate an SDTM domain specification from CRF mappings.

    This is the core function of the SDTM Spec Builder MCP tool.
    In a full implementation, this would read from an aCRF (annotated CRF)
    and produce a complete SDTM mapping specification document.
    """
    domain = domain or STANDARD_DOMAINS.get(domain_code)
    if domain is None:
        raise ValueError(f"Unknown SDTM domain: {domain_code}")

    # Merge CRF mappings into variable derivations
    mapping_by_var = {m.sdtm_variable: m for m in crf_mappings}

    spec = {
        "domain": domain_code,
        "name": domain.domain_name,
        "class": domain.domain_class,
        "description": domain.description,
        "dataset_structure": "One record per subject per event"
        if domain.domain_class == "Events"
        else "One record per subject per finding per visit"
        if domain.domain_class == "Findings"
        else "One record per subject per intervention"
        if domain.domain_class == "Interventions"
        else "One record per subject",
        "keys": [v.name for v in domain.key_variables],
        "variables": [],
        "crf_annotations": [],
    }

    for var in domain.variables:
        mapping = mapping_by_var.get(var.name)
        var_spec = {
            "name": var.name,
            "label": var.label,
            "type": var.data_type,
            "length": var.length,
            "mandatory": var.mandatory,
            "controlled_terms": var.controlled_terms,
            "derivation": mapping.transformation if mapping else var.derivation,
            "source_crf": f"{mapping.crf_page} → {mapping.crf_field}" if mapping else "",
        }
        spec["variables"].append(var_spec)
        if mapping:
            spec["crf_annotations"].append({
                "crf_page": mapping.crf_page,
                "crf_field": mapping.crf_field,
                "sdtm_variable": mapping.sdtm_variable,
                "rule": mapping.rule,
            })

    return spec
