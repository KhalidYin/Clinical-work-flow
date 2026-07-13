"""Study runtime-manifest loading and local path validation.

The manifest is a lock file, not a discovery mechanism.  It pins the Engine
contract, Wiki snapshots and toolchain used by one Study.  The endpoint used to
reach a Wiki service is injected by the runtime configuration; it is never
derived from the Study's parent or sibling directories.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import ValidationError

from .project import ProjectConfigError, resolve_project_path

if TYPE_CHECKING:
    from src.knowledge.models import RuntimeManifest


RUNTIME_MANIFEST_FILE = "runtime-manifest.yaml"


class RuntimeManifestConfigError(ProjectConfigError):
    """Raised when a Study runtime manifest is absent, malformed, or unsafe."""


def load_runtime_manifest(
    project_dir: str | Path, *, required: bool = False
) -> "RuntimeManifest | None":
    """Load the exact P2 ``RuntimeManifest`` lock from a Study directory.

    The Pydantic model enforces the shared schema.  This loader additionally
    rejects fallback paths outside the Study root, preventing implicit sibling
    Wiki discovery and path traversal before a runtime ever opens a snapshot.
    """

    manifest_path = Path(project_dir) / RUNTIME_MANIFEST_FILE
    if not manifest_path.exists():
        if required:
            raise RuntimeManifestConfigError(
                f"Missing required runtime manifest: {manifest_path}"
            )
        return None

    # ``src.config`` is loaded while Runtime modules initialise, while the
    # knowledge package itself imports Runtime contracts.  Delay this shared
    # model import until a caller explicitly loads a manifest.
    from src.knowledge.models import RuntimeManifest

    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RuntimeManifestConfigError(
            f"Invalid YAML in {manifest_path}: {exc}"
        ) from exc

    if not isinstance(raw, dict):
        raise RuntimeManifestConfigError(f"{manifest_path} must contain a YAML mapping")

    try:
        manifest = RuntimeManifest.model_validate(raw)
    except ValidationError as exc:
        raise RuntimeManifestConfigError(f"Invalid {manifest_path}: {exc}") from exc

    try:
        resolve_project_path(project_dir, manifest.workflow_knowledge.fallback_path)
        resolve_project_path(project_dir, manifest.domain_knowledge.fallback_path)
    except ProjectConfigError as exc:
        raise RuntimeManifestConfigError(
            f"Invalid snapshot fallback path in {manifest_path}: {exc}"
        ) from exc

    return manifest
