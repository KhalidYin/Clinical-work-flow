"""P5 representative-content and synthetic-pilot release gate."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
import pytest

from scripts.content.finalize_p5_content import RECEIPT_ID, REVIEW_ID, finalize
from service.contracts import SchemaBundle, canonical_json_sha256
from service.repository import Card, VaultRepository


ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault"
SCHEMAS = ROOT / "schemas" / "engine"
STAGES = {
    "protocol_analysis", "sap_generation", "sdtm_spec", "sdtm_programming",
    "adam_spec", "adam_programming", "tfl_shell_design", "tfl_programming",
    "qc_validation", "submission_packaging",
}
OFFICIAL_SOURCE_IDS = {
    "src-ich-e9-r1", "src-cdisc-sdtmig-3-3", "src-cdisc-adamig-1-3",
    "src-cdisc-adam-conformance-5-0", "src-fda-sdtcg-2026",
}


@pytest.fixture(scope="module")
def bundle() -> SchemaBundle:
    return SchemaBundle.load(SCHEMAS)


@pytest.fixture(scope="module")
def repository(bundle: SchemaBundle) -> VaultRepository:
    result = VaultRepository(ROOT, bundle)
    result.refresh()
    return result


def _cards_of_type(repository: VaultRepository, record_type: str) -> list[Card]:
    return [card for card in repository.cards.values() if card.record["type"] == record_type]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_representative_content_inventory_is_within_p5_scope(repository: VaultRepository) -> None:
    assert len(_cards_of_type(repository, "workflow_playbook")) == 10
    assert len(_cards_of_type(repository, "method")) >= 20
    assert len(_cards_of_type(repository, "standard_rule")) == 10
    assert len(_cards_of_type(repository, "programming_pattern")) == 10
    assert len(_cards_of_type(repository, "deliverable_pattern")) == 8
    assert len(list((VAULT / "10_MOC").glob("*.md"))) == 10

    article_roots = (
        VAULT / "10_MOC", VAULT / "20_Knowledge", VAULT / "30_Workflows",
        VAULT / "40_Toolkit", VAULT / "50_Cases" / "Synthetic-Studies",
    )
    articles = [
        path for root in article_roots for path in root.rglob("*.md")
        if path.name != "README.md"
    ]
    assert 60 <= len(articles) <= 80


def test_ten_stage_playbooks_are_complete_and_non_executable(repository: VaultRepository) -> None:
    playbooks = _cards_of_type(repository, "workflow_playbook")
    assert {card.record["stage"] for card in playbooks} == STAGES
    assert len({card.record["stage"] for card in playbooks}) == len(playbooks)
    headings = ("触发条件", "责任角色", "输入", "步骤", "决策门", "输出", "质量门禁", "异常处理", "来源", "非执行边界")
    forbidden_keys = {"next_stage", "skip_stage", "stage_override", "command", "commands"}
    for card in playbooks:
        record = card.record
        assert record["sources"]
        assert record["prerequisites"]
        assert record["steps"]
        assert record["expected_inputs"]
        assert record["expected_outputs"]
        assert record["decision_points"]
        assert record["review_requirements"]
        assert all(heading in card.body for heading in headings), record["id"]
        assert not forbidden_keys.intersection(record), record["id"]


def test_verified_approved_records_have_complete_governance_and_source_links(
    repository: VaultRepository,
) -> None:
    source_ids = {
        card.record["id"] for card in _cards_of_type(repository, "source_record")
    }
    governed_ids = set(repository.cards)
    for card in repository.cards.values():
        record = card.record
        expected_hash = canonical_json_sha256({
            "frontmatter": {key: value for key, value in record.items() if key != "content_hash"},
            "body": card.body,
        })
        assert record["content_hash"] == expected_hash, record["id"]
        if record["approval_status"] != "approved":
            continue
        assert record["content_status"] == "verified"
        assert record["rights_status"] != "unknown"
        assert record["storage_mode"] != "unknown"
        assert record["review_due"]
        assert record["approval_receipt_id"]
        assert record["audit_reference"]
        assert card.production_eligible, (record["id"], card.eligibility_reasons)
        if record["type"] not in {"source_record", "figure_record"}:
            assert record["sources"], record["id"]
            assert set(record["sources"]).issubset(source_ids), record["id"]
        for statement in record.get("statements", []):
            assert statement["evidence_refs"]
            assert set(statement["evidence_refs"]).issubset(source_ids), statement["rule_id"]
        assert record["id"] in governed_ids


def test_p5_receipt_maps_schema_finding_ids_to_each_released_record(
    repository: VaultRepository, bundle: SchemaBundle
) -> None:
    governance = VAULT / "80_Governance" / "Review-Receipts"
    packet = json.loads((governance / f"{REVIEW_ID}.json").read_text(encoding="utf-8"))
    decision = json.loads((governance / f"{REVIEW_ID}_decision.json").read_text(encoding="utf-8"))
    confirmation = json.loads((governance / f"{REVIEW_ID}_confirmation.json").read_text(encoding="utf-8"))
    bundle.validate_definition("review/review-protocol.schema.json", "review_packet", packet)
    bundle.validate_definition("review/review-protocol.schema.json", "decision_receipt", decision)
    bundle.validate_definition("review/review-protocol.schema.json", "confirmation_receipt", confirmation)

    released_ids = {
        card.record["id"] for card in repository.cards.values()
        if card.record.get("approval_receipt_id") == RECEIPT_ID
    }
    packet_targets = {finding["id"]: finding["location"] for finding in packet["findings"]}
    assert set(packet_targets.values()) == released_ids
    assert {entry["finding_id"] for entry in decision["decisions"]} == set(packet_targets)
    assert {entry["finding_id"] for entry in confirmation["results"]} == set(packet_targets)
    assert decision["reviewer_role"] == "non_human_test_fixture"
    assert "cannot satisfy" in decision["general_notes"]


def test_release_generator_is_idempotent_and_check_only() -> None:
    assert finalize(write=False) >= 60


def test_programming_patterns_declare_honest_validation_level(repository: VaultRepository) -> None:
    levels: list[str] = []
    for card in _cards_of_type(repository, "programming_pattern"):
        match = re.search(r"验证等级：\*\*(illustrative|tested|qualified|production)\*\*", card.body)
        assert match, card.record["id"]
        levels.append(match.group(1))
    assert levels.count("illustrative") == 9
    assert levels.count("tested") == 1
    assert "qualified" not in levels
    assert "production" not in levels


def test_official_source_accessions_are_hash_bound_and_section_located(
    repository: VaultRepository,
) -> None:
    for source_id in OFFICIAL_SOURCE_IDS:
        card = repository.cards[source_id]
        record = card.record
        assert record["source_kind"] == "document"
        assert record["original_uri"].startswith("repo://sources/accessions/")
        accession = ROOT / record["original_uri"].removeprefix("repo://")
        assert accession.is_file()
        assert _sha256(accession) == record["original_sha256"]
        payload = json.loads(accession.read_text(encoding="utf-8"))
        assert payload["upstream_uri"].startswith("https://")
        assert payload["upstream_version"]
        assert payload["locators"]
        assert all(locator.get("section") for locator in payload["locators"])
        assert "## 定位" in card.body


def test_synthetic_teae_figure_has_page_hash_and_visual_qa(repository: VaultRepository) -> None:
    source = repository.cards["src-synthetic-teae-figure"].record
    figure = repository.cards["fig-synthetic-teae-evidence"].record
    method = repository.cards["kn-method-teae-classification"].record
    pdf = ROOT / source["original_uri"].removeprefix("repo://")
    render = ROOT / "tests" / "fixtures" / "pdf" / "rendered-digital" / "page-001.png"
    qa = json.loads((ROOT / "sources" / "accessions" / "synthetic-teae-visual-qa.json").read_text(encoding="utf-8"))

    assert _sha256(pdf) == source["original_sha256"] == figure["source_sha256"]
    assert len(PdfReader(pdf).pages) == source["page_count"] == 1
    assert figure["locator"]["physical_page"] == 1
    assert _sha256(render) == figure["figure_sha256"] == qa["render_sha256"]
    with Image.open(render) as image:
        image.verify()
    assert qa["machine_qa"]["status"] == "passed"
    assert qa["agent_visual_qa"]["status"] == "passed"
    assert "not a human GxP approval" in qa["agent_visual_qa"]["note"]
    assert source["id"] in method["sources"]


def test_promotion_candidate_remains_inbox_only_and_runtime_ineligible(
    repository: VaultRepository,
) -> None:
    candidate = repository.cards["precedent-synth-onco-001-promotion-candidate"]
    assert candidate.relative_path.startswith("vault/98_Inbox/")
    assert candidate.record["content_status"] == "inbox"
    assert candidate.record["approval_status"] == "proposed"
    assert candidate.record["approval_receipt_id"] is None
    assert candidate.production_eligible is False
    assert not any(
        "precedent-synth-onco-001-promotion-candidate" in path.read_text(encoding="utf-8")
        for path in (VAULT / "70_Prior_Studies").rglob("*.md")
    )
