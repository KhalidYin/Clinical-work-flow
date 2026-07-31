"""Contracts for deterministic LLM context packages built from governed hits."""

from __future__ import annotations

from dataclasses import dataclass

from service.retrieval import Citation, ExplicitGap, QueryPlan, RetrievalVisibility


@dataclass(frozen=True, slots=True)
class ContextItem:
    knowledge_revision_id: str
    stable_key: str
    claim: str
    rank: int
    citations: tuple[Citation, ...]


@dataclass(frozen=True, slots=True)
class ContextPackage:
    context_id: str
    query_plan: QueryPlan
    visibility: RetrievalVisibility
    items: tuple[ContextItem, ...]
    gaps: tuple[ExplicitGap, ...]
    rendered_text: str
    truncated: bool
    partial: bool
    max_characters: int
