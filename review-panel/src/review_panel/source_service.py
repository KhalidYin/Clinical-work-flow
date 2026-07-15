from __future__ import annotations

from dataclasses import dataclass

from review_panel.errors import PathForbiddenError, ReviewNotFoundError
from review_panel.repository import ReviewRepository, resolve_declared_source


@dataclass(frozen=True)
class SourceService:
    repository: ReviewRepository
    max_preview_bytes: int = 64_000

    def preview_source(self, queue_id: str, review_id: str, source_index: int) -> dict[str, object]:
        detail = self.repository.get_detail(queue_id, review_id)
        packet = detail["packet"]
        source_documents = packet["source_documents"]
        if source_index < 0 or source_index >= len(source_documents):
            raise ReviewNotFoundError(f"Source index not declared: {source_index}")

        queue = self.repository._require_queue(queue_id)
        declared = source_documents[source_index]
        try:
            path = resolve_declared_source(queue, declared)
        except ValueError as exc:
            if str(exc) == "path_forbidden":
                raise PathForbiddenError("Source path escapes queue owner root.") from exc
            raise ReviewNotFoundError(f"Source file not found: {source_index}") from exc

        data = path.read_bytes()
        truncated = len(data) > self.max_preview_bytes
        preview = data[: self.max_preview_bytes]
        content = preview.decode("utf-8", errors="replace")
        return {
            "queue_id": queue_id,
            "review_id": review_id,
            "source_index": source_index,
            "declared_path": declared,
            "content": content,
            "truncated": truncated,
            "bytes_read": len(preview),
        }

