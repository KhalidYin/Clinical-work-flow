"""Run isolated schema-invalid and timeout OpenCode POC failure scenarios."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Mapping, Sequence
from uuid import uuid4

from scripts.harness_poc_loop import (
    LIVE_SECRET_NAMES,
    PocLoopRunner,
    build_poc_environment,
    validate_replay_counts,
)


FAILURE_SCENARIOS = ("schema_invalid", "timeout")


def build_scenario_environment(
    *,
    base: Mapping[str, str],
    scenario: str,
) -> dict[str, str]:
    if scenario not in FAILURE_SCENARIOS:
        raise ValueError("unsupported P15 failure scenario")
    environment = {
        key: value
        for key, value in base.items()
        if key not in LIVE_SECRET_NAMES
    }
    environment.update(
        {
            "P15_MOCK_SCENARIO": scenario,
            "P15_MOCK_DELAY_SECONDS": "0",
            "KNOWLEDGE_P15_MODEL_TIMEOUT_SECONDS": "30",
            "KNOWLEDGE_P15_EXPECTED_FAILURE": scenario,
        }
    )
    if scenario == "timeout":
        environment.update(
            {
                # Leave enough time for OpenCode startup, then make the internal
                # model request exceed the whole Attempt budget deterministically.
                "P15_MOCK_DELAY_SECONDS": "30",
                "KNOWLEDGE_P15_MODEL_TIMEOUT_SECONDS": "20",
            }
        )
    return environment


class FailureScenarioRunner(PocLoopRunner):
    def _managed_attempt_container_count(self, attempt_id: str) -> int:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-aq",
                "--filter",
                f"label=clinical.harness.attempt_id={attempt_id}",
            ],
            cwd=self._root,
            env=self._environment,
            check=False,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            raise RuntimeError("failed to inspect managed Attempt containers")
        return len([line for line in result.stdout.splitlines() if line.strip()])

    def execute_failure(self, scenario: str) -> dict[str, object]:
        completed = False
        try:
            up = ["up", "-d"]
            if self._build:
                up.append("--build")
            up.extend(("p15-api", "worker-enrichment"))
            self._run(up)
            self._run(("wait", "worker-enrichment"))
            first = self._mock_request_count()

            self._run(("run", "--rm", "--no-deps", "worker-enrichment"))
            second = self._mock_request_count()
            replay = validate_replay_counts(first=first, second=second)
            workflow = self._verify()
            if workflow.get("scenario") != scenario:
                raise RuntimeError("P15 verifier returned the wrong failure scenario")
            attempt_id = workflow.get("attempt_id")
            if not isinstance(attempt_id, str):
                raise RuntimeError("P15 failure verifier returned no Attempt identity")
            managed_containers = self._managed_attempt_container_count(attempt_id)
            if managed_containers != 0:
                raise RuntimeError("P15 failure left a managed Attempt container behind")
            deepseek_requests = self._deepseek_request_count()
            if deepseek_requests != 0:
                raise RuntimeError("POC failure observed an unauthorized DeepSeek request")
            completed = True
            return {
                "scenario": scenario,
                "result": "passed",
                "model_requests": replay,
                "managed_attempt_containers": managed_containers,
                "deepseek_requests": deepseek_requests,
                "workflow": workflow,
            }
        finally:
            if not self._keep:
                cleanup = self._run(
                    ("down", "--volumes", "--remove-orphans"),
                    check=False,
                )
                if cleanup.returncode != 0 and completed:
                    raise RuntimeError(
                        "POC failure passed but isolated project cleanup failed"
                    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--scenario", choices=FAILURE_SCENARIOS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    knowledge_root = Path(__file__).resolve().parents[1]
    results: list[dict[str, object]] = []
    scenarios = (args.scenario,) if args.scenario else FAILURE_SCENARIOS
    for index, scenario in enumerate(scenarios):
        project_name = f"clinical-harness-poc-fail-{uuid4().hex[:10]}"
        base = build_poc_environment(
            project_name=project_name,
            knowledge_root=knowledge_root,
        )
        environment = build_scenario_environment(base=base, scenario=scenario)
        runner = FailureScenarioRunner(
            project_name=project_name,
            knowledge_root=knowledge_root,
            environment=environment,
            build=(not args.no_build and index == 0),
            keep=args.keep,
        )
        result = runner.execute_failure(scenario)
        if args.keep:
            result["diagnostic_project"] = project_name
        results.append(result)
    print(
        json.dumps(
            {
                "result": "passed",
                "mode": "internal-mock-failure-matrix",
                "scenarios": results,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
