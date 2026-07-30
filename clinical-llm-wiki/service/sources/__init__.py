"""Governed Source Registry application boundary."""

from .contracts import (
    DataBoundary,
    OrphanReconcileResult,
    RegistrationIntentRecord,
    RegistrationIntentStatus,
    RightsClassification,
    RightsPolicy,
    SourceRegistrationCommand,
    SourceRegistrationReceipt,
)
from .repository import (
    InMemorySourceRegistryRepository,
    RegistrationConflictError,
    SqlAlchemySourceRegistryRepository,
    SourceRegistryRepository,
    SourceRepositoryError,
)
from .service import (
    SourceRegistrationError,
    SourceRegistryService,
    UnsupportedSourceMediaError,
)

__all__ = [
    "DataBoundary",
    "InMemorySourceRegistryRepository",
    "OrphanReconcileResult",
    "RegistrationConflictError",
    "RegistrationIntentRecord",
    "RegistrationIntentStatus",
    "RightsClassification",
    "RightsPolicy",
    "SqlAlchemySourceRegistryRepository",
    "SourceRegistrationCommand",
    "SourceRegistrationError",
    "SourceRegistrationReceipt",
    "SourceRegistryRepository",
    "SourceRegistryService",
    "SourceRepositoryError",
    "UnsupportedSourceMediaError",
]
