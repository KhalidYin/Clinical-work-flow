"""Bounded P9.1 SDTM AE POC runner with an authoritative v2 step ledger."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.agents.ae_metadata_poc import (
    MAPPING_APPROVED_PATH,
    MAPPING_CANDIDATE_PATH,
    MAPPING_CONTEXT_PATH,
    MAPPING_REVIEW_ID,
    REQUIRED_RULE_IDS,
    WIKI_CONTEXT_PATH,
    prepare_metadata_mapping_review,
    write_metadata_wiki_context,
)
from src.agents.ae_metadata_workflow import (
    CANONICAL_DATASET_PATH,
    CANONICAL_TRACEABILITY_PATH,
    PROGRAM_REVIEW_ID,
    apply_program_review,
    ensure_approved_mapping,
    retry_validation_after_review,
    run_after_mapping_approval,
)
from src.application_api.poc_models import (
    LEGACY_POC_STEP_ALIASES,
    POC_STEP_DEFINITIONS,
    PocArtifactKind,
    PocArtifactRef,
    PocBlocker,
    PocBlockerKind,
    PocCheckState,
    PocDependencyRequirement,
    PocDependencyStatus,
    PocInputCheck,
    PocInputCheckState,
    PocInputCheckSummary,
    PocInputDependency,
    PocInputFile,
    PocRecoveryAction,
    PocResumeRequest,
    PocRunRequest,
    PocRunResponse,
    PocRunState,
    PocStep,
    PocStepCheck,
    PocStepKind,
    PocStepState,
    PocVariableProfile,
    normalize_poc_run_state,
)
from src.codegen.ae_programs import (
    DRAFT_DATASET_PATH,
    EXECUTION_LOG_PATH,
    PROGRAM_MANIFEST_PATH,
    PROVENANCE_PATH,
    TRACEABILITY_PATH,
    VALIDATION_PATH,
)
from src.mcp_tools.edc_importer import (
    PARSER_NAME,
    SourceParseError,
    parse_registered_edc_source,
    write_source_parse_artifacts,
)
from src.runtime.minimum_information import (
    KnowledgeAvailability,
    TargetStandardLock,
    plan_minimum_information,
)
from src.runtime.review_protocol import ReviewQueue


SOURCE_METADATA_PATH = "work/derived/edc/source-metadata.json"
SOURCE_PROFILE_PATH = "work/derived/edc/source-data-profile.json"
SOURCE_VALIDATION_PATH = "work/derived/edc/source-parser-validation.json"
INPUT_CHECK_PATH = "work/derived/edc/poc-input-check.json"
MINIMUM_INFORMATION_PATH = "work/derived/plans/minimum-information-sdtm-ae.json"
POC_SNAPSHOT_ID = "snapshot-sdtmig34-core-events-ae-v1"
POC_SNAPSHOT_PATH = "snapshots/snapshot-sdtmig34-core-events-ae-v1.json"
POC_SNAPSHOT_REFERENCE = f"locked-knowledge/{POC_SNAPSHOT_PATH}"
POC_SNAPSHOT_SHA256 = "d8aafb73ccca987d597e372435b664ba074c1a45688d5e2eef809c72f475a9ec"
KEY_PROFILE_VARIABLES = (
    "STUDYID",
    "Subject",
    "SUBJID",
    "RecordPosition",
    "AETERM",
    "AESTDAT",
    "AEENDAT",
)

MAPPING_INPUT_REFS = [SOURCE_METADATA_PATH, MINIMUM_INFORMATION_PATH, WIKI_CONTEXT_PATH]


class PocRunnerError(RuntimeError):
    """POC runner cannot accept the requested state transition."""


class PocRunner:
    """Synchronous, file-backed runner for one bounded SDTM AE POC."""

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
        latest = latest_poc_run(self.study_dir)
        if latest is not None and not request.force_restart:
            state = normalize_poc_run_state(str(latest.get("run_state", "running")))
            if state is PocRunState.RUNNING:
                return self._response(latest, accepted=False, message="POC run is already running")
            if state is PocRunState.BLOCKED:
                raise PocRunnerError(
                    "POC run is blocked; use Review or Retry current step instead of Run POC"
                )

        now = _utc_now()
        run = {
            "schema_version": "2.0",
            "run_id": _new_run_id(self.study_dir.name, now),
            "study_id": self.study_dir.name,
            "target_artifact": request.target_artifact,
            "run_state": PocRunState.RUNNING.value,
            "current_step": "input-check",
            "blocking_reason": None,
            "blocking_review_id": None,
            "blocker": None,
            "input_check": _not_run_input_check().model_dump(mode="json"),
            "steps": _new_steps(),
            "created_at": now,
            "updated_at": now,
            "resume_count": 0,
            "intent": request.intent,
        }
        self._write_run(run)
        self._append_event("run_started", "input-check", "POC runner started", run)
        self._advance(run)
        return self._response(run, accepted=True)

    def resume(self, run_id: str, request: PocResumeRequest) -> PocRunResponse:
        run = self.load_run(run_id)
        if run is None:
            raise PocRunnerError(f"POC run not found: {run_id}")
        if str(run.get("schema_version")) != "2.0":
            run = self._upgrade_legacy_run(run)
        state = normalize_poc_run_state(str(run.get("run_state", "running")))
        if state is PocRunState.DONE:
            return self._response(run, accepted=False, message="POC run is already done")
        if state is not PocRunState.BLOCKED:
            raise PocRunnerError(f"Only a blocked POC run can resume; current state is {state.value}")

        blocker = PocBlocker.model_validate(run.get("blocker"))
        if request.review_id and request.review_id != blocker.review_id:
            raise PocRunnerError("Resume review_id does not match the active blocker")
        if blocker.review_id:
            receipt = ReviewQueue(self.study_dir).check_decision(blocker.review_id)
            if receipt is None:
                raise PocRunnerError("DecisionReceipt is required before this blocked step can resume")
        elif request.reason.value != "retry_after_failure":
            raise PocRunnerError("Input/system blockers require reason=retry_after_failure")

        run["resume_count"] = int(run.get("resume_count", 0)) + 1
        run["resume_step_id"] = blocker.stage_id
        run["resume_blocker_kind"] = blocker.kind.value
        run["resume_review_id"] = blocker.review_id
        run["run_state"] = PocRunState.RUNNING.value
        run["blocking_reason"] = None
        run["blocking_review_id"] = None
        run["blocker"] = None
        self._set_step_state(run, blocker.stage_id, PocStepState.RUNNING)
        self._write_run(run)
        self._append_event("run_resumed", blocker.stage_id, "POC runner resumed", run)
        self._advance(run)
        return self._response(run, accepted=True)

    def load_run(self, run_id: str) -> dict[str, Any] | None:
        return load_poc_run(self.study_dir, run_id)

    def _advance(self, run: dict[str, Any]) -> None:
        try:
            if run.get("resume_step_id") == "validation-review":
                self._resume_validation_or_program_review(run)
                return

            if self._step_state(run, "input-check") is not PocStepState.DONE:
                if not self._ensure_input_check(run):
                    return
            if self._step_state(run, "minimum-information") is not PocStepState.DONE:
                self._ensure_minimum_information(run)
            if self._step_state(run, "wiki-context") is not PocStepState.DONE:
                self._ensure_wiki_context(run)

            if self._canonical_exists():
                self._complete_existing_canonical(run)
                return

            if self._step_state(run, "mapping-spec") is not PocStepState.DONE:
                if not self._ensure_mapping_approval(run):
                    return

            if self._has_decision(PROGRAM_REVIEW_ID):
                self._apply_program_review(run)
                return
            if self._has_packet(PROGRAM_REVIEW_ID):
                if self._step_state(run, "program-execution") is not PocStepState.DONE:
                    self._complete_step(
                        run,
                        "program-execution",
                        "程序与 Python draft 已生成，等待独立审核。",
                        input_refs=self._program_input_refs(),
                        evidence_refs=[MAPPING_APPROVED_PATH],
                        artifact_paths=self._program_artifact_paths(),
                    )
                self._block_review(
                    run,
                    "validation-review",
                    PROGRAM_REVIEW_ID,
                    "等待三语言程序和 Python draft 人工审核",
                    input_refs=self._validation_review_input_refs(),
                    evidence_refs=[
                        VALIDATION_PATH,
                        f".review_queue/{PROGRAM_REVIEW_ID}.json",
                    ],
                )
                return

            self._start_step(run, "program-execution", "生成程序并运行注册的 Python reference adapter。")
            result = run_after_mapping_approval(self.study_dir)
            deferred_summary = list(result.get("deferred_review_summary") or [])
            deferred_count = sum(int(item.get("count", 0)) for item in deferred_summary)
            self._complete_step(
                run,
                "program-execution",
                "程序生成和 Python reference execution 已产生可审核证据。",
                checks=[
                    PocStepCheck(
                        check_id="registered-reference-execution",
                        state=(
                            PocCheckState.WARNING
                            if (
                                result.get("status") == "validation_review_required"
                                or deferred_summary
                            )
                            else PocCheckState.PASS
                        ),
                        summary=(
                            f"{result.get('status')}; {deferred_count} 项数据问题延后审核"
                            if deferred_summary
                            else str(result.get("status"))
                        ),
                        evidence_refs=[str(result.get("validation_path") or VALIDATION_PATH)],
                    )
                ],
                input_refs=self._program_input_refs(),
                evidence_refs=[MAPPING_APPROVED_PATH, VALIDATION_PATH],
                artifact_paths=self._program_artifact_paths(),
            )
            if result.get("status") == "validation_review_required":
                self._block_validation(run, result)
                return
            self._block_review(
                run,
                "validation-review",
                PROGRAM_REVIEW_ID,
                "等待三语言程序和 Python draft 人工审核",
                input_refs=self._validation_review_input_refs(),
                evidence_refs=[
                    VALIDATION_PATH,
                    f".review_queue/{PROGRAM_REVIEW_ID}.json",
                ],
            )
        except Exception as exc:  # noqa: BLE001 - unexpected faults become one visible blocker
            self._block_system(run, exc)

    def _ensure_input_check(self, run: dict[str, Any]) -> bool:
        self._start_step(run, "input-check", "校验登记来源、解析器和数据元信息。")
        source_hint: dict[str, Any] = {}
        try:
            inventory = _read_yaml(self.study_dir / "source-inventory.yaml")
            source = next(
                (item for item in inventory.get("sources", []) if item.get("role") == "ae_source_data"),
                None,
            )
            if not isinstance(source, dict):
                raise SourceParseError("source-inventory.yaml lacks role=ae_source_data")
            source_hint = source
            parsed = parse_registered_edc_source(
                str(source["path"]),
                str(source["format"]),
                allowed_root=self.study_dir,
                expected_sha256=str(source["sha256"]),
                catalog_file=source.get("catalog_file"),
            )
            paths = write_source_parse_artifacts(
                parsed,
                study_root=self.study_dir,
                output_dir=self.study_dir / "work/derived/edc",
                review_queue=None,
            )
            input_check = self._successful_input_check(parsed, paths)
            self._persist_input_check(run, input_check)
            self._complete_step(
                run,
                "input-check",
                input_check.summary.message,
                checks=input_check.checks,
                input_refs=[
                    "source-inventory.yaml",
                    str(parsed.source_metadata["source"]["relative_path"]),
                ],
                evidence_refs=[
                    SOURCE_VALIDATION_PATH,
                    SOURCE_METADATA_PATH,
                    SOURCE_PROFILE_PATH,
                ],
                artifact_paths=[
                    INPUT_CHECK_PATH,
                    SOURCE_METADATA_PATH,
                    SOURCE_PROFILE_PATH,
                    SOURCE_VALIDATION_PATH,
                ],
            )
            return True
        except Exception as exc:  # noqa: BLE001 - classify input boundary failures below
            blocker, input_check = self._input_failure(exc, source_hint)
            self._persist_input_check(run, input_check)
            self._block(run, blocker, checks=input_check.checks)
            return False

    def _successful_input_check(
        self,
        parsed: Any,
        paths: Mapping[str, str],
    ) -> PocInputCheck:
        metadata = parsed.source_metadata
        profile = parsed.data_profile
        availability = metadata.get("metadata_availability", {})
        gaps = list(parsed.validation_report.get("gaps") or [])
        variable_metadata = {item["name"]: item for item in metadata.get("variables", [])}
        variable_profiles = {item["name"]: item for item in profile.get("variables", [])}
        selected_profiles: list[PocVariableProfile] = []
        for variable in KEY_PROFILE_VARIABLES:
            if variable not in variable_metadata:
                continue
            item = variable_metadata[variable]
            data_item = variable_profiles.get(variable, {})
            missing_count = int(data_item.get("missing_count", 0))
            series = parsed.data[variable]
            selected_profiles.append(
                PocVariableProfile(
                    variable=variable,
                    label=_available_value(item.get("column_label")),
                    data_type=str(item.get("logical_type") or "unknown"),
                    format=_available_value(item.get("source_format")),
                    missing_count=missing_count,
                    non_missing_count=int(len(parsed.data) - missing_count),
                    distinct_count=int(series.nunique(dropna=True)),
                    value_labels_available=_is_available(item.get("value_labels")),
                    evidence_refs=[f"{SOURCE_PROFILE_PATH}#variables/{variable}"],
                )
            )

        warnings = [
            f"{gap.get('metadata')}: {gap.get('reason')}"
            for gap in gaps
        ]
        status = PocInputCheckState.WARNING if warnings else PocInputCheckState.READY
        source = metadata["source"]
        dataset = metadata["dataset"]
        checks = [
            PocStepCheck(
                check_id="source-exists",
                state=PocCheckState.PASS,
                summary="登记的 AE source file 存在。",
                evidence_refs=[str(source["relative_path"])],
            ),
            PocStepCheck(
                check_id="source-sha256",
                state=PocCheckState.PASS,
                summary="Source SHA-256 与 source-inventory.yaml 一致。",
                observed=str(source["sha256"]),
                evidence_refs=["source-inventory.yaml", SOURCE_METADATA_PATH],
            ),
            PocStepCheck(
                check_id="source-parser",
                state=PocCheckState.PASS,
                summary=f"{PARSER_NAME} 已成功解析 {source['format']}。",
                evidence_refs=[SOURCE_VALIDATION_PATH],
            ),
            PocStepCheck(
                check_id="metadata-availability",
                state=PocCheckState.WARNING if warnings else PocCheckState.PASS,
                summary=("存在显式 metadata gap。" if warnings else "来源 metadata 可用性检查通过。"),
                detail="；".join(warnings) if warnings else None,
                evidence_refs=[f"{SOURCE_METADATA_PATH}#metadata_availability"],
            ),
        ]
        return PocInputCheck(
            checked_at=_utc_now(),
            summary=PocInputCheckSummary(
                status=status,
                required_total=1,
                required_ready=1,
                blocking_count=0,
                warning_count=len(warnings),
                message=(
                    f"AE source 已解析：{dataset['row_count']} 行、{dataset['column_count']} 列；"
                    f"{len(warnings)} 个 metadata gap。"
                ),
            ),
            files=[
                PocInputFile(
                    source_id="ae-source-data",
                    label="AE registered source",
                    relative_path=str(source["relative_path"]),
                    format=str(source["format"]),
                    exists=True,
                    sha256=str(source["sha256"]),
                    size_bytes=int(source["size_bytes"]),
                    parser=PARSER_NAME,
                    parser_available=True,
                    row_count=int(dataset["row_count"]),
                    column_count=int(dataset["column_count"]),
                    labels_available=_is_available(availability.get("column_labels")),
                    formats_available=_is_available(availability.get("formats")),
                    value_labels_available=_is_available(availability.get("value_labels")),
                    warnings=warnings,
                    evidence_refs=[paths["source_metadata"], paths["data_profile"], paths["validation"]],
                )
            ],
            dependencies=_target_dependencies(PocDependencyStatus.AVAILABLE),
            checks=checks,
            variable_profiles=selected_profiles,
            warnings=warnings,
        )

    def _input_failure(
        self,
        exc: Exception,
        source_hint: Mapping[str, Any],
    ) -> tuple[PocBlocker, PocInputCheck]:
        message = str(exc) or exc.__class__.__name__
        lower = message.lower()
        code = "source_parse_failed"
        recovery = PocRecoveryAction.REPAIR_INPUT
        if isinstance(exc, FileNotFoundError) or (
            isinstance(exc, OSError) and ("not found" in lower or "cannot find" in lower)
        ):
            code = "source_file_missing"
            recovery = PocRecoveryAction.PROVIDE_INPUT
        elif "lacks role=ae_source_data" in lower:
            code = "source_inventory_missing"
            recovery = PocRecoveryAction.PROVIDE_INPUT
        elif "sha-256 mismatch" in lower:
            code = "source_hash_mismatch"
        elif "required for registered" in lower or isinstance(exc, ModuleNotFoundError):
            code = "parser_dependency_missing"
            recovery = PocRecoveryAction.INSTALL_DEPENDENCY
        elif "unsupported registered source format" in lower:
            code = "unsupported_source_format"
        elif "does not match the file extension" in lower:
            code = "source_format_extension_mismatch"
        elif "outside the registered study root" in lower:
            code = "source_path_not_authorized"
        elif isinstance(exc, (KeyError, TypeError)):
            code = "source_inventory_invalid"

        relative_path = str(source_hint.get("path") or "source-inventory.yaml")
        source_format = str(source_hint.get("format") or "unknown")
        check = PocStepCheck(
            check_id=code,
            state=PocCheckState.FAIL,
            summary=message,
            evidence_refs=["source-inventory.yaml", relative_path],
        )
        input_check = PocInputCheck(
            checked_at=_utc_now(),
            summary=PocInputCheckSummary(
                status=PocInputCheckState.BLOCKED,
                required_total=1,
                required_ready=0,
                blocking_count=1,
                warning_count=0,
                message=f"Input Check blocked: {message}",
            ),
            files=[
                PocInputFile(
                    source_id="ae-source-data",
                    label="AE registered source",
                    relative_path=relative_path,
                    format=source_format,
                    exists=code != "source_file_missing",
                    sha256=str(source_hint.get("sha256")) if source_hint.get("sha256") else None,
                    parser=PARSER_NAME,
                    parser_available=False if code == "parser_dependency_missing" else None,
                    warnings=[message],
                    evidence_refs=["source-inventory.yaml"],
                )
            ],
            dependencies=_target_dependencies(
                PocDependencyStatus.MISSING
                if recovery is PocRecoveryAction.PROVIDE_INPUT
                else PocDependencyStatus.INVALID
            ),
            checks=[check],
            warnings=[],
        )
        blocker = PocBlocker(
            kind=PocBlockerKind.INPUT,
            stage_id="input-check",
            code=code,
            summary="AE source Input Check 未通过",
            detail=message,
            affected_artifacts=[relative_path],
            evidence_refs=[INPUT_CHECK_PATH, "source-inventory.yaml"],
            recovery_action=recovery,
            retryable=True,
        )
        return blocker, input_check

    def _ensure_minimum_information(self, run: dict[str, Any]) -> None:
        self._start_step(run, "minimum-information", "按 sdtm_ae_dataset 目标计算最小信息依赖。")
        inventory = _read_yaml(self.study_dir / "source-inventory.yaml")
        metadata = _read_json(self.study_dir / SOURCE_METADATA_PATH)
        project = _read_yaml(self.study_dir / "project.yaml")
        available_paths = {
            str(item["path"])
            for item in inventory.get("sources", [])
            if item.get("path") and (self.study_dir / str(item["path"])).exists()
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
                reference=POC_SNAPSHOT_REFERENCE,
            ),
            available_source_paths=available_paths,
        )
        _write_json_atomic(
            self.study_dir / MINIMUM_INFORMATION_PATH,
            plan.model_dump(mode="json"),
        )
        self._complete_step(
            run,
            "minimum-information",
            "raw-only SDTM AE 目标依赖已解析；Protocol/SAP/CRF 本目标不要求。",
            checks=[
                PocStepCheck(
                    check_id="raw-only-target-dependencies",
                    state=PocCheckState.PASS,
                    summary="AE raw data 为 required；Protocol/SAP/CRF 为 not_required。",
                    evidence_refs=[MINIMUM_INFORMATION_PATH, INPUT_CHECK_PATH],
                )
            ],
            input_refs=[INPUT_CHECK_PATH, SOURCE_METADATA_PATH, "project.yaml"],
            evidence_refs=[INPUT_CHECK_PATH, SOURCE_METADATA_PATH],
            artifact_paths=[MINIMUM_INFORMATION_PATH],
        )

    def _ensure_wiki_context(self, run: dict[str, Any]) -> None:
        self._start_step(run, "wiki-context", "锁定并投影本次 Mapping 实际采用的 Wiki 规则。")
        snapshot_path = self.wiki_dir / POC_SNAPSHOT_PATH
        if not snapshot_path.exists():
            raise PocRunnerError(f"POC test-only Wiki snapshot is missing: {POC_SNAPSHOT_PATH}")
        context = write_metadata_wiki_context(self.study_dir, self.wiki_dir)
        rules = list(context.get("rules") or [])
        locator_refs = [
            f"{rule['source_id']}:{locator['locator_id']}"
            for rule in rules
            for locator in rule.get("locators", [])
        ]
        self._complete_step(
            run,
            "wiki-context",
            f"已锁定 {len(rules)} 条 SDTMIG 3.4 规则；仅限 P9 POC 测试，不具备生产资格。",
            checks=[
                PocStepCheck(
                    check_id="poc-test-wiki-snapshot",
                    state=PocCheckState.PASS,
                    summary=f"p9-poc-test-only snapshot 可用并关闭 {len(rules)} 条规则引用。",
                    detail="；".join(str(rule["rule_id"]) for rule in rules),
                    observed=len(rules),
                    expected=len(REQUIRED_RULE_IDS),
                    evidence_refs=[
                        POC_SNAPSHOT_REFERENCE,
                        *locator_refs,
                    ],
                )
            ],
            input_refs=[MINIMUM_INFORMATION_PATH, POC_SNAPSHOT_REFERENCE],
            evidence_refs=[WIKI_CONTEXT_PATH, *locator_refs],
            artifact_paths=[WIKI_CONTEXT_PATH],
        )

    def _ensure_mapping_approval(self, run: dict[str, Any]) -> bool:
        self._start_step(run, "mapping-spec", "生成或应用 AE MappingSpec Review。")
        if (self.study_dir / MAPPING_APPROVED_PATH).exists():
            ensure_approved_mapping(self.study_dir)
            self._complete_step(
                run,
                "mapping-spec",
                "复用已验证的 approved MappingSpec。",
                input_refs=MAPPING_INPUT_REFS,
                evidence_refs=[
                    MAPPING_CONTEXT_PATH,
                    f".review_queue/{MAPPING_REVIEW_ID}_decision.json",
                ],
                artifact_paths=[MAPPING_CONTEXT_PATH, MAPPING_APPROVED_PATH],
            )
            return True
        if not self._has_decision(MAPPING_REVIEW_ID):
            if not self._has_packet(MAPPING_REVIEW_ID):
                prepare_metadata_mapping_review(self.study_dir, self.wiki_dir)
                self._append_event(
                    "mapping_review_written",
                    "mapping-spec",
                    "写入 AE MappingSpec ReviewPacket",
                    run,
                )
            self._block_review(
                run,
                "mapping-spec",
                MAPPING_REVIEW_ID,
                "等待 AE MappingSpec 人工审核",
                input_refs=MAPPING_INPUT_REFS,
                evidence_refs=[
                    MAPPING_CONTEXT_PATH,
                    MAPPING_CANDIDATE_PATH,
                    f".review_queue/{MAPPING_REVIEW_ID}.json",
                ],
                artifact_paths=[MAPPING_CONTEXT_PATH, MAPPING_CANDIDATE_PATH],
            )
            return False
        ensure_approved_mapping(self.study_dir)
        self._complete_step(
            run,
            "mapping-spec",
            "DecisionReceipt 已应用并生成 approved MappingSpec。",
            input_refs=MAPPING_INPUT_REFS,
            evidence_refs=[
                MAPPING_CONTEXT_PATH,
                f".review_queue/{MAPPING_REVIEW_ID}_decision.json",
            ],
            artifact_paths=[MAPPING_CONTEXT_PATH, MAPPING_APPROVED_PATH],
        )
        return True

    def _resume_validation_or_program_review(self, run: dict[str, Any]) -> None:
        review_id = str(run.pop("resume_review_id", "") or "")
        blocker_kind = str(run.pop("resume_blocker_kind", "") or "")
        run.pop("resume_step_id", None)
        self._write_run(run)
        if review_id == PROGRAM_REVIEW_ID:
            self._apply_program_review(run)
            return
        if blocker_kind != PocBlockerKind.VALIDATION.value:
            raise PocRunnerError("Unsupported validation-review resume route")
        result = retry_validation_after_review(self.study_dir)
        if result.get("status") == "validation_review_required":
            self._block_validation(run, result)
            return
        self._block_review(
            run,
            "validation-review",
            PROGRAM_REVIEW_ID,
            "验证已通过，等待三语言程序和 Python draft 人工审核",
            input_refs=self._validation_review_input_refs(),
            evidence_refs=[
                VALIDATION_PATH,
                f".review_queue/{PROGRAM_REVIEW_ID}.json",
            ],
        )

    def _apply_program_review(self, run: dict[str, Any]) -> None:
        self._start_step(run, "validation-review", "应用 Program Review DecisionReceipt。")
        result = apply_program_review(self.study_dir)
        if result["status"] == "rework_required":
            self._block(
                run,
                PocBlocker(
                    kind=PocBlockerKind.SYSTEM,
                    stage_id="validation-review",
                    code="program_review_rework_required",
                    summary="Program review 要求 rework",
                    detail="Review 含 rejected/modified finding；修订受控产物后再启动新的审核证据链。",
                    evidence_refs=[f".review_queue/{PROGRAM_REVIEW_ID}_decision.json"],
                    recovery_action=PocRecoveryAction.RETRY_CURRENT_STEP,
                    retryable=True,
                ),
            )
            return
        self._complete_step(
            run,
            "validation-review",
            "Program Review DecisionReceipt 已应用。",
            checks=self._completed_program_review_checks(),
            input_refs=self._validation_review_input_refs(),
            evidence_refs=[
                VALIDATION_PATH,
                f".review_queue/{PROGRAM_REVIEW_ID}.json",
                f".review_queue/{PROGRAM_REVIEW_ID}_decision.json",
            ],
            artifact_paths=[f".review_queue/{PROGRAM_REVIEW_ID}_confirmation.json"],
        )
        self._complete_run(run, result)

    def _program_input_refs(self) -> list[str]:
        refs = [MAPPING_APPROVED_PATH]
        spec_path = self.study_dir / MAPPING_APPROVED_PATH
        if spec_path.exists():
            source = _read_json(spec_path).get("source", {})
            source_path = source.get("relative_path") if isinstance(source, Mapping) else None
            if source_path:
                refs.append(str(source_path))
        return refs

    def _program_artifact_paths(self) -> list[str]:
        paths = [
            PROGRAM_MANIFEST_PATH,
            DRAFT_DATASET_PATH,
            VALIDATION_PATH,
            EXECUTION_LOG_PATH,
            PROVENANCE_PATH,
            TRACEABILITY_PATH,
        ]
        manifest_path = self.study_dir / PROGRAM_MANIFEST_PATH
        if manifest_path.exists():
            manifest = _read_json(manifest_path)
            paths.extend(
                str(program["path"])
                for program in manifest.get("programs", [])
                if isinstance(program, Mapping) and program.get("path")
            )
        return list(dict.fromkeys(paths))

    def _validation_review_input_refs(self) -> list[str]:
        return [
            MAPPING_APPROVED_PATH,
            PROGRAM_MANIFEST_PATH,
            DRAFT_DATASET_PATH,
            VALIDATION_PATH,
            PROVENANCE_PATH,
            TRACEABILITY_PATH,
        ]

    def _completed_program_review_checks(self) -> list[PocStepCheck]:
        validation_path = self.study_dir / VALIDATION_PATH
        if not validation_path.exists():
            return [
                PocStepCheck(
                    check_id="program-review-applied",
                    state=PocCheckState.PASS,
                    summary="Program Review 已应用；无独立 validation artifact。",
                    evidence_refs=[f".review_queue/{PROGRAM_REVIEW_ID}_decision.json"],
                )
            ]
        validation = _read_json(validation_path)
        if validation.get("blocking_summary"):
            raise PocRunnerError(
                "Program Review cannot complete while strong-blocking validation remains"
            )
        deferred = list(validation.get("deferred_review_summary") or [])
        if not deferred:
            return [
                PocStepCheck(
                    check_id="program-review-applied",
                    state=PocCheckState.PASS,
                    summary="Validation 无未处置 finding；Program Review 已应用。",
                    evidence_refs=[
                        VALIDATION_PATH,
                        f".review_queue/{PROGRAM_REVIEW_ID}_decision.json",
                    ],
                )
            ]
        return [
            PocStepCheck(
                check_id=f"{item.get('check_code', 'validation')}-deferred-reviewed",
                state=PocCheckState.WARNING,
                summary=(
                    f"{item.get('variable', 'dataset')}: "
                    f"{int(item.get('count', 0))}/{int(item.get('row_count', 0))} "
                    "项数据问题已后审接受，原记录保持不变。"
                ),
                detail="处置结果为 deferred_review；不表示数据质量检查通过。",
                observed=int(item.get("count", 0)),
                expected=0,
                affected_variables=(
                    [str(item["variable"])] if item.get("variable") else []
                ),
                evidence_refs=[
                    VALIDATION_PATH,
                    f".review_queue/{PROGRAM_REVIEW_ID}_decision.json",
                    *list(item.get("finding_ids") or [])[:20],
                ],
            )
            for item in deferred
        ]

    def _block_validation(self, run: dict[str, Any], result: Mapping[str, Any]) -> None:
        summaries = list(result.get("blocking_summary") or [])
        affected = sorted(
            {str(item.get("variable")) for item in summaries if item.get("variable")}
        )
        total = sum(int(item.get("count", 0)) for item in summaries)
        row_count = max([int(item.get("row_count", 0)) for item in summaries] or [0])
        review_id = str(result["review_id"])
        checks = [
            PocStepCheck(
                check_id=str(item.get("check_code") or "validation"),
                state=PocCheckState.FAIL,
                summary=(
                    f"{item.get('variable', 'dataset')}: "
                    f"{int(item.get('count', 0))}/{int(item.get('row_count', 0))} 条记录"
                ),
                observed=int(item.get("count", 0)),
                expected=0,
                affected_variables=[str(item.get("variable"))] if item.get("variable") else [],
                evidence_refs=[VALIDATION_PATH, *list(item.get("finding_ids") or [])[:20]],
            )
            for item in summaries
        ]
        self._block(
            run,
            PocBlocker(
                kind=PocBlockerKind.VALIDATION,
                stage_id="validation-review",
                code="ae_reference_validation_failed",
                summary=f"AE reference validation blocked: {total}/{row_count} 项记录问题",
                detail=(
                    "不得自动过滤或补值。请审核验证 finding，修复源数据或建立新的受控 MappingSpec "
                    "后再 Retry current step。"
                ),
                affected_variables=affected,
                affected_artifacts=[DRAFT_DATASET_PATH, CANONICAL_DATASET_PATH],
                evidence_refs=[VALIDATION_PATH, EXECUTION_LOG_PATH, str(result["review_packet_path"])],
                recovery_action=PocRecoveryAction.SUBMIT_REVIEW_DECISION,
                review_id=review_id,
                retryable=True,
            ),
            checks=checks,
            input_refs=self._validation_review_input_refs(),
            evidence_refs=[
                VALIDATION_PATH,
                EXECUTION_LOG_PATH,
                str(result["review_packet_path"]),
            ],
            artifact_paths=[VALIDATION_PATH, str(result["review_packet_path"])],
        )

    def _block_review(
        self,
        run: dict[str, Any],
        step_id: str,
        review_id: str,
        reason: str,
        *,
        input_refs: list[str] | None = None,
        evidence_refs: list[str] | None = None,
        artifact_paths: list[str] | None = None,
    ) -> None:
        self._block(
            run,
            PocBlocker(
                kind=PocBlockerKind.REVIEW,
                stage_id=step_id,
                code="review_decision_required",
                summary=reason,
                detail="提交 DecisionReceipt 后使用 Resume；ReviewPacket 本身不代表步骤完成。",
                evidence_refs=[f".review_queue/{review_id}.json"],
                recovery_action=PocRecoveryAction.SUBMIT_REVIEW_DECISION,
                review_id=review_id,
            ),
            input_refs=input_refs,
            evidence_refs=evidence_refs,
            artifact_paths=artifact_paths,
        )

    def _block_system(self, run: dict[str, Any], exc: Exception) -> None:
        step_id = str(run.get("current_step") or "input-check")
        self._block(
            run,
            PocBlocker(
                kind=PocBlockerKind.SYSTEM,
                stage_id=step_id,
                code=f"unexpected_{exc.__class__.__name__.lower()}",
                summary=str(exc) or exc.__class__.__name__,
                detail="这是未预期运行错误；修复根因后只重试当前阶段。",
                recovery_action=PocRecoveryAction.RETRY_CURRENT_STEP,
                retryable=True,
            ),
        )

    def _block(
        self,
        run: dict[str, Any],
        blocker: PocBlocker,
        *,
        checks: list[PocStepCheck] | None = None,
        input_refs: list[str] | None = None,
        evidence_refs: list[str] | None = None,
        artifact_paths: list[str] | None = None,
    ) -> None:
        refs = [_artifact_ref(self.study_dir, path) for path in artifact_paths or []]
        self._set_step_state(
            run,
            blocker.stage_id,
            PocStepState.BLOCKED,
            kind=(
                PocStepKind.REVIEW
                if blocker.kind in {PocBlockerKind.REVIEW, PocBlockerKind.VALIDATION}
                else PocStepKind.ERROR
            ),
            summary=blocker.summary,
            checks=checks,
            input_refs=input_refs,
            evidence_refs=evidence_refs or blocker.evidence_refs,
            artifact_refs=[item for item in refs if item is not None],
            blocking_reason=blocker.summary,
            review_id=blocker.review_id,
        )
        run["run_state"] = PocRunState.BLOCKED.value
        run["current_step"] = blocker.stage_id
        run["blocking_reason"] = blocker.summary
        run["blocking_review_id"] = blocker.review_id
        run["blocker"] = blocker.model_dump(mode="json")
        self._write_run(run)
        self._append_event(
            "run_blocked",
            blocker.stage_id,
            blocker.summary,
            run,
            severity="warning" if blocker.kind in {PocBlockerKind.REVIEW, PocBlockerKind.VALIDATION} else "error",
        )

    def _start_step(self, run: dict[str, Any], step_id: str, summary: str) -> None:
        if self._step_state(run, step_id) is PocStepState.DONE:
            return
        self._set_step_state(
            run,
            step_id,
            PocStepState.RUNNING,
            kind=PocStepKind.INSTRUCTION,
            summary=summary,
            started_at=_utc_now(),
            blocking_reason=None,
            review_id=None,
        )
        run["current_step"] = step_id
        run["run_state"] = PocRunState.RUNNING.value
        run["blocker"] = None
        run["blocking_reason"] = None
        run["blocking_review_id"] = None
        self._write_run(run)
        self._append_event("step_started", step_id, summary, run)

    def _complete_step(
        self,
        run: dict[str, Any],
        step_id: str,
        summary: str,
        *,
        checks: list[PocStepCheck] | None = None,
        input_refs: list[str] | None = None,
        evidence_refs: list[str] | None = None,
        artifact_paths: list[str] | None = None,
    ) -> None:
        refs = [_artifact_ref(self.study_dir, path) for path in artifact_paths or []]
        self._set_step_state(
            run,
            step_id,
            PocStepState.DONE,
            kind=PocStepKind.ARTIFACT if refs else PocStepKind.INSTRUCTION,
            summary=summary,
            completed_at=_utc_now(),
            checks=checks,
            input_refs=input_refs,
            evidence_refs=evidence_refs,
            artifact_refs=[item for item in refs if item is not None],
            blocking_reason=None,
            review_id=None,
        )
        run["current_step"] = step_id
        self._write_run(run)
        self._append_event("step_completed", step_id, summary, run)

    def _complete_existing_canonical(self, run: dict[str, Any]) -> None:
        for step_id, _ in POC_STEP_DEFINITIONS:
            if step_id in {"input-check", "minimum-information", "wiki-context", "canonical-ae"}:
                continue
            if self._step_state(run, step_id) is PocStepState.PENDING:
                self._set_step_state(
                    run,
                    step_id,
                    PocStepState.SKIPPED,
                    summary="本次 run 检测到既有 canonical AE，未重放该阶段。",
                    completed_at=_utc_now(),
                )
        self._complete_run(
            run,
            {"canonical_dataset_path": CANONICAL_DATASET_PATH, "status": "canonical_reused"},
        )

    def _complete_run(self, run: dict[str, Any], result: Mapping[str, Any]) -> None:
        canonical_artifacts = [CANONICAL_DATASET_PATH]
        trace_path = str(
            result.get("canonical_traceability_path") or CANONICAL_TRACEABILITY_PATH
        )
        if (self.study_dir / trace_path).exists():
            canonical_artifacts.append(trace_path)
        self._set_step_state(
            run,
            "canonical-ae",
            PocStepState.DONE,
            kind=PocStepKind.COMPLETE,
            summary="Canonical AE 已写入并保持受控 POC 范围声明。",
            completed_at=_utc_now(),
            input_refs=[
                DRAFT_DATASET_PATH,
                f".review_queue/{PROGRAM_REVIEW_ID}_confirmation.json",
            ],
            evidence_refs=[
                PROVENANCE_PATH,
                TRACEABILITY_PATH,
                f".review_queue/{PROGRAM_REVIEW_ID}_decision.json",
            ],
            artifact_refs=[
                item
                for item in [
                    _artifact_ref(self.study_dir, path) for path in canonical_artifacts
                ]
                if item is not None
            ],
        )
        run["run_state"] = PocRunState.DONE.value
        run["current_step"] = "canonical-ae"
        run["blocker"] = None
        run["blocking_reason"] = None
        run["blocking_review_id"] = None
        run["result"] = dict(result)
        self._write_run(run)
        self._append_event("run_done", "canonical-ae", "Canonical AE written", run)

    def _persist_input_check(self, run: dict[str, Any], value: PocInputCheck) -> None:
        payload = value.model_dump(mode="json")
        _write_json_atomic(self.study_dir / INPUT_CHECK_PATH, payload)
        run["input_check"] = payload
        self._write_run(run)

    def _set_step_state(
        self,
        run: dict[str, Any],
        step_id: str,
        state: PocStepState,
        **updates: Any,
    ) -> None:
        steps = [PocStep.model_validate(item) for item in run.get("steps", [])]
        target = next((item for item in steps if item.step_id == step_id), None)
        if target is None:
            raise PocRunnerError(f"Unknown POC step: {step_id}")
        if state is PocStepState.RUNNING:
            for item in steps:
                if item.step_id != step_id and item.state is PocStepState.RUNNING:
                    item.state = PocStepState.PENDING
                    item.started_at = None
        values = target.model_dump()
        values.update({key: value for key, value in updates.items() if value is not None})
        if "blocking_reason" in updates and updates["blocking_reason"] is None:
            values["blocking_reason"] = None
        if "review_id" in updates and updates["review_id"] is None:
            values["review_id"] = None
        values["state"] = state
        replacement = PocStep.model_validate(values)
        run["steps"] = [
            (replacement if item.step_id == step_id else item).model_dump(mode="json")
            for item in steps
        ]
        run["updated_at"] = _utc_now()

    def _step_state(self, run: Mapping[str, Any], step_id: str) -> PocStepState:
        for item in run.get("steps", []):
            if item.get("step_id") == step_id:
                return PocStepState(str(item["state"]))
        raise PocRunnerError(f"Unknown POC step: {step_id}")

    def _write_run(self, run: Mapping[str, Any]) -> None:
        path = self.runs_dir / f"{run['run_id']}.json"
        _write_json_atomic(path, dict(run))

    def _append_event(
        self,
        event_type: str,
        step_id: str,
        summary: str,
        run: Mapping[str, Any],
        *,
        severity: str = "ok",
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
            "severity": severity,
            "related_refs": [{"ref_type": "run", "ref_id": str(run["run_id"]), "sha256": None}],
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    def _response(
        self,
        run: Mapping[str, Any],
        *,
        accepted: bool,
        message: str | None = None,
    ) -> PocRunResponse:
        return PocRunResponse(
            accepted=accepted,
            run_id=str(run["run_id"]),
            run_state=normalize_poc_run_state(str(run["run_state"])),
            state_endpoint=f"/api/v1/studies/{self.study_dir.name}/poc-state",
            message=message or str(run.get("blocking_reason") or run.get("run_state") or "accepted"),
        )

    def _upgrade_legacy_run(self, run: Mapping[str, Any]) -> dict[str, Any]:
        upgraded = dict(run)
        raw_state = str(upgraded.get("run_state", "blocked_error"))
        state = normalize_poc_run_state(raw_state)
        review_id = str(upgraded.get("blocking_review_id") or "") or None
        current = _legacy_step_id(str(upgraded.get("current_step") or "input-check"), review_id)
        steps = [PocStep.model_validate(item) for item in _new_steps()]
        if state is PocRunState.BLOCKED:
            target = next(item for item in steps if item.step_id == current)
            target.state = PocStepState.BLOCKED
            target.summary = str(upgraded.get("blocking_reason") or "Legacy run is blocked")
            target.blocking_reason = target.summary
            target.review_id = review_id
            kind = PocBlockerKind.REVIEW if raw_state == "blocked_review" else PocBlockerKind.SYSTEM
            blocker = PocBlocker(
                kind=kind,
                stage_id=current,
                code="legacy_pending_review" if kind is PocBlockerKind.REVIEW else "legacy_runner_error",
                summary=target.summary,
                detail="Legacy run 已升级为 v2 ledger；只恢复当前可见阻断阶段。",
                evidence_refs=[f".review_queue/{review_id}.json"] if review_id else [],
                recovery_action=(
                    PocRecoveryAction.SUBMIT_REVIEW_DECISION
                    if review_id
                    else PocRecoveryAction.RETRY_CURRENT_STEP
                ),
                review_id=review_id,
                retryable=not bool(review_id),
            )
            upgraded["blocker"] = blocker.model_dump(mode="json")
        elif state is PocRunState.RUNNING:
            next(item for item in steps if item.step_id == current).state = PocStepState.RUNNING
            upgraded["blocker"] = None
        else:
            for item in steps:
                item.state = (
                    PocStepState.DONE if item.step_id == "canonical-ae" else PocStepState.SKIPPED
                )
            upgraded["blocker"] = None
        upgraded.update(
            {
                "schema_version": "2.0",
                "run_state": state.value,
                "current_step": current,
                "steps": [item.model_dump(mode="json") for item in steps],
                "input_check": _not_run_input_check().model_dump(mode="json"),
                "updated_at": _utc_now(),
            }
        )
        self._write_run(upgraded)
        self._append_event("legacy_run_upgraded", current, "Legacy POC run upgraded to v2 ledger", upgraded)
        return upgraded

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


def _new_steps() -> list[dict[str, Any]]:
    return [
        PocStep(
            step_id=step_id,
            ordinal=ordinal,
            title=title,
            state=PocStepState.PENDING,
            summary="等待 Runner 执行。",
        ).model_dump(mode="json")
        for ordinal, (step_id, title) in enumerate(POC_STEP_DEFINITIONS, start=1)
    ]


def _not_run_input_check() -> PocInputCheck:
    return PocInputCheck(
        summary=PocInputCheckSummary(
            status=PocInputCheckState.NOT_RUN,
            required_total=1,
            required_ready=0,
            blocking_count=0,
            warning_count=0,
            message="Input Check 尚未执行。",
        ),
        dependencies=_target_dependencies(PocDependencyStatus.MISSING, source_blocking=False),
    )


def _target_dependencies(
    source_status: PocDependencyStatus,
    *,
    source_blocking: bool | None = None,
) -> list[PocInputDependency]:
    if source_blocking is None:
        source_blocking = source_status is not PocDependencyStatus.AVAILABLE
    return [
        PocInputDependency(
            input_id="ae-source-data",
            label="AE raw data",
            requirement=PocDependencyRequirement.REQUIRED,
            status=source_status,
            blocking=source_blocking,
            detail="当前 sdtm_ae_dataset 的唯一 required 输入。",
            evidence_refs=["source-inventory.yaml"],
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
            for input_id, label in (("protocol", "Protocol"), ("sap", "SAP"), ("crf", "CRF"))
        ],
    ]


def _artifact_ref(study_dir: Path, relative_path: str) -> PocArtifactRef | None:
    path = study_dir / relative_path
    if not path.exists() or not path.is_file():
        return None
    suffix = path.suffix.lower()
    kind = {
        ".json": PocArtifactKind.JSON,
        ".csv": PocArtifactKind.CSV,
        ".txt": PocArtifactKind.TEXT,
        ".py": PocArtifactKind.TEXT,
        ".r": PocArtifactKind.TEXT,
        ".sas": PocArtifactKind.TEXT,
        ".log": PocArtifactKind.TEXT,
        ".yaml": PocArtifactKind.YAML,
        ".yml": PocArtifactKind.YAML,
    }.get(suffix, PocArtifactKind.UNKNOWN)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    artifact_id = f"poc-{hashlib.sha256(relative_path.encode('utf-8')).hexdigest()[:16]}"
    return PocArtifactRef(
        artifact_id=artifact_id,
        label=path.name,
        relative_path=relative_path,
        kind=kind,
        sha256=digest,
        preview_available=kind in {
            PocArtifactKind.JSON,
            PocArtifactKind.CSV,
            PocArtifactKind.TEXT,
            PocArtifactKind.YAML,
        },
    )


def _available_value(value: Any) -> str | None:
    if not isinstance(value, Mapping) or value.get("status") != "available":
        return None
    raw = value.get("value")
    return str(raw) if raw is not None else None


def _is_available(value: Any) -> bool:
    return isinstance(value, Mapping) and value.get("status") == "available"


def _legacy_step_id(step_id: str, review_id: str | None) -> str:
    if step_id == "review-gate" and review_id and "program" in review_id.lower():
        return "validation-review"
    return LEGACY_POC_STEP_ALIASES.get(step_id, "input-check")


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


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


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
