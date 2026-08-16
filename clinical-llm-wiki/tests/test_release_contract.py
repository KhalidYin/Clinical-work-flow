from __future__ import annotations

from importlib import import_module

import pytest
from pydantic import ValidationError


def _module():
    return import_module("service.releases.contracts")


def test_release_build_contract_pins_base_evaluation_profile_and_membership() -> None:
    module = _module()
    command = module.ReleaseBuildCommand(
        release_candidate_id="release-candidate-synthetic-v2",
        version="synthetic.2",
        base_release_id="release-synthetic-v1",
        evaluation_run_id="evaluation-synthetic-pass",
        chunk_profile_id="chunk-profile-synthetic-v1",
        rotation_case_ids=("rotation-synthetic-safe", "rotation-synthetic-risk"),
        additional_revision_ids=(),
        index_capabilities={
            "metadata": "available",
            "full_text": "available",
            "vector": "degraded",
            "relation": "degraded",
        },
        db_schema_revision="20260816_0012",
        knowledge_contract_version="p17-v1",
        parser_profile_version="parser-synthetic-v1",
        model_profile_version="replay-v1",
        prompt_profile_version="prompt-v1",
    )

    assert command.base_release_id == "release-synthetic-v1"
    assert command.rotation_case_ids == (
        "rotation-synthetic-safe",
        "rotation-synthetic-risk",
    )
    assert "manifest_sha256" not in type(command).model_fields


def test_release_contract_rejects_unscoped_or_fake_capabilities() -> None:
    module = _module()
    payload = {
        "release_candidate_id": "release-candidate-synthetic-v2",
        "version": "synthetic.2",
        "base_release_id": None,
        "evaluation_run_id": "evaluation-synthetic-pass",
        "chunk_profile_id": "chunk-profile-synthetic-v1",
        "rotation_case_ids": (),
        "additional_revision_ids": ("revision-synthetic-1",),
        "index_capabilities": {
            "metadata": "available",
            "full_text": "available",
            "vector": "available",
            "relation": "degraded",
        },
        "db_schema_revision": "20260816_0012",
        "knowledge_contract_version": "p17-v1",
        "parser_profile_version": "parser-synthetic-v1",
        "model_profile_version": "replay-v1",
        "prompt_profile_version": "prompt-v1",
    }
    with pytest.raises(ValidationError, match="vector"):
        module.ReleaseBuildCommand.model_validate(payload)

    payload["index_capabilities"]["vector"] = "degraded"
    payload["additional_revision_ids"] = ()
    with pytest.raises(ValidationError, match="membership"):
        module.ReleaseBuildCommand.model_validate(payload)
