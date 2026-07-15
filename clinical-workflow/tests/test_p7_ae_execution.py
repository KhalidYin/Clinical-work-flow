"""P7-P3 controlled AE execution and validation gate."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from src.agents.ae_execution import AEExecutionError, run_controlled_ae_execution


ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = ROOT.parent
FIXTURE = ROOT / "tests" / "fixtures" / "studies" / "ae-pilot"
WIKI_PACKAGE = (
    PLATFORM_ROOT
    / "clinical-llm-wiki"
    / "sources"
    / "packages"
    / "src-cdisc-sdtmig-3-4"
)


def _copy_fixture(tmp_path: Path) -> Path:
    study = tmp_path / "ae-pilot"
    shutil.copytree(FIXTURE, study)
    return study


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_controlled_ae_execution_writes_draft_artifacts_and_provenance(
    tmp_path: Path,
) -> None:
    study = _copy_fixture(tmp_path)

    result = run_controlled_ae_execution(study, WIKI_PACKAGE)

    assert result.status == "draft_written"
    assert result.adapter_id == "p7_synthetic_ae_python_adapter_v1"
    assert result.canonical_dataset_path is None
    assert result.draft_dataset_path == "output/sdtm/drafts/ae.csv"
    assert result.draft_dataset_sha256
    assert set(result.applied_mapping_ids) == {
        "map-ae-studyid",
        "map-ae-domain",
        "map-ae-usubjid",
        "map-ae-aeseq",
        "map-ae-aeterm",
        "map-ae-aestdtc",
        "map-ae-aeendtc",
        "map-ae-aestdy",
        "map-ae-aeendy",
    }

    draft_path = study / result.draft_dataset_path
    assert _read_csv(draft_path) == _read_csv(study / "expected" / "sdtm" / "ae.csv")
    assert hashlib.sha256(draft_path.read_bytes()).hexdigest() == result.draft_dataset_sha256

    program = _read_json(study / result.program_manifest_path)
    assert program["arbitrary_command_allowed"] is False
    assert program["network_access"] is False
    assert program["canonical_output_allowed"] is False
    assert {step["mapping_id"] for step in program["steps"]} == set(result.applied_mapping_ids)
    assert all(step["rule_refs"] for step in program["steps"])

    validation = _read_json(study / result.validation_report_path)
    assert validation["passed"] is True
    assert validation["blocking_findings"] == []
    assert validation["canonical_dataset_allowed"] is False

    provenance = _read_json(study / result.provenance_path)
    assert provenance["draft_dataset_sha256"] == result.draft_dataset_sha256
    assert provenance["canonical_dataset_path"] is None
    assert provenance["context_sha256"] == result.context_sha256
    assert set(provenance["applied_rule_evidence"]) == set(result.applied_rule_refs)
    assert all(provenance["applied_rule_evidence"].values())


def test_controlled_ae_execution_rejects_unregistered_adapter(tmp_path: Path) -> None:
    study = _copy_fixture(tmp_path)

    with pytest.raises(AEExecutionError, match="unregistered AE execution adapter"):
        run_controlled_ae_execution(study, WIKI_PACKAGE, adapter_id="python")


def test_controlled_ae_execution_rejects_arbitrary_command_arguments(
    tmp_path: Path,
) -> None:
    study = _copy_fixture(tmp_path)

    with pytest.raises(AEExecutionError, match="script_path"):
        run_controlled_ae_execution(
            study,
            WIKI_PACKAGE,
            extra_action_arguments={"script_path": "scripts/run_anything.py"},
        )


def test_controlled_ae_execution_blocks_validation_without_canonical_artifact(
    tmp_path: Path,
) -> None:
    study = _copy_fixture(tmp_path)
    expected_path = study / "expected" / "sdtm" / "ae.csv"
    expected_text = expected_path.read_text(encoding="utf-8")
    expected_path.write_text(expected_text.replace("Headache", "Migraine"), encoding="utf-8")
    new_hash = hashlib.sha256(expected_path.read_bytes()).hexdigest()
    manifest_path = study / "fixture-manifest.json"
    manifest = _read_json(manifest_path)
    for item in manifest["source_files"]:
        if item["path"] == "expected/sdtm/ae.csv":
            item["sha256"] = new_hash
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    result = run_controlled_ae_execution(study, WIKI_PACKAGE)

    assert result.status == "blocked"
    assert result.draft_dataset_path is None
    assert result.canonical_dataset_path is None
    assert result.blocking_findings == ("VAL-AE-001",)
    assert not (study / "output" / "sdtm" / "drafts" / "ae.csv").exists()
    validation = _read_json(study / result.validation_report_path)
    assert validation["passed"] is False
    assert validation["blocking_findings"][0]["category"] == "dataset_mismatch"
