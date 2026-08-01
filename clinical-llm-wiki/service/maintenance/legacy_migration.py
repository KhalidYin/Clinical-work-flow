"""Fail-closed, one-time migration of the retired Markdown Wiki authority.

This module is deliberately separate from database schema migrations.  It inventories immutable
legacy bytes, maps governed records to deterministic P12 identities, and writes
an immutable report to the configured ObjectStore.  Historical hashes are
preserved as evidence; all newly produced JSON uses the P12 canonical format.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

import yaml
from sqlalchemy.orm import Session, sessionmaker

from service.db.models import (
    AuditEvent,
    CandidateEvidence,
    Evidence,
    KnowledgeCandidate,
    KnowledgeRevision,
    KnowledgeUnit,
    ProcessingRun,
    Release,
    ReleaseItem,
    ReviewDecision,
    Source,
    SourceArtifact,
    SourceVersion,
)
from service.object_store import ObjectDescriptor, ObjectStorePort


_FRONTMATTER = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)\Z", re.DOTALL)
_REPORT_KEY = "migration/p13/legacy-wiki-migration-report-v1.json"


class LegacyMigrationError(RuntimeError):
    """Legacy bytes cannot be mapped without losing identity or evidence."""


@dataclass(frozen=True, slots=True)
class LegacyRecord:
    legacy_id: str
    version: str
    knowledge_type: str
    approval_status: str
    approval_receipt_id: str | None
    content_hash: str
    source_path: str
    source_sha256: str
    body: str
    record: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class MigrationRecord:
    legacy_id: str
    legacy_version: str
    legacy_content_hash: str
    legacy_approval_receipt_id: str | None
    source_path: str
    source_sha256: str
    knowledge_unit_id: str
    knowledge_revision_id: str
    source_id: str
    source_version_id: str
    evidence_id: str
    target_content_sha256: str
    status: str


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    schema_version: str
    migration_id: str
    records: tuple[MigrationRecord, ...]
    asset_inventory: tuple[Mapping[str, Any], ...]
    unresolved_assets: tuple[str, ...]
    report_sha256: str

    def report_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "migration_id": self.migration_id,
            "record_count": len(self.records),
            "records": [asdict(item) for item in self.records],
            "asset_inventory": [dict(item) for item in self.asset_inventory],
            "unresolved_assets": list(self.unresolved_assets),
        }


@dataclass(frozen=True, slots=True)
class MigrationApplyResult:
    record_count: int
    released_revision_count: int
    report_object_key: str
    report_sha256: str
    release_id: str
    release_manifest_sha256: str


def canonical_json_bytes(value: Any) -> bytes:
    """P12 canonical JSON: UTF-8, sorted compact keys, no trailing newline."""

    return json.dumps(
        _json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def scan_legacy_vault(vault_root: Path) -> tuple[LegacyRecord, ...]:
    """Read governed Markdown while making malformed frontmatter fatal.

    Plain Markdown navigation pages remain non-governed and are ignored.  A page
    that starts a frontmatter envelope has asserted structure and therefore may
    never disappear silently from the migration inventory.
    """

    root = vault_root.resolve()
    records: list[LegacyRecord] = []
    seen: set[str] = set()
    for path in sorted(
        root.rglob("*.md"), key=lambda item: item.relative_to(root).as_posix()
    ):
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise LegacyMigrationError(f"cannot read legacy page {path}: {exc}") from exc
        if not text.startswith("---"):
            continue
        match = _FRONTMATTER.match(text)
        if match is None:
            raise LegacyMigrationError(f"invalid frontmatter envelope: {path}")
        try:
            metadata = yaml.safe_load(match.group(1))
        except yaml.YAMLError as exc:
            raise LegacyMigrationError(f"invalid YAML frontmatter in {path}: {exc}") from exc
        if not isinstance(metadata, dict):
            raise LegacyMigrationError(f"frontmatter must be an object: {path}")
        record = _json_value(metadata)
        record_type = record.get("type")
        record_id = record.get("id")
        # The retirement crosswalk treats every explicitly identified typed page
        # as governed migration input.  That includes navigation and historical
        # governance evidence, even though the old runtime index exposed only a
        # smaller set of knowledge-card types.
        if not record_type or not record_id:
            continue
        legacy_id = str(record_id)
        if legacy_id in seen:
            raise LegacyMigrationError(f"duplicate governed id {legacy_id}: {path}")
        seen.add(legacy_id)
        relative = path.relative_to(root).as_posix()
        records.append(
            LegacyRecord(
                legacy_id=legacy_id,
                version=str(record.get("version") or "0.0.0"),
                knowledge_type=str(record_type),
                approval_status=str(record.get("approval_status") or "unreviewed"),
                approval_receipt_id=(
                    str(record["approval_receipt_id"])
                    if record.get("approval_receipt_id")
                    else None
                ),
                content_hash=str(record.get("content_hash") or sha256(raw).hexdigest()),
                source_path=relative,
                source_sha256=sha256(raw).hexdigest(),
                body=match.group(2).strip(),
                record=record,
            )
        )
    return tuple(records)


def build_migration_plan(wiki_root: Path) -> MigrationPlan:
    root = wiki_root.resolve()
    legacy = scan_legacy_vault(root / "vault")
    records: list[MigrationRecord] = []
    for item in legacy:
        target_payload = {
            "legacy_record": item.record,
            "legacy_body": item.body,
            "legacy_source_path": item.source_path,
            "legacy_source_sha256": item.source_sha256,
        }
        digest = sha256(canonical_json_bytes(target_payload)).hexdigest()
        identity_digest = sha256(item.legacy_id.encode("utf-8")).hexdigest()[:24]
        records.append(
            MigrationRecord(
                legacy_id=item.legacy_id,
                legacy_version=item.version,
                legacy_content_hash=item.content_hash,
                legacy_approval_receipt_id=item.approval_receipt_id,
                source_path=f"vault/{item.source_path}",
                source_sha256=item.source_sha256,
                knowledge_unit_id=item.legacy_id,
                knowledge_revision_id=f"krev-legacy-{identity_digest}",
                source_id=f"src-legacy-{identity_digest}",
                source_version_id=f"sv-legacy-{identity_digest}",
                evidence_id=f"ev-legacy-{identity_digest}",
                target_content_sha256=digest,
                status=("released" if item.approval_status == "approved" else "review_required"),
            )
        )
    inventory = _asset_inventory(root)
    payload = {
        "schema_version": "1.0.0",
        "migration_id": "p13-legacy-wiki-v1",
        "record_count": len(records),
        "records": [asdict(item) for item in records],
        "asset_inventory": [dict(item) for item in inventory],
        "unresolved_assets": [],
    }
    return MigrationPlan(
        schema_version="1.0.0",
        migration_id="p13-legacy-wiki-v1",
        records=tuple(records),
        asset_inventory=inventory,
        unresolved_assets=(),
        report_sha256=sha256(canonical_json_bytes(payload)).hexdigest(),
    )


def write_immutable_report(
    plan: MigrationPlan, object_store: ObjectStorePort
) -> ObjectDescriptor:
    content = canonical_json_bytes(plan.report_payload())
    actual = sha256(content).hexdigest()
    if actual != plan.report_sha256:
        raise LegacyMigrationError("migration report differs from the reviewed plan")
    return object_store.put_bytes(
        _REPORT_KEY,
        content,
        media_type="application/json",
        expected_sha256=plan.report_sha256,
    )


def build_runtime_release_manifest(wiki_root: Path) -> dict[str, Any]:
    """Build the compatibility projection stored by one immutable P12 Release."""

    root = wiki_root.resolve()
    bundle_path = root / "schemas" / "engine" / "contract-bundle.json"
    try:
        bundle_lock = json.loads(bundle_path.read_text(encoding="utf-8"))
        bundle = {
            "id": str(bundle_lock["bundle_id"]),
            "version": str(bundle_lock["bundle_version"]),
            "sha256": str(bundle_lock["bundle_sha256"]),
        }
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise LegacyMigrationError("Engine schema bundle lock cannot be migrated") from exc
    eligible = [
        dict(item.record)
        for item in scan_legacy_vault(root / "vault")
        if _runtime_eligible(item.record)
    ]
    workflow = [item for item in eligible if item.get("type") == "workflow_playbook"]
    domain = [
        item
        for item in eligible
        if item.get("type")
        not in {"workflow_playbook", "source_record", "figure_record", "navigation"}
        and isinstance(item.get("statements"), list)
    ]
    return {
        "schema_version": "1.0.0",
        "release_id": "release-p13-legacy-wiki-v1",
        "version": "p13-legacy-wiki-v1",
        "schema_bundle": bundle,
        "runtime_snapshots": [
            _runtime_snapshot("snapshot-p12-release-workflow-v1", bundle, workflow),
            _runtime_snapshot("snapshot-p12-release-domain-v1", bundle, domain),
        ],
    }


def apply_migration(
    wiki_root: Path,
    session_factory: sessionmaker[Session],
    object_store: ObjectStorePort,
) -> MigrationApplyResult:
    """Apply deterministic canonical rows without mutating an existing revision."""

    root = wiki_root.resolve()
    plan = build_migration_plan(root)
    report = write_immutable_report(plan, object_store)
    legacy_by_id = {item.legacy_id: item for item in scan_legacy_vault(root / "vault")}
    release_manifest = build_runtime_release_manifest(root)
    release_bytes = canonical_json_bytes(release_manifest)
    release_descriptor = object_store.put_bytes(
        "release/p13/legacy-wiki-v1/manifest.json",
        release_bytes,
        media_type="application/json",
    )
    released_ids: list[str] = []

    with session_factory.begin() as session:
        for mapping in plan.records:
            legacy = legacy_by_id[mapping.legacy_id]
            identity = mapping.source_id.removeprefix("src-legacy-")
            raw = (root / mapping.source_path).read_bytes()
            canonical = canonical_json_bytes(
                {
                    "legacy_record": legacy.record,
                    "legacy_body": legacy.body,
                    "legacy_source_path": legacy.source_path,
                    "legacy_source_sha256": legacy.source_sha256,
                }
            )
            raw_object = object_store.put_bytes(
                f"migration/p13/sources/{identity}.md",
                raw,
                media_type="text/markdown",
                expected_sha256=mapping.source_sha256,
            )
            canonical_object = object_store.put_bytes(
                f"migration/p13/records/{identity}.json",
                canonical,
                media_type="application/json",
                expected_sha256=mapping.target_content_sha256,
            )
            original_artifact_id = f"art-legacy-original-{identity}"
            canonical_artifact_id = f"art-legacy-canonical-{identity}"
            run_id = f"run-legacy-{identity}"
            candidate_id = f"cand-legacy-{identity}"

            _add_or_verify(
                session,
                Source,
                mapping.source_id,
                "source_id",
                expected={"title": str(legacy.record.get("title") or legacy.legacy_id)},
                create={
                    "source_id": mapping.source_id,
                    "title": str(legacy.record.get("title") or legacy.legacy_id),
                    "source_type": "legacy_wiki_page",
                    "owner_org": str(legacy.record.get("owner") or "legacy-wiki"),
                },
            )
            _add_or_verify(
                session,
                SourceVersion,
                mapping.source_version_id,
                "source_version_id",
                expected={"sha256": mapping.source_sha256},
                create={
                    "source_version_id": mapping.source_version_id,
                    "source_id": mapping.source_id,
                    "version": mapping.legacy_version,
                    "sha256": mapping.source_sha256,
                    "rights": {
                        "legacy_rights_status": legacy.record.get("rights_status", "unknown"),
                        "allowed_uses": legacy.record.get("allowed_uses", []),
                    },
                    "data_boundary": "local_processing_only",
                    "status": "registered",
                },
            )
            _add_or_verify(
                session,
                SourceArtifact,
                original_artifact_id,
                "artifact_id",
                expected={"sha256": raw_object.sha256},
                create={
                    "artifact_id": original_artifact_id,
                    "source_version_id": mapping.source_version_id,
                    "artifact_kind": "original",
                    "parent_artifact_id": None,
                    "object_key": raw_object.object_key,
                    "sha256": raw_object.sha256,
                    "media_type": raw_object.media_type,
                    "size_bytes": raw_object.size_bytes,
                    "parser_profile_version": None,
                    "status": "available",
                },
            )
            _add_or_verify(
                session,
                SourceArtifact,
                canonical_artifact_id,
                "artifact_id",
                expected={"sha256": canonical_object.sha256},
                create={
                    "artifact_id": canonical_artifact_id,
                    "source_version_id": mapping.source_version_id,
                    "artifact_kind": "parser_output",
                    "parent_artifact_id": original_artifact_id,
                    "object_key": canonical_object.object_key,
                    "sha256": canonical_object.sha256,
                    "media_type": canonical_object.media_type,
                    "size_bytes": canonical_object.size_bytes,
                    "parser_profile_version": "p13-legacy-migration-v1",
                    "status": "available",
                },
            )
            _add_or_verify(
                session,
                ProcessingRun,
                run_id,
                "run_id",
                expected={"source_version_id": mapping.source_version_id},
                create={
                    "run_id": run_id,
                    "source_version_id": mapping.source_version_id,
                    "status": "released" if mapping.status == "released" else "evidence_ready",
                    "requested_by_subject": "migration:p13",
                },
            )
            locator = {"legacy_path": mapping.source_path}
            locator_hash = sha256(canonical_json_bytes(locator)).hexdigest()
            _add_or_verify(
                session,
                Evidence,
                mapping.evidence_id,
                "evidence_id",
                expected={"content_sha256": mapping.target_content_sha256},
                create={
                    "evidence_id": mapping.evidence_id,
                    "source_version_id": mapping.source_version_id,
                    "source_artifact_id": original_artifact_id,
                    "derived_artifact_id": canonical_artifact_id,
                    "source_sha256": mapping.source_sha256,
                    "parser_profile_version": "p13-legacy-migration-v1",
                    "evidence_type": "legacy_governed_page",
                    "locator": locator,
                    "locator_sha256": locator_hash,
                    "content": canonical.decode("utf-8"),
                    "content_sha256": mapping.target_content_sha256,
                    "schema_version": "1.0.0",
                },
            )
            claim = _legacy_claim(legacy)
            scope = {
                "legacy_id": legacy.legacy_id,
                "legacy_version": legacy.version,
                "legacy_record": legacy.record,
                "migration_report": report.object_key,
            }
            _add_or_verify(
                session,
                KnowledgeCandidate,
                candidate_id,
                "candidate_id",
                expected={"content_sha256": mapping.target_content_sha256},
                create={
                    "candidate_id": candidate_id,
                    "candidate_group_id": f"legacy-{identity}",
                    "parent_candidate_id": None,
                    "run_id": run_id,
                    "revision_number": 1,
                    "status": "author_confirmed",
                    "knowledge_type": legacy.knowledge_type,
                    "claim": claim,
                    "scope": scope,
                    "applicability": legacy.record.get("applicability"),
                    "conditions": [],
                    "exceptions": [],
                    "advisory_signals": [],
                    "confidence": None,
                    "content_sha256": mapping.target_content_sha256,
                    "author_actor_id": None,
                    "author_subject": "migration:p13",
                },
            )
            if session.get(CandidateEvidence, (candidate_id, mapping.evidence_id)) is None:
                session.add(
                    CandidateEvidence(
                        candidate_id=candidate_id,
                        evidence_id=mapping.evidence_id,
                        evidence_role="supports",
                    )
                )
            _add_or_verify(
                session,
                KnowledgeUnit,
                mapping.knowledge_unit_id,
                "knowledge_unit_id",
                expected={"stable_key": mapping.legacy_id},
                create={
                    "knowledge_unit_id": mapping.knowledge_unit_id,
                    "stable_key": mapping.legacy_id,
                    "knowledge_type": legacy.knowledge_type,
                },
            )
            _add_or_verify(
                session,
                KnowledgeRevision,
                mapping.knowledge_revision_id,
                "knowledge_revision_id",
                expected={"content_sha256": mapping.target_content_sha256},
                create={
                    "knowledge_revision_id": mapping.knowledge_revision_id,
                    "knowledge_unit_id": mapping.knowledge_unit_id,
                    "candidate_id": candidate_id,
                    "revision_number": 1,
                    "status": mapping.status,
                    "claim": claim,
                    "scope": scope,
                    "applicability": legacy.record.get("applicability"),
                    "conditions": [],
                    "exceptions": [],
                    "content_sha256": mapping.target_content_sha256,
                    "author_actor_id": None,
                    "approved_at": (
                        datetime.now(timezone.utc) if mapping.status == "released" else None
                    ),
                },
            )
            if mapping.status == "released":
                released_ids.append(mapping.knowledge_revision_id)
                decision_id = f"decision-legacy-{identity}"
                _add_or_verify(
                    session,
                    ReviewDecision,
                    decision_id,
                    "decision_id",
                    expected={"content_sha256": mapping.target_content_sha256},
                    create={
                        "decision_id": decision_id,
                        "candidate_id": candidate_id,
                        "knowledge_revision_id": mapping.knowledge_revision_id,
                        "decision": "approved",
                        "candidate_revision_number": 1,
                        "content_sha256": mapping.target_content_sha256,
                        "idempotency_key": f"p13:{legacy.legacy_id}",
                        "actor_subject": "migration:p13",
                        "actor_role": "legacy_review_import",
                        "rationale": legacy.approval_receipt_id or "legacy approved record",
                        "invalidated_step_ids": [],
                    },
                )
            audit_id = f"audit-legacy-{identity}"
            _add_or_verify(
                session,
                AuditEvent,
                audit_id,
                "audit_event_id",
                expected={"entity_id": mapping.knowledge_unit_id},
                create={
                    "audit_event_id": audit_id,
                    "actor_subject": "migration:p13",
                    "action": "legacy_knowledge_migrated",
                    "entity_type": "knowledge_unit",
                    "entity_id": mapping.knowledge_unit_id,
                    "run_id": run_id,
                    "details": {
                        "legacy_path": mapping.source_path,
                        "legacy_sha256": mapping.source_sha256,
                        "migration_report_sha256": report.sha256,
                    },
                },
            )
            session.flush()

        release_id = "release-p13-legacy-wiki-v1"
        _add_or_verify(
            session,
            Release,
            release_id,
            "release_id",
            expected={"manifest_sha256": release_descriptor.sha256},
            create={
                "release_id": release_id,
                "version": "p13-legacy-wiki-v1",
                "status": "released",
                "previous_release_id": None,
                "manifest_object_key": release_descriptor.object_key,
                "manifest_sha256": release_descriptor.sha256,
                "db_schema_revision": "20260801_0008",
                "knowledge_contract_version": "1.0.0",
                "parser_profile_version": "p13-legacy-migration-v1",
                "model_profile_version": "not-used",
                "prompt_profile_version": "not-used",
                "index_manifest_version": "legacy-migration-no-index",
                "release_manager_subject": "migration:p13",
                "published_at": datetime.now(timezone.utc),
            },
        )
        session.flush()
        for revision_id in released_ids:
            key = (release_id, revision_id)
            existing = session.get(ReleaseItem, key)
            revision = session.get(KnowledgeRevision, revision_id)
            if revision is None:
                raise LegacyMigrationError(f"released revision disappeared: {revision_id}")
            if existing is None:
                session.add(
                    ReleaseItem(
                        release_id=release_id,
                        knowledge_revision_id=revision_id,
                        content_sha256=revision.content_sha256,
                    )
                )
            elif existing.content_sha256 != revision.content_sha256:
                raise LegacyMigrationError(f"released item collision: {revision_id}")

    return MigrationApplyResult(
        record_count=len(plan.records),
        released_revision_count=len(released_ids),
        report_object_key=report.object_key,
        report_sha256=report.sha256,
        release_id="release-p13-legacy-wiki-v1",
        release_manifest_sha256=release_descriptor.sha256,
    )


def _asset_inventory(root: Path) -> tuple[Mapping[str, Any], ...]:
    scopes = (
        "vault",
        "sources/accessions",
        "sources/packages",
        "snapshots",
        ".review_queue",
        "audit_trail.jsonl",
    )
    inventory: list[Mapping[str, Any]] = []
    for scope in scopes:
        target = root / scope
        paths = (
            [target]
            if target.is_file()
            else sorted(
                (path for path in target.rglob("*") if path.is_file()),
                key=lambda item: item.relative_to(root).as_posix(),
            )
            if target.is_dir()
            else []
        )
        inventory.append(
            {
                "path": scope,
                "file_count": len(paths),
                "files": [
                    {
                        "path": path.relative_to(root).as_posix(),
                        "sha256": sha256(path.read_bytes()).hexdigest(),
                    }
                    for path in paths
                ],
            }
        )
    return tuple(inventory)


def _runtime_eligible(record: Mapping[str, Any]) -> bool:
    if record.get("content_status") != "verified" or record.get("approval_status") != "approved":
        return False
    if not record.get("approval_receipt_id") or not record.get("audit_reference"):
        return False
    rights = record.get("rights_status")
    allowed = set(record.get("allowed_uses", []))
    return rights == "cleared" or (
        rights == "restricted"
        and bool({"runtime", "runtime_context", "internal_knowledge_service"} & allowed)
    )


def _runtime_snapshot(
    snapshot_id: str,
    bundle: Mapping[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    snapshot_bundle = {"version": bundle["version"], "sha256": bundle["sha256"]}
    digest = sha256(
        canonical_json_bytes({"schema_bundle": snapshot_bundle, "items": items})
    ).hexdigest()
    return {
        "snapshot_id": snapshot_id,
        "version": "1.0.0",
        "sha256": digest,
        "schema_bundle": snapshot_bundle,
        "items": items,
    }


def _legacy_claim(record: LegacyRecord) -> str:
    raw = record.record
    statements = raw.get("statements")
    if isinstance(statements, list):
        text = " ".join(
            str(item.get("statement"))
            for item in statements
            if isinstance(item, Mapping) and item.get("statement")
        )
        if text:
            return text
    for key in ("summary", "purpose", "title"):
        value = raw.get(key)
        if isinstance(value, str) and value:
            return value
    return record.body or record.legacy_id


def _add_or_verify(
    session: Session,
    model: type[Any],
    primary_key: Any,
    primary_key_name: str,
    *,
    expected: Mapping[str, Any],
    create: Mapping[str, Any],
) -> Any:
    existing = session.get(model, primary_key)
    if existing is None:
        created = model(**dict(create))
        session.add(created)
        return created
    mismatched = [
        name for name, value in expected.items() if getattr(existing, name) != value
    ]
    if mismatched:
        raise LegacyMigrationError(
            f"canonical identity collision for {primary_key_name}={primary_key}: "
            + ", ".join(mismatched)
        )
    return existing


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _run_p13_legacy_wiki(dry_run: bool) -> int:
    root = Path(__file__).resolve().parents[2]
    plan = build_migration_plan(root)
    if dry_run:
        return len(plan.records)
    import os

    from service.db.session import (
        create_database_engine,
        create_session_factory,
        database_url_from_environment,
    )
    from service.object_store import LocalObjectStore

    object_root = os.environ.get("KNOWLEDGE_OBJECT_STORE_ROOT")
    if not object_root:
        raise LegacyMigrationError("KNOWLEDGE_OBJECT_STORE_ROOT is required")
    engine = create_database_engine(database_url_from_environment())
    result = apply_migration(
        root,
        create_session_factory(engine),
        LocalObjectStore(root=Path(object_root)),
    )
    return result.record_count


LegacyMigrationCallable = Callable[[bool], int]
REGISTERED_MIGRATIONS: dict[str, LegacyMigrationCallable] = {
    "p13-legacy-wiki-v1": _run_p13_legacy_wiki,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--migration", choices=sorted(REGISTERED_MIGRATIONS))
    parser.add_argument("--apply", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.list:
        for name in sorted(REGISTERED_MIGRATIONS):
            print(name)
        return 0
    if args.migration is None:
        parser.error("--migration is required unless --list is used")
    migrated = REGISTERED_MIGRATIONS[args.migration](not args.apply)
    print(f"mode={'apply' if args.apply else 'dry-run'} migrated={migrated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
