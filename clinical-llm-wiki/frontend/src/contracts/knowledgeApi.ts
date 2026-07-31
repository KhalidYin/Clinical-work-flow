export const CONTRACT_VERSION = "knowledge-api.prerelease.v1";

export const API_PATHS = {
  session: "/api/prerelease/v1/session",
  health: "/api/prerelease/v1/health",
  currentRelease: "/api/prerelease/v1/releases/current",
  sources: "/api/prerelease/v1/sources",
  processingRuns: "/api/prerelease/v1/processing-runs",
  candidates: "/api/prerelease/v1/candidates",
  knowledgeRevisions: "/api/prerelease/v1/knowledge-revisions",
  relationQuery: "/api/prerelease/v1/relations/query",
  auditEvents: "/api/prerelease/v1/audit-events",
  adminUsers: "/api/prerelease/v1/admin/users",
} as const;

export function resolveApiPath(path: string): string {
  return new URL(path, window.location.origin).toString();
}

export type CapabilityState = "available" | "degraded" | "disabled";
export type HumanRole =
  | "platform_admin"
  | "knowledge_curator"
  | "reviewer"
  | "release_manager"
  | "consumer";
export type ProductPermission =
  | "source:read"
  | "source:register"
  | "source:upload"
  | "processing:read"
  | "processing:start"
  | "processing:retry"
  | "processing:execute"
  | "object:read"
  | "object:write_derived"
  | "evidence:read"
  | "evidence:write"
  | "candidate:read"
  | "candidate:write"
  | "candidate:submit"
  | "relation:propose"
  | "review:decide"
  | "query:released"
  | "model:invoke"
  | "evaluation:run"
  | "index:build"
  | "release:build"
  | "release:publish"
  | "admin:read"
  | "admin:manage_users"
  | "admin:manage_roles"
  | "admin:manage_service_accounts"
  | "audit:read";

export const ROLE_LABELS: Record<HumanRole, string> = {
  platform_admin: "Admin",
  knowledge_curator: "Knowledge Curator",
  reviewer: "Knowledge Reviewer",
  release_manager: "Release Manager",
  consumer: "Consumer",
};

export function roleLabel(role: HumanRole): string {
  return ROLE_LABELS[role];
}

export type RecordStatus =
  | "registered"
  | "processing"
  | "candidate"
  | "approved"
  | "released"
  | "restricted"
  | "disabled";

export interface ResponseMeta {
  contractVersion: typeof CONTRACT_VERSION;
  fixture: boolean;
  generatedAt: string;
}

export interface ApiResponse<T> {
  data: T;
  meta: ResponseMeta;
}

export interface Session {
  actorId: string;
  displayName: string;
  principalType: "human";
  roles: HumanRole[];
  organization: string;
  permissions: ProductPermission[];
}

export interface PlatformHealth {
  status: "healthy" | "degraded";
  api: CapabilityState;
  database: CapabilityState;
  objectStore: CapabilityState;
  semanticIndex: CapabilityState;
  checkedAt: string;
}

export interface CurrentRelease {
  releaseId: string | null;
  version: string | null;
  status: "released" | "not_released";
  indexVersion: string | null;
  releasedAt: string | null;
}

export interface SourceSummary {
  sourceId: string;
  title: string;
  version: string;
  mediaType: "PDF" | "DOCX" | "XLSX" | "Markdown" | "TXT";
  rights: "licensed" | "internal" | "restricted";
  status: RecordStatus;
  sourceHash: string;
  updatedAt: string;
}

export interface SourceCollection {
  items: SourceSummary[];
  total: number;
  partial: boolean;
  warnings: string[];
}

export interface ObjectReference {
  objectKey: string;
  sha256: string;
  mediaType: string;
  sizeBytes: number;
  artifactRole: "original" | "derived";
}

export interface SourceRegistration {
  sourceId: string;
  sourceVersionId: string;
  runId: string;
  status: "queued";
  originalObject: ObjectReference;
}

export type ProcessingRunStatus =
  | "queued"
  | "processing"
  | "evidence_ready"
  | "author_confirmation_required"
  | "review_required"
  | "approved"
  | "release_blocked"
  | "released"
  | "failed"
  | "cancelled";

export interface ProcessingAttempt {
  attemptId: string;
  attemptNumber: number;
  status: "queued" | "leased" | "succeeded" | "failed" | "expired" | "cancelled";
  errorType: string | null;
  checkpoint: Record<string, unknown> | null;
  artifactCount: number;
}

export interface ProcessingStep {
  stepId: string;
  stepKey: string;
  pool: "document" | "enrichment" | "release";
  status: "queued" | "processing" | "succeeded" | "failed" | "cancelled";
  dependsOn: string[];
  latestAttempt: ProcessingAttempt;
}

export interface ProcessingRun {
  runId: string;
  sourceVersionId: string;
  status: ProcessingRunStatus;
  createdAt: string;
  updatedAt: string;
  originalArtifactCount: number;
  derivedArtifactCount: number;
  evidenceCount: number;
  steps: ProcessingStep[];
}

export interface ProcessingRunCollection {
  items: ProcessingRun[];
  total: number;
  partial: boolean;
  warnings: string[];
}

export type CandidateStatus =
  | "author_confirmation_required"
  | "author_confirmed"
  | "superseded";

export type KnowledgeReviewStatus =
  | "review_required"
  | "approved"
  | "rejected"
  | "changes_requested"
  | "released"
  | "superseded"
  | "retired";

export interface CandidateSummary {
  candidateId: string;
  candidateGroupId: string;
  runId: string;
  revisionNumber: number;
  status: CandidateStatus;
  knowledgeType: string;
  claim: string;
  scope: Record<string, unknown>;
  applicability: Record<string, unknown>;
  contentSha256: string;
  evidenceCount: number;
  relationProposalCount: number;
  authorActorId: string | null;
  knowledgeRevisionId: string | null;
  reviewStatus: KnowledgeReviewStatus | null;
}

export interface CandidateCollection {
  items: CandidateSummary[];
  total: number;
  partial: boolean;
  warnings: string[];
}

export interface CandidateEvidence {
  evidenceId: string;
  sourceVersionId: string;
  locator: Record<string, unknown>;
  content: string;
  contentSha256: string;
  rights: Record<string, unknown>;
}

export type RelationType =
  | "applies_to"
  | "conflicts_with"
  | "depends_on"
  | "derived_from"
  | "supersedes"
  | "supports"
  | "used_by";

export interface CandidateRelationProposal {
  relationType: RelationType;
  targetKnowledgeUnitId: string;
  evidenceIds: string[];
  status: "proposed" | "accepted" | "rejected" | "superseded";
}

export interface CandidateDetail extends CandidateSummary {
  parentCandidateId: string | null;
  conditions: Record<string, unknown>[];
  exceptions: Record<string, unknown>[];
  evidence: CandidateEvidence[];
  relationProposals: CandidateRelationProposal[];
}

export type RelationNodeStatus =
  | "unversioned"
  | "review_required"
  | "approved"
  | "rejected"
  | "changes_requested"
  | "released"
  | "superseded"
  | "retired";

export interface RelationEvidence {
  evidenceId: string;
  sourceVersionId: string;
  locator: Record<string, unknown>;
  content: string;
  contentSha256: string;
}

export interface RelationNode {
  knowledgeUnitId: string;
  stableKey: string;
  knowledgeType: string;
  knowledgeRevisionId: string | null;
  revisionNumber: number | null;
  status: RelationNodeStatus;
  claim: string | null;
  releaseIds: string[];
}

export interface RelationEdge {
  relationId: string;
  sourceKnowledgeUnitId: string;
  targetKnowledgeUnitId: string;
  relationType: RelationType;
  status: string;
  evidence: RelationEvidence[];
}

export interface RelationQuery {
  rootNodeId: string | null;
  requestedDepth: number;
  appliedDepth: number;
  nodes: RelationNode[];
  edges: RelationEdge[];
  totalNodes: number;
  truncated: boolean;
  partial: boolean;
  warnings: string[];
}

export interface AuditVersion {
  revisionNumber: number | null;
  contentSha256: string | null;
}

export interface AuditEvent {
  auditEventId: string;
  actorId: string;
  action: string;
  objectType: string;
  objectId: string;
  runId: string | null;
  beforeVersion: AuditVersion | null;
  afterVersion: AuditVersion | null;
  result: string | null;
  correlationId: string | null;
  createdAt: string;
}

export interface AuditEventCollection {
  items: AuditEvent[];
  total: number;
  nextCursor: string | null;
  partial: boolean;
  warnings: string[];
}

export interface CandidateRevisionRequest {
  expectedRevisionNumber: number;
  expectedContentSha256: string;
  claim: string;
  scope: Record<string, unknown>;
  applicability: Record<string, unknown>;
  conditions: Record<string, unknown>[];
  exceptions: Record<string, unknown>[];
  idempotencyKey: string;
}

export interface CandidateRevision {
  candidateId: string;
  parentCandidateId: string;
  revisionNumber: number;
  contentSha256: string;
  status: "author_confirmation_required";
}

export interface AuthorConfirmationRequest {
  expectedRevisionNumber: number;
  expectedContentSha256: string;
  idempotencyKey: string;
}

export interface AuthorConfirmation {
  candidateId: string;
  candidateStatus: "author_confirmed";
  knowledgeRevisionId: string;
  revisionStatus: "review_required";
  decisionId: string;
}

export type ReviewDecisionOutcome = "approved" | "rejected" | "changes_requested";

export interface ReviewDecisionRequest {
  candidateId: string;
  expectedRevisionNumber: number;
  expectedContentSha256: string;
  decision: ReviewDecisionOutcome;
  idempotencyKey: string;
  rationale: string | null;
}

export interface ReviewDecision {
  candidateId: string;
  knowledgeRevisionId: string;
  revisionStatus: ReviewDecisionOutcome;
  decisionId: string;
}

export type ApiErrorCode =
  | "authentication_required"
  | "invalid_identity"
  | "permission_denied"
  | "service_unavailable"
  | "registration_conflict"
  | "invalid_source"
  | "unsupported_media"
  | "run_not_found"
  | "retry_not_allowed"
  | "candidate_not_found"
  | "invalid_governance_transition"
  | "stale_revision"
  | "duplicate_decision";

export interface ErrorResponse {
  error: {
    code: ApiErrorCode;
    message: string;
  };
  meta: ResponseMeta;
}

export interface RetryReceipt {
  runId: string;
  stepId: string;
  attemptId: string;
  status: "queued";
}

export interface CancelReceipt {
  runId: string;
  status: "cancelled";
}

export interface PlatformUser {
  userId: string;
  displayName: string;
  email: string;
  identitySource: "local_test" | "oidc";
  roles: HumanRole[];
  status: "active" | "disabled";
  lastActiveAt: string | null;
}

export interface UserCollection {
  items: PlatformUser[];
  total: number;
  partial: boolean;
  warnings: string[];
}
