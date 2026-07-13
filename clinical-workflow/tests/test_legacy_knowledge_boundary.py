"""Prove deprecated v2.1 knowledge cannot silently re-enter production paths."""

from __future__ import annotations

from pathlib import Path

from src.knowledge import clinical_standards


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_knowledge_is_explicitly_migration_source_only() -> None:
    assert clinical_standards.LEGACY_COMPATIBILITY_STATUS == "migration_source_only"
    assert clinical_standards.CDISC_KNOWLEDGE  # compatibility surface remains readable


def test_production_modules_do_not_import_legacy_knowledge() -> None:
    production_roots = (
        ROOT / "src/runtime",
        ROOT / "src/agents",
        ROOT / "src/mcp_tools",
        ROOT / "src/config",
        ROOT / "src/change_management",
        ROOT / "src/knowledge",
    )
    offenders: list[str] = []
    for root in production_roots:
        for path in root.rglob("*.py"):
            if path.name == "clinical_standards.py":
                continue
            if "clinical_standards" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, "production imports deprecated hardcoded knowledge: " + ", ".join(
        offenders
    )
