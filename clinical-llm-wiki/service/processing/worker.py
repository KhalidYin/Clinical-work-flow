"""Pool-parameterized worker runtime with P2-A document handlers."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import time
from typing import Any, Protocol

from sqlalchemy import select

from service.auth import (
    ActorContext,
    AuthorizationError,
    GrantStatus,
    Permission,
    PrincipalType,
    ServiceAccountGrant,
    WorkerPool,
    require_permission,
    resolve_service_account_actor,
)
from service.db.models import ServiceAccount
from service.db.session import (
    create_database_engine,
    create_session_factory,
    database_url_from_environment,
)
from service.object_store import LocalObjectStore
from service.governance import KnowledgeGovernanceService, SqlAlchemyGovernanceRepository
from service.sources import (
    SourceRegistryService,
    SqlAlchemySourceRegistryRepository,
)

from .contracts import ClaimedStepAttempt, StepOutcome
from .document_worker import (
    DocumentWorkerService,
    SqlAlchemyDocumentRepository,
    document_step_handlers,
)
from .ledger import PostgresProcessingLedger, ProcessingLedgerPort
from .enrichment import (
    EnrichmentWorkerService,
    SqlAlchemyEnrichmentRepository,
    enrichment_step_handlers,
    load_enrichment_profiles,
    offline_provider_from_config,
)
from .model_profiles import authorized_live_provider_from_environment
from .model_provider import ModelProfile, ModelProviderPort
from .parsers import ParserRegistry


class StepHandler(Protocol):
    def __call__(self, context: "StepExecutionContext") -> StepOutcome: ...


@dataclass(frozen=True, slots=True)
class StepExecutionContext:
    claim: ClaimedStepAttempt
    _heartbeat: Callable[[], None]
    _checkpoint: Callable[[dict[str, Any]], None]

    def heartbeat(self) -> None:
        self._heartbeat()

    def checkpoint(self, value: dict[str, Any]) -> None:
        self._checkpoint(value)


class WorkerRuntime:
    """Executes only registered step keys for exactly one authorized pool."""

    def __init__(
        self,
        *,
        ledger: ProcessingLedgerPort,
        actor: ActorContext,
        worker_id: str,
        handlers: Mapping[str, StepHandler],
        pool: WorkerPool | None = None,
        lease_seconds: int = 60,
    ) -> None:
        if actor.principal_type is not PrincipalType.SERVICE_ACCOUNT:
            raise AuthorizationError("worker runtime requires a service account actor")
        resolved_pool = pool or actor.worker_pool
        if resolved_pool is None or actor.worker_pool is not resolved_pool:
            raise AuthorizationError("worker actor pool does not match runtime pool")
        require_permission(actor, Permission.PROCESSING_EXECUTE)
        if not worker_id:
            raise ValueError("worker_id is required")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        self._ledger = ledger
        self._actor = actor
        self._worker_id = worker_id
        self._handlers = dict(handlers)
        self._pool = resolved_pool
        self._lease_seconds = lease_seconds

    @property
    def pool(self) -> WorkerPool:
        return self._pool

    def run_once(self) -> bool:
        if not self._handlers:
            return False
        self._ledger.recover_expired_leases(actor=self._actor, pool=self._pool)
        claim = self._ledger.claim_next(
            actor=self._actor,
            worker_id=self._worker_id,
            supported_step_keys=frozenset(self._handlers),
            lease_seconds=self._lease_seconds,
        )
        if claim is None:
            return False
        handler = self._handlers[claim.step_key]
        context = StepExecutionContext(
            claim=claim,
            _heartbeat=lambda: self._ledger.heartbeat(
                actor=self._actor,
                worker_id=self._worker_id,
                attempt_id=claim.attempt_id,
                lease_seconds=self._lease_seconds,
            ),
            _checkpoint=lambda value: self._ledger.save_checkpoint(
                actor=self._actor,
                worker_id=self._worker_id,
                attempt_id=claim.attempt_id,
                checkpoint=value,
            ),
        )
        try:
            outcome = StepOutcome.model_validate(handler(context))
        except Exception as exc:
            self._ledger.fail_attempt(
                actor=self._actor,
                worker_id=self._worker_id,
                attempt_id=claim.attempt_id,
                error_type="handler_error",
                error_message=f"handler_error: {type(exc).__name__}",
            )
            return True
        self._ledger.complete_attempt(
            actor=self._actor,
            worker_id=self._worker_id,
            attempt_id=claim.attempt_id,
            outcome=outcome,
        )
        return True


class MultiPoolWorkerRuntime:
    """Local coordinator using exactly the same per-pool runtime semantics."""

    def __init__(self, runtimes: Sequence[WorkerRuntime]) -> None:
        pools = [runtime.pool for runtime in runtimes]
        if len(set(pools)) != len(pools):
            raise ValueError("multi-pool runtime accepts at most one runtime per pool")
        self._runtimes = tuple(runtimes)

    def run_once(self) -> int:
        return sum(runtime.run_once() for runtime in self._runtimes)


def load_service_account_actor(
    *,
    session_factory,
    service_account_id: str,
    pool: WorkerPool,
) -> ActorContext:
    with session_factory() as session:
        record = session.scalar(
            select(ServiceAccount).where(ServiceAccount.service_account_id == service_account_id)
        )
    if record is None:
        raise RuntimeError("configured worker service account does not exist")
    grant = ServiceAccountGrant(
        service_account_id=record.service_account_id,
        display_name=record.display_name,
        worker_pool=record.worker_pool,
        scopes=record.scopes,
        secret_ref=record.secret_ref,
        status=GrantStatus(record.status),
    )
    if grant.worker_pool is not pool:
        raise AuthorizationError("configured service account belongs to another worker pool")
    _require_secret_reference(grant.secret_ref)
    return resolve_service_account_actor(grant)


def _require_secret_reference(reference: str) -> None:
    scheme, name = reference.split("://", 1)
    if scheme != "env":
        raise RuntimeError("local worker entrypoint supports env:// secret references only")
    if not os.environ.get(name):
        raise RuntimeError(f"required worker credential reference is not configured: {name}")


def enrichment_provider_from_environment(
    model_profile: ModelProfile,
    environ: Mapping[str, str] | None = None,
) -> ModelProviderPort:
    """Select explicit offline or live enrichment mode without implicit fallback."""

    values = os.environ if environ is None else environ
    provider_mode = values.get("KNOWLEDGE_ENRICHMENT_PROVIDER_MODE", "replay")
    if provider_mode == "live":
        return authorized_live_provider_from_environment(
            model_profile=model_profile,
            environ=values,
        )
    fixture_path = values.get("KNOWLEDGE_ENRICHMENT_RECORDS_PATH")
    if not fixture_path:
        raise RuntimeError(
            "KNOWLEDGE_ENRICHMENT_RECORDS_PATH is required for fake/replay mode"
        )
    return offline_provider_from_config(
        mode=provider_mode,
        records_path=Path(fixture_path),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", choices=[pool.value for pool in WorkerPool])
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--list-pools", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.list_pools:
        for pool in WorkerPool:
            print(pool.value)
        return 0
    if args.pool is None:
        _parser().error("--pool is required unless --list-pools is used")
    pool = WorkerPool(args.pool)
    account_variable = f"KNOWLEDGE_{pool.value.upper()}_WORKER_SERVICE_ACCOUNT_ID"
    account_id = os.environ.get(account_variable)
    if not account_id:
        raise RuntimeError(f"{account_variable} is required")
    engine = create_database_engine(database_url_from_environment())
    sessions = create_session_factory(engine)
    actor = load_service_account_actor(
        session_factory=sessions,
        service_account_id=account_id,
        pool=pool,
    )
    ledger = PostgresProcessingLedger(sessions)
    handlers: Mapping[str, StepHandler] = {}
    if pool is WorkerPool.DOCUMENT:
        object_root = os.environ.get("KNOWLEDGE_OBJECT_STORE_ROOT")
        if not object_root:
            raise RuntimeError("KNOWLEDGE_OBJECT_STORE_ROOT is required for the document worker")
        object_store = LocalObjectStore(root=Path(object_root))
        cleanup = SourceRegistryService(
            repository=SqlAlchemySourceRegistryRepository(sessions),
            object_store=object_store,
            ledger=ledger,
        ).reconcile_orphans(
            actor=actor,
            minimum_age_seconds=int(
                os.environ.get(
                    "KNOWLEDGE_OBJECT_CLEANUP_MIN_AGE_SECONDS",
                    "300",
                )
            ),
        )
        print(
            "object cleanup "
            f"scanned={cleanup.scanned} deleted={cleanup.deleted} "
            f"missing={cleanup.missing} failed={cleanup.failed}"
        )
        document_service = DocumentWorkerService(
            repository=SqlAlchemyDocumentRepository(sessions),
            object_store=object_store,
            parsers=ParserRegistry.default(),
            actor_id=actor.actor_id,
        )
        handlers = document_step_handlers(document_service)
    elif pool is WorkerPool.ENRICHMENT:
        model_profile, prompt_profile = load_enrichment_profiles(
            sessions,
            model_profile_id=os.environ.get(
                "KNOWLEDGE_ENRICHMENT_MODEL_PROFILE_ID",
                "demo-extractor",
            ),
            model_profile_version=os.environ.get(
                "KNOWLEDGE_ENRICHMENT_MODEL_PROFILE_VERSION",
                "1.0.0",
            ),
            prompt_profile_id=os.environ.get(
                "KNOWLEDGE_ENRICHMENT_PROMPT_PROFILE_ID",
                "atomic-candidate",
            ),
            prompt_profile_version=os.environ.get(
                "KNOWLEDGE_ENRICHMENT_PROMPT_PROFILE_VERSION",
                "1.0.0",
            ),
        )
        model_provider = enrichment_provider_from_environment(model_profile)
        enrichment_service = EnrichmentWorkerService(
            repository=SqlAlchemyEnrichmentRepository(sessions),
            governance=KnowledgeGovernanceService(
                repository=SqlAlchemyGovernanceRepository(sessions)
            ),
            provider=model_provider,
            model_profile=model_profile,
            prompt_profile=prompt_profile,
            actor=actor,
        )
        handlers = enrichment_step_handlers(enrichment_service)
    runtime = WorkerRuntime(
        ledger=ledger,
        actor=actor,
        worker_id=os.environ.get("KNOWLEDGE_WORKER_ID", f"{pool.value}-{os.getpid()}"),
        handlers=handlers,
        pool=pool,
        lease_seconds=int(os.environ.get("KNOWLEDGE_WORKER_LEASE_SECONDS", "60")),
    )
    try:
        while True:
            runtime.run_once()
            if args.once:
                return 0
            time.sleep(max(0.1, args.poll_seconds))
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
