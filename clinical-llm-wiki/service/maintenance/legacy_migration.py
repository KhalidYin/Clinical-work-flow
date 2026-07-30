"""Legacy Wiki asset migration entrypoint, isolated from DDL and data backfill."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence


LegacyMigrationCallable = Callable[[bool], int]

# P4 will register reviewed crosswalk migrations. P1 fails closed with an empty registry.
REGISTERED_MIGRATIONS: dict[str, LegacyMigrationCallable] = {}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--migration", choices=sorted(REGISTERED_MIGRATIONS))
    parser.add_argument("--apply", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.list:
        for name in sorted(REGISTERED_MIGRATIONS):
            print(name)
        return 0
    if args.migration is None:
        parser.error("--migration is required unless --list is used")
    migrated = REGISTERED_MIGRATIONS[args.migration](not args.apply)
    print(f"mode={'apply' if args.apply else 'dry-run'} migrated={migrated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
