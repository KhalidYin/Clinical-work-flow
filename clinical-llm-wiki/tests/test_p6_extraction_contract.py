"""P6-P1 source acquisition and extraction-contract gates."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from scripts.content.extraction_contract import (
    ExtractionContractError,
    validate_extraction_package,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "knowledge" / "extraction-contract-positive.json"
GOLD_SET = ROOT / "tests" / "fixtures" / "knowledge" / "sdtmig34-gold-set.json"
ACQUISITION = (
    ROOT / "sources" / "packages" / "src-cdisc-sdtmig-3-4" / "acquisition.json"
)
REVIEW_PACKET = (
    ROOT / ".review_queue" / "archive" / "sdtm_spec_sdtmig34_gold_v1_001.json"
)
DECISION_RECEIPT = REVIEW_PACKET.with_name("sdtm_spec_sdtmig34_gold_v1_001_decision.json")
CONFIRMATION_RECEIPT = REVIEW_PACKET.with_name(
    "sdtm_spec_sdtmig34_gold_v1_001_confirmation.json"
)


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_positive_extraction_contract_has_closed_evidence_and_relations() -> None:
    validate_extraction_package(_fixture())


def test_sdtmig34_gold_set_covers_required_source_and_knowledge_shapes() -> None:
    gold_set = json.loads(GOLD_SET.read_text(encoding="utf-8"))
    validate_extraction_package(gold_set)

    assert {unit["unit_type"] for unit in gold_set["units"]} >= {
        "domain",
        "table",
        "variable_row",
        "paragraph",
        "example",
        "cross_reference",
        "erratum",
    }
    assert {statement["knowledge_type"] for statement in gold_set["statements"]} >= {
        "definition",
        "requirement",
        "variable_rule",
        "example",
        "cross_reference",
        "exception",
    }
    aeterm = next(
        statement
        for statement in gold_set["statements"]
        if statement["statement_id"] == "stmt-sdtmig34-aeterm-required"
    )
    assert {evidence["artifact_id"] for evidence in aeterm["evidence"]} == {
        "artifact-cdisc-sdtmig-3-4-pdf",
        "artifact-cdisc-sdtmig-3-4-xlsx",
    }
    assert all(statement["review_status"] == "approved" for statement in gold_set["statements"])
    assert {
        statement["review_receipt_id"] for statement in gold_set["statements"]
    } == {"review-sdtmig34-gold-v1-001"}


def test_gold_set_review_packet_is_schema_valid_and_covers_every_statement() -> None:
    packet = json.loads(REVIEW_PACKET.read_text(encoding="utf-8"))
    schema_path = (
        ROOT.parent
        / "clinical-workflow"
        / "schemas"
        / "review"
        / "review-protocol.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    packet_schema = deepcopy(schema["$defs"]["review_packet"])
    packet_schema.pop("$id")
    packet_schema["$schema"] = schema["$schema"]
    packet_schema["$defs"] = schema["$defs"]
    Draft202012Validator(packet_schema).validate(packet)

    gold_set = json.loads(GOLD_SET.read_text(encoding="utf-8"))
    reviewed_locations = {finding["location"] for finding in packet["findings"]}
    assert {statement["statement_id"] for statement in gold_set["statements"]} <= reviewed_locations
    assert packet["auto_approved_count"] == 0
    assert packet["urgency"] == "blocking"


def test_gold_set_human_review_triplet_is_valid_and_complete() -> None:
    schema_path = (
        ROOT.parent
        / "clinical-workflow"
        / "schemas"
        / "review"
        / "review-protocol.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    def definition(name: str) -> dict[str, object]:
        value = deepcopy(schema["$defs"][name])
        value.pop("$id", None)
        value["$schema"] = schema["$schema"]
        value["$defs"] = schema["$defs"]
        return value

    packet = json.loads(REVIEW_PACKET.read_text(encoding="utf-8"))
    decision = json.loads(DECISION_RECEIPT.read_text(encoding="utf-8"))
    confirmation = json.loads(CONFIRMATION_RECEIPT.read_text(encoding="utf-8"))
    Draft202012Validator(definition("decision_receipt")).validate(decision)
    Draft202012Validator(definition("confirmation_receipt")).validate(confirmation)

    finding_ids = {finding["id"] for finding in packet["findings"]}
    assert {item["finding_id"] for item in decision["decisions"]} == finding_ids
    assert {item["finding_id"] for item in confirmation["results"]} == finding_ids
    assert {item["decision"] for item in decision["decisions"]} == {"approved"}
    assert {item["application_status"] for item in confirmation["results"]} == {
        "applied"
    }
    assert confirmation["summary"] == {
        "total": 8,
        "applied": 8,
        "adjusted": 0,
        "failed": 0,
    }


def test_local_sdtmig34_gold_set_text_hashes_bind_to_exact_artifacts() -> None:
    import fitz
    from openpyxl import load_workbook

    gold_set = json.loads(GOLD_SET.read_text(encoding="utf-8"))
    manifest = json.loads((ACQUISITION.parent / "source-manifest.json").read_text(encoding="utf-8"))
    manifest_artifacts = {artifact["artifact_id"]: artifact for artifact in manifest["artifacts"]}
    gold_artifacts = {artifact["artifact_id"]: artifact for artifact in gold_set["artifacts"]}
    for artifact_id in (
        "artifact-cdisc-sdtmig-3-4-pdf",
        "artifact-cdisc-sdtmig-3-4-xlsx",
    ):
        assert (
            manifest_artifacts[artifact_id]["original_sha256"]
            == gold_artifacts[artifact_id]["artifact_sha256"]
        )

    release_accession = ROOT / "sources" / "accessions" / "cdisc-sdtmig-3-4-release.json"
    assert hashlib.sha256(release_accession.read_bytes()).hexdigest() == gold_artifacts[
        "artifact-cdisc-sdtmig-3-4-release-accession"
    ]["artifact_sha256"]

    originals = ACQUISITION.parent / "original"
    pdf_path = originals / manifest_artifacts["artifact-cdisc-sdtmig-3-4-pdf"][
        "original_filename"
    ]
    xlsx_path = originals / manifest_artifacts["artifact-cdisc-sdtmig-3-4-xlsx"][
        "original_filename"
    ]
    if not pdf_path.is_file() or not xlsx_path.is_file():
        pytest.skip("restricted local-only SDTMIG originals are not present")

    document = fitz.open(pdf_path)
    workbook = load_workbook(xlsx_path, read_only=True, data_only=False)
    try:
        for unit in gold_set["units"]:
            locator = unit["locator"]
            if locator["locator_type"] == "pdf_region":
                page = document[locator["physical_page"] - 1]
                bbox = locator["bbox"]
                if unit["unit_type"] == "table":
                    values = [
                        word[4]
                        for word in page.get_text("words", sort=True)
                        if word[0] >= bbox[0] - 1
                        and word[1] >= bbox[1] - 1
                        and word[2] <= bbox[2] + 1
                        and word[3] <= bbox[3] + 1
                    ]
                    source_text = " ".join(values)
                else:
                    block = min(
                        page.get_text("blocks", sort=True),
                        key=lambda item: sum(
                            abs(item[index] - bbox[index]) for index in range(4)
                        ),
                    )
                    source_text = block[4]
                normalized = " ".join(source_text.split())
                assert hashlib.sha256(normalized.encode("utf-8")).hexdigest() == unit[
                    "text_sha256"
                ]
            elif locator["locator_type"] == "xlsx_row":
                row = [
                    cell.value
                    for cell in workbook[locator["sheet_name"]][locator["row_number"]]
                ]
                normalized = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
                assert hashlib.sha256(normalized.encode("utf-8")).hexdigest() == unit[
                    "text_sha256"
                ]
    finally:
        workbook.close()
        document.close()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("knowledge_type", "guidance_guess"),
        ("modality", "probably"),
    ],
)
def test_statement_rejects_uncontrolled_semantics(field: str, value: str) -> None:
    payload = _fixture()
    payload["statements"][0][field] = value  # type: ignore[index]
    with pytest.raises(ExtractionContractError, match="schema validation failed"):
        validate_extraction_package(payload)


def test_approved_statement_requires_review_receipt() -> None:
    payload = _fixture()
    payload["statements"][0].pop("review_receipt_id")  # type: ignore[index]
    with pytest.raises(ExtractionContractError, match="review_receipt_id"):
        validate_extraction_package(payload)


def test_deferred_source_unit_requires_reason() -> None:
    payload = _fixture()
    unit = payload["units"][0]  # type: ignore[index]
    unit["processing_status"] = "deferred"
    unit["processing_note"] = None
    with pytest.raises(ExtractionContractError, match="processing_note"):
        validate_extraction_package(payload)


def test_dangling_locator_fails_closed() -> None:
    payload = _fixture()
    payload["statements"][0]["evidence"][0]["locator_id"] = "loc-missing"  # type: ignore[index]
    with pytest.raises(ExtractionContractError, match="missing locator"):
        validate_extraction_package(payload)


def test_dangling_relation_target_fails_closed() -> None:
    payload = deepcopy(_fixture())
    relation = payload["relations"][0]  # type: ignore[index]
    relation["target_kind"] = "source_unit"
    relation["to_id"] = "unit-missing"
    with pytest.raises(ExtractionContractError, match="dangling to_id"):
        validate_extraction_package(payload)


def test_sdtmig34_dual_artifact_acquisition_is_hash_locked_and_local_only() -> None:
    acquisition = json.loads(ACQUISITION.read_text(encoding="utf-8"))
    package = ACQUISITION.parent
    manifest = json.loads((package / "source-manifest.json").read_text(encoding="utf-8"))

    assert acquisition["status"] == "ingested_from_user_provided_authorized_copy"
    assert {artifact["media_type"] for artifact in acquisition["requested_artifacts"]} == {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    assert manifest["storage_mode"] == "local_only"
    assert manifest["rights_status"] == "restricted"
    assert manifest["page_count"] == 461
    assert manifest["pdf_status"] == "human_qa"
    assert {artifact["role"] for artifact in manifest["artifacts"]} == {
        "primary_citation",
        "structured_companion",
    }
    for artifact in manifest["artifacts"]:
        original = package / artifact["original_relative_path"]
        assert original.is_file()
        assert artifact["original_sha256"] == hashlib.sha256(original.read_bytes()).hexdigest()
