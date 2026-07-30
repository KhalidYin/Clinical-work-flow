from __future__ import annotations

import json
from pathlib import Path

import yaml

from service.auth import IdentitySource, ProductRole


ROOT = Path(__file__).resolve().parents[1]


def test_local_identity_bundle_keeps_authentication_separate_from_internal_roles(
    tmp_path: Path,
) -> None:
    from service.demo_runtime import load_demo_identity_bundle

    path = tmp_path / "identities.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "issuer": "local://p12-demo",
                "identities": [
                    {
                        "token": "author-token-at-least-eight",
                        "userId": "usr-demo-author",
                        "subject": "demo-author",
                        "displayName": "Demo Author",
                        "email": "author@example.test",
                        "roles": ["knowledge_curator"],
                    },
                    {
                        "token": "reviewer-token-at-least-eight",
                        "userId": "usr-demo-reviewer",
                        "subject": "demo-reviewer",
                        "displayName": "Demo Reviewer",
                        "email": "reviewer@example.test",
                        "roles": ["reviewer"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    bundle = load_demo_identity_bundle(path)
    assertions = bundle.token_assertions()

    assert set(assertions) == {
        "author-token-at-least-eight",
        "reviewer-token-at-least-eight",
    }
    assert assertions["author-token-at-least-eight"].identity_source is IdentitySource.LOCAL_TEST
    assert assertions["author-token-at-least-eight"].subject == "demo-author"
    assert bundle.identities[0].roles == (ProductRole.KNOWLEDGE_CURATOR,)
    assert "roles" not in assertions["author-token-at-least-eight"].model_dump()


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


def test_demo_start_script_generates_local_credentials_and_waits_for_health() -> None:
    script = (ROOT / "scripts" / "start-demo.ps1").read_text(encoding="utf-8")

    assert "RandomNumberGenerator" in script
    assert ".demo-runtime" in script
    assert "--wait" in script
    assert "--volumes" in script
    assert "KNOWLEDGE_POSTGRES_PASSWORD=" in script
