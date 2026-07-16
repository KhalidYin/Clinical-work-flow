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

from src.runtime.pipeline_contract import PipelineStage


STUDY_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")
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
    """Read-only local-first facade over Study files."""

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
        incomplete_reasons = []
        if partial_errors:
            incomplete_reasons.append("artifact scan returned partial errors")
        if self._manifest_lock(record)["status"] != "locked":
            incomplete_reasons.append("runtime manifest or knowledge lock unavailable")
        return {
            "study_id": record.study_id,
            "stage_order": [stage.value for stage in PipelineStage],
            "stages": stages,
            "run_state": self._run_state(stages, pending_review_count, partial_errors),
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
        return {
            "study_id": record.study_id,
            "title": record.project.get("protocol_id"),
            "therapeutic_area": record.project.get("therapeutic_area"),
            "current_stage": _current_stage(stages),
            "run_state": self._run_state(stages, pending, []),
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
    ) -> str:
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
        events = []
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
