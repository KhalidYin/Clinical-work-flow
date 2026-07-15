from __future__ import annotations

import argparse
import json
from pathlib import Path

from review_panel.config import ReviewPanelConfig
from review_panel.queue_registry import QueueRegistry
from review_panel.schema_loader import ReviewSchemaLoader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clinical-review-panel")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check = subparsers.add_parser("check", help="Validate config, schema, and queue registry.")
    check.add_argument("--repo-root", type=Path, default=None)
    check.add_argument("--host", default="127.0.0.1")
    check.add_argument("--port", type=int, default=8790)

    serve = subparsers.add_parser("serve", help="Run the loopback Review Panel API.")
    serve.add_argument("--repo-root", type=Path, default=None)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8790)
    return parser


def run_check(args: argparse.Namespace) -> int:
    config = ReviewPanelConfig.from_repo_root(
        args.repo_root,
        bind_host=args.host,
        port=args.port,
    )
    schema = ReviewSchemaLoader(config.schema_path).load()
    queues = QueueRegistry(config).discover()
    payload = {
        "ok": True,
        "repo_root": str(config.repo_root),
        "bind_host": config.bind_host,
        "port": config.port,
        "schema_id": schema.schema.get("$id"),
        "queues": [queue.to_public_dict() for queue in queues],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "check":
        return run_check(args)
    if args.command == "serve":
        import uvicorn

        from review_panel.app import create_app

        config = ReviewPanelConfig.from_repo_root(
            args.repo_root,
            bind_host=args.host,
            port=args.port,
        )
        uvicorn.run(create_app(config.repo_root), host=config.bind_host, port=config.port)
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2
