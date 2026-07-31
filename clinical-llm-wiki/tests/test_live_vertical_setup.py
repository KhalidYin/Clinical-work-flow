from service.processing.live_vertical_setup import (
    LIVE_SOURCE,
    deepseek_model_profile,
    live_source_command,
)


def test_deepseek_profile_matches_runtime_environment_contract() -> None:
    profile = deepseek_model_profile()

    assert profile.profile_id == "deepseek-v4-flash-extractor"
    assert profile.version == "1.0.1"
    assert profile.provider == "deepseek"
    assert profile.model == "deepseek-v4-flash"
    assert profile.deployment_class.value == "external_api"
    assert profile.secret_ref == "env://KNOWLEDGE_MODEL_API_KEY"
    assert profile.endpoint_ref == "env://KNOWLEDGE_MODEL_ENDPOINT"
    assert {item.value for item in profile.allowed_data_boundaries} == {
        "external_allowed"
    }
    assert {item.value for item in profile.capabilities} == {
        "structured_generation"
    }


def test_live_source_is_explicitly_synthetic_and_external_allowed() -> None:
    command = live_source_command()

    assert command.data_boundary.value == "external_allowed"
    assert command.source_type == "synthetic_test"
    assert command.expected_sha256
    assert b"synthetic test data" in LIVE_SOURCE
    assert b"not a clinical standard" in LIVE_SOURCE
