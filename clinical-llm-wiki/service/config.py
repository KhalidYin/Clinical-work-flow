"""Configuration for the loopback-only first release of the Knowledge Service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WikiServiceConfig:
    """Filesystem roots are explicit so the service never guesses a Study path."""

    vault_root: Path
    schemas_dir: Path
    bind_host: str = "127.0.0.1"
    bind_port: int = 8787

    @classmethod
    def from_environment(cls) -> "WikiServiceConfig":
        root = Path(os.environ.get("CLINICAL_WIKI_ROOT", Path(__file__).parents[1])).resolve()
        schemas = Path(
            os.environ.get("CLINICAL_WIKI_SCHEMAS_DIR", root / "schemas" / "engine")
        ).resolve()
        host = os.environ.get("CLINICAL_WIKI_BIND_HOST", "127.0.0.1")
        # The process is deliberately loopback-only in this release.  Remote
        # deployment must be an explicit future configuration and threat-model change.
        if host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("first-release Knowledge Service may bind only to loopback")
        return cls(
            vault_root=root,
            schemas_dir=schemas,
            bind_host=host,
            bind_port=int(os.environ.get("CLINICAL_WIKI_BIND_PORT", "8787")),
        )
