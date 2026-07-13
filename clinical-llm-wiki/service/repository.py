"""Markdown-frontmatter repository and SQLite FTS index.

The Markdown card is always the source of truth. SQLite is disposable derived
state and is rebuilt from cards whenever this process starts or refreshes.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from .contracts import SchemaBundle, canonical_json_sha256


_FRONTMATTER = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)\Z", re.DOTALL)
_IGNORED_TOP_LEVEL = frozenset({".git", ".obsidian", "service", "scripts", "schemas", "indexes", "snapshots", "tests"})
_GOVERNED_TYPES = frozenset({
    "concept", "method", "standard_rule", "decision_rule", "programming_pattern",
    "deliverable_pattern", "prior_study_pattern", "workflow_playbook", "source_record",
    "figure_record",
})
_RECEIPT_SUFFIX = "_decision.json"
_NON_HUMAN_TEST_FIXTURE_ROLE = "non_human_test_fixture"
_SYNTHETIC_PILOT_STUDY_ID = "SYNTH-ONCO-001"
_SYNTHETIC_PILOT_CONDITION = "synthetic-pilot-only"


class RepositoryError(ValueError):
    """A vault record cannot safely enter the governed local index."""


@dataclass(frozen=True, slots=True)
class Card:
    record: dict[str, Any]
    body: str
    path: Path
    relative_path: str
    production_eligible: bool
    eligibility_reasons: tuple[str, ...]


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _safe_relative(root: Path, value: str | Path) -> Path:
    path = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        return path.relative_to(root.resolve())
    except ValueError as exc:
        raise RepositoryError("path must stay within the Wiki root") from exc


def parse_markdown_card(root: Path, path: Path) -> tuple[dict[str, Any], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RepositoryError(f"cannot read {path}: {exc}") from exc
    match = _FRONTMATTER.match(text)
    if match is None:
        raise RepositoryError(f"{path} does not contain YAML frontmatter")
    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise RepositoryError(f"invalid YAML frontmatter in {path}: {exc}") from exc
    if not isinstance(metadata, dict):
        raise RepositoryError(f"frontmatter in {path} must be an object")
    return _normalize_yaml_values(metadata), match.group(2).strip()


class VaultRepository:
    def __init__(self, root: Path, bundle: SchemaBundle) -> None:
        self.root = root.resolve()
        self.bundle = bundle
        self.index_path = self.root / "indexes" / "knowledge.sqlite"
        self._cards: dict[str, Card] = {}

    @property
    def cards(self) -> dict[str, Card]:
        return dict(self._cards)

    def refresh(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        loaded: dict[str, Card] = {}
        for path in sorted(self.root.rglob("*.md")):
            relative = path.relative_to(self.root)
            if not relative.parts or relative.parts[0] in _IGNORED_TOP_LEVEL:
                continue
            if relative.parts[:3] == ("vault", "90_System", "Templates"):
                continue
            try:
                record, body = parse_markdown_card(self.root, path)
            except RepositoryError:
                # Non-governed navigation pages are allowed; only frontmatter pages
                # claiming a governed record are fail-closed below.
                continue
            if "id" not in record or record.get("type") not in _GOVERNED_TYPES:
                continue
            self._validate_record(record)
            record_id = str(record["id"])
            if record_id in loaded:
                raise RepositoryError(f"duplicate governed record id: {record_id}")
            reasons = tuple(self._eligibility_reasons(record))
            loaded[record_id] = Card(
                record=record,
                body=body,
                path=path,
                relative_path=relative.as_posix(),
                production_eligible=not reasons,
                eligibility_reasons=reasons,
            )
        self._cards = loaded
        self._rebuild_index()

    def _schema_for(self, record: dict[str, Any]) -> str:
        record_type = record.get("type")
        if record_type == "workflow_playbook":
            return "knowledge/workflow-playbook.schema.json"
        if record_type == "source_record":
            return "knowledge/source.schema.json"
        if record_type == "figure_record":
            return "knowledge/figure.schema.json"
        return "knowledge/knowledge-item.schema.json"

    def _validate_record(self, record: dict[str, Any]) -> None:
        self.bundle.validate(self._schema_for(record), record)

    def _eligibility_reasons(self, record: dict[str, Any]) -> Iterable[str]:
        if record.get("content_status") != "verified":
            yield "content_not_verified"
        if record.get("approval_status") != "approved":
            yield "use_not_approved"
        receipt_id = record.get("approval_receipt_id")
        audit_reference = record.get("audit_reference")
        if not receipt_id or not audit_reference:
            yield "approval_evidence_missing"
        elif not self._has_approval_evidence(
            str(receipt_id), str(record["id"]), str(audit_reference), record
        ):
            yield "approval_evidence_unverified"
        rights = record.get("rights_status")
        allowed = set(record.get("allowed_uses", []))
        if rights != "cleared" and not (rights == "restricted" and "runtime" in allowed):
            yield "rights_not_cleared_for_runtime"
        if record.get("storage_mode") == "unknown":
            yield "storage_mode_unknown"
        review_due = record.get("review_due")
        try:
            if not review_due or date.fromisoformat(str(review_due)) < _today():
                yield "review_overdue_or_missing"
        except ValueError:
            yield "review_due_invalid"
        compatibility = record.get("contract_compatibility", {})
        if not _semver_in_range(self.bundle.version, compatibility):
            yield "contract_incompatible"
        if record.get("superseded_by") or record.get("approval_status") == "superseded":
            yield "record_superseded"
        if record.get("type") == "source_record" and record.get("source_kind") == "pdf":
            if record.get("pdf_status") != "citation_ready":
                yield "pdf_not_citation_ready"

    def _has_approval_evidence(
        self,
        receipt_id: str,
        record_id: str,
        audit_reference: str,
        record: dict[str, Any],
    ) -> bool:
        # An audit reference must resolve to a governed local artifact or cite a
        # receipt in audit_trail.jsonl. A YAML field alone never grants approval.
        if not self._audit_reference_exists(audit_reference, receipt_id):
            return False
        for receipt_path in self._receipt_paths():
            data = _read_receipt(receipt_path)
            if data is None:
                continue
            review_id = str(data.get("review_id", ""))
            filename_id = receipt_path.name[: -len(_RECEIPT_SUFFIX)] if receipt_path.name.endswith(_RECEIPT_SUFFIX) else receipt_path.stem
            if not _receipt_id_matches(receipt_id, review_id, filename_id):
                continue
            if (
                data.get("reviewer_role") == _NON_HUMAN_TEST_FIXTURE_ROLE
                and not _has_p5_synthetic_scope(record)
            ):
                continue
            packet_targets = self._review_packet_targets(review_id)
            decisions = data.get("decisions", [])
            if any(
                isinstance(decision, dict)
                and decision.get("decision") in {"approved", "modified"}
                and (
                    _decision_targets_record(str(decision.get("finding_id", "")), record_id)
                    or packet_targets.get(str(decision.get("finding_id", ""))) == record_id
                )
                for decision in decisions
            ):
                return True
        return False

    def _review_packet_targets(self, review_id: str) -> dict[str, str]:
        """Map schema-valid finding IDs to governed record IDs from their packet.

        DecisionReceipt.finding_id normally references ``F-001`` rather than a
        knowledge-item ID.  The ReviewPacket ``location`` is therefore the
        durable bridge to the governed record.  Direct record IDs remain
        supported for the imported P3 seed receipt.
        """

        targets: dict[str, str] = {}
        locations = (
            self.root / ".review_queue",
            self.root / "vault" / "80_Governance" / "Review-Receipts",
        )
        for location in locations:
            if not location.exists():
                continue
            for path in location.rglob("*.json"):
                data = _read_json_object(path)
                if data is None or data.get("review_id") != review_id:
                    continue
                for finding in data.get("findings", []):
                    if not isinstance(finding, dict):
                        continue
                    finding_id = finding.get("id")
                    record_id = finding.get("location")
                    if isinstance(finding_id, str) and isinstance(record_id, str):
                        targets[finding_id] = record_id
        return targets

    def _receipt_paths(self) -> Iterable[Path]:
        locations = (
            self.root / ".review_queue",
            self.root / "vault" / "80_Governance" / "Review-Receipts",
        )
        for location in locations:
            if location.exists():
                yield from location.rglob(f"*{_RECEIPT_SUFFIX}")
                yield from location.rglob("*.md")

    def _audit_reference_exists(self, audit_reference: str, receipt_id: str) -> bool:
        try:
            candidate = self.root / _safe_relative(self.root, audit_reference)
        except RepositoryError:
            return False
        if candidate.exists() and candidate.is_file():
            return True
        # Governance receipts may use an audit key rather than an additional
        # mutable audit file.  It remains valid only if the key is recorded in
        # a local human-readable review receipt alongside the DecisionReceipt.
        for receipt_path in self._receipt_paths():
            try:
                if audit_reference in receipt_path.read_text(encoding="utf-8"):
                    return True
            except OSError:
                continue
        audit_log = self.root / "audit_trail.jsonl"
        if not audit_log.exists():
            return False
        try:
            return any(receipt_id in line and audit_reference in line for line in audit_log.read_text(encoding="utf-8").splitlines())
        except OSError:
            return False

    def _rebuild_index(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.index_path) as connection:
            connection.execute("DROP TABLE IF EXISTS records")
            connection.execute("DROP TABLE IF EXISTS records_fts")
            connection.execute(
                """CREATE TABLE records (
                    id TEXT PRIMARY KEY, type TEXT NOT NULL, title TEXT NOT NULL,
                    record_json TEXT NOT NULL, body TEXT NOT NULL, path TEXT NOT NULL,
                    production_eligible INTEGER NOT NULL, reasons_json TEXT NOT NULL
                )"""
            )
            connection.execute(
                "CREATE VIRTUAL TABLE records_fts USING fts5(id UNINDEXED, title, body, topics, domains, stages)"
            )
            for card in self._cards.values():
                record = card.record
                connection.execute(
                    "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record["id"], record["type"], record["title"],
                        json.dumps(record, ensure_ascii=False, sort_keys=True), card.body,
                        card.relative_path, int(card.production_eligible),
                        json.dumps(card.eligibility_reasons),
                    ),
                )
                connection.execute(
                    "INSERT INTO records_fts VALUES (?, ?, ?, ?, ?, ?)",
                    (record["id"], record["title"], card.body,
                     " ".join(record.get("topics", [])),
                     " ".join(record.get("domains", [])),
                     " ".join(record.get("workflow_stages", []))),
                )

    def get(self, record_id: str) -> Card | None:
        return self._cards.get(record_id)

    def search(
        self,
        *,
        query: str = "",
        record_type: str | None = None,
        stage: str | None = None,
        domain: str | None = None,
        topic: str | None = None,
        production_only: bool = False,
        limit: int = 20,
    ) -> list[Card]:
        candidates = list(self._cards.values())
        if query.strip():
            # FTS candidate selection is deliberately separate from authoritative
            # metadata filtering; SQLite remains a rebuildable performance layer.
            with sqlite3.connect(self.index_path) as connection:
                try:
                    rows = connection.execute(
                        "SELECT id FROM records_fts WHERE records_fts MATCH ? LIMIT ?", (query, limit * 5)
                    ).fetchall()
                except sqlite3.OperationalError as exc:
                    raise RepositoryError(f"invalid full-text query: {exc}") from exc
            wanted = {row[0] for row in rows}
            candidates = [card for card in candidates if card.record["id"] in wanted]
        def matches(card: Card) -> bool:
            record = card.record
            return (
                (record_type is None or record.get("type") == record_type)
                and (stage is None or stage in record.get("workflow_stages", []))
                and (domain is None or domain in record.get("domains", []))
                and (topic is None or topic in record.get("topics", []))
                and (not production_only or card.production_eligible)
            )
        return sorted((card for card in candidates if matches(card)), key=lambda item: item.record["id"])[:limit]

    def create_proposal(self, record: dict[str, Any], body: str) -> Card:
        if record.get("approval_status") not in {None, "proposed"}:
            raise RepositoryError("proposals cannot set approval_status directly")
        if record.get("content_status") not in {None, "inbox", "draft"}:
            raise RepositoryError("proposals may only start as inbox or draft content")
        candidate = dict(record)
        candidate["approval_status"] = "proposed"
        candidate["content_status"] = candidate.get("content_status", "draft")
        candidate["approval_receipt_id"] = None
        candidate["audit_reference"] = None
        candidate["created"] = candidate.get("created", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        candidate["schema_version"] = candidate.get("schema_version", self.bundle.version)
        candidate["content_hash"] = canonical_json_sha256({"frontmatter": {k: v for k, v in candidate.items() if k != "content_hash"}, "body": body})
        self._validate_record(candidate)
        record_id = str(candidate["id"])
        if record_id in self._cards:
            raise RepositoryError(f"proposal id already exists: {record_id}")
        inbox = self.root / "vault" / "98_Inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        path = inbox / f"{record_id}.md"
        if path.exists():
            raise RepositoryError(f"proposal path already exists: {path.name}")
        frontmatter = yaml.safe_dump(candidate, allow_unicode=True, sort_keys=False).strip()
        path.write_text(f"---\n{frontmatter}\n---\n\n{body.strip()}\n", encoding="utf-8")
        self._write_proposal_packet(record_id, path, candidate)
        self.refresh()
        return self._cards[record_id]

    def _write_proposal_packet(self, record_id: str, path: Path, record: dict[str, Any]) -> None:
        queue = self.root / ".review_queue"
        queue.mkdir(parents=True, exist_ok=True)
        safe_id = record_id.replace("-", "_")
        review_id = f"sap_review_{safe_id}_v1_001"
        packet = {
            "review_id": review_id,
            "review_type": "sap_review",
            "source_documents": [path.relative_to(self.root).as_posix()],
            "agent_summary": f"Governance approval required for knowledge proposal {record_id}.",
            "findings": [{
                "id": "F-001", "category": "compliance", "severity": "warning",
                "location": record_id, "title": "Approve governed knowledge proposal",
                "current_value": "proposal", "proposed_value": record["title"],
                "rationale": "A human DecisionReceipt is required before production use.",
                "evidence_refs": list(record.get("sources", [])) or [record_id],
                "auto_approved": False,
            }],
            "urgency": "blocking",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "generated_by": "clinical-knowledge-service",
            "auto_approved_count": 0,
        }
        self.bundle.validate_definition("review/review-protocol.schema.json", "review_packet", packet)
        (queue / f"{review_id}.json").write_text(
            json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def _receipt_id_matches(expected: str, review_id: str, filename_id: str) -> bool:
    def normalize(value: str) -> str:
        return value.removeprefix("review-").replace("_", "-")

    expected_normalized = normalize(expected)
    return expected_normalized in {normalize(review_id), normalize(filename_id)}


def _read_receipt(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if path.suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
    # Imported evidence can be a read-only Markdown record containing several
    # JSON code blocks.  We select the one shaped as a DecisionReceipt.
    for block in re.findall(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and {"review_id", "reviewer", "decisions"}.issubset(data):
            return data
    return None


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _decision_targets_record(finding_id: str, record_id: str) -> bool:
    if record_id in finding_id:
        return True
    # Existing imported receipt uses the durable stem before the descriptive
    # '-baseline' suffix. This is still stricter than a generic approval.
    parts = record_id.split("-")
    return len(parts) >= 3 and "-".join(parts[:3]) in finding_id


def _has_p5_synthetic_scope(record: dict[str, Any]) -> bool:
    """Fail closed for the only non-human approval scope accepted in P5.

    A non-human fixture is evidence for the named synthetic pilot only. Future
    fixtures must add an explicit machine contract instead of inheriting this
    exception through reviewer text or a generic ``approved`` decision.
    """

    applicability = record.get("applicability")
    if not isinstance(applicability, dict):
        return False
    study_ids = applicability.get("study_ids")
    conditions = applicability.get("conditions")
    return (
        study_ids == [_SYNTHETIC_PILOT_STUDY_ID]
        and isinstance(conditions, list)
        and _SYNTHETIC_PILOT_CONDITION in conditions
    )


def _normalize_yaml_values(value: Any) -> Any:
    """PyYAML turns ISO dates into Python objects; contracts require JSON strings."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize_yaml_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_yaml_values(item) for item in value]
    return value


def _semver_in_range(version: str, compatibility: Any) -> bool:
    if not isinstance(compatibility, dict):
        return False
    try:
        current = tuple(int(part) for part in version.split("-", 1)[0].split("."))
        minimum = tuple(int(part) for part in str(compatibility["minimum"]).split("-", 1)[0].split("."))
        maximum = tuple(int(part) for part in str(compatibility["maximum_exclusive"]).split("-", 1)[0].split("."))
    except (KeyError, ValueError):
        return False
    return len(current) == len(minimum) == len(maximum) == 3 and minimum <= current < maximum
