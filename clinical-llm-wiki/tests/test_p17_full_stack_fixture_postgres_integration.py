"""Opt-in PostgreSQL acceptance for the two-stage P17 browser fixture."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.p17_full_stack_fixture import (
    build_publishable_candidate,
    prepare_full_stack_fixture,
    provision_fixture_users,
)
from service.auth import (
    ActorContext,
    IdentitySource,
    PrincipalType,
    ProductRole,
    ROLE_PERMISSIONS,
)
from service.auth.password_sessions import (
    Argon2idPasswordHasher,
    PasswordSessionService,
    SqlAlchemyPasswordSessionRepository,
)
from service.db.session import create_database_engine, create_session_factory
from service.knowledge import (
    RotationDecisionCommand,
    RotationOutcome,
    RotationProposalCommand,
)
from service.object_store import LocalObjectStore
from service.platform_api.repository import SqlAlchemyKnowledgeLifecycleRepository
from service.releases import (
    ImmutableReleaseResolver,
    ReleasePublishCommand,
    ReleasePublisher,
    ReleaseWorkbenchService,
    SqlAlchemyReleaseRepository,
    SqlAlchemyReleaseWorkbenchRepository,
)
from service.releases.repository import ReleaseMembershipError
from service.evaluation import SqlAlchemyEvaluationReadRepository


ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("KNOWLEDGE_TEST_DATABASE_URL")
E9_ASSET = ROOT / ".poc-assets/ich-e9/E9_Guideline.pdf"

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or not E9_ASSET.is_file(),
    reason="KNOWLEDGE_TEST_DATABASE_URL and the validated local E9 asset are required",
)


def _actor(role: ProductRole, actor_id: str) -> ActorContext:
    return ActorContext(
        actor_id=actor_id,
        display_name=f"P17 fixture {role.value}",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({role}),
        permissions=ROLE_PERMISSIONS[role],
        identity_source=IdentitySource.LOCAL_TEST,
    )


def test_full_stack_fixture_preserves_worker_and_human_governance_boundaries(
    tmp_path: Path,
) -> None:
    assert TEST_DATABASE_URL is not None
    object_store_root = tmp_path / "objects"
    fixture = prepare_full_stack_fixture(
        database_url=TEST_DATABASE_URL,
        asset_path=E9_ASSET,
        object_store_root=object_store_root,
    )
    credentials = provision_fixture_users(database_url=TEST_DATABASE_URL)

    engine = create_database_engine(TEST_DATABASE_URL)
    sessions = create_session_factory(engine)
    objects = LocalObjectStore(root=object_store_root)
    release_repository = SqlAlchemyReleaseRepository(
        sessions,
        object_store=objects,
    )
    resolver = ImmutableReleaseResolver(repository=release_repository)
    lifecycle = SqlAlchemyKnowledgeLifecycleRepository(sessions)
    evaluations = SqlAlchemyEvaluationReadRepository(sessions)
    workbench = ReleaseWorkbenchService(
        repository=SqlAlchemyReleaseWorkbenchRepository(
            sessions,
            releases=release_repository,
        )
    )
    manager = _actor(ProductRole.RELEASE_MANAGER, "usr-p17-fixture-manager")
    try:
        password_sessions = PasswordSessionService(
            repository=SqlAlchemyPasswordSessionRepository(sessions),
            hasher=Argon2idPasswordHasher(),
        )
        assert {credential.role for credential in credentials} == {
            ProductRole.KNOWLEDGE_CURATOR,
            ProductRole.REVIEWER,
            ProductRole.RELEASE_MANAGER,
        }
        for credential in credentials:
            login = password_sessions.login(
                username=credential.username,
                password=credential.password,
            )
            assert login.actor.roles == frozenset({credential.role})
            assert login.must_change_password is False

        e9_run = evaluations.get_run(evaluation_run_id=fixture.e9_evaluation_run_id)
        assert e9_run is not None
        assert e9_run.purpose == "retrieval_baseline"
        assert e9_run.outcome == "informational"
        assert e9_run.external_model_requests == 0
        failed_cases = tuple(
            case for case in e9_run.case_results if case.failure_category != "none"
        )
        assert failed_cases
        assert all(case.query_id for case in failed_cases)

        current = resolver.resolve()
        assert current.release_id == fixture.historical_release_id
        stale = workbench.get(
            actor=manager,
            candidate_id=fixture.stale_candidate_id,
        )
        assert "base_release_is_stale" in stale.blockers
        assert stale.allowed_actions == ()

        rotation = lifecycle.get_rotation_case(rotation_case_id=fixture.rotation_case_id)
        assert rotation is not None
        assert rotation.status == "open"
        assert "no_action" in rotation.eligible_outcomes

        with pytest.raises(ReleaseMembershipError, match="must be decided"):
            build_publishable_candidate(
                database_url=TEST_DATABASE_URL,
                object_store_root=object_store_root,
                fixture=fixture,
            )

        proposed = lifecycle.propose_rotation_case(
            actor=_actor(ProductRole.KNOWLEDGE_CURATOR, "usr-p17-fixture-curator"),
            command=RotationProposalCommand(
                rotation_case_id=rotation.rotation_case_id,
                expected_case_version=rotation.case_version,
                outcome=RotationOutcome.NO_ACTION,
                target_knowledge_revision_id=None,
                idempotency_key="p17-fixture-proposal-no-action",
                rationale="Keep the released synthetic fact after explicit review.",
            ),
        )
        decided, decision = lifecycle.decide_rotation_case(
            actor=_actor(ProductRole.REVIEWER, "usr-p17-fixture-reviewer"),
            command=RotationDecisionCommand(
                rotation_case_id=proposed.rotation_case_id,
                expected_case_version=proposed.case_version,
                outcome=RotationOutcome.NO_ACTION,
                target_knowledge_revision_id=None,
                idempotency_key="p17-fixture-decision-no-action",
                rationale="The source changed, but the governed claim remains applicable.",
            ),
        )
        assert decided.status == "decided"
        assert decision.rotation_case_id == rotation.rotation_case_id

        prepared = build_publishable_candidate(
            database_url=TEST_DATABASE_URL,
            object_store_root=object_store_root,
            fixture=fixture,
        )
        assert prepared.release_id == fixture.publishable_candidate_id
        publishable = workbench.get(
            actor=manager,
            candidate_id=prepared.release_id,
        )
        assert publishable.blockers == ()
        assert publishable.allowed_actions == ("publish",)

        ReleasePublisher(
            repository=release_repository,
            object_store=objects,
        ).publish(
            actor=manager,
            command=ReleasePublishCommand(
                release_id=prepared.release_id,
                base_release_id=fixture.historical_release_id,
            ),
        )
        assert resolver.resolve().release_id == fixture.publishable_candidate_id
        assert (
            resolver.resolve(release_id=fixture.historical_release_id).release_id
            == fixture.historical_release_id
        )
        included = lifecycle.get_rotation_case(rotation_case_id=fixture.rotation_case_id)
        assert included is not None
        assert included.status == "included_in_release"
        assert included.included_release_id == fixture.publishable_candidate_id
    finally:
        engine.dispose()
