"""Machine-readable contract for the fixed clinical workflow pipeline.

The contract is owned by the Workflow Engine.  Knowledge content may explain how
to execute a stage, but it cannot add, remove, skip, or reorder pipeline stages.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CONTRACT_VERSION = "1.0.0"
SEMVER_PATTERN = (
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
ContractVersion = Annotated[str, Field(pattern=SEMVER_PATTERN)]


class PipelineContractError(ValueError):
    """Raised when a pipeline contract violates the canonical pipeline."""


class PipelineStage(StrEnum):
    PROTOCOL_ANALYSIS = "protocol_analysis"
    SAP_GENERATION = "sap_generation"
    SDTM_SPEC = "sdtm_spec"
    SDTM_PROGRAMMING = "sdtm_programming"
    ADAM_SPEC = "adam_spec"
    ADAM_PROGRAMMING = "adam_programming"
    TFL_SHELL_DESIGN = "tfl_shell_design"
    TFL_PROGRAMMING = "tfl_programming"
    QC_VALIDATION = "qc_validation"
    SUBMISSION_PACKAGING = "submission_packaging"


class ExecutorName(StrEnum):
    PROTOCOL_SAP = "ProtocolSAPAgent"
    DATA_STANDARDS = "DataStandardsAgent"
    TFL_QC_SUBMISSION = "TFLQCSubmissionAgent"


class CapabilityName(StrEnum):
    PROTOCOL_ANALYSIS = "protocol_analysis"
    ENDPOINT_CLASSIFICATION = "endpoint_classification"
    ESTIMANDS_DERIVATION = "estimands_derivation"
    SAP_GENERATION = "sap_generation"
    SDTM_SPEC_GENERATION = "sdtm_spec_generation"
    SDTM_PROGRAMMING = "sdtm_programming"
    ADAM_SPEC_GENERATION = "adam_spec_generation"
    ADAM_PROGRAMMING = "adam_programming"
    CT_ALIGNMENT = "ct_alignment"
    CDISC_VALIDATION = "cdisc_validation"
    TFL_SHELL_GENERATION = "tfl_shell_generation"
    TFL_PROGRAMMING = "tfl_programming"
    QC_VALIDATION = "qc_validation"
    P21_TRIAGE = "p21_triage"
    DEFINE_XML_GENERATION = "define_xml_generation"
    SUBMISSION_PACKAGING = "submission_packaging"
    SOURCE_DISCOVERY = "source_discovery"
    SOURCE_DATA_IMPORT = "source_data_import"


class ToolName(StrEnum):
    SDTM_SPEC_BUILD = "sdtm_spec_build"
    ADAM_SPEC_BUILD = "adam_spec_build"
    TFL_SHELLS_LIST = "tfl_shells_list"
    CDISC_VALIDATE = "cdisc_validate"
    DEFINE_XML_BUILD = "define_xml_build"
    TRIAGE_P21 = "triage_p21"
    EDC_IMPORT = "edc_import"
    CTGOV_SEARCH = "ctgov_search"
    CTGOV_STUDY_DETAIL = "ctgov_study_detail"
    CTGOV_DOWNLOAD_DOCS = "ctgov_download_docs"
    CTGOV_CHECK_DOCS = "ctgov_check_docs"


class ExecutableName(StrEnum):
    PROTOCOL_DOCUMENT_PARSER = "protocol_document_parser"
    SAP_DOCUMENT_GENERATOR = "sap_document_generator"
    SDTM_PROGRAM_RUNNER = "sdtm_program_runner"
    ADAM_PROGRAM_RUNNER = "adam_program_runner"
    TFL_RENDERER = "tfl_renderer"
    QC_COMPARATOR = "qc_comparator"
    SUBMISSION_PACKAGER = "submission_packager"


class ArtifactName(StrEnum):
    PROTOCOL_DOCUMENT = "protocol_document"
    STUDY_FACTS = "study_facts"
    PROTOCOL_ANALYSIS = "protocol_analysis"
    SAP = "sap"
    CRF_METADATA = "crf_metadata"
    EDC_METADATA = "edc_metadata"
    SDTM_SPECS = "sdtm_specs"
    APPROVED_SDTM_SPECS = "approved_sdtm_specs"
    SDTM_PROGRAMS = "sdtm_programs"
    SDTM_DATASETS = "sdtm_datasets"
    ADAM_SPECS = "adam_specs"
    APPROVED_ADAM_SPECS = "approved_adam_specs"
    ADAM_PROGRAMS = "adam_programs"
    ADAM_DATASETS = "adam_datasets"
    TFL_SHELLS = "tfl_shells"
    APPROVED_TFL_SHELLS = "approved_tfl_shells"
    TFL_PROGRAMS = "tfl_programs"
    TFL_OUTPUTS = "tfl_outputs"
    ALL_WORK_PRODUCTS = "all_work_products"
    APPROVED_OUTPUTS = "approved_outputs"
    QC_REPORT = "qc_report"
    QC_EVIDENCE = "qc_evidence"
    SUBMISSION_MANIFEST = "submission_manifest"
    SUBMISSION_PACKAGE = "submission_package"


class StrictContractModel(BaseModel):
    """Base model for contracts that fail closed on undeclared fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class StageContract(StrictContractModel):
    ordinal: int = Field(ge=1, le=10)
    stage_id: PipelineStage
    display_name: str = Field(min_length=1)
    executor: ExecutorName
    depends_on: tuple[PipelineStage, ...] = ()
    required_inputs: tuple[ArtifactName, ...] = Field(min_length=1)
    canonical_outputs: tuple[ArtifactName, ...] = Field(min_length=1)
    completion_evidence: tuple[str, ...] = Field(min_length=1)
    allowed_capabilities: tuple[CapabilityName, ...] = Field(min_length=1)
    allowed_tools: tuple[ToolName, ...] = ()
    allowed_executables: tuple[ExecutableName, ...] = ()

    @field_validator(
        "depends_on",
        "required_inputs",
        "canonical_outputs",
        "completion_evidence",
        "allowed_capabilities",
        "allowed_tools",
        "allowed_executables",
    )
    @classmethod
    def reject_duplicates(cls, value: tuple[object, ...]) -> tuple[object, ...]:
        if len(value) != len(set(value)):
            raise ValueError("contract lists must not contain duplicate values")
        return value

    @field_validator("completion_evidence")
    @classmethod
    def validate_completion_evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for path in value:
            if not path.startswith("output/") or ".." in path or "\\" in path:
                raise ValueError("completion evidence must be a safe canonical output path")
            if path in {"output/programs", "output/programs/"}:
                raise ValueError("generic programs path is not canonical completion evidence")
        return value


class PipelineContract(StrictContractModel):
    contract_version: ContractVersion
    stages: tuple[StageContract, ...] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def validate_canonical_sequence(self) -> "PipelineContract":
        expected_stages = tuple(PipelineStage)
        actual_stages = tuple(stage.stage_id for stage in self.stages)
        if actual_stages != expected_stages:
            raise ValueError(
                "stages must use the canonical ten-stage order: "
                + ", ".join(expected_stages)
            )

        for index, stage in enumerate(self.stages, start=1):
            if stage.ordinal != index:
                raise ValueError(f"{stage.stage_id} must have ordinal {index}")
            expected_dependency = () if index == 1 else (expected_stages[index - 2],)
            if stage.depends_on != expected_dependency:
                raise ValueError(
                    f"{stage.stage_id} must depend on "
                    f"{[item.value for item in expected_dependency]}"
                )
        return self

    def get_stage(self, stage_id: PipelineStage | str) -> StageContract:
        try:
            canonical_id = PipelineStage(stage_id)
        except ValueError as exc:
            raise PipelineContractError(f"Unknown pipeline stage: {stage_id}") from exc
        return self.stages[tuple(PipelineStage).index(canonical_id)]

    def next_stage(self, stage_id: PipelineStage | str) -> PipelineStage | None:
        stage = self.get_stage(stage_id)
        if stage.ordinal == len(self.stages):
            return None
        return self.stages[stage.ordinal].stage_id


def _stage(
    ordinal: int,
    stage_id: PipelineStage,
    display_name: str,
    executor: ExecutorName,
    required_inputs: tuple[ArtifactName, ...],
    canonical_outputs: tuple[ArtifactName, ...],
    completion_evidence: tuple[str, ...],
    allowed_capabilities: tuple[CapabilityName, ...],
    *,
    allowed_tools: tuple[ToolName, ...] = (),
    allowed_executables: tuple[ExecutableName, ...] = (),
) -> StageContract:
    dependency = () if ordinal == 1 else (tuple(PipelineStage)[ordinal - 2],)
    return StageContract(
        ordinal=ordinal,
        stage_id=stage_id,
        display_name=display_name,
        executor=executor,
        depends_on=dependency,
        required_inputs=required_inputs,
        canonical_outputs=canonical_outputs,
        completion_evidence=completion_evidence,
        allowed_capabilities=allowed_capabilities,
        allowed_tools=allowed_tools,
        allowed_executables=allowed_executables,
    )


CANONICAL_PIPELINE = PipelineContract(
    contract_version=CONTRACT_VERSION,
    stages=(
        _stage(
            1,
            PipelineStage.PROTOCOL_ANALYSIS,
            "Protocol Analysis",
            ExecutorName.PROTOCOL_SAP,
            (ArtifactName.PROTOCOL_DOCUMENT, ArtifactName.STUDY_FACTS),
            (ArtifactName.PROTOCOL_ANALYSIS,),
            ("output/protocol/analysis.yaml",),
            (
                CapabilityName.PROTOCOL_ANALYSIS,
                CapabilityName.ENDPOINT_CLASSIFICATION,
                CapabilityName.ESTIMANDS_DERIVATION,
                CapabilityName.SOURCE_DISCOVERY,
            ),
            allowed_tools=(
                ToolName.CTGOV_SEARCH,
                ToolName.CTGOV_STUDY_DETAIL,
                ToolName.CTGOV_DOWNLOAD_DOCS,
                ToolName.CTGOV_CHECK_DOCS,
            ),
            allowed_executables=(ExecutableName.PROTOCOL_DOCUMENT_PARSER,),
        ),
        _stage(
            2,
            PipelineStage.SAP_GENERATION,
            "SAP Generation",
            ExecutorName.PROTOCOL_SAP,
            (ArtifactName.PROTOCOL_ANALYSIS, ArtifactName.PROTOCOL_DOCUMENT),
            (ArtifactName.SAP,),
            ("output/sap/sap.yaml",),
            (CapabilityName.SAP_GENERATION,),
            allowed_executables=(ExecutableName.SAP_DOCUMENT_GENERATOR,),
        ),
        _stage(
            3,
            PipelineStage.SDTM_SPEC,
            "SDTM Spec",
            ExecutorName.DATA_STANDARDS,
            (ArtifactName.SAP, ArtifactName.CRF_METADATA, ArtifactName.EDC_METADATA),
            (ArtifactName.SDTM_SPECS,),
            ("output/sdtm/specs/",),
            (
                CapabilityName.SDTM_SPEC_GENERATION,
                CapabilityName.CT_ALIGNMENT,
                CapabilityName.CDISC_VALIDATION,
                CapabilityName.SOURCE_DATA_IMPORT,
            ),
            allowed_tools=(
                ToolName.SDTM_SPEC_BUILD,
                ToolName.CDISC_VALIDATE,
                ToolName.EDC_IMPORT,
            ),
        ),
        _stage(
            4,
            PipelineStage.SDTM_PROGRAMMING,
            "SDTM Programming",
            ExecutorName.DATA_STANDARDS,
            (ArtifactName.APPROVED_SDTM_SPECS, ArtifactName.EDC_METADATA),
            (ArtifactName.SDTM_PROGRAMS, ArtifactName.SDTM_DATASETS),
            ("output/sdtm/programs/", "output/sdtm/datasets/"),
            (
                CapabilityName.SDTM_PROGRAMMING,
                CapabilityName.CDISC_VALIDATION,
                CapabilityName.SOURCE_DATA_IMPORT,
            ),
            allowed_tools=(ToolName.CDISC_VALIDATE, ToolName.EDC_IMPORT),
            allowed_executables=(ExecutableName.SDTM_PROGRAM_RUNNER,),
        ),
        _stage(
            5,
            PipelineStage.ADAM_SPEC,
            "ADaM Spec",
            ExecutorName.DATA_STANDARDS,
            (ArtifactName.SAP, ArtifactName.SDTM_SPECS, ArtifactName.SDTM_DATASETS),
            (ArtifactName.ADAM_SPECS,),
            ("output/adam/specs/",),
            (CapabilityName.ADAM_SPEC_GENERATION, CapabilityName.CDISC_VALIDATION),
            allowed_tools=(ToolName.ADAM_SPEC_BUILD, ToolName.CDISC_VALIDATE),
        ),
        _stage(
            6,
            PipelineStage.ADAM_PROGRAMMING,
            "ADaM Programming",
            ExecutorName.DATA_STANDARDS,
            (ArtifactName.APPROVED_ADAM_SPECS, ArtifactName.SDTM_DATASETS),
            (ArtifactName.ADAM_PROGRAMS, ArtifactName.ADAM_DATASETS),
            ("output/adam/programs/", "output/adam/datasets/"),
            (CapabilityName.ADAM_PROGRAMMING, CapabilityName.CDISC_VALIDATION),
            allowed_tools=(ToolName.CDISC_VALIDATE,),
            allowed_executables=(ExecutableName.ADAM_PROGRAM_RUNNER,),
        ),
        _stage(
            7,
            PipelineStage.TFL_SHELL_DESIGN,
            "TFL Shell Design",
            ExecutorName.TFL_QC_SUBMISSION,
            (ArtifactName.SAP, ArtifactName.ADAM_SPECS),
            (ArtifactName.TFL_SHELLS,),
            ("output/tfl/shells/",),
            (CapabilityName.TFL_SHELL_GENERATION,),
            allowed_tools=(ToolName.TFL_SHELLS_LIST,),
        ),
        _stage(
            8,
            PipelineStage.TFL_PROGRAMMING,
            "TFL Programming",
            ExecutorName.TFL_QC_SUBMISSION,
            (ArtifactName.APPROVED_TFL_SHELLS, ArtifactName.ADAM_DATASETS),
            (ArtifactName.TFL_PROGRAMS, ArtifactName.TFL_OUTPUTS),
            ("output/tfl/programs/", "output/tfl/outputs/"),
            (CapabilityName.TFL_PROGRAMMING,),
            allowed_executables=(ExecutableName.TFL_RENDERER,),
        ),
        _stage(
            9,
            PipelineStage.QC_VALIDATION,
            "QC Validation",
            ExecutorName.TFL_QC_SUBMISSION,
            (ArtifactName.ALL_WORK_PRODUCTS,),
            (ArtifactName.QC_REPORT,),
            ("output/qc/qc_report.yaml",),
            (
                CapabilityName.QC_VALIDATION,
                CapabilityName.CDISC_VALIDATION,
                CapabilityName.P21_TRIAGE,
            ),
            allowed_tools=(ToolName.CDISC_VALIDATE, ToolName.TRIAGE_P21),
            allowed_executables=(ExecutableName.QC_COMPARATOR,),
        ),
        _stage(
            10,
            PipelineStage.SUBMISSION_PACKAGING,
            "Submission Packaging",
            ExecutorName.TFL_QC_SUBMISSION,
            (ArtifactName.APPROVED_OUTPUTS, ArtifactName.QC_EVIDENCE),
            (ArtifactName.SUBMISSION_MANIFEST, ArtifactName.SUBMISSION_PACKAGE),
            ("output/submission/manifest.yaml", "output/submission/package/"),
            (
                CapabilityName.DEFINE_XML_GENERATION,
                CapabilityName.SUBMISSION_PACKAGING,
            ),
            allowed_tools=(ToolName.DEFINE_XML_BUILD,),
            allowed_executables=(ExecutableName.SUBMISSION_PACKAGER,),
        ),
    ),
)


def parse_semver(version: str) -> tuple[int, int, int]:
    """Return the numeric SemVer core, rejecting non-SemVer input."""
    match = re.fullmatch(SEMVER_PATTERN, version)
    if match is None:
        raise PipelineContractError(f"Invalid SemVer contract version: {version}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def assert_compatible_contract_version(required: str, actual: str) -> None:
    """Fail closed unless actual has the same major and meets the required version."""
    required_core = parse_semver(required)
    actual_core = parse_semver(actual)
    if required_core[0] != actual_core[0] or actual_core < required_core:
        raise PipelineContractError(
            f"Incompatible contract version: required {required}, received {actual}"
        )
