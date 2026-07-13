"""P6 HOME-to-evidence navigation acceptance for the seven global scenarios."""

from __future__ import annotations

from collections import deque
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault"
WIKI_LINK = re.compile(r"(?<!!)\[\[([^\]]+)\]\]")


def _resolve_link(origin: Path, raw_target: str) -> Path | None:
    target = raw_target.split("|", 1)[0].split("#", 1)[0].strip()
    if not target:
        return None
    for candidate in (origin.parent / target, VAULT / target):
        note = candidate if candidate.suffix == ".md" else candidate.with_suffix(".md")
        if note.is_file():
            return note.resolve()
    return None


def _navigation_distances() -> dict[Path, int]:
    home = (VAULT / "HOME.md").resolve()
    distances = {home: 0}
    queue = deque([home])
    while queue:
        note = queue.popleft()
        for raw_target in WIKI_LINK.findall(note.read_text(encoding="utf-8")):
            target = _resolve_link(note, raw_target)
            if target is not None and target not in distances:
                distances[target] = distances[note] + 1
                queue.append(target)
    return distances


def test_seven_global_scenarios_are_reachable_from_home_within_three_links() -> None:
    scenario_targets = {
        "randomized_design": (
            "20_Knowledge/Methods/Estimand Framework.md",
            "20_Knowledge/Methods/Sample Size and Precision.md",
            "30_Workflows/Stages/SAP Generation.md",
            "50_Cases/Synthetic-Studies/SYNTH-ONCO-001 Longitudinal Case.md",
        ),
        "missing_data": (
            "20_Knowledge/Methods/Missing Data Assumptions.md",
            "20_Knowledge/Methods/Sensitivity Analysis.md",
            "20_Knowledge/Programming/ADaM Derivation Metadata Pattern.md",
        ),
        "sdtm_to_submission": (
            "10_MOC/Stage-Traceability-MOC.md",
            "20_Knowledge/Standards/SDTM Domain Representation.md",
            "40_Toolkit/Deliverable-Patterns/Submission Readiness Package Pattern.md",
        ),
        "tfl_qc": (
            "30_Workflows/Stages/QC Validation.md",
            "20_Knowledge/Programming/Independent QC Reconciliation Pattern.md",
            "40_Toolkit/Deliverable-Patterns/QC Evidence Pack Pattern.md",
        ),
        "regulatory_locator": (
            "60_Sources/Registry/ICH E9 R1.md",
            "60_Sources/Registry/FDA Study Data Technical Conformance Guide.md",
        ),
        "figure_evidence": (
            "60_Sources/Registry/Synthetic TEAE Figure Source.md",
            "60_Sources/Figures/Synthetic TEAE Figure Evidence.md",
        ),
        "study_adae": (
            "50_Cases/Synthetic-Studies/SYNTH-ONCO-001 Longitudinal Case.md",
            "30_Workflows/Stages/ADaM Spec.md",
        ),
    }
    distances = _navigation_distances()
    failures: list[str] = []
    for scenario, targets in scenario_targets.items():
        for relative in targets:
            target = (VAULT / relative).resolve()
            distance = distances.get(target)
            if distance is None or distance > 3:
                failures.append(f"{scenario}: {relative} distance={distance}")
    assert not failures, "HOME navigation exceeds three links: " + "; ".join(failures)


def test_regulatory_and_figure_scenarios_expose_required_trace_fields() -> None:
    regulatory = (VAULT / "60_Sources/Registry/ICH E9 R1.md").read_text(encoding="utf-8")
    figure = (
        VAULT / "60_Sources/Figures/Synthetic TEAE Figure Evidence.md"
    ).read_text(encoding="utf-8")
    source = (
        VAULT / "60_Sources/Registry/Synthetic TEAE Figure Source.md"
    ).read_text(encoding="utf-8")
    accession = json.loads(
        (ROOT / "sources/accessions/ich-e9-r1.json").read_text(encoding="utf-8")
    )
    fda = (
        VAULT / "60_Sources/Registry/FDA Study Data Technical Conformance Guide.md"
    ).read_text(encoding="utf-8")
    fda_accession = json.loads(
        (ROOT / "sources/accessions/fda-sdtcg-2026.json").read_text(encoding="utf-8")
    )
    for token in ("source_version:", "original_uri:", "physical_page:", "印刷页"):
        assert token in regulatory
    assert accession["upstream_version"]
    assert all(
        locator.get("section")
        and locator.get("physical_page")
        and locator.get("printed_page")
        for locator in accession["locators"]
    )
    assert "U.S. Food and Drug Administration" in fda
    assert "United States" in fda
    assert all(
        locator.get("section")
        and locator.get("physical_page")
        and locator.get("printed_page")
        for locator in fda_accession["locators"]
    )
    for token in ("source_sha256:", "figure_sha256:", "physical_page:", "printed_page:", "bbox:", "derivation:"):
        assert token in figure
    assert "visual-qa.json" in source
    assert "rights_status: cleared" in figure
    visual_qa = json.loads(
        (ROOT / "sources/accessions/synthetic-teae-visual-qa.json").read_text(
            encoding="utf-8"
        )
    )
    assert visual_qa["page_crop"]["status"] == "not_performed"
    assert visual_qa["redraw"]["status"] == "not_applicable"
    assert visual_qa["agent_visual_qa"]["status"] == "passed"
    assert visual_qa["human_visual_qa"]["status"] == "approved"
    assert visual_qa["human_visual_qa"]["review_id"] == (
        "platform_p6_global_acceptance_v1_001"
    )
