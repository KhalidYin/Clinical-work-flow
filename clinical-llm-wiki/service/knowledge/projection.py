"""Deterministic P17 Evidence comparison and retrieval-chunk projection."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, model_validator

from .lifecycle import (
    ChunkProfileContract,
    EvidenceChangeType,
    EvidenceImpactRecord,
    EvidenceMappingBasis,
    ImpactAssessmentRecord,
    StrictLifecycleModel,
    retrieval_chunk_identity,
)


class ProjectionEvidence(StrictLifecycleModel):
    evidence_id: str = Field(min_length=1, max_length=160)
    source_version_id: str = Field(min_length=1, max_length=160)
    source_artifact_id: str = Field(min_length=1, max_length=160)
    evidence_type: str = Field(min_length=1, max_length=80)
    document_order: int = Field(ge=0)
    major_section: str = Field(min_length=1, max_length=500)
    table_id: str | None = Field(default=None, max_length=500)
    locator: dict[str, Any] = Field(min_length=1)
    content: str
    data_boundary: Literal[
        "local_processing_only",
        "enterprise_provider_only",
        "external_allowed",
        "prohibited",
    ]
    rights: dict[str, Any] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_table_boundary(self) -> "ProjectionEvidence":
        if self.evidence_type == "table" and self.table_id is None:
            raise ValueError("table evidence requires table_id")
        if self.evidence_type != "table" and self.table_id is not None:
            raise ValueError("non-table evidence cannot include table_id")
        return self


class ProjectedEvidenceSpan(StrictLifecycleModel):
    evidence_id: str
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    span_role: Literal["primary", "overlap"]

    @model_validator(mode="after")
    def validate_offsets(self) -> "ProjectedEvidenceSpan":
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        return self


class ProjectedRetrievalChunk(StrictLifecycleModel):
    chunk_id: str
    chunk_profile_id: str
    profile_version: str
    source_version_id: str
    source_artifact_id: str
    evidence_type: str
    ordinal: int = Field(ge=0)
    content: str = Field(min_length=1)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    token_count: int = Field(gt=0)
    locator: dict[str, Any]
    data_boundary: str
    rights: dict[str, Any]
    spans: tuple[ProjectedEvidenceSpan, ...] = Field(min_length=1)


class ProjectionFinding(StrictLifecycleModel):
    finding_id: str
    evidence_id: str | None
    finding_type: Literal[
        "empty",
        "duplicate",
        "boilerplate",
        "oversize",
        "boundary_violation",
    ]
    details: dict[str, Any]


class ChunkProjectionResult(StrictLifecycleModel):
    chunk_profile: ChunkProfileContract
    chunks: tuple[ProjectedRetrievalChunk, ...]
    findings: tuple[ProjectionFinding, ...]


@dataclass(frozen=True, slots=True)
class ComparableEvidence:
    evidence_id: str
    content_sha256: str
    locator_sha256: str
    rights: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise ValueError("evidence_id is required")
        for label, value in (
            ("content_sha256", self.content_sha256),
            ("locator_sha256", self.locator_sha256),
        ):
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ValueError(f"{label} must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class _Token:
    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class _Segment:
    evidence: ProjectionEvidence
    start_offset: int
    end_offset: int
    token_count: int
    span_role: Literal["primary", "overlap"]


def project_retrieval_chunks(
    *,
    profile: ChunkProfileContract,
    evidence: tuple[ProjectionEvidence, ...],
) -> ChunkProjectionResult:
    """Project ordered Evidence into immutable, explainable chunks."""

    _validate_projection_input(evidence)
    accepted, findings = _filter_projection_evidence(profile, evidence)
    chunks: list[ProjectedRetrievalChunk] = []
    pending: list[_Segment] = []
    pending_tokens = 0
    pending_boundary: tuple[str, ...] | None = None

    def flush() -> list[_Segment]:
        nonlocal pending, pending_tokens
        if not pending:
            return []
        emitted = list(pending)
        chunks.append(_build_chunk(profile, len(chunks), emitted))
        overlap = _tail_overlap(emitted, profile.overlap_tokens)
        pending = []
        pending_tokens = 0
        return overlap

    for item in accepted:
        tokens = _tokens(item.content)
        limit = (
            profile.table_hard_max_tokens
            if item.evidence_type == "table"
            else profile.hard_max_tokens
        )
        boundary = _boundary_key(item)
        if boundary != pending_boundary:
            flush()
            pending_boundary = boundary

        if len(tokens) > limit:
            flush()
            findings.append(
                _finding(
                    profile,
                    item.evidence_id,
                    "oversize",
                    {"tokenCount": len(tokens), "hardMaxTokens": limit},
                )
            )
            if item.evidence_type == "table":
                findings.append(
                    _finding(
                        profile,
                        item.evidence_id,
                        "boundary_violation",
                        {"reason": "table_row_exceeds_atomic_limit"},
                    )
                )
                continue
            for segments in _split_oversize(item, tokens, limit, profile.overlap_tokens):
                chunks.append(_build_chunk(profile, len(chunks), segments))
            pending_boundary = None
            continue

        segment = _full_segment(item)
        if pending and pending_tokens + len(tokens) > profile.target_max_tokens:
            if pending_tokens >= profile.target_min_tokens:
                overlap = flush()
                pending = overlap
                pending_tokens = sum(part.token_count for part in overlap)
            elif pending_tokens + len(tokens) > limit:
                flush()
        pending.append(segment)
        pending_tokens += len(tokens)

    flush()
    return ChunkProjectionResult(
        chunk_profile=profile,
        chunks=tuple(chunks),
        findings=tuple(findings),
    )


def compare_evidence_versions(
    *,
    assessment_id: str,
    from_source_version_id: str,
    to_source_version_id: str,
    comparison_profile_version: str,
    from_evidence: tuple[ComparableEvidence, ...],
    to_evidence: tuple[ComparableEvidence, ...],
) -> ImpactAssessmentRecord:
    """Classify two Evidence sets without mutating either source version."""

    _require_unique_ids(from_evidence)
    _require_unique_ids(to_evidence)
    impacts: list[EvidenceImpactRecord] = []
    matched_from: set[str] = set()
    matched_to: set[str] = set()
    from_by_content = _group_by(from_evidence, "content_sha256")
    to_by_content = _group_by(to_evidence, "content_sha256")

    for content_hash in sorted(from_by_content.keys() & to_by_content.keys()):
        old_group = from_by_content[content_hash]
        new_group = to_by_content[content_hash]
        if len(old_group) != 1 or len(new_group) != 1:
            for old in old_group:
                for new in new_group:
                    impacts.append(
                        _impact(
                            assessment_id,
                            EvidenceChangeType.AMBIGUOUS,
                            old,
                            new,
                            EvidenceMappingBasis.AMBIGUOUS,
                            {"reason": "many_to_many_content_match"},
                        )
                    )
            matched_from.update(item.evidence_id for item in old_group)
            matched_to.update(item.evidence_id for item in new_group)
            continue
        old = old_group[0]
        new = new_group[0]
        if _canonical_json(old.rights) != _canonical_json(new.rights):
            change_type = EvidenceChangeType.RIGHTS_CHANGED
        elif old.locator_sha256 == new.locator_sha256:
            change_type = EvidenceChangeType.UNCHANGED
        else:
            change_type = EvidenceChangeType.MOVED
        impacts.append(
            _impact(
                assessment_id,
                change_type,
                old,
                new,
                EvidenceMappingBasis.CONTENT_EXACT,
                {},
            )
        )
        matched_from.add(old.evidence_id)
        matched_to.add(new.evidence_id)

    remaining_from = [item for item in from_evidence if item.evidence_id not in matched_from]
    remaining_to = [item for item in to_evidence if item.evidence_id not in matched_to]
    from_by_locator = _group_by(remaining_from, "locator_sha256")
    to_by_locator = _group_by(remaining_to, "locator_sha256")
    for locator_hash in sorted(from_by_locator.keys() & to_by_locator.keys()):
        old_group = from_by_locator[locator_hash]
        new_group = to_by_locator[locator_hash]
        if len(old_group) == 1 and len(new_group) == 1:
            old = old_group[0]
            new = new_group[0]
            impacts.append(
                _impact(
                    assessment_id,
                    EvidenceChangeType.MODIFIED,
                    old,
                    new,
                    EvidenceMappingBasis.LOCATOR_EXACT,
                    {},
                )
            )
        else:
            for old in old_group:
                for new in new_group:
                    impacts.append(
                        _impact(
                            assessment_id,
                            EvidenceChangeType.AMBIGUOUS,
                            old,
                            new,
                            EvidenceMappingBasis.AMBIGUOUS,
                            {"reason": "many_to_many_locator_match"},
                        )
                    )
        matched_from.update(item.evidence_id for item in old_group)
        matched_to.update(item.evidence_id for item in new_group)

    for old in from_evidence:
        if old.evidence_id not in matched_from:
            impacts.append(
                _impact(
                    assessment_id,
                    EvidenceChangeType.REMOVED,
                    old,
                    None,
                    EvidenceMappingBasis.UNMATCHED,
                    {},
                )
            )
    for new in to_evidence:
        if new.evidence_id not in matched_to:
            impacts.append(
                _impact(
                    assessment_id,
                    EvidenceChangeType.ADDED,
                    None,
                    new,
                    EvidenceMappingBasis.UNMATCHED,
                    {},
                )
            )

    return ImpactAssessmentRecord(
        assessment_id=assessment_id,
        from_source_version_id=from_source_version_id,
        to_source_version_id=to_source_version_id,
        comparison_profile_version=comparison_profile_version,
        impacts=tuple(impacts),
    )


def _tokens(content: str) -> tuple[_Token, ...]:
    return tuple(_Token(match.group(), match.start(), match.end()) for match in re.finditer(r"\S+", content))


def _full_segment(item: ProjectionEvidence) -> _Segment:
    tokens = _tokens(item.content)
    return _Segment(item, tokens[0].start, tokens[-1].end, len(tokens), "primary")


def _split_oversize(
    item: ProjectionEvidence,
    tokens: tuple[_Token, ...],
    limit: int,
    overlap: int,
) -> list[list[_Segment]]:
    chunks: list[list[_Segment]] = []
    primary_start = 0
    prior_end = 0
    while primary_start < len(tokens):
        segments: list[_Segment] = []
        if primary_start and overlap:
            overlap_start = max(0, prior_end - overlap)
            segments.append(
                _Segment(
                    item,
                    tokens[overlap_start].start,
                    tokens[prior_end - 1].end,
                    prior_end - overlap_start,
                    "overlap",
                )
            )
        primary_limit = limit - sum(segment.token_count for segment in segments)
        primary_end = min(len(tokens), primary_start + primary_limit)
        segments.append(
            _Segment(
                item,
                tokens[primary_start].start,
                tokens[primary_end - 1].end,
                primary_end - primary_start,
                "primary",
            )
        )
        chunks.append(segments)
        prior_end = primary_end
        primary_start = primary_end
    return chunks


def _tail_overlap(segments: list[_Segment], limit: int) -> list[_Segment]:
    if limit == 0:
        return []
    remaining = limit
    result: list[_Segment] = []
    for segment in reversed(segments):
        tokens = _tokens(segment.evidence.content[segment.start_offset : segment.end_offset])
        take = min(remaining, len(tokens))
        if take:
            start = segment.start_offset + tokens[-take].start
            end = segment.start_offset + tokens[-1].end
            result.append(_Segment(segment.evidence, start, end, take, "overlap"))
            remaining -= take
        if remaining == 0:
            break
    return list(reversed(result))


def _build_chunk(
    profile: ChunkProfileContract,
    ordinal: int,
    segments: list[_Segment],
) -> ProjectedRetrievalChunk:
    first = segments[0].evidence
    content = " ".join(
        segment.evidence.content[segment.start_offset : segment.end_offset]
        for segment in segments
    )
    content_hash = sha256(content.encode("utf-8")).hexdigest()
    spans = tuple(
        ProjectedEvidenceSpan(
            evidence_id=segment.evidence.evidence_id,
            start_offset=segment.start_offset,
            end_offset=segment.end_offset,
            span_role=segment.span_role,
        )
        for segment in segments
    )
    identity_spans = tuple(
        (span.evidence_id, span.start_offset, span.end_offset, span.span_role)
        for span in spans
    )
    return ProjectedRetrievalChunk(
        chunk_id=retrieval_chunk_identity(
            profile_version=profile.version,
            source_version_id=first.source_version_id,
            ordinal=ordinal,
            evidence_spans=identity_spans,
            content_sha256=content_hash,
        ),
        chunk_profile_id=profile.chunk_profile_id,
        profile_version=profile.version,
        source_version_id=first.source_version_id,
        source_artifact_id=first.source_artifact_id,
        evidence_type=first.evidence_type,
        ordinal=ordinal,
        content=content,
        content_sha256=content_hash,
        token_count=sum(segment.token_count for segment in segments),
        locator={
            "majorSection": first.major_section,
            "tableId": first.table_id,
            "evidenceIds": list(dict.fromkeys(segment.evidence.evidence_id for segment in segments)),
        },
        data_boundary=first.data_boundary,
        rights=first.rights,
        spans=spans,
    )


def _filter_projection_evidence(
    profile: ChunkProfileContract,
    evidence: tuple[ProjectionEvidence, ...],
) -> tuple[list[ProjectionEvidence], list[ProjectionFinding]]:
    accepted: list[ProjectionEvidence] = []
    findings: list[ProjectionFinding] = []
    hashes: set[str] = set()
    for item in sorted(evidence, key=lambda value: value.document_order):
        if not item.content.strip():
            findings.append(_finding(profile, item.evidence_id, "empty", {}))
            continue
        if item.locator.get("is_boilerplate") is True:
            findings.append(_finding(profile, item.evidence_id, "boilerplate", {}))
            continue
        content_hash = sha256(item.content.strip().encode("utf-8")).hexdigest()
        if content_hash in hashes:
            findings.append(
                _finding(profile, item.evidence_id, "duplicate", {"contentSha256": content_hash})
            )
            continue
        hashes.add(content_hash)
        accepted.append(item)
    return accepted, findings


def _finding(
    profile: ChunkProfileContract,
    evidence_id: str | None,
    finding_type: str,
    details: dict[str, Any],
) -> ProjectionFinding:
    canonical = _canonical_json(
        {
            "details": details,
            "evidence_id": evidence_id,
            "finding_type": finding_type,
            "profile_version": profile.version,
        }
    )
    return ProjectionFinding(
        finding_id=f"finding-{uuid5(NAMESPACE_URL, canonical).hex}",
        evidence_id=evidence_id,
        finding_type=finding_type,
        details=details,
    )


def _validate_projection_input(evidence: tuple[ProjectionEvidence, ...]) -> None:
    ids = [item.evidence_id for item in evidence]
    orders = [item.document_order for item in evidence]
    if len(ids) != len(set(ids)):
        raise ValueError("projection evidence IDs must be unique")
    if len(orders) != len(set(orders)):
        raise ValueError("projection document_order values must be unique")


def _boundary_key(item: ProjectionEvidence) -> tuple[str, ...]:
    return (
        item.source_version_id,
        item.source_artifact_id,
        item.major_section,
        item.table_id or "",
        item.evidence_type,
        item.data_boundary,
        _canonical_json(item.rights),
    )


def _require_unique_ids(evidence: tuple[ComparableEvidence, ...]) -> None:
    ids = [item.evidence_id for item in evidence]
    if len(ids) != len(set(ids)):
        raise ValueError("comparison Evidence IDs must be unique")


def _group_by(
    evidence: list[ComparableEvidence] | tuple[ComparableEvidence, ...],
    attribute: str,
) -> dict[str, list[ComparableEvidence]]:
    groups: dict[str, list[ComparableEvidence]] = {}
    for item in evidence:
        groups.setdefault(getattr(item, attribute), []).append(item)
    return groups


def _impact(
    assessment_id: str,
    change_type: EvidenceChangeType,
    old: ComparableEvidence | None,
    new: ComparableEvidence | None,
    mapping_basis: EvidenceMappingBasis,
    details: dict[str, Any],
) -> EvidenceImpactRecord:
    facts = {
        "assessment_id": assessment_id,
        "change_type": change_type.value,
        "from_evidence_id": old.evidence_id if old else None,
        "to_evidence_id": new.evidence_id if new else None,
        "mapping_basis": mapping_basis.value,
    }
    identity = uuid5(NAMESPACE_URL, _canonical_json(facts)).hex
    return EvidenceImpactRecord(
        evidence_impact_id=f"impact-{identity}",
        change_type=change_type,
        from_evidence_id=facts["from_evidence_id"],
        to_evidence_id=facts["to_evidence_id"],
        mapping_basis=mapping_basis,
        details=details,
    )


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
