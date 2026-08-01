"""P0/P2 bounded POC runner flow tests."""

from __future__ import annotations

import hashlib
import csv
import json
from pathlib import Path
import shutil

from fastapi.testclient import TestClient
import pytest
import yaml

from src.agents.ae_metadata_poc import MAPPING_REVIEW_ID
from src.agents.ae_metadata_workflow import (
    CANONICAL_DATASET_PATH,
    PROGRAM_REVIEW_ID,
    prepare_validation_review,
)
from src.application_api import ApplicationApiConfig, create_app
from src.application_api.poc_models import PocState
from src.mcp_tools.edc_importer import SourceParseError
from src.runtime.review_protocol import (
    Decision,
    DecisionReceipt,
    FindingDecision,
    RejectionReason,
    ReviewQueue,
)


ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_FIXTURE = ROOT / "tests" / "fixtures" / "knowledge" / "sdtmig34-poc"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _study_container(tmp_path: Path) -> Path:
    container = tmp_path / "clinical-studies"
    study = container / "SAMPLE-AE-001"
    source = study / "input/edc/ae.csv"
    _write(
        source,
        "STUDYID,Subject,RecordPosition,AETERM,AESTDAT,AEENDAT,AESEV_STD,AESER_STD,"
        "AEREL_STD,AEACN_STD,AEOUT_STD,AETERM_PT,AETERM_SOC,"
        "AETERM_CoderDictName,AETERM_CoderDictVersion\n"
        "SAMPLE-AE-001,S001,1,Headache,01 JAN 2026,02 JAN 2026,MILD,N,NOT RELATED,"
        "NONE,RECOVERED,Headache,Nervous system disorders,MedDRA,27.0\n"
        "SAMPLE-AE-001,S001,2,Nausea,UN FEB 2026,,MODERATE,N,RELATED,"
        "DOSE NOT CHANGED,RECOVERING,Nausea,Gastrointestinal disorders,MedDRA,27.0\n",
    )
    _write(
        study / "project.yaml",
        'study_id: "SAMPLE-AE-001"\n'
        "synthetic_only: true\n"
        "standards:\n"
        '  sdtmig_version: "3.4"\n',
    )
    _write(
        study / "source-inventory.yaml",
        'inventory_id: "test-poc-inventory"\n'
        'status: "test"\n'
        "synthetic_only: true\n"
        "sources:\n"
        '  - path: "input/edc/ae.csv"\n'
        '    source_type: "edc_csv_dataset"\n'
        '    format: "csv"\n'
        '    role: "ae_source_data"\n'
        f'    sha256: "{_sha256(source)}"\n',
    )
    return container


def _client(container: Path) -> TestClient:
    return TestClient(
        create_app(
            ApplicationApiConfig(
                container_roots={"clinical-studies": container},
                poc_knowledge_package_root=KNOWLEDGE_FIXTURE,
            )
        )
    )


def _decide_all(study: Path, review_id: str, decision: Decision = Decision.APPROVED) -> None:
    queue = ReviewQueue(study)
    packet = queue.load_packet(review_id)
    assert packet is not None
    queue.submit_decision(
        DecisionReceipt(
            review_id=review_id,
            reviewer="POC flow reviewer",
            decisions=[
                FindingDecision(
                    finding_id=finding.id,
                    decision=decision,
                    rejection_reason=(
                        RejectionReason.INSUFFICIENT_EVIDENCE
                        if decision is Decision.REJECTED
                        else None
                    ),
                    comment="POC flow decision",
                )
                for finding in packet.findings_needing_decision()
            ],
        )
    )


def test_poc_runner_reaches_mapping_program_review_and_canonical(tmp_path: Path) -> None:
    container = _study_container(tmp_path)
    study = container / "SAMPLE-AE-001"
    client = _client(container)

    started = client.post(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs",
        json={"target_artifact": "sdtm_ae_dataset", "intent": "生成 AE POC"},
    )

    assert started.status_code == 202
    start_payload = started.json()
    assert start_payload["accepted"] is True
    assert start_payload["run_state"] == "blocked"
    assert (study / ".review_queue" / f"{MAPPING_REVIEW_ID}.json").exists()
    assert (study / "work/derived/edc/source-metadata.json").exists()
    assert (study / "work/derived/plans/minimum-information-sdtm-ae.json").exists()

    state = PocState.model_validate(
        client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    )
    assert state.run_id == start_payload["run_id"]
    assert state.active_step is not None
    assert state.active_step.review_id == MAPPING_REVIEW_ID
    assert state.blocker is not None
    assert state.blocker.kind.value == "review"
    wiki_step = next(step for step in state.steps if step.step_id == "wiki-context")
    mapping_step = next(step for step in state.steps if step.step_id == "mapping-spec")
    assert wiki_step.input_refs == [
        "work/derived/plans/minimum-information-sdtm-ae.json",
        "locked-knowledge/snapshots/snapshot-sdtmig34-core-events-ae-v1.json",
    ]
    assert {ref.relative_path for ref in wiki_step.artifact_refs} == {
        "work/knowledge/ae-wiki-context.json"
    }
    wiki_ref = wiki_step.artifact_refs[0]
    wiki_detail = client.get(
        f"/api/v1/studies/SAMPLE-AE-001/artifacts/{wiki_ref.artifact_id}"
    )
    assert wiki_detail.status_code == 200
    assert wiki_detail.json()["preview"]["value"]["scope"] == "p9-poc-test-only"
    assert len(wiki_detail.json()["preview"]["value"]["rules"]) == 5
    assert "work/knowledge/ae-wiki-context.json" in mapping_step.input_refs
    assert {ref.relative_path for ref in mapping_step.artifact_refs} >= {
        "work/mapping/ae-mapping-context.json",
        "work/mapping/ae-mapping-spec-candidate.json",
    }
    candidate_ref = next(
        ref
        for ref in mapping_step.artifact_refs
        if ref.relative_path == "work/mapping/ae-mapping-spec-candidate.json"
    )
    candidate_detail = client.get(
        f"/api/v1/studies/SAMPLE-AE-001/artifacts/{candidate_ref.artifact_id}"
    )
    assert candidate_detail.status_code == 200
    assert candidate_detail.json()["preview"]["value"]["target_dataset"] == "AE"
    assert {event.event_type for event in state.events} >= {
        "run_started",
        "mapping_review_written",
        "run_blocked",
    }

    _decide_all(study, MAPPING_REVIEW_ID)
    after_mapping = client.post(
        f"/api/v1/studies/SAMPLE-AE-001/poc-runs/{start_payload['run_id']}/resume",
        json={"reason": "review_decision_available", "review_id": MAPPING_REVIEW_ID},
    )

    assert after_mapping.status_code == 202
    assert after_mapping.json()["run_state"] == "blocked"
    assert (study / ".review_queue" / f"{PROGRAM_REVIEW_ID}.json").exists()
    assert (study / "programs/edc_to_sdtm/program-manifest.json").exists()
    assert (study / "output/sdtm/drafts/ae.csv").exists()
    after_mapping_state = PocState.model_validate(
        client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    )
    program_step = next(
        step for step in after_mapping_state.steps if step.step_id == "program-execution"
    )
    assert {ref.relative_path for ref in program_step.artifact_refs} >= {
        "programs/edc_to_sdtm/python/build_ae.py",
        "programs/edc_to_sdtm/r/build_ae.R",
        "programs/edc_to_sdtm/sas/build_ae.sas",
        "output/sdtm/drafts/ae.csv",
        "output/sdtm/logs/ae-reference-execution.json",
        "output/sdtm/traceability/ae-draft-traceability.json",
    }
    assert all(
        ref.preview_available
        for ref in program_step.artifact_refs
        if ref.relative_path.startswith("programs/edc_to_sdtm/")
    )
    sas_ref = next(
        ref
        for ref in program_step.artifact_refs
        if ref.relative_path == "programs/edc_to_sdtm/sas/build_ae.sas"
    )
    sas_detail = client.get(
        f"/api/v1/studies/SAMPLE-AE-001/artifacts/{sas_ref.artifact_id}"
    )
    assert sas_detail.status_code == 200
    assert sas_detail.json()["preview"]["kind"] == "text"

    _decide_all(study, PROGRAM_REVIEW_ID)
    after_program = client.post(
        f"/api/v1/studies/SAMPLE-AE-001/poc-runs/{start_payload['run_id']}/resume",
        json={"reason": "review_decision_available", "review_id": PROGRAM_REVIEW_ID},
    )

    assert after_program.status_code == 202
    assert after_program.json()["run_state"] == "done"
    assert (study / CANONICAL_DATASET_PATH).exists()
    done_state = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    assert done_state["run_state"] == "done"
    validation_step = next(
        step for step in done_state["steps"] if step["step_id"] == "validation-review"
    )
    assert all(check["state"] != "fail" for check in validation_step["checks"])
    canonical_step = next(
        step for step in done_state["steps"] if step["step_id"] == "canonical-ae"
    )
    assert {ref["relative_path"] for ref in canonical_step["artifact_refs"]} >= {
        "output/sdtm/datasets/ae.csv",
        "output/sdtm/traceability/ae-canonical-traceability.json",
    }
    assert any(event["event_type"] == "run_done" for event in done_state["events"])


def test_poc_runner_rejected_mapping_review_fails_closed(tmp_path: Path) -> None:
    container = _study_container(tmp_path)
    study = container / "SAMPLE-AE-001"
    client = _client(container)
    started = client.post(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs",
        json={"target_artifact": "sdtm_ae_dataset", "intent": "生成 AE POC"},
    ).json()

    _decide_all(study, MAPPING_REVIEW_ID, Decision.REJECTED)
    resumed = client.post(
        f"/api/v1/studies/SAMPLE-AE-001/poc-runs/{started['run_id']}/resume",
        json={"reason": "review_decision_available", "review_id": MAPPING_REVIEW_ID},
    )

    assert resumed.status_code == 202
    assert resumed.json()["run_state"] == "blocked"
    assert not (study / CANONICAL_DATASET_PATH).exists()
    state = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    assert state["run_state"] == "blocked"
    assert state["blocker"]["kind"] == "system"
    assert "rework" in state["blocking_reason"].lower()


def test_input_check_reports_raw_only_dependencies_and_blocks_duplicate_run(tmp_path: Path) -> None:
    container = _study_container(tmp_path)
    client = _client(container)
    started = client.post(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs",
        json={"target_artifact": "sdtm_ae_dataset", "intent": "生成 AE POC"},
    )
    assert started.status_code == 202
    before_events = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()["events"]

    duplicate = client.post(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs",
        json={"target_artifact": "sdtm_ae_dataset", "intent": "重复运行 AE POC"},
    )

    assert duplicate.status_code == 409
    state = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    assert state["events"] == before_events
    assert state["input_check"]["summary"]["required_ready"] == 1
    dependencies = {item["input_id"]: item for item in state["input_check"]["dependencies"]}
    assert dependencies["ae-source-data"]["status"] == "available"
    for input_id in ("protocol", "sap", "crf"):
        assert dependencies[input_id]["requirement"] == "not_required"
        assert dependencies[input_id]["blocking"] is False


@pytest.mark.parametrize(
    ("failure", "expected_code", "expected_recovery"),
    [
        ("missing", "source_file_missing", "provide_input"),
        ("hash", "source_hash_mismatch", "repair_input"),
        ("format", "unsupported_source_format", "repair_input"),
    ],
)
def test_input_check_classifies_source_failures(
    tmp_path: Path,
    failure: str,
    expected_code: str,
    expected_recovery: str,
) -> None:
    container = _study_container(tmp_path)
    study = container / "SAMPLE-AE-001"
    source = study / "input/edc/ae.csv"
    inventory_path = study / "source-inventory.yaml"
    inventory = yaml.safe_load(inventory_path.read_text(encoding="utf-8"))
    source_item = inventory["sources"][0]
    if failure == "missing":
        source.unlink()
    elif failure == "hash":
        source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    else:
        source_item["format"] = "parquet"
        inventory_path.write_text(yaml.safe_dump(inventory, sort_keys=False), encoding="utf-8")

    client = _client(container)
    response = client.post(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs",
        json={"target_artifact": "sdtm_ae_dataset", "intent": "检查 AE 输入"},
    )

    assert response.status_code == 202
    state = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    assert state["run_state"] == "blocked"
    assert state["active_step"]["step_id"] == "input-check"
    assert state["blocker"]["stage_id"] == "input-check"
    assert state["blocker"]["code"] == expected_code
    assert state["blocker"]["recovery_action"] == expected_recovery
    assert [step for step in state["steps"] if step["state"] == "blocked"] == [
        next(step for step in state["steps"] if step["step_id"] == "input-check")
    ]


def test_input_check_classifies_missing_parser_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    container = _study_container(tmp_path)

    def _missing_parser(*args: object, **kwargs: object) -> object:
        raise SourceParseError("pyreadstat is required for registered SAS/XPT sources")

    monkeypatch.setattr(
        "src.application_api.poc_runner.parse_registered_edc_source",
        _missing_parser,
    )
    client = _client(container)
    response = client.post(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs",
        json={"target_artifact": "sdtm_ae_dataset", "intent": "检查 parser"},
    )

    assert response.status_code == 202
    blocker = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()["blocker"]
    assert blocker["code"] == "parser_dependency_missing"
    assert blocker["recovery_action"] == "install_dependency"


def test_input_retry_rechecks_current_step_without_new_run(tmp_path: Path) -> None:
    container = _study_container(tmp_path)
    study = container / "SAMPLE-AE-001"
    source = study / "input/edc/ae.csv"
    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    client = _client(container)
    started = client.post(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs",
        json={"target_artifact": "sdtm_ae_dataset", "intent": "检查后重试"},
    ).json()
    inventory_path = study / "source-inventory.yaml"
    inventory = yaml.safe_load(inventory_path.read_text(encoding="utf-8"))
    inventory["sources"][0]["sha256"] = _sha256(source)
    inventory_path.write_text(yaml.safe_dump(inventory, sort_keys=False), encoding="utf-8")

    retried = client.post(
        f"/api/v1/studies/SAMPLE-AE-001/poc-runs/{started['run_id']}/resume",
        json={"reason": "retry_after_failure"},
    )

    assert retried.status_code == 202
    assert retried.json()["run_id"] == started["run_id"]
    state = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    assert state["blocker"]["kind"] == "review"
    assert state["blocker"]["stage_id"] == "mapping-spec"
    assert state["input_check"]["summary"]["required_ready"] == 1


def test_sas7bdat_aeterm_gaps_continue_to_program_review(tmp_path: Path) -> None:
    source_fixture = ROOT.parent / "clinical-studies/SAMPLE-AE-001/input/edc/ae09jun2025.sas7bdat"
    if not source_fixture.exists():
        pytest.skip("local SAS7BDAT POC fixture is unavailable")
    container = _study_container(tmp_path)
    study = container / "SAMPLE-AE-001"
    target = study / "input/edc/ae09jun2025.sas7bdat"
    shutil.copyfile(source_fixture, target)
    inventory_path = study / "source-inventory.yaml"
    inventory = yaml.safe_load(inventory_path.read_text(encoding="utf-8"))
    inventory["sources"][0].update(
        {"path": "input/edc/ae09jun2025.sas7bdat", "format": "sas7bdat", "sha256": _sha256(target)}
    )
    inventory_path.write_text(yaml.safe_dump(inventory, sort_keys=False), encoding="utf-8")
    client = _client(container)

    response = client.post(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs",
        json={"target_artifact": "sdtm_ae_dataset", "intent": "解析 SAS AE"},
    )

    assert response.status_code == 202
    input_check = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()["input_check"]
    source_file = input_check["files"][0]
    assert source_file["format"] == "sas7bdat"
    assert source_file["row_count"] == 1066
    assert source_file["column_count"] == 73
    assert source_file["labels_available"] is True
    assert source_file["formats_available"] is True
    assert source_file["value_labels_available"] is False
    profiles = {item["variable"]: item for item in input_check["variable_profiles"]}
    assert profiles["AETERM"]["label"]
    assert profiles["AETERM"]["missing_count"] == 128

    started = response.json()
    _decide_all(study, MAPPING_REVIEW_ID)
    resumed = client.post(
        f"/api/v1/studies/SAMPLE-AE-001/poc-runs/{started['run_id']}/resume",
        json={"reason": "review_decision_available", "review_id": MAPPING_REVIEW_ID},
    )
    assert resumed.status_code == 202
    state = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    assert state["blocker"]["kind"] == "review"
    assert state["blocker"]["review_id"] == PROGRAM_REVIEW_ID
    validation = json.loads(
        (study / "output/sdtm/validation/ae-reference-validation.json").read_text(
            encoding="utf-8"
        )
    )
    assert validation["blocking_findings"] == []
    assert validation["deferred_review_summary"][0]["variable"] == "AETERM"
    assert validation["deferred_review_summary"][0]["count"] == 128
    with (study / "output/sdtm/drafts/ae.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1066
    assert sum(1 for row in rows if not row["AETERM"]) == 128


def test_aeterm_missing_is_deferred_to_program_review_without_filtering(tmp_path: Path) -> None:
    container = _study_container(tmp_path)
    study = container / "SAMPLE-AE-001"
    source = study / "input/edc/ae.csv"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "SAMPLE-AE-001,S001,2,Nausea,",
            "SAMPLE-AE-001,S001,2,,",
        ),
        encoding="utf-8",
    )
    inventory_path = study / "source-inventory.yaml"
    inventory = yaml.safe_load(inventory_path.read_text(encoding="utf-8"))
    inventory["sources"][0]["sha256"] = _sha256(source)
    inventory_path.write_text(yaml.safe_dump(inventory, sort_keys=False), encoding="utf-8")
    client = _client(container)
    started = client.post(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs",
        json={"target_artifact": "sdtm_ae_dataset", "intent": "验证 AE 缺失"},
    ).json()
    _decide_all(study, MAPPING_REVIEW_ID)

    resumed = client.post(
        f"/api/v1/studies/SAMPLE-AE-001/poc-runs/{started['run_id']}/resume",
        json={"reason": "review_decision_available", "review_id": MAPPING_REVIEW_ID},
    )

    assert resumed.status_code == 202
    state = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    blocker = state["blocker"]
    assert blocker["kind"] == "review"
    assert blocker["stage_id"] == "validation-review"
    assert blocker["review_id"] == PROGRAM_REVIEW_ID
    packet = ReviewQueue(study).load_packet(PROGRAM_REVIEW_ID)
    assert packet is not None
    deferred = [finding for finding in packet.findings if "AETERM" in finding.title]
    assert len(deferred) == 1
    assert "1/2" in deferred[0].current_value
    assert not (study / CANONICAL_DATASET_PATH).exists()
    draft_path = study / "output/sdtm/drafts/ae.csv"
    assert draft_path.exists()
    with draft_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[1]["AETERM"] == ""

    validation_path = study / "output/sdtm/validation/ae-reference-validation.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    assert validation["blocking_findings"] == []
    assert validation["execution_allowed"] is True
    assert validation["deferred_review_summary"][0]["variable"] == "AETERM"
    assert validation["deferred_review_summary"][0]["count"] == 1
    program_step = next(item for item in state["steps"] if item["step_id"] == "program-execution")
    assert program_step["checks"][0]["state"] == "warning"

    _decide_all(study, PROGRAM_REVIEW_ID)
    promoted = client.post(
        f"/api/v1/studies/SAMPLE-AE-001/poc-runs/{started['run_id']}/resume",
        json={"reason": "review_decision_available", "review_id": PROGRAM_REVIEW_ID},
    )
    assert promoted.status_code == 202
    promoted_state = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    assert promoted_state["run_state"] == "done"
    with (study / CANONICAL_DATASET_PATH).open(newline="", encoding="utf-8") as handle:
        canonical_rows = list(csv.DictReader(handle))
    assert len(canonical_rows) == 2
    assert canonical_rows[1]["AETERM"] == ""
    canonical_trace = json.loads(
        (study / "output/sdtm/traceability/ae-canonical-traceability.json").read_text(
            encoding="utf-8"
        )
    )
    assert canonical_trace["deferred_review_summary"][0]["variable"] == "AETERM"


def test_structural_validation_finding_remains_evidence_addressed_blocker(
    tmp_path: Path,
) -> None:
    container = _study_container(tmp_path)
    study = container / "SAMPLE-AE-001"
    source = study / "input/edc/ae.csv"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "SAMPLE-AE-001,S001,2,Nausea,",
            "SAMPLE-AE-001,,2,Nausea,",
        ),
        encoding="utf-8",
    )
    inventory_path = study / "source-inventory.yaml"
    inventory = yaml.safe_load(inventory_path.read_text(encoding="utf-8"))
    inventory["sources"][0]["sha256"] = _sha256(source)
    inventory_path.write_text(yaml.safe_dump(inventory, sort_keys=False), encoding="utf-8")
    client = _client(container)
    started = client.post(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs",
        json={"target_artifact": "sdtm_ae_dataset", "intent": "验证 AE 结构阻断"},
    ).json()
    _decide_all(study, MAPPING_REVIEW_ID)

    resumed = client.post(
        f"/api/v1/studies/SAMPLE-AE-001/poc-runs/{started['run_id']}/resume",
        json={"reason": "review_decision_available", "review_id": MAPPING_REVIEW_ID},
    )

    assert resumed.status_code == 202
    state = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    blocker = state["blocker"]
    assert blocker["kind"] == "validation"
    assert blocker["stage_id"] == "validation-review"
    assert blocker["affected_variables"] == ["AESEQ", "USUBJID"]
    assert "/2" in blocker["summary"]
    assert "output/sdtm/validation/ae-reference-validation.json" in blocker["evidence_refs"]
    review_id = blocker["review_id"]
    packet = ReviewQueue(study).load_packet(review_id)
    assert packet is not None
    assert any("/2" in finding.current_value for finding in packet.findings)
    assert not (study / CANONICAL_DATASET_PATH).exists()
    assert not (study / "output/sdtm/drafts/ae.csv").exists()

    _decide_all(study, review_id)
    receipt_path = study / f".review_queue/{review_id}_decision.json"
    receipt_before = receipt_path.read_bytes()
    after_decision = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    enabled_actions = {
        item["action_id"] for item in after_decision["next_actions"] if item["enabled"]
    }
    assert "retry_current_step" in enabled_actions
    retried = client.post(
        f"/api/v1/studies/SAMPLE-AE-001/poc-runs/{started['run_id']}/resume",
        json={"reason": "retry_after_failure", "review_id": review_id},
    )
    assert retried.status_code == 202
    retried_state = client.get("/api/v1/studies/SAMPLE-AE-001/poc-state").json()
    assert retried_state["blocker"]["review_id"] == review_id
    assert receipt_path.read_bytes() == receipt_before

    validation_path = study / "output/sdtm/validation/ae-reference-validation.json"
    changed = json.loads(validation_path.read_text(encoding="utf-8"))
    changed["blocking_summary"][0]["count"] = 2
    validation_path.write_text(json.dumps(changed, indent=2) + "\n", encoding="utf-8")
    next_review = prepare_validation_review(study)
    assert next_review["review_id"] != review_id
    assert receipt_path.read_bytes() == receipt_before
