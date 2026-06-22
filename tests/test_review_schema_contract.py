import json
import re
from pathlib import Path

from src.runtime.review_protocol import (
    DECISION_RECEIPT_SCHEMA,
    FINDING_DECISION_SCHEMA,
    REVIEW_FINDING_SCHEMA,
    REVIEW_PACKET_SCHEMA,
    REVIEW_PROTOCOL_SCHEMA,
    Decision,
    FindingCategory,
    RejectionReason,
    ReviewType,
    Severity,
    Urgency,
)


ROOT = Path(__file__).resolve().parents[1]
REVIEW_SCHEMA_PATH = ROOT / "schemas" / "review" / "review-protocol.schema.json"
TS_SCHEMA_PATH = ROOT / "src" / "review_panel" / "src" / "schema.ts"


def load_schema() -> dict:
    return json.loads(REVIEW_SCHEMA_PATH.read_text(encoding="utf-8"))


def schema_def(name: str) -> dict:
    return load_schema()["$defs"][name]


def ts_union_values(type_name: str) -> list[str]:
    source = TS_SCHEMA_PATH.read_text(encoding="utf-8")
    match = re.search(
        rf"export type {type_name} =(?P<body>.*?);",
        source,
        flags=re.DOTALL,
    )
    assert match, f"Missing TypeScript union: {type_name}"
    return re.findall(r'"([^"]+)"', match.group("body"))


def test_review_schema_bundle_is_python_runtime_authority():
    schema = load_schema()

    assert REVIEW_PROTOCOL_SCHEMA == schema
    assert REVIEW_FINDING_SCHEMA["required"] == schema["$defs"]["review_finding"]["required"]
    assert REVIEW_PACKET_SCHEMA["required"] == schema["$defs"]["review_packet"]["required"]
    assert (
        FINDING_DECISION_SCHEMA["properties"]["decision"]["enum"]
        == schema["$defs"]["finding_decision"]["properties"]["decision"]["enum"]
    )
    assert (
        DECISION_RECEIPT_SCHEMA["required"]
        == schema["$defs"]["decision_receipt"]["required"]
    )


def test_python_enums_match_review_json_schema():
    review_finding = schema_def("review_finding")
    review_packet = schema_def("review_packet")
    finding_decision = schema_def("finding_decision")

    assert review_packet["properties"]["review_type"]["enum"] == [item.value for item in ReviewType]
    assert review_finding["properties"]["category"]["enum"] == [
        item.value for item in FindingCategory
    ]
    assert review_finding["properties"]["severity"]["enum"] == [item.value for item in Severity]
    assert review_packet["properties"]["urgency"]["enum"] == [item.value for item in Urgency]
    assert finding_decision["properties"]["decision"]["enum"] == [item.value for item in Decision]
    assert finding_decision["properties"]["rejection_reason"]["enum"] == [
        item.value for item in RejectionReason
    ]


def test_typescript_review_types_match_review_json_schema():
    review_finding = schema_def("review_finding")
    review_packet = schema_def("review_packet")
    finding_decision = schema_def("finding_decision")

    assert ts_union_values("ReviewType") == review_packet["properties"]["review_type"]["enum"]
    assert ts_union_values("FindingCategory") == review_finding["properties"]["category"]["enum"]
    assert ts_union_values("Severity") == review_finding["properties"]["severity"]["enum"]
    assert ts_union_values("Urgency") == review_packet["properties"]["urgency"]["enum"]
    assert ts_union_values("DecisionValue") == finding_decision["properties"]["decision"]["enum"]
    assert (
        ts_union_values("RejectionReason")
        == finding_decision["properties"]["rejection_reason"]["enum"]
    )


def test_required_fields_match_review_json_schema_contract():
    assert schema_def("review_finding")["required"] == [
        "id",
        "category",
        "severity",
        "location",
        "title",
        "current_value",
        "proposed_value",
        "rationale",
        "evidence_refs",
        "auto_approved",
    ]
    assert schema_def("review_packet")["required"] == [
        "review_id",
        "review_type",
        "source_documents",
        "agent_summary",
        "findings",
        "urgency",
        "created_at",
        "generated_by",
        "auto_approved_count",
    ]
    assert schema_def("decision_receipt")["required"] == [
        "review_id",
        "reviewer",
        "timestamp",
        "decisions",
    ]


def test_rejected_decision_condition_lives_in_review_json_schema():
    finding_decision = schema_def("finding_decision")
    condition_text = json.dumps(finding_decision["allOf"], sort_keys=True)

    assert "rejected" in condition_text
    assert "rejection_reason" in condition_text
    assert "insufficient_evidence" in condition_text
    assert "human_correction" in condition_text
