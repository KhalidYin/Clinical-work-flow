export const CONTRACT_VERSION = "knowledge-api.prerelease.v1";

export const API_PATHS = {
  session: "/api/prerelease/v1/session",
  health: "/api/prerelease/v1/health",
  currentRelease: "/api/prerelease/v1/releases/current",
  sources: "/api/prerelease/v1/sources",
  processingRuns: "/api/prerelease/v1/processing-runs",
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
