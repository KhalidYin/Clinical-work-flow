"""Evidence-to-Candidate enrichment worker with deterministic fake/replay support."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Callable, Mapping, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from service.auth import ActorContext, Permission, WorkerPool, require_permission
from service.db.models import (
    AuditEvent,
    Evidence,
    ModelInvocation as ModelInvocationRow,
    ModelProfile as ModelProfileRow,
    ProcessingRun,
    PromptProfile as PromptProfileRow,
    SourceVersion,
)
from service.governance import KnowledgeGovernanceService
from service.knowledge import (
    EvidenceReference,
    KnowledgeCandidateDraft,
    RelationProposal,
)

from .contracts import ArtifactManifest, ClaimedStepAttempt, StepDefinition, StepOutcome
from .model_provider import (
    DataBoundary,
    FakeModelProvider,
    ModelInvocation,
    ModelProfile,
    ModelProviderError,
    ModelProviderPort,
    ModelRequest,
    PromptProfile,
    ReplayModelProvider,
    StepAttemptContext,
)


ENRICHMENT_STEP_KEY = "enrichment.extract_candidate"
ENRICHMENT_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "candidate_group_id",
        "knowledge_type",
        "claim",
        "scope",
        "applicability",
        "conditions",
        "exceptions",
        "evidence_ids",
        "relation_proposals",
        "confidence",
    ],
    "properties": {
        "candidate_group_id": {"type": "string", "minLength": 1},
        "knowledge_type": {"type": "string", "minLength": 1},
        "claim": {"type": "string", "minLength": 1},
        "scope": {"type": "object", "minProperties": 1},
        "applicability": {"type": "object", "minProperties": 1},
        "conditions": {"type": "array", "items": {"type": "object"}},
        "exceptions": {"type": "array", "items": {"type": "object"}},
        "evidence_ids": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
        },
        "relation_proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "relation_type",
                    "target_knowledge_unit_id",
                    "evidence_ids",
                ],
                "properties": {
                    "relation_type": {
                        "enum": [
                            "applies_to",
                            "conflicts_with",
                            "depends_on",
                            "derived_from",
                            "supersedes",
                            "supports",
                            "used_by",
                        ]
                    },
                    "target_knowledge_unit_id": {"type": "string", "minLength": 1},
                    "evidence_ids": {
                        "type": "array",
                        "minItems": 1,
                        "uniqueItems": True,
                        "items": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
        "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
    },
}


@dataclass(frozen=True, slots=True)
class EnrichmentEvidence:
    reference: EvidenceReference
    content: str


@dataclass(frozen=True, slots=True)
class EnrichmentContext:
    run_id: str
    source_version_id: str
    data_boundary: DataBoundary
    evidence: tuple[EnrichmentEvidence, ...]


class EnrichmentRepositoryPort(Protocol):
    def load_context(self, *, run_id: str) -> EnrichmentContext: ...

    def record_invocation(self, *, actor_id: str, invocation: ModelInvocation) -> None: ...


class InMemoryEnrichmentRepository:
    def __init__(self, *, contexts: Mapping[str, EnrichmentContext]) -> None:
        self._contexts = dict(contexts)
        self.invocations: list[ModelInvocation] = []

    def load_context(self, *, run_id: str) -> EnrichmentContext:
        try:
            return self._contexts[run_id]
        except KeyError as exc:
            raise ValueError("run has no canonical evidence context") from exc

    def record_invocation(self, *, actor_id: str, invocation: ModelInvocation) -> None:
        del actor_id
        self.invocations.append(invocation)


class SqlAlchemyEnrichmentRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def load_context(self, *, run_id: str) -> EnrichmentContext:
        with self._sessions() as session:
            row = session.execute(
                select(ProcessingRun, SourceVersion)
                .join(
                    SourceVersion,
                    SourceVersion.source_version_id == ProcessingRun.source_version_id,
                )
                .where(ProcessingRun.run_id == run_id)
            ).one_or_none()
            if row is None:
                raise ValueError("run has no source version")
            run, version = row
            evidence_rows = tuple(
                session.scalars(
                    select(Evidence)
                    .where(Evidence.source_version_id == version.source_version_id)
                    .order_by(Evidence.evidence_id)
                )
            )
        if not evidence_rows:
            raise ValueError("run has no canonical evidence")
        rights = version.rights
        if not isinstance(rights, dict):
            raise ValueError("source version has no rights facts")
        return EnrichmentContext(
            run_id=run.run_id,
            source_version_id=version.source_version_id,
            data_boundary=DataBoundary(version.data_boundary),
            evidence=tuple(
                EnrichmentEvidence(
                    reference=EvidenceReference(
                        evidence_id=evidence.evidence_id,
                        source_version_id=evidence.source_version_id,
                        locator=evidence.locator,
                        content_sha256=evidence.content_sha256,
                        rights=rights,
                    ),
                    content=evidence.content,
                )
                for evidence in evidence_rows
            ),
        )

    def record_invocation(self, *, actor_id: str, invocation: ModelInvocation) -> None:
        with self._sessions.begin() as session:
            if session.get(ModelInvocationRow, invocation.invocation_id) is not None:
                return
            session.add(
                ModelInvocationRow(
                    invocation_id=invocation.invocation_id,
                    run_id=invocation.attempt.run_id,
                    step_id=invocation.attempt.step_id,
                    attempt_id=invocation.attempt.attempt_id,
                    attempt_number=invocation.attempt.attempt_number,
                    previous_attempt_id=invocation.attempt.previous_attempt_id,
                    status=invocation.status.value,
                    model_profile_id=invocation.model_profile_id,
                    model_profile_version=invocation.model_profile_version,
                    provider=invocation.provider,
                    model=invocation.model,
                    prompt_profile_id=invocation.prompt_profile_id,
                    prompt_profile_version=invocation.prompt_profile_version,
                    output_schema_sha256=invocation.output_schema_sha256,
                    data_boundary=invocation.data_boundary.value,
                    input_sha256=invocation.input_sha256,
                    output_sha256=invocation.output_sha256,
                    provider_request_id=invocation.provider_request_id,
                    prompt_tokens=invocation.token_usage.prompt_tokens,
                    completion_tokens=invocation.token_usage.completion_tokens,
                    total_tokens=invocation.token_usage.total_tokens,
                    cost_usd=invocation.cost_usd,
                    latency_ms=invocation.latency_ms,
                    output=invocation.output,
                    error_type=(
                        invocation.error_type.value if invocation.error_type is not None else None
                    ),
                    error_message=invocation.error_message,
                    created_at=invocation.created_at,
                )
            )
            session.add(
                AuditEvent(
                    audit_event_id=f"audit-{invocation.invocation_id}",
                    actor_subject=actor_id,
                    action=f"model.invocation.{invocation.status.value}",
                    entity_type="model_invocation",
                    entity_id=invocation.invocation_id,
                    run_id=invocation.attempt.run_id,
                    details={
                        "permission": Permission.MODEL_INVOKE.value,
                        "correlation_id": invocation.attempt.attempt_id,
                        "attempt_number": invocation.attempt.attempt_number,
                        "input_sha256": invocation.input_sha256,
                        "output_sha256": invocation.output_sha256,
                        "result": invocation.status.value,
                    },
                )
            )


class EnrichmentWorkerService:
    def __init__(
        self,
        *,
        repository: EnrichmentRepositoryPort,
        governance: KnowledgeGovernanceService,
        provider: ModelProviderPort,
        model_profile: ModelProfile,
        prompt_profile: PromptProfile,
        actor: ActorContext,
    ) -> None:
        require_permission(actor, Permission.MODEL_INVOKE)
        require_permission(actor, Permission.CANDIDATE_WRITE)
        if actor.worker_pool is not WorkerPool.ENRICHMENT:
            raise PermissionError("enrichment service requires the enrichment worker")
        self._repository = repository
        self._governance = governance
        self._provider = provider
        self._model_profile = model_profile
        self._prompt_profile = prompt_profile
        self._actor = actor

    def extract_candidate(self, claim: ClaimedStepAttempt) -> StepOutcome:
        source = self._repository.load_context(run_id=claim.run_id)
        request = ModelRequest(
            attempt=StepAttemptContext(
                run_id=claim.run_id,
                step_id=claim.step_id,
                attempt_id=claim.attempt_id,
                attempt_number=claim.attempt_number,
                previous_attempt_id=claim.previous_attempt_id,
            ),
            model_profile=self._model_profile,
            prompt_profile=self._prompt_profile,
            data_boundary=source.data_boundary,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "source_version_id": source.source_version_id,
                            "evidence": [
                                {
                                    "evidence_id": item.reference.evidence_id,
                                    "locator": item.reference.locator,
                                    "content_sha256": item.reference.content_sha256,
                                    "content": item.content,
                                }
                                for item in source.evidence
                            ],
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            ],
        )
        try:
            invocation = self._provider.invoke(request)
        except ModelProviderError as exc:
            self._repository.record_invocation(
                actor_id=self._actor.actor_id,
                invocation=exc.invocation,
            )
            raise
        self._repository.record_invocation(
            actor_id=self._actor.actor_id,
            invocation=invocation,
        )
        output = invocation.output
        if output is None:
            raise ValueError("successful model invocation has no output")
        reference_by_id = {
            item.reference.evidence_id: item.reference for item in source.evidence
        }
        try:
            references = tuple(reference_by_id[item] for item in output["evidence_ids"])
        except KeyError as exc:
            raise ValueError("model output cites unknown evidence") from exc
        draft = KnowledgeCandidateDraft(
            candidate_group_id=output["candidate_group_id"],
            run_id=claim.run_id,
            revision_number=1,
            knowledge_type=output["knowledge_type"],
            claim=output["claim"],
            scope=output["scope"],
            applicability=output["applicability"],
            conditions=output["conditions"],
            exceptions=output["exceptions"],
            evidence=references,
            relation_proposals=tuple(
                RelationProposal.model_validate(item)
                for item in output["relation_proposals"]
            ),
            confidence=output["confidence"],
        )
        candidate = self._governance.register_candidate(
            actor=self._actor,
            draft=draft,
        )
        return StepOutcome(
            output_sha256=candidate.content_sha256,
            artifact_manifest=ArtifactManifest(),
        )


def build_enrichment_step_definition(*, input_sha256: str) -> StepDefinition:
    return StepDefinition(
        step_key=ENRICHMENT_STEP_KEY,
        pool=WorkerPool.ENRICHMENT,
        input_sha256=input_sha256,
        depends_on=("document.persist_evidence",),
    )


def load_enrichment_profiles(
    session_factory: sessionmaker[Session],
    *,
    model_profile_id: str,
    model_profile_version: str,
    prompt_profile_id: str,
    prompt_profile_version: str,
) -> tuple[ModelProfile, PromptProfile]:
    with session_factory() as session:
        model = session.get(ModelProfileRow, (model_profile_id, model_profile_version))
        prompt = session.get(PromptProfileRow, (prompt_profile_id, prompt_profile_version))
    if model is None or prompt is None:
        raise RuntimeError("configured enrichment model or prompt profile does not exist")
    return (
        ModelProfile(
            profile_id=model.profile_id,
            version=model.version,
            provider=model.provider,
            model=model.model,
            deployment_class=model.deployment_class,
            secret_ref=model.secret_ref,
            endpoint_ref=model.endpoint_ref,
            allowed_data_boundaries=model.allowed_data_boundaries,
            capabilities=model.capabilities,
            timeout_seconds=model.timeout_seconds,
            max_output_tokens=model.max_output_tokens,
        ),
        PromptProfile(
            profile_id=prompt.profile_id,
            version=prompt.version,
            system_template=prompt.system_template,
            output_schema_id=prompt.output_schema_id,
            output_schema=prompt.output_schema,
        ),
    )


def offline_provider_from_config(
    *,
    mode: str,
    records_path: Path,
) -> ModelProviderPort:
    """Load an explicit offline fixture; never infer or fall back to a live provider."""

    payload = json.loads(records_path.read_text(encoding="utf-8"))
    if mode == "fake":
        if not isinstance(payload, dict):
            raise ValueError("fake output must be a JSON object")
        return FakeModelProvider(output=payload)
    if mode == "replay":
        if not isinstance(payload, dict):
            raise ValueError("replay records must be a JSON object")
        return ReplayModelProvider(records=payload)
    raise ValueError("P2-B2 provider mode must be fake or replay")


def enrichment_step_handlers(
    service: EnrichmentWorkerService,
) -> Mapping[str, Callable[[object], StepOutcome]]:
    return {ENRICHMENT_STEP_KEY: lambda context: service.extract_candidate(context.claim)}


__all__ = [
    "ENRICHMENT_OUTPUT_SCHEMA",
    "ENRICHMENT_STEP_KEY",
    "EnrichmentContext",
    "EnrichmentEvidence",
    "EnrichmentWorkerService",
    "InMemoryEnrichmentRepository",
    "SqlAlchemyEnrichmentRepository",
    "build_enrichment_step_definition",
    "enrichment_step_handlers",
    "load_enrichment_profiles",
    "offline_provider_from_config",
]
