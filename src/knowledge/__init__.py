"""Governed clinical knowledge contracts and compatibility checks."""

from .compatibility import (
    ContractCompatibilityError,
    assert_contract_compatible,
    schema_bundle_sha256,
    verify_sha256,
)
from .client import (
    HttpKnowledgeTransport,
    KnowledgeServiceClient,
    KnowledgeServiceContractError,
    KnowledgeServiceUnavailable,
)
from .resolver import ContextResolutionError, KnowledgeContextResolver
from .snapshot import LockedSnapshot, SnapshotError, load_locked_snapshot
from .models import (
    ApprovalStatus,
    CapabilityId,
    CompatibilityRange,
    ContentStatus,
    ExecutionContext,
    FigureRecord,
    KnowledgeItem,
    PdfStatus,
    RightsStatus,
    RuntimeManifest,
    SourceRecord,
    StorageMode,
    WorkflowStage,
    WorkflowPlaybook,
    is_approval_status_transition_allowed,
    is_content_status_transition_allowed,
    is_pdf_status_transition_allowed,
)

__all__ = [
    "ContractCompatibilityError",
    "ContextResolutionError",
    "HttpKnowledgeTransport",
    "ApprovalStatus",
    "CapabilityId",
    "CompatibilityRange",
    "ContentStatus",
    "ExecutionContext",
    "FigureRecord",
    "KnowledgeItem",
    "KnowledgeContextResolver",
    "KnowledgeServiceClient",
    "KnowledgeServiceContractError",
    "KnowledgeServiceUnavailable",
    "LockedSnapshot",
    "PdfStatus",
    "RightsStatus",
    "RuntimeManifest",
    "SourceRecord",
    "SnapshotError",
    "StorageMode",
    "WorkflowStage",
    "WorkflowPlaybook",
    "assert_contract_compatible",
    "is_approval_status_transition_allowed",
    "is_content_status_transition_allowed",
    "is_pdf_status_transition_allowed",
    "schema_bundle_sha256",
    "load_locked_snapshot",
    "verify_sha256",
]
