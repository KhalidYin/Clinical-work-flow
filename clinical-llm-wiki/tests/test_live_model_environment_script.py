from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "set-live-deepseek-env.ps1"
)


def test_deepseek_script_sets_exact_fail_closed_live_profile() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    expected_settings = {
        'KNOWLEDGE_ENRICHMENT_PROVIDER_MODE = "live"',
        'KNOWLEDGE_ENRICHMENT_MODEL_PROFILE_ID = "deepseek-v4-flash-extractor"',
        'KNOWLEDGE_ENRICHMENT_MODEL_PROFILE_VERSION = "1.0.1"',
        'KNOWLEDGE_ENRICHMENT_PROMPT_PROFILE_ID = "atomic-candidate"',
        'KNOWLEDGE_ENRICHMENT_PROMPT_PROFILE_VERSION = "1.1.0"',
        'KNOWLEDGE_LIVE_MODEL_ENABLED = "true"',
        'KNOWLEDGE_LIVE_MODEL_PROFILE_ID = "deepseek-v4-flash-extractor"',
        'KNOWLEDGE_LIVE_MODEL_PROFILE_VERSION = "1.0.1"',
        'KNOWLEDGE_LIVE_MODEL_ALLOWED_DATA_BOUNDARIES = "external_allowed"',
        'KNOWLEDGE_LIVE_MODEL_MAX_CALLS = "1"',
        'KNOWLEDGE_MODEL_ENDPOINT = "https://api.deepseek.com"',
    }
    assert expected_settings <= {line.strip() for line in content.splitlines()}


def test_deepseek_script_never_accepts_or_persists_a_plaintext_key() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert "Read-Host" in content
    assert "-AsSecureString" in content
    assert "SetEnvironmentVariable" not in content
    assert "[string]$ApiKey" not in content
    assert '$secretVariable = "KNOWLEDGE_MODEL_API_KEY"' in content
    assert "ConvertFrom-SecureString" in content
    assert "ConvertTo-SecureString" in content
    assert 'Join-Path $runtimePath "deepseek-api-key.dpapi"' in content
    assert "Write-Host $plainValue" not in content
