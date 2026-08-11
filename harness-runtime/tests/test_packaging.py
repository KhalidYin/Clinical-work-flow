"""Packaging contract for reproducible Harness Runtime installation."""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_setuptools_discovers_only_runtime_packages() -> None:
    pyproject = tomllib.loads(
        (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
            encoding="utf-8"
        )
    )

    package_find = pyproject["tool"]["setuptools"]["packages"]["find"]
    assert package_find["include"] == [
        "adapters*",
        "contracts*",
        "poc*",
        "supervisor*",
    ]
    assert package_find["exclude"] == ["tests*", "images*"]
