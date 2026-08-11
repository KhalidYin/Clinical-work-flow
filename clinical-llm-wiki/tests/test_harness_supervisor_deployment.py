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
        "name": "clinical-harness-p15-model",
    }
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
        "clinical-harness-p15-model"
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


def test_compose_smoke_request_is_synthetic_and_cannot_select_live_network() -> None:
    from service.processing.harness_supervisor_smoke import build_smoke_request

    request = build_smoke_request()

    assert request.model_profile.provider == "admission"
    assert request.model_profile.model == "invalid-offline-model"
    assert request.model_profile.secret_ref == "env://SYNTHETIC_PROVIDER_KEY"
    assert request.model_profile.endpoint_ref is None
    assert request.model_profile.timeout_seconds == 30
