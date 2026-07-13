"""Schema-bundle loading and deterministic hashing for cross-repository calls."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


class ContractError(ValueError):
    """The Wiki cannot prove a contract lock or payload is valid."""


def canonical_json_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class SchemaBundle:
    root: Path
    bundle_id: str
    version: str
    sha256: str
    _schemas: dict[str, dict[str, Any]]

    @classmethod
    def load(cls, root: Path) -> "SchemaBundle":
        bundle_path = root / "contract-bundle.json"
        try:
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
            paths = tuple(bundle["schemas"])
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ContractError(f"cannot load schema bundle from {bundle_path}: {exc}") from exc
        if not paths:
            raise ContractError("schema bundle must list at least one schema")
        schemas: dict[str, dict[str, Any]] = {}
        members: list[dict[str, Any]] = []
        for relative in sorted(set(paths)):
            try:
                schema = json.loads((root / relative).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ContractError(f"cannot read schema member {relative!r}: {exc}") from exc
            schemas[relative] = schema
            members.append({"path": relative.replace("\\", "/"), "schema": schema})
        actual = canonical_json_sha256({"schemas": members})
        expected = bundle.get("bundle_sha256")
        if actual != expected:
            raise ContractError("schema bundle hash mismatch; service must fail closed")
        return cls(
            root=root,
            bundle_id=str(bundle.get("bundle_id", "")),
            version=str(bundle.get("bundle_version", "")),
            sha256=actual,
            _schemas=schemas,
        )

    def assert_requested(self, value: dict[str, Any]) -> None:
        if value.get("version") != self.version or value.get("sha256") != self.sha256:
            raise ContractError("requested schema bundle version/hash does not match local bundle")

    def validate(self, relative_path: str, payload: dict[str, Any]) -> None:
        schema = self._schemas.get(relative_path)
        if schema is None:
            raise ContractError(f"schema not in loaded bundle: {relative_path}")
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.absolute_path))
        if errors:
            detail = "; ".join(error.message for error in errors[:3])
            raise ContractError(f"payload fails {relative_path}: {detail}")

    def validate_definition(
        self, relative_path: str, definition: str, payload: dict[str, Any]
    ) -> None:
        """Validate one schema-bundle definition without weakening its $defs."""
        base = self._schemas.get(relative_path)
        if base is None or definition not in base.get("$defs", {}):
            raise ContractError(f"definition {definition!r} not in schema {relative_path}")
        schema = dict(base["$defs"][definition])
        schema["$schema"] = base.get("$schema", "https://json-schema.org/draft/2020-12/schema")
        schema["$defs"] = base["$defs"]
        errors = sorted(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload),
            key=lambda error: list(error.absolute_path),
        )
        if errors:
            detail = "; ".join(error.message for error in errors[:3])
            raise ContractError(f"payload fails {relative_path}#{definition}: {detail}")
