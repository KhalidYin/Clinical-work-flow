"""
Change Management System for Clinical Programming AI Workflow.

Handles:
  1. Version Tracking    — MAJOR.MINOR.PATCH for every artifact
  2. Impact Analysis     — Downstream dependency cascade detection
  3. Audit Logging       — JSONL audit trail for GxP compliance
  4. Rollback            — Restore any previous version
  5. Incremental Review  — Show only changes, not full re-review
"""

from .change_record import (
    ChangeRecord, FileChange, StageImpact,
    ChangeType, ImpactType,
)
from .version_manager import (
    VersionManager, VersionInfo, VersionBump,
)
from .impact_analyzer import (
    ImpactAnalyzer, ImpactResult,
    DEPENDENCY_GRAPH, FILE_TO_STAGE,
)

__all__ = [
    "ChangeRecord", "FileChange", "StageImpact",
    "ChangeType", "ImpactType",
    "VersionManager", "VersionInfo", "VersionBump",
    "ImpactAnalyzer", "ImpactResult",
    "DEPENDENCY_GRAPH", "FILE_TO_STAGE",
]
