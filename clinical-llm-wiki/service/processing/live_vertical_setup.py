"""Prepare one fresh, synthetic P2-B3 run without invoking an external model."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path

from sqlalchemy import func, select

from service.auth import (
    ActorContext,
    IdentitySource,
    Permission,
    PrincipalType,
    ProductRole,
    ROLE_PERMISSIONS,
    WorkerPool,
)
from service.db.models import (
    Evidence,
    ModelInvocation,
    ModelProfile as ModelProfileRow,
    ProcessingRun,
    PromptProfile as PromptProfileRow,
)
from service.db.session import (
    create_database_engine,
    create_session_factory,
    database_url_from_environment,
)
from service.demo_runtime import DemoIdentity, load_demo_identity_bundle
from service.object_store import LocalObjectStore
from service.processing.document_worker import (
    DocumentWorkerService,
    SqlAlchemyDocumentRepository,
    document_step_handlers,
)
from service.processing.ledger import PostgresProcessingLedger
from service.processing.model_provider import ModelProfile
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


LIVE_MODEL_PROFILE_ID = "deepseek-v4-flash-extractor"
LIVE_MODEL_PROFILE_VERSION = "1.0.1"
LIVE_PROMPT_PROFILE_ID = "atomic-candidate"
LIVE_PROMPT_PROFILE_VERSION = "1.1.0"
LIVE_SOURCE_ID = "src-p2b3-live-synthetic-teae"
LIVE_SOURCE_VERSION = "1.0.0"
LIVE_SOURCE = (
    b"# Synthetic treatment-emergent adverse event rule\n\n"
    b"For this P2-B3 synthetic test fixture only, an adverse event is "
    b"treatment-emergent when its start date is on or after the first study dose "
    b"and no later than 30 days after the last study dose. This statement is "
    b"synthetic test data and is not a clinical standard.\n"
)


def deepseek_model_profile() -> ModelProfile:
    """Return the exact canonical profile authorized by the runtime environment."""

    return ModelProfile(
        profile_id=LIVE_MODEL_PROFILE_ID,
        version=LIVE_MODEL_PROFILE_VERSION,
        provider="deepseek",
        model="deepseek-v4-flash",
        deployment_class="external_api",
        secret_ref="env://KNOWLEDGE_MODEL_API_KEY",
        endpoint_ref="env://KNOWLEDGE_MODEL_ENDPOINT",
        allowed_data_boundaries=["external_allowed"],
        capabilities=["structured_generation"],
        timeout_seconds=60,
        max_output_tokens=4096,
    )


def live_source_command() -> SourceRegistrationCommand:
    """Return a fixed, outbound-safe command for the single live vertical."""

    return SourceRegistrationCommand(
        source_id=LIVE_SOURCE_ID,
        title="P2-B3 Synthetic — treatment-emergent adverse event rule",
        source_type="synthetic_test",
        version=LIVE_SOURCE_VERSION,
        rights=RightsPolicy(
            classification=RightsClassification.INTERNAL,
            storage_allowed=True,
            citation_required=True,
        ),
        data_boundary=DataBoundary.EXTERNAL_ALLOWED,
        media_type="text/markdown",
        expected_sha256=sha256(LIVE_SOURCE).hexdigest(),
        idempotency_key="p2b3-live-synthetic-teae-v1",
    )


def _required_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return Path(value)


def _curator_actor(identity: DemoIdentity) -> ActorContext:
    permissions: set[Permission] = set()
    for role in identity.roles:
        permissions.update(ROLE_PERMISSIONS[role])
    return ActorContext(
        actor_id=identity.user_id,
        display_name=identity.display_name,
        principal_type=PrincipalType.HUMAN,
        roles=frozenset(identity.roles),
        permissions=frozenset(permissions),
        identity_source=IdentitySource.LOCAL_TEST,
    )


def _ensure_live_profile(session_factory) -> None:
    profile = deepseek_model_profile()
    values = {
        "provider": profile.provider,
        "model": profile.model,
        "deployment_class": profile.deployment_class.value,
        "secret_ref": profile.secret_ref,
        "endpoint_ref": profile.endpoint_ref,
        "allowed_data_boundaries": sorted(
            boundary.value for boundary in profile.allowed_data_boundaries
        ),
        "capabilities": sorted(capability.value for capability in profile.capabilities),
        "timeout_seconds": profile.timeout_seconds,
        "max_output_tokens": profile.max_output_tokens,
        "cost_policy": {
            "currency": "USD",
            "mode": "metered_external_api",
            "structured_output_transport": "json_object+local_json_schema_v1",
        },
    }
    with session_factory.begin() as session:
        prompt = session.get(
            PromptProfileRow,
            (LIVE_PROMPT_PROFILE_ID, LIVE_PROMPT_PROFILE_VERSION),
        )
        if prompt is None:
            raise RuntimeError(
                "atomic-candidate@1.1.0 must be bootstrapped before live setup"
            )
        row = session.get(
            ModelProfileRow,
            (LIVE_MODEL_PROFILE_ID, LIVE_MODEL_PROFILE_VERSION),
        )
        if row is None:
            session.add(
                ModelProfileRow(
                    profile_id=LIVE_MODEL_PROFILE_ID,
                    version=LIVE_MODEL_PROFILE_VERSION,
                    **values,
                )
            )
            return
        drift = [
            name for name, expected in values.items() if getattr(row, name) != expected
        ]
        if drift:
            raise RuntimeError(
                "registered DeepSeek ModelProfile differs from the canonical setup: "
                + ", ".join(sorted(drift))
            )


def prepare_live_vertical() -> dict[str, object]:
    """Create canonical Evidence for one synthetic run, but never invoke a model."""

    identities_path = _required_path("KNOWLEDGE_LOCAL_IDENTITIES_PATH")
    object_root = _required_path("KNOWLEDGE_OBJECT_STORE_ROOT")
    bundle = load_demo_identity_bundle(identities_path)
    curator = next(
        identity
        for identity in bundle.identities
        if ProductRole.KNOWLEDGE_CURATOR in identity.roles
    )

    engine = create_database_engine(database_url_from_environment())
    sessions = create_session_factory(engine)
    try:
        _ensure_live_profile(sessions)
        ledger = PostgresProcessingLedger(sessions)
        objects = LocalObjectStore(root=object_root)
        receipt = SourceRegistryService(
            repository=SqlAlchemySourceRegistryRepository(sessions),
            object_store=objects,
            ledger=ledger,
        ).register_and_start(
            actor=_curator_actor(curator),
            command=live_source_command(),
            content=LIVE_SOURCE,
        )

        document_actor = load_service_account_actor(
            session_factory=sessions,
            service_account_id=os.environ.get(
                "KNOWLEDGE_DOCUMENT_WORKER_SERVICE_ACCOUNT_ID",
                "svc-demo-document",
            ),
            pool=WorkerPool.DOCUMENT,
        )
        runtime = WorkerRuntime(
            ledger=ledger,
            actor=document_actor,
            worker_id="p2b3-live-setup-document",
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
            target_run_id=receipt.run_id,
        )
        executed = 0
        while runtime.run_once():
            executed += 1
            if executed > 10:
                raise RuntimeError("live setup exceeded the bounded document step graph")

        with sessions() as session:
            run = session.get(ProcessingRun, receipt.run_id)
            evidence_count = session.scalar(
                select(func.count(Evidence.evidence_id)).where(
                    Evidence.source_version_id == receipt.source_version_id
                )
            )
            invocation_count = session.scalar(
                select(func.count(ModelInvocation.invocation_id)).where(
                    ModelInvocation.run_id == receipt.run_id
                )
            )
        if run is None or run.status != "evidence_ready":
            raise RuntimeError("synthetic live run did not reach evidence_ready")
        if not evidence_count:
            raise RuntimeError("synthetic live run produced no canonical Evidence")
        if invocation_count:
            raise RuntimeError("synthetic live run is not fresh")

        return {
            "ready_for_preflight": True,
            "run_id": receipt.run_id,
            "source_version_id": receipt.source_version_id,
            "data_boundary": DataBoundary.EXTERNAL_ALLOWED.value,
            "evidence_count": int(evidence_count),
            "model_profile_id": LIVE_MODEL_PROFILE_ID,
            "model_profile_version": LIVE_MODEL_PROFILE_VERSION,
            "model_invocation_count": int(invocation_count),
        }
    finally:
        engine.dispose()


def main() -> None:
    print(json.dumps(prepare_live_vertical(), sort_keys=True))


if __name__ == "__main__":
    main()
