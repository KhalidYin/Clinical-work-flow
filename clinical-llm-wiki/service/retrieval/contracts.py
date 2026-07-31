"""Provider-neutral contracts for explainable governed retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence


class RetrievalVisibility(str, Enum):
    RELEASED = "released"
    EVALUATION = "evaluation"


class RetrievalChannel(str, Enum):
    METADATA = "metadata"
    FTS = "fts"
    VECTOR = "vector"
    RELATION = "relation"


class CapabilityState(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"


class GapKind(str, Enum):
    VISIBILITY = "visibility"
    CAPABILITY = "capability"
    NO_RESULT = "no_result"
    LIMIT = "limit"
    RIGHTS = "rights"


@dataclass(frozen=True, slots=True)
class RetrievalFilters:
    knowledge_types: tuple[str, ...] = ()
    scope: Mapping[str, str] = field(default_factory=dict)
    source_version_ids: tuple[str, ...] = ()
    rights_classifications: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    query: str
    visibility: RetrievalVisibility = RetrievalVisibility.RELEASED
    filters: RetrievalFilters = field(default_factory=RetrievalFilters)
    limit: int = 10
    relation_depth: int = 1
    include_vector: bool = True

    def __post_init__(self) -> None:
        normalized = self.query.strip()
        if not normalized:
            raise ValueError("retrieval query must not be empty")
        if len(normalized) > 2000:
            raise ValueError("retrieval query exceeds 2000 characters")
        if not 1 <= self.limit <= 50:
            raise ValueError("retrieval limit must be between 1 and 50")
        if not 0 <= self.relation_depth <= 2:
            raise ValueError("relation depth must be between 0 and 2")
        object.__setattr__(self, "query", normalized)


@dataclass(frozen=True, slots=True)
class ReleaseScope:
    release_id: str
    version: str
    index_version: str


@dataclass(frozen=True, slots=True)
class Citation:
    evidence_id: str
    source_id: str
    source_title: str
    source_version_id: str
    source_version: str
    locator: Mapping[str, object]
    content_sha256: str
    source_sha256: str
    rights_classification: str
    citation_required: bool


@dataclass(frozen=True, slots=True)
class RevisionDocument:
    knowledge_unit_id: str
    stable_key: str
    knowledge_type: str
    knowledge_revision_id: str
    revision_number: int
    revision_status: str
    claim: str
    scope: Mapping[str, object]
    applicability: Mapping[str, object]
    conditions: tuple[Mapping[str, object], ...]
    exceptions: tuple[Mapping[str, object], ...]
    content_sha256: str
    release_ids: tuple[str, ...]
    citations: tuple[Citation, ...]


@dataclass(frozen=True, slots=True)
class ChannelCandidate:
    document: RevisionDocument
    score: float
    relation_paths: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True, slots=True)
class ChannelCapability:
    channel: RetrievalChannel
    state: CapabilityState
    version: str | None
    reason: str | None = None
    candidate_count: int = 0


@dataclass(frozen=True, slots=True)
class ChannelContribution:
    channel: RetrievalChannel
    rank: int
    raw_score: float
    fusion_score: float


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    knowledge_unit_id: str
    stable_key: str
    knowledge_type: str
    knowledge_revision_id: str
    revision_number: int
    visibility: RetrievalVisibility
    release_ids: tuple[str, ...]
    claim: str
    scope: Mapping[str, object]
    applicability: Mapping[str, object]
    final_score: float
    rank: int
    channel_contributions: tuple[ChannelContribution, ...]
    relation_paths: tuple[tuple[str, ...], ...]
    citations: tuple[Citation, ...]


@dataclass(frozen=True, slots=True)
class ExplicitGap:
    code: str
    kind: GapKind
    message: str
    channel: RetrievalChannel | None = None


@dataclass(frozen=True, slots=True)
class FusionPolicy:
    version: str = "rrf-neutral@1.0.0"
    rank_constant: int = 60
    channel_weights: Mapping[RetrievalChannel, float] = field(
        default_factory=lambda: {
            RetrievalChannel.METADATA: 1.0,
            RetrievalChannel.FTS: 1.0,
            RetrievalChannel.VECTOR: 1.0,
            RetrievalChannel.RELATION: 1.0,
        }
    )
    channel_priority: tuple[RetrievalChannel, ...] = (
        RetrievalChannel.METADATA,
        RetrievalChannel.FTS,
        RetrievalChannel.VECTOR,
        RetrievalChannel.RELATION,
    )

    def __post_init__(self) -> None:
        if self.rank_constant < 1:
            raise ValueError("fusion rank constant must be positive")
        if set(self.channel_weights) != set(RetrievalChannel):
            raise ValueError("fusion policy must define every retrieval channel")
        if any(weight < 0 for weight in self.channel_weights.values()):
            raise ValueError("fusion channel weights must be non-negative")
        if set(self.channel_priority) != set(RetrievalChannel):
            raise ValueError("fusion priority must include every retrieval channel exactly once")


@dataclass(frozen=True, slots=True)
class QueryPlan:
    query_id: str
    normalized_query: str
    visibility: RetrievalVisibility
    release_scope: ReleaseScope | None
    policy_version: str
    requested_limit: int
    relation_depth: int
    channels: tuple[ChannelCapability, ...]
    index_version: str | None


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    plan: QueryPlan
    hits: tuple[RetrievalHit, ...]
    gaps: tuple[ExplicitGap, ...]
    partial: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RevisionTrace:
    document: RevisionDocument
    visibility: RetrievalVisibility
    release_scope: ReleaseScope | None


class RetrievalChannelUnavailable(RuntimeError):
    """Raised by one channel without converting the whole query into a false success."""

    def __init__(self, channel: RetrievalChannel, *, reason: str) -> None:
        super().__init__(reason)
        self.channel = channel
        self.reason = reason


class RetrievalVisibilityError(RuntimeError):
    """Raised when a requested revision is not visible in the selected boundary."""


class RetrievalNotFoundError(RuntimeError):
    """Raised when a requested governed revision does not exist."""


class RetrievalRepositoryPort:
    """Structural documentation for retrieval repositories.

    Concrete ports use ``typing.Protocol`` in ``service.py`` so runtime adapters do not
    inherit framework classes.
    """

    def current_release(self) -> ReleaseScope | None:  # pragma: no cover - documentation
        raise NotImplementedError

    def metadata_candidates(  # pragma: no cover - documentation
        self,
        request: RetrievalRequest,
        *,
        release_scope: ReleaseScope | None,
    ) -> Sequence[ChannelCandidate]:
        raise NotImplementedError
