from __future__ import annotations

from importlib import import_module
import json
from pathlib import Path
import subprocess
import sys

from service.evaluation import GoldSuite


ROOT = Path(__file__).resolve().parents[1]


def _module():
    return import_module("scripts.ich_e9_poc")


def test_poc_identity_matches_the_checked_in_gold_suite() -> None:
    module = _module()
    suite = GoldSuite.model_validate_json(module.DEFAULT_GOLD_SUITE.read_text("utf-8"))

    assert module.SOURCE_ID == "src-ich-e9"
    assert module.SOURCE_VERSION == "1998-02-05"
    assert module.REGISTRATION_ACTOR_ID == "usr-p17-e9-curator"
    assert module.REGISTRATION_IDEMPOTENCY_KEY == "p17-ich-e9-1998-v1"
    assert module.expected_source_version_id() == suite.source_version_id
    assert module.ICH_E9_CHUNK_PROFILE_V1.chunk_profile_id == suite.chunk_profile_id
    assert module.ICH_E9_CHUNK_PROFILE_V1.version == suite.chunk_profile_version


def test_poc_help_is_local_and_does_not_start_docker_or_download() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.ich_e9_poc", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "ephemeral" in result.stdout.lower()
    assert result.stderr == ""


def test_checked_in_baseline_report_contains_no_source_text_when_present() -> None:
    module = _module()
    if not module.DEFAULT_REPORT.exists():
        return

    report = json.loads(module.DEFAULT_REPORT.read_text(encoding="utf-8"))
    assert report["evaluation"]["external_model_requests"] == 0
    assert report["evaluation"]["evaluation_notice"] == (
        "single_document_retrieval_baseline_not_clinical_quality_certification"
    )
    assert report["evaluation_operations"]["registered_suite_count"] == 1
    assert report["evaluation_operations"]["start_replay_stable"] is True
    assert report["evaluation_operations"]["case_replay_external_model_requests"] == 0
    assert report["evaluation_operations"]["self_regression_counts"] == {
        "improved": 0,
        "regressed": 0,
        "unchanged": 18,
        "added": 0,
        "removed": 0,
    }
    assert "content" not in json.dumps(report).lower()
