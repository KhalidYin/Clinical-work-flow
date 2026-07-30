"""Resumable data-backfill entrypoint, intentionally separate from schema DDL."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence


BackfillCallable = Callable[[int, str | None], tuple[int, str | None]]

# Tasks are registered only when an expand migration introduces a concrete backfill.
REGISTERED_BACKFILLS: dict[str, BackfillCallable] = {}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--task", choices=sorted(REGISTERED_BACKFILLS))
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--after-key")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.list:
        for name in sorted(REGISTERED_BACKFILLS):
            print(name)
        return 0
    if args.task is None:
        parser.error("--task is required unless --list is used")
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    processed, next_key = REGISTERED_BACKFILLS[args.task](args.batch_size, args.after_key)
    print(f"processed={processed} next_key={next_key or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
