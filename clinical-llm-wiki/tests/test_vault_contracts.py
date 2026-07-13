"""Independent-repository acceptance checks for the governed Vault seed."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from service.app import create_app
from service.config import WikiServiceConfig
from service.contracts import SchemaBundle
from service.repository import VaultRepository, parse_markdown_card


ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault"
_WIKI_LINK = re.compile(r"(?<!!)\[\[([^\]]+)\]\]")


def _schema_for(record: dict[str, object]) -> str:
    return {
        "workflow_playbook": "knowledge/workflow-playbook.schema.json",
        "source_record": "knowledge/source.schema.json",
        "figure_record": "knowledge/figure.schema.json",
    }.get(str(record["type"]), "knowledge/knowledge-item.schema.json")


def _link_exists(origin: Path, target: str) -> bool:
    """Resolve simple Obsidian links against their note and the Vault root."""
    target = target.split("|", 1)[0].split("#", 1)[0].strip()
    if not target or target.startswith(("http://", "https://", "mailto:")):
        return True
    targets = [origin.parent / target, VAULT / target]
    for candidate in targets:
        markdown_candidate = candidate.parent / f"{candidate.name}.md"
        if candidate.exists() or markdown_candidate.exists():
            return True
    return False


def test_templates_validate_against_mirrored_engine_contracts() -> None:
    bundle = SchemaBundle.load(ROOT / "schemas" / "engine")
    templates = sorted(
        template for template in (VAULT / "90_System" / "Templates").glob("*.md")
        if template.name != "README.md"
    )
    assert {template.name for template in templates} >= {
        "knowledge-item.md", "workflow-playbook.md", "source-record.md", "figure-record.md"
    }
    for template in templates:
        record, _ = parse_markdown_card(ROOT, template)
        bundle.validate(_schema_for(record), record)


def test_home_navigation_and_all_internal_wiki_links_resolve() -> None:
    home = VAULT / "HOME.md"
    home_text = home.read_text(encoding="utf-8")
    for stage in (
        "Protocol Analysis", "SAP Generation", "SDTM Spec", "SDTM Programming", "ADaM Spec",
        "ADaM Programming", "TFL Shell Design", "TFL Programming", "QC Validation", "Submission Packaging",
    ):
        assert f"30_Workflows/Stages/{stage}" in home_text

    failures: list[str] = []
    for note in VAULT.rglob("*.md"):
        for raw_target in _WIKI_LINK.findall(note.read_text(encoding="utf-8")):
            if not _link_exists(note, raw_target):
                failures.append(f"{note.relative_to(VAULT)} -> {raw_target}")
    assert not failures, "unresolved internal Obsidian links: " + "; ".join(failures)


def test_real_vault_seed_is_production_eligible_and_resolves_runtime_context() -> None:
    config = WikiServiceConfig(vault_root=ROOT, schemas_dir=ROOT / "schemas" / "engine")
    app = create_app(config)
    repository: VaultRepository = app.state.repository
    seed = repository.get("wp-sdtm-spec-baseline")
    assert seed is not None
    assert seed.production_eligible is True, seed.eligibility_reasons

    client = TestClient(app)
    version = client.get("/api/v1/version").json()
    manifest = json.loads((ROOT / "tests" / "fixtures" / "study" / "runtime_manifest.json").read_text(encoding="utf-8"))
    response = client.post(
        "/api/v1/runtime-context/resolve",
        json={
            "study_id": "STUDY-001",
            "stage": "sdtm_spec",
            "runtime_manifest": manifest,
            "schema_bundle": {"version": version["bundle_version"], "sha256": version["bundle_sha256"]},
            "require_domain": False,
        },
    )
    assert response.status_code == 200, response.text
    context = response.json()
    assert context["executable"] is True
    assert [rule["rule_id"] for rule in context["workflow_rules"]] == ["wp-sdtm-spec-baseline"]
    # The response is the Engine ExecutionContext schema, which deliberately
    # stores schema_version rather than a second mutable bundle field.  The
    # request lock was checked before this response was constructed.
    assert context["schema_version"] == version["bundle_version"]


def test_first_release_service_configuration_rejects_non_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAL_WIKI_BIND_HOST", "0.0.0.0")
    with pytest.raises(ValueError, match="loopback"):
        WikiServiceConfig.from_environment()
