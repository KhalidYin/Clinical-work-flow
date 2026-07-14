from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from review_panel.config import ReviewPanelConfig
from review_panel.contracts import QueueKind
from review_panel.queue_registry import QueueRegistry, QueueRegistryError, UnknownQueueError


REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_SCHEMA = REPO_ROOT / "clinical-workflow" / "schemas" / "review" / "review-protocol.schema.json"


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "clinical-workflow" / "schemas" / "review").mkdir(parents=True)
    shutil.copy2(
        REAL_SCHEMA,
        repo / "clinical-workflow" / "schemas" / "review" / "review-protocol.schema.json",
    )
    (repo / "clinical-llm-wiki").mkdir()
    (repo / "clinical-studies").mkdir()
    return repo


def write_marker(queue_path: Path, *, scope: str, owner_root: Path) -> None:
    (queue_path / ".queue_scope.json").write_text(
        json.dumps({"scope": scope, "owner_root": str(owner_root.resolve())}, indent=2),
        encoding="utf-8",
    )


def test_registry_discovers_only_trusted_allowlist(tmp_path: Path):
    repo = make_repo(tmp_path)
    platform_queue = repo / ".review_queue"
    wiki_queue = repo / "clinical-llm-wiki" / ".review_queue"
    study_queue = repo / "clinical-studies" / "STUDY-001" / ".review_queue"
    ignored_queue = repo / "clinical-llm-wiki" / "vault" / "nested" / ".review_queue"

    platform_queue.mkdir()
    write_marker(platform_queue, scope="platform", owner_root=repo)
    wiki_queue.mkdir()
    write_marker(wiki_queue, scope="wiki", owner_root=repo / "clinical-llm-wiki")
    study_queue.mkdir(parents=True)
    write_marker(study_queue, scope="study", owner_root=repo / "clinical-studies" / "STUDY-001")
    ignored_queue.mkdir(parents=True)

    config = ReviewPanelConfig.from_repo_root(repo)
    queues = {queue.queue_id: queue for queue in QueueRegistry(config).discover()}

    assert set(queues) == {"platform", "wiki", "study-study-001"}
    assert queues["platform"].queue_kind == QueueKind.PLATFORM
    assert queues["wiki"].queue_kind == QueueKind.WIKI
    assert queues["study-study-001"].queue_kind == QueueKind.STUDY
    assert queues["wiki"].to_public_dict() == {
        "queue_id": "wiki",
        "queue_kind": "wiki",
        "owner_label": "Clinical LLM Wiki",
        "protocol_scope": "wiki",
    }


def test_registry_ignores_missing_queues(tmp_path: Path):
    repo = make_repo(tmp_path)
    config = ReviewPanelConfig.from_repo_root(repo)

    assert QueueRegistry(config).discover() == []


def test_registry_rejects_scope_marker_mismatch(tmp_path: Path):
    repo = make_repo(tmp_path)
    wiki_queue = repo / "clinical-llm-wiki" / ".review_queue"
    wiki_queue.mkdir()
    write_marker(wiki_queue, scope="study", owner_root=repo / "clinical-llm-wiki")

    config = ReviewPanelConfig.from_repo_root(repo)
    with pytest.raises(QueueRegistryError, match="scope marker mismatch"):
        QueueRegistry(config).discover()


def test_registry_rejects_unknown_queue_id(tmp_path: Path):
    repo = make_repo(tmp_path)
    (repo / "clinical-llm-wiki" / ".review_queue").mkdir()

    config = ReviewPanelConfig.from_repo_root(repo)
    registry = QueueRegistry(config)

    with pytest.raises(UnknownQueueError, match="Unknown queue_id"):
        registry.require_queue("study-does-not-exist")
    with pytest.raises(UnknownQueueError, match="Invalid queue_id"):
        registry.require_queue("../wiki")


def test_registry_rejects_symlink_queue_escape(tmp_path: Path):
    if os.name == "nt":
        pytest.skip("Windows symlink privileges are environment-dependent.")

    repo = make_repo(tmp_path)
    outside = tmp_path / "outside-queue"
    outside.mkdir()
    link = repo / "clinical-llm-wiki" / ".review_queue"
    link.symlink_to(outside, target_is_directory=True)

    config = ReviewPanelConfig.from_repo_root(repo)
    with pytest.raises(QueueRegistryError, match="escapes trusted root"):
        QueueRegistry(config).discover()

