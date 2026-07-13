"""Engine-owned bridge from a fixed pipeline stage to governed knowledge."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from src.config import RuntimeManifestConfigError, load_runtime_manifest
from src.knowledge.models import ExecutionContext, ResolvedRule

from .pipeline_contract import PipelineStage

if TYPE_CHECKING:
    from src.knowledge.resolver import KnowledgeContextResolver


class RuntimeContextError(RuntimeError):
    """Study runtime context cannot be resolved safely."""


class RuntimeContextResolver:
    """Load the manifest from a Study and delegate only after Stage is fixed.

    This class intentionally accepts a stage selected by the Engine router; the
    Wiki is never asked to choose, override, or advance the pipeline.
    """

    def __init__(self, knowledge_resolver: "KnowledgeContextResolver") -> None:
        self._knowledge_resolver = knowledge_resolver

    def resolve_for_stage(
        self,
        project_dir: str | Path,
        stage: PipelineStage | str,
        *,
        study_rules: Iterable[ResolvedRule | Mapping[str, Any]] = (),
        manifest_name: str = "runtime-manifest.yaml",
    ) -> ExecutionContext:
        root = Path(project_dir)
        if manifest_name != "runtime-manifest.yaml":
            raise RuntimeContextError("the runtime manifest filename is fixed by the Study contract")
        try:
            manifest = load_runtime_manifest(root, required=True)
        except RuntimeManifestConfigError as exc:
            raise RuntimeContextError("Study runtime manifest cannot be read") from exc
        if manifest is None:  # defensive: required=True guarantees the type contract
            raise RuntimeContextError("Study runtime manifest is missing")
        try:
            return self._knowledge_resolver.resolve(
                project_dir=root, manifest=manifest, stage=stage,
                study_rules=study_rules,
            )
        except Exception as exc:
            raise RuntimeContextError("governed runtime context is unavailable") from exc
