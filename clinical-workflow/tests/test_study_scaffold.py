"""P4 checks for the self-contained Study filesystem contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import (
    ProjectConfigError,
    RuntimeManifestConfigError,
    load_project_config,
    load_runtime_manifest,
    resolve_project_path,
)


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "study_template"
MINIMAL_STUDY = ROOT / "tests" / "fixtures" / "studies" / "minimal"


def test_template_is_the_final_study_tree_without_legacy_workflow_state() -> None:
    expected_paths = (
        "workflow/overrides",
        "workflow/decisions",
        "workflow/snapshots",
        "workflow/promotion_candidates",
        "knowledge/overrides",
        "knowledge/decisions",
        "knowledge/snapshots",
        "knowledge/promotion_candidates",
        "input/protocol",
        "input/sap",
        "input/edc",
        "input/external",
        "output/protocol",
        "output/sap",
        "output/sdtm",
        "output/adam",
        "output/tfl",
        "output/qc",
        "output/submission",
        ".review_queue",
    )

    assert not (TEMPLATE / ".workflow").exists()
    assert (TEMPLATE / "audit_trail.jsonl").is_file()
    assert all((TEMPLATE / path).is_dir() for path in expected_paths)


def test_template_and_knowledge_enabled_fixture_load_exact_p2_manifest() -> None:
    template_project = load_project_config(TEMPLATE, required=True)
    template_manifest = load_runtime_manifest(TEMPLATE, required=True)
    fixture_project = load_project_config(MINIMAL_STUDY, required=True)
    fixture_manifest = load_runtime_manifest(MINIMAL_STUDY, required=True)

    assert template_project is not None
    assert template_manifest is not None
    assert template_manifest.study_id == template_project.study_id
    assert template_manifest.policies.live_upgrade == "forbidden"
    assert template_manifest.policies.fallback == "locked_snapshot_only"
    assert fixture_project is not None
    assert fixture_manifest is not None
    assert fixture_manifest.study_id == fixture_project.study_id
    assert fixture_manifest.workflow_knowledge.fallback_path.startswith("workflow/")
    assert fixture_manifest.domain_knowledge.fallback_path.startswith("knowledge/")


def test_study_config_paths_cannot_discover_a_sibling_repository() -> None:
    with pytest.raises(ProjectConfigError, match="escape"):
        resolve_project_path(
            MINIMAL_STUDY,
            "../../../../../clinical-llm-wiki/snapshots/a.json",
        )

    with pytest.raises(ProjectConfigError, match="relative"):
        resolve_project_path(
            MINIMAL_STUDY,
            "G:/Project/Python/Clinical work flow/clinical-llm-wiki",
        )


def test_runtime_manifest_rejects_snapshot_path_traversal(tmp_path: Path) -> None:
    manifest = (MINIMAL_STUDY / "runtime-manifest.yaml").read_text(encoding="utf-8")
    (tmp_path / "runtime-manifest.yaml").write_text(
        manifest.replace(
            "workflow/snapshots/workflow-001.json", "../outside/workflow.json"
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeManifestConfigError, match="fallback path"):
        load_runtime_manifest(tmp_path, required=True)
