from __future__ import annotations

from hashlib import sha256

import pytest

from service.auth import (
    GrantStatus,
    ServiceAccountGrant,
    WorkerPool,
    resolve_service_account_actor,
)
from service.object_store import InMemoryObjectStore, ObjectNotFoundError
from service.sources import (
    DataBoundary,
    InMemorySourceRegistryRepository,
    RegistrationConflictError,
    RightsClassification,
    RightsPolicy,
    SourceRegistrationCommand,
    SourceRegistrationError,
    SourceRegistryService,
    UnsupportedSourceMediaError,
)
from service.auth import (
    IdentitySource,
    PlatformUserGrant,
    resolve_human_actor,
    StaticAuthorizationGrantStore,
)


PDF = b"%PDF-1.7\nsynthetic governed source\n%%EOF"


def _curator():
    grant = PlatformUserGrant(
        user_id="usr-curator",
        identity_source=IdentitySource.LOCAL_TEST,
        issuer="local://p2a-tests",
        subject="curator",
        display_name="Knowledge Curator",
        email="curator@example.test",
        status=GrantStatus.ACTIVE,
        roles=["knowledge_curator"],
    )
    return resolve_human_actor(
        identity=type(
            "Identity",
            (),
            {
                "issuer": grant.issuer,
                "subject": grant.subject,
                "identity_source": grant.identity_source,
            },
        )(),
        grant_store=StaticAuthorizationGrantStore(users=[grant]),
    )


def _document_worker():
    return resolve_service_account_actor(
        ServiceAccountGrant(
            service_account_id="svc-document",
            display_name="Document Worker",
            worker_pool=WorkerPool.DOCUMENT,
            scopes=[
                "source:read",
                "object:read",
                "object:write_derived",
                "processing:execute",
                "evidence:write",
            ],
            secret_ref="env://P12_DOCUMENT_WORKER_TOKEN",
            status=GrantStatus.ACTIVE,
        )
    )


class FakeLedger:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.fail_next_create = False

    def create_run(self, **kwargs: object) -> str:
        if self.fail_next_create:
            self.fail_next_create = False
            raise RuntimeError("ledger unavailable")
        if any(item["run_id"] == kwargs["run_id"] for item in self.created):
            return str(kwargs["run_id"])
        self.created.append(kwargs)
        return str(kwargs["run_id"])


def _command(*, version: str = "3.4", expected_sha256: str | None = None):
    return SourceRegistrationCommand(
        source_id="src-sdtmig",
        title="Study Data Tabulation Model Implementation Guide",
        source_type="standard",
        version=version,
        rights=RightsPolicy(
            classification=RightsClassification.LICENSED,
            storage_allowed=True,
        ),
        data_boundary=DataBoundary.LOCAL_PROCESSING_ONLY,
        media_type="application/pdf",
        expected_sha256=expected_sha256 or sha256(PDF).hexdigest(),
        idempotency_key=f"upload-src-sdtmig-{version}",
    )


def test_register_is_idempotent_and_new_version_is_distinct() -> None:
    repository = InMemorySourceRegistryRepository()
    store = InMemoryObjectStore()
    ledger = FakeLedger()
    service = SourceRegistryService(
        repository=repository,
        object_store=store,
        ledger=ledger,
    )

    first = service.register_and_start(actor=_curator(), command=_command(), content=PDF)
    replay = service.register_and_start(actor=_curator(), command=_command(), content=PDF)
    second_version = service.register_and_start(
        actor=_curator(),
        command=_command(version="3.4.1"),
        content=PDF,
    )

    assert replay == first
    assert first.source_version_id != second_version.source_version_id
    assert first.status == "queued"
    assert first.original_object.sha256 == sha256(PDF).hexdigest()
    assert len(repository.visible_source_versions()) == 2
    assert len(ledger.created) == 2
    for invocation in ledger.created:
        steps = invocation["steps"]  # type: ignore[index]
        assert [step.step_key for step in steps][-1] == "enrichment.extract_candidate"
        assert steps[-1].pool is WorkerPool.ENRICHMENT
        assert steps[-1].depends_on == ("document.persist_evidence",)


def test_registered_source_replay_repairs_a_transient_run_creation_failure() -> None:
    repository = InMemorySourceRegistryRepository()
    store = InMemoryObjectStore()
    ledger = FakeLedger()
    ledger.fail_next_create = True
    service = SourceRegistryService(
        repository=repository,
        object_store=store,
        ledger=ledger,
    )

    with pytest.raises(SourceRegistrationError, match="run could not be started"):
        service.register_and_start(actor=_curator(), command=_command(), content=PDF)

    assert len(repository.visible_source_versions()) == 1
    repaired = service.register_and_start(
        actor=_curator(),
        command=_command(),
        content=PDF,
    )
    assert repaired.status == "queued"
    assert [item["run_id"] for item in ledger.created] == [repaired.run_id]
    assert len(repository.visible_source_versions()) == 1


def test_hash_mime_rights_and_version_conflicts_fail_closed() -> None:
    repository = InMemorySourceRegistryRepository()
    store = InMemoryObjectStore()
    service = SourceRegistryService(
        repository=repository,
        object_store=store,
        ledger=FakeLedger(),
    )

    with pytest.raises(SourceRegistrationError, match="hash"):
        service.register_and_start(
            actor=_curator(),
            command=_command(expected_sha256="0" * 64),
            content=PDF,
        )
    with pytest.raises(UnsupportedSourceMediaError, match="signature"):
        service.register_and_start(
            actor=_curator(),
            command=_command(expected_sha256=sha256(b"not a pdf").hexdigest()),
            content=b"not a pdf",
        )
    with pytest.raises(SourceRegistrationError, match="rights"):
        service.register_and_start(
            actor=_curator(),
            command=_command().model_copy(
                update={
                    "rights": RightsPolicy(
                        classification=RightsClassification.RESTRICTED,
                        storage_allowed=False,
                    )
                }
            ),
            content=PDF,
        )

    first = service.register_and_start(actor=_curator(), command=_command(), content=PDF)
    with pytest.raises(RegistrationConflictError, match="version"):
        service.register_and_start(
            actor=_curator(),
            command=_command(expected_sha256=sha256(PDF + b"x").hexdigest()),
            content=PDF + b"x",
        )

    assert repository.visible_source_versions() == [first.source_version_id]
    assert len(repository.registration_intents()) == 1


def test_database_commit_failure_deletes_object_and_never_publishes_source() -> None:
    repository = InMemorySourceRegistryRepository()
    repository.fail_next_commit = True
    store = InMemoryObjectStore()
    service = SourceRegistryService(
        repository=repository,
        object_store=store,
        ledger=FakeLedger(),
    )

    with pytest.raises(SourceRegistrationError, match="commit"):
        service.register_and_start(actor=_curator(), command=_command(), content=PDF)

    intent = repository.registration_intents()[0]
    assert intent.status == "compensated"
    assert repository.visible_source_versions() == []
    with pytest.raises(ObjectNotFoundError):
        store.head(intent.object_key)


def test_idempotent_replay_fails_closed_when_canonical_object_is_missing() -> None:
    repository = InMemorySourceRegistryRepository()
    store = InMemoryObjectStore()
    service = SourceRegistryService(
        repository=repository,
        object_store=store,
        ledger=FakeLedger(),
    )
    receipt = service.register_and_start(
        actor=_curator(),
        command=_command(),
        content=PDF,
    )
    store.delete(receipt.original_object.object_key)

    with pytest.raises(SourceRegistrationError, match="object is missing"):
        service.register_and_start(
            actor=_curator(),
            command=_command(),
            content=PDF,
        )


def test_failed_delete_becomes_auditable_cleanup_and_reconciles() -> None:
    repository = InMemorySourceRegistryRepository()
    repository.fail_next_commit = True

    class DeleteFailsOnceStore(InMemoryObjectStore):
        def __init__(self) -> None:
            super().__init__()
            self.fail_delete = True

        def delete(self, object_key: str) -> None:
            if self.fail_delete:
                self.fail_delete = False
                raise OSError("transient delete failure")
            super().delete(object_key)

    store = DeleteFailsOnceStore()
    service = SourceRegistryService(
        repository=repository,
        object_store=store,
        ledger=FakeLedger(),
    )

    with pytest.raises(SourceRegistrationError, match="commit"):
        service.register_and_start(actor=_curator(), command=_command(), content=PDF)

    intent = repository.registration_intents()[0]
    assert intent.status == "compensation_required"
    assert store.head(intent.object_key).sha256 == sha256(PDF).hexdigest()

    result = service.reconcile_orphans(
        actor=_document_worker(),
        limit=10,
        minimum_age_seconds=0,
    )

    assert result.scanned == 1
    assert result.deleted == 1
    assert repository.registration_intents()[0].status == "compensated"
    assert repository.audit_actions()[-1] == "object.orphan_compensated"
    with pytest.raises(ObjectNotFoundError):
        store.head(intent.object_key)
