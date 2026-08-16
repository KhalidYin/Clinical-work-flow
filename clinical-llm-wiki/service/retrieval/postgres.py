"""PostgreSQL metadata and full-text search for the P17 candidate sandbox."""

from __future__ import annotations

from collections import defaultdict
import re

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from service.db.models import (
    Evidence,
    RetrievalChunk,
    RetrievalChunkEvidence,
    Source,
    SourceVersion,
)

from .contracts import CandidateSearchRecord, EvidenceCitation, ReleaseCandidateScope


class PostgresCandidateSearchRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def search_metadata_fts(
        self,
        *,
        query: str,
        scope: ReleaseCandidateScope,
        limit: int,
    ) -> list[CandidateSearchRecord]:
        search_query = _websearch_or_query(query)
        with self._sessions() as session:
            query_expression = func.websearch_to_tsquery("english", search_query)
            content_vector = func.to_tsvector("english", RetrievalChunk.content)
            metadata_text = func.concat_ws(
                " ",
                Source.title,
                Source.source_type,
                SourceVersion.version,
                RetrievalChunk.evidence_type,
                cast(RetrievalChunk.locator, Text),
            )
            metadata_vector = func.to_tsvector("english", metadata_text)
            full_text_score = func.ts_rank_cd(content_vector, query_expression)
            metadata_score = func.ts_rank_cd(metadata_vector, query_expression)
            statement = (
                select(
                    RetrievalChunk,
                    Source.title,
                    SourceVersion.version,
                    metadata_score.label("metadata_score"),
                    full_text_score.label("full_text_score"),
                )
                .join(
                    SourceVersion,
                    SourceVersion.source_version_id == RetrievalChunk.source_version_id,
                )
                .join(Source, Source.source_id == SourceVersion.source_id)
                .where(
                    RetrievalChunk.source_version_id.in_(scope.source_version_ids),
                    RetrievalChunk.chunk_profile_id == scope.chunk_profile_id,
                    RetrievalChunk.data_boundary != "prohibited",
                    RetrievalChunk.rights["storage_allowed"].as_boolean().is_(True),
                    or_(
                        content_vector.op("@@")(query_expression),
                        metadata_vector.op("@@")(query_expression),
                    ),
                )
                .order_by(
                    (full_text_score + metadata_score).desc(),
                    full_text_score.desc(),
                    metadata_score.desc(),
                    RetrievalChunk.ordinal,
                    RetrievalChunk.chunk_id,
                )
                .limit(limit)
            )
            rows = list(session.execute(statement))
            citations = _citations_by_chunk(
                session,
                [row[0].chunk_id for row in rows],
            )
        return [
            CandidateSearchRecord(
                chunk_id=chunk.chunk_id,
                chunk_profile_id=chunk.chunk_profile_id,
                source_version_id=chunk.source_version_id,
                source_title=source_title,
                source_version=source_version,
                ordinal=chunk.ordinal,
                evidence_type=chunk.evidence_type,
                content=chunk.content,
                content_sha256=chunk.content_sha256,
                token_count=chunk.token_count,
                locator=chunk.locator,
                metadata_score=float(metadata_score_value),
                full_text_score=float(full_text_score_value),
                citations=tuple(citations[chunk.chunk_id]),
            )
            for (
                chunk,
                source_title,
                source_version,
                metadata_score_value,
                full_text_score_value,
            ) in rows
        ]

    def search_released_metadata_fts(
        self,
        *,
        query: str,
        chunk_ids: tuple[str, ...],
        chunk_profile_id: str,
        limit: int,
    ) -> list[CandidateSearchRecord]:
        """Search only the exact Chunk membership frozen by a resolved Release."""

        if not chunk_ids:
            return []
        search_query = _websearch_or_query(query)
        with self._sessions() as session:
            query_expression = func.websearch_to_tsquery("english", search_query)
            content_vector = func.to_tsvector("english", RetrievalChunk.content)
            metadata_text = func.concat_ws(
                " ",
                Source.title,
                Source.source_type,
                SourceVersion.version,
                RetrievalChunk.evidence_type,
                cast(RetrievalChunk.locator, Text),
            )
            metadata_vector = func.to_tsvector("english", metadata_text)
            full_text_score = func.ts_rank_cd(content_vector, query_expression)
            metadata_score = func.ts_rank_cd(metadata_vector, query_expression)
            statement = (
                select(
                    RetrievalChunk,
                    Source.title,
                    SourceVersion.version,
                    metadata_score.label("metadata_score"),
                    full_text_score.label("full_text_score"),
                )
                .join(
                    SourceVersion,
                    SourceVersion.source_version_id == RetrievalChunk.source_version_id,
                )
                .join(Source, Source.source_id == SourceVersion.source_id)
                .where(
                    RetrievalChunk.chunk_id.in_(chunk_ids),
                    RetrievalChunk.chunk_profile_id == chunk_profile_id,
                    RetrievalChunk.data_boundary != "prohibited",
                    RetrievalChunk.rights["storage_allowed"].as_boolean().is_(True),
                    or_(
                        content_vector.op("@@")(query_expression),
                        metadata_vector.op("@@")(query_expression),
                    ),
                )
                .order_by(
                    (full_text_score + metadata_score).desc(),
                    full_text_score.desc(),
                    metadata_score.desc(),
                    RetrievalChunk.ordinal,
                    RetrievalChunk.chunk_id,
                )
                .limit(limit)
            )
            rows = list(session.execute(statement))
            citations = _citations_by_chunk(
                session,
                [row[0].chunk_id for row in rows],
            )
        return [
            CandidateSearchRecord(
                chunk_id=chunk.chunk_id,
                chunk_profile_id=chunk.chunk_profile_id,
                source_version_id=chunk.source_version_id,
                source_title=source_title,
                source_version=source_version,
                ordinal=chunk.ordinal,
                evidence_type=chunk.evidence_type,
                content=chunk.content,
                content_sha256=chunk.content_sha256,
                token_count=chunk.token_count,
                locator=chunk.locator,
                metadata_score=float(metadata_score_value),
                full_text_score=float(full_text_score_value),
                citations=tuple(citations[chunk.chunk_id]),
            )
            for (
                chunk,
                source_title,
                source_version,
                metadata_score_value,
                full_text_score_value,
            ) in rows
        ]


def _websearch_or_query(value: str) -> str:
    tokens: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE):
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
        if len(tokens) == 32:
            break
    if not tokens:
        raise ValueError("query has no searchable terms")
    return " OR ".join(tokens)


def _citations_by_chunk(
    session: Session,
    chunk_ids: list[str],
) -> dict[str, list[EvidenceCitation]]:
    grouped: dict[str, list[EvidenceCitation]] = defaultdict(list)
    if not chunk_ids:
        return grouped
    rows = session.execute(
        select(RetrievalChunkEvidence, Evidence)
        .join(Evidence, Evidence.evidence_id == RetrievalChunkEvidence.evidence_id)
        .where(RetrievalChunkEvidence.chunk_id.in_(chunk_ids))
        .order_by(
            RetrievalChunkEvidence.chunk_id,
            RetrievalChunkEvidence.position,
        )
    )
    for span, evidence in rows:
        if evidence.source_artifact_id is None:
            raise ValueError("canonical Evidence citation has no source artifact")
        grouped[span.chunk_id].append(
            EvidenceCitation(
                evidence_id=evidence.evidence_id,
                source_version_id=evidence.source_version_id,
                source_artifact_id=evidence.source_artifact_id,
                locator=evidence.locator,
                content_sha256=evidence.content_sha256,
                start_offset=span.start_offset,
                end_offset=span.end_offset,
                span_role=span.span_role,
            )
        )
    return grouped


__all__ = ["PostgresCandidateSearchRepository"]
