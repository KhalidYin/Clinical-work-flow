from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError


IMAGE_REF = "ghcr.io/anomalyco/opencode:1.18.14@sha256:" + "b" * 64
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _write_pack(root: Path, *, manifest_updates: dict[str, object] | None = None) -> Path:
    pack_root = root / "knowledge-candidate-v1"
    (pack_root / "instructions").mkdir(parents=True)
    (pack_root / "skills" / "evidence-candidate" / "references").mkdir(parents=True)
    (pack_root / "schemas").mkdir(parents=True)
    (pack_root / "instructions" / "system.md").write_text(
        "Generate one evidence-linked knowledge candidate.\n",
        encoding="utf-8",
    )
    (pack_root / "skills" / "evidence-candidate" / "SKILL.md").write_text(
        "---\n"
        "name: evidence-candidate\n"
        "description: Build one candidate from authorized Evidence.\n"
        "---\n\n"
        "Read references/policy.md, then use only the authorized Evidence tool.\n",
        encoding="utf-8",
    )
    (pack_root / "skills" / "evidence-candidate" / "references" / "policy.md").write_text(
        "Every claim must cite an Evidence ID.\n",
        encoding="utf-8",
    )
    (pack_root / "schemas" / "candidate.schema.json").write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "required": ["claim", "evidence_ids"],
                "properties": {
                    "claim": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "additionalProperties": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (pack_root / "mcp-policy.yaml").write_text(
        json.dumps(
            {
                "contract_version": "1.0.0",
                "capabilities": [
                    {
                        "capability_id": "knowledge.read-evidence",
                        "tools": ["read_evidence"],
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    manifest: dict[str, object] = {
        "contract_version": "1.0.0",
        "pack_id": "knowledge-candidate-v1",
        "version": "1.0.0",
        "adapter_id": "opencode@1.18.14",
        "image_ref": IMAGE_REF,
        "instruction_file": "instructions/system.md",
        "skills": [
            {
                "skill_id": "evidence-candidate",
                "path": "skills/evidence-candidate",
            }
        ],
        "mcp_policy_file": "mcp-policy.yaml",
        "output_schema_file": "schemas/candidate.schema.json",
        "model": {
            "protocol": "openai-compatible",
            "structured_output": True,
        },
        "budget": {
            "max_calls": 1,
            "max_tokens": 4096,
            "max_time_seconds": 60,
        },
    }
    manifest.update(manifest_updates or {})
    (pack_root / "pack.yaml").write_text(
        json.dumps(manifest, sort_keys=True),
        encoding="utf-8",
    )
    return pack_root


def _resolver(pack_root: Path):
    from supervisor.pack_compiler import HarnessPackResolver

    return HarnessPackResolver({"knowledge-candidate-v1": pack_root})


def _ref(sha256: str):
    from contracts.spec import InstructionRef

    return InstructionRef(
        pack_id="knowledge-candidate-v1",
        version="1.0.0",
        sha256=sha256,
    )


def test_resolver_hash_locks_allowlisted_pack_and_rejects_drift(tmp_path: Path) -> None:
    from supervisor.pack_compiler import PackResolutionError

    pack_root = _write_pack(tmp_path)
    resolver = _resolver(pack_root)
    measured = resolver.measure("knowledge-candidate-v1")

    resolved = resolver.resolve(
        _ref(measured),
        adapter_id="opencode@1.18.14",
        image_ref=IMAGE_REF,
    )

    assert resolved.identity.sha256 == measured
    assert resolved.identity.pack_id == "knowledge-candidate-v1"
    assert resolved.manifest.skills[0].skill_id == "evidence-candidate"

    (pack_root / "instructions" / "system.md").write_text(
        "changed instruction\n",
        encoding="utf-8",
    )
    with pytest.raises(PackResolutionError, match="hash mismatch"):
        resolver.resolve(
            _ref(measured),
            adapter_id="opencode@1.18.14",
            image_ref=IMAGE_REF,
        )


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "command",
        "url",
        "environment",
        "secret",
        "network",
        "mount",
        "next_stage",
        "approve",
        "publish",
        "retry",
    ],
)
def test_manifest_rejects_transport_container_and_workflow_fields(
    tmp_path: Path,
    forbidden_field: str,
) -> None:
    from supervisor.pack_compiler import PackResolutionError

    pack_root = _write_pack(tmp_path, manifest_updates={forbidden_field: "forbidden"})

    with pytest.raises(PackResolutionError, match="manifest is invalid"):
        _resolver(pack_root).measure("knowledge-candidate-v1")


def test_manifest_rejects_duplicate_skills_and_path_escape(tmp_path: Path) -> None:
    from supervisor.pack_compiler import PackResolutionError

    duplicate_root = _write_pack(
        tmp_path / "duplicate",
        manifest_updates={
            "skills": [
                {"skill_id": "evidence-candidate", "path": "skills/evidence-candidate"},
                {"skill_id": "evidence-candidate", "path": "skills/evidence-candidate"},
            ]
        },
    )
    with pytest.raises(PackResolutionError, match="manifest is invalid"):
        _resolver(duplicate_root).measure("knowledge-candidate-v1")

    escaped_root = _write_pack(
        tmp_path / "escape",
        manifest_updates={"instruction_file": "../outside.md"},
    )
    with pytest.raises(PackResolutionError, match="manifest is invalid"):
        _resolver(escaped_root).measure("knowledge-candidate-v1")


def test_resolver_rejects_unknown_pack_and_identity_mismatches(tmp_path: Path) -> None:
    from supervisor.pack_compiler import HarnessPackResolver, PackResolutionError

    pack_root = _write_pack(tmp_path)
    resolver = _resolver(pack_root)
    measured = resolver.measure("knowledge-candidate-v1")

    with pytest.raises(PackResolutionError, match="not allowlisted"):
        HarnessPackResolver({}).measure("unknown-pack")
    with pytest.raises(PackResolutionError, match="version mismatch"):
        resolver.resolve(
            _ref(measured).model_copy(update={"version": "2.0.0"}),
            adapter_id="opencode@1.18.14",
            image_ref=IMAGE_REF,
        )
    with pytest.raises(PackResolutionError, match="adapter mismatch"):
        resolver.resolve(
            _ref(measured),
            adapter_id="other@1.0.0",
            image_ref=IMAGE_REF,
        )
    with pytest.raises(PackResolutionError, match="image mismatch"):
        resolver.resolve(
            _ref(measured),
            adapter_id="opencode@1.18.14",
            image_ref=IMAGE_REF.replace("b" * 64, "c" * 64),
        )


def test_resolver_rejects_missing_file_duplicate_mcp_and_symlink(tmp_path: Path) -> None:
    from supervisor.pack_compiler import PackResolutionError

    missing_root = _write_pack(tmp_path / "missing")
    (missing_root / "instructions" / "system.md").unlink()
    with pytest.raises(PackResolutionError, match="unavailable"):
        _resolver(missing_root).measure("knowledge-candidate-v1")

    duplicate_mcp_root = _write_pack(tmp_path / "duplicate-mcp")
    (duplicate_mcp_root / "mcp-policy.yaml").write_text(
        json.dumps(
            {
                "contract_version": "1.0.0",
                "capabilities": [
                    {
                        "capability_id": "knowledge.read-evidence",
                        "tools": ["read_evidence"],
                    },
                    {
                        "capability_id": "knowledge.read-evidence",
                        "tools": ["read_evidence"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(PackResolutionError, match="invalid"):
        _resolver(duplicate_mcp_root).measure("knowledge-candidate-v1")

    symlink_root = _write_pack(tmp_path / "symlink")
    instruction = symlink_root / "instructions" / "system.md"
    real_instruction = symlink_root / "instructions" / "real-system.md"
    instruction.rename(real_instruction)
    try:
        instruction.symlink_to(real_instruction)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    with pytest.raises(PackResolutionError, match="symlink"):
        _resolver(symlink_root).measure("knowledge-candidate-v1")


def test_compiler_materializes_only_pack_skills_and_trusted_mcp_binding(
    tmp_path: Path,
) -> None:
    from supervisor.pack_compiler import (
        HarnessPackCompiler,
        McpCapabilityBinding,
    )

    pack_root = _write_pack(tmp_path / "source")
    resolver = _resolver(pack_root)
    measured = resolver.measure("knowledge-candidate-v1")
    resolved = resolver.resolve(
        _ref(measured),
        adapter_id="opencode@1.18.14",
        image_ref=IMAGE_REF,
    )
    compiler = HarnessPackCompiler(
        {
            "knowledge.read-evidence": McpCapabilityBinding(
                capability_id="knowledge.read-evidence",
                server_name="clinical_attempt",
                tools=frozenset({"read_evidence"}),
                command=(
                    "/bin/sh",
                    "/harness/mcp_stdio_bridge.sh",
                    "/harness/mcp-bundle.json",
                    "/staging/mcp-audit.jsonl",
                ),
            )
        }
    )

    first = compiler.compile(resolved, tmp_path / "attempt-a")
    second = compiler.compile(resolved, tmp_path / "attempt-b")

    assert first.compiled_config_sha256 == second.compiled_config_sha256
    assert first.pack_identity == resolved.identity
    assert first.advertised_skills == ("evidence-candidate",)
    assert first.allowed_mcp_capabilities == ("knowledge.read-evidence",)
    assert (
        first.workspace_root
        / ".opencode"
        / "skills"
        / "evidence-candidate"
        / "SKILL.md"
    ).is_file()
    assert not (first.workspace_root / ".agents").exists()
    assert not (first.workspace_root / ".claude").exists()
    assert (first.workspace_root / "AGENTS.md").read_text(encoding="utf-8").startswith(
        "Generate one evidence-linked"
    )
    config = json.loads(first.opencode_config_path.read_text(encoding="utf-8"))
    assert config["permission"]["skill"] == {
        "*": "deny",
        "evidence-candidate": "allow",
    }
    assert config["mcp"]["clinical_attempt"]["command"][0:2] == [
        "/bin/sh",
        "/harness/mcp_stdio_bridge.sh",
    ]
    bundle = json.loads(first.mcp_bundle_path.read_text(encoding="utf-8"))
    assert bundle["allowed_tools"] == ["read_evidence"]
    serialized = json.dumps({"config": config, "bundle": bundle}, sort_keys=True)
    assert str(pack_root) not in serialized
    assert str(tmp_path) not in serialized


def test_compiler_rejects_pack_drift_after_resolution(tmp_path: Path) -> None:
    from supervisor.pack_compiler import (
        HarnessPackCompiler,
        McpCapabilityBinding,
        PackResolutionError,
    )

    pack_root = _write_pack(tmp_path / "source")
    resolver = _resolver(pack_root)
    measured = resolver.measure("knowledge-candidate-v1")
    resolved = resolver.resolve(
        _ref(measured),
        adapter_id="opencode@1.18.14",
        image_ref=IMAGE_REF,
    )
    (pack_root / "instructions" / "system.md").write_text(
        "drifted after resolution\n",
        encoding="utf-8",
    )
    compiler = HarnessPackCompiler(
        {
            "knowledge.read-evidence": McpCapabilityBinding(
                capability_id="knowledge.read-evidence",
                server_name="clinical_attempt",
                tools=frozenset({"read_evidence"}),
                command=("/bin/sh", "/harness/mcp_stdio_bridge.sh"),
            )
        }
    )

    with pytest.raises(PackResolutionError, match="hash mismatch"):
        compiler.compile(resolved, tmp_path / "attempt")


def test_supervisor_request_accepts_only_pack_ref_not_pack_content() -> None:
    from supervisor.service_contracts import SupervisorAttemptRequest

    body = {
        "attempt_id": "attempt-001",
        "run_id": "run-001",
        "step_id": "enrichment",
        "generation_token": "generation-001",
        "fencing_token": "fencing-001",
        "adapter_id": "opencode@1.18.14",
        "spec_sha256": "a" * 64,
        "input_sha256": "b" * 64,
        "input_bundle": {"provider": "synthetic", "model": "mock"},
        "instruction_ref": {
            "pack_id": "knowledge-candidate-v1",
            "version": "1.0.0",
            "sha256": "c" * 64,
        },
        "secret_refs": ["env://SYNTHETIC_PROVIDER_KEY"],
        "timeout_seconds": 60,
        "network_mode": "none",
    }

    request = SupervisorAttemptRequest.model_validate(body)
    assert request.instruction_ref is not None
    assert request.instruction_ref.pack_id == "knowledge-candidate-v1"

    for forbidden in ("skills", "opencode_config", "mcp_command", "mounts"):
        with pytest.raises(ValidationError):
            SupervisorAttemptRequest.model_validate({**body, forbidden: {}})


def test_execution_receipt_can_record_non_sensitive_pack_identity() -> None:
    from contracts.manifest import ArtifactManifest
    from contracts.receipt import ExecutionReceipt, ExitClassification
    from contracts.result import HarnessStatus

    receipt = ExecutionReceipt(
        execution_id="exec-001",
        spec_sha256="a" * 64,
        request_sha256="b" * 64,
        harness_id="opencode@1.18.14",
        adapter_id="opencode@1.18.14",
        status=HarnessStatus.SUCCEEDED,
        exit_classification=ExitClassification.SUCCEEDED,
        started_at="2026-08-11T00:00:00Z",
        ended_at="2026-08-11T00:00:01Z",
        artifact_manifest=ArtifactManifest(),
        pack_identity={
            "pack_id": "knowledge-candidate-v1",
            "version": "1.0.0",
            "sha256": "c" * 64,
        },
        compiled_config_sha256="d" * 64,
        advertised_skills=("evidence-candidate",),
        allowed_mcp_capabilities=("knowledge.read-evidence",),
    )

    serialized = receipt.model_dump_json()
    assert "knowledge-candidate-v1" in serialized
    assert "secret" not in serialized.lower()


def test_checked_in_knowledge_pack_is_valid_and_uses_admitted_image() -> None:
    from supervisor.pack_compiler import HarnessPackResolver

    pack_root = (
        PROJECT_ROOT
        / "clinical-llm-wiki"
        / "harness-packs"
        / "knowledge-candidate-v1"
    )
    admitted = json.loads(
        (
            PROJECT_ROOT
            / "harness-runtime"
            / "images"
            / "opencode-1.18.14.json"
        ).read_text(encoding="utf-8")
    )
    resolver = HarnessPackResolver({"knowledge-candidate-v1": pack_root})

    measured = resolver.measure("knowledge-candidate-v1")
    resolved = resolver.resolve(
        _ref(measured),
        adapter_id="opencode@1.18.14",
        image_ref=admitted["image_ref"],
    )

    assert resolved.manifest.image_ref == admitted["image_ref"]
    assert resolved.manifest.skills[0].skill_id == "evidence-candidate"
    assert resolved.mcp_policy.capabilities[0].capability_id == (
        "knowledge.read-evidence"
    )
