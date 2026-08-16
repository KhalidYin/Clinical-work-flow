"""P17 release-candidate retrieval public API."""

from .contracts import (
    CandidateSearchRecord,
    CapabilityState,
    ChunkExplanation,
    ContextPackage,
    EvidenceCitation,
    ReleaseCandidateScope,
    RetrievalCapabilities,
    RetrievalHit,
    RetrievalQuery,
    RetrievalResult,
    RouteContributions,
    retrieval_query_identity,
)
from .service import CandidateSearchRepositoryPort, FUSION_VERSION, RetrievalService

__all__ = [
    "CandidateSearchRecord",
    "CandidateSearchRepositoryPort",
    "CapabilityState",
    "ChunkExplanation",
    "ContextPackage",
    "EvidenceCitation",
    "FUSION_VERSION",
    "ReleaseCandidateScope",
    "RetrievalCapabilities",
    "RetrievalHit",
    "RetrievalQuery",
    "RetrievalResult",
    "RetrievalService",
    "RouteContributions",
    "retrieval_query_identity",
]
