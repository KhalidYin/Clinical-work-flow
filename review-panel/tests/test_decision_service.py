from __future__ import annotations

import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from review_panel.config import ReviewPanelConfig
from review_panel.decision_service import DecisionService
from review_panel.queue_registry import QueueRegistry
from review_panel.repository import ReviewRepository
from review_panel.schema_loader import ReviewSchemaLoader
from test_review_api import REAL_SCHEMA, decision_body, packet, write_packet


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "clinical-workflow" / "schemas" / "review").mkdir(parents=True)
    shutil.copy2(
        REAL_SCHEMA,
        repo / "clinical-workflow" / "schemas" / "review" / "review-protocol.schema.json",
    )
    (repo / "clinical-studies").mkdir()
    (repo / "clinical-llm-wiki" / ".review_queue").mkdir(parents=True)
    return repo


def service_for(repo: Path) -> DecisionService:
    config = ReviewPanelConfig.from_repo_root(repo)
    schema = ReviewSchemaLoader(config.schema_path).load()
    repository = ReviewRepository(config, QueueRegistry(config), schema)
    return DecisionService(repository)


def test_concurrent_submissions_create_one_receipt(tmp_path: Path):
    repo = make_repo(tmp_path)
    write_packet(repo, packet())
    service = service_for(repo)
    detail = service.repository.get_detail("wiki", "sdtm_spec_ae_v1_001")
    body = decision_body(detail["packet_sha256"])

    def submit() -> str:
        try:
            service.submit_decision("wiki", "sdtm_spec_ae_v1_001", body)
            return "ok"
        except Exception as exc:
            return exc.__class__.__name__

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(lambda _item: submit(), range(2)))

    assert results == ["ReceiptExistsError", "ok"]
    receipts = list((repo / "clinical-llm-wiki" / ".review_queue").glob("*_decision.json"))
    assert len(receipts) == 1


def test_write_failure_leaves_no_receipt_or_temp_file(tmp_path: Path, monkeypatch):
    repo = make_repo(tmp_path)
    write_packet(repo, packet())
    service = service_for(repo)
    detail = service.repository.get_detail("wiki", "sdtm_spec_ae_v1_001")

    def fail_link(_source: str, _target: Path) -> None:
        raise OSError("simulated link failure")

    monkeypatch.setattr(os, "link", fail_link)

    try:
        service.submit_decision(
            "wiki",
            "sdtm_spec_ae_v1_001",
            decision_body(detail["packet_sha256"]),
        )
    except Exception as exc:
        assert exc.__class__.__name__ == "ReviewValidationError"

    queue = repo / "clinical-llm-wiki" / ".review_queue"
    assert not (queue / "sdtm_spec_ae_v1_001_decision.json").exists()
    assert not list(queue.glob("*.tmp"))


def test_written_receipt_satisfies_engine_schema(tmp_path: Path):
    repo = make_repo(tmp_path)
    write_packet(repo, packet())
    service = service_for(repo)
    detail = service.repository.get_detail("wiki", "sdtm_spec_ae_v1_001")

    service.submit_decision(
        "wiki",
        "sdtm_spec_ae_v1_001",
        decision_body(detail["packet_sha256"]),
    )
    receipt = json.loads(
        (repo / "clinical-llm-wiki" / ".review_queue" / "sdtm_spec_ae_v1_001_decision.json")
        .read_text(encoding="utf-8")
    )

    assert service.repository.schema.validate("decision_receipt", receipt) == []

