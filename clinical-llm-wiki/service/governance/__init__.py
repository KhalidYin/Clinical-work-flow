"""Human governance application service for candidate and revision gates."""

from service.auth import AuthorizationError, SeparationOfDutiesError

from .service import (
    CandidateNotFoundError,
    DuplicateDecisionError,
    InMemoryGovernanceRepository,
    InvalidGovernanceTransitionError,
    KnowledgeGovernanceService,
    StaleRevisionError,
)
from .repository import SqlAlchemyGovernanceRepository
from .rotation import (
    ImpactMaterializationCommand,
    ImpactMaterializationError,
    MaterializedRotationCase,
    ReleasedRevisionEvidence,
    RotationImpactMaterializer,
    RotationMaterializationResult,
    eligible_rotation_outcomes,
)
from .rotation_repository import SqlAlchemyRotationRepository

__all__ = [
    "AuthorizationError",
    "CandidateNotFoundError",
    "DuplicateDecisionError",
    "InMemoryGovernanceRepository",
    "InvalidGovernanceTransitionError",
    "KnowledgeGovernanceService",
    "ImpactMaterializationCommand",
    "ImpactMaterializationError",
    "MaterializedRotationCase",
    "ReleasedRevisionEvidence",
    "RotationImpactMaterializer",
    "RotationMaterializationResult",
    "SeparationOfDutiesError",
    "StaleRevisionError",
    "SqlAlchemyGovernanceRepository",
    "SqlAlchemyRotationRepository",
    "eligible_rotation_outcomes",
]
