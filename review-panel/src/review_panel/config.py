from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_PORT = 8790


class ReviewPanelConfigError(ValueError):
    """Raised when local Review Panel configuration is unsafe or incomplete."""


@dataclass(frozen=True)
class ReviewPanelConfig:
    """Resolved local configuration for the root Review Panel service."""

    repo_root: Path
    schema_path: Path
    bind_host: str = DEFAULT_BIND_HOST
    port: int = DEFAULT_PORT

    @classmethod
    def from_repo_root(
        cls,
        repo_root: str | Path | None = None,
        *,
        bind_host: str = DEFAULT_BIND_HOST,
        port: int = DEFAULT_PORT,
    ) -> "ReviewPanelConfig":
        root = find_repo_root(Path.cwd() if repo_root is None else Path(repo_root))
        if bind_host != DEFAULT_BIND_HOST:
            raise ReviewPanelConfigError(
                "Review Panel is loopback-only; bind_host must be 127.0.0.1."
            )
        if port < 1 or port > 65535:
            raise ReviewPanelConfigError("port must be between 1 and 65535.")

        schema_path = (
            root / "clinical-workflow" / "schemas" / "review" / "review-protocol.schema.json"
        )
        if not schema_path.is_file():
            raise ReviewPanelConfigError(f"Engine Review Schema not found: {schema_path}")

        return cls(
            repo_root=root,
            schema_path=schema_path.resolve(),
            bind_host=bind_host,
            port=port,
        )


def find_repo_root(start: Path) -> Path:
    """Find the monorepo root from a starting path."""

    current = start.resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        if (
            (candidate / "clinical-workflow").is_dir()
            and (candidate / "clinical-llm-wiki").is_dir()
            and (candidate / "clinical-studies").is_dir()
        ):
            return candidate
    raise ReviewPanelConfigError(f"Cannot locate Clinical AI Workflow repo root from {start}.")


def ensure_path_within(path: Path, root: Path) -> Path:
    """Resolve an existing path and require it to remain inside root."""

    resolved_root = root.resolve(strict=True)
    resolved_path = path.resolve(strict=True)
    if not resolved_path.is_relative_to(resolved_root):
        raise ReviewPanelConfigError(f"Path escapes trusted root: {path}")
    return resolved_path

