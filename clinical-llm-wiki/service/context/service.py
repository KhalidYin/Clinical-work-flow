"""Deterministic context builder; no LLM or hidden retrieval is invoked here."""

from __future__ import annotations

from hashlib import sha256

from service.retrieval import RetrievalResult

from .contracts import ContextItem, ContextPackage


class ContextPackageBuilder:
    def build(
        self,
        result: RetrievalResult,
        *,
        max_hits: int = 8,
        max_characters: int = 12_000,
    ) -> ContextPackage:
        if not 1 <= max_hits <= 50:
            raise ValueError("context max_hits must be between 1 and 50")
        if not 500 <= max_characters <= 100_000:
            raise ValueError("context max_characters must be between 500 and 100000")

        items: list[ContextItem] = []
        sections: list[str] = []
        truncated = len(result.hits) > max_hits
        used = 0
        for hit in result.hits[:max_hits]:
            citations = tuple(hit.citations)
            citation_lines = [
                (
                    f"- [{citation.evidence_id}] {citation.source_title} "
                    f"{citation.source_version} · locator={dict(citation.locator)} "
                    f"· sha256={citation.content_sha256}"
                )
                for citation in citations
            ]
            section = "\n".join(
                (
                    f"## {hit.rank}. {hit.stable_key}",
                    hit.claim,
                    "Citations:",
                    *citation_lines,
                )
            )
            separator = 2 if sections else 0
            remaining = max_characters - used - separator
            if remaining <= 0:
                truncated = True
                break
            if len(section) > remaining:
                truncated = True
                section = section[:remaining].rstrip()
            items.append(
                ContextItem(
                    knowledge_revision_id=hit.knowledge_revision_id,
                    stable_key=hit.stable_key,
                    claim=hit.claim,
                    rank=hit.rank,
                    citations=citations,
                )
            )
            sections.append(section)
            used += len(section) + separator
            if used >= max_characters:
                break

        rendered = "\n\n".join(sections)
        context_id = "context-" + sha256(
            (
                f"{result.plan.query_id}\n{max_hits}\n{max_characters}\n"
                f"{','.join(item.knowledge_revision_id for item in items)}\n"
                f"{sha256(rendered.encode('utf-8')).hexdigest()}"
            ).encode("utf-8")
        ).hexdigest()[:32]
        return ContextPackage(
            context_id=context_id,
            query_plan=result.plan,
            visibility=result.plan.visibility,
            items=tuple(items),
            gaps=result.gaps,
            rendered_text=rendered,
            truncated=truncated,
            partial=result.partial or truncated,
            max_characters=max_characters,
        )
