"""Reproducible P6 source-trace and visual-evidence release metrics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from service.contracts import SchemaBundle
from service.repository import VaultRepository
from service.snapshot import load_locked_snapshot
from scripts.content.sdtmig34_release_gate import (
    CARD_IDS,
    CITATION_BUNDLE_PATH,
    QUALITY_REPORT_PATH,
    QUERY_BENCHMARK_PATH,
    SNAPSHOT_MANIFEST_PATH,
    SNAPSHOT_PATH,
    ReleaseGateError,
    build_outputs,
    check_outputs,
    tamper_for_negative_gate,
    validate_release_gate,
)


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_SOURCE_IDS = {
    "src-ich-e9-r1",
    "src-cdisc-sdtmig-3-3",
    "src-cdisc-adamig-1-3",
    "src-cdisc-adam-conformance-5-0",
    "src-fda-sdtcg-2026",
}


def _repository() -> VaultRepository:
    repository = VaultRepository(ROOT, SchemaBundle.load(ROOT / "schemas/engine"))
    repository.refresh()
    return repository


def test_every_approved_formal_statement_has_versioned_source_evidence() -> None:
    repository = _repository()
    source_ids = {
        card.record["id"]
        for card in repository.cards.values()
        if card.record["type"] == "source_record"
    }
    statements = [
        statement
        for card in repository.cards.values()
        if card.record["approval_status"] == "approved"
        for statement in card.record.get("statements", [])
    ]
    assert statements
    traced = [
        statement
        for statement in statements
        if statement.get("evidence_refs")
        and set(statement["evidence_refs"]).issubset(source_ids)
    ]
    assert len(traced) / len(statements) == 1.0


def test_official_accessions_have_version_and_medium_appropriate_locators() -> None:
    repository = _repository()
    for source_id in OFFICIAL_SOURCE_IDS:
        record = repository.cards[source_id].record
        accession_path = ROOT / record["original_uri"].removeprefix("repo://")
        assert hashlib.sha256(accession_path.read_bytes()).hexdigest() == record[
            "original_sha256"
        ]
        accession = json.loads(accession_path.read_text(encoding="utf-8"))
        assert accession["upstream_version"]
        assert accession["locators"]
        assert all(locator.get("section") for locator in accession["locators"])
        upstream_uri = accession["upstream_uri"]
        if upstream_uri.endswith(".pdf") or upstream_uri.endswith("/download"):
            assert all(
                locator.get("physical_page") and locator.get("printed_page")
                for locator in accession["locators"]
            )


def test_only_referenced_figure_has_complete_human_visual_evidence() -> None:
    qa = json.loads(
        (ROOT / "sources/accessions/synthetic-teae-visual-qa.json").read_text(
            encoding="utf-8"
        )
    )
    assert qa["machine_qa"]["status"] == "passed"
    assert qa["agent_visual_qa"]["status"] == "passed"
    assert qa["page_crop"]["status"] == "not_performed"
    assert qa["redraw"]["status"] == "not_applicable"
    assert qa["human_visual_qa"]["status"] == "approved"
    assert qa["human_visual_qa"]["review_id"] == (
        "platform_p6_global_acceptance_v1_001"
    )
    assert qa["human_visual_qa"]["scope"] == "local_synthetic_release_baseline"
    assert qa["human_visual_qa"]["reviewer_role"] == "human_platform_owner"


def test_sdtmig34_p5_release_artifacts_are_rebuildable() -> None:
    outputs = build_outputs()
    check_outputs(outputs)

    for path in (
        SNAPSHOT_PATH,
        SNAPSHOT_MANIFEST_PATH,
        QUERY_BENCHMARK_PATH,
        CITATION_BUNDLE_PATH,
        QUALITY_REPORT_PATH,
    ):
        assert path.is_file()

    quality_report = outputs["quality_report"]
    assert quality_report["passed"] is True
    assert quality_report["approved_statement_count"] == 28
    evidence_criterion = quality_report["criteria"][0]
    assert evidence_criterion["criterion"] == (
        "100% approved statement has source/version/locator/hash"
    )
    assert evidence_criterion["evidence"]["coverage"] == 1.0

    benchmark = outputs["query_benchmark"]
    assert benchmark["passed_count"] == benchmark["case_count"] == 11
    assert benchmark["gap_case_count"] == 4
    assert all(case["passed"] for case in benchmark["cases"])


def test_sdtmig34_p5_snapshot_is_approved_only_and_loadable() -> None:
    outputs = build_outputs()
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    assert [item["id"] for item in snapshot["items"]] == sorted(CARD_IDS)
    assert {item["approval_status"] for item in snapshot["items"]} == {"approved"}
    assert {item["content_status"] for item in snapshot["items"]} == {"verified"}
    assert "source_record" not in {item["type"] for item in snapshot["items"]}

    records = load_locked_snapshot(
        _repository(), outputs["citation_bundle"]["snapshot_lock"]
    )
    assert [record["id"] for record in records] == sorted(CARD_IDS)


def test_sdtmig34_p5_citation_bundle_declares_rules_and_gaps() -> None:
    bundle = json.loads(CITATION_BUNDLE_PATH.read_text(encoding="utf-8"))
    statement_ids = {rule["statement_id"] for rule in bundle["rules"]}
    assert {
        "proposal-sdtmig34-gold-aeterm-required-v1",
        "proposal-sdtmig34-gold-aeenrf-crossref-v1",
        "proposal-sdtmig34-gold-erratum-lnkgrp-v1",
    }.issubset(statement_ids)

    gap_ids = {gap["gap_id"] for gap in bundle["coverage_gaps"]}
    assert {
        "gap-sdtmig34-assumption-statements-not-approved-in-p6",
        "gap-ae-aedecod-coding-not-approved-in-p6",
        "gap-controlled-terminology-not-deep-extracted-in-p6",
        "gap-executable-implementation-guidance-deferred-to-p7",
    }.issubset(gap_ids)

    for rule in bundle["rules"]:
        assert rule["evidence"]
        for evidence in rule["evidence"]:
            assert evidence["source_id"] == "src-cdisc-sdtmig-3-4"
            assert evidence["locator_id"]
            assert evidence["artifact_sha256"]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_locator",
        "wrong_version_source",
        "snapshot_widened",
        "unapproved_snapshot_item",
    ],
)
def test_sdtmig34_p5_release_gate_rejects_invalid_artifacts(mutation: str) -> None:
    outputs = build_outputs()
    with pytest.raises(ReleaseGateError):
        validate_release_gate(tamper_for_negative_gate(outputs, mutation))
