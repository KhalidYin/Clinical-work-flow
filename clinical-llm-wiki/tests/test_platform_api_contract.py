from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from importlib import import_module
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
import pytest
from sqlalchemy.exc import OperationalError
import yaml

from service.auth import (
    IdentityAssertion,
    LocalIdentityProvider,
    PlatformUserGrant,
)
from service.object_store import ObjectDescriptor
from service.sources import SourceRegistrationReceipt


ROOT = Path(__file__).resolve().parents[1]
API_PREFIX = "/api/prerelease/v1"


def _platform_modules():
    try:
        app_module = import_module("service.platform_api.app")
        contracts_module = import_module("service.platform_api.contracts")
        repository_module = import_module("service.platform_api.repository")
    except ModuleNotFoundError as exc:
        pytest.fail(f"P1-D platform API is not implemented: {exc}")
    return app_module, contracts_module, repository_module


class FakePlatformRepository:
    def __init__(self, repository_module: Any) -> None:
        now = datetime(2026, 7, 30, 3, 0, tzinfo=timezone.utc)
        self._grants: dict[tuple[str, str], PlatformUserGrant] = {}
        self.sources = [
            repository_module.SourceSummaryRecord(
                source_id="src-sdtmig-34",
                title="Study Data Tabulation Model Implementation Guide",
                version="3.4",
                media_type="PDF",
                rights="licensed",
                status="registered",
                source_hash="a" * 64,
                updated_at=now,
            )
        ]
        self.users: list[Any] = []
        self.release = repository_module.CurrentReleaseRecord(
            release_id="rel-001",
            version="2026.07-p1d",
            status="released",
            index_version="idx-001",
            released_at=now,
        )
        self.database_is_available = True
        self.source_read_fails = False
        attempt = repository_module.ProcessingAttemptRecord(
            attempt_id="attempt-api-001",
            attempt_number=1,
            status="queued",
            error_type=None,
            checkpoint=None,
            artifact_count=0,
        )
        step = repository_module.ProcessingStepRecord(
            step_id="step-api-001",
            step_key="document.validate",
            pool="document",
            status="queued",
            depends_on=(),
            latest_attempt=attempt,
        )
        self.processing_runs = [
            repository_module.ProcessingRunRecord(
                run_id="run-api-001",
                source_version_id="srcv-api-001",
                status="queued",
                created_at=now,
                updated_at=now,
                original_artifact_count=1,
                derived_artifact_count=0,
                evidence_count=0,
                steps=(step,),
            )
        ]
        self.candidates = [
            repository_module.CandidateSummaryRecord(
                candidate_id="cand-api-001",
                candidate_group_id="candgrp-api-aeseq",
                run_id="run-api-001",
                revision_number=1,
                status="author_confirmation_required",
                knowledge_type="variable_definition",
                claim="AESEQ is the sequence identifier within the AE domain.",
                scope={"standard": "SDTM", "domain": "AE"},
                applicability={"standard_version": "3.4"},
                content_sha256="b" * 64,
                evidence_count=1,
                relation_proposal_count=1,
                author_actor_id=None,
                knowledge_revision_id=None,
                review_status=None,
            )
        ]

    def add_grant(self, grant: PlatformUserGrant) -> None:
        self._grants[(grant.issuer, grant.subject)] = grant

    def resolve_user(self, *, issuer: str, subject: str) -> PlatformUserGrant | None:
        return self._grants.get((issuer, subject))

    def database_available(self) -> bool:
        return self.database_is_available

    def get_current_release(self):
        return self.release

    def list_sources(self):
        if self.source_read_fails:
            raise OperationalError("SELECT", {}, RuntimeError("database unavailable"))
        return self.sources, []

    def list_platform_users(self):
        return self.users, []

    def list_processing_runs(self):
        return self.processing_runs, []

    def get_processing_run(self, *, run_id: str):
        return next(
            (record for record in self.processing_runs if record.run_id == run_id),
            None,
        )

    def list_candidates(self):
        return self.candidates, []

    def get_candidate_detail(self, *, candidate_id: str):
        summary = next(
            (record for record in self.candidates if record.candidate_id == candidate_id),
            None,
        )
        if summary is None:
            return None
        from service.platform_api.repository import (
            CandidateDetailRecord,
            CandidateEvidenceRecord,
            CandidateRelationProposalRecord,
        )

        return CandidateDetailRecord(
            **asdict(summary),
            parent_candidate_id=None,
            conditions=(),
            exceptions=(),
            evidence=(
                CandidateEvidenceRecord(
                    evidence_id="ev-api-001",
                    source_version_id="srcv-api-001",
                    locator={"page": 35, "section": "6.2 AE"},
                    content="AESEQ is the sequence identifier within the AE domain.",
                    content_sha256="a" * 64,
                    rights={"classification": "licensed", "storage_allowed": True},
                ),
            ),
            relation_proposals=(
                CandidateRelationProposalRecord(
                    relation_type="applies_to",
                    target_knowledge_unit_id="ku-sdtm-ae",
                    evidence_ids=("ev-api-001",),
                    status="proposed",
                ),
            ),
        )


class FakeSourceRegistry:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def register_and_start(self, **kwargs: Any) -> SourceRegistrationReceipt:
        self.calls.append(kwargs)
        command = kwargs["command"]
        content = kwargs["content"]
        return SourceRegistrationReceipt(
            source_id=command.source_id,
            source_version_id="srcv-upload-001",
            run_id="run-upload-001",
            original_object=ObjectDescriptor(
                object_key=(f"sources/src-upload/srcv-upload-001/{sha256(content).hexdigest()}.md"),
                sha256=sha256(content).hexdigest(),
                media_type=command.media_type,
                size_bytes=len(content),
            ),
        )


class FakeProcessingLedger:
    def __init__(self) -> None:
        self.retries: list[tuple[str, str]] = []
        self.cancelled: list[str] = []

    def retry_step(self, *, run_id: str, step_id: str, **_: object) -> str:
        self.retries.append((run_id, step_id))
        return "attempt-api-002"

    def cancel_run(self, *, run_id: str, **_: object) -> None:
        self.cancelled.append(run_id)


class FakeGovernanceService:
    def __init__(self) -> None:
        self.author_calls: list[dict[str, Any]] = []
        self.review_calls: list[dict[str, Any]] = []
        self.revision_calls: list[dict[str, Any]] = []

    def confirm_candidate(self, **kwargs: Any):
        from service.knowledge import (
            AuthorConfirmationReceipt,
            KnowledgeCandidateRecord,
            KnowledgeRevisionRecord,
        )

        self.author_calls.append(kwargs)
        return AuthorConfirmationReceipt(
            candidate=KnowledgeCandidateRecord(
                candidate_id="cand-api-001",
                candidate_group_id="candgrp-api-aeseq",
                run_id="run-api-001",
                revision_number=1,
                status="author_confirmed",
                knowledge_type="variable_definition",
                claim="AESEQ is the sequence identifier within the AE domain.",
                scope={"standard": "SDTM", "domain": "AE"},
                applicability={"standard_version": "3.4"},
                evidence=[
                    {
                        "evidence_id": "ev-api-001",
                        "source_version_id": "srcv-api-001",
                        "locator": {"page": 35},
                        "content_sha256": "a" * 64,
                        "rights": {
                            "classification": "licensed",
                            "storage_allowed": True,
                        },
                    }
                ],
                content_sha256="b" * 64,
                author_actor_id=kwargs["actor"].actor_id,
            ),
            revision=KnowledgeRevisionRecord(
                knowledge_revision_id="krev-api-001",
                knowledge_unit_id="ku-api-aeseq",
                candidate_id="cand-api-001",
                revision_number=1,
                status="review_required",
                claim="AESEQ is the sequence identifier within the AE domain.",
                scope={"standard": "SDTM", "domain": "AE"},
                applicability={"standard_version": "3.4"},
                content_sha256="b" * 64,
                author_actor_id=kwargs["actor"].actor_id,
            ),
            decision_id="decision-api-author-001",
        )

    def review_revision(self, **kwargs: Any):
        from service.knowledge import KnowledgeRevisionRecord, ReviewDecisionReceipt

        self.review_calls.append(kwargs)
        return ReviewDecisionReceipt(
            revision=KnowledgeRevisionRecord(
                knowledge_revision_id="krev-api-001",
                knowledge_unit_id="ku-api-aeseq",
                candidate_id="cand-api-001",
                revision_number=1,
                status=kwargs["command"].decision.value,
                claim="AESEQ is the sequence identifier within the AE domain.",
                scope={"standard": "SDTM", "domain": "AE"},
                applicability={"standard_version": "3.4"},
                content_sha256="b" * 64,
                author_actor_id="usr-curator",
            ),
            decision_id="decision-api-review-001",
        )

    def revise_candidate(self, **kwargs: Any):
        from service.knowledge import KnowledgeCandidateRecord

        self.revision_calls.append(kwargs)
        return KnowledgeCandidateRecord(
            candidate_id="cand-api-002",
            candidate_group_id="candgrp-api-aeseq",
            parent_candidate_id="cand-api-001",
            run_id="run-api-001",
            revision_number=2,
            status="author_confirmation_required",
            knowledge_type="variable_definition",
            claim=kwargs["command"].claim,
            scope=kwargs["command"].scope,
            applicability=kwargs["command"].applicability,
            evidence=[
                {
                    "evidence_id": "ev-api-001",
                    "source_version_id": "srcv-api-001",
                    "locator": {"page": 35},
                    "content_sha256": "a" * 64,
                    "rights": {
                        "classification": "licensed",
                        "storage_allowed": True,
                    },
                }
            ],
            content_sha256="c" * 64,
        )


def _identity(subject: str, display_name: str) -> IdentityAssertion:
    return IdentityAssertion(
        identity_source="local_test",
        issuer="local://p1d-tests",
        subject=subject,
        display_name=display_name,
        email=f"{subject}@example.test",
        claims_sha256=sha256(subject.encode("utf-8")).hexdigest(),
    )


def _grant(subject: str, display_name: str, role: str, *, status: str = "active"):
    return PlatformUserGrant(
        user_id=f"usr-{subject}",
        identity_source="local_test",
        issuer="local://p1d-tests",
        subject=subject,
        display_name=display_name,
        email=f"{subject}@example.test",
        status=status,
        roles=[role],
    )


@pytest.fixture()
def api_client():
    app_module, _, repository_module = _platform_modules()
    assertions = {
        "admin-token": _identity("admin", "Platform Admin"),
        "curator-token": _identity("curator", "Knowledge Curator"),
        "consumer-token": _identity("consumer", "Knowledge Consumer"),
        "reviewer-token": _identity("reviewer", "Knowledge Reviewer"),
        "disabled-token": _identity("disabled", "Disabled User"),
        "unmapped-token": _identity("unmapped", "Unmapped User"),
    }
    identity_provider = LocalIdentityProvider(
        environment="test",
        token_assertions=assertions,
    )
    repository = FakePlatformRepository(repository_module)
    grants = [
        _grant("admin", "Platform Admin", "platform_admin"),
        _grant("curator", "Knowledge Curator", "knowledge_curator"),
        _grant("consumer", "Knowledge Consumer", "consumer"),
        _grant("reviewer", "Knowledge Reviewer", "reviewer"),
        _grant("disabled", "Disabled User", "consumer", status="disabled"),
    ]
    for grant in grants:
        repository.add_grant(grant)
        repository.users.append(
            repository_module.PlatformUserRecord(
                user_id=grant.user_id,
                display_name=grant.display_name,
                email=grant.email,
                identity_source=grant.identity_source.value,
                roles=tuple(sorted(role.value for role in grant.roles)),
                status=grant.status.value,
                last_active_at=None,
            )
        )
    services = app_module.PlatformApiServices(
        identity_provider=identity_provider,
        repository=repository,
        organization_name="Clinical Knowledge Lab",
        object_store_available=False,
        semantic_index_available=False,
        source_registry=FakeSourceRegistry(),
        processing_ledger=FakeProcessingLedger(),
        governance=FakeGovernanceService(),
    )
    return TestClient(app_module.create_platform_app(services)), repository


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_is_public_and_reports_unimplemented_capabilities(api_client) -> None:
    client, _ = api_client

    response = client.get(f"{API_PREFIX}/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["fixture"] is False
    assert payload["data"]["status"] == "degraded"
    assert payload["data"]["api"] == "available"
    assert payload["data"]["database"] == "available"
    assert payload["data"]["objectStore"] == "disabled"
    assert payload["data"]["semanticIndex"] == "disabled"


def test_health_reports_database_failure_without_exposing_an_exception(api_client) -> None:
    client, repository = api_client
    repository.database_is_available = False

    response = client.get(f"{API_PREFIX}/health")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "degraded"
    assert response.json()["data"]["database"] == "degraded"


@pytest.mark.parametrize(
    ("token", "expected_code"),
    [
        (None, "authentication_required"),
        ("unknown-token", "invalid_identity"),
        ("unmapped-token", "invalid_identity"),
        ("disabled-token", "invalid_identity"),
    ],
)
def test_session_fails_closed_for_missing_invalid_unmapped_or_disabled_identity(
    api_client,
    token: str | None,
    expected_code: str,
) -> None:
    client, _ = api_client
    headers = _auth(token) if token else {}

    response = client.get(f"{API_PREFIX}/session", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == expected_code
    assert "unknown-token" not in response.text


def test_session_returns_internal_actor_roles_and_never_identity_claims(api_client) -> None:
    client, _ = api_client

    response = client.get(f"{API_PREFIX}/session", headers=_auth("admin-token"))

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["actorId"] == "usr-admin"
    assert data["principalType"] == "human"
    assert data["roles"] == ["platform_admin"]
    assert "admin:read" in data["permissions"]
    assert "review:decide" not in data["permissions"]
    assert {"issuer", "subject", "claims", "token", "secret"}.isdisjoint(data)


def test_backend_permissions_protect_sources_release_and_admin(api_client) -> None:
    client, _ = api_client

    assert client.get(f"{API_PREFIX}/sources", headers=_auth("admin-token")).status_code == 200
    assert client.get(f"{API_PREFIX}/admin/users", headers=_auth("admin-token")).status_code == 200
    assert (
        client.get(
            f"{API_PREFIX}/releases/current",
            headers=_auth("consumer-token"),
        ).status_code
        == 200
    )
    assert client.get(f"{API_PREFIX}/sources", headers=_auth("consumer-token")).status_code == 403
    assert (
        client.get(f"{API_PREFIX}/admin/users", headers=_auth("curator-token")).status_code == 403
    )


def test_repository_failure_is_a_sanitized_service_unavailable_response(api_client) -> None:
    client, repository = api_client
    repository.source_read_fails = True

    response = client.get(f"{API_PREFIX}/sources", headers=_auth("admin-token"))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert "SELECT" not in response.text


def test_real_read_routes_return_database_views_not_fixtures_or_secrets(api_client) -> None:
    client, _ = api_client

    sources = client.get(f"{API_PREFIX}/sources", headers=_auth("admin-token")).json()
    users = client.get(f"{API_PREFIX}/admin/users", headers=_auth("admin-token")).json()
    release = client.get(
        f"{API_PREFIX}/releases/current",
        headers=_auth("admin-token"),
    ).json()

    assert sources["meta"]["fixture"] is False
    assert sources["data"]["items"][0]["sourceId"] == "src-sdtmig-34"
    assert sources["data"]["items"][0]["sourceHash"] == "a" * 64
    assert release["data"]["releaseId"] == "rel-001"
    assert users["data"]["items"][0]["identitySource"] == "local_test"
    assert users["data"]["items"][0]["roles"] == ["platform_admin"]
    assert all(
        {"issuer", "subject", "secretRef", "password", "accessToken"}.isdisjoint(item)
        for item in users["data"]["items"]
    )


def test_source_registration_returns_202_run_and_never_confuses_object_with_evidence(
    api_client,
) -> None:
    client, _ = api_client
    content = b"# Source\n\nGoverned evidence."

    response = client.post(
        f"{API_PREFIX}/sources",
        headers={
            **_auth("curator-token"),
            "Idempotency-Key": "source-upload-api-001",
        },
        data={
            "source_id": "src-upload",
            "title": "Uploaded Markdown",
            "source_type": "standard",
            "version": "1.0",
            "rights_classification": "internal",
            "storage_allowed": "true",
            "data_boundary": "local_processing_only",
            "media_type": "text/markdown",
            "expected_sha256": sha256(content).hexdigest(),
        },
        files={"file": ("source.md", content, "text/markdown")},
    )

    assert response.status_code == 202
    data = response.json()["data"]
    assert data["runId"] == "run-upload-001"
    assert data["status"] == "queued"
    assert data["originalObject"]["artifactRole"] == "original"
    assert {"evidence", "candidate", "knowledge", "release"}.isdisjoint(data)

    forbidden = client.post(
        f"{API_PREFIX}/sources",
        headers={
            **_auth("consumer-token"),
            "Idempotency-Key": "source-upload-api-002",
        },
        data={
            "source_id": "src-upload",
            "title": "Uploaded Markdown",
            "source_type": "standard",
            "version": "1.0",
            "rights_classification": "internal",
            "storage_allowed": "true",
            "data_boundary": "local_processing_only",
            "media_type": "text/markdown",
            "expected_sha256": sha256(content).hexdigest(),
        },
        files={"file": ("source.md", content, "text/markdown")},
    )
    assert forbidden.status_code == 403


def test_processing_routes_expose_discrete_run_state_retry_and_cancel(api_client) -> None:
    client, _ = api_client

    collection = client.get(
        f"{API_PREFIX}/processing-runs",
        headers=_auth("curator-token"),
    )
    detail = client.get(
        f"{API_PREFIX}/processing-runs/run-api-001",
        headers=_auth("curator-token"),
    )
    retry = client.post(
        (f"{API_PREFIX}/processing-runs/run-api-001/steps/step-api-001/retry"),
        headers=_auth("curator-token"),
    )
    cancel = client.post(
        f"{API_PREFIX}/processing-runs/run-api-001/cancel",
        headers=_auth("curator-token"),
    )

    assert collection.status_code == 200
    assert detail.status_code == 200
    run = detail.json()["data"]
    assert run["originalArtifactCount"] == 1
    assert run["derivedArtifactCount"] == 0
    assert run["evidenceCount"] == 0
    assert run["steps"][0]["latestAttempt"]["status"] == "queued"
    assert {"chunk", "watermark", "partition", "tokenStream"}.isdisjoint(run)
    assert retry.status_code == 202
    assert retry.json()["data"]["attemptId"] == "attempt-api-002"
    assert cancel.status_code == 202
    assert cancel.json()["data"]["status"] == "cancelled"


def test_candidate_routes_project_gate_state_and_enforce_separate_permissions(
    api_client,
) -> None:
    client, _ = api_client

    collection = client.get(
        f"{API_PREFIX}/candidates",
        headers=_auth("curator-token"),
    )
    assert collection.status_code == 200
    item = collection.json()["data"]["items"][0]
    assert item["status"] == "author_confirmation_required"
    assert item["reviewStatus"] is None
    assert item["evidenceCount"] == 1

    confirmation = client.post(
        f"{API_PREFIX}/candidates/cand-api-001/author-confirmation",
        headers=_auth("curator-token"),
        json={
            "expectedRevisionNumber": 1,
            "expectedContentSha256": "b" * 64,
            "idempotencyKey": "api-author-confirm-001",
        },
    )
    assert confirmation.status_code == 200
    assert confirmation.json()["data"]["candidateStatus"] == "author_confirmed"
    assert confirmation.json()["data"]["revisionStatus"] == "review_required"

    forbidden_author = client.post(
        f"{API_PREFIX}/candidates/cand-api-001/author-confirmation",
        headers=_auth("reviewer-token"),
        json={
            "expectedRevisionNumber": 1,
            "expectedContentSha256": "b" * 64,
            "idempotencyKey": "api-author-forbidden-001",
        },
    )
    assert forbidden_author.status_code == 403

    review = client.post(
        f"{API_PREFIX}/knowledge-revisions/krev-api-001/review-decision",
        headers=_auth("reviewer-token"),
        json={
            "candidateId": "cand-api-001",
            "expectedRevisionNumber": 1,
            "expectedContentSha256": "b" * 64,
            "decision": "approved",
            "idempotencyKey": "api-review-approve-001",
            "rationale": "Evidence and applicability confirmed.",
        },
    )
    assert review.status_code == 200
    assert review.json()["data"]["revisionStatus"] == "approved"


def test_candidate_detail_exposes_evidence_and_revision_write_is_versioned(api_client) -> None:
    client, _ = api_client

    detail = client.get(
        f"{API_PREFIX}/candidates/cand-api-001",
        headers=_auth("curator-token"),
    )
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["evidence"][0]["locator"] == {"page": 35, "section": "6.2 AE"}
    assert data["evidence"][0]["rights"]["classification"] == "licensed"
    assert data["relationProposals"][0]["relationType"] == "applies_to"

    revision = client.post(
        f"{API_PREFIX}/candidates/cand-api-001/revisions",
        headers=_auth("curator-token"),
        json={
            "expectedRevisionNumber": 1,
            "expectedContentSha256": "b" * 64,
            "claim": "AESEQ identifies records in the SDTM AE domain.",
            "scope": {"standard": "SDTM", "domain": "AE"},
            "applicability": {"standard_version": "3.4"},
            "conditions": [],
            "exceptions": [],
            "idempotencyKey": "api-candidate-revision-002",
        },
    )
    assert revision.status_code == 201
    assert revision.json()["data"] == {
        "candidateId": "cand-api-002",
        "parentCandidateId": "cand-api-001",
        "revisionNumber": 2,
        "contentSha256": "c" * 64,
        "status": "author_confirmation_required",
    }


def _openapi_component_schema(spec: dict[str, Any], name: str) -> dict[str, Any]:
    definitions = deepcopy(spec["components"]["schemas"])

    def rewrite(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    item.replace("#/components/schemas/", "#/$defs/")
                    if key == "$ref" and isinstance(item, str)
                    else rewrite(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        return value

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": rewrite(definitions),
        "$ref": f"#/$defs/{name}",
    }


def test_checked_in_openapi_matches_runtime_paths_roles_and_responses(api_client) -> None:
    client, _ = api_client
    spec = yaml.safe_load(
        (ROOT / "schemas" / "application" / "knowledge-api.prerelease.yaml").read_text(
            encoding="utf-8"
        )
    )
    runtime_spec = client.app.openapi()
    runtime_paths = {path for path in runtime_spec["paths"] if path.startswith(API_PREFIX)}
    checked_paths = {f"{API_PREFIX}{path}" for path in spec["paths"]}

    assert (
        runtime_paths
        == checked_paths
        == {
            f"{API_PREFIX}/session",
            f"{API_PREFIX}/health",
            f"{API_PREFIX}/releases/current",
            f"{API_PREFIX}/sources",
            f"{API_PREFIX}/processing-runs",
            f"{API_PREFIX}/processing-runs/{{run_id}}",
            (f"{API_PREFIX}/processing-runs/{{run_id}}/steps/{{step_id}}/retry"),
            f"{API_PREFIX}/processing-runs/{{run_id}}/cancel",
            f"{API_PREFIX}/candidates",
            f"{API_PREFIX}/candidates/{{candidate_id}}",
            f"{API_PREFIX}/candidates/{{candidate_id}}/revisions",
            f"{API_PREFIX}/candidates/{{candidate_id}}/author-confirmation",
            f"{API_PREFIX}/knowledge-revisions/{{revision_id}}/review-decision",
            f"{API_PREFIX}/admin/users",
        }
    )
    assert spec["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"
    assert spec["components"]["schemas"]["HumanRole"]["enum"] == [
        "platform_admin",
        "knowledge_curator",
        "reviewer",
        "release_manager",
        "consumer",
    ]
    assert spec["components"]["schemas"]["IdentitySource"]["enum"] == [
        "local_test",
        "oidc",
    ]
    assert runtime_spec["paths"][f"{API_PREFIX}/health"]["get"].get("security") is None
    assert runtime_spec["paths"][f"{API_PREFIX}/session"]["get"]["security"] == [{"bearerAuth": []}]

    response_cases = [
        ("HealthResponse", client.get(f"{API_PREFIX}/health")),
        (
            "SessionResponse",
            client.get(f"{API_PREFIX}/session", headers=_auth("admin-token")),
        ),
        (
            "CurrentReleaseResponse",
            client.get(f"{API_PREFIX}/releases/current", headers=_auth("admin-token")),
        ),
        (
            "SourceCollectionResponse",
            client.get(f"{API_PREFIX}/sources", headers=_auth("admin-token")),
        ),
        (
            "ProcessingRunCollectionResponse",
            client.get(
                f"{API_PREFIX}/processing-runs",
                headers=_auth("admin-token"),
            ),
        ),
        (
            "ProcessingRunResponse",
            client.get(
                f"{API_PREFIX}/processing-runs/run-api-001",
                headers=_auth("admin-token"),
            ),
        ),
        (
            "CandidateCollectionResponse",
            client.get(
                f"{API_PREFIX}/candidates",
                headers=_auth("admin-token"),
            ),
        ),
        (
            "UserCollectionResponse",
            client.get(f"{API_PREFIX}/admin/users", headers=_auth("admin-token")),
        ),
    ]
    for component_name, response in response_cases:
        assert response.status_code == 200
        Draft202012Validator(_openapi_component_schema(spec, component_name)).validate(
            response.json()
        )


def test_api_dtos_are_pydantic_models_separate_from_sqlalchemy_metadata() -> None:
    _, contracts_module, _ = _platform_modules()

    assert contracts_module.SessionResponse.__module__ == "service.platform_api.contracts"
    assert not hasattr(contracts_module.SessionResponse, "__table__")
