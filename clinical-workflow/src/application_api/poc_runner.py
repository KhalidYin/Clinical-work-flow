"""Bounded P9.1 SDTM AE POC runner.

This runner is deliberately narrow:
- one Study at a time;
- one target artifact: SAMPLE-AE-001 SDTM AE CSV;
- synchronous execution to the next observable state;
- no arbitrary commands and no SAS execution.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.agents.ae_metadata_poc import (
    MAPPING_APPROVED_PATH,
    MAPPING_REVIEW_ID,
    prepare_metadata_mapping_review,
)
from src.agents.ae_metadata_workflow import (
    CANONICAL_DATASET_PATH,
    PROGRAM_REVIEW_ID,
    apply_program_review,
    run_after_mapping_approval,
)
from src.application_api.poc_models import (
    PocResumeRequest,
    PocRunRequest,
    PocRunResponse,
    PocRunState,
)
from src.mcp_tools.edc_importer import parse_registered_edc_source, write_source_parse_artifacts
from src.runtime.minimum_information import (
    KnowledgeAvailability,
    TargetStandardLock,
    plan_minimum_information,
)
from src.runtime.review_protocol import ReviewQueue


POC_RUN_ACTIVE_STATES = {"running", "blocked_review", "blocked_error"}
POC_RUN_TERMINAL_STATES = {"done", "failed"}
SOURCE_METADATA_PATH = "work/derived/edc/source-metadata.json"
MINIMUM_INFORMATION_PATH = "work/derived/plans/minimum-information-sdtm-ae.json"
POC_SNAPSHOT_ID = "snapshot-sdtmig34-core-events-ae-v1"
POC_SNAPSHOT_PATH = "snapshots/snapshot-sdtmig34-core-events-ae-v1.json"
POC_SNAPSHOT_SHA256 = "d8aafb73ccca987d597e372435b664ba074c1a45688d5e2eef809c72f475a9ec"


class PocRunnerError(RuntimeError):
    """POC runner failed before reaching an observable state."""


class PocRunner:
    """Synchronous runner for the bounded SDTM AE POC."""

    def __init__(self, study_dir: str | Path, wiki_dir: str | Path) -> None:
        self.study_dir = Path(study_dir).resolve()
        self.wiki_dir = Path(wiki_dir).resolve()
        self.app_dir = self.study_dir / ".application_api"
        self.runs_dir = self.app_dir / "poc_runs"
        self.events_path = self.app_dir / "poc_events.jsonl"
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def start(self, request: PocRunRequest) -> PocRunResponse:
        if request.target_artifact != "sdtm_ae_dataset":
            raise PocRunnerError("Only target_artifact=sdtm_ae_dataset is supported")
        active = latest_poc_run(self.study_dir)
        if active and active.get("run_state") in POC_RUN_ACTIVE_STATES and not request.force_restart:
            run = dict(active)
            self._append_event("run_reused", str(run["current_step"]), "复用已有 active POC run", run)
            self._advance(run)
            return self._response(run, accepted=True)

        now = _utc_now()
        run = {
            "run_id": _new_run_id(self.study_dir.name, now),
            "study_id": self.study_dir.name,
            "target_artifact": request.target_artifact,
            "run_state": PocRunState.RUNNING.value,
            "current_step": "source-intake",
            "blocking_reason": None,
            "blocking_review_id": None,
            "created_at": now,
            "updated_at": now,
            "resume_count": 0,
            "intent": request.intent,
        }
        self._write_run(run)
        self._append_event("run_started", "source-intake", "POC runner started", run)
        self._advance(run)
        return self._response(run, accepted=True)

    def resume(self, run_id: str, request: PocResumeRequest) -> PocRunResponse:
        run = self.load_run(run_id)
        if run is None:
            raise PocRunnerError(f"POC run not found: {run_id}")
        if run["run_state"] == PocRunState.DONE.value:
            return self._response(run, accepted=True)
        if run["run_state"] == PocRunState.BLOCKED_ERROR.value and (
            request.reason.value != "retry_after_failure"
        ):
            raise PocRunnerError("blocked_error can only resume with retry_after_failure")
        run["resume_count"] = int(run.get("resume_count", 0)) + 1
        run["run_state"] = PocRunState.RUNNING.value
        run["updated_at"] = _utc_now()
        self._write_run(run)
        self._append_event("run_resumed", str(run["current_step"]), "POC runner resumed", run)
        self._advance(run)
        return self._response(run, accepted=True)

    def load_run(self, run_id: str) -> dict[str, Any] | None:
        path = self.runs_dir / f"{run_id}.json"
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise PocRunnerError(f"Invalid POC run record: {run_id}")
        return payload

    def _advance(self, run: dict[str, Any]) -> None:
        try:
            self._ensure_source_metadata(run)
            self._ensure_minimum_information(run)

            if self._canonical_exists():
                self._complete(run, "canonical-ae", "Canonical AE already exists")
                return

            if not (self.study_dir / MAPPING_APPROVED_PATH).exists():
                if not self._has_decision(MAPPING_REVIEW_ID):
                    if not self._has_packet(MAPPING_REVIEW_ID):
                        self._ensure_mapping_review(run)
                    self._block_review(
                        run,
                        "mapping-spec",
                        MAPPING_REVIEW_ID,
                        "等待 AE MappingSpec 人工审核",
                    )
                    return
                self._run_programming_after_mapping(run)
                self._block_review(
                    run,
                    "output-review",
                    PROGRAM_REVIEW_ID,
                    "等待三语言程序和 Python draft 人工审核",
                )
                return

            if not self._has_decision(PROGRAM_REVIEW_ID):
                if not self._has_packet(PROGRAM_REVIEW_ID):
                    self._run_programming_after_mapping(run)
                self._block_review(
                    run,
                    "output-review",
                    PROGRAM_REVIEW_ID,
                    "等待三语言程序和 Python draft 人工审核",
                )
                return

            self._apply_program_review(run)
        except Exception as exc:  # noqa: BLE001 - convert all runner faults to visible state
            self._block_error(run, str(exc))

    def _ensure_source_metadata(self, run: dict[str, Any]) -> None:
        run["current_step"] = "sas-metadata"
        metadata_path = self.study_dir / SOURCE_METADATA_PATH
        if metadata_path.exists():
            self._append_event("source_metadata_reused", "sas-metadata", "复用已解析 Source Metadata", run)
            return
        inventory = _read_yaml(self.study_dir / "source-inventory.yaml")
        source = next(
            (
                item
                for item in inventory.get("sources", [])
                if item.get("role") == "ae_source_data"
            ),
            None,
        )
        if not source:
            raise PocRunnerError("source-inventory.yaml lacks role=ae_source_data")
        parsed = parse_registered_edc_source(
            str(source["path"]),
            str(source["format"]),
            allowed_root=self.study_dir,
            expected_sha256=str(source.get("sha256")),
        )
        write_source_parse_artifacts(
            parsed,
            study_root=self.study_dir,
            output_dir=self.study_dir / "work/derived/edc",
            review_queue=None,
        )
        self._append_event("source_metadata_written", "sas-metadata", "写入 Source Metadata", run)

    def _ensure_minimum_information(self, run: dict[str, Any]) -> None:
        run["current_step"] = "minimum-information"
        plan_path = self.study_dir / MINIMUM_INFORMATION_PATH
        if plan_path.exists():
            self._append_event("minimum_plan_reused", "minimum-information", "复用 Minimum Information Plan", run)
            return
        inventory = _read_yaml(self.study_dir / "source-inventory.yaml")
        metadata = _read_json(self.study_dir / SOURCE_METADATA_PATH)
        project = _read_yaml(self.study_dir / "project.yaml")
        available_paths = {
            str(item["path"])
            for item in inventory.get("sources", [])
            if (self.study_dir / str(item["path"])).exists()
        }
        plan = plan_minimum_information(
            study_id=str(project["study_id"]),
            source_inventory=inventory,
            source_metadata=metadata,
            target_standard=TargetStandardLock(
                standard="SDTMIG",
                version="3.4",
                locked=True,
                reference="project.yaml#standards/sdtmig_version",
            ),
            knowledge=KnowledgeAvailability(
                available=(self.wiki_dir / POC_SNAPSHOT_PATH).exists(),
                snapshot_id=POC_SNAPSHOT_ID,
                version="1.0.0",
                sha256=POC_SNAPSHOT_SHA256,
                reference=f"clinical-llm-wiki/{POC_SNAPSHOT_PATH}",
            ),
            available_source_paths=available_paths,
        )
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(
            json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        self._append_event("minimum_plan_written", "minimum-information", "写入 Minimum Information Plan", run)

    def _ensure_mapping_review(self, run: dict[str, Any]) -> None:
        run["current_step"] = "mapping-spec"
        prepare_metadata_mapping_review(self.study_dir, self.wiki_dir)
        self._append_event("mapping_review_written", "mapping-spec", "写入 AE MappingSpec ReviewPacket", run)

    def _run_programming_after_mapping(self, run: dict[str, Any]) -> None:
        run["current_step"] = "codegen"
        result = run_after_mapping_approval(self.study_dir)
        self._append_event(
            "program_review_written",
            "output-review",
            f"写入 Program ReviewPacket: {result.get('status')}",
            run,
        )

    def _apply_program_review(self, run: dict[str, Any]) -> None:
        run["current_step"] = "canonical-ae"
        result = apply_program_review(self.study_dir)
        if result["status"] == "rework_required":
            self._block_error(run, "Program review rejected or modified; rework required")
            return
        self._complete(run, "canonical-ae", "Canonical AE written")

    def _block_review(
        self,
        run: dict[str, Any],
        step_id: str,
        review_id: str,
        reason: str,
    ) -> None:
        run.update(
            {
                "run_state": PocRunState.BLOCKED_REVIEW.value,
                "current_step": step_id,
                "blocking_reason": reason,
                "blocking_review_id": review_id,
                "updated_at": _utc_now(),
            }
        )
        self._write_run(run)
        self._append_event("run_blocked_review", step_id, reason, run)

    def _block_error(self, run: dict[str, Any], reason: str) -> None:
        run.update(
            {
                "run_state": PocRunState.BLOCKED_ERROR.value,
                "blocking_reason": reason,
                "blocking_review_id": None,
                "updated_at": _utc_now(),
            }
        )
        self._write_run(run)
        self._append_event("run_blocked_error", str(run["current_step"]), reason, run)

    def _complete(self, run: dict[str, Any], step_id: str, summary: str) -> None:
        run.update(
            {
                "run_state": PocRunState.DONE.value,
                "current_step": step_id,
                "blocking_reason": None,
                "blocking_review_id": None,
                "updated_at": _utc_now(),
            }
        )
        self._write_run(run)
        self._append_event("run_done", step_id, summary, run)

    def _write_run(self, run: Mapping[str, Any]) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        path = self.runs_dir / f"{run['run_id']}.json"
        path.write_text(json.dumps(dict(run), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _append_event(
        self,
        event_type: str,
        step_id: str,
        summary: str,
        run: Mapping[str, Any],
    ) -> None:
        self.app_dir.mkdir(parents=True, exist_ok=True)
        now = _utc_now()
        event = {
            "event_id": _new_event_id(event_type, now, str(run["run_id"]), summary),
            "event_type": event_type,
            "occurred_at": now,
            "study_id": self.study_dir.name,
            "run_id": run["run_id"],
            "step_id": step_id,
            "summary": summary,
            "severity": "error" if event_type.endswith("error") else "ok",
            "related_refs": [{"ref_type": "run", "ref_id": str(run["run_id"]), "sha256": None}],
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _response(self, run: Mapping[str, Any], *, accepted: bool) -> PocRunResponse:
        return PocRunResponse(
            accepted=accepted,
            run_id=str(run["run_id"]),
            run_state=PocRunState(str(run["run_state"])),
            state_endpoint=f"/api/v1/studies/{self.study_dir.name}/poc-state",
            message=str(run.get("blocking_reason") or run.get("run_state") or "accepted"),
        )

    def _canonical_exists(self) -> bool:
        return (self.study_dir / CANONICAL_DATASET_PATH).exists()

    def _has_decision(self, review_id: str) -> bool:
        return ReviewQueue(self.study_dir).check_decision(review_id) is not None

    def _has_packet(self, review_id: str) -> bool:
        return ReviewQueue(self.study_dir).load_packet(review_id) is not None


def latest_poc_run(study_dir: str | Path) -> dict[str, Any] | None:
    runs_dir = Path(study_dir) / ".application_api" / "poc_runs"
    if not runs_dir.exists():
        return None
    runs: list[dict[str, Any]] = []
    for path in runs_dir.glob("run-*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            runs.append(payload)
    runs.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
    return runs[0] if runs else None


def load_poc_run(study_dir: str | Path, run_id: str) -> dict[str, Any] | None:
    path = Path(study_dir) / ".application_api" / "poc_runs" / f"{run_id}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PocRunnerError(f"Invalid POC run record: {run_id}")
    return payload


def list_poc_events(study_dir: str | Path) -> list[dict[str, Any]]:
    path = Path(study_dir) / ".application_api" / "poc_events.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PocRunnerError(f"JSON object expected: {path}")
    return payload


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PocRunnerError(f"YAML object expected: {path}")
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_run_id(study_id: str, now: str) -> str:
    digest = hashlib.sha256(f"{study_id}:{now}".encode("utf-8")).hexdigest()[:16]
    return f"run-poc-{digest}"


def _new_event_id(event_type: str, now: str, run_id: str, summary: str) -> str:
    digest = hashlib.sha256(
        f"{event_type}:{now}:{run_id}:{summary}".encode("utf-8")
    ).hexdigest()[:18]
    return f"evt-poc-{digest}"
