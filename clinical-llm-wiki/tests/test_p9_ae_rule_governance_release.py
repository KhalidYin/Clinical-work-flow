from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.content.p9_ae_rule_governance_release import (
    RELEASE_PATH,
    SNAPSHOT_PATH,
    TARGET_CARD_PATH,
    P9RuleGovernanceReleaseError,
    build_release,
    clean_room_query,
    write_release,
)
from service.contracts import canonical_json_sha256


ROOT = Path(__file__).resolve().parents[1]
HEX = "a" * 64


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _wiki_copy(tmp_path: Path) -> Path:
    target = tmp_path / "wiki"
    shutil.copytree(ROOT / "schemas", target / "schemas")
    shutil.copytree(ROOT / "vault", target / "vault")
    target_card = target / TARGET_CARD_PATH
    if target_card.exists():
        target_card.unlink()
    (target / ".review_queue" / "archive").mkdir(parents=True)
    return target


def _approved_candidate(**overrides: object) -> dict:
    candidate = {
        "candidate_id": "candidate-p9-ae-mapping-evidence-gate-v1",
        "classification": "general_rule_candidate",
        "target_knowledge_id": "pattern-p9-sdtm-ae-metadata-mapping-evidence-gate",
        "target_rule_id": "rule-p9-sdtm-ae-metadata-mapping-evidence-gate",
        "title": "P9 SDTM AE metadata mapping evidence gate",
        "review_status": "approved",
        "deidentified": True,
        "source_study_sha256": HEX,
        "source_mapping_spec_sha256": "b" * 64,
        "source_context_sha256": "c" * 64,
        "source_decision_sha256": "d" * 64,
        "source_version": {
            "standard": "SDTMIG",
            "version": "3.4",
            "snapshot_id": "snapshot-sdtmig34-core-events-ae-v1",
            "snapshot_sha256": "e" * 64,
        },
        "applicability": {
            "domains": ["sdtm", "ae"],
            "workflow_stages": ["sdtm_spec", "sdtm_programming"],
            "conditions": [
                "source metadata is hash-locked",
                "MappingSpec uses only allowlisted operations",
                "each mapping cites approved Wiki rules",
            ],
        },
        "non_applicability": [
            "does not approve Study-specific constants or identifier prefixes",
            "does not claim full SDTMIG conformance",
        ],
        "evidence": {
            "operation_allowlist": ["constant", "concat", "copy_trim"],
            "operations_used": ["constant", "copy_trim"],
            "approved_rule_refs": ["proposal-sdtmig34-gold-aeterm-required-v1"],
            "gap_ids": ["gap-controlled-value-labels"],
            "source_rows": 1066,
        },
        "approval": {
            "review_id": "sap_review_p9_ae_rule_governance_v1_001",
            "approval_receipt_id": "review-sap-review-p9-ae-rule-governance-v1-001",
            "decision_receipt_sha256": "d" * 64,
            "review_packet_sha256": "f" * 64,
            "reviewer": "P9 Wiki regression reviewer",
            "reviewer_role": "knowledge_governance",
            "approved_at": "2026-07-17T09:30:00+08:00",
        },
    }
    candidate.update(overrides)
    payload = {
        "schema_version": "1.0.0",
        "approved_candidate_id": "approved-p9-ae-rule-governance-v1",
        "report_sha256": "1" * 64,
        "candidate": candidate,
    }
    payload["approved_candidate_sha256"] = canonical_json_sha256(payload)
    return payload


def test_p9_rule_release_writes_approved_card_snapshot_and_clean_query(tmp_path: Path) -> None:
    wiki = _wiki_copy(tmp_path)
    candidate_path = tmp_path / "approved-candidate.json"
    _write_json(candidate_path, _approved_candidate())

    outputs = build_release(wiki, candidate_path)
    result = write_release(wiki, outputs)
    query = clean_room_query(wiki, outputs["release"]["snapshot_lock"])

    assert result["knowledge_card"] == TARGET_CARD_PATH
    assert (wiki / RELEASE_PATH).is_file()
    assert (wiki / SNAPSHOT_PATH).is_file()
    assert query["knowledge_id"] == "pattern-p9-sdtm-ae-metadata-mapping-evidence-gate"
    assert query["rule_ids"] == ["rule-p9-sdtm-ae-metadata-mapping-evidence-gate"]
    assert query["usage_scope"] == "p9-poc-test-only"
    release = json.loads((wiki / RELEASE_PATH).read_text(encoding="utf-8"))
    card_text = (wiki / TARGET_CARD_PATH).read_text(encoding="utf-8")
    assert release["usage_scope"] == "p9-poc-test-only"
    assert "测试用途声明" in card_text
    assert "p9-poc-test-only" in card_text
    assert "SAMPLE-AE-001" not in card_text


@pytest.mark.parametrize(
    "payload",
    [
        _approved_candidate(review_status="pending"),
        _approved_candidate(title="SAMPLE-AE-001 leaked title"),
        _approved_candidate(evidence={
            "operation_allowlist": ["constant"],
            "operations_used": ["constant"],
            "approved_rule_refs": [],
            "gap_ids": [],
            "source_rows": 1,
        }),
    ],
)
def test_p9_rule_release_rejects_unapproved_leaking_or_untraced_candidate(
    tmp_path: Path,
    payload: dict,
) -> None:
    wiki = _wiki_copy(tmp_path)
    candidate_path = tmp_path / "bad-candidate.json"
    payload["approved_candidate_sha256"] = canonical_json_sha256({
        key: value for key, value in payload.items() if key != "approved_candidate_sha256"
    })
    _write_json(candidate_path, payload)

    with pytest.raises(P9RuleGovernanceReleaseError):
        build_release(wiki, candidate_path)


def test_p9_rule_release_fails_closed_on_conflict(tmp_path: Path) -> None:
    wiki = _wiki_copy(tmp_path)
    candidate_path = tmp_path / "approved-candidate.json"
    _write_json(candidate_path, _approved_candidate())
    write_release(wiki, build_release(wiki, candidate_path))

    with pytest.raises(P9RuleGovernanceReleaseError, match="already exists"):
        build_release(wiki, candidate_path)


def test_p9_rule_release_rejects_hash_drift(tmp_path: Path) -> None:
    wiki = _wiki_copy(tmp_path)
    candidate = _approved_candidate()
    candidate["candidate"]["source_decision_sha256"] = "9" * 64
    candidate_path = tmp_path / "drifted-candidate.json"
    _write_json(candidate_path, candidate)

    with pytest.raises(P9RuleGovernanceReleaseError, match="content hash mismatch"):
        build_release(wiki, candidate_path)
