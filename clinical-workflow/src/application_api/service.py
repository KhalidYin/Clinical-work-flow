"""Read-only P8 Application API service.

The service derives every response from files under configured Study container
roots.  It does not cache business state, does not write Study files, and does
not call Runtime tools.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from src.application_api.poc_models import (
    LEGACY_POC_STEP_ALIASES,
    POC_STEP_DEFINITIONS,
    PocActionType,
    PocActiveStep,
    PocArtifactRef,
    PocBlocker,
    PocBlockerKind,
    PocDependencyRequirement,
    PocDependencyStatus,
    PocEvent,
    PocHealthItem,
    PocHealthSeverity,
    PocInputCheck,
    PocInputCheckState,
    PocInputCheckSummary,
    PocInputDependency,
    PocInputFile,
    PocNextAction,
    PocRecoveryAction,
    PocRunRequest,
    PocRunState,
    PocResumeRequest,
    PocStep,
    PocStepKind,
    PocStepState,
    PocState,
    normalize_poc_run_state,
)
from src.application_api.poc_runner import (
    PocRunner,
    PocRunnerError,
    latest_poc_run,
    list_poc_events,
    load_poc_run,
)
from src.runtime.pipeline_contract import PipelineStage
from src.runtime.review_protocol import (
    Decision,
    DecisionReceipt,
    FindingDecision,
    RejectionReason,
    ReviewQueue,
)


STUDY_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")
REVIEW_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,127}$")
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{16,128}$")
SUPPORTED_CONTAINER_ID = "clinical-studies"

class ApplicationApiError(RuntimeError):
    """Structured API error returned by the FastAPI adapter."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = dict(details or {})

    def as_response(self) -> dict[str, Any]:
        response: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.details:
            response["details"] = self.details
        return response


@dataclass(frozen=True, slots=True)
class ApplicationApiConfig:
    """Local container roots authorized for Study discovery."""

    container_roots: Mapping[str, Path]

    @classmethod
    def for_platform_root(cls, platform_root: str | Path) -> "ApplicationApiConfig":
        root = Path(platform_root)
        return cls(container_roots={SUPPORTED_CONTAINER_ID: root / "clinical-studies"})

    def normalized_roots(self) -> dict[str, Path]:
        roots: dict[str, Path] = {}
        for container_id, root in self.container_roots.items():
            if container_id != SUPPORTED_CONTAINER_ID:
                raise ApplicationApiError(
                    "path_not_authorized",
                    f"unsupported container id: {container_id}",
                    status_code=400,
                )
            roots[container_id] = Path(root).resolve()
        return roots


@dataclass(frozen=True, slots=True)
class StudyRecord:
    """A discovered Study directory and parsed project metadata."""

    study_id: str
    container_id: str
    container_root: Path
    study_dir: Path
    project: dict[str, Any]


class ApplicationApiService:
    """Local-first facade over Study files.

    P8-P3 write operations are limited to Application API run request files,
    event records, and Review Protocol DecisionReceipt files.
    """

    def __init__(self, config: ApplicationApiConfig) -> None:
        self._roots = config.normalized_roots()

    def list_studies(self) -> dict[str, Any]:
        records, partial_errors = self._discover_studies()
        return {
            "studies": [self._study_summary(record) for record in records],
            "partial_errors": partial_errors,
        }

    def get_status(self, study_id: str) -> dict[str, Any]:
        record = self._get_record(study_id)
        artifacts, partial_errors = self._list_artifact_summaries(record)
        pending_review_count = self._pending_review_count(record)
        stages = self._stage_statuses(artifacts, pending_review_count)
        active_run = self._active_run(record)
        incomplete_reasons = []
        if partial_errors:
            incomplete_reasons.append("artifact scan returned partial errors")
        if self._manifest_lock(record)["status"] != "locked":
            incomplete_reasons.append("runtime manifest or knowledge lock unavailable")
        return {
            "study_id": record.study_id,
            "stage_order": [stage.value for stage in PipelineStage],
            "stages": stages,
            "run_state": self._run_state(
                stages,
                pending_review_count,
                partial_errors,
                active_run,
            ),
            "pending_review_count": pending_review_count,
            "knowledge_lock": self._manifest_lock(record),
            "incomplete_reasons": incomplete_reasons,
        }

    def list_artifacts(self, study_id: str) -> dict[str, Any]:
        record = self._get_record(study_id)
        artifacts, partial_errors = self._list_artifact_summaries(record)
        return {"artifacts": artifacts, "partial_errors": partial_errors}

    def get_artifact(self, study_id: str, artifact_id: str) -> dict[str, Any]:
        record = self._get_record(study_id)
        artifacts, _ = self._list_artifact_summaries(record)
        artifact = next((item for item in artifacts if item["artifact_id"] == artifact_id), None)
        if artifact is None:
            raise ApplicationApiError(
                "artifact_not_found",
                f"registered artifact not found: {artifact_id}",
                status_code=404,
            )
        relative_path = artifact["_study_relative_path"]
        artifact_path = self._safe_study_path(record, relative_path)
        return {
            "artifact": _without_private_fields(artifact),
            "registered_ref": {
                "container_id": record.container_id,
                "relative_path": _posix_relative(record.container_root, artifact_path),
                "sha256": artifact["sha256"],
            },
            "preview": self._preview_artifact(artifact_path),
        }

    def get_context(self, study_id: str) -> dict[str, Any]:
        record = self._get_record(study_id)
        traceability = self._read_optional_json(
            record,
            "output/sdtm/traceability/ae_traceability_report.json",
        )
        source_refs: list[dict[str, Any]] = []
        rule_refs: list[dict[str, Any]] = []
        study_decision_refs: list[dict[str, Any]] = []
        gaps: list[str] = []
        if traceability:
            source_refs = _unique_related_refs(
                {
                    evidence["source_id"]: evidence.get("artifact_sha256")
                    for rule in traceability.get("applied_rules", [])
                    for evidence in rule.get("evidence", [])
                    if evidence.get("source_id")
                },
                "source",
            )
            rule_refs = _unique_related_refs(
                {rule["rule_id"]: None for rule in traceability.get("applied_rules", [])},
                "rule",
            )
            study_decision_refs = _unique_related_refs(
                {item: None for item in traceability.get("applied_study_decisions", [])},
                "study_decision",
            )
            gaps = [
                str(item.get("gap_id", item))
                for item in traceability.get("explicit_gaps", [])
            ]
        return {
            "study_id": record.study_id,
            "bundle_lock": self._bundle_lock(),
            "source_refs": source_refs,
            "rule_refs": rule_refs,
            "study_decision_refs": study_decision_refs,
            "gaps": gaps,
        }

    def get_provenance(self, study_id: str) -> dict[str, Any]:
        record = self._get_record(study_id)
        artifacts, _ = self._list_artifact_summaries(record)
        trace_refs = []
        for artifact in artifacts:
            artifact_id = artifact["artifact_id"]
            if artifact["artifact_type"] in {"provenance", "traceability_report"}:
                trace_refs.append(
                    {"ref_type": "artifact", "ref_id": artifact_id, "sha256": artifact["sha256"]}
                )
        return {
            "study_id": record.study_id,
            "traceability_refs": trace_refs,
            "artifacts": [_without_private_fields(item) for item in artifacts],
        }

    def get_audit(self, study_id: str, cursor: str | None = None) -> dict[str, Any]:
        record = self._get_record(study_id)
        events = self._audit_events(record)
        if cursor:
            events = [event for event in events if event["event_id"] > cursor]
        return {"events": events, "next_cursor": events[-1]["event_id"] if events else _empty_cursor()}

    def get_poc_state(self, study_id: str) -> dict[str, Any]:
        """Return the bounded P9.1 POC state contract.

        P1 intentionally exposes a contract-complete state without executing the
        runner.  P2 replaces the contract placeholder with real start/resume
        execution while preserving this payload shape.
        """

        record = self._get_record(study_id)
        return self._poc_contract_state(record).model_dump(mode="json")

    def start_poc_run(
        self,
        study_id: str,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        record = self._get_record(study_id)
        parsed = PocRunRequest.model_validate(dict(request))
        try:
            response = self._poc_runner(record).start(parsed)
        except PocRunnerError as exc:
            raise ApplicationApiError(
                "poc_runner_failed",
                str(exc),
                status_code=409,
            ) from exc
        return response.model_dump(mode="json")

    def get_poc_run(self, study_id: str, run_id: str) -> dict[str, Any]:
        record = self._get_record(study_id)
        if not re.fullmatch(r"run-[A-Za-z0-9_-]{8,64}", run_id):
            raise ApplicationApiError("invalid_request", f"invalid run_id: {run_id}", status_code=400)
        run = load_poc_run(record.study_dir, run_id)
        if run is None:
            raise ApplicationApiError("run_not_found", f"POC run not found: {run_id}", status_code=404)
        raw_state = str(run.get("run_state", "running"))
        run_state = normalize_poc_run_state(raw_state)
        blocker = self._poc_run_blocker(run, run_state, [])
        return {
            "run_id": run["run_id"],
            "study_id": record.study_id,
            "run_state": run_state.value,
            "legacy_run_state": raw_state if raw_state != run_state.value else None,
            "current_step": self._legacy_poc_step_id(
                str(run.get("current_step") or "input-check"),
                str(run.get("blocking_review_id") or "") or None,
            ),
            "blocker": blocker.model_dump(mode="json") if blocker else None,
            "state_endpoint": f"/api/v1/studies/{record.study_id}/poc-state",
        }

    def resume_poc_run(
        self,
        study_id: str,
        run_id: str,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        record = self._get_record(study_id)
        if not re.fullmatch(r"run-[A-Za-z0-9_-]{8,64}", run_id):
            raise ApplicationApiError("invalid_request", f"invalid run_id: {run_id}", status_code=400)
        parsed = PocResumeRequest.model_validate(dict(request))
        try:
            response = self._poc_runner(record).resume(run_id, parsed)
        except PocRunnerError as exc:
            raise ApplicationApiError(
                "poc_runner_failed",
                str(exc),
                status_code=409,
            ) from exc
        return response.model_dump(mode="json")

    def start_run(
        self,
        study_id: str,
        request: Mapping[str, Any],
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Persist a Runtime run request without executing Runtime tools."""

        record = self._get_record(study_id)
        request_hash = _canonical_sha256(request)
        existing = self._read_idempotency(record, "start_run", idempotency_key, request_hash)
        if existing is not None:
            return existing
        active = self._active_run(record)
        if active is not None:
            raise ApplicationApiError(
                "runtime_busy",
                f"study already has an active run: {active['run_id']}",
                status_code=409,
                retryable=True,
            )
        intent = str(request.get("intent", "")).strip()
        if len(intent) < 3:
            raise ApplicationApiError(
                "invalid_request",
                "run intent must contain at least 3 characters",
                status_code=400,
            )
        target_stage = self._validate_target_stage(request.get("target_stage"))
        pending_reviews = self._pending_review_ids(record)
        run_state = "blocked_review" if pending_reviews else "queued"
        blocking_reason = (
            f"pending review: {pending_reviews[0]}" if pending_reviews else None
        )
        now = _utc_now()
        run_id = _new_run_id(record.study_id, idempotency_key, now)
        event_type = "run_blocked" if pending_reviews else "run_requested"
        event = self._append_app_event(
            record,
            event_type=event_type,
            stage_id=target_stage,
            related_refs=[{"ref_type": "run", "ref_id": run_id, "sha256": None}],
        )
        run_record = {
            "run_id": run_id,
            "study_id": record.study_id,
            "run_state": run_state,
            "current_stage": target_stage,
            "blocking_reason": blocking_reason,
            "event_cursor": event["event_id"],
            "intent": intent,
            "dataset": request.get("dataset"),
            "dry_run": bool(request.get("dry_run", False)),
            "idempotency_key": idempotency_key,
            "created_at": now,
            "updated_at": now,
            "resume_count": 0,
            "runtime_execution_started": False,
        }
        self._write_run(record, run_record)
        response = {
            "run_id": run_id,
            "run_state": run_state,
            "accepted": True,
            "idempotency_key": idempotency_key,
        }
        self._write_idempotency(record, "start_run", idempotency_key, request_hash, response)
        return response

    def get_run(self, study_id: str, run_id: str) -> dict[str, Any]:
        record = self._get_record(study_id)
        run = self._load_run(record, run_id)
        if run is None:
            raise ApplicationApiError("run_not_found", f"run not found: {run_id}", status_code=404)
        return self._run_status_response(run)

    def resume_run(
        self,
        study_id: str,
        run_id: str,
        request: Mapping[str, Any],
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        record = self._get_record(study_id)
        request_hash = _canonical_sha256(request)
        existing = self._read_idempotency(record, "resume_run", idempotency_key, request_hash)
        if existing is not None:
            return existing
        run = self._load_run(record, run_id)
        if run is None:
            raise ApplicationApiError("run_not_found", f"run not found: {run_id}", status_code=404)
        if run["run_state"] in {"completed", "failed"}:
            raise ApplicationApiError(
                "runtime_busy",
                f"run is terminal and cannot be resumed: {run_id}",
                status_code=409,
            )
        reason = request.get("reason")
        if reason not in {"review_decision_available", "retry_after_failure", "operator_resume"}:
            raise ApplicationApiError("invalid_request", "invalid resume reason", status_code=400)
        pending_reviews = self._pending_review_ids(record)
        run_state = "blocked_review" if pending_reviews else "queued"
        event_type = "run_blocked" if pending_reviews else "run_requested"
        event = self._append_app_event(
            record,
            event_type=event_type,
            stage_id=str(run["current_stage"]),
            related_refs=[{"ref_type": "run", "ref_id": run_id, "sha256": None}],
        )
        now = _utc_now()
        run.update(
            {
                "run_state": run_state,
                "blocking_reason": (
                    f"pending review: {pending_reviews[0]}" if pending_reviews else None
                ),
                "event_cursor": event["event_id"],
                "updated_at": now,
                "resume_count": int(run.get("resume_count", 0)) + 1,
                "last_resume_reason": reason,
            }
        )
        self._write_run(record, run)
        response = {
            "run_id": run_id,
            "run_state": run_state,
            "accepted": True,
            "idempotency_key": idempotency_key,
        }
        self._write_idempotency(record, "resume_run", idempotency_key, request_hash, response)
        return response

    def list_events(self, study_id: str, cursor: str | None = None) -> dict[str, Any]:
        return self.get_audit(study_id, cursor=cursor)

    def _poc_contract_state(self, record: StudyRecord) -> PocState:
        artifacts, partial_errors = self._list_artifact_summaries(record)
        artifact_refs = self._poc_artifact_refs(artifacts)
        pending_reviews = self._pending_review_ids(record)
        active_run = latest_poc_run(record.study_dir)
        source = self._poc_source_summary(record)
        input_check = self._poc_input_check(active_run, source)
        legacy_run_state = None
        blocker = None

        if active_run is not None:
            raw_state = str(active_run.get("run_state", "running"))
            run_state = normalize_poc_run_state(raw_state)
            legacy_run_state = raw_state if raw_state not in {state.value for state in PocRunState} else None
            blocker = self._poc_run_blocker(active_run, run_state, partial_errors)
        elif partial_errors:
            run_state = PocRunState.BLOCKED
            blocker = self._poc_system_blocker(partial_errors)
        elif pending_reviews:
            run_state = PocRunState.BLOCKED
            review_id = pending_reviews[0]
            stage_id = self._legacy_poc_step_id("review-gate", review_id)
            blocker = PocBlocker(
                kind=PocBlockerKind.REVIEW,
                stage_id=stage_id,
                code="pending_review_without_run",
                summary="存在待审核 ReviewPacket",
                detail="提交 DecisionReceipt 后，由 Runner 显式 Resume；ReviewPacket 本身不代表步骤完成。",
                evidence_refs=[f".review_queue/{review_id}.json"],
                recovery_action=PocRecoveryAction.SUBMIT_REVIEW_DECISION,
                review_id=review_id,
            )
        else:
            run_state = PocRunState.IDLE

        steps = self._poc_contract_steps(active_run, run_state, blocker, artifact_refs)
        active_step = self._poc_active_step(run_state, blocker, steps)
        blocking_reason = blocker.summary if blocker else None
        return PocState(
            study_id=record.study_id,
            run_id=str(active_run["run_id"]) if active_run else None,
            run_state=run_state,
            legacy_run_state=legacy_run_state,
            source=source,
            knowledge=self._poc_knowledge_summary(record),
            input_check=input_check,
            blocker=blocker,
            blocking_reason=blocking_reason,
            active_step=active_step,
            steps=steps,
            next_actions=self._poc_next_actions(record, run_state, blocker),
            health=self._poc_health(record, partial_errors),
            events=self._poc_events(record),
            partial_errors=list(partial_errors),
        )

    def _poc_artifact_refs(self, artifacts: Iterable[dict[str, Any]]) -> list[PocArtifactRef]:
        refs: list[PocArtifactRef] = []
        for artifact in artifacts:
            display = str(artifact["display_name"])
            suffix = Path(display).suffix.lower()
            kind = {
                ".json": "json",
                ".csv": "csv",
                ".txt": "text",
                ".yaml": "yaml",
                ".yml": "yaml",
            }.get(suffix, "unknown")
            refs.append(
                PocArtifactRef(
                    artifact_id=str(artifact["artifact_id"]),
                    label=display,
                    relative_path=display,
                    kind=kind,
                    sha256=str(artifact["sha256"]),
                    preview_available=bool(artifact.get("preview_available")),
                )
            )
        return refs

    def _poc_contract_steps(
        self,
        active_run: Mapping[str, Any] | None,
        run_state: PocRunState,
        blocker: PocBlocker | None,
        artifact_refs: list[PocArtifactRef],
    ) -> list[PocStep]:
        if active_run and str(active_run.get("schema_version")) == "2.0" and active_run.get("steps"):
            steps = [PocStep.model_validate(item) for item in active_run["steps"]]
        else:
            current_step = self._legacy_poc_step_id(
                str((active_run or {}).get("current_step") or "input-check"),
                str((active_run or {}).get("blocking_review_id") or "") or None,
            )
            steps = []
            for ordinal, (step_id, title) in enumerate(POC_STEP_DEFINITIONS, start=1):
                state = PocStepState.PENDING
                kind = PocStepKind.INSTRUCTION
                summary = "等待 Runner v2 ledger；未根据磁盘产物推断完成状态。"
                if run_state is PocRunState.RUNNING and step_id == current_step:
                    state = PocStepState.RUNNING
                    summary = "Legacy run 正在此阶段执行；P2 将写入原生 v2 ledger。"
                elif run_state is PocRunState.BLOCKED and blocker and step_id == blocker.stage_id:
                    state = PocStepState.BLOCKED
                    kind = PocStepKind.REVIEW if blocker.kind is PocBlockerKind.REVIEW else PocStepKind.ERROR
                    summary = blocker.summary
                elif run_state is PocRunState.DONE:
                    state = PocStepState.DONE if step_id == "canonical-ae" else PocStepState.SKIPPED
                    summary = (
                        "Legacy run 记录为完成。"
                        if step_id == "canonical-ae"
                        else "Legacy record 未包含可验证的逐步 ledger。"
                    )
                steps.append(
                    PocStep(
                        step_id=step_id,
                        ordinal=ordinal,
                        title=title,
                        state=state,
                        kind=kind,
                        summary=summary,
                        blocking_reason=blocker.summary if blocker and step_id == blocker.stage_id else None,
                        review_id=blocker.review_id if blocker and step_id == blocker.stage_id else None,
                    )
                )

        artifacts_by_step: dict[str, list[PocArtifactRef]] = {}
        for artifact in artifact_refs:
            step_id = self._poc_artifact_step_id(artifact.relative_path)
            artifacts_by_step.setdefault(step_id, []).append(artifact)
        for step in steps:
            supplemental = artifacts_by_step.get(step.step_id, [])
            known = {item.artifact_id for item in step.artifact_refs}
            step.artifact_refs.extend(item for item in supplemental if item.artifact_id not in known)
        return steps

    def _poc_active_step(
        self,
        run_state: PocRunState,
        blocker: PocBlocker | None,
        steps: list[PocStep],
    ) -> PocActiveStep:
        if blocker is not None:
            step = next(item for item in steps if item.step_id == blocker.stage_id)
            return PocActiveStep(
                step_id=step.step_id,
                kind=step.kind,
                title=step.title,
                summary=blocker.summary,
                blocking_reason=blocker.summary,
                next_instruction=blocker.detail,
                review_id=blocker.review_id,
                artifact_refs=step.artifact_refs,
            )
        if run_state is PocRunState.RUNNING:
            step = next((item for item in steps if item.state is PocStepState.RUNNING), steps[0])
            return PocActiveStep(
                step_id=step.step_id,
                kind=step.kind,
                title=step.title,
                summary=step.summary,
                next_instruction="等待同步执行返回或刷新状态。",
                artifact_refs=step.artifact_refs,
            )
        if run_state is PocRunState.DONE:
            step = next(item for item in steps if item.step_id == "canonical-ae")
            return PocActiveStep(
                step_id=step.step_id,
                kind=PocStepKind.COMPLETE,
                title=step.title,
                summary="POC run ledger 已到达完成状态。",
                artifact_refs=step.artifact_refs,
            )
        step = steps[0]
        return PocActiveStep(
            step_id=step.step_id,
            kind=PocStepKind.INSTRUCTION,
            title="准备执行 Input Check",
            summary="点击 Run POC 后先验证目标所需输入，不从已有产物推断步骤完成。",
            next_instruction="确认 SAS7BDAT 已登记后运行 POC。",
            artifact_refs=step.artifact_refs,
        )

    def _poc_run_blocker(
        self,
        active_run: Mapping[str, Any],
        run_state: PocRunState,
        partial_errors: Iterable[dict[str, Any]],
    ) -> PocBlocker | None:
        if run_state is not PocRunState.BLOCKED:
            return None
        if str(active_run.get("schema_version")) == "2.0" and active_run.get("blocker"):
            return PocBlocker.model_validate(active_run["blocker"])

        raw_state = str(active_run.get("run_state") or "blocked_error")
        review_id = str(active_run.get("blocking_review_id") or "") or None
        stage_id = self._legacy_poc_step_id(
            str(active_run.get("current_step") or "input-check"),
            review_id,
        )
        reason = str(active_run.get("blocking_reason") or "Legacy POC run is blocked")
        if raw_state == "blocked_review":
            return PocBlocker(
                kind=PocBlockerKind.REVIEW,
                stage_id=stage_id,
                code="legacy_pending_review",
                summary=reason,
                detail="这是 legacy run 的兼容视图；提交 DecisionReceipt 后使用 Resume。",
                evidence_refs=[f".review_queue/{review_id}.json"] if review_id else [],
                recovery_action=PocRecoveryAction.SUBMIT_REVIEW_DECISION,
                review_id=review_id,
            )
        if partial := list(partial_errors):
            return self._poc_system_blocker(partial, stage_id=stage_id, summary=reason)
        return PocBlocker(
            kind=PocBlockerKind.SYSTEM,
            stage_id=stage_id,
            code="legacy_runner_error",
            summary=reason,
            detail="修复可见根因后只重试当前阶段；普通 Run 不应复用这个 blocked run。",
            recovery_action=PocRecoveryAction.RETRY_CURRENT_STEP,
            retryable=True,
        )

    def _poc_system_blocker(
        self,
        partial_errors: Iterable[dict[str, Any]],
        *,
        stage_id: str = "input-check",
        summary: str = "Study 状态读取不完整",
    ) -> PocBlocker:
        partial = list(partial_errors)
        return PocBlocker(
            kind=PocBlockerKind.SYSTEM,
            stage_id=stage_id,
            code="study_state_partial_error",
            summary=summary,
            detail="Application API 无法完整读取 Study 证据；修复列出的文件或权限问题后刷新。",
            affected_artifacts=[str(item.get("message", "unknown")) for item in partial],
            evidence_refs=["poc-state.partial_errors"],
            recovery_action=PocRecoveryAction.REFRESH,
        )

    def _poc_input_check(
        self,
        active_run: Mapping[str, Any] | None,
        source: Mapping[str, Any],
    ) -> PocInputCheck:
        if active_run and str(active_run.get("schema_version")) == "2.0" and active_run.get("input_check"):
            return PocInputCheck.model_validate(active_run["input_check"])

        source_path = str(source.get("relative_path") or "input/edc/registered-source.sas7bdat")
        source_available = bool(source.get("relative_path") and source.get("sha256"))
        return PocInputCheck(
            summary=PocInputCheckSummary(
                status=PocInputCheckState.PARTIAL if source_available else PocInputCheckState.NOT_RUN,
                required_total=1,
                required_ready=1 if source_available else 0,
                blocking_count=0 if source_available else 1,
                warning_count=1,
                message=(
                    "已读取 legacy source metadata；完整 parser/profile 检查将在 Runner v2 执行。"
                    if source_available
                    else "Input Check 尚未执行。"
                ),
            ),
            files=[
                PocInputFile(
                    source_id="ae-source-data",
                    label="AE SAS7BDAT source",
                    relative_path=source_path,
                    format=str(source.get("format") or "sas7bdat"),
                    exists=source_available,
                    sha256=str(source["sha256"]) if source.get("sha256") else None,
                    row_count=source.get("row_count"),
                    column_count=source.get("column_count"),
                    warnings=["legacy metadata does not prove parser/profile checks"],
                )
            ],
            dependencies=[
                PocInputDependency(
                    input_id="ae-source-data",
                    label="AE raw data",
                    requirement=PocDependencyRequirement.REQUIRED,
                    status=(
                        PocDependencyStatus.AVAILABLE
                        if source_available
                        else PocDependencyStatus.MISSING
                    ),
                    blocking=not source_available,
                    evidence_refs=[source_path] if source_available else [],
                ),
                *[
                    PocInputDependency(
                        input_id=input_id,
                        label=label,
                        requirement=PocDependencyRequirement.NOT_REQUIRED,
                        status=PocDependencyStatus.NOT_REQUIRED,
                        blocking=False,
                        detail="当前 sdtm_ae_dataset raw-only POC 不以该文档为固定前置条件。",
                    )
                    for input_id, label in (
                        ("protocol", "Protocol"),
                        ("sap", "SAP"),
                        ("crf", "CRF"),
                    )
                ],
            ],
            warnings=["compatibility view: full Input Check ledger is not available"],
        )

    @staticmethod
    def _legacy_poc_step_id(step_id: str, review_id: str | None = None) -> str:
        if step_id == "review-gate" and review_id and "program" in review_id.lower():
            return "validation-review"
        return LEGACY_POC_STEP_ALIASES.get(step_id, "input-check")

    @staticmethod
    def _poc_artifact_step_id(relative_path: str) -> str:
        path = relative_path.replace("\\", "/")
        if "minimum-information" in path:
            return "minimum-information"
        if path.startswith("knowledge/"):
            return "wiki-context"
        if path.startswith("work/mapping/"):
            return "mapping-spec"
        if path.startswith("programs/") or path.startswith("output/sdtm/drafts/"):
            return "program-execution"
        if "validation" in path or ".review_queue/" in path:
            return "validation-review"
        if path.startswith("output/sdtm/datasets/"):
            return "canonical-ae"
        return "input-check"

    def _poc_next_actions(
        self,
        record: StudyRecord,
        run_state: PocRunState,
        blocker: PocBlocker | None,
    ) -> list[PocNextAction]:
        active_run = latest_poc_run(record.study_dir)
        run_id = str(active_run["run_id"]) if active_run else "{run_id}"
        review_blocker = bool(
            blocker
            and blocker.kind in {PocBlockerKind.REVIEW, PocBlockerKind.VALIDATION}
            and blocker.review_id
        )
        decision_available = bool(
            review_blocker
            and ReviewQueue(record.study_dir).check_decision(str(blocker.review_id)) is not None
        )
        retry_enabled = bool(
            run_state is PocRunState.BLOCKED
            and blocker
            and blocker.retryable
            and (
                blocker.kind in {PocBlockerKind.INPUT, PocBlockerKind.SYSTEM}
                or (blocker.kind is PocBlockerKind.VALIDATION and decision_available)
            )
        )
        resume_enabled = bool(
            run_state is PocRunState.BLOCKED
            and blocker
            and blocker.kind is PocBlockerKind.REVIEW
            and decision_available
        )
        open_review_enabled = bool(review_blocker and not decision_available)
        actions = [
            PocNextAction(
                action_id=PocActionType.RUN_POC,
                label="Run POC",
                enabled=run_state is PocRunState.IDLE,
                primary=run_state is PocRunState.IDLE,
                reason=None if run_state is PocRunState.IDLE else f"current state is {run_state.value}",
                endpoint=f"/api/v1/studies/{record.study_id}/poc-runs",
            ),
            PocNextAction(
                action_id=PocActionType.RETRY_CURRENT_STEP,
                label="Retry current step",
                enabled=retry_enabled,
                primary=retry_enabled,
                reason=(
                    None
                    if retry_enabled
                    else "修复当前阻断；validation blocker 还需先提交 DecisionReceipt。"
                ),
                endpoint=f"/api/v1/studies/{record.study_id}/poc-runs/{run_id}/resume",
            ),
            PocNextAction(
                action_id=PocActionType.OPEN_REVIEW,
                label="Review",
                enabled=open_review_enabled,
                primary=open_review_enabled,
                reason=None if open_review_enabled else "no pending review decision",
                method="GET",
                endpoint=f"/api/v1/studies/{record.study_id}/reviews",
            ),
            PocNextAction(
                action_id=PocActionType.RESUME,
                label="Resume",
                enabled=resume_enabled,
                primary=resume_enabled,
                reason=None if resume_enabled else "DecisionReceipt is not available",
                endpoint=f"/api/v1/studies/{record.study_id}/poc-runs/{run_id}/resume",
            ),
            PocNextAction(
                action_id=PocActionType.REFRESH,
                label="Refresh",
                enabled=True,
                method="GET",
                endpoint=f"/api/v1/studies/{record.study_id}/poc-state",
            ),
            PocNextAction(
                action_id=PocActionType.OPEN_OUTPUT_FOLDER,
                label="Open output folder",
                enabled=False,
                reason="browser cannot open local folders through the API contract",
                method="GET",
                endpoint=f"/api/v1/studies/{record.study_id}/artifacts",
            ),
        ]
        return actions

    def _poc_health(
        self,
        record: StudyRecord,
        partial_errors: Iterable[dict[str, Any]],
    ) -> list[PocHealthItem]:
        items = [
            PocHealthItem(
                check_id="study-visible",
                severity=PocHealthSeverity.OK,
                summary="Study directory is visible to Application API",
                evidence_refs=["project.yaml"],
            )
        ]
        if partial := list(partial_errors):
            items.append(
                PocHealthItem(
                    check_id="artifact-scan",
                    severity=PocHealthSeverity.ERROR,
                    summary="Artifact scan returned partial errors",
                    detail=json.dumps(partial, ensure_ascii=False),
                )
            )
        if not (record.study_dir / "runtime-manifest.yaml").exists():
            items.append(
                PocHealthItem(
                    check_id="runtime-manifest",
                    severity=PocHealthSeverity.WARNING,
                    summary="runtime-manifest.yaml is missing; P9.1 POC still runs under bounded test scope",
                    evidence_refs=["runtime-manifest.draft.yaml"],
                )
            )
        return items

    def _poc_source_summary(self, record: StudyRecord) -> dict[str, Any]:
        metadata = self._read_optional_json(record, "work/derived/edc/source-metadata.json") or {}
        source = metadata.get("source", {}) if isinstance(metadata, dict) else {}
        return {
            "format": source.get("format"),
            "relative_path": source.get("relative_path"),
            "sha256": source.get("sha256"),
            "row_count": (metadata.get("dataset") or {}).get("row_count") if isinstance(metadata, dict) else None,
            "column_count": (metadata.get("dataset") or {}).get("column_count") if isinstance(metadata, dict) else None,
        }

    def _poc_knowledge_summary(self, record: StudyRecord) -> dict[str, Any]:
        reuse = self._read_optional_json(
            record,
            "knowledge/promotion_candidates/ae-rule-reuse-context.json",
        ) or {}
        return {
            "test_only": True,
            "status": "available" if reuse else "missing",
            "scope": "p9-poc-test-only",
            "rule_refs": reuse.get("rule_refs", []) if isinstance(reuse, dict) else [],
        }

    def _poc_events(self, record: StudyRecord) -> list[PocEvent]:
        events = []
        for raw in list_poc_events(record.study_dir)[-20:]:
            events.append(
                PocEvent(
                    event_id=str(raw["event_id"]),
                    event_type=str(raw["event_type"]),
                    occurred_at=str(raw["occurred_at"]),
                    run_id=str(raw.get("run_id")) if raw.get("run_id") else None,
                    step_id=str(raw.get("step_id")) if raw.get("step_id") else None,
                    summary=str(raw.get("summary") or raw["event_type"]),
                    severity=str(raw.get("severity", "ok")),
                    related_refs=list(raw.get("related_refs") or []),
                )
            )
        return events

    def _poc_runner(self, record: StudyRecord) -> PocRunner:
        sibling_wiki = record.container_root.parent / "clinical-llm-wiki"
        if sibling_wiki.exists():
            return PocRunner(record.study_dir, sibling_wiki)
        platform_wiki = Path(__file__).resolve().parents[3] / "clinical-llm-wiki"
        return PocRunner(record.study_dir, platform_wiki)

    def list_reviews(self, study_id: str) -> dict[str, Any]:
        record = self._get_record(study_id)
        queue = record.study_dir / ".review_queue"
        reviews: list[dict[str, Any]] = []
        partial_errors: list[dict[str, Any]] = []
        if not queue.exists():
            return {"reviews": [], "partial_errors": []}
        for path in sorted(queue.glob("*.json")):
            name = path.name
            if name.startswith(".") or any(
                suffix in name for suffix in ("_decision", "_confirmation", "_rework")
            ):
                continue
            try:
                packet = json.loads(path.read_text(encoding="utf-8"))
                reviews.append(self._review_summary(record, path, packet))
            except Exception as exc:
                partial_errors.append(_error("schema_validation_failed", f"{name}: {exc}"))
        return {"reviews": reviews, "partial_errors": partial_errors}

    def submit_review_decision(
        self,
        study_id: str,
        review_id: str,
        request: Mapping[str, Any],
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        record = self._get_record(study_id)
        request_hash = _canonical_sha256(request)
        review_id = _safe_review_id(review_id)
        existing = self._read_idempotency(
            record,
            "submit_review_decision",
            idempotency_key,
            request_hash,
        )
        if existing is not None:
            return existing
        queue = ReviewQueue(record.study_dir)
        packet = queue.load_packet(review_id)
        if packet is None:
            raise ApplicationApiError(
                "review_not_found",
                f"review not found: {review_id}",
                status_code=404,
            )
        packet_path = record.study_dir / ".review_queue" / f"{review_id}.json"
        packet_sha256 = _sha256_file(packet_path)
        if request.get("packet_sha256") != packet_sha256:
            raise ApplicationApiError(
                "stale_decision",
                "packet_sha256 does not match current ReviewPacket",
                status_code=412,
            )
        if request.get("review_id") != review_id:
            raise ApplicationApiError(
                "invalid_request",
                "request review_id must match path review_id",
                status_code=400,
            )
        existing_decision = record.study_dir / ".review_queue" / f"{review_id}_decision.json"
        if existing_decision.exists():
            raise ApplicationApiError(
                "review_not_pending",
                f"review already has a DecisionReceipt: {review_id}",
                status_code=409,
            )
        decisions = self._decision_objects(packet.findings_needing_decision(), request)
        receipt = DecisionReceipt(
            review_id=review_id,
            reviewer=str(request.get("reviewer", "")),
            decisions=decisions,
            general_notes=str(request.get("general_notes", "")),
        )
        try:
            decision_path = queue.submit_decision(receipt)
        except ValueError as exc:
            raise ApplicationApiError(
                "schema_validation_failed",
                f"DecisionReceipt rejected by Review Protocol: {exc}",
                status_code=400,
            ) from exc
        decision_sha256 = _sha256_file(decision_path)
        self._append_app_event(
            record,
            event_type="decision_receipt_written",
            stage_id=PipelineStage.SDTM_SPEC.value,
            related_refs=[
                {"ref_type": "review", "ref_id": review_id, "sha256": packet_sha256},
                {
                    "ref_type": "decision",
                    "ref_id": decision_path.stem,
                    "sha256": decision_sha256,
                },
            ],
        )
        response = {
            "review_id": review_id,
            "decision_receipt_id": decision_path.stem,
            "written": True,
            "idempotency_key": idempotency_key,
        }
        self._write_idempotency(
            record,
            "submit_review_decision",
            idempotency_key,
            request_hash,
            response,
        )
        return response

    def _validate_target_stage(self, value: object) -> str:
        if value is None:
            return PipelineStage.SDTM_PROGRAMMING.value
        try:
            return PipelineStage(str(value)).value
        except ValueError as exc:
            raise ApplicationApiError(
                "invalid_request",
                f"unknown target_stage: {value}",
                status_code=400,
            ) from exc

    def _app_dir(self, record: StudyRecord) -> Path:
        path = record.study_dir / ".application_api"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _runs_dir(self, record: StudyRecord) -> Path:
        path = self._app_dir(record) / "runs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _idempotency_dir(self, record: StudyRecord) -> Path:
        path = self._app_dir(record) / "idempotency"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _events_path(self, record: StudyRecord) -> Path:
        return self._app_dir(record) / "events.jsonl"

    def _load_run(self, record: StudyRecord, run_id: str) -> dict[str, Any] | None:
        if not re.fullmatch(r"run-[A-Za-z0-9_-]{8,64}", run_id):
            raise ApplicationApiError("invalid_request", f"invalid run_id: {run_id}", status_code=400)
        path = self._runs_dir(record) / f"{run_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ApplicationApiError("schema_validation_failed", "run record must be an object")
        return data

    def _write_run(self, record: StudyRecord, run: Mapping[str, Any]) -> None:
        path = self._runs_dir(record) / f"{run['run_id']}.json"
        _write_json(path, dict(run))

    def _active_run(self, record: StudyRecord) -> dict[str, Any] | None:
        active_states = {"queued", "running", "blocked_review", "blocked_error"}
        runs: list[dict[str, Any]] = []
        runs_dir = record.study_dir / ".application_api" / "runs"
        if not runs_dir.exists():
            return None
        for path in runs_dir.glob("run-*.json"):
            try:
                run = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if isinstance(run, dict) and run.get("run_state") in active_states:
                runs.append(run)
        runs.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
        return runs[0] if runs else None

    def _run_status_response(self, run: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "run_id": run["run_id"],
            "study_id": run["study_id"],
            "run_state": run["run_state"],
            "current_stage": run["current_stage"],
            "blocking_reason": run.get("blocking_reason"),
            "event_cursor": run["event_cursor"],
        }

    def _idempotency_path(self, record: StudyRecord, operation: str, key: str) -> Path:
        safe_digest = hashlib.sha256(f"{operation}:{key}".encode("utf-8")).hexdigest()
        return self._idempotency_dir(record) / f"{safe_digest}.json"

    def _read_idempotency(
        self,
        record: StudyRecord,
        operation: str,
        key: str,
        request_hash: str,
    ) -> dict[str, Any] | None:
        if not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
            raise ApplicationApiError(
                "invalid_request",
                "Idempotency-Key must match ^[A-Za-z0-9_.:-]{16,128}$",
                status_code=400,
            )
        path = self._idempotency_path(record, operation, key)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("request_hash") != request_hash:
            raise ApplicationApiError(
                "idempotency_conflict",
                "same Idempotency-Key used with different request body",
                status_code=409,
            )
        response = data.get("response")
        if not isinstance(response, dict):
            raise ApplicationApiError("schema_validation_failed", "invalid idempotency record")
        return response

    def _write_idempotency(
        self,
        record: StudyRecord,
        operation: str,
        key: str,
        request_hash: str,
        response: Mapping[str, Any],
    ) -> None:
        _write_json(
            self._idempotency_path(record, operation, key),
            {
                "operation": operation,
                "idempotency_key_sha256": hashlib.sha256(key.encode("utf-8")).hexdigest(),
                "request_hash": request_hash,
                "response": dict(response),
                "created_at": _utc_now(),
            },
        )

    def _append_app_event(
        self,
        record: StudyRecord,
        *,
        event_type: str,
        stage_id: str,
        related_refs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        now = _utc_now()
        events_path = self._events_path(record)
        event = {
            "event_id": _new_event_id(
                record.study_id,
                event_type,
                now,
                related_refs,
                _next_event_sequence(events_path, now),
            ),
            "event_type": event_type,
            "occurred_at": now,
            "study_id": record.study_id,
            "stage_id": stage_id,
            "related_refs": related_refs,
        }
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return event

    def _application_events(self, record: StudyRecord) -> list[dict[str, Any]]:
        path = record.study_dir / ".application_api" / "events.jsonl"
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(raw, dict):
                events.append(
                    {
                        "event_id": str(raw["event_id"]),
                        "event_type": str(raw["event_type"]),
                        "occurred_at": str(raw["occurred_at"]),
                        "study_id": record.study_id,
                        "stage_id": raw.get("stage_id"),
                        "related_refs": list(raw.get("related_refs") or []),
                    }
                )
        return events

    def _pending_review_ids(self, record: StudyRecord) -> list[str]:
        queue = record.study_dir / ".review_queue"
        if not queue.exists():
            return []
        pending: list[str] = []
        for packet in sorted(queue.glob("*.json")):
            name = packet.name
            if name.startswith("."):
                continue
            if any(suffix in name for suffix in ("_decision", "_confirmation", "_rework")):
                continue
            decision = packet.with_name(packet.stem + "_decision.json")
            confirmation = packet.with_name(packet.stem + "_confirmation.json")
            if not decision.exists() and not confirmation.exists():
                pending.append(packet.stem)
        return pending

    def _review_summary(
        self,
        record: StudyRecord,
        path: Path,
        packet: Mapping[str, Any],
    ) -> dict[str, Any]:
        review_id = str(packet["review_id"])
        queue = record.study_dir / ".review_queue"
        decisions = sorted(queue.glob(f"{review_id}_decision*.json"))
        confirmation = queue / f"{review_id}_confirmation.json"
        rework = queue / f"{review_id}_rework.json"
        decision_state = "pending"
        if rework.exists():
            decision_state = "rejected"
        elif confirmation.exists():
            decision_state = "confirmed"
        elif decisions:
            decision_state = "decided"
            for decision_path in decisions:
                try:
                    receipt = DecisionReceipt.from_dict(
                        json.loads(decision_path.read_text(encoding="utf-8"))
                    )
                    if receipt.rejected_count():
                        decision_state = "rejected"
                        break
                except (json.JSONDecodeError, KeyError, ValueError):
                    decision_state = "invalid"
                    break
        return {
            "review_id": review_id,
            "review_type": packet.get("review_type", ""),
            "urgency": packet.get("urgency", "normal"),
            "decision_state": decision_state,
            "finding_count": len(packet.get("findings", [])),
            "packet_sha256": _sha256_file(path),
            "confirmation_sha256": _sha256_file(confirmation) if confirmation.exists() else None,
            "agent_summary": packet.get("agent_summary", ""),
            "source_documents": list(packet.get("source_documents", [])),
            "created_at": packet.get("created_at"),
            "findings": [_review_finding_summary(item) for item in packet.get("findings", [])],
        }

    def _decision_objects(
        self,
        expected_findings: Iterable[Any],
        request: Mapping[str, Any],
    ) -> list[FindingDecision]:
        reviewer = str(request.get("reviewer", "")).strip()
        if len(reviewer) < 2:
            raise ApplicationApiError("invalid_request", "reviewer is required", status_code=400)
        expected_ids = {finding.id for finding in expected_findings}
        raw_decisions = request.get("decisions")
        if not isinstance(raw_decisions, list) or not raw_decisions:
            raise ApplicationApiError("invalid_request", "decisions must be a non-empty list")
        seen: set[str] = set()
        decisions: list[FindingDecision] = []
        for item in raw_decisions:
            if not isinstance(item, Mapping):
                raise ApplicationApiError("invalid_request", "each decision must be an object")
            finding_id = str(item.get("finding_id", ""))
            if finding_id in seen:
                raise ApplicationApiError(
                    "schema_validation_failed",
                    f"duplicate finding decision: {finding_id}",
                    status_code=400,
                )
            if finding_id not in expected_ids:
                raise ApplicationApiError(
                    "schema_validation_failed",
                    f"unknown or auto-approved finding: {finding_id}",
                    status_code=400,
                )
            seen.add(finding_id)
            try:
                decision = Decision(str(item.get("decision")))
                rejection_reason = (
                    RejectionReason(str(item["rejection_reason"]))
                    if item.get("rejection_reason") is not None
                    else None
                )
            except ValueError as exc:
                raise ApplicationApiError(
                    "schema_validation_failed",
                    f"invalid finding decision: {finding_id}",
                    status_code=400,
                ) from exc
            decisions.append(
                FindingDecision(
                    finding_id=finding_id,
                    decision=decision,
                    modified_value=item.get("modified_value"),
                    rejection_reason=rejection_reason,
                    human_correction=item.get("human_correction"),
                    reference=item.get("reference"),
                    comment=item.get("comment"),
                )
            )
        if seen != expected_ids:
            missing = sorted(expected_ids - seen)
            raise ApplicationApiError(
                "schema_validation_failed",
                f"decisions do not cover all required findings: {missing}",
                status_code=400,
            )
        return decisions

    def _discover_studies(self) -> tuple[list[StudyRecord], list[dict[str, Any]]]:
        records: list[StudyRecord] = []
        partial_errors: list[dict[str, Any]] = []
        for container_id, root in self._roots.items():
            if not root.exists():
                partial_errors.append(
                    _error("path_not_authorized", f"container root not found: {container_id}")
                )
                continue
            for candidate in sorted(path for path in root.iterdir() if path.is_dir()):
                project_path = candidate / "project.yaml"
                if not project_path.exists():
                    continue
                try:
                    self._assert_inside(root, candidate)
                    project = _read_yaml(project_path)
                    study_id = _required_study_id(project)
                    records.append(
                        StudyRecord(
                            study_id=study_id,
                            container_id=container_id,
                            container_root=root,
                            study_dir=candidate.resolve(),
                            project=project,
                        )
                    )
                except Exception as exc:
                    partial_errors.append(
                        _error(
                            "schema_validation_failed",
                            f"invalid study at {candidate.name}: {exc}",
                        )
                    )
        records.sort(key=lambda record: self._last_activity(record), reverse=True)
        return records, partial_errors

    def _get_record(self, study_id: str) -> StudyRecord:
        if not STUDY_ID_PATTERN.fullmatch(study_id):
            raise ApplicationApiError(
                "invalid_request",
                f"invalid study_id: {study_id}",
                status_code=400,
            )
        records, _ = self._discover_studies()
        matches = [record for record in records if record.study_id == study_id]
        if not matches:
            raise ApplicationApiError(
                "study_not_found",
                f"study not found: {study_id}",
                status_code=404,
            )
        if len(matches) > 1:
            raise ApplicationApiError(
                "idempotency_conflict",
                f"duplicate study id discovered: {study_id}",
                status_code=409,
            )
        return matches[0]

    def _study_summary(self, record: StudyRecord) -> dict[str, Any]:
        artifacts, _ = self._list_artifact_summaries(record)
        pending = self._pending_review_count(record)
        stages = self._stage_statuses(artifacts, pending)
        active_run = self._active_run(record)
        return {
            "study_id": record.study_id,
            "title": record.project.get("protocol_id"),
            "therapeutic_area": record.project.get("therapeutic_area"),
            "current_stage": _current_stage(stages),
            "run_state": self._run_state(stages, pending, [], active_run),
            "pending_review_count": pending,
            "knowledge_lock": self._manifest_lock(record),
            "last_activity_at": _iso_mtime(self._last_activity_path(record)),
        }

    def _list_artifact_summaries(
        self,
        record: StudyRecord,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        artifacts: list[dict[str, Any]] = []
        partial_errors: list[dict[str, Any]] = []
        scan_roots = [record.study_dir / "output", record.study_dir / ".review_queue"]
        for scan_root in scan_roots:
            if not scan_root.exists():
                continue
            for path in sorted(item for item in scan_root.rglob("*") if item.is_file() or item.is_symlink()):
                try:
                    if path.is_symlink():
                        raise ApplicationApiError(
                            "path_not_authorized",
                            "symlink artifacts are not registered",
                            status_code=400,
                        )
                    resolved = self._assert_inside(record.study_dir, path)
                    relative_to_study = _posix_relative(record.study_dir, resolved)
                    if not _is_registered_artifact(relative_to_study):
                        continue
                    artifacts.append(self._artifact_summary(record, resolved, relative_to_study))
                except ApplicationApiError as exc:
                    partial_errors.append(exc.as_response())
        artifacts.sort(key=lambda item: (item["stage_id"], item["display_name"]))
        return artifacts, partial_errors

    def _artifact_summary(
        self,
        record: StudyRecord,
        path: Path,
        relative_to_study: str,
    ) -> dict[str, Any]:
        sha256 = _sha256_file(path)
        artifact_type = _artifact_type(relative_to_study)
        artifact_state = _artifact_state(record, relative_to_study)
        artifact_id = _artifact_id(relative_to_study)
        return {
            "artifact_id": artifact_id,
            "stage_id": _artifact_stage(relative_to_study),
            "artifact_state": artifact_state,
            "artifact_type": artifact_type,
            "display_name": relative_to_study,
            "sha256": sha256,
            "provenance_id": self._provenance_id_for(relative_to_study),
            "preview_available": path.suffix.lower() in {".json", ".csv", ".txt", ".yaml", ".yml"},
            "_study_relative_path": relative_to_study,
        }

    def _stage_statuses(
        self,
        artifacts: Iterable[dict[str, Any]],
        pending_review_count: int,
    ) -> list[dict[str, Any]]:
        artifact_list = list(artifacts)
        statuses = []
        for index, stage in enumerate(PipelineStage, start=1):
            stage_artifacts = [item for item in artifact_list if item["stage_id"] == stage.value]
            canonical = [item for item in stage_artifacts if item["artifact_state"] == "canonical"]
            draft = [item for item in stage_artifacts if item["artifact_state"] == "draft"]
            status = "not_started"
            if canonical:
                status = "completed"
            elif draft or (stage == PipelineStage.SDTM_SPEC and pending_review_count):
                status = "blocked_review" if pending_review_count else "ready"
            elif index == 1:
                status = "ready"
            statuses.append(
                {
                    "stage_id": stage.value,
                    "ordinal": index,
                    "status": status,
                    "canonical_artifact_count": len(canonical),
                    "draft_artifact_count": len(draft),
                    "blocking_review_count": (
                        pending_review_count if stage == PipelineStage.SDTM_SPEC else 0
                    ),
                    "last_event_id": None,
                }
            )
        return statuses

    def _run_state(
        self,
        stages: Iterable[dict[str, Any]],
        pending_review_count: int,
        partial_errors: Iterable[dict[str, Any]],
        active_run: Mapping[str, Any] | None = None,
    ) -> str:
        if active_run is not None:
            return str(active_run["run_state"])
        if list(partial_errors):
            return "blocked_error"
        if pending_review_count:
            return "blocked_review"
        if any(stage["status"] == "completed" for stage in stages):
            return "completed"
        return "idle"

    def _pending_review_count(self, record: StudyRecord) -> int:
        queue = record.study_dir / ".review_queue"
        if not queue.exists():
            return 0
        count = 0
        for packet in queue.glob("*.json"):
            name = packet.name
            if name.startswith("."):
                continue
            if any(suffix in name for suffix in ("_decision", "_confirmation", "_rework")):
                continue
            decision = packet.with_name(packet.stem + "_decision.json")
            confirmation = packet.with_name(packet.stem + "_confirmation.json")
            if not decision.exists() and not confirmation.exists():
                count += 1
        return count

    def _manifest_lock(self, record: StudyRecord) -> dict[str, Any]:
        manifest = record.study_dir / "runtime-manifest.yaml"
        if not manifest.exists():
            return {"status": "missing", "bundle_lock": self._bundle_lock()}
        try:
            data = _read_yaml(manifest)
            version = str(data.get("schema_version", self._bundle_lock()["version"]))
            return {
                "status": "locked",
                "bundle_lock": {
                    "version": version,
                    "sha256": self._bundle_lock()["sha256"],
                },
            }
        except Exception:
            return {"status": "mismatch", "bundle_lock": self._bundle_lock()}

    def _bundle_lock(self) -> dict[str, str]:
        bundle_path = Path(__file__).resolve().parents[2] / "schemas" / "contract-bundle.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        return {"version": str(bundle["bundle_version"]), "sha256": str(bundle["bundle_sha256"])}

    def _safe_study_path(self, record: StudyRecord, relative_path: str) -> Path:
        if _unsafe_relative_path(relative_path):
            raise ApplicationApiError(
                "path_not_authorized",
                f"unsafe relative path: {relative_path}",
                status_code=400,
            )
        return self._assert_inside(record.study_dir, record.study_dir / relative_path)

    def _assert_inside(self, root: Path, path: Path) -> Path:
        root_resolved = root.resolve()
        resolved = path.resolve()
        if resolved != root_resolved and root_resolved not in resolved.parents:
            raise ApplicationApiError(
                "path_not_authorized",
                "path escapes the authorized container root",
                status_code=400,
            )
        return resolved

    def _read_optional_json(self, record: StudyRecord, relative_path: str) -> dict[str, Any] | None:
        path = record.study_dir / relative_path
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ApplicationApiError(
                "provenance_unavailable",
                f"invalid JSON artifact: {relative_path}",
                status_code=409,
            ) from exc
        if not isinstance(data, dict):
            raise ApplicationApiError(
                "provenance_unavailable",
                f"JSON artifact must be an object: {relative_path}",
                status_code=409,
            )
        return data

    def _preview_artifact(self, path: Path) -> dict[str, Any] | None:
        suffix = path.suffix.lower()
        if suffix == ".json":
            return {"kind": "json", "value": json.loads(path.read_text(encoding="utf-8"))}
        if suffix in {".yaml", ".yml"}:
            return {"kind": "yaml", "value": _read_yaml(path)}
        if suffix == ".csv":
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            return {"kind": "csv", "rows": rows[:20], "row_count": len(rows)}
        if suffix == ".txt":
            return {"kind": "text", "value": path.read_text(encoding="utf-8")[:5000]}
        return None

    def _provenance_id_for(self, relative_path: str) -> str | None:
        if relative_path.endswith(".provenance.json"):
            return _artifact_id(relative_path)
        candidate = f"{relative_path}.provenance.json"
        if relative_path.startswith("output/sdtm/datasets/"):
            candidate = relative_path.replace("/datasets/", "/datasets/") + ".provenance.json"
        return _artifact_id(candidate)

    def _audit_events(self, record: StudyRecord) -> list[dict[str, Any]]:
        events = self._application_events(record)
        audit_path = record.study_dir / str(record.project.get("paths", {}).get("audit_log", "audit_trail.jsonl"))
        if audit_path.exists():
            for line in audit_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                    events.append(self._normalize_audit_event(record, raw, audit_path))
                except json.JSONDecodeError:
                    continue
        artifacts, _ = self._list_artifact_summaries(record)
        for artifact in artifacts:
            path = self._safe_study_path(record, artifact["_study_relative_path"])
            event_type = "artifact_written"
            if artifact["artifact_type"] == "review_receipt":
                event_type = _review_event_type(path.name)
            events.append(
                {
                    "event_id": _event_id(path),
                    "event_type": event_type,
                    "occurred_at": _iso_mtime(path),
                    "study_id": record.study_id,
                    "stage_id": artifact["stage_id"],
                    "related_refs": [
                        {
                            "ref_type": "artifact",
                            "ref_id": artifact["artifact_id"],
                            "sha256": artifact["sha256"],
                        }
                    ],
                }
            )
        events.sort(key=lambda event: event["event_id"])
        return events

    def _normalize_audit_event(
        self,
        record: StudyRecord,
        raw: Mapping[str, Any],
        path: Path,
    ) -> dict[str, Any]:
        return {
            "event_id": str(raw.get("event_id") or _event_id(path)),
            "event_type": str(raw.get("event_type") or "artifact_written"),
            "occurred_at": str(raw.get("occurred_at") or _iso_mtime(path)),
            "study_id": record.study_id,
            "stage_id": raw.get("stage_id"),
            "related_refs": list(raw.get("related_refs") or []),
        }

    def _last_activity(self, record: StudyRecord) -> float:
        return self._last_activity_path(record).stat().st_mtime

    def _last_activity_path(self, record: StudyRecord) -> Path:
        paths = [
            path
            for path in record.study_dir.rglob("*")
            if path.is_file() and not path.is_symlink()
        ]
        if not paths:
            return record.study_dir / "project.yaml"
        return max(paths, key=lambda path: path.stat().st_mtime)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _new_run_id(study_id: str, idempotency_key: str, now: str) -> str:
    digest = hashlib.sha256(f"{study_id}:{idempotency_key}:{now}".encode("utf-8")).hexdigest()
    return f"run-{digest[:20]}"


def _new_event_id(
    study_id: str,
    event_type: str,
    now: str,
    related_refs: Iterable[Mapping[str, Any]],
    sequence: int,
) -> str:
    timestamp = datetime.fromisoformat(now).strftime("%Y%m%d%H%M%S")
    refs_payload = json.dumps(list(related_refs), ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha1(
        f"{study_id}:{event_type}:{now}:{refs_payload}".encode("utf-8")
    ).hexdigest()[:12]
    return f"evt-{timestamp}-{sequence:06d}-{digest}"


def _next_event_sequence(events_path: Path, now: str) -> int:
    if not events_path.exists():
        return 1
    timestamp = datetime.fromisoformat(now).strftime("%Y%m%d%H%M%S")
    prefix = f"evt-{timestamp}-"
    count = 0
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if line.startswith('{"event_id":'):
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(raw.get("event_id", "")).startswith(prefix):
                count += 1
    return count + 1


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("YAML document must be an object")
    return data


def _required_study_id(project: Mapping[str, Any]) -> str:
    study_id = str(project.get("study_id", ""))
    if not STUDY_ID_PATTERN.fullmatch(study_id):
        raise ValueError("study_id missing or invalid")
    return study_id


def _safe_review_id(review_id: str) -> str:
    if (
        not REVIEW_ID_PATTERN.fullmatch(review_id)
        or "/" in review_id
        or "\\" in review_id
        or ":" in review_id
    ):
        raise ApplicationApiError(
            "invalid_request",
            f"invalid review_id: {review_id}",
            status_code=400,
        )
    return review_id


def _review_finding_summary(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "finding_id": str(item.get("id", "")),
        "category": str(item.get("category", "")),
        "severity": str(item.get("severity", "")),
        "location": str(item.get("location", "")),
        "title": str(item.get("title", "")),
        "current_value": str(item.get("current_value", "")),
        "proposed_value": str(item.get("proposed_value", "")),
        "rationale": str(item.get("rationale", "")),
        "evidence_refs": [str(ref) for ref in item.get("evidence_refs", [])],
        "auto_approved": bool(item.get("auto_approved", False)),
    }


def _is_registered_artifact(relative_path: str) -> bool:
    if _unsafe_relative_path(relative_path):
        return False
    if relative_path.startswith("output/") and Path(relative_path).suffix.lower() in {
        ".csv",
        ".json",
        ".txt",
        ".yaml",
        ".yml",
    }:
        return True
    if relative_path.startswith(".review_queue/."):
        return False
    if relative_path.startswith(".review_queue/") and relative_path.endswith(".json"):
        return True
    return False


def _artifact_id(relative_path: str) -> str:
    normalized = relative_path.strip().replace("\\", "/").lstrip("./")
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "--", normalized)
    if not slug or not slug[0].isalnum():
        slug = "artifact-" + slug.lstrip(".-")
    return slug[:128]


def _artifact_type(relative_path: str) -> str:
    if relative_path.startswith(".review_queue/"):
        return "review_receipt"
    if relative_path.endswith(".provenance.json"):
        return "provenance"
    if "/traceability/" in relative_path:
        return "traceability_report"
    if "/programs/" in relative_path:
        return "program_manifest"
    if "/validation/" in relative_path:
        return "validation_report"
    if relative_path.endswith(".csv") and "/sdtm/" in relative_path:
        return "dataset"
    return "other"


def _artifact_state(record: StudyRecord, relative_path: str) -> str:
    if "/drafts/" in relative_path:
        return "draft"
    if relative_path.startswith(".review_queue/") and "_rework" in relative_path:
        return "invalid"
    if relative_path.startswith(".review_queue/"):
        return "canonical" if _has_confirmation(record, relative_path) else "draft"
    return "canonical"


def _has_confirmation(record: StudyRecord, relative_path: str) -> bool:
    name = Path(relative_path).name
    if "_confirmation" in name:
        return True
    if "_decision" in name:
        review_id = name.replace("_decision.json", "")
    elif name.endswith(".json"):
        review_id = name[:-5]
    else:
        return False
    return (record.study_dir / ".review_queue" / f"{review_id}_confirmation.json").exists()


def _artifact_stage(relative_path: str) -> str:
    if relative_path.startswith(".review_queue/"):
        return PipelineStage.SDTM_SPEC.value
    if relative_path.startswith("output/sdtm/"):
        return PipelineStage.SDTM_PROGRAMMING.value
    if relative_path.startswith("output/adam/"):
        return PipelineStage.ADAM_PROGRAMMING.value
    if relative_path.startswith("output/tfl/"):
        return PipelineStage.TFL_PROGRAMMING.value
    return PipelineStage.PROTOCOL_ANALYSIS.value


def _unsafe_relative_path(relative_path: str) -> bool:
    return (
        not relative_path
        or "\\" in relative_path
        or relative_path.startswith("/")
        or re.match(r"^[A-Za-z]:", relative_path) is not None
        or any(part == ".." for part in Path(relative_path).parts)
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _posix_relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _iso_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def _event_id(path: Path) -> str:
    timestamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y%m%d%H%M%S")
    digest = hashlib.sha1(path.as_posix().encode("utf-8")).hexdigest()[:12]
    return f"evt-{timestamp}-{digest}"


def _empty_cursor() -> str:
    return "evt-00000000000000-empty0"


def _review_event_type(filename: str) -> str:
    if "_confirmation" in filename:
        return "confirmation_receipt_written"
    if "_decision" in filename:
        return "decision_receipt_written"
    return "review_packet_written"


def _unique_related_refs(items: Mapping[str, str | None], ref_type: str) -> list[dict[str, Any]]:
    return [
        {"ref_type": ref_type, "ref_id": ref_id, "sha256": sha256}
        for ref_id, sha256 in sorted(items.items())
    ]


def _error(code: str, message: str) -> dict[str, Any]:
    return {"code": code, "message": message, "retryable": False}


def _without_private_fields(item: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in item.items() if not key.startswith("_")}


def _current_stage(stages: Iterable[dict[str, Any]]) -> str:
    ordered = list(stages)
    for stage in ordered:
        if stage["status"] in {"blocked_review", "blocked_error", "ready", "running"}:
            return str(stage["stage_id"])
    completed = [stage for stage in ordered if stage["status"] == "completed"]
    return str(completed[-1]["stage_id"] if completed else PipelineStage.PROTOCOL_ANALYSIS.value)
