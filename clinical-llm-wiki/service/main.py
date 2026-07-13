"""Command entry point: `python -m service.main` binds only to loopback."""

from __future__ import annotations

import uvicorn

from .app import create_app
from .config import WikiServiceConfig


def main() -> None:
    config = WikiServiceConfig.from_environment()
    uvicorn.run(create_app(config), host=config.bind_host, port=config.bind_port)


if __name__ == "__main__":
    main()
