"""P6-P2-D compact audit report and blocking human gate tests."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator
import pytest

from scripts.pdf.structure_map_review import (
    DEFAULT_REVIEW_LANGUAGE,
    PACKET_NAME,
    REPORT_NAME,
    REVIEW_ID,
    build_structure_review_artifacts,
    build_structure_review_packet,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "sources" / "packages" / "src-cdisc-sdtmig-3-4"
REPORT = PACKAGE / REPORT_NAME
ACTIVE_PACKET = ROOT / ".review_queue" / PACKET_NAME
PACKET = ROOT / ".review_queue" / "archive" / PACKET_NAME


def _read(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema_definition(name: str) -> dict[str, object]:
    schema = _read(
        ROOT.parent
        / "clinical-workflow"
        / "schemas"
        / "review"
        / "review-protocol.schema.json"
    )
    definition = deepcopy(schema["$defs"][name])  # type: ignore[index]
    definition.pop("$id", None)
    definition["$schema"] = schema["$schema"]
    definition["$defs"] = schema["$defs"]
    return definition


def test_structure_review_report_closes_all_machine_checks() -> None:
    report = _read(REPORT)
    assert report["review_id"] == REVIEW_ID
    assert report["gate_status"] == "pending_human_review"
    assert report["summary"] == {
        "checks_failed": 0,
        "checks_passed": 8,
        "checks_total": 8,
        "human_findings_pending": 8,
    }
    checks = report["checks"]
    assert [item["check_id"] for item in checks] == [  # type: ignore[index]
        f"CHK-{index:03d}" for index in range(1, 9)
    ]
    assert {item["status"] for item in checks} == {"passed"}  # type: ignore[index]
    assert report["visual_qa"]["human_review"] == "pending"  # type: ignore[index]


def test_structure_review_hashes_are_bound_to_p2_summaries() -> None:
    report = _read(REPORT)
    base = _read(PACKAGE / "structure-map-summary.json")
    deep = _read(PACKAGE / "deep-structure-summary.json")
    bindings = report["source_bindings"]
    assert bindings["base_structure_map_sha256"] == base["structure_map_sha256"]  # type: ignore[index]
    assert bindings["deep_structure_map_sha256"] == deep[  # type: ignore[index]
        "deep_structure_map_sha256"
    ]
    assert bindings["source_sha256"] == base["source_sha256"] == deep[  # type: ignore[index]
        "source_sha256"
    ]


def test_structure_review_packet_is_blocking_and_schema_valid() -> None:
    packet = _read(PACKET)
    Draft202012Validator(_schema_definition("review_packet")).validate(packet)
    assert packet["review_id"] == REVIEW_ID
    assert packet["review_type"] == "sdtm_spec"
    assert packet["urgency"] == "blocking"
    assert packet["auto_approved_count"] == 0
    findings = packet["findings"]
    assert [item["id"] for item in findings] == [  # type: ignore[index]
        f"F-{index:03d}" for index in range(1, 9)
    ]
    assert all(not item["auto_approved"] for item in findings)  # type: ignore[index]


def test_review_sources_are_repo_metadata_not_restricted_or_derived_files() -> None:
    packet = _read(PACKET)
    source_documents = packet["source_documents"]
    assert source_documents
    for declared in source_documents:  # type: ignore[union-attr]
        path = ROOT / declared
        assert path.is_file(), declared
        normalized = path.relative_to(ROOT).as_posix()
        assert "/original/" not in normalized
        assert "/derived/" not in normalized
        assert path.suffix not in {".pdf", ".xlsx"}


def test_gate_triplet_is_archived_after_human_approval() -> None:
    assert PACKET.is_file()
    assert PACKET.with_name(f"{REVIEW_ID}_decision.json").is_file()
    assert PACKET.with_name(f"{REVIEW_ID}_confirmation.json").is_file()
    assert not ACTIVE_PACKET.exists()
    assert not ACTIVE_PACKET.with_name(f"{REVIEW_ID}_decision.json").exists()
    assert not ACTIVE_PACKET.with_name(f"{REVIEW_ID}_confirmation.json").exists()


def test_local_maps_reproduce_committed_review_artifacts_when_available() -> None:
    if not (PACKAGE / "derived" / "structure-map.json").is_file():
        pytest.skip("local-only P2 maps are not present")
    if not (PACKAGE / "derived" / "structure-map-deep.json").is_file():
        pytest.skip("local-only P2 deep map is not present")

    packet = _read(PACKET)
    report, rebuilt_packet = build_structure_review_artifacts(
        ROOT,
        created_at=packet["created_at"],  # type: ignore[arg-type]
        packet_language="en",
    )
    assert report == _read(REPORT)
    assert rebuilt_packet == packet


def test_future_structure_review_packets_default_to_chinese_human_text() -> None:
    packet = build_structure_review_packet(
        created_at="2026-07-15T13:40:00+08:00",
        base_hash="a" * 64,
        deep_hash="b" * 64,
    )
    assert DEFAULT_REVIEW_LANGUAGE == "zh-CN"
    human_text = [packet["agent_summary"]]
    for finding in packet["findings"]:
        human_text.extend(
            finding[field]
            for field in (
                "title",
                "current_value",
                "proposed_value",
                "rationale",
            )
        )
    assert all(re.search(r"[\u4e00-\u9fff]", value) for value in human_text)
    assert packet["review_id"] == REVIEW_ID
    assert packet["review_type"] == "sdtm_spec"
    assert [finding["id"] for finding in packet["findings"]] == [
        f"F-{index:03d}" for index in range(1, 9)
    ]
