from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parent


def test_harness_compose_profile_isolates_socket_and_machine_credentials() -> None:
    base = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    harness = yaml.safe_load(
        (ROOT / "compose.harness.yaml").read_text(encoding="utf-8")
    )
    supervisor = harness["services"]["harness-supervisor"]
    model_mock = harness["services"]["p15-openai-mock"]
    worker = harness["services"]["worker-enrichment"]

    assert supervisor["profiles"] == ["harness"]
    assert supervisor["networks"] == ["harness-control"]
    assert harness["networks"]["harness-control"]["internal"] is True
    assert harness["networks"]["harness-model"] == {
        "internal": True,
        "name": "${HARNESS_P15_MODEL_NETWORK_NAME:-clinical-harness-p15-model}",
    }
    assert harness["networks"]["harness-deepseek-client"]["name"] == (
        "${HARNESS_DEEPSEEK_CLIENT_NETWORK_NAME:-clinical-harness-deepseek-client}"
    )
    assert model_mock["networks"] == ["harness-model"]
    assert model_mock["read_only"] is True
    assert model_mock["cap_drop"] == ["ALL"]
    assert set(worker["networks"]) == {"default", "harness-control"}
    assert worker["environment"]["KNOWLEDGE_HARNESS_SUPERVISOR_URL"] == (
        "http://harness-supervisor:8790"
    )
    assert worker["environment"]["KNOWLEDGE_HARNESS_EXECUTION_MODE"] == (
        "opencode-supervised"
    )

    supervisor_volumes = "\n".join(supervisor["volumes"])
    worker_volumes = "\n".join(base["services"]["worker-enrichment"]["volumes"])
    assert "/var/run/docker.sock:/var/run/docker.sock" in supervisor_volumes
    assert "docker.sock" not in worker_volumes
    assert "SYNTHETIC_PROVIDER_KEY" not in supervisor["environment"]
    assert supervisor["environment"]["SYNTHETIC_PROVIDER_KEY_FILE"] == (
        "/run/secrets/p15_mock_key"
    )
    assert model_mock["environment"]["P15_MOCK_API_KEY_FILE"] == (
        "/run/secrets/p15_mock_key"
    )
    assert supervisor["secrets"] == ["p15_mock_key"]
    assert model_mock["secrets"] == ["p15_mock_key"]
    assert "SYNTHETIC_PROVIDER_KEY" not in worker["environment"]
    assert "HARNESS_SUPERVISOR_MACHINE_TOKEN" in supervisor["environment"]
    assert "HARNESS_SUPERVISOR_MACHINE_TOKEN" not in worker["environment"]
    assert "SUPERVISOR_MACHINE_TOKEN" in worker["environment"]
    assert supervisor["environment"]["HARNESS_SUPERVISOR_PACK_ID"] == (
        "knowledge-candidate-v1"
    )
    assert supervisor["environment"]["HARNESS_SUPERVISOR_MODEL_BASE_URL"] == (
        "http://p15-openai-mock:8080/v1"
    )
    assert supervisor["environment"]["HARNESS_SUPERVISOR_INTERNAL_NETWORK_NAME"] == (
        "${HARNESS_P15_MODEL_NETWORK_NAME:-clinical-harness-p15-model}"
    )
    assert supervisor["environment"]["HARNESS_SUPERVISOR_DEEPSEEK_NETWORK_NAME"] == (
        "${HARNESS_DEEPSEEK_CLIENT_NETWORK_NAME:-clinical-harness-deepseek-client}"
    )
    assert worker["environment"]["KNOWLEDGE_HARNESS_PACK_ID"] == (
        "knowledge-candidate-v1"
    )
    assert "KNOWLEDGE_HARNESS_PACK_SHA256" in worker["environment"]


def test_supervisor_image_has_dedicated_service_entrypoint() -> None:
    dockerfile = (REPOSITORY_ROOT / "harness-runtime" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "[docker,service]" in dockerfile
    assert 'CMD ["python", "-m", "supervisor.main"]' in dockerfile


def test_supervisor_secret_volume_is_ephemeral_and_not_shared_with_worker() -> None:
    harness = yaml.safe_load(
        (ROOT / "compose.harness.yaml").read_text(encoding="utf-8")
    )
    supervisor = harness["services"]["harness-supervisor"]
    worker = harness["services"]["worker-enrichment"]

    assert supervisor["environment"]["HARNESS_SUPERVISOR_SECRET_ROOT"] == (
        "/run/harness-secrets"
    )
    assert "harness-supervisor-secrets:/run/harness-secrets" in supervisor["volumes"]
    assert all(
        "harness-supervisor-secrets" not in volume
        for volume in worker.get("volumes", [])
    )
    assert harness["volumes"]["harness-supervisor-secrets"] == {
        "driver": "local",
        "driver_opts": {
            "type": "tmpfs",
            "device": "tmpfs",
            "o": "size=16m,mode=0700",
        },
    }
    rendered = yaml.safe_dump(harness)
    assert "deepseek-api-key" not in rendered
    assert "synthetic-opaque-value" not in rendered


def test_p15_poc_overlay_runs_setup_before_one_shot_enrichment() -> None:
    poc = yaml.safe_load(
        (ROOT / "compose.harness.poc.yaml").read_text(encoding="utf-8")
    )
    setup = poc["services"]["p15-setup"]
    worker = poc["services"]["worker-enrichment"]

    assert setup["command"] == [
        "python",
        "-m",
        "service.processing.harness_poc_setup",
    ]
    assert worker["depends_on"]["p15-setup"]["condition"] == (
        "service_completed_successfully"
    )
    assert worker["command"] == [
        "python",
        "-m",
        "service.processing.worker",
        "--pool",
        "enrichment",
        "--once",
    ]
    assert worker["restart"] == "no"
    assert worker["environment"]["KNOWLEDGE_ENRICHMENT_MODEL_PROFILE_ID"] == (
        "p15-internal-mock"
    )
    assert "ports" not in poc["services"]["p15-api"]
    assert poc["services"]["p15-api"]["networks"] == ["default"]
    assert poc["services"]["p15-api"]["environment"][
        "KNOWLEDGE_BROWSER_ORIGINS"
    ] == "http://p15-api:8788"
    verifier = poc["services"]["p15-verify"]
    assert verifier["depends_on"]["worker-enrichment"]["condition"] == (
        "service_completed_successfully"
    )
    assert verifier["depends_on"]["p15-api"]["condition"] == "service_healthy"
    assert "KNOWLEDGE_P15_VERIFIER_PASSWORD" in verifier["environment"]
    assert "KNOWLEDGE_DATABASE_URL" in verifier["environment"]
    assert verifier["environment"]["KNOWLEDGE_P15_PACK_SHA256"] == (
        "${HARNESS_PACK_SHA256:?set the measured knowledge-candidate-v1 Pack SHA-256}"
    )


def test_p15_mock_key_fixture_is_single_line_and_obviously_synthetic() -> None:
    fixture = ROOT / "poc" / "fixtures" / "p15-synthetic-provider-key.txt"
    lines = fixture.read_text(encoding="utf-8").splitlines()

    assert lines == ["synthetic-p15-mock-only-key"]
    assert not lines[0].startswith(("sk-", "dsk-"))


def test_compose_smoke_request_is_synthetic_and_cannot_select_live_network() -> None:
    import hashlib
    import json

    from service.processing.harness_supervisor_smoke import build_smoke_request

    request = build_smoke_request()

    assert request.model_profile.provider == "admission"
    assert request.model_profile.model == "invalid-offline-model"
    assert request.model_profile.secret_ref == "env://SYNTHETIC_PROVIDER_KEY"
    assert request.model_profile.endpoint_ref is None
    assert request.model_profile.timeout_seconds == 30
    payload = json.loads(request.messages[0].content)
    assert len(payload["evidence"]) == 1
    evidence = payload["evidence"][0]
    assert evidence["evidence_id"] == "evidence-compose-offline-smoke"
    assert evidence["locator"] == {
        "kind": "synthetic_test",
        "source_id": "compose-offline-smoke",
    }
    assert evidence["content_sha256"] == hashlib.sha256(
        evidence["content"].encode("utf-8")
    ).hexdigest()
