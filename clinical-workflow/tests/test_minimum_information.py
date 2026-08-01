import copy
import json
from pathlib import Path

import yaml

from src.runtime.minimum_information import (
    ExecutionEligibility,
    KnowledgeAvailability,
    TargetStandardLock,
    plan_minimum_information,
    validate_minimum_information_plan,
    verify_knowledge_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
PLATFORM_ROOT = ROOT.parent
SAMPLE_STUDY = PLATFORM_ROOT / "clinical-studies" / "SAMPLE-AE-001"
KNOWLEDGE_SNAPSHOT = (
    ROOT
    / "tests"
    / "fixtures"
    / "knowledge"
    / "sdtmig34-poc"
    / "snapshots"
    / "snapshot-sdtmig34-core-events-ae-v1.json"
)
SNAPSHOT_ID = "snapshot-sdtmig34-core-events-ae-v1"
SNAPSHOT_VERSION = "1.0.0"
SNAPSHOT_SHA = "d8aafb73ccca987d597e372435b664ba074c1a45688d5e2eef809c72f475a9ec"


def _inventory() -> dict:
    return yaml.safe_load((SAMPLE_STUDY / "source-inventory.yaml").read_text(encoding="utf-8"))


def _metadata() -> dict:
    return json.loads(
        (SAMPLE_STUDY / "work/derived/edc/source-metadata.json").read_text(encoding="utf-8")
    )


def _available_paths(inventory: dict) -> set[str]:
    return {source["path"] for source in inventory["sources"]}


def _knowledge(available: bool = True) -> KnowledgeAvailability:
    return KnowledgeAvailability(
        available=available,
        snapshot_id=SNAPSHOT_ID if available else None,
        version=SNAPSHOT_VERSION if available else None,
        sha256=SNAPSHOT_SHA if available else None,
        reference="locked-knowledge/snapshots/snapshot-sdtmig34-core-events-ae-v1.json",
        reason=None if available else "Locked snapshot is unavailable",
    )


def _standard(locked: bool = True) -> TargetStandardLock:
    return TargetStandardLock(
        standard="SDTMIG",
        version="3.4",
        locked=locked,
        reference="runtime-manifest.draft.yaml#domain_knowledge",
    )


def _plan(
    inventory: dict | None = None,
    metadata: dict | None = None,
    *,
    available_paths: set[str] | None = None,
    knowledge: KnowledgeAvailability | None = None,
    standard: TargetStandardLock | None = None,
):
    inventory = inventory or _inventory()
    return plan_minimum_information(
        study_id="SAMPLE-AE-001",
        source_inventory=inventory,
        source_metadata=_metadata() if metadata is None else metadata,
        target_standard=standard or _standard(),
        knowledge=knowledge or _knowledge(),
        available_source_paths=(
            _available_paths(inventory) if available_paths is None else available_paths
        ),
        generated_at="2026-07-16T09:30:00+00:00",
    )


def _requirement(plan, group: str, requirement_id: str):
    return next(item for item in getattr(plan, group) if item.requirement_id == requirement_id)


def test_full_input_plan_is_schema_valid_and_does_not_advance_pipeline() -> None:
    plan = _plan()

    assert plan.execution_eligibility is ExecutionEligibility.DRAFT_ALLOWED
    assert set(("STUDYID", "DOMAIN", "USUBJID", "AESEQ", "AETERM")) <= set(
        plan.producible_variables
    )
    assert plan.target_standard == "SDTMIG"
    assert plan.target_standard_version == "3.4"
    assert plan.creates_stage_completion_evidence is False
    assert len(plan.required_wiki_queries) == 3
    assert {review.blocking_before for review in plan.required_reviews} == {
        "mapping_context",
        "program_generation",
    }
    assert validate_minimum_information_plan(plan.model_dump(mode="json")) == []


def test_raw_only_without_crf_protocol_or_sap_still_allows_draft() -> None:
    inventory = _inventory()
    inventory["sources"] = [
        source for source in inventory["sources"] if source["role"] == "ae_source_data"
    ]

    plan = _plan(inventory, available_paths=_available_paths(inventory))

    assert plan.execution_eligibility is ExecutionEligibility.DRAFT_ALLOWED
    assert _requirement(plan, "conditional", "crf_metadata").status == "not_required"
    assert _requirement(plan, "optional", "protocol_context").blocking is False
    assert _requirement(plan, "optional", "sap_context").blocking is False
    assert {"AESTDY", "AEENDY"} <= set(plan.blocked_variables)
    assert "gap-reference-date" in {gap.gap_id for gap in plan.explicit_gaps}


def test_missing_conditional_inputs_block_only_affected_variables() -> None:
    inventory = _inventory()
    inventory["sources"] = [
        source for source in inventory["sources"]
        if source["role"] not in {"reference_date_source", "crf_metadata"}
    ]
    metadata = _metadata()
    coding_names = {
        "AEDECOD",
        "AEBODSYS",
        "AESOC",
        "AETERM_PT",
        "AETERM_SOC",
    }
    metadata["variables"] = [
        variable for variable in metadata["variables"] if variable["name"].upper() not in coding_names
    ]

    plan = _plan(inventory, metadata, available_paths=_available_paths(inventory))

    assert plan.execution_eligibility is ExecutionEligibility.DRAFT_ALLOWED
    assert set(("AEDECOD", "AEBODSYS", "AESOC", "AESTDY", "AEENDY")) <= set(
        plan.blocked_variables
    )
    assert {gap.gap_id for gap in plan.explicit_gaps} >= {
        "gap-reference-date",
        "gap-meddra-coding",
    }
    assert not any(
        gap.blocking for gap in plan.explicit_gaps if gap.gap_id in {
            "gap-reference-date",
            "gap-meddra-coding",
        }
    )


def test_missing_raw_source_fails_closed() -> None:
    inventory = _inventory()
    paths = _available_paths(inventory)
    raw_path = next(
        source["path"] for source in inventory["sources"] if source["role"] == "ae_source_data"
    )
    paths.remove(raw_path)

    plan = _plan(inventory, available_paths=paths)

    assert plan.execution_eligibility is ExecutionEligibility.BLOCKED
    assert _requirement(plan, "required", "ae_raw_dataset").status == "missing"
    assert plan.producible_variables == ()


def test_missing_subject_identity_fails_closed() -> None:
    metadata = _metadata()
    subject_names = {"USUBJID", "SUBJID", "SUBJECT", "SUBJECTID"}
    metadata["variables"] = [
        variable for variable in metadata["variables"]
        if variable["name"].upper() not in subject_names
    ]

    plan = _plan(metadata=metadata)

    assert plan.execution_eligibility is ExecutionEligibility.BLOCKED
    assert _requirement(plan, "required", "subject_identity").status == "missing"
    assert {"USUBJID", "AESEQ"} <= set(plan.blocked_variables)


def test_damaged_source_metadata_fails_closed_without_guessing() -> None:
    metadata = copy.deepcopy(_metadata())
    metadata.pop("variables")

    plan = _plan(metadata=metadata)

    assert plan.execution_eligibility is ExecutionEligibility.BLOCKED
    assert _requirement(plan, "required", "source_metadata").status == "invalid"
    assert plan.producible_variables == ()
    assert "gap-source-metadata" in {gap.gap_id for gap in plan.explicit_gaps}


def test_unavailable_snapshot_or_unlocked_standard_fails_closed() -> None:
    snapshot_blocked = _plan(knowledge=_knowledge(False))
    standard_blocked = _plan(standard=_standard(False))

    assert snapshot_blocked.execution_eligibility is ExecutionEligibility.BLOCKED
    assert "gap-governed-knowledge" in {gap.gap_id for gap in snapshot_blocked.explicit_gaps}
    assert standard_blocked.execution_eligibility is ExecutionEligibility.BLOCKED
    assert _requirement(standard_blocked, "required", "target_standard").status == "missing"


def test_snapshot_verification_detects_tampering(tmp_path: Path) -> None:
    verified = verify_knowledge_snapshot(
        KNOWLEDGE_SNAPSHOT,
        expected_snapshot_id=SNAPSHOT_ID,
        expected_version=SNAPSHOT_VERSION,
        expected_sha256=SNAPSHOT_SHA,
    )
    tampered_path = tmp_path / "snapshot.json"
    tampered = json.loads(KNOWLEDGE_SNAPSHOT.read_text(encoding="utf-8"))
    tampered["items"][0]["title"] = "tampered"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    rejected = verify_knowledge_snapshot(
        tampered_path,
        expected_snapshot_id=SNAPSHOT_ID,
        expected_version=SNAPSHOT_VERSION,
        expected_sha256=SNAPSHOT_SHA,
    )

    assert verified.available is True
    assert rejected.available is False
    assert rejected.reason == "Knowledge snapshot identity/content hash cannot be verified"


def test_plan_hash_is_deterministic_for_same_evidence_and_time() -> None:
    first = _plan()
    second = _plan()

    assert first.plan_sha256 == second.plan_sha256
    assert first.model_dump(mode="json") == second.model_dump(mode="json")

    tampered = first.model_dump(mode="json")
    tampered["execution_eligibility"] = "blocked"
    assert validate_minimum_information_plan(tampered) == [
        "plan_sha256: content hash mismatch"
    ]
