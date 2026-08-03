from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_demo_replay_profile_never_reuses_worker_machine_credential() -> None:
    from service.demo_runtime import DEMO_REPLAY_SECRET_REF

    assert DEMO_REPLAY_SECRET_REF == "secret://offline-replay/no-provider-secret"
    assert "WORKER_TOKEN" not in DEMO_REPLAY_SECRET_REF


def test_demo_replay_output_cites_only_canonical_evidence() -> None:
    from service.demo_runtime import build_demo_replay_output
    from service.knowledge import EvidenceReference
    from service.knowledge.contracts import EvidenceRights
    from service.processing.enrichment import EnrichmentContext, EnrichmentEvidence
    from service.processing.model_provider import DataBoundary

    context = EnrichmentContext(
        run_id="run-demo",
        source_version_id="srcv-demo",
        data_boundary=DataBoundary.ENTERPRISE_PROVIDER_ONLY,
        evidence=(
            EnrichmentEvidence(
                reference=EvidenceReference(
                    evidence_id="evidence-demo-001",
                    source_version_id="srcv-demo",
                    locator={"section": "AE", "paragraph": 1},
                    content_sha256="a" * 64,
                    rights=EvidenceRights(
                        classification="internal",
                        storage_allowed=True,
                        citation_required=True,
                    ),
                ),
                content="AESEQ uniquely identifies one adverse-event record.",
            ),
        ),
    )

    output = build_demo_replay_output(
        context,
        target_knowledge_unit_id="ku-demo-sdtm-ae",
    )

    assert output["evidence_ids"] == ["evidence-demo-001"]
    assert output["relation_proposals"] == [
        {
            "relation_type": "applies_to",
            "target_knowledge_unit_id": "ku-demo-sdtm-ae",
            "evidence_ids": ["evidence-demo-001"],
        }
    ]
    assert "candidate_id" not in output
    assert "status" not in output


def test_compose_bootstrap_precedes_api_and_independent_workers() -> None:
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert services["bootstrap"]["command"] == ["python", "-m", "service.demo_runtime"]
    assert services["bootstrap"]["depends_on"]["migration"]["condition"] == (
        "service_completed_successfully"
    )
    for name in ("api", "worker-document", "worker-enrichment"):
        assert services[name]["depends_on"]["bootstrap"]["condition"] == (
            "service_completed_successfully"
        )
    assert "profiles" not in services["worker-document"]
    assert "profiles" not in services["worker-enrichment"]
    assert services["worker-enrichment"]["environment"][
        "KNOWLEDGE_ENRICHMENT_PROVIDER_MODE"
    ] == "replay"
    assert services["worker-enrichment"]["environment"][
        "KNOWLEDGE_ENRICHMENT_RECORDS_PATH"
    ].endswith("/demo/replay-records.json")


def test_demo_start_script_bootstraps_password_without_writing_human_secret() -> None:
    script = (ROOT / "scripts" / "start-demo.ps1").read_text(encoding="utf-8")

    assert "RandomNumberGenerator" in script
    assert ".demo-runtime" in script
    assert "--wait" in script
    assert "--volumes" in script
    assert "KNOWLEDGE_POSTGRES_PASSWORD=" in script
    assert "run --rm -T admin-bootstrap" in script
    assert "一次性临时密码" in script
    assert "access.json" not in script
    assert "token =" not in script
    assert 'KNOWLEDGE_DEMO_HOST' in script
    assert 'Get-NetIPConfiguration' in script
    assert '本机回环地址：http://localhost:4173/app.html#/candidates' in script


def test_compose_has_no_human_bearer_identity_mount() -> None:
    content = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "KNOWLEDGE_LOCAL_IDENTITIES_PATH" not in content
    assert "identities.json" not in content
    assert "service.auth.bootstrap_admin" in content
