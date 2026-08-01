import csv
import json
from pathlib import Path

import pytest

from src.agents.ae_metadata_poc import (
    AEMetadataPOCError,
    MAPPING_APPROVED_PATH,
    MAPPING_CANDIDATE_PATH,
    MAPPING_CONTEXT_PATH,
    MAPPING_REVIEW_ID,
    WIKI_CONTEXT_PATH,
    prepare_metadata_mapping_review,
    validate_mapping_spec,
    write_metadata_wiki_context,
)
from src.agents.ae_metadata_workflow import (
    CANONICAL_DATASET_PATH,
    PROGRAM_REVIEW_ID,
    apply_program_review,
    run_after_mapping_approval,
)
from src.codegen.ae_programs import (
    PROGRAM_MANIFEST_PATH,
    generate_program_artifacts,
    run_python_reference,
)
from src.mcp_tools.edc_importer import parse_registered_edc_source
from src.runtime.minimum_information import (
    KnowledgeAvailability,
    TargetStandardLock,
    plan_minimum_information,
)
from src.runtime.review_protocol import (
    Decision,
    DecisionReceipt,
    FindingDecision,
    RejectionReason,
    ReviewQueue,
)


ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "tests" / "fixtures" / "knowledge" / "sdtmig34-poc"
SNAPSHOT_SHA = "d8aafb73ccca987d597e372435b664ba074c1a45688d5e2eef809c72f475a9ec"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _study(tmp_path: Path, *, include_reference: bool = False) -> Path:
    study = tmp_path / "SAMPLE-AE-001"
    source = study / "input/edc/ae.csv"
    source.parent.mkdir(parents=True)
    source.write_text(
        "STUDYID,Subject,RecordPosition,AETERM,AESTDAT,AEENDAT,AESEV_STD,AESER_STD,"
        "AEREL_STD,AEACN_STD,AEOUT_STD,AETERM_PT,AETERM_SOC,"
        "AETERM_CoderDictName,AETERM_CoderDictVersion\n"
        "SAMPLE-AE-001,S001,1,Headache,01 JAN 2026,02 JAN 2026,MILD,N,NOT RELATED,NONE,RECOVERED,"
        "Headache,Nervous system disorders,MedDRA,27.0\n"
        "SAMPLE-AE-001,S001,2,Nausea,UN FEB 2026,,MODERATE,N,RELATED,DOSE NOT CHANGED,RECOVERING,"
        "Nausea,Gastrointestinal disorders,MedDRA,27.0\n",
        encoding="utf-8",
    )
    source_sha = __import__("hashlib").sha256(source.read_bytes()).hexdigest()
    parsed = parse_registered_edc_source(
        "input/edc/ae.csv",
        "csv",
        allowed_root=study,
        expected_sha256=source_sha,
        generated_at="2026-07-16T10:00:00+00:00",
    )
    _write_json(study / "work/derived/edc/source-metadata.json", parsed.source_metadata)
    (study / "project.yaml").write_text(
        "study_id: SAMPLE-AE-001\nsynthetic_only: true\n",
        encoding="utf-8",
    )
    sources = [{
        "path": "input/edc/ae.csv", "source_type": "edc_csv_dataset",
        "format": "csv", "role": "ae_source_data", "sha256": source_sha,
    }]
    if include_reference:
        reference = study / "input/raw/subject-reference.csv"
        reference.parent.mkdir(parents=True)
        reference.write_text(
            "subject_id,usubjid,rfstdtc\nS001,SAMPLE-AE-001-S001,2026-01-01\n",
            encoding="utf-8",
        )
        sources.append({
            "path": "input/raw/subject-reference.csv", "source_type": "reference",
            "format": "csv", "role": "reference_date_source",
        })
    inventory = {
        "inventory_id": "test-inventory", "status": "test", "synthetic_only": True,
        "sources": sources,
    }
    plan = plan_minimum_information(
        study_id="SAMPLE-AE-001",
        source_inventory=inventory,
        source_metadata=parsed.source_metadata,
        target_standard=TargetStandardLock(
            standard="SDTMIG", version="3.4", locked=True, reference="test-standard-lock"
        ),
        knowledge=KnowledgeAvailability(
            available=True,
            snapshot_id="snapshot-sdtmig34-core-events-ae-v1",
            version="1.0.0",
            sha256=SNAPSHOT_SHA,
            reference="locked-knowledge/snapshots/snapshot-sdtmig34-core-events-ae-v1.json",
        ),
        available_source_paths={item["path"] for item in sources},
        generated_at="2026-07-16T10:01:00+00:00",
    )
    _write_json(
        study / "work/derived/plans/minimum-information-sdtm-ae.json",
        plan.model_dump(mode="json"),
    )
    return study


def _decide_all(study: Path, review_id: str, decision: Decision = Decision.APPROVED) -> None:
    queue = ReviewQueue(study)
    packet = queue.load_packet(review_id)
    assert packet is not None
    queue.submit_decision(DecisionReceipt(
        review_id=review_id,
        reviewer="POC regression reviewer",
        decisions=[
            FindingDecision(
                finding_id=finding.id,
                decision=decision,
                rejection_reason=(
                    RejectionReason.INSUFFICIENT_EVIDENCE
                    if decision == Decision.REJECTED else None
                ),
                comment="POC test decision",
            )
            for finding in packet.findings_needing_decision()
        ],
    ))


def test_raw_only_prepares_schema_valid_mapping_review_without_crf(tmp_path: Path) -> None:
    study = _study(tmp_path)

    result = prepare_metadata_mapping_review(
        study, WIKI, generated_at="2026-07-16T10:02:00+00:00"
    )
    candidate = json.loads((study / MAPPING_CANDIDATE_PATH).read_text(encoding="utf-8"))
    mapping_context = json.loads((study / MAPPING_CONTEXT_PATH).read_text(encoding="utf-8"))
    wiki_context = json.loads((study / WIKI_CONTEXT_PATH).read_text(encoding="utf-8"))
    packet = ReviewQueue(study).load_packet(MAPPING_REVIEW_ID)

    assert result["status"] == "mapping_review_required"
    assert wiki_context["scope"] == "p9-poc-test-only"
    assert wiki_context["production_eligible"] is False
    assert len(wiki_context["rules"]) == 5
    assert all(rule["locators"] for rule in wiki_context["rules"])
    assert mapping_context["knowledge"]["context_path"] == WIKI_CONTEXT_PATH
    assert (
        mapping_context["knowledge"]["context_sha256"]
        == wiki_context["context_sha256"]
    )
    assert validate_mapping_spec(candidate) == []
    assert candidate["arbitrary_commands_allowed"] is False
    assert {item["target_variable"] for item in candidate["mappings"]} >= {
        "STUDYID", "DOMAIN", "USUBJID", "AESEQ", "AETERM", "AESTDTC", "AEENDTC"
    }
    assert {gap["gap_id"] for gap in candidate["explicit_gaps"]} >= {
        "gap-controlled-value-labels", "gap-reference-date-identity-no-overlap"
    }
    assert packet is not None
    assert "CRF" in packet.findings[0].rationale
    assert not (study / MAPPING_APPROVED_PATH).exists()
    assert not (study / PROGRAM_MANIFEST_PATH).exists()


def test_study_local_wiki_context_is_idempotent_and_drift_guarded(
    tmp_path: Path,
) -> None:
    study = _study(tmp_path)
    first = write_metadata_wiki_context(
        study,
        WIKI,
        generated_at="2026-07-20T00:00:00+00:00",
    )
    before = (study / WIKI_CONTEXT_PATH).read_bytes()
    second = write_metadata_wiki_context(
        study,
        WIKI,
        generated_at="2026-07-21T00:00:00+00:00",
    )

    assert second == first
    assert (study / WIKI_CONTEXT_PATH).read_bytes() == before

    tampered = dict(first)
    tampered["rules"] = []
    (study / WIKI_CONTEXT_PATH).write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(AEMetadataPOCError, match="content hash drifted"):
        write_metadata_wiki_context(study, WIKI)


def test_mapping_hash_tamper_and_unknown_operation_fail_closed(tmp_path: Path) -> None:
    study = _study(tmp_path)
    prepare_metadata_mapping_review(study, WIKI)
    candidate = json.loads((study / MAPPING_CANDIDATE_PATH).read_text(encoding="utf-8"))
    candidate["mappings"][0]["operation"] = "run_shell"
    assert any("operation" in item for item in validate_mapping_spec(candidate))

    _decide_all(study, MAPPING_REVIEW_ID)
    (study / MAPPING_CANDIDATE_PATH).write_text(json.dumps(candidate), encoding="utf-8")
    with pytest.raises(AEMetadataPOCError, match="drifted"):
        run_after_mapping_approval(study)
    assert not (study / CANONICAL_DATASET_PATH).exists()


def test_approved_mapping_drives_three_languages_python_draft_and_promotion(
    tmp_path: Path,
) -> None:
    study = _study(tmp_path)
    prepare_metadata_mapping_review(study, WIKI)
    _decide_all(study, MAPPING_REVIEW_ID)

    execution = run_after_mapping_approval(study)
    manifest = json.loads((study / PROGRAM_MANIFEST_PATH).read_text(encoding="utf-8"))
    approved = json.loads((study / MAPPING_APPROVED_PATH).read_text(encoding="utf-8"))
    with (study / execution["draft_dataset_path"]).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert execution["status"] == "program_review_required"
    assert {item["language"] for item in manifest["programs"]} == {"python", "r", "sas"}
    assert manifest["mapping_spec_sha256"] == approved["spec_sha256"]
    assert all(approved["spec_sha256"] in (study / item["path"]).read_text(encoding="utf-8")
               for item in manifest["programs"])
    assert rows[0]["AESTDTC"] == "2026-01-01"
    assert rows[1]["AESTDTC"] == "2026-02"
    assert "AESEV" not in rows[0]
    assert not (study / CANONICAL_DATASET_PATH).exists()

    _decide_all(study, PROGRAM_REVIEW_ID)
    promoted = apply_program_review(study)
    canonical_trace = json.loads(
        (study / promoted["canonical_traceability_path"]).read_text(encoding="utf-8")
    )
    assert promoted["status"] == "canonical_written"
    assert (study / CANONICAL_DATASET_PATH).exists()
    assert {gap["gap_id"] for gap in canonical_trace["explicit_gaps"]} >= {
        "gap-controlled-value-labels", "gap-reference-date-identity-no-overlap"
    }
    assert all(rule["locators"] for rule in canonical_trace["rule_evidence"].values())


def test_program_rejection_and_program_hash_drift_never_promote(tmp_path: Path) -> None:
    rejected_study = _study(tmp_path / "rejected")
    prepare_metadata_mapping_review(rejected_study, WIKI)
    _decide_all(rejected_study, MAPPING_REVIEW_ID)
    run_after_mapping_approval(rejected_study)
    _decide_all(rejected_study, PROGRAM_REVIEW_ID, Decision.REJECTED)
    assert apply_program_review(rejected_study)["status"] == "rework_required"
    assert not (rejected_study / CANONICAL_DATASET_PATH).exists()

    drifted_study = _study(tmp_path / "drifted")
    prepare_metadata_mapping_review(drifted_study, WIKI)
    _decide_all(drifted_study, MAPPING_REVIEW_ID)
    from src.agents.ae_metadata_poc import approve_mapping_from_receipt
    approve_mapping_from_receipt(drifted_study)
    manifest = generate_program_artifacts(drifted_study)
    python_path = drifted_study / next(
        item["path"] for item in manifest["programs"] if item["language"] == "python"
    )
    python_path.write_text(python_path.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
    with pytest.raises(AEMetadataPOCError, match="program hash drifted"):
        run_python_reference(drifted_study)
    assert not (drifted_study / CANONICAL_DATASET_PATH).exists()


def test_missing_registered_source_and_snapshot_tamper_fail_before_mapping(tmp_path: Path) -> None:
    study = _study(tmp_path / "missing")
    (study / "input/edc/ae.csv").unlink()
    with pytest.raises(Exception):
        prepare_metadata_mapping_review(study, WIKI)

    study2 = _study(tmp_path / "snapshot")
    wiki_copy = tmp_path / "wiki"
    snapshot_source = WIKI / "snapshots/snapshot-sdtmig34-core-events-ae-v1.json"
    snapshot_target = wiki_copy / "snapshots/snapshot-sdtmig34-core-events-ae-v1.json"
    snapshot_target.parent.mkdir(parents=True)
    snapshot = json.loads(snapshot_source.read_text(encoding="utf-8"))
    snapshot["items"][0]["title"] = "tampered"
    _write_json(snapshot_target, snapshot)
    release_source = WIKI / "sources/packages/src-cdisc-sdtmig-3-4/approved-proposal-release.json"
    release_target = wiki_copy / "sources/packages/src-cdisc-sdtmig-3-4/approved-proposal-release.json"
    release_target.parent.mkdir(parents=True)
    release_target.write_bytes(release_source.read_bytes())
    with pytest.raises(AEMetadataPOCError, match="snapshot content hash drifted"):
        prepare_metadata_mapping_review(study2, wiki_copy)
