from __future__ import annotations

import json
from pathlib import Path

from review_panel.cli import main


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_check_command_reports_schema_and_queues(capsys):
    exit_code = main(["check", "--repo-root", str(REPO_ROOT)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["schema_id"] == "https://clinical-workflow/schemas/review-protocol"
    assert any(queue["queue_id"] == "wiki" for queue in payload["queues"])

