"""Local stdin-only injection entrypoint for the ephemeral secret store."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import getpass
import os
from pathlib import Path
import sys
from typing import TextIO

from .secret_store import P16_EPHEMERAL_SECRET_NAMES, TmpfsSecretStore


def inject_secret_from_stream(
    *,
    store: TmpfsSecretStore,
    name: str,
    input_stream: TextIO,
    output_stream: TextIO,
) -> None:
    value = input_stream.readline(65_537)
    if value.endswith("\n"):
        value = value[:-1]
    if value.endswith("\r"):
        value = value[:-1]
    if not value or len(value) > 65_536:
        raise ValueError("secret input must be non-empty and at most 65536 characters")
    store.inject(name, value)
    output_stream.write("secret accepted\n")


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
    getpass_reader: Callable[[str], str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="harness-secret")
    subparsers = parser.add_subparsers(dest="command", required=True)
    inject = subparsers.add_parser("inject")
    inject.add_argument("name", choices=sorted(P16_EPHEMERAL_SECRET_NAMES))
    arguments = parser.parse_args(argv)

    values = os.environ if environ is None else environ
    secret_root = values.get("HARNESS_SUPERVISOR_SECRET_ROOT", "")
    if not secret_root:
        raise RuntimeError("HARNESS_SUPERVISOR_SECRET_ROOT is required")
    store = TmpfsSecretStore(
        root=Path(secret_root),
        allowed_names=P16_EPHEMERAL_SECRET_NAMES,
        clear_on_start=False,
    )
    selected_input = input_stream or sys.stdin
    selected_output = output_stream or sys.stdout
    if selected_input.isatty():
        value = (getpass_reader or getpass.getpass)("Secret: ")
        if not value or len(value) > 65_536:
            raise ValueError(
                "secret input must be non-empty and at most 65536 characters"
            )
        store.inject(arguments.name, value)
        selected_output.write("secret accepted\n")
    else:
        inject_secret_from_stream(
            store=store,
            name=arguments.name,
            input_stream=selected_input,
            output_stream=selected_output,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
