"""Explainable hybrid retrieval orchestration with fail-closed visibility."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping, Protocol, Sequence

from service.auth import ActorContext, Permission, require_permission

from .contracts import (
    CapabilityState,
    ChannelCandidate,
    ChannelCapability,
    ChannelContribution,
    ExplicitGap,
    FusionPolicy,
    GapKind,
    QueryPlan,
    ReleaseScope,
    RetrievalChannel,
    RetrievalChannelUnavailable,
    RetrievalHit,
    RetrievalNotFoundError,
    RetrievalRequest,
    RetrievalResult,
    RetrievalVisibility,
    RetrievalVisibilityError,
    RevisionDocument,
    RevisionTrace,
)


class RetrievalRepository(Protocol):
    def current_release(self) -> ReleaseScope | None: ...

    def index_version(
        self,
        *,
        visibility: RetrievalVisibility,
        release_scope: ReleaseScope | None,
    ) -> str | None: ...

    def metadata_candidates(
        self,
        request: RetrievalRequest,
        *,
        release_scope: ReleaseScope | None,
    ) -> Sequence[ChannelCandidate]: ...

    def fts_candidates(
        self,
        request: RetrievalRequest,
        *,
        release_scope: ReleaseScope | None,
    ) -> Sequence[ChannelCandidate]: ...

    def relation_candidates(
        self,
        *,
        seed_revision_ids: Sequence[str],
        visibility: RetrievalVisibility,
        release_scope: ReleaseScope | None,
        depth: int,
        limit: int,
    ) -> Sequence[ChannelCandidate]: ...

    def get_revision(
        self,
        *,
        knowledge_revision_id: str,
        visibility: RetrievalVisibility,
        release_scope: ReleaseScope | None,
    ) -> RevisionDocument | None: ...


@dataclass(frozen=True, slots=True)
class VectorProviderStatus:
    state: CapabilityState
    version: str | None
    reason: str | None = None


class VectorCandidateProvider(Protocol):
    def status(self) -> VectorProviderStatus: ...

    def candidates(
        self,
        request: RetrievalRequest,
        *,
        release_scope: ReleaseScope | None,
    ) -> Sequence[ChannelCandidate]: ...


class HybridRetrievalService:
    """Combine explainable candidate channels without hiding degraded capability."""

    def __init__(
        self,
        *,
        repository: RetrievalRepository,
        vector_provider: VectorCandidateProvider | None = None,
        fusion_policy: FusionPolicy | None = None,
    ) -> None:
        self._repository = repository
        self._vector_provider = vector_provider
        self._fusion_policy = fusion_policy or FusionPolicy()

    def search(self, *, actor: ActorContext, request: RetrievalRequest) -> RetrievalResult:
        self._authorize(actor, request.visibility)
        release_scope = self._release_scope(request.visibility)
        if request.visibility is RetrievalVisibility.RELEASED and release_scope is None:
            return self._no_current_release(request)

        capabilities: dict[RetrievalChannel, ChannelCapability] = {}
        gaps: list[ExplicitGap] = []
        warnings: list[str] = []
        channel_results: dict[RetrievalChannel, tuple[ChannelCandidate, ...]] = {}

        self._run_repository_channel(
            RetrievalChannel.METADATA,
            request=request,
            release_scope=release_scope,
            callable_=self._repository.metadata_candidates,
            capabilities=capabilities,
            gaps=gaps,
            channel_results=channel_results,
        )
        self._run_repository_channel(
            RetrievalChannel.FTS,
            request=request,
            release_scope=release_scope,
            callable_=self._repository.fts_candidates,
            capabilities=capabilities,
            gaps=gaps,
            channel_results=channel_results,
        )
        self._run_vector_channel(
            request=request,
            release_scope=release_scope,
            capabilities=capabilities,
            gaps=gaps,
            channel_results=channel_results,
        )

        seed_revision_ids = self._ordered_seed_ids(channel_results)
        self._run_relation_channel(
            request=request,
            release_scope=release_scope,
            seed_revision_ids=seed_revision_ids,
            capabilities=capabilities,
            gaps=gaps,
            channel_results=channel_results,
        )

        hits = self._fuse(
            channel_results,
            visibility=request.visibility,
            limit=request.limit,
        )
        if not hits:
            gaps.append(
                ExplicitGap(
                    code="no_matching_released_knowledge"
                    if request.visibility is RetrievalVisibility.RELEASED
                    else "no_matching_approved_knowledge",
                    kind=GapKind.NO_RESULT,
                    message=(
                        "No governed knowledge matched the query and filters in the selected "
                        "visibility boundary."
                    ),
                )
            )

        ordered_capabilities = tuple(
            capabilities[channel] for channel in self._fusion_policy.channel_priority
        )
        partial = any(
            capability.state is not CapabilityState.AVAILABLE
            for capability in ordered_capabilities
            if not (
                capability.state is CapabilityState.DISABLED
                and capability.reason == "not_requested"
            )
        )
        plan = self._query_plan(
            request,
            release_scope=release_scope,
            capabilities=ordered_capabilities,
        )
        return RetrievalResult(
            plan=plan,
            hits=hits,
            gaps=tuple(gaps),
            partial=partial,
            warnings=tuple(warnings),
        )

    def get_revision(
        self,
        *,
        actor: ActorContext,
        knowledge_revision_id: str,
        visibility: RetrievalVisibility = RetrievalVisibility.RELEASED,
    ) -> RevisionTrace:
        self._authorize(actor, visibility)
        release_scope = self._release_scope(visibility)
        if visibility is RetrievalVisibility.RELEASED and release_scope is None:
            raise RetrievalVisibilityError("there is no current immutable release")
        document = self._repository.get_revision(
            knowledge_revision_id=knowledge_revision_id,
            visibility=visibility,
            release_scope=release_scope,
        )
        if document is None:
            raise RetrievalNotFoundError("knowledge revision was not found in this visibility")
        return RevisionTrace(
            document=document,
            visibility=visibility,
            release_scope=release_scope,
        )

    def _authorize(self, actor: ActorContext, visibility: RetrievalVisibility) -> None:
        if visibility is RetrievalVisibility.RELEASED:
            require_permission(actor, Permission.QUERY_RELEASED)
            return
        require_permission(actor, Permission.EVALUATION_RUN)

    def _release_scope(self, visibility: RetrievalVisibility) -> ReleaseScope | None:
        if visibility is RetrievalVisibility.EVALUATION:
            return None
        return self._repository.current_release()

    def _no_current_release(self, request: RetrievalRequest) -> RetrievalResult:
        capabilities = tuple(
            ChannelCapability(
                channel=channel,
                state=CapabilityState.DISABLED,
                version=None,
                reason="no_current_release",
            )
            for channel in self._fusion_policy.channel_priority
        )
        gap = ExplicitGap(
            code="no_current_release",
            kind=GapKind.VISIBILITY,
            message=(
                "Production retrieval is empty because no immutable release is current; "
                "approved-but-unreleased revisions are not exposed."
            ),
        )
        return RetrievalResult(
            plan=self._query_plan(
                request,
                release_scope=None,
                capabilities=capabilities,
            ),
            hits=(),
            gaps=(gap,),
            partial=True,
        )

    def _run_repository_channel(
        self,
        channel: RetrievalChannel,
        *,
        request: RetrievalRequest,
        release_scope: ReleaseScope | None,
        callable_,
        capabilities: dict[RetrievalChannel, ChannelCapability],
        gaps: list[ExplicitGap],
        channel_results: dict[RetrievalChannel, tuple[ChannelCandidate, ...]],
    ) -> None:
        try:
            candidates = tuple(callable_(request, release_scope=release_scope))
        except RetrievalChannelUnavailable as exc:
            capabilities[channel] = ChannelCapability(
                channel=channel,
                state=CapabilityState.UNAVAILABLE,
                version=None,
                reason=exc.reason,
            )
            channel_results[channel] = ()
            gaps.append(
                ExplicitGap(
                    code=f"{channel.value}_unavailable",
                    kind=GapKind.CAPABILITY,
                    channel=channel,
                    message=f"{channel.value} retrieval is unavailable: {exc.reason}",
                )
            )
            return
        channel_results[channel] = self._stable_channel_order(candidates)
        capabilities[channel] = ChannelCapability(
            channel=channel,
            state=CapabilityState.AVAILABLE,
            version=f"{channel.value}@1.0.0",
            candidate_count=len(candidates),
        )

    def _run_vector_channel(
        self,
        *,
        request: RetrievalRequest,
        release_scope: ReleaseScope | None,
        capabilities: dict[RetrievalChannel, ChannelCapability],
        gaps: list[ExplicitGap],
        channel_results: dict[RetrievalChannel, tuple[ChannelCandidate, ...]],
    ) -> None:
        channel = RetrievalChannel.VECTOR
        if not request.include_vector:
            capabilities[channel] = ChannelCapability(
                channel=channel,
                state=CapabilityState.DISABLED,
                version=None,
                reason="not_requested",
            )
            channel_results[channel] = ()
            return
        if self._vector_provider is None:
            capabilities[channel] = ChannelCapability(
                channel=channel,
                state=CapabilityState.DISABLED,
                version=None,
                reason="embedding_profile_not_configured",
            )
            channel_results[channel] = ()
            gaps.append(
                ExplicitGap(
                    code="vector_disabled",
                    kind=GapKind.CAPABILITY,
                    channel=channel,
                    message=(
                        "Semantic retrieval is disabled because no compliant embedding "
                        "ModelProfile is configured."
                    ),
                )
            )
            return
        status = self._vector_provider.status()
        if status.state is not CapabilityState.AVAILABLE:
            capabilities[channel] = ChannelCapability(
                channel=channel,
                state=status.state,
                version=status.version,
                reason=status.reason,
            )
            channel_results[channel] = ()
            gaps.append(
                ExplicitGap(
                    code=f"vector_{status.state.value}",
                    kind=GapKind.CAPABILITY,
                    channel=channel,
                    message=f"Semantic retrieval is {status.state.value}: {status.reason}.",
                )
            )
            return
        try:
            candidates = tuple(
                self._vector_provider.candidates(
                    request,
                    release_scope=release_scope,
                )
            )
        except RetrievalChannelUnavailable as exc:
            capabilities[channel] = ChannelCapability(
                channel=channel,
                state=CapabilityState.UNAVAILABLE,
                version=status.version,
                reason=exc.reason,
            )
            channel_results[channel] = ()
            gaps.append(
                ExplicitGap(
                    code="vector_unavailable",
                    kind=GapKind.CAPABILITY,
                    channel=channel,
                    message=f"Semantic retrieval is unavailable: {exc.reason}",
                )
            )
            return
        channel_results[channel] = self._stable_channel_order(candidates)
        capabilities[channel] = ChannelCapability(
            channel=channel,
            state=CapabilityState.AVAILABLE,
            version=status.version,
            candidate_count=len(candidates),
        )

    def _run_relation_channel(
        self,
        *,
        request: RetrievalRequest,
        release_scope: ReleaseScope | None,
        seed_revision_ids: Sequence[str],
        capabilities: dict[RetrievalChannel, ChannelCapability],
        gaps: list[ExplicitGap],
        channel_results: dict[RetrievalChannel, tuple[ChannelCandidate, ...]],
    ) -> None:
        channel = RetrievalChannel.RELATION
        if request.relation_depth == 0:
            capabilities[channel] = ChannelCapability(
                channel=channel,
                state=CapabilityState.DISABLED,
                version=None,
                reason="not_requested",
            )
            channel_results[channel] = ()
            return
        if not seed_revision_ids:
            capabilities[channel] = ChannelCapability(
                channel=channel,
                state=CapabilityState.AVAILABLE,
                version="relation@1.0.0",
                reason="no_seed_candidates",
            )
            channel_results[channel] = ()
            return
        try:
            candidates = tuple(
                self._repository.relation_candidates(
                    seed_revision_ids=seed_revision_ids,
                    visibility=request.visibility,
                    release_scope=release_scope,
                    depth=request.relation_depth,
                    limit=max(request.limit * 2, 10),
                )
            )
        except RetrievalChannelUnavailable as exc:
            capabilities[channel] = ChannelCapability(
                channel=channel,
                state=CapabilityState.UNAVAILABLE,
                version=None,
                reason=exc.reason,
            )
            channel_results[channel] = ()
            gaps.append(
                ExplicitGap(
                    code="relation_unavailable",
                    kind=GapKind.CAPABILITY,
                    channel=channel,
                    message=f"Relation expansion is unavailable: {exc.reason}",
                )
            )
            return
        channel_results[channel] = self._stable_channel_order(candidates)
        capabilities[channel] = ChannelCapability(
            channel=channel,
            state=CapabilityState.AVAILABLE,
            version="relation@1.0.0",
            candidate_count=len(candidates),
        )

    def _ordered_seed_ids(
        self,
        channel_results: Mapping[RetrievalChannel, Sequence[ChannelCandidate]],
    ) -> tuple[str, ...]:
        ordered: list[str] = []
        seen: set[str] = set()
        for channel in (
            RetrievalChannel.METADATA,
            RetrievalChannel.FTS,
            RetrievalChannel.VECTOR,
        ):
            for candidate in channel_results.get(channel, ()):
                revision_id = candidate.document.knowledge_revision_id
                if revision_id not in seen:
                    seen.add(revision_id)
                    ordered.append(revision_id)
        return tuple(ordered)

    def _stable_channel_order(
        self,
        candidates: Sequence[ChannelCandidate],
    ) -> tuple[ChannelCandidate, ...]:
        best: dict[str, ChannelCandidate] = {}
        for candidate in candidates:
            revision_id = candidate.document.knowledge_revision_id
            existing = best.get(revision_id)
            if existing is None or candidate.score > existing.score:
                best[revision_id] = candidate
        return tuple(
            sorted(
                best.values(),
                key=lambda item: (
                    -item.score,
                    item.document.stable_key,
                    item.document.knowledge_revision_id,
                ),
            )
        )

    def _fuse(
        self,
        channel_results: Mapping[RetrievalChannel, Sequence[ChannelCandidate]],
        *,
        visibility: RetrievalVisibility,
        limit: int,
    ) -> tuple[RetrievalHit, ...]:
        documents: dict[str, RevisionDocument] = {}
        contributions: dict[str, list[ChannelContribution]] = {}
        relation_paths: dict[str, set[tuple[str, ...]]] = {}
        totals: dict[str, float] = {}

        for channel in self._fusion_policy.channel_priority:
            weight = self._fusion_policy.channel_weights[channel]
            for rank, candidate in enumerate(channel_results.get(channel, ()), start=1):
                revision_id = candidate.document.knowledge_revision_id
                contribution = weight / (self._fusion_policy.rank_constant + rank)
                documents[revision_id] = candidate.document
                totals[revision_id] = totals.get(revision_id, 0.0) + contribution
                contributions.setdefault(revision_id, []).append(
                    ChannelContribution(
                        channel=channel,
                        rank=rank,
                        raw_score=candidate.score,
                        fusion_score=contribution,
                    )
                )
                relation_paths.setdefault(revision_id, set()).update(
                    candidate.relation_paths
                )

        ordered_ids = sorted(
            documents,
            key=lambda revision_id: (
                -totals[revision_id],
                documents[revision_id].stable_key,
                revision_id,
            ),
        )[:limit]
        hits: list[RetrievalHit] = []
        priority = {
            channel: index
            for index, channel in enumerate(self._fusion_policy.channel_priority)
        }
        for rank, revision_id in enumerate(ordered_ids, start=1):
            document = documents[revision_id]
            hits.append(
                RetrievalHit(
                    knowledge_unit_id=document.knowledge_unit_id,
                    stable_key=document.stable_key,
                    knowledge_type=document.knowledge_type,
                    knowledge_revision_id=document.knowledge_revision_id,
                    revision_number=document.revision_number,
                    visibility=visibility,
                    release_ids=document.release_ids,
                    claim=document.claim,
                    scope=document.scope,
                    applicability=document.applicability,
                    final_score=totals[revision_id],
                    rank=rank,
                    channel_contributions=tuple(
                        sorted(
                            contributions[revision_id],
                            key=lambda item: priority[item.channel],
                        )
                    ),
                    relation_paths=tuple(sorted(relation_paths[revision_id])),
                    citations=document.citations,
                )
            )
        return tuple(hits)

    def _query_plan(
        self,
        request: RetrievalRequest,
        *,
        release_scope: ReleaseScope | None,
        capabilities: tuple[ChannelCapability, ...],
    ) -> QueryPlan:
        index_version = self._repository.index_version(
            visibility=request.visibility,
            release_scope=release_scope,
        )
        facts = {
            "query": request.query.casefold(),
            "visibility": request.visibility.value,
            "filters": {
                "knowledge_types": list(request.filters.knowledge_types),
                "scope": dict(sorted(request.filters.scope.items())),
                "source_version_ids": list(request.filters.source_version_ids),
                "rights_classifications": list(request.filters.rights_classifications),
            },
            "limit": request.limit,
            "relation_depth": request.relation_depth,
            "include_vector": request.include_vector,
            "release_id": release_scope.release_id if release_scope else None,
            "index_version": index_version,
            "policy_version": self._fusion_policy.version,
        }
        query_id = "query-" + sha256(
            json.dumps(facts, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:32]
        return QueryPlan(
            query_id=query_id,
            normalized_query=request.query,
            visibility=request.visibility,
            release_scope=release_scope,
            policy_version=self._fusion_policy.version,
            requested_limit=request.limit,
            relation_depth=request.relation_depth,
            channels=capabilities,
            index_version=index_version,
        )
