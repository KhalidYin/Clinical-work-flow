"""Versioned, product-owned Harness Pack contracts.

Packs describe instructions, discoverable skills, an output schema and logical
MCP capabilities.  They deliberately cannot carry transport, container,
network, secret or workflow-transition configuration.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .request import StrictContractModel


def _safe_relative_path(value: str) -> str:
    if "\\" in value:
        raise ValueError("path must use POSIX separators")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError("path must remain inside the Pack")
    return value


class HarnessPackIdentity(StrictContractModel):
    pack_id: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    version: str = Field(min_length=1, max_length=100)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class HarnessPackSkill(StrictContractModel):
    skill_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*$")
    path: str

    _validate_path = field_validator("path")(_safe_relative_path)


class HarnessPackModelPolicy(StrictContractModel):
    protocol: Literal["openai-compatible"]
    structured_output: Literal[True]


class HarnessPackBudgetPolicy(StrictContractModel):
    max_calls: int = Field(ge=1)
    max_tokens: int = Field(ge=1)
    max_time_seconds: int = Field(ge=1, le=3600)


class HarnessPackManifest(StrictContractModel):
    contract_version: Literal["1.0.0"] = "1.0.0"
    pack_id: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    version: str = Field(min_length=1, max_length=100)
    adapter_id: Literal["opencode@1.18.14"]
    image_ref: str = Field(
        pattern=r"^[a-z0-9][a-z0-9._/:-]*:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}$"
    )
    instruction_file: str
    skills: tuple[HarnessPackSkill, ...] = ()
    mcp_policy_file: str
    output_schema_file: str
    model: HarnessPackModelPolicy
    budget: HarnessPackBudgetPolicy

    _validate_instruction_path = field_validator("instruction_file")(_safe_relative_path)
    _validate_mcp_path = field_validator("mcp_policy_file")(_safe_relative_path)
    _validate_schema_path = field_validator("output_schema_file")(_safe_relative_path)

    @model_validator(mode="after")
    def skills_must_be_unique(self) -> "HarnessPackManifest":
        skill_ids = [skill.skill_id for skill in self.skills]
        skill_paths = [skill.path for skill in self.skills]
        if len(skill_ids) != len(set(skill_ids)) or len(skill_paths) != len(set(skill_paths)):
            raise ValueError("skill ids and paths must be unique")
        return self


class HarnessPackMcpCapability(StrictContractModel):
    capability_id: str = Field(min_length=1, max_length=200)
    tools: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def tools_must_be_unique(self) -> "HarnessPackMcpCapability":
        if len(self.tools) != len(set(self.tools)):
            raise ValueError("MCP tools must be unique")
        return self


class HarnessPackMcpPolicy(StrictContractModel):
    contract_version: Literal["1.0.0"] = "1.0.0"
    capabilities: tuple[HarnessPackMcpCapability, ...] = ()

    @model_validator(mode="after")
    def capabilities_must_be_unique(self) -> "HarnessPackMcpPolicy":
        ids = [capability.capability_id for capability in self.capabilities]
        if len(ids) != len(set(ids)):
            raise ValueError("MCP capability ids must be unique")
        return self


__all__ = [
    "HarnessPackBudgetPolicy",
    "HarnessPackIdentity",
    "HarnessPackManifest",
    "HarnessPackMcpCapability",
    "HarnessPackMcpPolicy",
    "HarnessPackModelPolicy",
    "HarnessPackSkill",
]
