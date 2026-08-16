from __future__ import annotations

from datetime import datetime, timezone

from service.auth import (
    ActorContext,
    IdentitySource,
    Permission,
    PrincipalType,
    ProductRole,
)
from service.releases import (
    ReleaseGateFact,
    ReleaseManifestPayload,
    ReleaseSummaryRecord,
    ReleaseWorkbenchService,
    ReleaseWorkbenchSnapshot,
)


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


def _summary(release_id: str, status: str, *, current: bool = False):
    return ReleaseSummaryRecord(
        release_id=release_id,
        version=release_id,
        status=status,
        base_release_id="release-base" if status == "candidate" else None,
        item_count=3,
        is_current=current,
        created_at=NOW,
        published_at=NOW if status == "released" else None,
    )


def _manifest(release_id: str, items: tuple[dict[str, object], ...]):
    return ReleaseManifestPayload(
        release_id=release_id,
        release_version=release_id,
        base_release_id=None if release_id == "release-base" else "release-base",
        evaluation_run_id="evaluation-release-candidate",
        chunk_profile_id="profile-p17",
        chunk_profile_version="v1",
        rotation_case_ids=(),
        db_schema_revision="20260816_0012",
        knowledge_contract_version="p17-v1",
        parser_profile_version="parser-v1",
        model_profile_version="replay-v1",
        prompt_profile_version="prompt-v1",
        index_descriptor={
            "object_key": f"releases/{release_id}/index.json",
            "sha256": "a" * 64,
            "media_type": "application/json",
            "size_bytes": 100,
        },
        items=items,
    )


class FakeRepository:
    def __init__(self, snapshot: ReleaseWorkbenchSnapshot) -> None:
        self.snapshot = snapshot

    def load_workbench(self, *, candidate_id: str | None):
        assert candidate_id in {None, "release-candidate"}
        return self.snapshot


def _manager() -> ActorContext:
    return ActorContext(
        actor_id="usr-release-manager",
        display_name="Release Manager",
        principal_type=PrincipalType.HUMAN,
        roles=frozenset({ProductRole.RELEASE_MANAGER}),
        permissions=frozenset({Permission.QUERY_RELEASED, Permission.RELEASE_PUBLISH}),
        identity_source=IdentitySource.LOCAL_TEST,
    )


def test_release_workbench_computes_diff_and_publish_action_on_the_server() -> None:
    base = _manifest(
        "release-base",
        (
            {
                "knowledge_revision_id": "revision-carried",
                "content_sha256": "1" * 64,
                "disposition": "add",
                "evidence_ids": ["e1"],
                "chunk_ids": ["c1"],
            },
            {
                "knowledge_revision_id": "revision-retired",
                "content_sha256": "2" * 64,
                "disposition": "add",
                "evidence_ids": ["e2"],
                "chunk_ids": ["c2"],
            },
        ),
    )
    candidate = _manifest(
        "release-candidate",
        (
            {
                "knowledge_revision_id": "revision-carried",
                "content_sha256": "1" * 64,
                "disposition": "carry_forward",
                "evidence_ids": ["e1"],
                "chunk_ids": ["c1"],
            },
            {
                "knowledge_revision_id": "revision-replacement",
                "content_sha256": "3" * 64,
                "disposition": "replace",
                "evidence_ids": ["e3"],
                "chunk_ids": ["c3"],
            },
            {
                "knowledge_revision_id": "revision-added",
                "content_sha256": "4" * 64,
                "disposition": "add",
                "evidence_ids": ["e4"],
                "chunk_ids": ["c4"],
            },
        ),
    )
    snapshot = ReleaseWorkbenchSnapshot(
        current=_summary("release-base", "released", current=True),
        candidate=_summary("release-candidate", "candidate"),
        history=(_summary("release-base", "released", current=True),),
        candidate_manifest=candidate,
        base_manifest=base,
        gates=(
            ReleaseGateFact(code="candidate_integrity", passed=True, reason="hash_verified"),
            ReleaseGateFact(
                code="base_release_current", passed=True, reason="base_matches_current"
            ),
            ReleaseGateFact(code="evaluation_passed", passed=True, reason="evaluation_passed"),
            ReleaseGateFact(code="publication_snapshot", passed=True, reason="snapshot_valid"),
        ),
    )

    result = ReleaseWorkbenchService(repository=FakeRepository(snapshot)).get(
        actor=_manager(), candidate_id=None
    )

    assert result.diff is not None
    assert result.diff.included_revision_ids == (
        "revision-added",
        "revision-carried",
        "revision-replacement",
    )
    assert result.diff.carried_revision_ids == ("revision-carried",)
    assert result.diff.replaced_revision_ids == ("revision-replacement",)
    assert result.diff.retired_revision_ids == ("revision-retired",)
    assert result.blockers == ()
    assert result.allowed_actions == ("publish",)


def test_release_workbench_returns_blockers_instead_of_inferring_publishability() -> None:
    snapshot = ReleaseWorkbenchSnapshot(
        current=_summary("release-base", "released", current=True),
        candidate=_summary("release-candidate", "candidate"),
        history=(),
        candidate_manifest=None,
        base_manifest=None,
        gates=(
            ReleaseGateFact(
                code="candidate_integrity",
                passed=False,
                reason="manifest_hash_mismatch",
            ),
        ),
    )

    result = ReleaseWorkbenchService(repository=FakeRepository(snapshot)).get(
        actor=_manager(), candidate_id="release-candidate"
    )

    assert result.diff is None
    assert result.blockers == ("manifest_hash_mismatch",)
    assert result.allowed_actions == ()
