from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from review_panel.errors import (
    ReceiptExistsError,
    ReviewConflictError,
    ReviewValidationError,
)
from review_panel.repository import ReviewRepository
from review_panel.schema_loader import file_sha256


@dataclass(frozen=True)
class DecisionService:
    repository: ReviewRepository

    def submit_decision(
        self,
        queue_id: str,
        review_id: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        queue = self.repository._require_queue(queue_id)
        packet_path = self.repository.packet_path(queue, review_id)
        packet = self.repository._load_valid_packet(packet_path)
        current_hash = file_sha256(packet_path)
        if request.get("packet_sha256") != current_hash:
            raise ReviewConflictError("ReviewPacket changed; reload before submitting.")

        receipt = self._build_receipt(review_id, packet, request)
        self._validate_finding_coverage(packet, receipt)
        self.repository.schema.require_valid("decision_receipt", receipt)
        target = self._target_receipt_path(queue.queue_path, review_id, receipt.get("reviewer_role"))
        self._write_json_exclusive(target, receipt)
        return {
            "ok": True,
            "queue_id": queue_id,
            "review_id": review_id,
            "receipt_file": target.name,
            "packet_sha256": current_hash,
        }

    def _build_receipt(
        self,
        review_id: str,
        packet: dict[str, Any],
        request: dict[str, Any],
    ) -> dict[str, Any]:
        if request.get("review_id") not in (None, review_id):
            raise ReviewValidationError("Request review_id does not match route review_id.")
        reviewer = request.get("reviewer")
        if not isinstance(reviewer, str) or len(reviewer.strip()) < 2:
            raise ReviewValidationError("reviewer must contain at least 2 characters.")
        decisions = request.get("decisions")
        if not isinstance(decisions, list):
            raise ReviewValidationError("decisions must be a list.")

        receipt: dict[str, Any] = {
            "review_id": review_id,
            "reviewer": reviewer.strip(),
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "decisions": decisions,
        }
        reviewer_role = self._validate_reviewer_role(packet, request.get("reviewer_role"))
        if reviewer_role:
            receipt["reviewer_role"] = reviewer_role
        general_notes = request.get("general_notes")
        if general_notes:
            receipt["general_notes"] = str(general_notes)
        return receipt

    def _validate_reviewer_role(
        self,
        packet: dict[str, Any],
        reviewer_role: Any,
    ) -> str | None:
        required_reviewers = packet.get("required_reviewers") or []
        if not required_reviewers:
            if reviewer_role:
                raise ReviewValidationError("reviewer_role is only allowed for assigned reviews.")
            return None
        if not isinstance(reviewer_role, str) or not reviewer_role:
            raise ReviewValidationError("reviewer_role is required for assigned reviews.")
        allowed_roles = {item["role"] for item in required_reviewers}
        if reviewer_role not in allowed_roles:
            raise ReviewValidationError(f"reviewer_role must be one of {sorted(allowed_roles)}.")
        return reviewer_role

    def _validate_finding_coverage(
        self,
        packet: dict[str, Any],
        receipt: dict[str, Any],
    ) -> None:
        actionable_ids = {
            finding["id"] for finding in packet["findings"] if not finding.get("auto_approved", False)
        }
        decision_ids = [decision.get("finding_id") for decision in receipt["decisions"]]
        if len(decision_ids) != len(set(decision_ids)):
            raise ReviewValidationError("Duplicate finding decisions are not allowed.")
        decision_id_set = set(decision_ids)
        if decision_id_set != actionable_ids:
            missing = sorted(actionable_ids - decision_id_set)
            extra = sorted(decision_id_set - actionable_ids)
            raise ReviewValidationError(
                f"Decision coverage mismatch. missing={missing}; extra={extra}"
            )

    def _target_receipt_path(
        self,
        queue_path: Path,
        review_id: str,
        reviewer_role: str | None,
    ) -> Path:
        if reviewer_role:
            return queue_path / f"{review_id}_decision_{_safe_role(reviewer_role)}.json"
        return queue_path / f"{review_id}_decision.json"

    def _write_json_exclusive(self, target: Path, payload: dict[str, Any]) -> None:
        if target.exists():
            raise ReceiptExistsError()
        data = (json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                "wb",
                dir=target.parent,
                prefix=f".{target.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_name = handle.name
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temp_name, target)
            except FileExistsError as exc:
                raise ReceiptExistsError() from exc
        except ReceiptExistsError:
            raise
        except OSError as exc:
            raise ReviewValidationError(f"Could not write DecisionReceipt: {exc}") from exc
        finally:
            if temp_name:
                try:
                    os.unlink(temp_name)
                except FileNotFoundError:
                    pass


def _safe_role(role: str) -> str:
    safe = re.sub(r"[^a-z0-9_]+", "_", role.lower()).strip("_")
    if not safe:
        raise ReviewValidationError("reviewer_role must contain a file-safe value.")
    return safe

