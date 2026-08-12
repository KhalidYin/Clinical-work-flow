"""Run the isolated P15 OpenCode workflow twice and verify one canonical result."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
from typing import Callable, Mapping, Sequence
from uuid import uuid4


COMPOSE_FILES = (
    "compose.yaml",
    "compose.harness.yaml",
    "compose.harness.poc.yaml",
)
LIVE_SECRET_NAMES = (
    "DEEPSEEK_API_KEY",
    "KNOWLEDGE_MODEL_API_KEY",
)


def measure_pack(root: Path) -> str:
    """Match the trusted Supervisor's path-and-content Pack measurement."""

    resolved = root.resolve()
    entries = sorted(
        resolved.rglob("*"),
        key=lambda path: path.relative_to(resolved).as_posix(),
    )
    files: list[Path] = []
    for path in entries:
        if not path.resolve().is_relative_to(resolved):
            raise RuntimeError("Harness Pack contains a path outside its root")
        if path.is_file():
            files.append(path)
    if not files:
        raise RuntimeError("Harness Pack is empty")
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(resolved).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_poc_environment(
    *,
    project_name: str,
    knowledge_root: Path,
    secret_factory: Callable[[], str] = lambda: secrets.token_urlsafe(24),
) -> dict[str, str]:
    fixture = (knowledge_root / "poc" / "fixtures" / "p15-synthetic-provider-key.txt")
    if not fixture.is_file():
        raise RuntimeError("P15 synthetic provider fixture is unavailable")
    return {
        "KNOWLEDGE_POSTGRES_PASSWORD": secret_factory(),
        "KNOWLEDGE_ADMIN_USERNAME": "poc-admin",
        "KNOWLEDGE_ADMIN_PASSWORD": secret_factory(),
        "KNOWLEDGE_ADMIN_DISPLAY_NAME": "POC 管理员",
        "KNOWLEDGE_ADMIN_EMAIL": "poc-admin@knowledge.local",
        "KNOWLEDGE_DOCUMENT_WORKER_SERVICE_ACCOUNT_ID": "svc-demo-document",
        "KNOWLEDGE_ENRICHMENT_WORKER_SERVICE_ACCOUNT_ID": "svc-demo-enrichment",
        "KNOWLEDGE_RELEASE_WORKER_SERVICE_ACCOUNT_ID": "svc-demo-release",
        "P12_DOCUMENT_WORKER_TOKEN": secret_factory(),
        "P12_ENRICHMENT_WORKER_TOKEN": secret_factory(),
        "P12_RELEASE_WORKER_TOKEN": secret_factory(),
        "KNOWLEDGE_RUNTIME_CONSUMER_SECRET": secret_factory(),
        "KNOWLEDGE_P15_VERIFIER_PASSWORD": secret_factory(),
        "HARNESS_SUPERVISOR_MACHINE_TOKEN": secret_factory(),
        "HARNESS_SUPERVISOR_SPEC_SHA256": "a" * 64,
        "HARNESS_PACK_SHA256": measure_pack(
            knowledge_root / "harness-packs" / "knowledge-candidate-v1"
        ),
        "HARNESS_SYNTHETIC_PROVIDER_KEY_FILE": str(fixture.resolve()),
        "HARNESS_P15_MODEL_NETWORK_NAME": f"{project_name}-model",
        "HARNESS_DEEPSEEK_CLIENT_NETWORK_NAME": f"{project_name}-deepseek-client",
    }


def validate_replay_counts(*, first: int, second: int) -> dict[str, int]:
    if first < 1:
        raise RuntimeError("first POC Worker produced no internal model requests")
    if second != first:
        raise RuntimeError("second POC Worker produced additional model requests")
    return {
        "first_worker_mock_requests": first,
        "second_worker_mock_requests": second,
        "duplicate_mock_requests": second - first,
    }


class PocLoopRunner:
    def __init__(
        self,
        *,
        project_name: str,
        knowledge_root: Path,
        environment: Mapping[str, str],
        build: bool,
        keep: bool,
    ) -> None:
        self._project_name = project_name
        self._root = knowledge_root
        self._environment = dict(os.environ)
        for name in LIVE_SECRET_NAMES:
            self._environment.pop(name, None)
        self._environment.update(environment)
        self._build = build
        self._keep = keep
        self._base = ["docker", "compose", "--project-name", project_name]
        for file_name in COMPOSE_FILES:
            self._base.extend(("-f", file_name))
        self._base.extend(("--profile", "harness"))

    def _run(
        self,
        arguments: Sequence[str],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [*self._base, *arguments],
            cwd=self._root,
            env=self._environment,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if check and result.returncode != 0:
            diagnostic = "\n".join(
                (result.stdout + "\n" + result.stderr).splitlines()[-40:]
            )
            raise RuntimeError(
                f"Docker Compose command failed ({' '.join(arguments)}):\n{diagnostic}"
            )
        return result

    def _mock_request_count(self) -> int:
        result = self._run(
            (
                "exec",
                "-T",
                "p15-openai-mock",
                "python",
                "-c",
                "from pathlib import Path; p=Path('/var/lib/p15-mock/requests.jsonl'); "
                "print(len(p.read_text(encoding='utf-8').splitlines()) if p.exists() else 0)",
            ),
        )
        return int(result.stdout.strip())

    def _deepseek_request_count(self) -> int:
        result = self._run(
            ("logs", "--no-color", "harness-egress-deepseek"),
        )
        combined = f"{result.stdout}\n{result.stderr}".lower()
        return combined.count("api.deepseek.com")

    def _wait_for_api(self) -> None:
        probe = (
            "exec",
            "-T",
            "p15-api",
            "python",
            "-c",
            "import urllib.request; "
            "urllib.request.urlopen('http://127.0.0.1:8788/api/prerelease/v1/health', "
            "timeout=2)",
        )
        for _attempt in range(20):
            if self._run(probe, check=False).returncode == 0:
                return
            time.sleep(1)
        raise RuntimeError("P15 API did not become healthy before verification")

    def _verify(self) -> dict[str, object]:
        self._wait_for_api()
        result = self._run(
            ("run", "--rm", "--no-deps", "p15-verify"),
        )
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("P15 verifier returned no result")
        payload = json.loads(lines[-1])
        if not isinstance(payload, dict):
            raise RuntimeError("P15 verifier result is not an object")
        return payload

    def execute(self) -> dict[str, object]:
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
            result = self._verify()
            deepseek_requests = self._deepseek_request_count()
            if deepseek_requests != 0:
                raise RuntimeError("POC loop observed an unauthorized DeepSeek request")
            completed = True
            return {
                "result": "passed",
                "mode": "internal-mock",
                "canonical_authority": "postgresql-and-authenticated-api",
                "model_requests": replay,
                "public_model_egress": {
                    "network_policy_id": "none",
                    "deepseek_requests": 0,
                },
                "workflow": result,
            }
        finally:
            if not self._keep:
                cleanup = self._run(
                    ("down", "--volumes", "--remove-orphans"),
                    check=False,
                )
                if cleanup.returncode != 0 and completed:
                    raise RuntimeError("POC succeeded but isolated project cleanup failed")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="reuse existing local images instead of rebuilding them",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep the randomly named isolated Compose project for diagnosis",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    knowledge_root = Path(__file__).resolve().parents[1]
    project_name = f"clinical-harness-poc-{uuid4().hex[:10]}"
    environment = build_poc_environment(
        project_name=project_name,
        knowledge_root=knowledge_root,
    )
    runner = PocLoopRunner(
        project_name=project_name,
        knowledge_root=knowledge_root,
        environment=environment,
        build=not args.no_build,
        keep=args.keep,
    )
    result = runner.execute()
    if args.keep:
        result["diagnostic_project"] = project_name
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
