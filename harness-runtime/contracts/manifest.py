"""H0-B artifact manifest: supervisor-recomputed staging output inventory."""

from __future__ import annotations

from pydantic import Field

from .request import StrictContractModel


class ArtifactManifestItem(StrictContractModel):
    key: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ArtifactManifest(StrictContractModel):
    """Supervisor-recomputed manifest; never built from harness self-reports."""

    items: tuple[ArtifactManifestItem, ...] = ()
