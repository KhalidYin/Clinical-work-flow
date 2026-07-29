from __future__ import annotations

from pathlib import Path

import yaml

from src.runtime.pipeline_contract import PipelineStage


ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "clinical-studies" / "SYNTH-E2E-001"


def test_p11_scaffold_is_synthetic_and_not_executable() -> None:
    project = yaml.safe_load((STUDY / "project.yaml").read_text(encoding="utf-8"))
    manifest = yaml.safe_load(
        (STUDY / "runtime-manifest.draft.yaml").read_text(encoding="utf-8")
    )

    assert project["study_id"] == "SYNTH-E2E-001"
    assert project["synthetic_only"] is True
    assert project["scaffold_status"] == "p11_g0_contract_only"
    assert not (STUDY / "runtime-manifest.yaml").exists()
    assert manifest["execution_boundary"]["executable"] is False
    assert set(manifest["required_locks"].values()) == {"not_locked"}


def test_p11_artifact_inventory_declares_exact_canonical_order() -> None:
    inventory = yaml.safe_load(
        (STUDY / "artifact-inventory.yaml").read_text(encoding="utf-8")
    )
    stages = inventory["stages"]

    assert inventory["inventory_status"] == "planned"
    assert [stage["ordinal"] for stage in stages] == list(range(1, 11))
    assert [stage["stage_id"] for stage in stages] == [
        stage.value for stage in PipelineStage
    ]
    assert {stage["status"] for stage in stages} == {"planned"}


def test_p11_gate_evidence_is_not_precreated_in_review_queue() -> None:
    queue_files = {
        path.name for path in (STUDY / ".review_queue").iterdir() if path.is_file()
    }

    assert queue_files == {"README.md"}
    assert not list(STUDY.rglob("P11-G*.md"))
