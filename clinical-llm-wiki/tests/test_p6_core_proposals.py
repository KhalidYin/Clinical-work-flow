"""P6-P3-C SDTMIG 3.4 Core proposal extraction gates."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from service.contracts import canonical_json_sha256
from service.repository import parse_markdown_card
from scripts.content.sdtmig34_core_proposals import (
    CORE_SCOPE_UNIT_IDS,
    DEFAULT_INBOX_CARD,
    DEFAULT_REPORT,
    DEFAULT_RESPONSE,
    CoreProposalError,
    load_json,
    run_core_proposals,
)


ROOT = Path(__file__).resolve().parents[1]


def _write_response(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _assert_no_raw_source_text_keys(payload: object) -> None:
    if isinstance(payload, dict):
        assert "source_text" not in payload
        assert "source_text_sha256" not in payload
        for value in payload.values():
            _assert_no_raw_source_text_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            _assert_no_raw_source_text_keys(item)


def test_core_input_projects_scope_without_restricted_source_text() -> None:
    result = run_core_proposals(include_source_text=False)
    projection = result["report"]["input_projection"]

    assert projection["unit_total"] == 25
    assert len(result["input"]["source_units"]) == len(CORE_SCOPE_UNIT_IDS)
    assert all("source_text" not in unit for unit in result["input"]["source_units"])
    assert {
        "unit-sdtmig34-pdf-table-p0017-g01",
        "unit-sdtmig34-deep-p0022-b016",
    } == {
        item["unit_id"]
        for item in projection["units"]
        if item["disposition"] == "non_knowledge"
    }


def test_core_batch_passes_gate_and_remains_proposed_only() -> None:
    result = run_core_proposals()
    batch = result["batch"]
    package = batch["extraction_package"]
    statements = package["statements"]

    assert batch["quality_summary"] == {
        "unit_total": 25,
        "candidate_unit_count": 23,
        "non_knowledge_unit_count": 2,
        "deferred_unit_count": 0,
        "proposal_total": 21,
        "blocking_issue_count": 0,
        "gate_status": "pass",
    }
    assert batch["gold_evaluation"] is None
    assert len(batch["coverage"]) == 25
    assert all(statement["review_status"] == "proposed" for statement in statements)
    assert all(statement["review_receipt_id"] is None for statement in statements)
    assert all(
        statement["statement_id"].startswith("proposal-sdtmig34-core-")
        for statement in statements
    )

    non_knowledge = [
        entry for entry in batch["coverage"] if entry["disposition"] == "non_knowledge"
    ]
    assert len(non_knowledge) == 2
    assert all(entry["rationale"] and not entry["proposal_ids"] for entry in non_knowledge)

    domain_code = next(
        statement
        for statement in statements
        if statement["statement_id"]
        == "proposal-sdtmig34-core-domain-code-consistency-v1"
    )
    assert {item["locator_id"] for item in domain_code["evidence"]} == {
        "loc-sdtmig34-deep-p0011-b018",
        "loc-sdtmig34-deep-p0012-b001",
    }


def test_core_quality_report_matches_committed_compact_artifact() -> None:
    result = run_core_proposals(include_source_text=True)
    report = result["report"]

    assert report == load_json(DEFAULT_REPORT)
    assert report["semantic_quality"]["raw_source_text_committed"] is False
    assert report["semantic_quality"]["duplicate_evidence_key_count"] == 0
    assert report["semantic_quality"]["candidate_without_proposal_count"] == 0
    _assert_no_raw_source_text_keys(report)


def test_core_inbox_card_is_proposed_and_vault_hash_valid() -> None:
    record, body = parse_markdown_card(ROOT / "vault", DEFAULT_INBOX_CARD)
    expected_hash = canonical_json_sha256(
        {
            "frontmatter": {
                key: value for key, value in record.items() if key != "content_hash"
            },
            "body": body,
        }
    )

    assert record["approval_status"] == "proposed"
    assert record["content_status"] == "inbox"
    assert record["content_hash"] == expected_hash
    assert "不得被 Runtime 当作 approved knowledge 调用" in body
    assert "The SDTMIG for Human Clinical Trials is based" not in body


def test_core_rejects_unknown_source_unit(tmp_path: Path) -> None:
    response = deepcopy(load_json(DEFAULT_RESPONSE))
    response["proposals"][0]["source_unit_ids"] = ["unit-sdtmig34-missing"]

    with pytest.raises(CoreProposalError, match="unknown source unit"):
        run_core_proposals(
            response_path=_write_response(tmp_path / "bad-response.json", response)
        )


def test_core_rejects_non_knowledge_source_unit(tmp_path: Path) -> None:
    response = deepcopy(load_json(DEFAULT_RESPONSE))
    response["proposals"][0]["source_unit_ids"] = [
        "unit-sdtmig34-pdf-table-p0017-g01"
    ]

    with pytest.raises(CoreProposalError, match="non-knowledge unit"):
        run_core_proposals(
            response_path=_write_response(tmp_path / "bad-response.json", response)
        )


def test_sdtmig34_source_registry_card_remains_non_runtime_proposed() -> None:
    card = ROOT / "vault" / "60_Sources" / "Registry" / "CDISC SDTMIG 3.4.md"
    record, body = parse_markdown_card(ROOT / "vault", card)
    expected_hash = canonical_json_sha256(
        {
            "frontmatter": {
                key: value for key, value in record.items() if key != "content_hash"
            },
            "body": body,
        }
    )

    assert record["id"] == "src-cdisc-sdtmig-3-4"
    assert record["approval_status"] == "proposed"
    assert record["content_status"] == "inbox"
    assert record["storage_mode"] == "local_only"
    assert record["content_hash"] == expected_hash
    assert "P3-C 候选入口" in body
    assert "SDTMIG 3.4 Core Proposal Batch" in body
