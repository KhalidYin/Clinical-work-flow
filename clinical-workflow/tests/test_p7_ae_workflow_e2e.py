"""P7-P4 AE vertical workflow E2E, review, promotion, and traceability."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from src.agents.ae_workflow import (
    AEWorkflowError,
    apply_ae_review_decision,
    build_sdtm_ae_dataset,
    read_csv_rows,
    submit_fixture_ae_acceptance,
    submit_fixture_ae_rejection,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "studies" / "ae-pilot"
WIKI_PACKAGE = (
    ROOT
    / "tests"
    / "fixtures"
    / "knowledge"
    / "sdtmig34-poc"
    / "sources"
    / "packages"
    / "src-cdisc-sdtmig-3-4"
)


def _copy_fixture(tmp_path: Path, name: str = "ae-pilot") -> Path:
    study = tmp_path / name
    shutil.copytree(FIXTURE, study)
    return study


def _copy_wiki_package(tmp_path: Path) -> Path:
    package = tmp_path / "src-cdisc-sdtmig-3-4"
    shutil.copytree(WIKI_PACKAGE, package)
    return package


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_build_sdtm_ae_dataset_runs_full_chain_with_review_and_traceability(
    tmp_path: Path,
) -> None:
    study = _copy_fixture(tmp_path)

    result = build_sdtm_ae_dataset(study, WIKI_PACKAGE, auto_approve=True)

    assert result.status == "canonical_written"
    assert result.review_id == "sdtm_spec_ae_v1_001"
    assert result.draft_dataset_path == "output/sdtm/drafts/ae.csv"
    assert result.canonical_dataset_path == "output/sdtm/datasets/ae.csv"
    assert result.canonical_dataset_sha256
    assert read_csv_rows(study / result.canonical_dataset_path) == read_csv_rows(
        study / "expected" / "sdtm" / "ae.csv"
    )

    packet = _read_json(study / result.review_packet_path)
    assert "用户请求：生成 AE 数据集" in packet["agent_summary"]
    assert packet["urgency"] == "blocking"
    assert {finding["location"] for finding in packet["findings"]} >= {
        "AE.AEDECOD",
        "AE.AESEV",
        "AE.AEENRF",
    }

    decision = _read_json(study / result.decision_receipt_path)
    assert {item["decision"] for item in decision["decisions"]} == {"approved"}

    confirmation = _read_json(study / result.confirmation_receipt_path)
    assert confirmation["summary"]["failed"] == 0
    assert confirmation["summary"]["applied"] == len(decision["decisions"])

    traceability = _read_json(study / result.traceability_report_path)
    assert traceability["scope_statement"].startswith("P7 synthetic AE baseline")
    assert traceability["canonical_dataset_sha256"] == result.canonical_dataset_sha256
    assert traceability["applied_study_decisions"] == [
        "study-context-synth-ae-001-date-policy",
        "study-context-synth-ae-001-rfstdtc-source",
    ]
    assert traceability["explicit_gaps"]
    assert traceability["applied_rules"]
    for rule in traceability["applied_rules"]:
        assert rule["source_version"] == "SDTMIG 3.4 Final, PDF re-issued 2022-07-21"
        assert rule["mapping_ids"]
        assert all(
            item["source_id"]
            and item["artifact_id"]
            and item["locator_id"]
            and item["artifact_sha256"]
            for item in rule["evidence"]
        )


def test_review_required_mode_can_resume_after_decision(tmp_path: Path) -> None:
    study = _copy_fixture(tmp_path)

    initial = build_sdtm_ae_dataset(study, WIKI_PACKAGE, auto_approve=False)
    assert initial.status == "review_required"
    assert initial.canonical_dataset_path is None
    assert not (study / "output" / "sdtm" / "datasets" / "ae.csv").exists()

    submit_fixture_ae_acceptance(study, initial.review_id)
    resumed = apply_ae_review_decision(study, WIKI_PACKAGE, initial.review_id)

    assert resumed.status == "canonical_written"
    assert (study / resumed.canonical_dataset_path).exists()


def test_rejected_review_writes_rework_and_does_not_promote(tmp_path: Path) -> None:
    study = _copy_fixture(tmp_path)

    initial = build_sdtm_ae_dataset(study, WIKI_PACKAGE, auto_approve=False)
    submit_fixture_ae_rejection(study, initial.review_id)
    result = apply_ae_review_decision(study, WIKI_PACKAGE, initial.review_id)

    assert result.status == "rework_required"
    assert result.canonical_dataset_path is None
    assert not (study / "output" / "sdtm" / "datasets" / "ae.csv").exists()
    rework = _read_json(study / result.traceability_report_path)
    assert rework["status"] == "rework_required"
    assert rework["rejected_findings"]


def test_broken_applied_rule_traceability_fails_closed(tmp_path: Path) -> None:
    study = _copy_fixture(tmp_path)

    initial = build_sdtm_ae_dataset(study, WIKI_PACKAGE, auto_approve=False)
    submit_fixture_ae_acceptance(study, initial.review_id)
    provenance_path = study / "output" / "sdtm" / "drafts" / "ae.csv.provenance.json"
    provenance = _read_json(provenance_path)
    provenance["applied_rule_evidence"].pop(next(iter(provenance["applied_rule_evidence"])))
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(AEWorkflowError, match="applied rule evidence missing"):
        apply_ae_review_decision(study, WIKI_PACKAGE, initial.review_id)

    assert not (study / "output" / "sdtm" / "datasets" / "ae.csv").exists()


def test_locked_package_copy_produces_equivalent_e2e_result(tmp_path: Path) -> None:
    online_study = _copy_fixture(tmp_path, "online-ae-pilot")
    offline_study = _copy_fixture(tmp_path, "offline-ae-pilot")
    locked_package = _copy_wiki_package(tmp_path)

    online = build_sdtm_ae_dataset(online_study, WIKI_PACKAGE, auto_approve=True)
    offline = build_sdtm_ae_dataset(offline_study, locked_package, auto_approve=True)

    assert online.canonical_dataset_sha256 == offline.canonical_dataset_sha256
    assert read_csv_rows(online_study / online.canonical_dataset_path) == read_csv_rows(
        offline_study / offline.canonical_dataset_path
    )
    online_trace = _read_json(online_study / online.traceability_report_path)
    offline_trace = _read_json(offline_study / offline.traceability_report_path)
    assert online_trace["context_sha256"] == offline_trace["context_sha256"]
    assert online_trace["applied_rules"] == offline_trace["applied_rules"]


def test_damaged_knowledge_package_stops_before_review(tmp_path: Path) -> None:
    study = _copy_fixture(tmp_path)
    package = _copy_wiki_package(tmp_path)
    (package / "approved-proposal-release.json").unlink()

    with pytest.raises(FileNotFoundError):
        build_sdtm_ae_dataset(study, package, auto_approve=True)

    assert not (study / ".review_queue" / "sdtm_spec_ae_v1_001.json").exists()
    assert not (study / "output" / "sdtm" / "datasets" / "ae.csv").exists()
