"""
MCP Tool: TFL Renderer
Generates Tables, Figures, and Listings from ADaM datasets.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class TFLType(StrEnum):
    TABLE = "table"
    FIGURE = "figure"
    LISTING = "listing"


class OutputFormat(StrEnum):
    RTF = "rtf"
    PDF = "pdf"
    HTML = "html"
    XPT = "xpt"


@dataclass
class TFLShell:
    """A TFL shell (mock-up) defining one table/figure/listing."""

    tfl_id: str  # e.g., "T14.1.1" (Table 14.1.1)
    tfl_type: TFLType
    title: str
    population: str  # Analysis population (FAS, Safety, PP, ITT)
    source_dataset: str  # Primary ADaM dataset
    columns: list[dict[str, str]] = field(default_factory=list)
    footnotes: list[str] = field(default_factory=list)
    analysis_method: str = ""  # Descriptive, ANCOVA, MMRM, KM, Cox PH, etc.
    subgroup: str = ""  # Subgroup variable name
    sorting: str = ""  # Sorting specification
    page_layout: str = "landscape"  # portrait or landscape
    data_selection: dict[str, Any] = field(default_factory=dict)

    @property
    def number(self) -> str:
        return self.tfl_id

    @property
    def section(self) -> str:
        parts = self.tfl_id.lstrip("TFL").split(".")
        if len(parts) >= 2:
            return f"{parts[0]}.{parts[1]}"
        return ""


# ── Standard TFL shell catalog per CSR section ───────────────────

STANDARD_TFL_SHELLS: list[TFLShell] = [
    # ── Section 14.1: Disposition ──
    TFLShell(
        tfl_id="T14.1.1",
        tfl_type=TFLType.TABLE,
        title="Subject Disposition",
        population="All Randomized",
        source_dataset="ADSL",
        columns=[
            {"header": "Disposition Category", "var": "DCDECOD"},
            {"header": "Treatment A (N=XX)", "var": "TRT01AN"},
            {"header": "Treatment B (N=XX)", "var": "TRT01AN"},
            {"header": "Total (N=XX)", "var": "_total_"},
        ],
        footnotes=[
            "N = number of subjects randomized.",
            "Percentages are based on the number of subjects randomized in each treatment arm.",
        ],
    ),
    TFLShell(
        tfl_id="F14.1.2",
        tfl_type=TFLType.FIGURE,
        title="Subject Disposition Flow Diagram (CONSORT)",
        population="All Screened",
        source_dataset="ADSL",
        analysis_method="CONSORT Flow Diagram",
    ),
    # ── Section 14.1: Demographics & Baseline ──
    TFLShell(
        tfl_id="T14.1.2",
        tfl_type=TFLType.TABLE,
        title="Demographic and Baseline Characteristics",
        population="FAS",
        source_dataset="ADSL",
        columns=[
            {"header": "Characteristic", "var": "_param_"},
            {"header": "Statistics", "var": "_stat_"},
            {"header": "Treatment A", "var": "TRT01AN"},
            {"header": "Treatment B", "var": "TRT01AN"},
            {"header": "Total", "var": "_total_"},
        ],
        footnotes=["FAS = Full Analysis Set."],
    ),
    # ── Section 14.2: Efficacy ──
    TFLShell(
        tfl_id="T14.2.1",
        tfl_type=TFLType.TABLE,
        title="Primary Efficacy Endpoint Analysis",
        population="FAS",
        source_dataset="ADEF",
        columns=[
            {"header": "Analysis Result", "var": "_param_"},
            {"header": "Treatment A", "var": "TRT01AN"},
            {"header": "Treatment B", "var": "TRT01AN"},
            {"header": "Treatment Difference (95% CI)", "var": "_diff_"},
            {"header": "p-value", "var": "_pval_"},
        ],
        analysis_method="ANCOVA with treatment and stratification factors",
        footnotes=[
            "FAS = Full Analysis Set. CI = confidence interval.",
            "ANCOVA model: change from baseline = treatment + baseline + strata1 + strata2.",
        ],
    ),
    TFLShell(
        tfl_id="F14.2.1",
        tfl_type=TFLType.FIGURE,
        title="Kaplan-Meier Plot of Overall Survival",
        population="FAS",
        source_dataset="ADTTE",
        analysis_method="Kaplan-Meier with Cox proportional hazards",
        footnotes=["FAS = Full Analysis Set. OS = Overall Survival."],
    ),
    TFLShell(
        tfl_id="F14.2.2",
        tfl_type=TFLType.FIGURE,
        title="Forest Plot of Subgroup Analysis — Primary Endpoint",
        population="FAS",
        source_dataset="ADEF",
        analysis_method="Forest plot by subgroups",
    ),
    # ── Section 14.3: Safety ──
    TFLShell(
        tfl_id="T14.3.1",
        tfl_type=TFLType.TABLE,
        title="Overall Summary of Treatment-Emergent Adverse Events",
        population="Safety",
        source_dataset="ADAE",
        columns=[
            {"header": "Category", "var": "_param_"},
            {"header": "Treatment A (N=XX)", "var": "TRT01AN"},
            {"header": "Treatment B (N=XX)", "var": "TRT01AN"},
        ],
        footnotes=[
            "TEAE = Treatment-Emergent Adverse Event.",
            "Safety population includes all subjects who received at least one dose of study drug.",
        ],
    ),
    TFLShell(
        tfl_id="T14.3.2",
        tfl_type=TFLType.TABLE,
        title="Treatment-Emergent Adverse Events by System Organ Class and Preferred Term (>=5% Incidence)",
        population="Safety",
        source_dataset="ADAE",
        columns=[
            {"header": "System Organ Class / Preferred Term", "var": "AEBODSYS / AEDECOD"},
            {"header": "Treatment A (N=XX) n (%)", "var": "TRT01AN"},
            {"header": "Treatment B (N=XX) n (%)", "var": "TRT01AN"},
        ],
        footnotes=["TEAEs with incidence >=5% in any treatment arm are displayed."],
    ),
    # ── Listings ──
    TFLShell(
        tfl_id="L16.2.1",
        tfl_type=TFLType.LISTING,
        title="Listing of Subject Disposition",
        population="All Randomized",
        source_dataset="ADSL",
        columns=[
            {"header": "Site", "var": "SITEID"},
            {"header": "Subject", "var": "USUBJID"},
            {"header": "Age/Sex", "var": "AGE/SEX"},
            {"header": "Treatment", "var": "TRT01A"},
            {"header": "Disposition", "var": "DCDECOD"},
        ],
    ),
    TFLShell(
        tfl_id="L16.2.4",
        tfl_type=TFLType.LISTING,
        title="Listing of Adverse Events",
        population="Safety",
        source_dataset="ADAE",
        columns=[
            {"header": "Site/Subject", "var": "SITEID/USUBJID"},
            {"header": "Treatment", "var": "TRTA"},
            {"header": "Preferred Term", "var": "AEDECOD"},
            {"header": "Severity", "var": "AESEV"},
            {"header": "Serious", "var": "AESER"},
            {"header": "Related", "var": "AREL"},
            {"header": "Start Day", "var": "ASTDY"},
            {"header": "Duration", "var": "ADURN"},
        ],
    ),
]

# K-M figure (oncology) — conditional
ONCOLOGY_TFL_SHELLS: list[TFLShell] = [
    TFLShell(
        tfl_id="F14.2.3",
        tfl_type=TFLType.FIGURE,
        title="Waterfall Plot of Best Percent Change from Baseline in Tumor Size",
        population="FAS (measurable disease at baseline)",
        source_dataset="ADTR",
        analysis_method="Best percent change per subject, sorted descending",
    ),
    TFLShell(
        tfl_id="F14.2.4",
        tfl_type=TFLType.FIGURE,
        title="Swimmer Plot of Treatment Duration and Response",
        population="FAS",
        source_dataset="ADTR, ADTTE",
        analysis_method="Longitudinal display per subject",
    ),
    TFLShell(
        tfl_id="T14.2.3",
        tfl_type=TFLType.TABLE,
        title="Objective Response Rate per RECIST 1.1",
        population="FAS (measurable disease)",
        source_dataset="ADTR",
        columns=[
            {"header": "Response Category", "var": "_param_"},
            {"header": "Treatment A n (%)", "var": "TRT01AN"},
            {"header": "Treatment B n (%)", "var": "TRT01AN"},
            {"header": "Odds Ratio (95% CI)", "var": "_or_"},
            {"header": "p-value", "var": "_pval_"},
        ],
        footnotes=["RECIST 1.1 assessed by IRC. FAS = Full Analysis Set."],
    ),
]


# ── Renderer interface ───────────────────────────────────────────


class TFLRenderer(Protocol):
    """Protocol for TFL rendering backends."""

    def render(self, shell: TFLShell, data: Any, output_format: OutputFormat) -> bytes:
        ...


class RTFRenderer:
    """Renders TFLs to RTF format for Clinical Study Report integration."""

    def render(self, shell: TFLShell, data: Any, output_format: OutputFormat = OutputFormat.RTF) -> bytes:
        # In a full implementation, would use python-docx or similar
        # to produce formatted RTF with proper headers, footnotes, page breaks
        import json
        return json.dumps({
            "tfl_id": shell.tfl_id,
            "title": shell.title,
            "format": "RTF",
            "columns": shell.columns,
            "footnotes": shell.footnotes,
            "rows": len(data) if hasattr(data, '__len__') else 0,
        }).encode("utf-8")


def get_tfl_shells(trial_phase: str = "phase_iii",
                   therapeutic_area: str = "non_oncology") -> list[TFLShell]:
    """Return TFL shells appropriate for the trial configuration."""
    shells = list(STANDARD_TFL_SHELLS)
    if therapeutic_area == "oncology":
        shells.extend(ONCOLOGY_TFL_SHELLS)
    # Phase I trials have reduced TFL requirements
    if trial_phase == "phase_i":
        shells = [s for s in shells if s.tfl_id.startswith("T14.3")]
        return shells[:3]
    return shells
