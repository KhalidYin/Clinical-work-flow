from __future__ import annotations

from importlib import import_module

import pytest
from pydantic import ValidationError

from service.auth import (
    ActorContext,
    IdentitySource,
    Permission,
    PrincipalType,
    ProductRole,
    SeparationOfDutiesError,
    WorkerPool,
)


def _contracts():
    return import_module("service.knowledge.contracts")


def _governance():
    return import_module("service.governance.service")


def _human(
    *,
    actor_id: str,
    role: ProductRole,
    permissions: set[Permission],
) -> ActorContext:
    return ActorContext(
        actor_id=actor_id,
        display_name=actor_id,
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({role}),
        permissions=frozenset(permissions),
        identity_source=IdentitySource.OIDC,
    )


def _worker(*, pool: WorkerPool, permissions: set[Permission]) -> ActorContext:
    return ActorContext(
        actor_id=f"svc-{pool.value}",
        display_name=f"{pool.value} worker",
        principal_type=PrincipalType.SERVICE_ACCOUNT,
        roles=frozenset({ProductRole.SERVICE_ACCOUNT}),
        permissions=frozenset(permissions),
        worker_pool=pool,
    )


def _eligible_draft():
    contract = _contracts()
    return contract.KnowledgeCandidateDraft(
        candidate_group_id="candgrp-ae-seq",
        run_id="run-ae",
        revision_number=1,
        knowledge_type="variable_definition",
        claim="AESEQ is the sequence identifier within the AE domain.",
        scope={"standard": "SDTM", "domain": "AE"},
        applicability={"standard_version": "3.4"},
        evidence=[
            {
                "evidence_id": "ev-ae-1",
                "source_version_id": "srcv-sdtm-34",
                "locator": {"page": 35, "section": "6.2 AE"},
                "content_sha256": "a" * 64,
                "rights": {
                    "classification": "licensed",
                    "storage_allowed": True,
                    "citation_required": True,
                },
            }
        ],
        relation_proposals=[
            {
                "relation_type": "applies_to",
                "target_knowledge_unit_id": "ku-sdtm-ae",
                "evidence_ids": ["ev-ae-1"],
            }
        ],
    )


def test_candidate_eligibility_requires_traceable_evidence_rights_and_applicability() -> None:
    contract = _contracts()
    valid = _eligible_draft()
    assert valid.evidence[0].source_version_id == "srcv-sdtm-34"

    payload = valid.model_dump(mode="json")
    payload["evidence"][0]["locator"] = {}
    with pytest.raises(ValidationError, match="locator"):
        contract.KnowledgeCandidateDraft.model_validate(payload)

    payload = valid.model_dump(mode="json")
    payload["evidence"][0]["rights"]["storage_allowed"] = False
    with pytest.raises(ValidationError, match="storage"):
        contract.KnowledgeCandidateDraft.model_validate(payload)

    payload = valid.model_dump(mode="json")
    payload["applicability"] = {}
    with pytest.raises(ValidationError, match="applicability"):
        contract.KnowledgeCandidateDraft.model_validate(payload)

    payload = valid.model_dump(mode="json")
    payload["evidence"] = []
    with pytest.raises(ValidationError, match="evidence"):
        contract.KnowledgeCandidateDraft.model_validate(payload)


def test_relation_proposal_requires_allowed_type_existing_endpoint_and_edge_evidence() -> None:
    contract = _contracts()
    valid = _eligible_draft()

    payload = valid.model_dump(mode="json")
    payload["relation_proposals"][0]["relation_type"] = "invented_relation"
    with pytest.raises(ValidationError, match="relation_type"):
        contract.KnowledgeCandidateDraft.model_validate(payload)

    payload = valid.model_dump(mode="json")
    payload["relation_proposals"][0]["target_knowledge_unit_id"] = ""
    with pytest.raises(ValidationError, match="target_knowledge_unit_id"):
        contract.KnowledgeCandidateDraft.model_validate(payload)

    payload = valid.model_dump(mode="json")
    payload["relation_proposals"][0]["evidence_ids"] = ["ev-not-attached"]
    with pytest.raises(ValidationError, match="edge evidence"):
        contract.KnowledgeCandidateDraft.model_validate(payload)


def test_advisory_signals_are_evidence_grounded_and_match_relation_meaning() -> None:
    contract = _contracts()
    valid = _eligible_draft()

    payload = valid.model_dump(mode="json")
    payload["advisory_signals"] = [
        {
            "signal_type": "explicit_gap",
            "description": "The source does not define a sponsor-specific exception.",
            "target_knowledge_unit_id": "ku-sdtm-ae",
            "evidence_ids": ["ev-ae-1"],
        }
    ]
    with pytest.raises(ValidationError, match="must not identify"):
        contract.KnowledgeCandidateDraft.model_validate(payload)

    payload = valid.model_dump(mode="json")
    payload["advisory_signals"] = [
        {
            "signal_type": "possible_duplicate",
            "description": "The claim may duplicate the governed AE variable definition.",
            "target_knowledge_unit_id": "ku-sdtm-ae",
            "evidence_ids": ["ev-not-attached"],
        }
    ]
    with pytest.raises(ValidationError, match="must belong"):
        contract.KnowledgeCandidateDraft.model_validate(payload)

    payload = valid.model_dump(mode="json")
    payload["relation_proposals"] = [
        {
            "relation_type": "conflicts_with",
            "target_knowledge_unit_id": "ku-sdtm-ae",
            "evidence_ids": ["ev-ae-1"],
        }
    ]
    with pytest.raises(ValidationError, match="possible_conflict"):
        contract.KnowledgeCandidateDraft.model_validate(payload)

    payload["advisory_signals"] = [
        {
            "signal_type": "possible_conflict",
            "description": "The proposed rule may conflict with the governed AE rule.",
            "target_knowledge_unit_id": "ku-sdtm-ae",
            "evidence_ids": ["ev-ae-1"],
        }
    ]
    candidate = contract.KnowledgeCandidateDraft.model_validate(payload)
    assert candidate.advisory_signals[0].signal_type.value == "possible_conflict"


def test_relation_semantics_reject_self_cycle_closure_and_invalid_supersession() -> None:
    contract = _contracts()
    governance = _governance()
    source_id = contract.knowledge_unit_id_for_candidate_group("candgrp-ae-seq")
    worker = _worker(
        pool=WorkerPool.ENRICHMENT,
        permissions={Permission.CANDIDATE_WRITE, Permission.RELATION_PROPOSE},
    )

    self_payload = _eligible_draft().model_dump(mode="json")
    self_payload["relation_proposals"][0]["target_knowledge_unit_id"] = source_id
    self_repository = governance.InMemoryGovernanceRepository(
        runs={"run-ae": "evidence_ready"},
        evidence_ids={"ev-ae-1"},
        knowledge_unit_ids={source_id},
    )
    with pytest.raises(governance.CandidateEligibilityError, match="own knowledge unit"):
        governance.KnowledgeGovernanceService(
            repository=self_repository
        ).register_candidate(
            actor=worker,
            draft=contract.KnowledgeCandidateDraft.model_validate(self_payload),
        )
    assert self_repository.candidates == ()

    cycle_payload = _eligible_draft().model_dump(mode="json")
    cycle_payload["relation_proposals"][0] = {
        "relation_type": "depends_on",
        "target_knowledge_unit_id": "ku-b",
        "evidence_ids": ["ev-ae-1"],
    }
    cycle_repository = governance.InMemoryGovernanceRepository(
        runs={"run-ae": "evidence_ready"},
        evidence_ids={"ev-ae-1"},
        knowledge_unit_ids={"ku-b", source_id},
        relation_edges={("ku-b", "depends_on", source_id)},
    )
    with pytest.raises(governance.CandidateEligibilityError, match="cycle"):
        governance.KnowledgeGovernanceService(
            repository=cycle_repository
        ).register_candidate(
            actor=worker,
            draft=contract.KnowledgeCandidateDraft.model_validate(cycle_payload),
        )

    closure_payload = _eligible_draft().model_dump(mode="json")
    closure_payload["relation_proposals"] = [
        {
            "relation_type": "depends_on",
            "target_knowledge_unit_id": target,
            "evidence_ids": ["ev-ae-1"],
        }
        for target in ("ku-b", "ku-c")
    ]
    closure_repository = governance.InMemoryGovernanceRepository(
        runs={"run-ae": "evidence_ready"},
        evidence_ids={"ev-ae-1"},
        knowledge_unit_ids={"ku-b", "ku-c"},
        relation_edges={("ku-b", "depends_on", "ku-c")},
    )
    with pytest.raises(governance.CandidateEligibilityError, match="transitive closure"):
        governance.KnowledgeGovernanceService(
            repository=closure_repository
        ).register_candidate(
            actor=worker,
            draft=contract.KnowledgeCandidateDraft.model_validate(closure_payload),
        )

    supersedes_payload = _eligible_draft().model_dump(mode="json")
    supersedes_payload["relation_proposals"][0] = {
        "relation_type": "supersedes",
        "target_knowledge_unit_id": "ku-old",
        "evidence_ids": ["ev-ae-1"],
    }
    supersedes_payload["advisory_signals"] = [
        {
            "signal_type": "possible_duplicate",
            "description": "The candidate may replace the governed prior rule.",
            "target_knowledge_unit_id": "ku-old",
            "evidence_ids": ["ev-ae-1"],
        }
    ]
    supersedes_repository = governance.InMemoryGovernanceRepository(
        runs={"run-ae": "evidence_ready"},
        evidence_ids={"ev-ae-1"},
        knowledge_unit_ids={"ku-old"},
    )
    service = governance.KnowledgeGovernanceService(
        repository=supersedes_repository
    )
    with pytest.raises(governance.CandidateEligibilityError, match="governed revision"):
        service.register_candidate(
            actor=worker,
            draft=contract.KnowledgeCandidateDraft.model_validate(
                supersedes_payload
            ),
        )
    governed_repository = governance.InMemoryGovernanceRepository(
        runs={"run-ae": "evidence_ready"},
        evidence_ids={"ev-ae-1"},
        knowledge_unit_ids={"ku-old"},
        governed_knowledge_unit_ids={"ku-old"},
    )
    accepted = governance.KnowledgeGovernanceService(
        repository=governed_repository
    ).register_candidate(
        actor=worker,
        draft=contract.KnowledgeCandidateDraft.model_validate(supersedes_payload),
    )
    assert accepted.relation_proposals[0].relation_type.value == "supersedes"

    conflict_payload = _eligible_draft().model_dump(mode="json")
    conflict_payload["relation_proposals"] = [
        {
            "relation_type": relation_type,
            "target_knowledge_unit_id": "ku-target",
            "evidence_ids": ["ev-ae-1"],
        }
        for relation_type in ("conflicts_with", "supports")
    ]
    conflict_payload["advisory_signals"] = [
        {
            "signal_type": "possible_conflict",
            "description": "The candidate conflicts with the target rule.",
            "target_knowledge_unit_id": "ku-target",
            "evidence_ids": ["ev-ae-1"],
        }
    ]
    conflict_repository = governance.InMemoryGovernanceRepository(
        runs={"run-ae": "evidence_ready"},
        evidence_ids={"ev-ae-1"},
        knowledge_unit_ids={"ku-target"},
    )
    with pytest.raises(governance.CandidateEligibilityError, match="cannot coexist"):
        governance.KnowledgeGovernanceService(
            repository=conflict_repository
        ).register_candidate(
            actor=worker,
            draft=contract.KnowledgeCandidateDraft.model_validate(conflict_payload),
        )


def test_advisory_and_relation_targets_must_be_canonical_units() -> None:
    contract = _contracts()
    governance = _governance()
    payload = _eligible_draft().model_dump(mode="json")
    payload["advisory_signals"] = [
        {
            "signal_type": "possible_duplicate",
            "description": "The candidate may duplicate an unresolved target.",
            "target_knowledge_unit_id": "ku-missing",
            "evidence_ids": ["ev-ae-1"],
        }
    ]
    repository = governance.InMemoryGovernanceRepository(
        runs={"run-ae": "evidence_ready"},
        evidence_ids={"ev-ae-1"},
        knowledge_unit_ids={"ku-sdtm-ae"},
    )

    with pytest.raises(governance.CandidateEligibilityError, match="advisory target"):
        governance.KnowledgeGovernanceService(repository=repository).register_candidate(
            actor=_worker(
                pool=WorkerPool.ENRICHMENT,
                permissions={
                    Permission.CANDIDATE_WRITE,
                    Permission.RELATION_PROPOSE,
                },
            ),
            draft=contract.KnowledgeCandidateDraft.model_validate(payload),
        )
    assert repository.candidates == ()


def test_candidate_is_persisted_before_author_confirmation_and_author_precedes_review() -> None:
    contract = _contracts()
    governance = _governance()
    repository = governance.InMemoryGovernanceRepository(
        runs={"run-ae": "evidence_ready"},
        evidence_ids={"ev-ae-1"},
        knowledge_unit_ids={"ku-sdtm-ae"},
    )
    service = governance.KnowledgeGovernanceService(repository=repository)
    enrichment = _worker(
        pool=WorkerPool.ENRICHMENT,
        permissions={Permission.CANDIDATE_WRITE, Permission.RELATION_PROPOSE},
    )
    author = _human(
        actor_id="usr-author",
        role=ProductRole.KNOWLEDGE_CURATOR,
        permissions={Permission.CANDIDATE_SUBMIT},
    )
    reviewer = _human(
        actor_id="usr-reviewer",
        role=ProductRole.REVIEWER,
        permissions={Permission.REVIEW_DECIDE},
    )

    with pytest.raises(governance.CandidateNotFoundError):
        service.confirm_candidate(
            actor=author,
            command=contract.AuthorConfirmationCommand(
                candidate_id="cand-missing",
                expected_revision_number=1,
                expected_content_sha256="a" * 64,
                idempotency_key="author-confirm-missing",
            ),
        )
    assert repository.run_status("run-ae") == "evidence_ready"

    candidate = service.register_candidate(
        actor=enrichment,
        draft=_eligible_draft(),
    )
    assert candidate.status is contract.CandidateStatus.AUTHOR_CONFIRMATION_REQUIRED
    assert repository.run_status("run-ae") == "author_confirmation_required"

    with pytest.raises(governance.InvalidGovernanceTransitionError, match="author"):
        service.review_revision(
            actor=reviewer,
            command=contract.ReviewDecisionCommand(
                candidate_id=candidate.candidate_id,
                knowledge_revision_id="krev-missing",
                expected_revision_number=1,
                expected_content_sha256=candidate.content_sha256,
                decision="approved",
                idempotency_key="review-before-author",
            ),
        )

    confirmation = service.confirm_candidate(
        actor=author,
        command=contract.AuthorConfirmationCommand(
            candidate_id=candidate.candidate_id,
            expected_revision_number=1,
            expected_content_sha256=candidate.content_sha256,
            idempotency_key="author-confirm-ae-1",
        ),
    )
    assert confirmation.revision.status is contract.KnowledgeRevisionStatus.REVIEW_REQUIRED
    assert repository.run_status("run-ae") == "review_required"

    approval = service.review_revision(
        actor=reviewer,
        command=contract.ReviewDecisionCommand(
            candidate_id=candidate.candidate_id,
            knowledge_revision_id=confirmation.revision.knowledge_revision_id,
            expected_revision_number=1,
            expected_content_sha256=confirmation.revision.content_sha256,
            decision="approved",
            idempotency_key="review-approve-ae-1",
        ),
    )
    assert approval.revision.status is contract.KnowledgeRevisionStatus.APPROVED
    assert repository.run_status("run-ae") == "approved"
    assert [event.action for event in repository.audit_events] == [
        "candidate.created",
        "candidate.author_confirmed",
        "knowledge_revision.approved",
    ]


def test_stale_duplicate_self_review_and_worker_decisions_fail_closed() -> None:
    contract = _contracts()
    governance = _governance()
    repository = governance.InMemoryGovernanceRepository(
        runs={"run-ae": "evidence_ready"},
        evidence_ids={"ev-ae-1"},
        knowledge_unit_ids={"ku-sdtm-ae"},
    )
    service = governance.KnowledgeGovernanceService(repository=repository)
    candidate = service.register_candidate(
        actor=_worker(
            pool=WorkerPool.ENRICHMENT,
            permissions={Permission.CANDIDATE_WRITE, Permission.RELATION_PROPOSE},
        ),
        draft=_eligible_draft(),
    )
    author = _human(
        actor_id="usr-author",
        role=ProductRole.KNOWLEDGE_CURATOR,
        permissions={Permission.CANDIDATE_SUBMIT},
    )
    reviewer = _human(
        actor_id="usr-reviewer",
        role=ProductRole.REVIEWER,
        permissions={Permission.REVIEW_DECIDE},
    )

    with pytest.raises(governance.StaleRevisionError):
        service.confirm_candidate(
            actor=author,
            command=contract.AuthorConfirmationCommand(
                candidate_id=candidate.candidate_id,
                expected_revision_number=2,
                expected_content_sha256=candidate.content_sha256,
                idempotency_key="author-stale-ae-1",
            ),
        )

    confirmation_command = contract.AuthorConfirmationCommand(
        candidate_id=candidate.candidate_id,
        expected_revision_number=1,
        expected_content_sha256=candidate.content_sha256,
        idempotency_key="author-confirm-ae-1",
    )
    confirmation = service.confirm_candidate(actor=author, command=confirmation_command)
    with pytest.raises(governance.DuplicateDecisionError):
        service.confirm_candidate(actor=author, command=confirmation_command)

    with pytest.raises(SeparationOfDutiesError):
        service.review_revision(
            actor=author.model_copy(update={"permissions": frozenset({Permission.REVIEW_DECIDE})}),
            command=contract.ReviewDecisionCommand(
                candidate_id=candidate.candidate_id,
                knowledge_revision_id=confirmation.revision.knowledge_revision_id,
                expected_revision_number=1,
                expected_content_sha256=confirmation.revision.content_sha256,
                decision="approved",
                idempotency_key="author-self-review-ae-1",
            ),
        )

    document_worker = _worker(
        pool=WorkerPool.DOCUMENT,
        permissions={Permission.EVIDENCE_WRITE},
    )
    with pytest.raises(governance.AuthorizationError):
        service.confirm_candidate(actor=document_worker, command=confirmation_command)

    review_command = contract.ReviewDecisionCommand(
        candidate_id=candidate.candidate_id,
        knowledge_revision_id=confirmation.revision.knowledge_revision_id,
        expected_revision_number=1,
        expected_content_sha256=confirmation.revision.content_sha256,
        decision="approved",
        idempotency_key="review-approve-ae-1",
    )
    service.review_revision(actor=reviewer, command=review_command)
    with pytest.raises(governance.DuplicateDecisionError):
        service.review_revision(actor=reviewer, command=review_command)


def test_released_revision_is_immutable_and_retirement_is_a_new_governance_fact() -> None:
    contract = _contracts()

    released = contract.KnowledgeRevisionRecord(
        knowledge_revision_id="krev-ae-1",
        knowledge_unit_id="ku-aeseq",
        candidate_id="cand-ae-1",
        revision_number=1,
        status="released",
        claim="AESEQ is the sequence identifier within the AE domain.",
        scope={"standard": "SDTM", "domain": "AE"},
        applicability={"standard_version": "3.4"},
        conditions=[],
        exceptions=[],
        content_sha256="b" * 64,
        author_actor_id="usr-author",
    )

    with pytest.raises(contract.ReleasedRevisionImmutableError):
        contract.require_revision_mutable(released)
    assert contract.KnowledgeRevisionStatus.RETIRED.value == "retired"
    assert contract.KnowledgeRevisionStatus.SUPERSEDED.value == "superseded"


def test_change_request_creates_a_new_candidate_revision_without_overwriting_history() -> None:
    contract = _contracts()
    governance = _governance()
    repository = governance.InMemoryGovernanceRepository(
        runs={"run-ae": "evidence_ready"},
        evidence_ids={"ev-ae-1"},
        knowledge_unit_ids={"ku-sdtm-ae"},
    )
    service = governance.KnowledgeGovernanceService(repository=repository)
    enrichment = _worker(
        pool=WorkerPool.ENRICHMENT,
        permissions={Permission.CANDIDATE_WRITE, Permission.RELATION_PROPOSE},
    )
    author = _human(
        actor_id="usr-author",
        role=ProductRole.KNOWLEDGE_CURATOR,
        permissions={
            Permission.CANDIDATE_WRITE,
            Permission.CANDIDATE_SUBMIT,
            Permission.RELATION_PROPOSE,
        },
    )
    reviewer = _human(
        actor_id="usr-reviewer",
        role=ProductRole.REVIEWER,
        permissions={Permission.REVIEW_DECIDE},
    )
    first = service.register_candidate(actor=enrichment, draft=_eligible_draft())
    confirmed = service.confirm_candidate(
        actor=author,
        command=contract.AuthorConfirmationCommand(
            candidate_id=first.candidate_id,
            expected_revision_number=1,
            expected_content_sha256=first.content_sha256,
            idempotency_key="author-confirm-change-1",
        ),
    )
    service.review_revision(
        actor=reviewer,
        command=contract.ReviewDecisionCommand(
            candidate_id=first.candidate_id,
            knowledge_revision_id=confirmed.revision.knowledge_revision_id,
            expected_revision_number=1,
            expected_content_sha256=confirmed.revision.content_sha256,
            decision="changes_requested",
            idempotency_key="review-change-1",
            rationale="Clarify the scope.",
        ),
    )

    second = service.revise_candidate(
        actor=author,
        command=contract.CandidateRevisionCommand(
            candidate_id=first.candidate_id,
            expected_revision_number=1,
            expected_content_sha256=first.content_sha256,
            claim="AESEQ is the sequence identifier for records in the SDTM AE domain.",
            scope={"standard": "SDTM", "domain": "AE"},
            applicability={"standard_version": "3.4"},
            conditions=[],
            exceptions=[],
            idempotency_key="author-revise-change-2",
        ),
    )

    assert second.revision_number == 2
    assert second.parent_candidate_id == first.candidate_id
    assert repository.get_candidate(first.candidate_id).status is contract.CandidateStatus.SUPERSEDED
    assert repository.get_revision(confirmed.revision.knowledge_revision_id).status is (
        contract.KnowledgeRevisionStatus.CHANGES_REQUESTED
    )
    assert repository.run_status("run-ae") == "author_confirmation_required"
    assert len(repository.candidates) == 2
