"""Deterministic fake Harness CLI for the H0-A adapter contract spike.

Simulates the CLI surface of a mature Harness without any external product:
- reads input.json from argv[1]
- emits structured event lines (JSON) to stdout
- writes output.json to argv[2]
- exit code 0 on success, 1 on explicit failure, hangs on mode=hang

Usage: python fake_cli.py <input.json> <output.json>
"""

from __future__ import annotations

import hashlib
import json
import sys
import time


def _emit(event: dict[str, object]) -> None:
    print(json.dumps(event, ensure_ascii=False, sort_keys=True), flush=True)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        _emit({"type": "failed", "payload": {"reason": "usage: fake_cli INPUT OUTPUT"}})
        return 2
    input_path, output_path = args
    with open(input_path, encoding="utf-8") as fh:
        payload = json.load(fh)

    _emit({"type": "started", "payload": {}})
    mode = payload.get("mode", "ok")

    if mode == "fail":
        reason = payload.get("reason", "explicit failure")
        _emit({"type": "failed", "payload": {"reason": reason}})
        return 1

    if mode == "hang":
        seconds = float(payload.get("seconds", 3600))
        time.sleep(seconds)
        return 0

    result = {
        "claim": payload.get("claim", "fake-claim"),
        "evidence_ids": payload.get("evidence_ids", []),
    }
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=2, sort_keys=True)

    _emit({"type": "checkpoint", "payload": {"phase": "draft"}})
    digest = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    _emit({"type": "finished", "payload": {"output_sha256": digest}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
