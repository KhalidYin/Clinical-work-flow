"""Build the P6-P5 SDTMIG 3.4 release gate artifacts.

P5 publishes a locked, approved-only snapshot and machine-readable query/citation
evidence for the SDTMIG 3.4 Core/Events/AE deep scope.  It does not widen the
knowledge scope, execute an AE workflow, or create new clinical facts.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from scripts.content.extraction_contract import (
    ExtractionContractError,
    validate_extraction_package,
)
from scripts.content.sdtmig34_core_proposals import canonical_json_bytes, sha256_payload
from scripts.content.sdtmig34_relation_graph import CARD_GROUPS, GRAPH_PATH, QUERY_INDEX_PATH
from scripts.content.sdtmig34_proposal_finalize import APPROVAL_RECEIPT_ID, DEFAULT_RELEASE
from service.contracts import SchemaBundle, canonical_json_sha256
from service.repository import VaultRepository
from service.snapshot import load_locked_snapshot


ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "sources" / "packages" / "src-cdisc-sdtmig-3-4"
SOURCE_MANIFEST = PACKAGE / "source-manifest.json"
SNAPSHOT_PATH = ROOT / "snapshots" / "snapshot-sdtmig34-core-events-ae-v1.json"
SNAPSHOT_MANIFEST_PATH = PACKAGE / "snapshot-manifest.json"
QUERY_BENCHMARK_PATH = PACKAGE / "query-benchmark.json"
CITATION_BUNDLE_PATH = PACKAGE / "ae-citation-bundle.json"
QUALITY_REPORT_PATH = PACKAGE / "p6-release-quality-report.json"
GENERATED_AT = "2026-07-15T18:20:00+08:00"
SNAPSHOT_ID = "snapshot-sdtmig34-core-events-ae-v1"
CARD_IDS = tuple(group["card_id"] for group in CARD_GROUPS)
FORBIDDEN_SOURCE_IDS = {"src-cdisc-sdtmig-3-3"}


class ReleaseGateError(ValueError):
    """Raised when P5 cannot prove the release gate."""


BENCHMARK_CASES = [
    {
        "case_id": "bench-ae-domain-definition",
        "question": "AE domain definition",
        "filters": {"domain": "AE", "knowledge_type": "definition"},
        "expected_statement_ids": [
            "proposal-sdtmig34-gold-ae-definition-v1",
            "proposal-sdtmig34-gold-ae-structure-v1",
        ],
        "expectation": "returns_expected",
    },
    {
        "case_id": "bench-aeterm-required",
        "question": "AE.AETERM required topic variable",
        "filters": {"domain": "AE", "variable": "AETERM"},
        "expected_statement_ids": ["proposal-sdtmig34-gold-aeterm-required-v1"],
        "expectation": "returns_expected",
    },
    {
        "case_id": "bench-aeenrf-timing-cross-reference",
        "question": "AE.AEENRF relative timing cross-reference",
        "filters": {"domain": "AE", "variable": "AEENRF"},
        "expected_statement_ids": ["proposal-sdtmig34-gold-aeenrf-crossref-v1"],
        "expectation": "returns_expected",
    },
    {
        "case_id": "bench-study-day-timing",
        "question": "--DY study day calculation support",
        "filters": {"variable": "--DY"},
        "expected_statement_ids": [
            "proposal-sdtmig34-core-study-day-calculation-method-v1",
            "proposal-sdtmig34-core-study-day-reference-and-limit-v1",
            "proposal-sdtmig34-core-study-day-variable-purpose-v1",
        ],
        "expectation": "returns_expected",
    },
    {
        "case_id": "bench-reltype-erratum-exception",
        "question": "RELTYPE=MANY erratum",
        "filters": {"variable": "RELTYPE", "knowledge_type": "exception"},
        "expected_statement_ids": ["proposal-sdtmig34-gold-erratum-lnkgrp-v1"],
        "expectation": "returns_expected",
    },
    {
        "case_id": "bench-example-is-not-requirement",
        "question": "AE example identity",
        "filters": {"domain": "AE", "knowledge_type": "example"},
        "expected_statement_ids": ["proposal-sdtmig34-gold-ae-example1-v1"],
        "expectation": "returns_expected",
    },
    {
        "case_id": "bench-requirement-partition",
        "question": "Requirement partition",
        "filters": {"knowledge_type": "requirement"},
        "expected_statement_ids": [
            "proposal-sdtmig34-core-conformance-required-expected-columns-v1",
            "proposal-sdtmig34-core-domain-code-consistency-v1",
            "proposal-sdtmig34-core-general-observation-classes-v1",
            "proposal-sdtmig34-core-missing-values-as-nulls-v1",
            "proposal-sdtmig34-gold-events-class-guidance-v1",
        ],
        "expectation": "returns_expected",
    },
    {
        "case_id": "bench-assumption-explicit-gap",
        "question": "Assumption statement partition",
        "filters": {"knowledge_type": "assumption"},
        "expected_statement_ids": [],
        "expectation": "explicit_gap",
        "gap_id": "gap-sdtmig34-assumption-statements-not-approved-in-p6",
    },
    {
        "case_id": "bench-aedecod-explicit-gap",
        "question": "AE.AEDECOD coding rule",
        "filters": {"domain": "AE", "variable": "AEDECOD"},
        "expected_statement_ids": [],
        "expectation": "explicit_gap",
        "gap_id": "gap-ae-aedecod-coding-not-approved-in-p6",
    },
    {
        "case_id": "bench-ct-explicit-gap",
        "question": "Controlled Terminology package for AE coding",
        "filters": {"variable": "AEDECOD", "knowledge_type": "controlled_terminology"},
        "expected_statement_ids": [],
        "expectation": "explicit_gap",
        "gap_id": "gap-controlled-terminology-not-deep-extracted-in-p6",
    },
    {
        "case_id": "bench-implementation-guidance-explicit-gap",
        "question": "Executable implementation guidance",
        "filters": {"knowledge_type": "implementation_guidance"},
        "expected_statement_ids": [],
        "expectation": "explicit_gap",
        "gap_id": "gap-executable-implementation-guidance-deferred-to-p7",
    },
]

COVERAGE_GAPS = [
    {
        "gap_id": "gap-sdtmig34-assumption-statements-not-approved-in-p6",
        "topic": "Assumption statements",
        "status": "not_in_approved_deep_scope",
        "handling": "Do not infer assumptions from examples or requirements; request an approved extraction or human review.",
    },
    {
        "gap_id": "gap-ae-aedecod-coding-not-approved-in-p6",
        "topic": "AEDECOD / MedDRA coding",
        "status": "not_in_approved_deep_scope",
        "handling": "P7 must request additional governed knowledge or human review; do not infer coding rules from AETERM.",
    },
    {
        "gap_id": "gap-controlled-terminology-not-deep-extracted-in-p6",
        "topic": "Controlled Terminology",
        "status": "external_dependency_registered_not_deep_extracted",
        "handling": "Use only explicit CT source integration in a later phase; current bundle returns a gap.",
    },
    {
        "gap_id": "gap-crf-edc-to-sdtm-programming-not-in-p6",
        "topic": "CRF/EDC to SDTM programming process",
        "status": "workflow_execution_deferred",
        "handling": "P6 provides citation evidence only; P7 owns MappingSpec/program candidate generation.",
    },
    {
        "gap_id": "gap-executable-implementation-guidance-deferred-to-p7",
        "topic": "Executable implementation guidance",
        "status": "workflow_execution_deferred",
        "handling": "P6 provides governed citation evidence only; P7 owns executable workflow guidance and program candidates.",
    },
    {
        "gap_id": "gap-study-specific-ae-rules-not-in-p6",
        "topic": "Current study AE rules",
        "status": "requires_study_context",
        "handling": "Study-specific decisions must come from the Study workspace and Review Protocol.",
    },
    {
        "gap_id": "gap-full-ae-variable-table-not-approved-in-p6",
        "topic": "Full AE variable table",
        "status": "partial_deep_scope",
        "handling": "Only AETERM and AEENRF are approved variable-level examples in P6.",
    },
]


def _read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReleaseGateError(f"JSON artifact must be an object: {path}")
    return payload


def _repository() -> VaultRepository:
    bundle = SchemaBundle.load(ROOT / "schemas" / "engine")
    repository = VaultRepository(ROOT, bundle)
    repository.refresh()
    return repository


def build_snapshot(repository: VaultRepository) -> dict[str, Any]:
    cards = []
    for card_id in CARD_IDS:
        card = repository.get(card_id)
        if card is None:
            raise ReleaseGateError(f"snapshot card is missing: {card_id}")
        if not card.production_eligible:
            raise ReleaseGateError(
                f"snapshot card is not production eligible: {card_id}: {card.eligibility_reasons}"
            )
        cards.append(card)
    content = {
        "schema_bundle": {
            "version": repository.bundle.version,
            "sha256": repository.bundle.sha256,
        },
        "items": [card.record for card in sorted(cards, key=lambda item: item.record["id"])],
    }
    return {
        "snapshot_id": SNAPSHOT_ID,
        "version": "1.0.0",
        "created_at": GENERATED_AT,
        "sha256": canonical_json_sha256(content),
        **content,
    }


def build_snapshot_manifest(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "manifest_id": "snapshot-manifest-sdtmig34-core-events-ae-v1",
        "generated_at": GENERATED_AT,
        "snapshot_id": snapshot["snapshot_id"],
        "snapshot_path": SNAPSHOT_PATH.relative_to(ROOT).as_posix(),
        "version": snapshot["version"],
        "sha256": snapshot["sha256"],
        "item_ids": [item["id"] for item in snapshot["items"]],
        "scope": {
            "source_id": "src-cdisc-sdtmig-3-4",
            "implementation_guide": "SDTMIG-3.4",
            "deep_scope": ["Core chapters 1-4", "Events 6.2", "AE 6.2.1"],
            "approval_receipt_id": APPROVAL_RECEIPT_ID,
        },
        "runtime_boundary": (
            "Approved-only domain knowledge snapshot for P7 citation/runtime-context "
            "experiments; it is not an executable AE mapping program."
        ),
    }


def _artifact_index(release: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["artifact_id"]: item
        for item in release["extraction_package"]["artifacts"]
    }


def _unit_locator_index(release: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        unit["locator"]["locator_id"]: unit["locator"]
        for unit in release["extraction_package"]["units"]
    }


def _statement_index(release: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["statement_id"]: item
        for item in release["extraction_package"]["statements"]
    }


def _graph_statement_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["node_id"]: item
        for item in graph["nodes"]
        if item.get("node_type") == "statement"
    }


def _match_query(index: dict[str, Any], filters: dict[str, str]) -> list[str]:
    pools: list[set[str]] = []
    if "domain" in filters:
        pools.append(set(index["domain_index"].get(filters["domain"], [])))
    if "variable" in filters:
        pools.append(set(index["variable_index"].get(filters["variable"], [])))
    if "knowledge_type" in filters:
        pools.append(set(index["knowledge_type_index"].get(filters["knowledge_type"], [])))
    if not pools:
        return sorted(
            statement_id
            for values in index["knowledge_type_index"].values()
            for statement_id in values
        )
    return sorted(set.intersection(*pools))


def build_query_benchmark(index: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    graph_statements = _graph_statement_index(graph)
    cases = []
    for case in BENCHMARK_CASES:
        actual = _match_query(index, case["filters"])
        expected = sorted(case["expected_statement_ids"])
        passed = actual == expected
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        cases.append(
            {
                **case,
                "actual_statement_ids": actual,
                "actual_locator_ids": sorted(
                    {
                        locator_id
                        for statement_id in actual
                        for locator_id in graph_statements.get(statement_id, {}).get("locator_ids", [])
                    }
                ),
                "passed": passed,
                "missing_statement_ids": missing,
                "unexpected_statement_ids": unexpected,
            }
        )
    return {
        "schema_version": "1.0.0",
        "benchmark_id": "query-benchmark-sdtmig34-core-events-ae-v1",
        "generated_at": GENERATED_AT,
        "graph_id": graph["graph_id"],
        "query_index_id": index["index_id"],
        "case_count": len(cases),
        "passed_count": sum(1 for case in cases if case["passed"]),
        "gap_case_count": sum(1 for case in cases if case["expectation"] == "explicit_gap"),
        "cases": cases,
    }


def _statement_card_id(statement_id: str, graph: dict[str, Any]) -> str:
    node = _graph_statement_index(graph).get(statement_id)
    if node is None:
        raise ReleaseGateError(f"statement missing from relation graph: {statement_id}")
    return str(node["card_id"])


def _evidence_details(statement: dict[str, Any], release: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = _artifact_index(release)
    locators = _unit_locator_index(release)
    details = []
    for evidence in statement["evidence"]:
        artifact = artifacts.get(evidence["artifact_id"])
        locator = locators.get(evidence["locator_id"])
        if artifact is None or locator is None:
            raise ReleaseGateError(f"evidence cannot be resolved for {statement['statement_id']}")
        details.append(
            {
                "source_id": evidence["source_id"],
                "artifact_id": evidence["artifact_id"],
                "artifact_sha256": evidence["artifact_sha256"],
                "artifact_role": artifact["role"],
                "locator_id": evidence["locator_id"],
                "locator_type": locator["locator_type"],
                "physical_page": locator.get("physical_page"),
                "printed_page": locator.get("printed_page"),
                "section_path": locator.get("section_path", []),
                "row_key": locator.get("row_key"),
                "row_number": locator.get("row_number"),
                "sheet_name": locator.get("sheet_name"),
            }
        )
    return details


def build_citation_bundle(
    *,
    release: dict[str, Any],
    graph: dict[str, Any],
    benchmark: dict[str, Any],
    snapshot_manifest: dict[str, Any],
    source_manifest: dict[str, Any],
) -> dict[str, Any]:
    statements = _statement_index(release)
    ae_statement_ids = sorted(
        {
            statement_id
            for case in benchmark["cases"]
            if case["case_id"]
            in {
                "bench-ae-domain-definition",
                "bench-aeterm-required",
                "bench-aeenrf-timing-cross-reference",
                "bench-study-day-timing",
                "bench-reltype-erratum-exception",
                "bench-example-is-not-requirement",
            }
            for statement_id in case["actual_statement_ids"]
        }
    )
    rules = []
    for statement_id in ae_statement_ids:
        statement = statements[statement_id]
        rules.append(
            {
                "statement_id": statement_id,
                "card_id": _statement_card_id(statement_id, graph),
                "subject": statement["subject"],
                "knowledge_type": statement["knowledge_type"],
                "modality": statement["modality"],
                "statement": statement["statement"],
                "scope": statement["scope"],
                "conditions": statement["conditions"],
                "exceptions": statement["exceptions"],
                "evidence": _evidence_details(statement, release),
            }
        )
    return {
        "schema_version": "1.0.0",
        "bundle_id": "ae-citation-bundle-sdtmig34-core-events-ae-v1",
        "generated_at": GENERATED_AT,
        "source": {
            "source_id": release["source_id"],
            "source_sha256": release["source_sha256"],
            "source_version": "SDTMIG 3.4 Final, PDF re-issued 2022-07-21",
            "primary_artifact_id": source_manifest["primary_artifact_id"],
            "rights_status": source_manifest["rights_status"],
            "storage_mode": source_manifest["storage_mode"],
        },
        "snapshot_lock": {
            "snapshot_id": snapshot_manifest["snapshot_id"],
            "version": snapshot_manifest["version"],
            "sha256": snapshot_manifest["sha256"],
        },
        "query_benchmark_id": benchmark["benchmark_id"],
        "rules": rules,
        "coverage_gaps": COVERAGE_GAPS,
        "usage_boundary": (
            "P7 may use this bundle for citation-backed rule retrieval and explicit "
            "gap reporting only. MappingSpec/program generation remains P7 work."
        ),
    }


def build_quality_report(
    *,
    release: dict[str, Any],
    graph: dict[str, Any],
    benchmark: dict[str, Any],
    snapshot: dict[str, Any],
    citation_bundle: dict[str, Any],
) -> dict[str, Any]:
    statements = release["extraction_package"]["statements"]
    complete_evidence = _statement_evidence_completeness(release)
    criteria = [
        {
            "criterion": "100% approved statement has source/version/locator/hash",
            "status": "passed" if complete_evidence["coverage"] == 1.0 else "failed",
            "evidence": complete_evidence,
        },
        {
            "criterion": "0 dangling relation",
            "status": "passed" if graph["quality"]["dangling_relation_count"] == 0 else "failed",
            "evidence": {"dangling_relation_count": graph["quality"]["dangling_relation_count"]},
        },
        {
            "criterion": "query benchmark distinguishes expected types and explicit gaps",
            "status": "passed" if benchmark["passed_count"] == benchmark["case_count"] else "failed",
            "evidence": {"passed": benchmark["passed_count"], "total": benchmark["case_count"]},
        },
        {
            "criterion": "snapshot is approved-only deep scope",
            "status": "passed"
            if [item["id"] for item in snapshot["items"]] == sorted(CARD_IDS)
            else "failed",
            "evidence": {"item_ids": [item["id"] for item in snapshot["items"]]},
        },
        {
            "criterion": "P7 citation bundle returns rules and explicit gaps",
            "status": "passed" if citation_bundle["rules"] and citation_bundle["coverage_gaps"] else "failed",
            "evidence": {
                "rule_count": len(citation_bundle["rules"]),
                "gap_count": len(citation_bundle["coverage_gaps"]),
            },
        },
    ]
    return {
        "schema_version": "1.0.0",
        "report_id": "p6-release-quality-report-sdtmig34-core-events-ae-v1",
        "generated_at": GENERATED_AT,
        "source_id": release["source_id"],
        "approval_receipt_id": APPROVAL_RECEIPT_ID,
        "approved_statement_count": len(statements),
        "snapshot_id": snapshot["snapshot_id"],
        "query_benchmark_id": benchmark["benchmark_id"],
        "citation_bundle_id": citation_bundle["bundle_id"],
        "relation_graph_quality": graph["quality"],
        "criteria": criteria,
        "passed": all(item["status"] == "passed" for item in criteria),
    }


def _statement_evidence_completeness(release: dict[str, Any]) -> dict[str, Any]:
    artifacts = _artifact_index(release)
    locators = _unit_locator_index(release)
    complete = []
    incomplete = []
    for statement in release["extraction_package"]["statements"]:
        ok = True
        for evidence in statement["evidence"]:
            artifact = artifacts.get(evidence.get("artifact_id"))
            locator = locators.get(evidence.get("locator_id"))
            ok = ok and evidence.get("source_id") == release["source_id"]
            ok = ok and artifact is not None
            ok = ok and locator is not None
            ok = ok and artifact is not None and evidence.get("artifact_sha256") == artifact["artifact_sha256"]
            ok = ok and bool(evidence.get("locator_id"))
        if ok:
            complete.append(statement["statement_id"])
        else:
            incomplete.append(statement["statement_id"])
    total = len(complete) + len(incomplete)
    return {
        "complete_count": len(complete),
        "incomplete_count": len(incomplete),
        "coverage": len(complete) / total if total else 0,
        "incomplete_statement_ids": incomplete,
    }


def build_outputs() -> dict[str, Any]:
    repository = _repository()
    release = _read_json(DEFAULT_RELEASE)
    graph = _read_json(GRAPH_PATH)
    query_index = _read_json(QUERY_INDEX_PATH)
    source_manifest = _read_json(SOURCE_MANIFEST)
    snapshot = build_snapshot(repository)
    snapshot_manifest = build_snapshot_manifest(snapshot)
    benchmark = build_query_benchmark(query_index, graph)
    citation_bundle = build_citation_bundle(
        release=release,
        graph=graph,
        benchmark=benchmark,
        snapshot_manifest=snapshot_manifest,
        source_manifest=source_manifest,
    )
    quality_report = build_quality_report(
        release=release,
        graph=graph,
        benchmark=benchmark,
        snapshot=snapshot,
        citation_bundle=citation_bundle,
    )
    outputs = {
        "release": release,
        "graph": graph,
        "query_index": query_index,
        "source_manifest": source_manifest,
        "snapshot": snapshot,
        "snapshot_manifest": snapshot_manifest,
        "query_benchmark": benchmark,
        "citation_bundle": citation_bundle,
        "quality_report": quality_report,
    }
    validate_release_gate(outputs)
    return outputs


def validate_release_gate(outputs: dict[str, Any]) -> None:
    release = outputs["release"]
    graph = outputs["graph"]
    query_index = outputs["query_index"]
    snapshot = outputs["snapshot"]
    benchmark = outputs["query_benchmark"]
    citation_bundle = outputs["citation_bundle"]
    quality_report = outputs["quality_report"]

    try:
        validate_extraction_package(release["extraction_package"])
    except ExtractionContractError as exc:
        raise ReleaseGateError(f"extraction package failed release gate: {exc}") from exc
    if release["source_id"] in FORBIDDEN_SOURCE_IDS:
        raise ReleaseGateError("release uses a forbidden source id")
    for artifact in release["extraction_package"]["artifacts"]:
        if artifact["artifact_id"].endswith("3-3") or artifact["artifact_sha256"] == "":
            raise ReleaseGateError("invalid or forbidden artifact in release")
    for statement in release["extraction_package"]["statements"]:
        if statement["review_status"] != "approved":
            raise ReleaseGateError(f"release contains non-approved statement: {statement['statement_id']}")
        if statement["review_receipt_id"] != APPROVAL_RECEIPT_ID:
            raise ReleaseGateError(f"statement is not bound to P3-E receipt: {statement['statement_id']}")
        for evidence in statement["evidence"]:
            if evidence["source_id"] in FORBIDDEN_SOURCE_IDS:
                raise ReleaseGateError(f"statement mixes forbidden source: {statement['statement_id']}")
            if "locator_id" not in evidence or not evidence["locator_id"]:
                raise ReleaseGateError(f"statement evidence lacks locator: {statement['statement_id']}")
    completeness = _statement_evidence_completeness(release)
    if completeness["coverage"] != 1.0:
        raise ReleaseGateError(f"statement evidence is incomplete: {completeness}")

    if graph["release_sha256"] != sha256_payload(release):
        raise ReleaseGateError("relation graph release hash drifted")
    if graph["quality"]["dangling_relation_count"] != 0:
        raise ReleaseGateError("relation graph contains dangling relations")
    if query_index["graph_sha256"] != sha256_payload(graph):
        raise ReleaseGateError("query index graph hash drifted")

    snapshot_ids = [item["id"] for item in snapshot["items"]]
    if snapshot_ids != sorted(CARD_IDS):
        raise ReleaseGateError(f"snapshot widened beyond P6 deep scope: {snapshot_ids}")
    if any(item["approval_status"] != "approved" for item in snapshot["items"]):
        raise ReleaseGateError("snapshot contains unapproved content")
    if snapshot["sha256"] != canonical_json_sha256(
        {"schema_bundle": snapshot["schema_bundle"], "items": snapshot["items"]}
    ):
        raise ReleaseGateError("snapshot canonical hash is invalid")

    if benchmark["passed_count"] != benchmark["case_count"]:
        raise ReleaseGateError("query benchmark has failing cases")
    gap_ids = {
        case.get("gap_id")
        for case in benchmark["cases"]
        if case.get("expectation") == "explicit_gap"
    }
    bundle_gap_ids = {item["gap_id"] for item in citation_bundle["coverage_gaps"]}
    if not gap_ids.issubset(bundle_gap_ids):
        raise ReleaseGateError("benchmark gaps are not present in the citation bundle")
    if not citation_bundle["rules"]:
        raise ReleaseGateError("citation bundle has no rules")
    if not quality_report["passed"]:
        raise ReleaseGateError("quality report did not pass")


def write_outputs(outputs: dict[str, Any]) -> None:
    _write_json(SNAPSHOT_PATH, outputs["snapshot"])
    _write_json(SNAPSHOT_MANIFEST_PATH, outputs["snapshot_manifest"])
    _write_json(QUERY_BENCHMARK_PATH, outputs["query_benchmark"])
    _write_json(CITATION_BUNDLE_PATH, outputs["citation_bundle"])
    _write_json(QUALITY_REPORT_PATH, outputs["quality_report"])
    # Prove the committed snapshot is loadable by the runtime snapshot reader.
    repository = _repository()
    load_locked_snapshot(repository, outputs["citation_bundle"]["snapshot_lock"])


def check_outputs(outputs: dict[str, Any]) -> None:
    for path, key in (
        (SNAPSHOT_PATH, "snapshot"),
        (SNAPSHOT_MANIFEST_PATH, "snapshot_manifest"),
        (QUERY_BENCHMARK_PATH, "query_benchmark"),
        (CITATION_BUNDLE_PATH, "citation_bundle"),
        (QUALITY_REPORT_PATH, "quality_report"),
    ):
        _assert_json_matches(path, outputs[key])
    repository = _repository()
    load_locked_snapshot(repository, outputs["citation_bundle"]["snapshot_lock"])


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(payload))


def _assert_json_matches(path: Path, expected: dict[str, Any]) -> None:
    if not path.is_file():
        raise ReleaseGateError(f"generated file is missing: {path}")
    if path.read_bytes() != canonical_json_bytes(expected):
        raise ReleaseGateError(f"generated file is stale: {path}")


def tamper_for_negative_gate(outputs: dict[str, Any], mutation: str) -> dict[str, Any]:
    """Return a deliberately invalid copy for regression tests."""

    bad = deepcopy(outputs)
    if mutation == "missing_locator":
        bad["release"]["extraction_package"]["statements"][0]["evidence"][0].pop("locator_id")
    elif mutation == "wrong_version_source":
        bad["release"]["extraction_package"]["statements"][0]["evidence"][0]["source_id"] = "src-cdisc-sdtmig-3-3"
    elif mutation == "snapshot_widened":
        bad["snapshot"]["items"].append(deepcopy(bad["snapshot"]["items"][0]))
        bad["snapshot"]["items"][-1]["id"] = "kr-out-of-scope-rule"
    elif mutation == "unapproved_snapshot_item":
        bad["snapshot"]["items"][0]["approval_status"] = "proposed"
    else:
        raise ValueError(f"unknown mutation: {mutation}")
    return bad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = build_outputs()
    if args.check:
        check_outputs(outputs)
        action = "verified"
    else:
        write_outputs(outputs)
        action = "generated"
    print(
        json.dumps(
            {
                "action": action,
                "snapshot_id": outputs["snapshot"]["snapshot_id"],
                "statements": outputs["quality_report"]["approved_statement_count"],
                "benchmark_cases": outputs["query_benchmark"]["case_count"],
                "citation_rules": len(outputs["citation_bundle"]["rules"]),
                "coverage_gaps": len(outputs["citation_bundle"]["coverage_gaps"]),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseGateError as error:
        raise SystemExit(f"SDTMIG 3.4 release gate failed: {error}") from error
