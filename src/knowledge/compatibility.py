"""Fail-closed SemVer and SHA-256 checks for cross-repository contracts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from .models import CompatibilityRange


_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class ContractCompatibilityError(ValueError):
    """Raised whenever a version or hash lock cannot be proven valid."""


@dataclass(frozen=True, slots=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()

    def _compare_core(self, other: "SemVer") -> int:
        left = (self.major, self.minor, self.patch)
        right = (other.major, other.minor, other.patch)
        if left != right:
            return -1 if left < right else 1
        if not self.prerelease and not other.prerelease:
            return 0
        if not self.prerelease:
            return 1
        if not other.prerelease:
            return -1
        for left_identifier, right_identifier in zip(self.prerelease, other.prerelease):
            if left_identifier == right_identifier:
                continue
            left_numeric = left_identifier.isdigit()
            right_numeric = right_identifier.isdigit()
            if left_numeric and right_numeric:
                return -1 if int(left_identifier) < int(right_identifier) else 1
            if left_numeric != right_numeric:
                return -1 if left_numeric else 1
            return -1 if left_identifier < right_identifier else 1
        if len(self.prerelease) == len(other.prerelease):
            return 0
        return -1 if len(self.prerelease) < len(other.prerelease) else 1

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._compare_core(other) < 0

    def __le__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._compare_core(other) <= 0

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._compare_core(other) > 0

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._compare_core(other) >= 0


def parse_semver(value: str) -> SemVer:
    """Parse strict SemVer; malformed or incomplete values are rejected."""

    match = _SEMVER_RE.fullmatch(value)
    if match is None:
        raise ContractCompatibilityError(f"invalid SemVer: {value!r}")
    prerelease = tuple(match.group(4).split(".")) if match.group(4) else ()
    if any(part.isdigit() and len(part) > 1 and part.startswith("0") for part in prerelease):
        raise ContractCompatibilityError(f"invalid SemVer prerelease: {value!r}")
    return SemVer(int(match.group(1)), int(match.group(2)), int(match.group(3)), prerelease)


def is_version_compatible(version: str, supported: "CompatibilityRange") -> bool:
    """Return false, rather than guessing, for every malformed version."""

    try:
        candidate = parse_semver(version)
        minimum = parse_semver(supported.minimum)
        maximum = parse_semver(supported.maximum_exclusive)
    except (ContractCompatibilityError, AttributeError, TypeError):
        return False
    return minimum <= candidate < maximum


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_canonical_json(payload: Any) -> str:
    """Hash deterministic UTF-8 JSON, independent of input key order."""

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256_bytes(encoded)


def schema_bundle_sha256(root: str | Path, schema_paths: Iterable[str]) -> str:
    """Hash a versioned Schema bundle independently of file order and line endings."""

    bundle_root = Path(root)
    normalized_paths = sorted(set(schema_paths))
    if not normalized_paths:
        raise ContractCompatibilityError("schema bundle must contain at least one schema")

    schemas: list[dict[str, Any]] = []
    for relative_path in normalized_paths:
        path = bundle_root / relative_path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContractCompatibilityError(
                f"cannot load schema bundle member {relative_path!r}: {exc}"
            ) from exc
        schemas.append({"path": relative_path.replace("\\", "/"), "schema": payload})
    return sha256_canonical_json({"schemas": schemas})


def verify_sha256(payload: bytes, expected_sha256: str) -> bool:
    """Return false for malformed locks; hash validation is always fail closed."""

    if not isinstance(expected_sha256, str) or _SHA256_RE.fullmatch(expected_sha256) is None:
        return False
    return hashlib.sha256(payload).hexdigest() == expected_sha256


def assert_contract_compatible(
    *,
    version: str,
    supported: "CompatibilityRange",
    payload: bytes,
    expected_sha256: str,
) -> None:
    """Prove both version compatibility and payload identity or raise."""

    if not is_version_compatible(version, supported):
        raise ContractCompatibilityError(
            f"contract version {version!r} is outside the supported range"
        )
    if not verify_sha256(payload, expected_sha256):
        raise ContractCompatibilityError("contract SHA-256 is missing, malformed, or mismatched")
