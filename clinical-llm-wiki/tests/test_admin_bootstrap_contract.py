from __future__ import annotations

import pytest

from service.auth.bootstrap_admin import admin_bootstrap_config_from_environment


def _environment() -> dict[str, str]:
    return {
        "KNOWLEDGE_ADMIN_USERNAME": "admin",
        "KNOWLEDGE_ADMIN_PASSWORD": "a-secure-initial-password",
        "KNOWLEDGE_ADMIN_DISPLAY_NAME": "系统管理员",
        "KNOWLEDGE_ADMIN_EMAIL": "admin@knowledge.local",
        "KNOWLEDGE_ADMIN_INITIAL_PASSWORD_MIN_LENGTH": "12",
    }


def test_admin_bootstrap_config_reads_all_initial_identity_fields_from_environment() -> None:
    config = admin_bootstrap_config_from_environment(_environment())

    assert config.username == "admin"
    assert config.password == "a-secure-initial-password"
    assert config.display_name == "系统管理员"
    assert config.email == "admin@knowledge.local"
    assert config.minimum_password_length == 12
    assert config.require_password_change is True


def test_admin_bootstrap_require_password_change_defaults_to_true_when_unset() -> None:
    config = admin_bootstrap_config_from_environment(_environment())

    assert config.require_password_change is True


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("false", False),
        ("False", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("true", True),
        ("True", True),
        ("1", True),
        ("", True),
    ),
)
def test_admin_bootstrap_require_password_change_respects_environment(
    value: str,
    expected: bool,
) -> None:
    environment = _environment()
    environment["KNOWLEDGE_ADMIN_REQUIRE_PASSWORD_CHANGE"] = value
    config = admin_bootstrap_config_from_environment(environment)

    assert config.require_password_change is expected


@pytest.mark.parametrize(
    "missing",
    (
        "KNOWLEDGE_ADMIN_USERNAME",
        "KNOWLEDGE_ADMIN_PASSWORD",
        "KNOWLEDGE_ADMIN_DISPLAY_NAME",
        "KNOWLEDGE_ADMIN_EMAIL",
    ),
)
def test_admin_bootstrap_config_fails_closed_when_required_value_is_missing(
    missing: str,
) -> None:
    environment = _environment()
    del environment[missing]

    with pytest.raises(RuntimeError, match=missing):
        admin_bootstrap_config_from_environment(environment)


@pytest.mark.parametrize("value", ("7", "129", "not-a-number"))
def test_admin_bootstrap_rejects_unsafe_initial_password_length_configuration(
    value: str,
) -> None:
    environment = _environment()
    environment["KNOWLEDGE_ADMIN_INITIAL_PASSWORD_MIN_LENGTH"] = value

    with pytest.raises(RuntimeError, match="KNOWLEDGE_ADMIN_INITIAL_PASSWORD_MIN_LENGTH"):
        admin_bootstrap_config_from_environment(environment)
