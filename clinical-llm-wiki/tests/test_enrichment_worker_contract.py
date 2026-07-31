from __future__ import annotations

from importlib import import_module

import pytest

from service.auth import (
    ActorContext,
    Permission,
    PrincipalType,
    ProductRole,
    WorkerPool,
)
from service.governance import InMemoryGovernanceRepository, KnowledgeGovernanceService
from service.knowledge import EvidenceReference
from service.processing.contracts import ClaimedStepAttempt
from service.processing.model_provider import (
    DataBoundary,
    FakeModelProvider,
    ModelProfile,
    PromptProfile,
)
from service.sources import RightsClassification


def _enrichment():
    try:
        return import_module("service.processing.enrichment")
    except ModuleNotFoundError as exc:
        pytest.fail(f"P2-B2 enrichment worker is not implemented: {exc}")


def _actor() -> ActorContext:
    return ActorContext(
        actor_id="svc-enrichment",
        display_name="Enrichment Worker",
        principal_type=PrincipalType.SERVICE_ACCOUNT,
        roles=frozenset({ProductRole.SERVICE_ACCOUNT}),
        permissions=frozenset(
            {
                Permission.EVIDENCE_READ,
                Permission.MODEL_INVOKE,
                Permission.CANDIDATE_WRITE,
                Permission.RELATION_PROPOSE,
                Permission.PROCESSING_EXECUTE,
            }
        ),
        worker_pool=WorkerPool.ENRICHMENT,
    )


def _profile() -> ModelProfile:
    return ModelProfile(
        profile_id="demo-extractor",
        version="1.0.0",
        provider="replay",
        model="atomic-candidate",
        deployment_class="enterprise_managed",
        secret_ref="env://P12_ENRICHMENT_WORKER_TOKEN",
        allowed_data_boundaries=["enterprise_provider_only"],
        capabilities=["structured_generation"],
    )


def _prompt(enrichment) -> PromptProfile:
    return PromptProfile(
        profile_id="atomic-candidate",
        version="1.0.0",
        system_template="Extract one evidence-grounded knowledge candidate.",
        output_schema_id="knowledge-candidate.v1",
        output_schema=enrichment.ENRICHMENT_OUTPUT_SCHEMA,
    )


def _evidence() -> EvidenceReference:
    return EvidenceReference(
        evidence_id="evidence-aeseq",
        source_version_id="srcv-sdtm-demo",
        locator={"section": "AE", "paragraph": 1},
        content_sha256="a" * 64,
        rights={
            "classification": RightsClassification.LICENSED,
            "storage_allowed": True,
            "citation_required": True,
        },
    )


def _claim(attempt_number: int) -> ClaimedStepAttempt:
    return ClaimedStepAttempt(
        run_id="run-sdtm-demo",
        step_id="step-enrichment",
        step_key="enrichment.extract_candidate",
        pool=WorkerPool.ENRICHMENT,
        attempt_id=f"attempt-enrichment-{attempt_number}",
        attempt_number=attempt_number,
        previous_attempt_id=(
            None if attempt_number == 1 else f"attempt-enrichment-{attempt_number - 1}"
        ),
        input_sha256="f" * 64,
        checkpoint=None,
    )


def test_fake_enrichment_creates_one_candidate_and_retry_adds_only_attempt_facts() -> None:
    enrichment = _enrichment()
    governance_repository = InMemoryGovernanceRepository(
        runs={"run-sdtm-demo": "processing"},
        evidence_ids={"evidence-aeseq"},
        knowledge_unit_ids={"ku-sdtm-ae"},
    )
    governance = KnowledgeGovernanceService(repository=governance_repository)
    repository = enrichment.InMemoryEnrichmentRepository(
        contexts={
            "run-sdtm-demo": enrichment.EnrichmentContext(
                run_id="run-sdtm-demo",
                source_version_id="srcv-sdtm-demo",
                data_boundary=DataBoundary.ENTERPRISE_PROVIDER_ONLY,
                evidence=(
                    enrichment.EnrichmentEvidence(
                        reference=_evidence(),
                        content="AESEQ is the sequence identifier within the AE domain.",
                    ),
                ),
            )
        }
    )
    provider = FakeModelProvider(
        output={
            "candidate_group_id": "sdtm.ae.aeseq.definition",
            "knowledge_type": "variable_definition",
            "claim": "AESEQ is the sequence identifier within the AE domain.",
            "scope": {"standard": "SDTM", "domain": "AE"},
            "applicability": {"standard_version": "3.4"},
            "conditions": [],
            "exceptions": [],
            "evidence_ids": ["evidence-aeseq"],
            "relation_proposals": [
                {
                    "relation_type": "applies_to",
                    "target_knowledge_unit_id": "ku-sdtm-ae",
                    "evidence_ids": ["evidence-aeseq"],
                }
            ],
            "advisory_signals": [],
            "confidence": 0.99,
        }
    )
    service = enrichment.EnrichmentWorkerService(
        repository=repository,
        governance=governance,
        provider=provider,
        model_profile=_profile(),
        prompt_profile=_prompt(enrichment),
        actor=_actor(),
    )

    first = service.extract_candidate(_claim(1))
    retry = service.extract_candidate(_claim(2))

    assert first.output_sha256 == retry.output_sha256
    assert len(repository.invocations) == 2
    assert repository.invocations[0].input_sha256 == repository.invocations[1].input_sha256
    assert repository.invocations[0].attempt.attempt_id != repository.invocations[1].attempt.attempt_id
    assert len(governance_repository.candidates) == 1
    assert governance_repository.run_status("run-sdtm-demo") == "author_confirmation_required"


def test_model_output_with_unknown_evidence_cannot_create_a_candidate() -> None:
    enrichment = _enrichment()
    governance_repository = InMemoryGovernanceRepository(
        runs={"run-sdtm-demo": "processing"},
        evidence_ids={"evidence-aeseq"},
        knowledge_unit_ids={"ku-sdtm-ae"},
    )
    repository = enrichment.InMemoryEnrichmentRepository(
        contexts={
            "run-sdtm-demo": enrichment.EnrichmentContext(
                run_id="run-sdtm-demo",
                source_version_id="srcv-sdtm-demo",
                data_boundary=DataBoundary.ENTERPRISE_PROVIDER_ONLY,
                evidence=(
                    enrichment.EnrichmentEvidence(
                        reference=_evidence(),
                        content="AESEQ is the sequence identifier within the AE domain.",
                    ),
                ),
            )
        }
    )
    service = enrichment.EnrichmentWorkerService(
        repository=repository,
        governance=KnowledgeGovernanceService(
            repository=governance_repository
        ),
        provider=FakeModelProvider(
            output={
                "candidate_group_id": "sdtm.ae.unverified",
                "knowledge_type": "variable_definition",
                "claim": "This claim has no canonical Evidence reference.",
                "scope": {"standard": "SDTM", "domain": "AE"},
                "applicability": {"standard_version": "3.4"},
                "conditions": [],
                "exceptions": [],
                "evidence_ids": ["evidence-not-canonical"],
                "relation_proposals": [],
                "advisory_signals": [],
                "confidence": 0.99,
            }
        ),
        model_profile=_profile(),
        prompt_profile=_prompt(enrichment),
        actor=_actor(),
    )

    with pytest.raises(ValueError, match="unknown evidence"):
        service.extract_candidate(_claim(1))

    assert len(repository.invocations) == 1
    assert governance_repository.candidates == ()
    assert governance_repository.run_status("run-sdtm-demo") == "processing"


def test_offline_provider_configuration_accepts_only_explicit_fake_or_replay_files(
    tmp_path,
) -> None:
    enrichment = _enrichment()
    fake_path = tmp_path / "fake.json"
    fake_path.write_text('{"claim":"from fake"}', encoding="utf-8")
    replay_path = tmp_path / "replay.json"
    replay_path.write_text(
        '{"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa":'
        '{"claim":"from replay"}}',
        encoding="utf-8",
    )

    assert type(
        enrichment.offline_provider_from_config(mode="fake", records_path=fake_path)
    ).__name__ == "FakeModelProvider"
    assert type(
        enrichment.offline_provider_from_config(mode="replay", records_path=replay_path)
    ).__name__ == "ReplayModelProvider"
    with pytest.raises(ValueError, match="fake or replay"):
        enrichment.offline_provider_from_config(mode="live", records_path=replay_path)
