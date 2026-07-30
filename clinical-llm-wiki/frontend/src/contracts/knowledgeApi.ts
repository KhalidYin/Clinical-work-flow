export const CONTRACT_VERSION = "knowledge-api.prerelease.v1";

export const API_PATHS = {
  session: "/api/prerelease/v1/session",
  health: "/api/prerelease/v1/health",
  currentRelease: "/api/prerelease/v1/releases/current",
  sources: "/api/prerelease/v1/sources",
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
  mediaType: "PDF" | "DOCX" | "XLSX" | "Markdown";
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
