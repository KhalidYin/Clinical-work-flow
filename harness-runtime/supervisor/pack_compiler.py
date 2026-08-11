"""Resolve a hash-locked Harness Pack and compile one Attempt configuration."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
import stat
from typing import Mapping

from pydantic import ValidationError
import yaml

from contracts.pack import (
    HarnessPackIdentity,
    HarnessPackManifest,
    HarnessPackMcpPolicy,
)
from contracts.spec import InstructionRef


class PackResolutionError(ValueError):
    """The requested Pack is absent, unsafe, invalid or has drifted."""


@dataclass(frozen=True, slots=True)
class ResolvedHarnessPack:
    root: Path
    identity: HarnessPackIdentity
    manifest: HarnessPackManifest
    mcp_policy: HarnessPackMcpPolicy


@dataclass(frozen=True, slots=True)
class McpCapabilityBinding:
    """Supervisor-trusted transport binding for one logical capability."""

    capability_id: str
    server_name: str
    tools: frozenset[str]
    command: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompiledHarnessPack:
    pack_identity: HarnessPackIdentity
    compiled_config_sha256: str
    advertised_skills: tuple[str, ...]
    allowed_mcp_capabilities: tuple[str, ...]
    workspace_root: Path
    opencode_config_path: Path
    mcp_bundle_path: Path


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


class HarnessPackResolver:
    def __init__(self, roots: Mapping[str, Path]) -> None:
        self._roots = {pack_id: Path(root).resolve() for pack_id, root in roots.items()}

    def measure(self, pack_id: str) -> str:
        root, _manifest, _mcp_policy = self._load(pack_id)
        digest = hashlib.sha256()
        entries = sorted(root.rglob("*"))
        for path in entries:
            self._require_inside(root, path)
        files = [path for path in entries if path.is_file()]
        if not files:
            raise PackResolutionError("Pack is empty")
        for path in files:
            self._require_inside(root, path)
            relative = path.relative_to(root).as_posix()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    def resolve(
        self,
        reference: InstructionRef,
        *,
        adapter_id: str,
        image_ref: str,
    ) -> ResolvedHarnessPack:
        root, manifest, mcp_policy = self._load(reference.pack_id)
        measured = self.measure(reference.pack_id)
        if reference.sha256 is None or measured != reference.sha256:
            raise PackResolutionError("Harness Pack hash mismatch")
        if reference.version != manifest.version:
            raise PackResolutionError("Harness Pack version mismatch")
        if adapter_id != manifest.adapter_id:
            raise PackResolutionError("Harness Pack adapter mismatch")
        if image_ref != manifest.image_ref:
            raise PackResolutionError("Harness Pack image mismatch")
        return ResolvedHarnessPack(
            root=root,
            identity=HarnessPackIdentity(
                pack_id=manifest.pack_id,
                version=manifest.version,
                sha256=measured,
            ),
            manifest=manifest,
            mcp_policy=mcp_policy,
        )

    def _load(
        self,
        pack_id: str,
    ) -> tuple[Path, HarnessPackManifest, HarnessPackMcpPolicy]:
        root = self._roots.get(pack_id)
        if root is None:
            raise PackResolutionError("Harness Pack is not allowlisted")
        if not root.is_dir():
            raise PackResolutionError("Harness Pack root is unavailable")
        try:
            manifest_value = yaml.safe_load((root / "pack.yaml").read_text(encoding="utf-8"))
            manifest = HarnessPackManifest.model_validate(manifest_value)
        except (OSError, UnicodeError, yaml.YAMLError, ValidationError, TypeError) as exc:
            raise PackResolutionError("Harness Pack manifest is invalid") from exc
        if manifest.pack_id != pack_id:
            raise PackResolutionError("Harness Pack manifest is invalid: pack_id mismatch")
        required_files = (
            manifest.instruction_file,
            manifest.mcp_policy_file,
            manifest.output_schema_file,
        )
        for relative in required_files:
            path = root / relative
            self._require_regular_file(root, path)
        for skill in manifest.skills:
            self._require_regular_file(root, root / skill.path / "SKILL.md")
        try:
            schema = json.loads((root / manifest.output_schema_file).read_text(encoding="utf-8"))
            if not isinstance(schema, dict):
                raise TypeError("schema must be an object")
            mcp_value = yaml.safe_load(
                (root / manifest.mcp_policy_file).read_text(encoding="utf-8")
            )
            mcp_policy = HarnessPackMcpPolicy.model_validate(mcp_value)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            yaml.YAMLError,
            ValidationError,
            TypeError,
        ) as exc:
            raise PackResolutionError("Harness Pack referenced content is invalid") from exc
        return root, manifest, mcp_policy

    @staticmethod
    def _require_inside(root: Path, path: Path) -> None:
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
        except (OSError, ValueError) as exc:
            raise PackResolutionError("Harness Pack path escapes its root") from exc
        candidate = path
        while True:
            metadata = candidate.lstat()
            attributes = getattr(metadata, "st_file_attributes", 0)
            reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            if candidate.is_symlink() or attributes & reparse_flag:
                raise PackResolutionError("Harness Pack symlinks/reparse points are forbidden")
            if candidate == root:
                break
            candidate = candidate.parent

    @classmethod
    def _require_regular_file(cls, root: Path, path: Path) -> None:
        if path.is_symlink():
            raise PackResolutionError("Harness Pack symlinks are forbidden")
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise PackResolutionError("Harness Pack path escapes its root") from exc
        if not path.is_file():
            raise PackResolutionError("Harness Pack referenced file is unavailable")
        cls._require_inside(root, path)


class HarnessPackCompiler:
    def __init__(self, bindings: Mapping[str, McpCapabilityBinding]) -> None:
        self._bindings = dict(bindings)

    def compile(self, pack: ResolvedHarnessPack, attempt_root: Path) -> CompiledHarnessPack:
        self._require_unchanged(pack)
        workspace = attempt_root / "workspace"
        config_root = attempt_root / "config"
        workspace.mkdir(parents=True, exist_ok=True)
        config_root.mkdir(parents=True, exist_ok=True)

        shutil.copyfile(pack.root / pack.manifest.instruction_file, workspace / "AGENTS.md")
        skill_permissions: dict[str, str] = {"*": "deny"}
        advertised_skills: list[str] = []
        for skill in pack.manifest.skills:
            source = pack.root / skill.path
            target = workspace / ".opencode" / "skills" / skill.skill_id
            shutil.copytree(source, target, dirs_exist_ok=True)
            advertised_skills.append(skill.skill_id)
            skill_permissions[skill.skill_id] = "allow"
        schema_target = workspace / "output.schema.json"
        shutil.copyfile(pack.root / pack.manifest.output_schema_file, schema_target)

        allowed_tools: set[str] = set()
        mcp_config: dict[str, object] = {}
        capability_ids: list[str] = []
        for capability in pack.mcp_policy.capabilities:
            binding = self._bindings.get(capability.capability_id)
            if binding is None:
                raise PackResolutionError("Harness Pack requests an untrusted MCP capability")
            requested = set(capability.tools)
            if not requested.issubset(binding.tools):
                raise PackResolutionError("Harness Pack requests unauthorized MCP tools")
            allowed_tools.update(requested)
            capability_ids.append(capability.capability_id)
            mcp_config[binding.server_name] = {
                "type": "local",
                "command": list(binding.command),
                "enabled": True,
            }

        bundle = {
            "contract_version": "1.0.0",
            "allowed_tools": sorted(allowed_tools),
        }
        config = {
            "$schema": "https://opencode.ai/config.json",
            "permission": {"skill": skill_permissions},
            "mcp": mcp_config,
        }
        mcp_bundle_path = config_root / "mcp-bundle.json"
        opencode_config_path = config_root / "opencode.json"
        mcp_bundle_path.write_bytes(_canonical_bytes(bundle))
        opencode_config_path.write_bytes(_canonical_bytes(config))
        compiled_identity = {
            "pack_identity": pack.identity.model_dump(mode="json"),
            "config": config,
            "mcp_bundle": bundle,
            "advertised_skills": advertised_skills,
            "allowed_mcp_capabilities": capability_ids,
        }
        compiled_hash = hashlib.sha256(_canonical_bytes(compiled_identity)).hexdigest()
        self._require_unchanged(pack)
        return CompiledHarnessPack(
            pack_identity=pack.identity,
            compiled_config_sha256=compiled_hash,
            advertised_skills=tuple(advertised_skills),
            allowed_mcp_capabilities=tuple(capability_ids),
            workspace_root=workspace,
            opencode_config_path=opencode_config_path,
            mcp_bundle_path=mcp_bundle_path,
        )

    @staticmethod
    def _require_unchanged(pack: ResolvedHarnessPack) -> None:
        measured = HarnessPackResolver(
            {pack.identity.pack_id: pack.root}
        ).measure(pack.identity.pack_id)
        if measured != pack.identity.sha256:
            raise PackResolutionError("Harness Pack hash mismatch during compilation")


__all__ = [
    "CompiledHarnessPack",
    "HarnessPackCompiler",
    "HarnessPackResolver",
    "McpCapabilityBinding",
    "PackResolutionError",
    "ResolvedHarnessPack",
]
