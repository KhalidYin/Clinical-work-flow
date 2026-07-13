import json
from pathlib import Path

import yaml

from src.runtime.agent_loop import AgentRuntime
from src.runtime.decision_application import (
    ApplicationStatus,
    DecisionApplicationError,
    apply_decision_receipt,
)
from src.runtime.review_protocol import (
    Decision,
    DecisionReceipt,
    FindingCategory,
    FindingDecision,
    RejectionReason,
    ReviewFinding,
    ReviewPacket,
    ReviewQueue,
    ReviewType,
    Severity,
    Urgency,
)


def finding(
    finding_id: str,
    location: str,
    current_value: str,
    proposed_value: str,
    *,
    auto_approved: bool = False,
) -> ReviewFinding:
    return ReviewFinding(
        id=finding_id,
        category=FindingCategory.FORMATTING,
        severity=Severity.WARNING,
        location=location,
        title=f"Review {finding_id}",
        current_value=current_value,
        proposed_value=proposed_value,
        rationale="Structured fixture finding with enough detail for validation.",
        evidence_refs=["SPEC-15"],
        auto_approved=auto_approved,
    )


def packet_with_findings(*findings: ReviewFinding) -> ReviewPacket:
    return ReviewPacket(
        review_id="tfl_shell_t14_1_1_v1_001",
        review_type=ReviewType.TFL_SHELL,
        source_documents=["output/tfl/shells/t14_1_1.yaml"],
        agent_summary="Review generated TFL shell fields before programming.",
        findings=list(findings),
        urgency=Urgency.BLOCKING,
        generated_by="TFLQCSubmissionAgent",
    )


def write_shell(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
title: Old Subject Disposition
population: Safety
analysis_method: Old method
footnotes:
  - Needs source confirmation
""".lstrip(),
        encoding="utf-8",
    )


def test_apply_decision_receipt_updates_yaml_and_writes_confirmation_and_rework(tmp_path):
    shell_path = tmp_path / "output" / "tfl" / "shells" / "t14_1_1.yaml"
    write_shell(shell_path)

    packet = packet_with_findings(
        finding(
            "F-001",
            "output/tfl/shells/t14_1_1.yaml#title",
            "Old Subject Disposition",
            "Subject Disposition",
        ),
        finding(
            "F-002",
            "output/tfl/shells/t14_1_1.yaml#population",
            "Safety",
            "All Randomized",
        ),
        finding(
            "F-003",
            "output/tfl/shells/t14_1_1.yaml#analysis_method",
            "Old method",
            "Use incorrect proposed method",
        ),
        finding(
            "F-004",
            "output/tfl/shells/t14_1_1.yaml#footnotes[0]",
            "Needs source confirmation",
            "Protocol section not provided",
        ),
    )
    receipt = DecisionReceipt(
        review_id=packet.review_id,
        reviewer="Lead Programmer",
        decisions=[
            FindingDecision("F-001", Decision.APPROVED),
            FindingDecision("F-002", Decision.MODIFIED, modified_value="FAS"),
            FindingDecision(
                "F-003",
                Decision.REJECTED,
                rejection_reason=RejectionReason.INCORRECT_METHOD,
                human_correction="Use the SAP-defined method instead of the proposed method.",
                reference="SAP Section 9.1",
            ),
            FindingDecision(
                "F-004",
                Decision.REJECTED,
                rejection_reason=RejectionReason.INSUFFICIENT_EVIDENCE,
            ),
        ],
    )

    confirmation = apply_decision_receipt(
        project_dir=tmp_path,
        review_queue_dir=".review_queue",
        packet=packet,
        receipt=receipt,
    )

    updated = yaml.safe_load(shell_path.read_text(encoding="utf-8"))
    assert updated["title"] == "Subject Disposition"
    assert updated["population"] == "FAS"
    assert updated["analysis_method"] == "Old method"
    assert updated["footnotes"][0] == "Needs source confirmation"
    assert confirmation.summary() == {
        "total": 4,
        "applied": 2,
        "adjusted": 2,
        "failed": 0,
    }

    confirmation_data = json.loads(
        (tmp_path / ".review_queue" / f"{packet.review_id}_confirmation.json").read_text(
            encoding="utf-8"
        )
    )
    assert confirmation_data["summary"]["adjusted"] == 2
    assert {
        result["finding_id"]: result["application_status"]
        for result in confirmation_data["results"]
    } == {
        "F-001": "applied",
        "F-002": "applied",
        "F-003": "applied_with_adjustment",
        "F-004": "applied_with_adjustment",
    }

    rework_data = json.loads(
        (tmp_path / ".review_queue" / f"{packet.review_id}_rework.json").read_text(
            encoding="utf-8"
        )
    )
    assert [directive["finding_id"] for directive in rework_data["directives"]] == [
        "F-003",
        "F-004",
    ]
    assert rework_data["directives"][0]["human_correction"].startswith("Use the SAP-defined")
    assert "human_correction" not in rework_data["directives"][1]


def test_decision_application_requires_all_non_auto_approved_findings(tmp_path):
    packet = packet_with_findings(
        finding("F-001", "output/tfl/shells/t14_1_1.yaml#title", "Old", "New"),
        finding(
            "F-002",
            "output/tfl/shells/t14_1_1.yaml#population",
            "Safety",
            "FAS",
            auto_approved=True,
        ),
    )
    receipt = DecisionReceipt(
        review_id=packet.review_id,
        reviewer="Lead Programmer",
        decisions=[],
    )

    try:
        apply_decision_receipt(
            project_dir=tmp_path,
            review_queue_dir=".review_queue",
            packet=packet,
            receipt=receipt,
        )
    except DecisionApplicationError as exc:
        assert "missing decisions" in str(exc)
        assert "F-001" in str(exc)
        assert "F-002" not in str(exc)
    else:
        raise AssertionError("Expected DecisionApplicationError")


def test_decision_application_records_failed_result_for_missing_artifact(tmp_path):
    packet = packet_with_findings(
        finding(
            "F-001",
            "output/tfl/shells/missing.yaml#title",
            "Old Subject Disposition",
            "Subject Disposition",
        )
    )
    receipt = DecisionReceipt(
        review_id=packet.review_id,
        reviewer="Lead Programmer",
        decisions=[FindingDecision("F-001", Decision.APPROVED)],
    )

    confirmation = apply_decision_receipt(
        project_dir=tmp_path,
        review_queue_dir=".review_queue",
        packet=packet,
        receipt=receipt,
    )

    result = confirmation.results[0]
    assert result.application_status == ApplicationStatus.FAILED
    assert "does not exist" in (result.error_message or "")


def test_review_queue_archives_confirmation_and_rework_files(tmp_path):
    shell_path = tmp_path / "output" / "tfl" / "shells" / "t14_1_1.yaml"
    write_shell(shell_path)
    queue = ReviewQueue(tmp_path)
    packet = packet_with_findings(
        finding(
            "F-001",
            "output/tfl/shells/t14_1_1.yaml#analysis_method",
            "Old method",
            "Use incorrect proposed method",
        )
    )
    receipt = DecisionReceipt(
        review_id=packet.review_id,
        reviewer="Lead Programmer",
        decisions=[
            FindingDecision(
                "F-001",
                Decision.REJECTED,
                rejection_reason=RejectionReason.INCORRECT_METHOD,
                human_correction="Use the SAP-defined method instead of the proposed method.",
            )
        ],
    )

    queue.submit_packet(packet)
    queue.submit_decision(receipt)
    apply_decision_receipt(
        project_dir=tmp_path,
        review_queue_dir=queue.queue_dir,
        packet=packet,
        receipt=receipt,
    )

    assert queue.pending_packets() == []
    queue.archive_completed(packet.review_id)

    archived_names = {path.name for path in queue.archive_dir.glob("*.json")}
    assert archived_names == {
        f"{packet.review_id}.json",
        f"{packet.review_id}_decision.json",
        f"{packet.review_id}_confirmation.json",
        f"{packet.review_id}_rework.json",
    }
    assert queue.list_archived() == [packet.review_id]


def test_runtime_applies_decisions_before_archiving_review_files(tmp_path):
    shell_path = tmp_path / "output" / "tfl" / "shells" / "t14_1_1.yaml"
    write_shell(shell_path)
    runtime = AgentRuntime(project_dir=tmp_path, git_auto_commit=False)
    packet = packet_with_findings(
        finding(
            "F-001",
            "output/tfl/shells/t14_1_1.yaml#title",
            "Old Subject Disposition",
            "Subject Disposition",
        )
    )
    receipt = DecisionReceipt(
        review_id=packet.review_id,
        reviewer="Lead Programmer",
        decisions=[FindingDecision("F-001", Decision.APPROVED)],
    )

    runtime.review_queue.submit_packet(packet)
    runtime.review_queue.submit_decision(receipt)
    runtime._apply_decisions(receipt)

    updated = yaml.safe_load(shell_path.read_text(encoding="utf-8"))
    assert updated["title"] == "Subject Disposition"
    assert (runtime.review_queue.archive_dir / f"{packet.review_id}.json").exists()
    assert (runtime.review_queue.archive_dir / f"{packet.review_id}_decision.json").exists()
    assert (runtime.review_queue.archive_dir / f"{packet.review_id}_confirmation.json").exists()
    assert runtime.state.change_log[-1]["application_summary"]["applied"] == 1
