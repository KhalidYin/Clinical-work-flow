"""P7-P2 AE knowledge query package and MappingSpec candidate gate."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.agents.ae_mapping import (
    AEMappingCandidateError,
    AEMappingContextError,
    build_ae_mapping_context,
    validate_ae_mapping_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = ROOT.parent
FIXTURE = ROOT / "tests" / "fixtures" / "studies" / "ae-pilot"
WIKI_PACKAGE = (
    PLATFORM_ROOT
    / "clinical-llm-wiki"
    / "sources"
    / "packages"
    / "src-cdisc-sdtmig-3-4"
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _context() -> dict:
    return build_ae_mapping_context(FIXTURE, WIKI_PACKAGE)


def test_ae_mapping_context_packages_one_bounded_wiki_query() -> None:
    context = _context()

    assert context["synthetic_only"] is True
    assert context["query"] == {
        "task": "build_sdtm_dataset",
        "dataset": "AE",
        "stage": "sdtm_spec",
        "filters": {
            "domain": "AE",
            "implementation_guide": "SDTMIG-3.4",
            "include_core_rules": True,
            "include_explicit_gaps": True,
        },
    }
    assert context["p6_context"] == {
        "snapshot_id": "snapshot-sdtmig34-core-events-ae-v1",
        "citation_bundle_id": "ae-citation-bundle-sdtmig34-core-events-ae-v1",
        "query_benchmark_id": "query-benchmark-sdtmig34-core-events-ae-v1",
    }
    assert len(context["knowledge"]["rules"]) == 28
    assert {
        "proposal-sdtmig34-gold-aeterm-required-v1",
        "proposal-sdtmig34-core-study-day-calculation-method-v1",
    }.issubset(context["knowledge"]["rules"])
    assert {
        "gap-ae-aedecod-coding-not-approved-in-p6",
        "gap-controlled-terminology-not-deep-extracted-in-p6",
        "gap-executable-implementation-guidance-deferred-to-p7",
    }.issubset(context["knowledge"]["gaps"])

    aeterm = context["knowledge"]["rules"]["proposal-sdtmig34-gold-aeterm-required-v1"]
    assert aeterm["evidence"]
    assert all(item["source_id"] == "src-cdisc-sdtmig-3-4" for item in aeterm["evidence"])
    assert all(item["locator_id"] and item["artifact_sha256"] for item in aeterm["evidence"])
    assert "input/raw/ae.csv#verbatim_term" in context["study"]["allowed_source_refs"]
    assert "study-context-synth-ae-001-rfstdtc-source" in context["study"]["study_context_refs"]
    assert len(context["context_sha256"]) == 64


def test_ae_mapping_candidate_is_schema_valid_and_context_closed() -> None:
    context = _context()
    schema = _read_json(FIXTURE / "contracts" / "ae-mapping-spec.schema.json")
    candidate = _read_json(FIXTURE / "mapping-specs" / "ae-mapping-spec-success.json")

    validation = validate_ae_mapping_candidate(candidate, context, schema)

    assert validation.spec_id == "map-spec-synth-ae-001-v1"
    assert validation.context_sha256 == context["context_sha256"]
    assert validation.mapped_variables == (
        "AEENDTC",
        "AEENDY",
        "AESEQ",
        "AESTDTC",
        "AESTDY",
        "AETERM",
        "DOMAIN",
        "STUDYID",
        "USUBJID",
    )
    assert validation.gap_variables == ("AEDECOD", "AEENRF", "AESEV")
    assert validation.rule_ref_count >= 8
    assert validation.gap_ref_count == 3
    assert len(validation.candidate_sha256) == 64


def test_same_locked_inputs_produce_equivalent_context() -> None:
    left = _context()
    right = _context()

    assert left == right
    assert left["context_sha256"] == right["context_sha256"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("invent_rule", "rules outside context"),
        ("invent_source", "source fields outside context"),
        ("invent_gap", "gap outside context"),
        ("invent_study_ref", "Study context outside context"),
        ("wrong_p6_lock", "P6 locks"),
    ],
)
def test_ae_mapping_candidate_rejects_references_outside_context(
    mutation: str, message: str
) -> None:
    context = _context()
    schema = _read_json(FIXTURE / "contracts" / "ae-mapping-spec.schema.json")
    candidate = _read_json(FIXTURE / "mapping-specs" / "ae-mapping-spec-success.json")
    bad = deepcopy(candidate)

    if mutation == "invent_rule":
        bad["mappings"][0]["rule_refs"] = ["proposal-sdtmig34-fake-rule-v1"]
    elif mutation == "invent_source":
        bad["mappings"][0]["source_refs"] = ["input/raw/ae.csv#nonexistent"]
    elif mutation == "invent_gap":
        bad["gaps"][0]["source_gap_id"] = "gap-not-in-context"
    elif mutation == "invent_study_ref":
        bad["mappings"][5]["study_decision_refs"] = ["study-context-not-in-context"]
    elif mutation == "wrong_p6_lock":
        bad["p6_context"]["snapshot_id"] = "snapshot-different"

    with pytest.raises(AEMappingCandidateError, match=message):
        validate_ae_mapping_candidate(bad, context, schema)


def test_ae_mapping_context_fails_closed_on_fixture_hash_drift(tmp_path: Path) -> None:
    fixture = tmp_path / "ae-pilot"
    import shutil

    shutil.copytree(FIXTURE, fixture)
    (fixture / "input" / "raw" / "ae.csv").write_text(
        "subject_id,ae_record_id,verbatim_term,start_date,end_date,severity,meddra_pt,ongoing\n",
        encoding="utf-8",
    )

    with pytest.raises(AEMappingContextError, match="hash drifted"):
        build_ae_mapping_context(fixture, WIKI_PACKAGE)
