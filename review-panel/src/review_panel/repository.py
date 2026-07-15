from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from review_panel.config import ReviewPanelConfig
from review_panel.contracts import QueueRegistration, derive_review_status
from review_panel.errors import QueueNotFoundError, ReviewNotFoundError, ReviewValidationError
from review_panel.queue_registry import QueueRegistry, QueueRegistryError, UnknownQueueError
from review_panel.schema_loader import (
    LoadedReviewSchema,
    ReviewSchemaError,
    file_sha256,
    read_json_file,
)


PACKET_EXCLUDED_SUFFIXES = (
    "_decision.json",
    "_confirmation.json",
    "_rework.json",
    "_conflict.json",
    "_corrupt.json",
)


@dataclass(frozen=True)
class ReviewRepository:
    config: ReviewPanelConfig
    registry: QueueRegistry
    schema: LoadedReviewSchema

    def health(self) -> dict[str, Any]:
        queues = self._discover_queues_with_errors()
        return {
            "ok": True,
            "local_only": True,
            "bind_host": self.config.bind_host,
            "schema_id": self.schema.schema.get("$id"),
            "queue_count": len(queues["queues"]),
            "partial": bool(queues["errors"]),
        }

    def list_reviews(self) -> dict[str, Any]:
        discovered = self._discover_queues_with_errors()
        reviews: list[dict[str, Any]] = []
        errors = list(discovered["errors"])
        for queue in discovered["queues"]:
            try:
                queue_reviews, queue_errors = self._list_queue_reviews(queue)
            except Exception as exc:
                errors.append(
                    {
                        "queue_id": queue.queue_id,
                        "code": "queue_invalid",
                        "message": str(exc),
                    }
                )
                continue
            reviews.extend(queue_reviews)
            errors.extend(queue_errors)

        reviews.sort(
            key=lambda item: (
                0 if item["urgency"] == "blocking" else 1,
                item["created_at"],
                item["queue_id"],
                item["review_id"],
            )
        )
        return {
            "ok": True,
            "partial": bool(errors),
            "queues": [queue.to_public_dict() for queue in discovered["queues"]],
            "reviews": reviews,
            "errors": errors,
        }

    def get_detail(self, queue_id: str, review_id: str) -> dict[str, Any]:
        queue = self._require_queue(queue_id)
        packet_path = self.packet_path(queue, review_id)
        packet = self._load_valid_packet(packet_path)
        receipts, receipt_errors = self._load_receipts(queue, review_id)
        confirmation, confirmation_error = self._load_confirmation(queue, review_id)
        errors = receipt_errors + ([confirmation_error] if confirmation_error else [])
        return {
            "queue": queue.to_public_dict(),
            "queue_id": queue.queue_id,
            "review_id": review_id,
            "packet_sha256": file_sha256(packet_path),
            "status": derive_review_status(
                packet_valid=True,
                partial_errors=bool(errors),
                decision_receipt_count=len(receipts),
                confirmation_present=confirmation is not None,
            ).value,
            "packet": packet,
            "source_availability": self.source_availability(queue, packet),
            "decision_receipts": receipts,
            "confirmation_receipt": confirmation,
            "errors": errors,
        }

    def packet_path(self, queue: QueueRegistration, review_id: str) -> Path:
        if not review_id or "/" in review_id or "\\" in review_id or ".." in review_id:
            raise ReviewNotFoundError("Invalid review_id.")
        path = queue.queue_path / f"{review_id}.json"
        if not path.is_file():
            raise ReviewNotFoundError(f"ReviewPacket not found: {review_id}")
        return path

    def source_availability(
        self,
        queue: QueueRegistration,
        packet: dict[str, Any],
    ) -> list[dict[str, Any]]:
        result = []
        for index, declared in enumerate(packet.get("source_documents", [])):
            available = False
            reason = None
            try:
                source_path = resolve_declared_source(queue, declared)
                available = source_path.is_file()
                if not available:
                    reason = "not_found"
            except ValueError as exc:
                reason = str(exc)
            result.append(
                {
                    "index": index,
                    "declared_path": declared,
                    "available": available,
                    "reason": reason,
                }
            )
        return result

    def _discover_queues_with_errors(self) -> dict[str, Any]:
        try:
            return {"queues": self.registry.discover(), "errors": []}
        except QueueRegistryError as exc:
            return {
                "queues": [],
                "errors": [{"queue_id": None, "code": "queue_invalid", "message": str(exc)}],
            }

    def _require_queue(self, queue_id: str) -> QueueRegistration:
        try:
            return self.registry.require_queue(queue_id)
        except UnknownQueueError as exc:
            raise QueueNotFoundError(str(exc)) from exc
        except QueueRegistryError as exc:
            raise ReviewValidationError(str(exc)) from exc

    def _list_queue_reviews(
        self,
        queue: QueueRegistration,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        reviews: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        for packet_path in sorted(queue.queue_path.glob("*.json")):
            if not _is_packet_file(packet_path):
                continue
            try:
                packet = self._load_valid_packet(packet_path)
            except ReviewValidationError as exc:
                errors.append(
                    {
                        "queue_id": queue.queue_id,
                        "review_id": packet_path.stem,
                        "code": "review_invalid",
                        "message": exc.message,
                    }
                )
                continue
            receipts, receipt_errors = self._load_receipts(queue, packet["review_id"])
            confirmation, confirmation_error = self._load_confirmation(queue, packet["review_id"])
            partial_errors = bool(receipt_errors or confirmation_error)
            reviews.append(
                {
                    "queue_id": queue.queue_id,
                    "queue_kind": queue.queue_kind.value,
                    "review_id": packet["review_id"],
                    "review_type": packet["review_type"],
                    "urgency": packet["urgency"],
                    "created_at": packet["created_at"],
                    "status": derive_review_status(
                        packet_valid=True,
                        partial_errors=partial_errors,
                        decision_receipt_count=len(receipts),
                        confirmation_present=confirmation is not None,
                    ).value,
                    "actionable_findings": _actionable_count(packet),
                    "total_findings": len(packet["findings"]),
                    "auto_approved_count": packet["auto_approved_count"],
                    "agent_summary": packet["agent_summary"],
                }
            )
            errors.extend(receipt_errors)
            if confirmation_error:
                errors.append(confirmation_error)
        return reviews, errors

    def _load_valid_packet(self, packet_path: Path) -> dict[str, Any]:
        try:
            packet = read_json_file(packet_path)
        except ReviewSchemaError as exc:
            raise ReviewValidationError(str(exc)) from exc
        violations = self.schema.validate("review_packet", packet)
        if violations:
            raise ReviewValidationError(
                f"ReviewPacket {packet_path.name} does not satisfy schema: {violations}"
            )
        return packet

    def _load_receipts(
        self,
        queue: QueueRegistration,
        review_id: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        receipts = []
        errors = []
        for path in sorted(queue.queue_path.glob(f"{review_id}_decision*.json")):
            try:
                receipt = read_json_file(path)
                self.schema.require_valid("decision_receipt", receipt)
                receipts.append(receipt)
            except Exception as exc:
                errors.append(
                    {
                        "queue_id": queue.queue_id,
                        "review_id": review_id,
                        "code": "review_invalid",
                        "message": f"Invalid DecisionReceipt {path.name}: {exc}",
                    }
                )
        return receipts, errors

    def _load_confirmation(
        self,
        queue: QueueRegistration,
        review_id: str,
    ) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
        path = queue.queue_path / f"{review_id}_confirmation.json"
        if not path.exists():
            return None, None
        try:
            confirmation = read_json_file(path)
            self.schema.require_valid("confirmation_receipt", confirmation)
            return confirmation, None
        except Exception as exc:
            return None, {
                "queue_id": queue.queue_id,
                "review_id": review_id,
                "code": "review_invalid",
                "message": f"Invalid ConfirmationReceipt {path.name}: {exc}",
            }


def resolve_declared_source(queue: QueueRegistration, declared_path: str) -> Path:
    declared = Path(declared_path)
    candidate = declared if declared.is_absolute() else queue.owner_root / declared
    try:
        resolved = candidate.resolve(strict=True)
        owner = queue.owner_root.resolve(strict=True)
    except OSError as exc:
        raise ValueError("not_found") from exc
    if not resolved.is_relative_to(owner):
        raise ValueError("path_forbidden")
    return resolved


def _is_packet_file(path: Path) -> bool:
    name = path.name
    return (
        name != ".queue_scope.json"
        and not name.startswith(".")
        and not any(name.endswith(suffix) for suffix in PACKET_EXCLUDED_SUFFIXES)
        and "_decision_" not in name
    )


def _actionable_count(packet: dict[str, Any]) -> int:
    return sum(1 for finding in packet["findings"] if not finding.get("auto_approved", False))
