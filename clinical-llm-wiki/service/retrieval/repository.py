"""PostgreSQL read adapter for governed retrieval candidates and citations."""

from __future__ import annotations

from collections import deque
from hashlib import sha256
from typing import Iterable, Sequence

from sqlalchemy import Text, cast, func, literal, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from service.db.models import (
    CandidateEvidence,
    Evidence,
    KnowledgeCandidate,
    KnowledgeRelation,
    KnowledgeRevision,
    KnowledgeUnit,
    Release,
    ReleaseItem,
    Source,
    SourceVersion,
)

from .contracts import (
    ChannelCandidate,
    Citation,
    ReleaseScope,
    RetrievalChannel,
    RetrievalChannelUnavailable,
    RetrievalRequest,
    RetrievalVisibility,
    RevisionDocument,
)


class SqlAlchemyRetrievalRepository:
    """Query canonical revisions without creating a Candidate/approved visibility bypass."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def current_release(self) -> ReleaseScope | None:
        with self._session_factory() as session:
            release = session.scalar(
                select(Release)
                .where(Release.status == "released")
                .order_by(
                    Release.published_at.desc().nullslast(),
                    Release.created_at.desc(),
                )
                .limit(1)
            )
        if release is None:
            return None
        return ReleaseScope(
            release_id=release.release_id,
            version=release.version,
            index_version=release.index_manifest_version,
        )

    def index_version(
        self,
        *,
        visibility: RetrievalVisibility,
        release_scope: ReleaseScope | None,
    ) -> str | None:
        if visibility is RetrievalVisibility.RELEASED:
            return release_scope.index_version if release_scope else None
        with self._session_factory() as session:
            hashes = tuple(
                session.scalars(
                    select(KnowledgeRevision.content_sha256)
                    .where(KnowledgeRevision.status == "approved")
                    .order_by(
                        KnowledgeRevision.knowledge_unit_id,
                        KnowledgeRevision.revision_number,
                    )
                )
            )
        digest = sha256("\n".join(hashes).encode("utf-8")).hexdigest()[:16]
        return f"evaluation-direct@{digest}"

    def metadata_candidates(
        self,
        request: RetrievalRequest,
        *,
        release_scope: ReleaseScope | None,
    ) -> Sequence[ChannelCandidate]:
        documents = self._visible_documents(
            visibility=request.visibility,
            release_scope=release_scope,
        )
        candidates: list[ChannelCandidate] = []
        query = request.query.casefold()
        query_tokens = {token for token in _tokenize(query) if token}
        has_filters = _has_filters(request)
        for document in documents:
            if not _document_matches_filters(document, request):
                continue
            metadata = " ".join(
                (
                    document.stable_key,
                    document.knowledge_type,
                    _flatten_json(document.scope),
                    _flatten_json(document.applicability),
                )
            ).casefold()
            metadata_tokens = set(_tokenize(metadata))
            if query == document.stable_key.casefold():
                score = 1.0
            elif query in metadata:
                score = 0.95
            elif query_tokens and query_tokens.issubset(metadata_tokens):
                score = 0.85
            elif query_tokens.intersection(metadata_tokens):
                score = 0.65
            elif has_filters:
                score = 0.5
            else:
                continue
            candidates.append(ChannelCandidate(document=document, score=score))
        return candidates

    def fts_candidates(
        self,
        request: RetrievalRequest,
        *,
        release_scope: ReleaseScope | None,
    ) -> Sequence[ChannelCandidate]:
        try:
            with self._session_factory() as session:
                visibility = self._visibility_clause(
                    request.visibility,
                    release_scope=release_scope,
                )
                document_text = func.concat_ws(
                    " ",
                    KnowledgeUnit.stable_key,
                    KnowledgeUnit.knowledge_type,
                    KnowledgeRevision.claim,
                    cast(KnowledgeRevision.scope, Text),
                    func.coalesce(cast(KnowledgeRevision.applicability, Text), literal("")),
                )
                vector = func.to_tsvector(text("'simple'::regconfig"), document_text)
                tsquery = func.websearch_to_tsquery(
                    text("'simple'::regconfig"),
                    request.query,
                )
                statement = (
                    select(
                        KnowledgeRevision.knowledge_revision_id,
                        func.ts_rank_cd(vector, tsquery).label("score"),
                    )
                    .join(
                        KnowledgeUnit,
                        KnowledgeUnit.knowledge_unit_id
                        == KnowledgeRevision.knowledge_unit_id,
                    )
                    .join(
                        KnowledgeCandidate,
                        KnowledgeCandidate.candidate_id
                        == KnowledgeRevision.candidate_id,
                    )
                    .where(visibility, vector.op("@@")(tsquery))
                )
                if request.filters.knowledge_types:
                    statement = statement.where(
                        KnowledgeUnit.knowledge_type.in_(
                            request.filters.knowledge_types
                        )
                    )
                rows = session.execute(
                    statement.order_by(
                        text("score DESC"),
                        KnowledgeUnit.stable_key,
                        KnowledgeRevision.knowledge_revision_id,
                    ).limit(max(request.limit * 4, 20))
                ).all()
                documents = self._documents_by_revision_ids(
                    session,
                    [str(row.knowledge_revision_id) for row in rows],
                    visibility=request.visibility,
                    release_scope=release_scope,
                )
        except SQLAlchemyError as exc:
            raise RetrievalChannelUnavailable(
                RetrievalChannel.FTS,
                reason="postgres_fts_query_failed",
            ) from exc

        by_id = {
            document.knowledge_revision_id: document for document in documents
        }
        return [
            ChannelCandidate(
                document=by_id[str(row.knowledge_revision_id)],
                score=float(row.score),
            )
            for row in rows
            if str(row.knowledge_revision_id) in by_id
            and _document_matches_filters(
                by_id[str(row.knowledge_revision_id)],
                request,
            )
        ]

    def relation_candidates(
        self,
        *,
        seed_revision_ids: Sequence[str],
        visibility: RetrievalVisibility,
        release_scope: ReleaseScope | None,
        depth: int,
        limit: int,
    ) -> Sequence[ChannelCandidate]:
        if depth <= 0 or not seed_revision_ids:
            return ()
        try:
            documents = self._visible_documents(
                visibility=visibility,
                release_scope=release_scope,
            )
            by_revision = {
                document.knowledge_revision_id: document for document in documents
            }
            by_unit = {document.knowledge_unit_id: document for document in documents}
            with self._session_factory() as session:
                relations = tuple(
                    session.scalars(
                        select(KnowledgeRelation).where(
                            KnowledgeRelation.source_revision_id.in_(tuple(by_revision))
                        )
                    )
                )
        except SQLAlchemyError as exc:
            raise RetrievalChannelUnavailable(
                RetrievalChannel.RELATION,
                reason="relation_query_failed",
            ) from exc

        edges_by_revision: dict[str, list[KnowledgeRelation]] = {}
        for relation in relations:
            if relation.target_knowledge_unit_id not in by_unit:
                continue
            edges_by_revision.setdefault(relation.source_revision_id, []).append(
                relation
            )
        for edges in edges_by_revision.values():
            edges.sort(
                key=lambda edge: (
                    edge.relation_type,
                    edge.target_knowledge_unit_id,
                    edge.relation_id,
                )
            )

        queue: deque[tuple[str, int, tuple[str, ...]]] = deque()
        for revision_id in seed_revision_ids:
            if revision_id in by_revision:
                queue.append(
                    (
                        revision_id,
                        0,
                        (by_revision[revision_id].stable_key,),
                    )
                )
        best: dict[str, ChannelCandidate] = {}
        visited_at_depth: dict[str, int] = {
            revision_id: 0 for revision_id in seed_revision_ids
        }
        while queue:
            revision_id, current_depth, path = queue.popleft()
            if current_depth >= depth:
                continue
            for edge in edges_by_revision.get(revision_id, ()):
                target = by_unit[edge.target_knowledge_unit_id]
                next_depth = current_depth + 1
                next_path = path + (edge.relation_type, target.stable_key)
                score = 1.0 / next_depth
                existing = best.get(target.knowledge_revision_id)
                candidate = ChannelCandidate(
                    document=target,
                    score=score,
                    relation_paths=(next_path,),
                )
                if existing is None:
                    best[target.knowledge_revision_id] = candidate
                else:
                    merged_paths = tuple(
                        sorted(
                            {
                                *existing.relation_paths,
                                *candidate.relation_paths,
                            }
                        )
                    )
                    best[target.knowledge_revision_id] = ChannelCandidate(
                        document=target,
                        score=max(existing.score, score),
                        relation_paths=merged_paths,
                    )
                previous_depth = visited_at_depth.get(target.knowledge_revision_id)
                if previous_depth is None or next_depth < previous_depth:
                    visited_at_depth[target.knowledge_revision_id] = next_depth
                    queue.append(
                        (target.knowledge_revision_id, next_depth, next_path)
                    )
        return tuple(
            sorted(
                best.values(),
                key=lambda item: (
                    -item.score,
                    item.document.stable_key,
                    item.document.knowledge_revision_id,
                ),
            )[:limit]
        )

    def get_revision(
        self,
        *,
        knowledge_revision_id: str,
        visibility: RetrievalVisibility,
        release_scope: ReleaseScope | None,
    ) -> RevisionDocument | None:
        with self._session_factory() as session:
            documents = self._documents_by_revision_ids(
                session,
                [knowledge_revision_id],
                visibility=visibility,
                release_scope=release_scope,
            )
        return documents[0] if documents else None

    def _visible_documents(
        self,
        *,
        visibility: RetrievalVisibility,
        release_scope: ReleaseScope | None,
    ) -> tuple[RevisionDocument, ...]:
        with self._session_factory() as session:
            revision_ids = tuple(
                session.scalars(
                    select(KnowledgeRevision.knowledge_revision_id)
                    .join(
                        KnowledgeUnit,
                        KnowledgeUnit.knowledge_unit_id
                        == KnowledgeRevision.knowledge_unit_id,
                    )
                    .where(
                        self._visibility_clause(
                            visibility,
                            release_scope=release_scope,
                        )
                    )
                    .order_by(
                        KnowledgeUnit.stable_key,
                        KnowledgeRevision.revision_number,
                    )
                )
            )
            return self._documents_by_revision_ids(
                session,
                revision_ids,
                visibility=visibility,
                release_scope=release_scope,
            )

    def _documents_by_revision_ids(
        self,
        session: Session,
        revision_ids: Iterable[str],
        *,
        visibility: RetrievalVisibility,
        release_scope: ReleaseScope | None,
    ) -> tuple[RevisionDocument, ...]:
        ids = tuple(dict.fromkeys(revision_ids))
        if not ids:
            return ()
        rows = session.execute(
            select(KnowledgeRevision, KnowledgeUnit, KnowledgeCandidate)
            .join(
                KnowledgeUnit,
                KnowledgeUnit.knowledge_unit_id
                == KnowledgeRevision.knowledge_unit_id,
            )
            .join(
                KnowledgeCandidate,
                KnowledgeCandidate.candidate_id == KnowledgeRevision.candidate_id,
            )
            .where(
                KnowledgeRevision.knowledge_revision_id.in_(ids),
                self._visibility_clause(
                    visibility,
                    release_scope=release_scope,
                ),
            )
        ).all()
        release_ids_by_revision: dict[str, tuple[str, ...]] = {}
        if rows:
            release_rows = session.execute(
                select(
                    ReleaseItem.knowledge_revision_id,
                    ReleaseItem.release_id,
                )
                .join(Release, Release.release_id == ReleaseItem.release_id)
                .where(
                    ReleaseItem.knowledge_revision_id.in_(
                        tuple(row[0].knowledge_revision_id for row in rows)
                    ),
                    Release.status == "released",
                )
                .order_by(ReleaseItem.release_id)
            ).all()
            grouped: dict[str, list[str]] = {}
            for revision_id, release_id in release_rows:
                grouped.setdefault(str(revision_id), []).append(str(release_id))
            release_ids_by_revision = {
                revision_id: tuple(release_ids)
                for revision_id, release_ids in grouped.items()
            }

        documents = [
            RevisionDocument(
                knowledge_unit_id=unit.knowledge_unit_id,
                stable_key=unit.stable_key,
                knowledge_type=unit.knowledge_type,
                knowledge_revision_id=revision.knowledge_revision_id,
                revision_number=revision.revision_number,
                revision_status=revision.status,
                claim=revision.claim,
                scope=dict(revision.scope),
                applicability=dict(revision.applicability or {}),
                conditions=tuple(dict(item) for item in revision.conditions),
                exceptions=tuple(dict(item) for item in revision.exceptions),
                content_sha256=revision.content_sha256,
                release_ids=release_ids_by_revision.get(
                    revision.knowledge_revision_id,
                    (),
                ),
                citations=self._citations_for_candidate(
                    session,
                    candidate.candidate_id,
                ),
            )
            for revision, unit, candidate in rows
        ]
        order = {revision_id: index for index, revision_id in enumerate(ids)}
        return tuple(
            sorted(
                documents,
                key=lambda item: order[item.knowledge_revision_id],
            )
        )

    def _citations_for_candidate(
        self,
        session: Session,
        candidate_id: str,
    ) -> tuple[Citation, ...]:
        rows = session.execute(
            select(Evidence, SourceVersion, Source)
            .join(
                CandidateEvidence,
                CandidateEvidence.evidence_id == Evidence.evidence_id,
            )
            .join(
                SourceVersion,
                SourceVersion.source_version_id == Evidence.source_version_id,
            )
            .join(Source, Source.source_id == SourceVersion.source_id)
            .where(CandidateEvidence.candidate_id == candidate_id)
            .order_by(
                Source.source_id,
                SourceVersion.version,
                Evidence.evidence_id,
            )
        ).all()
        return tuple(
            Citation(
                evidence_id=evidence.evidence_id,
                source_id=source.source_id,
                source_title=source.title,
                source_version_id=source_version.source_version_id,
                source_version=source_version.version,
                locator=dict(evidence.locator),
                content_sha256=evidence.content_sha256,
                source_sha256=source_version.sha256,
                rights_classification=str(
                    source_version.rights.get("classification", "restricted")
                ),
                citation_required=bool(
                    source_version.rights.get("citation_required", True)
                ),
            )
            for evidence, source_version, source in rows
        )

    def _visibility_clause(
        self,
        visibility: RetrievalVisibility,
        *,
        release_scope: ReleaseScope | None,
    ):
        if visibility is RetrievalVisibility.EVALUATION:
            return KnowledgeRevision.status == "approved"
        if release_scope is None:
            return literal(False)
        return KnowledgeRevision.knowledge_revision_id.in_(
            select(ReleaseItem.knowledge_revision_id).where(
                ReleaseItem.release_id == release_scope.release_id
            )
        )


def _has_filters(request: RetrievalRequest) -> bool:
    filters = request.filters
    return bool(
        filters.knowledge_types
        or filters.scope
        or filters.source_version_ids
        or filters.rights_classifications
    )


def _document_matches_filters(
    document: RevisionDocument,
    request: RetrievalRequest,
) -> bool:
    filters = request.filters
    if (
        filters.knowledge_types
        and document.knowledge_type not in filters.knowledge_types
    ):
        return False
    for key, expected in filters.scope.items():
        if str(document.scope.get(key, "")) != expected:
            return False
    if filters.source_version_ids and not any(
        citation.source_version_id in filters.source_version_ids
        for citation in document.citations
    ):
        return False
    if filters.rights_classifications and not any(
        citation.rights_classification in filters.rights_classifications
        for citation in document.citations
    ):
        return False
    return True


def _flatten_json(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(
            f"{key} {_flatten_json(item)}"
            for key, item in sorted(value.items())
        )
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_json(item) for item in value)
    return str(value)


def _tokenize(value: str) -> tuple[str, ...]:
    normalized = "".join(character if character.isalnum() else " " for character in value)
    return tuple(token for token in normalized.casefold().split() if token)
