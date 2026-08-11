"""P16/P2 tests for the Supervisor-owned ephemeral secret boundary."""

from __future__ import annotations

import os
from io import StringIO
import json
from pathlib import Path

import pytest


def test_store_rejects_unregistered_name_before_writing(tmp_path: Path) -> None:
    from supervisor.secret_store import TmpfsSecretStore

    store = TmpfsSecretStore(
        root=tmp_path,
        allowed_names=frozenset({"deepseek-api-key"}),
        clear_on_start=True,
    )

    with pytest.raises(ValueError, match="not allowed"):
        store.inject("../unregistered-key", "synthetic-marker")

    assert tuple(tmp_path.iterdir()) == ()


def test_store_injects_and_resolves_registered_opaque_reference(tmp_path: Path) -> None:
    from supervisor.secret_store import TmpfsSecretStore

    store = TmpfsSecretStore(
        root=tmp_path,
        allowed_names=frozenset({"deepseek-api-key"}),
        clear_on_start=True,
    )

    store.inject("deepseek-api-key", "synthetic-marker")

    assert store.resolve("secret://deepseek-api-key") == "synthetic-marker"
    stored = tmp_path / "deepseek-api-key"
    assert stored.is_file()
    if os.name != "nt":
        assert stored.stat().st_mode & 0o777 == 0o600


def test_missing_secret_error_is_sanitized(tmp_path: Path) -> None:
    from supervisor.secret_store import TmpfsSecretStore

    store = TmpfsSecretStore(
        root=tmp_path,
        allowed_names=frozenset({"deepseek-api-key"}),
        clear_on_start=True,
    )

    with pytest.raises(ValueError, match="required secret is unavailable") as error:
        store.resolve("secret://deepseek-api-key")

    assert str(tmp_path) not in str(error.value)
    assert "deepseek-api-key" not in str(error.value)
    assert error.value.__cause__ is None


def test_restart_clears_secrets_and_orphan_attempt_material(tmp_path: Path) -> None:
    from supervisor.secret_store import TmpfsSecretStore

    first = TmpfsSecretStore(
        root=tmp_path,
        allowed_names=frozenset({"deepseek-api-key"}),
        clear_on_start=True,
    )
    first.inject("deepseek-api-key", "synthetic-marker")
    orphan = tmp_path / "attempt-orphan"
    orphan.mkdir()
    (orphan / "auth.json").write_text("synthetic-marker", encoding="utf-8")

    restarted = TmpfsSecretStore(
        root=tmp_path,
        allowed_names=frozenset({"deepseek-api-key"}),
        clear_on_start=True,
    )

    assert tuple(tmp_path.iterdir()) == ()
    with pytest.raises(ValueError, match="required secret is unavailable"):
        restarted.resolve("secret://deepseek-api-key")


def test_stdin_injection_does_not_echo_secret_or_name(tmp_path: Path) -> None:
    from supervisor.secret_cli import inject_secret_from_stream
    from supervisor.secret_store import TmpfsSecretStore

    store = TmpfsSecretStore(
        root=tmp_path,
        allowed_names=frozenset({"deepseek-api-key"}),
        clear_on_start=True,
    )
    output = StringIO()

    inject_secret_from_stream(
        store=store,
        name="deepseek-api-key",
        input_stream=StringIO("synthetic-marker\n"),
        output_stream=output,
    )

    assert store.resolve("secret://deepseek-api-key") == "synthetic-marker"
    assert output.getvalue() == "secret accepted\n"
    assert "synthetic-marker" not in output.getvalue()
    assert "deepseek-api-key" not in output.getvalue()


def test_cli_main_replaces_secret_from_stdin_without_clearing_store(
    tmp_path: Path,
) -> None:
    from supervisor.secret_cli import main
    from supervisor.secret_store import P16_EPHEMERAL_SECRET_NAMES, TmpfsSecretStore

    output = StringIO()
    environment = {"HARNESS_SUPERVISOR_SECRET_ROOT": str(tmp_path)}

    first = main(
        ["inject", "deepseek-api-key"],
        environ=environment,
        input_stream=StringIO("first-synthetic-marker\n"),
        output_stream=output,
    )
    second = main(
        ["inject", "deepseek-api-key"],
        environ=environment,
        input_stream=StringIO("second-synthetic-marker\n"),
        output_stream=output,
    )

    store = TmpfsSecretStore(
        root=tmp_path,
        allowed_names=P16_EPHEMERAL_SECRET_NAMES,
        clear_on_start=False,
    )
    assert (first, second) == (0, 0)
    assert store.resolve("secret://deepseek-api-key") == "second-synthetic-marker"
    assert tuple(path.name for path in tmp_path.iterdir()) == ("deepseek-api-key",)
    assert "first-synthetic-marker" not in output.getvalue()
    assert "second-synthetic-marker" not in output.getvalue()


def test_cli_main_uses_no_echo_reader_for_interactive_terminal(tmp_path: Path) -> None:
    from supervisor.secret_cli import main
    from supervisor.secret_store import P16_EPHEMERAL_SECRET_NAMES, TmpfsSecretStore

    class TerminalInput(StringIO):
        def isatty(self) -> bool:
            return True

        def readline(self, *args: object, **kwargs: object) -> str:
            raise AssertionError("interactive secret must not use echoing readline")

    output = StringIO()
    result = main(
        ["inject", "deepseek-api-key"],
        environ={"HARNESS_SUPERVISOR_SECRET_ROOT": str(tmp_path)},
        input_stream=TerminalInput(),
        output_stream=output,
        getpass_reader=lambda _prompt: "interactive-synthetic-marker",
    )

    store = TmpfsSecretStore(
        root=tmp_path,
        allowed_names=P16_EPHEMERAL_SECRET_NAMES,
        clear_on_start=False,
    )
    assert result == 0
    assert store.resolve("secret://deepseek-api-key") == (
        "interactive-synthetic-marker"
    )
    assert output.getvalue() == "secret accepted\n"
    assert "interactive-synthetic-marker" not in output.getvalue()


def test_store_rejects_empty_secret_without_replacing_existing(tmp_path: Path) -> None:
    from supervisor.secret_store import TmpfsSecretStore

    store = TmpfsSecretStore(
        root=tmp_path,
        allowed_names=frozenset({"deepseek-api-key"}),
        clear_on_start=True,
    )
    store.inject("deepseek-api-key", "first-synthetic-marker")

    with pytest.raises(ValueError, match="must not be empty"):
        store.inject("deepseek-api-key", "")

    assert store.resolve("secret://deepseek-api-key") == "first-synthetic-marker"


def test_attempt_materializer_creates_fixed_auth_file_and_cleans_it(
    tmp_path: Path,
) -> None:
    from supervisor.secret_store import AttemptSecretMaterializer

    materializer = AttemptSecretMaterializer(root=tmp_path)

    auth_path = materializer.materialize(
        attempt_id="attempt-001",
        request_sha256="a" * 64,
        provider="deepseek",
        secret="synthetic-marker",
    )

    assert json.loads(auth_path.read_text(encoding="utf-8")) == {
        "deepseek": {"type": "api", "key": "synthetic-marker"}
    }
    assert "synthetic-marker" not in str(auth_path)
    assert "attempt-001" not in str(auth_path)
    materializer.cleanup("attempt-001", "a" * 64)
    assert tuple(tmp_path.iterdir()) == ()


def test_attempt_context_cleans_partial_material_after_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from supervisor.secret_store import AttemptSecretMaterializer

    materializer = AttemptSecretMaterializer(root=tmp_path)
    original_write_text = Path.write_text

    def fail_after_partial_write(
        path: Path,
        data: str,
        *,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        original_write_text(
            path,
            data,
            encoding=encoding,
            errors=errors,
            newline=newline,
        )
        raise OSError(f"synthetic-marker at {path}")

    monkeypatch.setattr(Path, "write_text", fail_after_partial_write)

    with pytest.raises(OSError):
        with materializer.auth_file(
            attempt_id="attempt-001",
            request_sha256="a" * 64,
            provider="deepseek",
            secret="synthetic-marker",
        ):
            raise AssertionError("materialization failure must prevent execution")

    assert tuple(tmp_path.iterdir()) == ()


def test_attempt_cleanup_failure_is_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from supervisor.secret_store import (
        AttemptSecretMaterializer,
        SecretCleanupError,
    )

    materializer = AttemptSecretMaterializer(root=tmp_path)
    materializer.materialize(
        attempt_id="attempt-001",
        request_sha256="a" * 64,
        provider="deepseek",
        secret="synthetic-marker",
    )

    def fail_remove(_directory: Path) -> None:
        raise OSError(f"synthetic-marker at {tmp_path}")

    monkeypatch.setattr("supervisor.secret_store._remove_tree", fail_remove)
    try:
        with pytest.raises(SecretCleanupError) as error:
            materializer.cleanup("attempt-001", "a" * 64)

        assert str(error.value) == "attempt secret cleanup failed"
        assert "synthetic-marker" not in str(error.value)
        assert str(tmp_path) not in str(error.value)
    finally:
        monkeypatch.undo()
        materializer.cleanup("attempt-001", "a" * 64)


def test_startup_reset_failure_is_sanitized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from supervisor.secret_store import SecretCleanupError, TmpfsSecretStore

    orphan = tmp_path / "attempt-orphan"
    orphan.mkdir()
    (orphan / "auth.json").write_text("synthetic-marker", encoding="utf-8")

    def fail_remove(_directory: Path) -> None:
        raise OSError(f"synthetic-marker at {tmp_path}")

    monkeypatch.setattr("supervisor.secret_store._remove_tree", fail_remove)
    try:
        with pytest.raises(SecretCleanupError) as error:
            TmpfsSecretStore(
                root=tmp_path,
                allowed_names=frozenset({"deepseek-api-key"}),
                clear_on_start=True,
            )

        assert str(error.value) == "ephemeral secret store reset failed"
        assert "synthetic-marker" not in str(error.value)
        assert str(tmp_path) not in str(error.value)
    finally:
        monkeypatch.undo()
        TmpfsSecretStore(
            root=tmp_path,
            allowed_names=frozenset({"deepseek-api-key"}),
            clear_on_start=True,
        )
