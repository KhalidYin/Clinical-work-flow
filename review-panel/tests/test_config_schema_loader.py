from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from review_panel.config import ReviewPanelConfig, ReviewPanelConfigError
from review_panel.schema_loader import ReviewSchemaError, ReviewSchemaLoader, read_json_file


REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_SCHEMA = REPO_ROOT / "clinical-workflow" / "schemas" / "review" / "review-protocol.schema.json"
REAL_REVIEW_ARCHIVE = REPO_ROOT / "clinical-llm-wiki" / ".review_queue" / "archive"


def test_config_resolves_repo_root_and_enforces_loopback():
    config = ReviewPanelConfig.from_repo_root(REPO_ROOT)

    assert config.repo_root == REPO_ROOT
    assert config.bind_host == "127.0.0.1"
    assert config.schema_path == REAL_SCHEMA

    with pytest.raises(ReviewPanelConfigError, match="loopback-only"):
        ReviewPanelConfig.from_repo_root(REPO_ROOT, bind_host="0.0.0.0")


def test_schema_loader_uses_engine_schema_for_real_review_triplet():
    schema = ReviewSchemaLoader(REAL_SCHEMA).load()

    packet = read_json_file(REAL_REVIEW_ARCHIVE / "sdtm_spec_sdtmig34_gold_v1_001.json")
    decision = read_json_file(
        REAL_REVIEW_ARCHIVE / "sdtm_spec_sdtmig34_gold_v1_001_decision.json"
    )
    confirmation = read_json_file(
        REAL_REVIEW_ARCHIVE / "sdtm_spec_sdtmig34_gold_v1_001_confirmation.json"
    )

    assert schema.validate("review_packet", packet) == []
    assert schema.validate("decision_receipt", decision) == []
    assert schema.validate("confirmation_receipt", confirmation) == []


def test_schema_loader_fails_when_schema_is_missing_or_damaged(tmp_path: Path):
    missing = tmp_path / "missing.schema.json"
    with pytest.raises(ReviewSchemaError, match="not found"):
        ReviewSchemaLoader(missing).load()

    damaged = tmp_path / "review-protocol.schema.json"
    damaged.write_text(json.dumps({"type": "object"}), encoding="utf-8")
    with pytest.raises(ReviewSchemaError, match="missing required definition"):
        ReviewSchemaLoader(damaged).load()


def copy_real_schema(repo_root: Path) -> None:
    schema_dir = repo_root / "clinical-workflow" / "schemas" / "review"
    schema_dir.mkdir(parents=True)
    shutil.copy2(REAL_SCHEMA, schema_dir / "review-protocol.schema.json")

