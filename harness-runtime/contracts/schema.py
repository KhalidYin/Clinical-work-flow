"""H0-B JSON Schema export for the harness runtime contract.

Same style as ``processing_runtime_contract_json_schema`` in the knowledge
product: code and schema stay in sync via ``TypeAdapter.json_schema`` and
are exported with a stable ``$id`` so versions/hashes can be locked.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter

from .manifest import ArtifactManifest
from .receipt import ExecutionReceipt, ValidationReceipt
from .request import HarnessExecutionRequest
from .result import HarnessEvent, HarnessResult
from .spec import StepExecutionSpec

_CONTRACT_TYPES = (
    StepExecutionSpec
    | HarnessExecutionRequest
    | HarnessEvent
    | HarnessResult
    | ExecutionReceipt
    | ValidationReceipt
    | ArtifactManifest
)


def harness_contract_json_schema() -> dict[str, Any]:
    schema = TypeAdapter(_CONTRACT_TYPES).json_schema(
        ref_template="#/$defs/{model}"
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://clinical.example/schemas/harness-runtime.v1.schema.json",
        "title": "H0 Harness Runtime Contract",
        **schema,
    }


def harness_contract_schema_sha256() -> str:
    """Stable lock for the exported contract (JSON-text SHA-256)."""
    import hashlib

    return hashlib.sha256(
        json.dumps(harness_contract_json_schema(), sort_keys=True).encode("utf-8")
    ).hexdigest()


__all__ = [
    "harness_contract_json_schema",
    "harness_contract_schema_sha256",
]
