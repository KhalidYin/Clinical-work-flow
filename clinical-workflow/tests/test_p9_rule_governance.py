from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from src.knowledge import (
    AERuleGovernanceError,
    RULE_GOVERNANCE_APPROVED_PATH,
    RULE_GOVERNANCE_REPORT_PATH,
    RULE_GOVERNANCE_REVIEW_ID,
    TARGET_KNOWLEDGE_ID,
    TARGET_RULE_ID,
    approve_ae_rule_governance_from_receipt,
    build_ae_rule_governance_report,
    build_clean_ae_rule_reuse_context,
    prepare_ae_rule_governance_review,
    validate_ae_rule_governance_report,
)
from src.knowledge.compatibility import sha256_canonical_json
from src.runtime.review_protocol import (
    Decision,
    DecisionReceipt,
    FindingDecision,
    RejectionReason,
    ReviewPacket,
    ReviewQueue,
    validate_review_packet_schema,
)


ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT.parent
SAMPLE_STUDY = PLATFORM / "clinical-studies" / "SAMPLE-AE-001"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _copy_mapping_artifacts(tmp_path: Path) -> Path:
    study = tmp_path / "study"
    mapping = study / "work" / "mapping"
    mapping.mkdir(parents=True)
    for name in ("ae-mapping-context.json", "ae-mapping-spec-candidate.json"):
        shutil.copy2(SAMPLE_STUDY / "work" / "mapping" / name, mapping / name)
    return study


def _decide_all(study: Path, decision: Decision = Decision.APPROVED) -> None:
    queue = ReviewQueue(study)
    packet = queue.load_packet(RULE_GOVERNANCE_REVIEW_ID)
    assert packet is not None
    queue.submit_decision(DecisionReceipt(
        review_id=RULE_GOVERNANCE_REVIEW_ID,
        reviewer="P9 rule governance regression reviewer",
        decisions=[
            FindingDecision(
                finding_id=finding.id,
                decision=decision,
                rejection_reason=(
                    RejectionReason.INSUFFICIENT_EVIDENCE
                    if decision == Decision.REJECTED else None
                ),
                comment="P9 governance regression decision",
            )
            for finding in packet.findings_needing_decision()
        ],
        reviewer_role=None,
        general_notes="临时回归测试 DecisionReceipt。",
    ))


def test_actual_sample_rule_governance_is_approved_and_test_reusable() -> None:
    report = _read_json(SAMPLE_STUDY / RULE_GOVERNANCE_REPORT_PATH)
    packet = ReviewPacket.from_dict(
        _read_json(SAMPLE_STUDY / ".review_queue" / f"{RULE_GOVERNANCE_REVIEW_ID}.json")
    )
    approved = _read_json(SAMPLE_STUDY / RULE_GOVERNANCE_APPROVED_PATH)
    reuse = _read_json(
        SAMPLE_STUDY / "knowledge/promotion_candidates/ae-rule-reuse-context.json"
    )

    assert validate_ae_rule_governance_report(report) == []
    assert report["classification_counts"]["general_rule_candidate"] == 1
    assert report["classification_counts"]["study_specific_rule"] >= 2
    assert report["classification_counts"]["unresolved_gap"] == 3
    assert report["general_rule_candidates"][0]["target_knowledge_id"] == TARGET_KNOWLEDGE_ID
    assert "SAMPLE-AE-001" not in json.dumps(
        report["general_rule_candidates"], ensure_ascii=False, sort_keys=True
    )
    assert packet is not None
    assert validate_review_packet_schema(packet.to_dict()) == []
    assert approved["candidate"]["review_status"] == "approved"
    assert approved["candidate"]["source_decision_sha256"]
    assert reuse["clean_room_query"]["usage_scope"] == "p9-poc-test-only"
    assert reuse["reuse_context"]["source_study_artifacts_read"] is False
    assert reuse["reuse_context"]["mapping_context_rule_refs"] == [TARGET_RULE_ID]


def test_approved_rule_governance_candidate_is_deidentified_and_hash_bound(
    tmp_path: Path,
) -> None:
    study = _copy_mapping_artifacts(tmp_path)
    prepare_ae_rule_governance_review(study)
    _decide_all(study)

    approved = approve_ae_rule_governance_from_receipt(study)

    candidate = approved["candidate"]
    assert candidate["review_status"] == "approved"
    assert candidate["source_decision_sha256"] == candidate["approval"]["decision_receipt_sha256"]
    assert candidate["source_mapping_spec_sha256"]
    assert candidate["applicability"]["domains"] == ["sdtm", "ae"]
    assert "SAMPLE-AE-001" not in json.dumps(candidate, ensure_ascii=False, sort_keys=True)
    assert (study / RULE_GOVERNANCE_APPROVED_PATH).is_file()


def test_rule_governance_rejection_and_evidence_gaps_fail_closed(tmp_path: Path) -> None:
    rejected = _copy_mapping_artifacts(tmp_path / "rejected")
    prepare_ae_rule_governance_review(rejected)
    _decide_all(rejected, Decision.REJECTED)
    with pytest.raises(AERuleGovernanceError, match="requires rework"):
        approve_ae_rule_governance_from_receipt(rejected)
    assert not (rejected / RULE_GOVERNANCE_APPROVED_PATH).exists()

    no_evidence = _copy_mapping_artifacts(tmp_path / "no-evidence")
    spec_path = no_evidence / "work/mapping/ae-mapping-spec-candidate.json"
    spec = _read_json(spec_path)
    spec["knowledge"]["rules"] = []
    spec_body = dict(spec)
    spec_body.pop("spec_sha256", None)
    spec["spec_sha256"] = sha256_canonical_json(spec_body)
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    with pytest.raises(AERuleGovernanceError, match="approved rule evidence"):
        build_ae_rule_governance_report(no_evidence)


def test_report_validation_rejects_deidentification_and_hash_drift(tmp_path: Path) -> None:
    study = _copy_mapping_artifacts(tmp_path)
    report = build_ae_rule_governance_report(study)
    report["general_rule_candidates"][0]["deidentified"] = False
    assert any("deidentified" in item for item in validate_ae_rule_governance_report(report))

    report = build_ae_rule_governance_report(study)
    report["classification_counts"]["general_rule_candidate"] = 99
    assert any("classification_counts" in item for item in validate_ae_rule_governance_report(report))


def test_clean_query_result_becomes_mapping_context_rule_ref() -> None:
    context = build_clean_ae_rule_reuse_context({
        "query_id": "clean-room-p9-ae-rule-governance-v1",
        "knowledge_id": TARGET_KNOWLEDGE_ID,
        "knowledge_version": "1.0.0",
        "rule_ids": [TARGET_RULE_ID],
        "snapshot_id": "snapshot-p9-ae-rule-governance-v1",
        "snapshot_sha256": "a" * 64,
    })

    assert context["source_study_artifacts_read"] is False
    assert context["mapping_context_rule_refs"] == [TARGET_RULE_ID]
    assert context["knowledge"]["rules"][0]["knowledge_id"] == TARGET_KNOWLEDGE_ID
