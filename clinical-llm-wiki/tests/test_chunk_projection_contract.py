from __future__ import annotations

import pytest

from service import knowledge


def _contract(name: str):
    assert hasattr(knowledge, name), f"P17 projection contract is missing: {name}"
    return getattr(knowledge, name)


def _profile():
    return _contract("ChunkProfileContract")(
        chunk_profile_id="chunk-profile-test",
        version="v1-test",
        tokenizer_id="whitespace-v1",
        target_min_tokens=4,
        target_max_tokens=6,
        hard_max_tokens=8,
        overlap_tokens=2,
        table_hard_max_tokens=10,
        format_rules={
            "major_section_boundary": True,
            "table_row_atomic": True,
        },
    )


def _evidence(
    evidence_id: str,
    content: str,
    *,
    order: int,
    section: str = "1",
    evidence_type: str = "prose",
    table_id: str | None = None,
    locator_extra: dict[str, object] | None = None,
    source_version_id: str = "source-version-1",
    source_artifact_id: str = "artifact-1",
    data_boundary: str = "enterprise_provider_only",
    rights: dict[str, object] | None = None,
):
    return _contract("ProjectionEvidence")(
        evidence_id=evidence_id,
        source_version_id=source_version_id,
        source_artifact_id=source_artifact_id,
        evidence_type=evidence_type,
        document_order=order,
        major_section=section,
        table_id=table_id,
        locator={"section": section, **(locator_extra or {})},
        content=content,
        data_boundary=data_boundary,
        rights=rights or {"classification": "licensed", "storage_allowed": True},
    )


def test_projection_is_deterministic_and_never_overlaps_across_boundaries() -> None:
    project_retrieval_chunks = _contract("project_retrieval_chunks")
    evidence = (
        _evidence("ev-1", "one two three four", order=1),
        _evidence("ev-2", "five six seven", order=2),
        _evidence("ev-3", "eight nine ten", order=3, section="2"),
    )

    first = project_retrieval_chunks(profile=_profile(), evidence=evidence)
    repeated = project_retrieval_chunks(profile=_profile(), evidence=evidence)

    assert first == repeated
    assert [chunk.ordinal for chunk in first.chunks] == [0, 1, 2]
    assert [chunk.chunk_id for chunk in first.chunks] == [
        chunk.chunk_id for chunk in repeated.chunks
    ]
    assert all(chunk.content_sha256 for chunk in first.chunks)
    assert first.chunks[1].spans[0].span_role == "overlap"
    assert first.chunks[1].spans[0].evidence_id == "ev-1"
    assert {span.evidence_id for span in first.chunks[2].spans} == {"ev-3"}
    assert all(
        chunk.data_boundary == "enterprise_provider_only"
        and chunk.rights == {"classification": "licensed", "storage_allowed": True}
        for chunk in first.chunks
    )


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ({"source_artifact_id": "artifact-1"}, {"source_artifact_id": "artifact-2"}),
        ({"evidence_type": "prose"}, {"evidence_type": "figure"}),
        (
            {"data_boundary": "enterprise_provider_only"},
            {"data_boundary": "local_processing_only"},
        ),
        (
            {"rights": {"classification": "licensed", "storage_allowed": True}},
            {"rights": {"classification": "restricted", "storage_allowed": True}},
        ),
        (
            {"evidence_type": "table", "table_id": "table-1"},
            {"evidence_type": "table", "table_id": "table-2"},
        ),
    ],
)
def test_projection_never_crosses_artifact_format_table_data_or_rights_boundary(
    left: dict[str, object],
    right: dict[str, object],
) -> None:
    project_retrieval_chunks = _contract("project_retrieval_chunks")
    result = project_retrieval_chunks(
        profile=_profile(),
        evidence=(
            _evidence("ev-left", "one two", order=1, **left),
            _evidence("ev-right", "three four", order=2, **right),
        ),
    )

    assert len(result.chunks) == 2
    assert [
        {span.evidence_id for span in chunk.spans} for chunk in result.chunks
    ] == [{"ev-left"}, {"ev-right"}]


def test_projection_preserves_oversize_spans_and_audits_every_exclusion() -> None:
    project_retrieval_chunks = _contract("project_retrieval_chunks")
    result = project_retrieval_chunks(
        profile=_profile(),
        evidence=(
            _evidence(
                "ev-oversize",
                "one two three four five six seven eight nine ten",
                order=1,
            ),
            _evidence("ev-empty", "   ", order=2),
            _evidence("ev-duplicate", "one two three four", order=3),
            _evidence("ev-duplicate-2", "one two three four", order=4),
            _evidence(
                "ev-boilerplate",
                "copyright footer",
                order=5,
                locator_extra={"is_boilerplate": True},
            ),
        ),
    )

    oversize_chunks = [
        chunk
        for chunk in result.chunks
        if any(span.evidence_id == "ev-oversize" for span in chunk.spans)
    ]
    assert len(oversize_chunks) == 2
    assert oversize_chunks[0].spans[0].start_offset == 0
    assert oversize_chunks[0].spans[0].end_offset < len(
        "one two three four five six seven eight nine ten"
    )
    assert oversize_chunks[1].spans[-1].end_offset == len(
        "one two three four five six seven eight nine ten"
    )
    assert {finding.finding_type for finding in result.findings} == {
        "oversize",
        "empty",
        "duplicate",
        "boilerplate",
    }
    assert all(finding.finding_id for finding in result.findings)


def test_comparison_emits_only_seven_change_types_and_supports_many_to_many() -> None:
    comparable_evidence = _contract("ComparableEvidence")
    compare_evidence_versions = _contract("compare_evidence_versions")
    evidence_change_type = _contract("EvidenceChangeType")
    old = (
        comparable_evidence("old-unchanged", "a" * 64, "1" * 64, {"r": 1}),
        comparable_evidence("old-moved", "b" * 64, "2" * 64, {"r": 1}),
        comparable_evidence("old-modified", "c" * 64, "3" * 64, {"r": 1}),
        comparable_evidence("old-rights", "d" * 64, "4" * 64, {"r": 1}),
        comparable_evidence("old-removed", "e" * 64, "5" * 64, {"r": 1}),
        comparable_evidence("old-split", "f" * 64, "6" * 64, {"r": 1}),
    )
    new = (
        comparable_evidence("new-unchanged", "a" * 64, "1" * 64, {"r": 1}),
        comparable_evidence("new-moved", "b" * 64, "7" * 64, {"r": 1}),
        comparable_evidence("new-modified", "0" * 64, "3" * 64, {"r": 1}),
        comparable_evidence("new-rights", "d" * 64, "4" * 64, {"r": 2}),
        comparable_evidence("new-added", "9" * 64, "9" * 64, {"r": 1}),
        comparable_evidence("new-split-a", "f" * 64, "a" * 64, {"r": 1}),
        comparable_evidence("new-split-b", "f" * 64, "b" * 64, {"r": 1}),
    )

    assessment = compare_evidence_versions(
        assessment_id="assessment-1",
        from_source_version_id="source-version-1",
        to_source_version_id="source-version-2",
        comparison_profile_version="comparison-v1",
        from_evidence=old,
        to_evidence=new,
    )

    assert {impact.change_type for impact in assessment.impacts} == set(evidence_change_type)
    split = [
        impact
        for impact in assessment.impacts
        if impact.from_evidence_id == "old-split"
    ]
    assert {impact.to_evidence_id for impact in split} == {
        "new-split-a",
        "new-split-b",
    }
    assert all(impact.change_type is evidence_change_type.AMBIGUOUS for impact in split)
