"""Deterministic fake `opencode` CLI for the OpenCode adapter tests.

Simulates `opencode run <prompt> --format json` (non-interactive JSONL
events). Modes are read from the prompt file content:
- ok: step_start -> text -> step_finish, exit 0
- tool: also emits a tool_use event
- fail: emits an error event and exits 1
- hang: sleeps until killed
"""

from __future__ import annotations

import json
import sys
import time


def _emit(event: dict[str, object]) -> None:
    print(json.dumps(event, ensure_ascii=False, sort_keys=True), flush=True)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    # opencode run <prompt> --format json
    if len(args) < 3 or args[0] != "run":
        _emit({"type": "error", "sessionID": "s1", "data": {"message": "usage error"}})
        return 1
    payload = json.loads(args[1])  # prompt text (JSON payload from the adapter)
    mode = payload.get("mode", "ok")

    _emit({"type": "step_start", "sessionID": "s1", "data": {}})
    if mode == "tool":
        _emit(
            {
                "type": "tool_use",
                "sessionID": "s1",
                "data": {"tool": {"toolName": "write_artifact"}, "arguments": {}},
            }
        )
    if mode == "fail":
        _emit(
            {
                "type": "error",
                "sessionID": "s1",
                "data": {"message": "boom: explicit failure"},
            }
        )
        return 1
    if mode == "hang":
        time.sleep(3600)
        return 0
    _emit(
        {
            "type": "text",
            "sessionID": "s1",
            "data": {"text": "fake-opencode-result: candidate extracted"},
        }
    )
    _emit({"type": "step_finish", "sessionID": "s1", "data": {}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
