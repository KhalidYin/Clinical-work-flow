"""P5 representative-content and synthetic-pilot release gate."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
import pytest

from scripts.content.finalize_p5_content import (
    RECEIPT_ID,
    REVIEW_ID,
    SYNTHETIC_PILOT_CONDITION,
    SYNTHETIC_STUDY_ID,
    finalize,
)
from service.contracts import SchemaBundle, canonical_json_sha256
from service.repository import Card, VaultRepository


ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault"
REVIEW_ARCHIVE = ROOT / ".review_queue" / "archive"
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


def _bind_test_receipt(
    root: Path,
    record: dict[str, object],
    *,
    review_id: str,
    reviewer_role: str,
) -> None:
    review_archive = root / ".review_queue" / "archive"
    review_archive.mkdir(parents=True, exist_ok=True)
    governance_notes = root / "vault" / "80_Governance" / "Review-Receipts"
    governance_notes.mkdir(parents=True, exist_ok=True)
    audit_name = f"{review_id}.md"
    (governance_notes / audit_name).write_text(
        "structured review evidence\n", encoding="utf-8"
    )
    (review_archive / f"{review_id}_decision.json").write_text(
        json.dumps(
            {
                "review_id": review_id,
                "reviewer": "P5 Test Reviewer",
                "reviewer_role": reviewer_role,
                "timestamp": "2026-07-13T18:30:00+08:00",
                "decisions": [{"finding_id": record["id"], "decision": "approved"}],
            }
        ),
        encoding="utf-8",
    )
    record["approval_receipt_id"] = f"review-{review_id.replace('_', '-')}"
    record["audit_reference"] = (
        f"vault/80_Governance/Review-Receipts/{audit_name}"
    )


def test_representative_content_inventory_is_within_p5_scope(repository: VaultRepository) -> None:
    assert len(_cards_of_type(repository, "workflow_playbook")) == 10
    assert len(_cards_of_type(repository, "method")) >= 20
    assert len(_cards_of_type(repository, "standard_rule")) == 10
    assert len(_cards_of_type(repository, "programming_pattern")) == 10
    assert len(_cards_of_type(repository, "deliverable_pattern")) == 8
    # P5 established the minimum mature MOC inventory; later approved plans may
    # add navigation projections such as the generated workflow map.
    assert len(list((VAULT / "10_MOC").glob("*.md"))) >= 10

    article_roots = (
        VAULT / "10_MOC", VAULT / "20_Knowledge", VAULT / "30_Workflows",
        VAULT / "40_Toolkit", VAULT / "50_Cases" / "Synthetic-Studies",
    )
    generated_relations = VAULT / "10_MOC" / "Workflow-Relations"
    articles = [
        path for root in article_roots for path in root.rglob("*.md")
        if path.name != "README.md" and generated_relations not in path.parents
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
    packet = json.loads((REVIEW_ARCHIVE / f"{REVIEW_ID}.json").read_text(encoding="utf-8"))
    decision = json.loads((REVIEW_ARCHIVE / f"{REVIEW_ID}_decision.json").read_text(encoding="utf-8"))
    confirmation = json.loads((REVIEW_ARCHIVE / f"{REVIEW_ID}_confirmation.json").read_text(encoding="utf-8"))
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


def test_p5_non_human_receipt_is_bound_to_exact_synthetic_scope(
    repository: VaultRepository,
) -> None:
    released = [
        card
        for card in repository.cards.values()
        if card.record.get("approval_receipt_id") == RECEIPT_ID
    ]
    assert released
    for card in released:
        applicability = card.record["applicability"]
        assert applicability["study_ids"] == [SYNTHETIC_STUDY_ID], card.record["id"]
        assert applicability["conditions"] == [SYNTHETIC_PILOT_CONDITION], card.record["id"]
        assert card.production_eligible, (card.record["id"], card.eligibility_reasons)


@pytest.mark.parametrize(
    ("study_ids", "conditions"),
    [
        ([], [SYNTHETIC_PILOT_CONDITION]),
        (["STUDY-PRODUCTION-001"], [SYNTHETIC_PILOT_CONDITION]),
        (["SYNTH-OTHER-001"], [SYNTHETIC_PILOT_CONDITION]),
        ([SYNTHETIC_STUDY_ID], []),
    ],
)
def test_non_human_receipt_with_empty_or_wrong_scope_is_production_ineligible(
    repository: VaultRepository,
    study_ids: list[str],
    conditions: list[str],
) -> None:
    released = next(
        card
        for card in repository.cards.values()
        if card.record.get("approval_receipt_id") == RECEIPT_ID
    )
    record = deepcopy(released.record)
    record["applicability"]["study_ids"] = study_ids
    record["applicability"]["conditions"] = conditions

    reasons = tuple(repository._eligibility_reasons(record))

    assert "approval_evidence_unverified" in reasons


def test_non_human_scope_rule_follows_reviewer_role_not_p5_receipt_id(
    repository: VaultRepository,
    tmp_path: Path,
) -> None:
    released = next(
        card
        for card in repository.cards.values()
        if card.record.get("approval_receipt_id") == RECEIPT_ID
    )
    record = deepcopy(released.record)
    _bind_test_receipt(
        tmp_path,
        record,
        review_id="alternate_synthetic_fixture_v1_001",
        reviewer_role="non_human_test_fixture",
    )
    alternate_repository = VaultRepository(tmp_path, repository.bundle)

    assert "approval_evidence_unverified" not in tuple(
        alternate_repository._eligibility_reasons(record)
    )
    record["applicability"]["study_ids"] = []
    assert "approval_evidence_unverified" in tuple(
        alternate_repository._eligibility_reasons(record)
    )


def test_human_receipt_does_not_require_synthetic_scope(
    repository: VaultRepository,
    tmp_path: Path,
) -> None:
    released = next(
        card
        for card in repository.cards.values()
        if card.record.get("approval_receipt_id") == RECEIPT_ID
    )
    record = deepcopy(released.record)
    record["applicability"]["study_ids"] = []
    record["applicability"]["conditions"] = []
    _bind_test_receipt(
        tmp_path,
        record,
        review_id="human_scope_v1_001",
        reviewer_role="knowledge_governance",
    )

    human_repository = VaultRepository(tmp_path, repository.bundle)
    assert "approval_evidence_unverified" not in tuple(
        human_repository._eligibility_reasons(record)
    )


def test_release_generator_is_idempotent_and_check_only() -> None:
    assert finalize(write=False) >= 60


def test_obsidian_vault_excludes_machine_json_and_scripts() -> None:
    forbidden_suffixes = {".json", ".jsonl", ".py", ".js", ".ts", ".sh", ".ps1"}
    offending = [
        path.relative_to(VAULT).as_posix()
        for path in VAULT.rglob("*")
        if path.is_file()
        and ".obsidian" not in path.relative_to(VAULT).parts
        and path.suffix.lower() in forbidden_suffixes
    ]
    assert not offending
    assert (VAULT / ".obsidian" / "app.json").is_file()
    assert not (ROOT / ".obsidian").exists()
    assert list(REVIEW_ARCHIVE.glob("*.json"))


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


def test_synthetic_longitudinal_case_keeps_semantic_and_delivery_trace_consistent(
    repository: VaultRepository,
) -> None:
    case = repository.get("precedent-synth-onco-001-longitudinal-case")
    assert case is not None
    for concept in (
        "Estimand 属性",
        "主要终点",
        "ITT",
        "Safety",
        "模型",
        "缺失",
        "敏感性",
        "SDTM",
        "ADaM",
        "参数",
        "programming_pattern",
        "TFL",
        "CSR/Submission",
    ):
        assert concept in case.body
    assert "不将合成结果表达为真实证据" in case.body


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
