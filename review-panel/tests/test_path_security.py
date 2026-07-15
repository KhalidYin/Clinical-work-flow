from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from review_panel.app import create_app
from test_review_api import REAL_SCHEMA, packet, write_packet


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


def test_source_endpoint_rejects_undeclared_index_and_path_traversal(tmp_path: Path):
    repo = make_repo(tmp_path)
    (repo / "secret.txt").write_text("secret", encoding="utf-8")
    write_packet(repo, packet(source_documents=["../secret.txt"]))
    client = TestClient(create_app(repo))

    undeclared = client.get("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001/sources/9")
    assert undeclared.status_code == 404

    traversal = client.get("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001/sources/0")
    assert traversal.status_code == 403


def test_source_endpoint_rejects_symlink_escape(tmp_path: Path):
    if os.name == "nt":
        pytest.skip("Windows symlink privileges are environment-dependent.")

    repo = make_repo(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    link = repo / "clinical-llm-wiki" / "linked.txt"
    link.symlink_to(outside)
    write_packet(repo, packet(source_documents=["linked.txt"]))
    client = TestClient(create_app(repo))

    response = client.get("/api/v1/reviews/wiki/sdtm_spec_ae_v1_001/sources/0")
    assert response.status_code == 403


def test_browser_never_controls_disk_paths(tmp_path: Path):
    repo = make_repo(tmp_path)
    write_packet(repo, packet())
    client = TestClient(create_app(repo))

    response = client.get("/api/v1/reviews/..%2Fclinical-llm-wiki/sdtm_spec_ae_v1_001")

    assert response.status_code == 404
    assert not any(repo.rglob("*_decision.json"))
