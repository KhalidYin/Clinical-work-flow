export const CONTRACT_VERSION = "knowledge-api.prerelease.v1";

export const API_PATHS = {
  login: "/api/prerelease/v1/auth/login",
  changePassword: "/api/prerelease/v1/auth/password/change",
  logout: "/api/prerelease/v1/auth/logout",
  session: "/api/prerelease/v1/session",
  health: "/api/prerelease/v1/health",
  currentRelease: "/api/prerelease/v1/releases/current",
  releaseWorkbench: "/api/prerelease/v1/releases/workbench",
  releasedQuery: "/api/prerelease/v1/query-lab/released-query",
  evaluations: "/api/prerelease/v1/evaluations",
  sources: "/api/prerelease/v1/sources",
  processingRuns: "/api/prerelease/v1/processing-runs",
  candidates: "/api/prerelease/v1/candidates",
  rotationCases: "/api/prerelease/v1/rotation-cases",
  knowledgeRevisions: "/api/prerelease/v1/knowledge-revisions",
  relationQuery: "/api/prerelease/v1/relations/query",
  auditEvents: "/api/prerelease/v1/audit-events",
  adminUsers: "/api/prerelease/v1/admin/users",
  adminServiceAccounts: "/api/prerelease/v1/admin/service-accounts",
  adminModelProfiles: "/api/prerelease/v1/admin/model-profiles",
} as const;

export function chunkProjectionPath(runId: string): string {
  return `${API_PATHS.processingRuns}/${encodeURIComponent(runId)}/chunk-projection`;
}

export function rotationCasePath(rotationCaseId: string): string {
  return `${API_PATHS.rotationCases}/${encodeURIComponent(rotationCaseId)}`;
}

export function rotationProposalPath(rotationCaseId: string): string {
  return `${rotationCasePath(rotationCaseId)}/proposal`;
}

export function rotationDecisionPath(rotationCaseId: string): string {
  return `${rotationCasePath(rotationCaseId)}/decision`;
}

export function sourceHistoryPath(sourceId: string): string {
  return `${API_PATHS.sources}/${encodeURIComponent(sourceId)}/versions`;
}

export function sourceImpactAssessmentsPath(sourceId: string): string {
  return `${API_PATHS.sources}/${encodeURIComponent(sourceId)}/impact-assessments`;
}

export function impactAssessmentPath(assessmentId: string): string {
  return `/api/prerelease/v1/impact-assessments/${encodeURIComponent(assessmentId)}`;
}

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
  platform_admin: "平台管理员",
  knowledge_curator: "知识工程师",
  reviewer: "知识审核员",
  release_manager: "发布管理员",
  consumer: "知识使用者",
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
  mustChangePassword: boolean;
  sessionExpiresAt: string;
}

export function adminUserPasswordResetPath(userId: string): string {
  return `${API_PATHS.adminUsers}/${encodeURIComponent(userId)}/password/reset`;
}

export function adminUserStatusPath(userId: string): string {
  return `${API_PATHS.adminUsers}/${encodeURIComponent(userId)}/status`;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface PasswordChangeRequest {
  currentPassword: string;
  newPassword: string;
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

export interface ReleaseSummary {
  releaseId: string;
  version: string;
  status: string;
  baseReleaseId: string | null;
  itemCount: number;
  isCurrent: boolean;
  createdAt: string;
  publishedAt: string | null;
}

export type ReleaseGateCode =
  | "candidate_integrity"
  | "base_release_current"
  | "evaluation_passed"
  | "publication_snapshot";

export interface ReleaseGate {
  code: ReleaseGateCode;
  passed: boolean;
  reason: string;
}

export interface ReleaseDiff {
  includedCount: number;
  carriedCount: number;
  replacedCount: number;
  addedCount: number;
  retiredCount: number;
  includedRevisionIds: string[];
  carriedRevisionIds: string[];
  replacedRevisionIds: string[];
  addedRevisionIds: string[];
  retiredRevisionIds: string[];
}

export interface ReleaseWorkbench {
  current: ReleaseSummary | null;
  candidate: ReleaseSummary | null;
  history: ReleaseSummary[];
  diff: ReleaseDiff | null;
  gates: ReleaseGate[];
  blockers: string[];
  allowedActions: Array<"publish">;
}

export interface ReleasePublishRequest {
  baseReleaseId: string | null;
}

export interface PublishedRelease {
  releaseId: string;
  version: string;
  previousReleaseId: string | null;
  manifestObjectKey: string;
  manifestSha256: string;
  indexManifestVersion: string;
  publishedAt: string;
}

export interface ReleaseManifestItem {
  knowledgeRevisionId: string;
  contentSha256: string;
  disposition: string;
  evidenceIds: string[];
  chunkIds: string[];
}

export interface ReleaseManifest {
  schemaVersion: "p17-release-v1";
  releaseId: string;
  releaseVersion: string;
  baseReleaseId: string | null;
  evaluationRunId: string;
  chunkProfileId: string;
  chunkProfileVersion: string;
  rotationCaseIds: string[];
  dbSchemaRevision: string;
  knowledgeContractVersion: string;
  parserProfileVersion: string;
  modelProfileVersion: string;
  promptProfileVersion: string;
  indexDescriptor: {
    objectKey: string;
    sha256: string;
    mediaType: string;
    sizeBytes: number;
  };
  items: ReleaseManifestItem[];
}

export interface ReleasedManifest {
  releaseId: string;
  version: string;
  manifestSha256: string;
  manifest: ReleaseManifest;
}

export function releasePublishPath(releaseId: string): string {
  return `/api/prerelease/v1/releases/${encodeURIComponent(releaseId)}/publish`;
}

export function releaseManifestPath(releaseId: string): string {
  return `/api/prerelease/v1/releases/${encodeURIComponent(releaseId)}/manifest`;
}

export function evaluationRunPath(evaluationRunId: string): string {
  return `${API_PATHS.evaluations}/${encodeURIComponent(evaluationRunId)}`;
}

export function evaluationReplayPath(evaluationRunId: string, caseId: string): string {
  return `${evaluationRunPath(evaluationRunId)}/cases/${encodeURIComponent(caseId)}/replay`;
}

export function evaluationRegressionPath(
  evaluationRunId: string,
  baselineRunId: string,
): string {
  const params = new URLSearchParams({ baseline_run_id: baselineRunId });
  return `${evaluationRunPath(evaluationRunId)}/regression?${params.toString()}`;
}

export interface RetrievalCapability {
  status: CapabilityState;
  reason: string | null;
}

export interface RetrievalCapabilities {
  metadata: RetrievalCapability;
  fullText: RetrievalCapability;
  vector: RetrievalCapability;
  relation: RetrievalCapability;
  generation: RetrievalCapability;
}

export interface RetrievalCitation {
  evidenceId: string;
  sourceVersionId: string;
  sourceArtifactId: string;
  locator: Record<string, unknown>;
  contentSha256: string;
  startOffset: number;
  endOffset: number;
  spanRole: "primary" | "overlap";
}

export interface RetrievalHit {
  rank: number;
  chunkId: string;
  content: string;
  contentSha256: string;
  fusionScore: number;
  routeContributions: {
    metadata: number;
    fullText: number;
    vector: null;
    relation: null;
  };
  explanation: {
    sourceVersionId: string;
    sourceTitle: string;
    sourceVersion: string;
    chunkProfileId: string;
    ordinal: number;
    evidenceType: string;
    locator: Record<string, unknown>;
    tokenCount: number;
  };
  citations: RetrievalCitation[];
}

export interface ReleasedQueryLabResult {
  queryId: string;
  releaseId: string;
  releaseVersion: string;
  fusionVersion: "metadata-fts-weighted-v1";
  capabilities: RetrievalCapabilities;
  hits: RetrievalHit[];
  contextPackage: {
    scopeKind: "immutable_release";
    releaseId: string;
    chunkIds: string[];
    citations: RetrievalCitation[];
  };
  externalModelRequests: 0;
  evaluationNotice: "single_document_retrieval_baseline_not_clinical_quality_certification";
}

export interface ReleasedQueryLabRequest {
  query: string;
  topK: number;
  releaseId: string | null;
}

export interface CandidateQueryLabResult {
  queryId: string;
  fusionVersion: "metadata-fts-weighted-v1";
  capabilities: RetrievalCapabilities;
  hits: RetrievalHit[];
  contextPackage: {
    sandboxKind: "release_candidate";
    sandboxId: string;
    chunkIds: string[];
    citations: RetrievalCitation[];
  };
  externalModelRequests: 0;
  evaluationNotice: "single_document_retrieval_baseline_not_clinical_quality_certification";
}

export type EvaluationPurpose = "retrieval_baseline" | "release_gate_synthetic";
export type EvaluationOutcome = "informational" | "passed" | "failed";

export interface EvaluationRunSummary {
  evaluationRunId: string;
  suiteId: string;
  suiteVersion: string;
  purpose: EvaluationPurpose;
  targetId: string;
  status: string;
  outcome: EvaluationOutcome;
  caseCount: number;
  metrics: { recallAt5: number; recallAt10: number };
  externalModelRequests: number;
  evaluationNotice: string;
  startedAt: string;
  completedAt: string | null;
}

export interface EvaluationRunCollection {
  items: EvaluationRunSummary[];
  total: number;
  partial: boolean;
  warnings: string[];
  availableSuites: EvaluationSuite[];
  allowedActions: Array<"start">;
}

export interface EvaluationSuite {
  suiteId: string;
  suiteVersion: string;
  documentId: string;
  sourceVersionId: string;
  chunkProfileId: string;
  caseCount: number;
  sandboxKind: "release_candidate";
  externalModelRequests: 0;
}

export interface EvaluationStartRequest {
  suiteId: string;
  suiteVersion: string;
}

export interface EvaluationCase {
  caseId: string;
  topic: string | null;
  question: string | null;
  queryId: string | null;
  outcome: "hit_top_5" | "hit_top_10_only" | "expected_not_in_top_10";
  failureCategory: "none" | "ranked_below_5" | "expected_not_retrieved";
  hitAt5: boolean;
  hitAt10: boolean;
  firstRelevantRank: number | null;
  expectedEvidenceIds: string[];
  retrievedEvidenceIds: string[];
  replay: {
    queryLabPath: "/query-lab";
    evaluationRunId: string;
    caseId: string;
    query: string | null;
    releaseId: string | null;
    topK: 10;
    availability: "available" | "candidate_scope_required" | "query_unavailable";
  };
}

export interface EvaluationRunDetail extends EvaluationRunSummary {
  thresholdChecks: Array<{
    metric: "recall_at_5" | "recall_at_10";
    observed: number;
    minimum: number;
    passed: boolean;
  }>;
  failureReasons: string[];
  caseResults: EvaluationCase[];
}

export interface EvaluationRegression {
  evaluationRunId: string;
  baselineRunId: string;
  suiteId: string;
  currentSuiteVersion: string;
  baselineSuiteVersion: string;
  metricDeltas: { recallAt5: number; recallAt10: number };
  counts: {
    improved: number;
    regressed: number;
    unchanged: number;
    added: number;
    removed: number;
  };
  caseDiffs: Array<{
    caseId: string;
    change: "improved" | "regressed" | "unchanged" | "added" | "removed";
    baselineOutcome: string | null;
    currentOutcome: string | null;
    baselineRank: number | null;
    currentRank: number | null;
  }>;
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

export type EvidenceChangeType =
  | "unchanged"
  | "moved"
  | "modified"
  | "added"
  | "removed"
  | "rights_changed"
  | "ambiguous";

export type EvidenceChangeCounts = Record<EvidenceChangeType, number>;

export interface ImpactSummary {
  affectedKnowledgeCount: number;
  rotationCaseCount: number;
}

export interface SourceVersion {
  sourceVersionId: string;
  version: string;
  status: string;
  rights: {
    classification: "licensed" | "internal" | "restricted";
    storageAllowed: boolean;
  };
  dataBoundary: string;
  sourceHash: string;
  effectiveDate: string | null;
  createdAt: string;
}

export interface EvidenceImpact {
  evidenceImpactId: string;
  changeType: EvidenceChangeType;
  fromEvidenceId: string | null;
  toEvidenceId: string | null;
  mappingBasis:
    | "content_exact"
    | "locator_exact"
    | "ordered_alignment"
    | "unmatched"
    | "ambiguous";
  details: Record<string, unknown>;
}

export interface ImpactAssessmentSummary {
  assessmentId: string;
  fromSourceVersionId: string;
  toSourceVersionId: string;
  comparisonProfileVersion: string;
  changeCounts: EvidenceChangeCounts;
  impactSummary: ImpactSummary;
  createdAt: string;
}

export interface ImpactAssessment extends ImpactAssessmentSummary {
  impacts: EvidenceImpact[];
}

export interface SourceHistory {
  sourceId: string;
  title: string;
  versions: SourceVersion[];
  comparisons: ImpactAssessmentSummary[];
  allowedActions: Array<"compare">;
  partial: boolean;
  warnings: string[];
}

export interface ImpactMaterializationRequest {
  fromSourceVersionId: string;
  toSourceVersionId: string;
}

export interface ChunkProfile {
  chunkProfileId: string;
  version: string;
  tokenizerId: string;
  targetMinTokens: number;
  targetMaxTokens: number;
  hardMaxTokens: number;
  overlapTokens: number;
  tableHardMaxTokens: number;
  formatRules: Record<string, unknown>;
}

export interface ChunkEvidence {
  evidenceId: string;
  sourceVersionId: string;
  sourceArtifactId: string;
  evidenceType: string;
  locator: Record<string, unknown>;
  content: string;
  contentSha256: string;
}

export interface ChunkSpan {
  evidenceId: string;
  position: number;
  startOffset: number;
  endOffset: number;
  spanRole: "primary" | "overlap";
}

export interface RetrievalChunk {
  chunkId: string;
  ordinal: number;
  evidenceType: string;
  content: string;
  contentSha256: string;
  tokenCount: number;
  locator: Record<string, unknown>;
  dataBoundary:
    | "local_processing_only"
    | "enterprise_provider_only"
    | "external_allowed"
    | "prohibited";
  rights: Record<string, unknown>;
  spans: ChunkSpan[];
}

export interface ChunkProjectionFinding {
  findingId: string;
  evidenceId: string | null;
  findingType:
    | "empty"
    | "duplicate"
    | "boilerplate"
    | "oversize"
    | "boundary_violation";
  details: Record<string, unknown>;
}

export interface ChunkProjection {
  runId: string;
  sourceVersionId: string;
  chunkProfile: ChunkProfile;
  evidence: ChunkEvidence[];
  chunks: RetrievalChunk[];
  findings: ChunkProjectionFinding[];
}

export type RotationOutcome = "carry_forward" | "replace" | "retire" | "no_action";
export type RotationCaseStatus =
  | "open"
  | "in_review"
  | "decided"
  | "included_in_release"
  | "closed";

export interface RotationDecisionReceipt {
  rotationDecisionId: string;
  rotationCaseId: string;
  outcome: RotationOutcome;
  expectedCaseVersion: number;
  targetKnowledgeRevisionId: string | null;
  actorId: string;
  actorRole: "reviewer";
  idempotencyKey: string;
  rationale: string | null;
  createdAt: string;
}

export interface RotationCase {
  rotationCaseId: string;
  impactAssessmentId: string;
  knowledgeRevisionId: string;
  status: RotationCaseStatus;
  changeTypes: EvidenceChangeType[];
  eligibleOutcomes: RotationOutcome[];
  proposedOutcome: RotationOutcome | null;
  proposedTargetKnowledgeRevisionId: string | null;
  proposedByActorId: string | null;
  proposedRationale: string | null;
  caseVersion: number;
  includedReleaseId: string | null;
  releasedInReleaseIds: string[];
  receipts: RotationDecisionReceipt[];
  allowedActions: Array<"propose" | "decide">;
  createdAt: string;
  updatedAt: string;
}

export interface RotationCaseCollection {
  items: RotationCase[];
  total: number;
  partial: boolean;
  warnings: string[];
}

export interface RotationProposalRequest {
  expectedCaseVersion: number;
  outcome: RotationOutcome;
  targetKnowledgeRevisionId: string | null;
  idempotencyKey: string;
  rationale: string | null;
}

export type RotationDecisionRequest = RotationProposalRequest;

export interface RotationDecision {
  case: RotationCase;
  receipt: RotationDecisionReceipt;
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

export interface CandidateAdvisorySignal {
  signalType: "possible_duplicate" | "possible_conflict" | "explicit_gap";
  description: string;
  targetKnowledgeUnitId: string | null;
  evidenceIds: string[];
}

export interface CandidateDetail extends CandidateSummary {
  parentCandidateId: string | null;
  conditions: Record<string, unknown>[];
  exceptions: Record<string, unknown>[];
  evidence: CandidateEvidence[];
  relationProposals: CandidateRelationProposal[];
  advisorySignals: CandidateAdvisorySignal[];
  originModelInvocationId: string | null;
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

export type LifecycleNodeType =
  | "source_version"
  | "evidence"
  | "retrieval_chunk"
  | "knowledge_revision"
  | "release";

export interface LifecycleNode {
  nodeId: string;
  nodeType: LifecycleNodeType;
  label: string;
  status: string;
  derived: boolean;
}

export interface LifecycleEdge {
  sourceNodeId: string;
  targetNodeId: string;
  relationType: "contains" | "projected_as" | "supports" | "included_in";
}

export interface ReleaseMembership {
  releaseId: string;
  version: string;
  status: string;
  current: boolean;
}

export interface LifecycleLineage {
  rootKnowledgeRevisionId: string;
  selectedReleaseId: string | null;
  nodes: LifecycleNode[];
  edges: LifecycleEdge[];
  releaseMembership: ReleaseMembership[];
  partial: boolean;
  warnings: string[];
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
  lifecycle: LifecycleLineage | null;
}

export interface AuditVersion {
  revisionNumber: number | null;
  contentSha256: string | null;
}

export interface AuditTarget {
  resourceType:
    | "impact_assessment"
    | "rotation_case"
    | "evaluation_run"
    | "release"
    | "processing_run";
  resourceId: string;
  path: string;
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
  authoritativeTarget: AuditTarget | null;
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
  | "invalid_credentials"
  | "account_locked"
  | "password_change_required"
  | "current_password_invalid"
  | "password_policy_failed"
  | "csrf_rejected"
  | "invalid_identity"
  | "permission_denied"
  | "service_unavailable"
  | "registration_conflict"
  | "invalid_source"
  | "unsupported_media"
  | "source_not_found"
  | "impact_materialization_invalid"
  | "run_not_found"
  | "chunk_projection_not_found"
  | "retry_not_allowed"
  | "candidate_not_found"
  | "invalid_governance_transition"
  | "stale_revision"
  | "duplicate_decision"
  | "rotation_case_not_found"
  | "impact_assessment_not_found"
  | "stale_rotation_case"
  | "invalid_rotation_transition"
  | "evaluation_run_not_found"
  | "evaluation_run_invalid"
  | "evaluation_suite_not_found"
  | "evaluation_suite_conflict"
  | "evaluation_case_not_found"
  | "evaluation_comparison_invalid"
  | "released_knowledge_not_found"
  | "released_knowledge_invalid"
  | "release_candidate_not_found"
  | "release_publish_blocked"
  | "release_object_integrity_failed";

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
  identitySource: "local_password" | "local_test" | "oidc";
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

export interface UserCreateRequest {
  username: string;
  displayName: string;
  email: string;
  roles: HumanRole[];
}

export interface AdminTemporaryPassword {
  userId: string;
  username: string | null;
  temporaryPassword: string;
  mustChangePassword: true;
}

export interface UserStatusRequest {
  status: "active" | "disabled";
}

export interface UserStatusReceipt {
  userId: string;
  status: "active" | "disabled";
}

export interface ServiceAccountSummary {
  serviceAccountId: string;
  displayName: string;
  workerPool: "document" | "enrichment" | "release";
  scopes: ProductPermission[];
  status: "active" | "disabled";
}

export interface ServiceAccountCollection {
  items: ServiceAccountSummary[];
  total: number;
  partial: boolean;
  warnings: string[];
}

export type ModelDeploymentClass = "enterprise_managed" | "external_api";
export type ModelDataBoundary = "external_allowed" | "enterprise_provider_only";

export interface ModelProfileRegistrationRequest {
  profileId: string;
  version: string;
  provider: string;
  model: string;
  deploymentClass: ModelDeploymentClass;
  secretRef: string;
  endpointRef: string | null;
  allowedDataBoundaries: ModelDataBoundary[];
  capabilities: ["structured_generation"];
  timeoutSeconds: number;
  maxOutputTokens: number;
  costPolicy: Record<string, unknown> | null;
}

export interface ModelProfile extends ModelProfileRegistrationRequest {
  createdAt: string;
  connectionState: "not_verified";
  liveEnabled: false;
}

export interface ModelProfileCollection {
  items: ModelProfile[];
  total: number;
  partial: boolean;
  warnings: string[];
}

export interface ModelProfileRegistration {
  profile: ModelProfile;
  created: boolean;
}
