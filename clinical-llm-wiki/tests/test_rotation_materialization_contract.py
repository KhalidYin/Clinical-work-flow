from __future__ import annotations

from hashlib import sha256
from importlib import import_module

import pytest


def _hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _evidence(
    evidence_type,
    evidence_id: str,
    *,
    content: str,
    locator: str,
    rights: str = "internal",
):
    return evidence_type(
        evidence_id=evidence_id,
        content_sha256=_hash(content),
        locator_sha256=_hash(locator),
        rights={"classification": rights, "storage_allowed": True},
    )


class FakeRotationRepository:
    def __init__(self, *, evidence_type, released_revision_type) -> None:
        self.source_ids = {"srcv-old": "src-synthetic", "srcv-new": "src-synthetic"}
        self.evidence = {
            "srcv-old": (
                _evidence(evidence_type, "old-safe-unchanged", content="same", locator="1"),
                _evidence(evidence_type, "old-safe-moved", content="moved", locator="2"),
                _evidence(evidence_type, "old-modified", content="before", locator="3"),
                _evidence(evidence_type, "old-removed", content="removed", locator="4"),
                _evidence(evidence_type, "old-rights", content="rights", locator="5"),
                _evidence(evidence_type, "old-ambiguous", content="split", locator="6"),
            ),
            "srcv-new": (
                _evidence(evidence_type, "new-safe-unchanged", content="same", locator="1"),
                _evidence(evidence_type, "new-safe-moved", content="moved", locator="22"),
                _evidence(evidence_type, "new-modified", content="after", locator="3"),
                _evidence(evidence_type, "new-rights", content="rights", locator="5", rights="restricted"),
                _evidence(evidence_type, "new-ambiguous-a", content="split", locator="61"),
                _evidence(evidence_type, "new-ambiguous-b", content="split", locator="62"),
                _evidence(evidence_type, "new-added", content="added", locator="7"),
            ),
        }
        self.revisions = (
            released_revision_type(
                knowledge_revision_id="revision-safe",
                evidence_ids=("old-safe-unchanged", "old-safe-moved"),
            ),
            released_revision_type(
                knowledge_revision_id="revision-risk",
                evidence_ids=(
                    "old-modified",
                    "old-removed",
                    "old-rights",
                    "old-ambiguous",
                ),
            ),
        )
        self.persisted = None
        self.persist_calls = 0

    def source_id_for_version(self, source_version_id: str) -> str | None:
        return self.source_ids.get(source_version_id)

    def comparable_evidence(self, source_version_id: str):
        return self.evidence.get(source_version_id, ())

    def released_revision_evidence(self, evidence_ids: frozenset[str]):
        return tuple(
            revision
            for revision in self.revisions
            if evidence_ids.intersection(revision.evidence_ids)
        )

    def persist_materialization(self, *, result, actor_id: str):
        assert actor_id == "usr-curator"
        if self.persisted is None:
            self.persisted = result
            self.persist_calls += 1
        elif self.persisted != result:
            raise AssertionError("materialization drift")
        return self.persisted


def _materializer():
    module = import_module("service.governance.rotation")
    repository = FakeRotationRepository(
        evidence_type=module.ComparableEvidence,
        released_revision_type=module.ReleasedRevisionEvidence,
    )
    return module, repository, module.RotationImpactMaterializer(repository=repository)


def test_materialization_is_case_specific_and_never_decides_or_publishes() -> None:
    module, repository, materializer = _materializer()

    result = materializer.materialize(
        actor_id="usr-curator",
        command=module.ImpactMaterializationCommand(
            from_source_version_id="srcv-old",
            to_source_version_id="srcv-new",
            comparison_profile_version="comparison-synthetic-v1",
        ),
    )

    assert {impact.change_type.value for impact in result.assessment.impacts} == {
        "unchanged",
        "moved",
        "modified",
        "added",
        "removed",
        "rights_changed",
        "ambiguous",
    }
    assert {case.knowledge_revision_id for case in result.cases} == {
        "revision-safe",
        "revision-risk",
    }
    safe = next(case for case in result.cases if case.knowledge_revision_id == "revision-safe")
    assert {change.value for change in safe.change_types} == {"unchanged", "moved"}
    assert tuple(outcome.value for outcome in safe.eligible_outcomes) == ("carry_forward",)
    risk = next(case for case in result.cases if case.knowledge_revision_id == "revision-risk")
    assert {change.value for change in risk.change_types} == {
        "modified",
        "removed",
        "rights_changed",
        "ambiguous",
    }
    assert tuple(outcome.value for outcome in risk.eligible_outcomes) == (
        "replace",
        "retire",
        "no_action",
    )
    assert all(case.status.value == "open" for case in result.cases)
    assert all(case.proposed_outcome is None for case in result.cases)
    assert all(case.included_release_id is None for case in result.cases)
    assert repository.persist_calls == 1


def test_materialization_replay_has_stable_ids_and_one_persisted_fact_set() -> None:
    module, repository, materializer = _materializer()
    command = module.ImpactMaterializationCommand(
        from_source_version_id="srcv-old",
        to_source_version_id="srcv-new",
        comparison_profile_version="comparison-synthetic-v1",
    )

    first = materializer.materialize(actor_id="usr-curator", command=command)
    second = materializer.materialize(actor_id="usr-curator", command=command)

    assert first == second
    assert first.assessment.assessment_id.startswith("impact-")
    assert [case.rotation_case_id for case in first.cases] == [
        case.rotation_case_id for case in second.cases
    ]
    assert repository.persist_calls == 1


def test_materialization_rejects_cross_source_or_missing_evidence() -> None:
    module, repository, materializer = _materializer()
    repository.source_ids["srcv-new"] = "src-other"
    command = module.ImpactMaterializationCommand(
        from_source_version_id="srcv-old",
        to_source_version_id="srcv-new",
        comparison_profile_version="comparison-synthetic-v1",
    )

    with pytest.raises(module.ImpactMaterializationError, match="same source"):
        materializer.materialize(actor_id="usr-curator", command=command)

    repository.source_ids["srcv-new"] = "src-synthetic"
    repository.evidence["srcv-new"] = ()
    with pytest.raises(module.ImpactMaterializationError, match="canonical Evidence"):
        materializer.materialize(actor_id="usr-curator", command=command)
