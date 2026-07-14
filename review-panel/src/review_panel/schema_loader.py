from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


class ReviewSchemaError(ValueError):
    """Raised when the Engine-owned Review Schema cannot be used."""


@dataclass(frozen=True)
class LoadedReviewSchema:
    schema_path: Path
    schema: dict[str, Any]

    def definition_schema(self, name: str) -> dict[str, Any]:
        try:
            definition = copy.deepcopy(self.schema["$defs"][name])
        except KeyError as exc:
            raise ReviewSchemaError(f"Review Schema definition not found: {name}") from exc
        definition.setdefault("$schema", self.schema.get("$schema"))
        definition["$defs"] = copy.deepcopy(self.schema["$defs"])
        return definition

    def validator_for(self, name: str) -> Draft202012Validator:
        return Draft202012Validator(
            self.definition_schema(name),
            format_checker=FormatChecker(),
        )

    def validate(self, name: str, data: dict[str, Any]) -> list[str]:
        validator = self.validator_for(name)
        return [
            error.message
            for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path))
        ]

    def require_valid(self, name: str, data: dict[str, Any]) -> None:
        violations = self.validate(name, data)
        if violations:
            raise ReviewSchemaError(f"{name} does not satisfy Review Schema: {violations}")


@dataclass(frozen=True)
class ReviewSchemaLoader:
    schema_path: Path

    def load(self) -> LoadedReviewSchema:
        if not self.schema_path.is_file():
            raise ReviewSchemaError(f"Review Schema not found: {self.schema_path}")
        try:
            schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ReviewSchemaError(f"Review Schema is not valid JSON: {self.schema_path}") from exc
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            raise ReviewSchemaError("Review Schema is not a valid Draft 2020-12 schema.") from exc
        for required in ("review_packet", "decision_receipt", "confirmation_receipt"):
            if required not in schema.get("$defs", {}):
                raise ReviewSchemaError(f"Review Schema missing required definition: {required}")
        return LoadedReviewSchema(self.schema_path.resolve(), schema)


def read_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReviewSchemaError(f"JSON file is invalid: {path}") from exc
    if not isinstance(data, dict):
        raise ReviewSchemaError(f"JSON file must contain an object: {path}")
    return data


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
