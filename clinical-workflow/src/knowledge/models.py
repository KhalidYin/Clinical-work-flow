"""Strict, executable contracts for governed clinical knowledge.

The models in this module are shared by the engine, the Wiki service, and Study
fixtures.  They intentionally reject unknown fields: a typo in governance
metadata must never be interpreted as an approved production rule.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
StableId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)+$", min_length=3),
]
KnowledgeItemId = Annotated[
    str,
    StringConstraints(pattern=r"^(?:kn|kr|pattern|precedent)-[a-z0-9]+(?:-[a-z0-9]+)*$"),
]
PlaybookId = Annotated[
    str, StringConstraints(pattern=r"^wp-[a-z0-9]+(?:-[a-z0-9]+)*$")
]
SourceId = Annotated[
    str, StringConstraints(pattern=r"^src-[a-z0-9]+(?:-[a-z0-9]+)*$")
]
FigureId = Annotated[
    str, StringConstraints(pattern=r"^fig-[a-z0-9]+(?:-[a-z0-9]+)*$")
]
ManifestId = Annotated[
    str, StringConstraints(pattern=r"^manifest-[a-z0-9]+(?:-[a-z0-9]+)*$")
]
ContextId = Annotated[
    str, StringConstraints(pattern=r"^ctx-[a-z0-9]+(?:-[a-z0-9]+)*$")
]
SemVerString = Annotated[
    str,
    StringConstraints(
        pattern=(
            r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
            r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
            r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
        )
    ),
]
NonEmptyString = Annotated[str, StringConstraints(min_length=1)]


class StrictContractModel(BaseModel):
    """Base class for every cross-repository contract."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        use_enum_values=False,
    )


class ContentStatus(StrEnum):
    INBOX = "inbox"
    DRAFT = "draft"
    REVIEWED = "reviewed"
    VERIFIED = "verified"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ApprovalStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class KnowledgeType(StrEnum):
    CONCEPT = "concept"
    METHOD = "method"
    STANDARD_RULE = "standard_rule"
    DECISION_RULE = "decision_rule"
    WORKFLOW_PLAYBOOK = "workflow_playbook"
    PROGRAMMING_PATTERN = "programming_pattern"
    DELIVERABLE_PATTERN = "deliverable_pattern"
    PRIOR_STUDY_PATTERN = "prior_study_pattern"
    SOURCE_RECORD = "source_record"
    FIGURE_RECORD = "figure_record"


class WorkflowStage(StrEnum):
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


class CapabilityId(StrEnum):
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


class Authority(StrEnum):
    REGULATORY = "regulatory"
    INDUSTRY_STANDARD = "industry_standard"
    COMPANY_SOP = "company_sop"
    DOMAIN_EXPERT = "domain_expert"
    APPROVED_PRECEDENT = "approved_precedent"
    STUDY_DECISION = "study_decision"
    AI_INFERENCE = "ai_inference"


class RightsStatus(StrEnum):
    CLEARED = "cleared"
    RESTRICTED = "restricted"
    PROHIBITED = "prohibited"
    UNKNOWN = "unknown"


class StorageMode(StrEnum):
    COMMITTED = "committed"
    LOCAL_ONLY = "local_only"
    LINK_ONLY = "link_only"
    UNKNOWN = "unknown"


class PdfStatus(StrEnum):
    QUARANTINE = "quarantine"
    INTEGRITY_VERIFIED = "integrity_verified"
    RIGHTS_CLEARED = "rights_cleared"
    PARSED = "parsed"
    MACHINE_QA = "machine_qa"
    HUMAN_QA = "human_qa"
    CITATION_READY = "citation_ready"


_CONTENT_TRANSITIONS: dict[ContentStatus, frozenset[ContentStatus]] = {
    ContentStatus.INBOX: frozenset({ContentStatus.DRAFT, ContentStatus.ARCHIVED}),
    ContentStatus.DRAFT: frozenset({ContentStatus.REVIEWED, ContentStatus.ARCHIVED}),
    ContentStatus.REVIEWED: frozenset(
        {ContentStatus.DRAFT, ContentStatus.VERIFIED, ContentStatus.ARCHIVED}
    ),
    ContentStatus.VERIFIED: frozenset({ContentStatus.DEPRECATED, ContentStatus.ARCHIVED}),
    ContentStatus.DEPRECATED: frozenset({ContentStatus.ARCHIVED}),
    ContentStatus.ARCHIVED: frozenset(),
}
_APPROVAL_TRANSITIONS: dict[ApprovalStatus, frozenset[ApprovalStatus]] = {
    ApprovalStatus.PROPOSED: frozenset({ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}),
    ApprovalStatus.APPROVED: frozenset({ApprovalStatus.SUPERSEDED}),
    ApprovalStatus.REJECTED: frozenset({ApprovalStatus.PROPOSED}),
    ApprovalStatus.SUPERSEDED: frozenset(),
}
_PDF_STATUS_SEQUENCE = tuple(PdfStatus)


def is_content_status_transition_allowed(
    current: ContentStatus, target: ContentStatus
) -> bool:
    return current == target or target in _CONTENT_TRANSITIONS[current]


def is_approval_status_transition_allowed(
    current: ApprovalStatus, target: ApprovalStatus
) -> bool:
    return current == target or target in _APPROVAL_TRANSITIONS[current]


def is_pdf_status_transition_allowed(current: PdfStatus, target: PdfStatus) -> bool:
    current_index = _PDF_STATUS_SEQUENCE.index(current)
    target_index = _PDF_STATUS_SEQUENCE.index(target)
    return target_index in {current_index, current_index + 1}


class RuleLayer(StrEnum):
    WORKFLOW = "workflow"
    DOMAIN = "domain"
    STUDY = "study"


class CompatibilityRange(StrictContractModel):
    """Half-open SemVer range: minimum <= version < maximum_exclusive."""

    minimum: SemVerString
    maximum_exclusive: SemVerString

    @model_validator(mode="after")
    def ordered(self) -> Self:
        from .compatibility import parse_semver

        if parse_semver(self.minimum) >= parse_semver(self.maximum_exclusive):
            raise ValueError("minimum must be lower than maximum_exclusive")
        return self


class Applicability(StrictContractModel):
    therapeutic_areas: tuple[NonEmptyString, ...] = ()
    trial_phases: tuple[NonEmptyString, ...] = ()
    sponsor_ids: tuple[NonEmptyString, ...] = ()
    study_ids: tuple[NonEmptyString, ...] = ()
    conditions: tuple[NonEmptyString, ...] = ()


class EvidenceLocator(StrictContractModel):
    physical_page: int = Field(ge=1)
    printed_page: NonEmptyString | None = None
    bbox: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def valid_bbox(self) -> Self:
        if self.bbox is not None:
            x0, y0, x1, y1 = self.bbox
            if min(self.bbox) < 0 or x1 <= x0 or y1 <= y0:
                raise ValueError("bbox must be non-negative and ordered as x0,y0,x1,y1")
        return self


class DerivationRecord(StrictContractModel):
    derivation_id: StableId
    tool: NonEmptyString
    tool_version: NonEmptyString
    input_sha256: Sha256
    output_sha256: Sha256
    parameters_sha256: Sha256
    created_at: datetime


class EligibilityDecision(StrictContractModel):
    eligible: bool
    reasons: tuple[str, ...]


class GovernedRecord(StrictContractModel):
    """Public minimum metadata shared by Wiki-governed records."""

    id: StableId
    type: KnowledgeType
    title: NonEmptyString
    version: SemVerString
    schema_version: SemVerString = "1.0.0"
    content_status: ContentStatus
    approval_status: ApprovalStatus
    domains: tuple[NonEmptyString, ...] = ()
    workflow_stages: tuple[WorkflowStage, ...] = ()
    topics: tuple[NonEmptyString, ...] = ()
    aliases: tuple[NonEmptyString, ...] = ()
    authority: Authority
    applicability: Applicability
    sources: tuple[StableId, ...] = ()
    owner: NonEmptyString
    created: datetime
    last_reviewed: date | None = None
    review_due: date | None = None
    supersedes: tuple[StableId, ...] = ()
    superseded_by: StableId | None = None
    content_hash: Sha256
    rights_status: RightsStatus
    allowed_uses: tuple[NonEmptyString, ...] = ()
    storage_mode: StorageMode
    contract_compatibility: CompatibilityRange
    approval_receipt_id: StableId | None = None
    audit_reference: NonEmptyString | None = None

    @model_validator(mode="after")
    def governance_is_coherent(self) -> Self:
        if self.approval_status is ApprovalStatus.SUPERSEDED and not self.superseded_by:
            raise ValueError("superseded records require superseded_by")
        if self.approval_status is ApprovalStatus.APPROVED and not self.approval_receipt_id:
            raise ValueError("approved records require approval_receipt_id")
        return self

    def production_eligibility(
        self,
        *,
        contract_version: str,
        use: str = "runtime",
        as_of: date | None = None,
    ) -> EligibilityDecision:
        """Return all fail-closed reasons that prevent production resolution."""

        from .compatibility import is_version_compatible

        today = as_of or datetime.now(timezone.utc).date()
        reasons: list[str] = []
        if self.content_status is not ContentStatus.VERIFIED:
            reasons.append("content_not_verified")
        if self.approval_status is not ApprovalStatus.APPROVED:
            reasons.append("use_not_approved")
        if not self.approval_receipt_id or not self.audit_reference:
            reasons.append("approval_evidence_missing")
        if self.rights_status is RightsStatus.CLEARED:
            pass
        elif self.rights_status is RightsStatus.RESTRICTED and use in self.allowed_uses:
            pass
        else:
            reasons.append("rights_not_cleared_for_use")
        if self.storage_mode is StorageMode.UNKNOWN:
            reasons.append("storage_mode_unknown")
        if self.review_due is None:
            reasons.append("review_due_missing")
        elif self.review_due < today:
            reasons.append("review_overdue")
        if self.superseded_by or self.approval_status is ApprovalStatus.SUPERSEDED:
            reasons.append("record_superseded")
        if not is_version_compatible(contract_version, self.contract_compatibility):
            reasons.append("contract_incompatible")
        return EligibilityDecision(eligible=not reasons, reasons=tuple(reasons))


class RuleStatement(StrictContractModel):
    rule_id: StableId
    statement: NonEmptyString
    rationale: NonEmptyString
    evidence_refs: tuple[StableId, ...] = Field(min_length=1)


class KnowledgeItem(GovernedRecord):
    id: KnowledgeItemId
    type: Literal[
        KnowledgeType.CONCEPT,
        KnowledgeType.METHOD,
        KnowledgeType.STANDARD_RULE,
        KnowledgeType.DECISION_RULE,
        KnowledgeType.PROGRAMMING_PATTERN,
        KnowledgeType.DELIVERABLE_PATTERN,
        KnowledgeType.PRIOR_STUDY_PATTERN,
    ]
    summary: NonEmptyString
    statements: tuple[RuleStatement, ...] = Field(min_length=1)


class PlaybookStep(StrictContractModel):
    step_id: StableId
    objective: NonEmptyString
    rationale: NonEmptyString
    evidence_required: tuple[NonEmptyString, ...] = ()
    expected_outcome: NonEmptyString


class WorkflowPlaybook(GovernedRecord):
    """Descriptive workflow knowledge; never an executable instruction object."""

    id: PlaybookId
    type: Literal[KnowledgeType.WORKFLOW_PLAYBOOK]
    stage: WorkflowStage
    purpose: NonEmptyString
    prerequisites: tuple[NonEmptyString, ...] = ()
    steps: tuple[PlaybookStep, ...] = Field(min_length=1)
    expected_inputs: tuple[NonEmptyString, ...] = ()
    expected_outputs: tuple[NonEmptyString, ...] = ()
    decision_points: tuple[NonEmptyString, ...] = ()
    review_requirements: tuple[NonEmptyString, ...] = ()
    capability_hints: tuple[CapabilityId, ...] = ()

    @model_validator(mode="after")
    def stage_is_declared(self) -> Self:
        if self.stage not in self.workflow_stages:
            raise ValueError("playbook stage must be present in workflow_stages")
        return self


class SourceRecord(GovernedRecord):
    id: SourceId
    type: Literal[KnowledgeType.SOURCE_RECORD]
    source_kind: Literal["pdf", "document", "web", "dataset", "other"]
    source_version: NonEmptyString
    original_uri: NonEmptyString
    original_sha256: Sha256
    pdf_status: PdfStatus | None = None
    page_count: int | None = Field(default=None, ge=1)
    locators: tuple[EvidenceLocator, ...] = ()
    derivations: tuple[DerivationRecord, ...] = ()
    license: NonEmptyString | None = None

    @model_validator(mode="after")
    def pdf_metadata_is_complete(self) -> Self:
        if self.source_kind == "pdf" and (self.pdf_status is None or self.page_count is None):
            raise ValueError("PDF sources require pdf_status and page_count")
        if self.source_kind != "pdf" and self.pdf_status is not None:
            raise ValueError("pdf_status is only valid for PDF sources")
        return self

    def production_eligibility(self, **kwargs: object) -> EligibilityDecision:
        base = super().production_eligibility(**kwargs)  # type: ignore[arg-type]
        reasons = list(base.reasons)
        if self.source_kind == "pdf" and self.pdf_status is not PdfStatus.CITATION_READY:
            reasons.append("pdf_not_citation_ready")
        return EligibilityDecision(eligible=not reasons, reasons=tuple(reasons))


class FigureRecord(GovernedRecord):
    id: FigureId
    type: Literal[KnowledgeType.FIGURE_RECORD]
    source_id: StableId
    source_sha256: Sha256
    figure_sha256: Sha256
    locator: EvidenceLocator
    caption: NonEmptyString
    derivation: DerivationRecord


class ArtifactLock(StrictContractModel):
    artifact_id: StableId
    version: SemVerString
    sha256: Sha256


class KnowledgeSnapshotLock(StrictContractModel):
    provider: NonEmptyString
    snapshot_id: StableId
    version: SemVerString
    sha256: Sha256
    fallback_path: NonEmptyString
    contract_compatibility: CompatibilityRange


class ToolchainLock(StrictContractModel):
    registry_version: SemVerString
    git_commit: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{7,40}$")]
    registry_sha256: Sha256
    capabilities: tuple[CapabilityId, ...]


class RuntimePolicies(StrictContractModel):
    live_upgrade: Literal["forbidden"] = "forbidden"
    conflict: Literal["fail_closed"] = "fail_closed"
    version: Literal["exact_manifest"] = "exact_manifest"
    fallback: Literal["locked_snapshot_only"] = "locked_snapshot_only"


class RuntimeManifest(StrictContractModel):
    manifest_id: ManifestId
    schema_version: SemVerString
    revision: int = Field(ge=1)
    study_id: NonEmptyString
    created_at: datetime
    pipeline_contract: ArtifactLock
    workflow_knowledge: KnowledgeSnapshotLock
    domain_knowledge: KnowledgeSnapshotLock
    toolchain: ToolchainLock
    policies: RuntimePolicies
    manifest_sha256: Sha256


class TEAEWindowRule(StrictContractModel):
    """Machine-executable treatment-emergent adverse-event window."""

    rule_type: Literal["teae_window"] = "teae_window"
    target_dataset: Literal["ADAE"] = "ADAE"
    target_variable: Literal["TRTEMFL"] = "TRTEMFL"
    event_start_date: Literal["ADAE.ASTDT"] = "ADAE.ASTDT"
    treatment_start_date: Literal["ADSL.TRTSDT"] = "ADSL.TRTSDT"
    treatment_end_date: Literal["ADSL.TRTEDT"] = "ADSL.TRTEDT"
    start_offset_days: int = Field(default=0, ge=-365, le=365)
    end_offset_days: int = Field(ge=0, le=365)
    lower_bound_inclusive: bool = True
    upper_bound_inclusive: bool = True
    incomplete_event_date_policy: Literal["review_required"]
    missing_treatment_date_policy: Literal["review_required"]
    multiple_treatment_period_policy: Literal["review_required"]
    pre_treatment_worsening_policy: Literal[
        "review_required", "include_if_worsened"
    ]


class ApprovalEvidence(StrictContractModel):
    """Hash-locked Review artifacts authorizing one Study decision finding."""

    review_id: NonEmptyString
    finding_id: NonEmptyString
    packet_path: NonEmptyString
    packet_sha256: Sha256
    decision_path: NonEmptyString
    decision_sha256: Sha256
    confirmation_path: NonEmptyString
    confirmation_sha256: Sha256


class StudyDecision(StrictContractModel):
    """Study-scoped executable rule whose content and approval are independently locked."""

    decision_id: StableId
    schema_version: SemVerString = "1.0.0"
    version: SemVerString
    study_id: NonEmptyString
    stage: WorkflowStage
    priority: int = Field(ge=1, le=1000)
    title: NonEmptyString
    statement: NonEmptyString
    source_ids: tuple[StableId, ...] = Field(min_length=1)
    structured_rule: TEAEWindowRule
    approval_evidence: ApprovalEvidence
    content_sha256: Sha256

    @model_validator(mode="after")
    def teae_rule_is_scoped_to_adam_spec(self) -> Self:
        if self.stage is not WorkflowStage.ADAM_SPEC:
            raise ValueError("TEAE Study decisions are only valid for the adam_spec stage")
        return self


class ResolvedRule(StrictContractModel):
    rule_id: StableId
    layer: RuleLayer
    priority: int = Field(ge=1, le=1000)
    title: NonEmptyString
    statement: NonEmptyString
    source_ids: tuple[StableId, ...] = Field(min_length=1)
    source_version: SemVerString
    source_sha256: Sha256
    approval_receipt_id: NonEmptyString
    structured_rule: TEAEWindowRule | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )

    @model_validator(mode="after")
    def structured_rules_are_study_scoped(self) -> Self:
        if self.structured_rule is not None and self.layer is not RuleLayer.STUDY:
            raise ValueError("structured executable rules must use the study layer")
        return self


class ContextConflict(StrictContractModel):
    conflict_id: StableId
    rule_ids: tuple[StableId, ...] = Field(min_length=2)
    reason: NonEmptyString
    resolution: NonEmptyString | None = None


class MissingRequirement(StrictContractModel):
    requirement_id: StableId
    description: NonEmptyString
    blocking: bool = True


class ProvenanceEntry(StrictContractModel):
    provenance_id: StableId
    object_id: StableId
    object_version: SemVerString
    object_sha256: Sha256
    source_kind: Literal[
        "pipeline_contract", "workflow_knowledge", "domain_knowledge", "study_decision"
    ]
    snapshot_id: StableId | None = None
    audit_reference: NonEmptyString


class ExecutionContext(StrictContractModel):
    bundle_id: ContextId
    schema_version: SemVerString
    study_id: NonEmptyString
    stage: WorkflowStage
    resolved_at: datetime
    manifest_id: StableId
    manifest_sha256: Sha256
    pipeline_contract: ArtifactLock
    workflow_rules: tuple[ResolvedRule, ...] = ()
    domain_rules: tuple[ResolvedRule, ...] = ()
    study_rules: tuple[ResolvedRule, ...] = ()
    conflicts: tuple[ContextConflict, ...] = ()
    missing_requirements: tuple[MissingRequirement, ...] = ()
    provenance: tuple[ProvenanceEntry, ...] = Field(min_length=1)
    executable: bool
    execution_context_sha256: Sha256

    @model_validator(mode="after")
    def fail_closed_on_unresolved_context(self) -> Self:
        blocking_missing = any(item.blocking for item in self.missing_requirements)
        unresolved_conflicts = any(item.resolution is None for item in self.conflicts)
        if self.executable and (blocking_missing or unresolved_conflicts):
            raise ValueError("execution context with unresolved blockers cannot be executable")
        expected_layers = (
            *((rule, RuleLayer.WORKFLOW) for rule in self.workflow_rules),
            *((rule, RuleLayer.DOMAIN) for rule in self.domain_rules),
            *((rule, RuleLayer.STUDY) for rule in self.study_rules),
        )
        if any(rule.layer is not expected for rule, expected in expected_layers):
            raise ValueError("resolved rule is stored in the wrong rule layer")
        return self
