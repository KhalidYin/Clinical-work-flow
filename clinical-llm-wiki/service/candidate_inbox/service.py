"""Candidate inbox contracts and persistence without knowledge promotion side effects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Mapping, Protocol
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from service.auth import ActorContext, Permission, require_permission
from service.db.models import AuditEvent, CandidateSubmission


class CandidateSubmissionType(str, Enum):
    CORRECTION = "correction"
    OBSERVATION = "observation"
    RULE_GAP = "rule_gap"
    PROPOSED_RULE = "proposed_rule"


@dataclass(frozen=True, slots=True)
class CandidateSubmissionCommand:
    submission_type: CandidateSubmissionType
    origin_system: str
    origin_record_ref: str
    summary: str
    proposed_claim: str | None
    scope: Mapping[str, str]
    source_references: tuple[str, ...]
    deidentified: bool
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class CandidateSubmissionReceipt:
    submission_id: str
    status: str
    payload_sha256: str
    duplicate: bool
    created_at: datetime


class UnsafeCandidatePayloadError(ValueError):
    """The handoff does not meet the bounded de-identification contract."""


class CandidateInboxRepository(Protocol):
    def save(
        self,
        *,
        actor: ActorContext,
        command: CandidateSubmissionCommand,
        payload: Mapping[str, object],
        payload_sha256: str,
    ) -> CandidateSubmissionReceipt: ...


class CandidateSubmissionService:
    """Accept a candidate handoff; never create or mutate governed knowledge."""

    _forbidden_scope_keys = frozenset(
        {
            "patient",
            "patient_id",
            "subject",
            "subject_id",
            "usubjid",
            "mrn",
            "name",
            "email",
        }
    )

    def __init__(self, *, repository: CandidateInboxRepository) -> None:
        self._repository = repository

    def submit(
        self,
        *,
        actor: ActorContext,
        command: CandidateSubmissionCommand,
    ) -> CandidateSubmissionReceipt:
        require_permission(actor, Permission.CANDIDATE_SUBMIT)
        self._validate(command)
        payload: dict[str, object] = {
            "schema_version": "1.0.0",
            "summary": command.summary.strip(),
            "proposed_claim": (
                command.proposed_claim.strip() if command.proposed_claim else None
            ),
            "scope": dict(sorted(command.scope.items())),
            "source_references": sorted(set(command.source_references)),
            "deidentified": True,
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return self._repository.save(
            actor=actor,
            command=command,
            payload=payload,
            payload_sha256=sha256(canonical.encode("utf-8")).hexdigest(),
        )

    def _validate(self, command: CandidateSubmissionCommand) -> None:
        if not command.deidentified:
            raise UnsafeCandidatePayloadError(
                "candidate submission requires an explicit de-identification attestation"
            )
        if not command.origin_system.strip() or not command.origin_record_ref.strip():
            raise UnsafeCandidatePayloadError("origin system and opaque record ref are required")
        if not command.summary.strip():
            raise UnsafeCandidatePayloadError("candidate summary is required")
        forbidden = {
            key.strip().lower()
            for key in command.scope
            if key.strip().lower() in self._forbidden_scope_keys
        }
        if forbidden:
            names = ", ".join(sorted(forbidden))
            raise UnsafeCandidatePayloadError(
                f"candidate scope contains forbidden identity key(s): {names}"
            )
        if len(command.idempotency_key.strip()) < 8:
            raise UnsafeCandidatePayloadError("idempotency key must contain at least 8 characters")


class SqlAlchemyCandidateInboxRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def save(
        self,
        *,
        actor: ActorContext,
        command: CandidateSubmissionCommand,
        payload: Mapping[str, object],
        payload_sha256: str,
    ) -> CandidateSubmissionReceipt:
        with self._sessions.begin() as session:
            existing = session.scalar(
                select(CandidateSubmission).where(
                    CandidateSubmission.submitted_by_actor_id == actor.actor_id,
                    CandidateSubmission.idempotency_key == command.idempotency_key,
                )
            )
            if existing is not None:
                return _receipt(existing, duplicate=True)

            submission_id = f"submission-{uuid4()}"
            created_at = datetime.now(timezone.utc)
            submission = CandidateSubmission(
                submission_id=submission_id,
                submitted_by_actor_id=actor.actor_id,
                submission_type=command.submission_type.value,
                origin_system=command.origin_system.strip(),
                origin_record_ref=command.origin_record_ref.strip(),
                payload=dict(payload),
                payload_sha256=payload_sha256,
                idempotency_key=command.idempotency_key.strip(),
                status="received",
                created_at=created_at,
            )
            session.add(submission)
            session.add(
                AuditEvent(
                    audit_event_id=f"audit-{uuid4()}",
                    actor_subject=actor.actor_id,
                    action="candidate_submission.received",
                    entity_type="candidate_submission",
                    entity_id=submission_id,
                    run_id=None,
                    details={
                        "submission_type": command.submission_type.value,
                        "origin_system": command.origin_system.strip(),
                        "payload_sha256": payload_sha256,
                    },
                    created_at=created_at,
                )
            )
            session.flush()
            return _receipt(submission, duplicate=False)


def _receipt(
    submission: CandidateSubmission,
    *,
    duplicate: bool,
) -> CandidateSubmissionReceipt:
    return CandidateSubmissionReceipt(
        submission_id=submission.submission_id,
        status=submission.status,
        payload_sha256=submission.payload_sha256,
        duplicate=duplicate,
        created_at=submission.created_at,
    )
