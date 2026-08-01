"""Idempotent local demo bootstrap for the governed knowledge product.

The bootstrap seeds configuration and identities, registers one real SourceVersion,
runs the real document worker to canonical Evidence, and writes one exact replay
record for the independent enrichment worker. It never inserts a Candidate directly.
"""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy import select

from service.auth import (
    ActorContext,
    IdentitySource,
    PrincipalType,
    ProductRole,
    ROLE_PERMISSIONS,
    WORKER_POOL_PERMISSIONS,
    WorkerPool,
)
from service.db.models import (
    JobStep,
    KnowledgeUnit,
    ModelProfile as ModelProfileRow,
    PromptProfile as PromptProfileRow,
    ServiceAccount,
    StepAttempt,
)
from service.db.session import (
    create_database_engine,
    create_session_factory,
    database_url_from_environment,
)
from service.object_store import LocalObjectStore
from service.processing.document_worker import (
    DocumentWorkerService,
    SqlAlchemyDocumentRepository,
    document_step_handlers,
)
from service.processing.enrichment import (
    ENRICHMENT_OUTPUT_SCHEMA,
    ENRICHMENT_STEP_KEY,
    EnrichmentContext,
    SqlAlchemyEnrichmentRepository,
    build_enrichment_model_request,
    load_enrichment_profiles,
)
from service.processing.ledger import PostgresProcessingLedger
from service.processing.model_provider import PromptProfile, StepAttemptContext
from service.processing.parsers import ParserRegistry
from service.processing.worker import WorkerRuntime, load_service_account_actor
from service.sources import (
    DataBoundary,
    RightsClassification,
    RightsPolicy,
    SourceRegistrationCommand,
    SourceRegistryService,
    SqlAlchemySourceRegistryRepository,
)


DEMO_MODEL_PROFILE_ID = "demo-extractor"
DEMO_MODEL_PROFILE_VERSION = "1.0.0"
DEMO_REPLAY_SECRET_REF = "secret://offline-replay/no-provider-secret"
DEMO_PROMPT_PROFILE_ID = "atomic-candidate"
DEMO_PROMPT_PROFILE_VERSION = "1.1.0"
DEMO_TARGET_KNOWLEDGE_UNIT_ID = "ku-demo-sdtm-ae"
DEMO_SOURCE_ID = "src-demo-aeseq"
DEMO_SOURCE = (
    b"# SDTM AE sequence identifier\n\n"
    b"AESEQ is the sequence identifier used to uniquely identify an adverse-event "
    b"record within the SDTM AE domain.\n"
)


def build_demo_replay_output(
    context: EnrichmentContext,
    *,
    target_knowledge_unit_id: str,
) -> dict[str, Any]:
    """Return an output that cites only Evidence loaded from the canonical repository."""

    evidence_id = context.evidence[0].reference.evidence_id
    return {
        "candidate_group_id": "demo-sdtm-aeseq",
        "knowledge_type": "variable_definition",
        "claim": (
            "AESEQ is the sequence identifier used to uniquely identify an "
            "adverse-event record within the SDTM AE domain."
        ),
        "scope": {
            "standard": "SDTM",
            "domain": "AE",
            "variable": "AESEQ",
        },
        "applicability": {
            "source_version_id": context.source_version_id,
            "data_boundary": context.data_boundary.value,
        },
        "conditions": [{"when": "an adverse-event record is represented in SDTM AE"}],
        "exceptions": [],
        "evidence_ids": [evidence_id],
        "relation_proposals": [
            {
                "relation_type": "applies_to",
                "target_knowledge_unit_id": target_knowledge_unit_id,
                "evidence_ids": [evidence_id],
            }
        ],
        "advisory_signals": [],
        "confidence": 0.98,
    }


def _required_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return Path(value)


def _seed_configuration(session_factory) -> None:
    prompt = PromptProfile(
        profile_id=DEMO_PROMPT_PROFILE_ID,
        version=DEMO_PROMPT_PROFILE_VERSION,
        system_template=(
            "Extract one atomic knowledge candidate from canonical evidence. "
            "Never invent evidence or publish knowledge."
        ),
        output_schema_id="knowledge-candidate.p2-b2.v2",
        output_schema=ENRICHMENT_OUTPUT_SCHEMA,
    )
    with session_factory.begin() as session:
        for pool in WorkerPool:
            account_id = os.environ.get(
                f"KNOWLEDGE_{pool.value.upper()}_WORKER_SERVICE_ACCOUNT_ID",
                f"svc-demo-{pool.value}",
            )
            token_name = f"P12_{pool.value.upper()}_WORKER_TOKEN"
            values = {
                "display_name": f"P12 Demo {pool.value.title()} Worker",
                "worker_pool": pool.value,
                "scopes": sorted(
                    permission.value for permission in WORKER_POOL_PERMISSIONS[pool]
                ),
                "secret_ref": f"env://{token_name}",
                "status": "active",
                "created_by_actor_id": "demo-bootstrap",
            }
            row = session.get(ServiceAccount, account_id)
            if row is None:
                session.add(ServiceAccount(service_account_id=account_id, **values))
            else:
                for name, value in values.items():
                    setattr(row, name, value)

        model = session.get(
            ModelProfileRow,
            (DEMO_MODEL_PROFILE_ID, DEMO_MODEL_PROFILE_VERSION),
        )
        model_values = {
            "provider": "offline-replay",
            "model": "p12-demo-replay",
            "deployment_class": "enterprise_managed",
            "secret_ref": DEMO_REPLAY_SECRET_REF,
            "endpoint_ref": None,
            "allowed_data_boundaries": [DataBoundary.ENTERPRISE_PROVIDER_ONLY.value],
            "capabilities": ["structured_generation"],
            "timeout_seconds": 60,
            "max_output_tokens": 4096,
            "cost_policy": {"mode": "offline_replay"},
        }
        if model is None:
            session.add(
                ModelProfileRow(
                    profile_id=DEMO_MODEL_PROFILE_ID,
                    version=DEMO_MODEL_PROFILE_VERSION,
                    **model_values,
                )
            )
        else:
            for name, value in model_values.items():
                setattr(model, name, value)

        prompt_row = session.get(
            PromptProfileRow,
            (DEMO_PROMPT_PROFILE_ID, DEMO_PROMPT_PROFILE_VERSION),
        )
        prompt_values = {
            "system_template": prompt.system_template,
            "output_schema_id": prompt.output_schema_id,
            "output_schema": prompt.output_schema,
            "output_schema_sha256": prompt.output_schema_sha256,
        }
        if prompt_row is None:
            session.add(
                PromptProfileRow(
                    profile_id=DEMO_PROMPT_PROFILE_ID,
                    version=DEMO_PROMPT_PROFILE_VERSION,
                    **prompt_values,
                )
            )
        else:
            for name, value in prompt_values.items():
                setattr(prompt_row, name, value)

        unit = session.get(KnowledgeUnit, DEMO_TARGET_KNOWLEDGE_UNIT_ID)
        if unit is None:
            session.add(
                KnowledgeUnit(
                    knowledge_unit_id=DEMO_TARGET_KNOWLEDGE_UNIT_ID,
                    stable_key="clinical.sdtm.ae.domain",
                    knowledge_type="domain",
                )
            )


def _bootstrap_actor() -> ActorContext:
    role = ProductRole.KNOWLEDGE_CURATOR
    return ActorContext(
        actor_id="demo-bootstrap",
        display_name="演示数据引导程序",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({role}),
        permissions=ROLE_PERMISSIONS[role],
        identity_source=IdentitySource.LOCAL_TEST,
    )


def bootstrap_demo() -> dict[str, str]:
    """Create the demo through public services and prepare exact replay input."""

    object_root = _required_path("KNOWLEDGE_OBJECT_STORE_ROOT")
    records_path = _required_path("KNOWLEDGE_ENRICHMENT_RECORDS_PATH")

    engine = create_database_engine(database_url_from_environment())
    sessions = create_session_factory(engine)
    try:
        _seed_configuration(sessions)
        ledger = PostgresProcessingLedger(sessions)
        objects = LocalObjectStore(root=object_root)
        registry = SourceRegistryService(
            repository=SqlAlchemySourceRegistryRepository(sessions),
            object_store=objects,
            ledger=ledger,
        )
        receipt = registry.register_and_start(
            actor=_bootstrap_actor(),
            command=SourceRegistrationCommand(
                source_id=DEMO_SOURCE_ID,
                title="P12 Demo — SDTM AE sequence identifier",
                source_type="clinical_standard",
                version="1.0.0",
                rights=RightsPolicy(
                    classification=RightsClassification.INTERNAL,
                    storage_allowed=True,
                    citation_required=True,
                ),
                data_boundary=DataBoundary.ENTERPRISE_PROVIDER_ONLY,
                media_type="text/markdown",
                expected_sha256=sha256(DEMO_SOURCE).hexdigest(),
                idempotency_key="p12-demo-aeseq-v1",
            ),
            content=DEMO_SOURCE,
        )

        document_actor = load_service_account_actor(
            session_factory=sessions,
            service_account_id=os.environ.get(
                "KNOWLEDGE_DOCUMENT_WORKER_SERVICE_ACCOUNT_ID",
                "svc-demo-document",
            ),
            pool=WorkerPool.DOCUMENT,
        )
        document_runtime = WorkerRuntime(
            ledger=ledger,
            actor=document_actor,
            worker_id="demo-bootstrap-document",
            handlers=document_step_handlers(
                DocumentWorkerService(
                    repository=SqlAlchemyDocumentRepository(sessions),
                    object_store=objects,
                    parsers=ParserRegistry.default(),
                    actor_id=document_actor.actor_id,
                )
            ),
            pool=WorkerPool.DOCUMENT,
            lease_seconds=60,
        )
        executed = 0
        while document_runtime.run_once():
            executed += 1
            if executed > 10:
                raise RuntimeError("document bootstrap exceeded the bounded step graph")

        context = SqlAlchemyEnrichmentRepository(sessions).load_context(
            run_id=receipt.run_id
        )
        with sessions() as session:
            row = session.execute(
                select(JobStep, StepAttempt)
                .join(
                    StepAttempt,
                    (StepAttempt.step_id == JobStep.step_id)
                    & (StepAttempt.run_id == JobStep.run_id),
                )
                .where(
                    JobStep.run_id == receipt.run_id,
                    JobStep.step_key == ENRICHMENT_STEP_KEY,
                )
                .order_by(StepAttempt.attempt_number.desc())
                .limit(1)
            ).one_or_none()
        if row is None:
            raise RuntimeError("registered demo run has no enrichment attempt")
        step, attempt = row
        model_profile, prompt_profile = load_enrichment_profiles(
            sessions,
            model_profile_id=DEMO_MODEL_PROFILE_ID,
            model_profile_version=DEMO_MODEL_PROFILE_VERSION,
            prompt_profile_id=DEMO_PROMPT_PROFILE_ID,
            prompt_profile_version=DEMO_PROMPT_PROFILE_VERSION,
        )
        request = build_enrichment_model_request(
            source=context,
            attempt=StepAttemptContext(
                run_id=receipt.run_id,
                step_id=step.step_id,
                attempt_id=attempt.attempt_id,
                attempt_number=attempt.attempt_number,
                previous_attempt_id=attempt.previous_attempt_id,
            ),
            model_profile=model_profile,
            prompt_profile=prompt_profile,
        )
        records_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = records_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    request.input_sha256: build_demo_replay_output(
                        context,
                        target_knowledge_unit_id=DEMO_TARGET_KNOWLEDGE_UNIT_ID,
                    )
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(records_path)
        return {
            "source_version_id": receipt.source_version_id,
            "run_id": receipt.run_id,
            "input_sha256": request.input_sha256,
        }
    finally:
        engine.dispose()


def main() -> None:
    result = bootstrap_demo()
    print(
        "demo bootstrap ready "
        f"run={result['run_id']} replay={result['input_sha256'][:16]}"
    )


if __name__ == "__main__":
    main()
