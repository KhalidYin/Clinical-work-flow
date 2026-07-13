"""Reproducible P6 source-trace and visual-evidence release metrics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from service.contracts import SchemaBundle
from service.repository import VaultRepository


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
