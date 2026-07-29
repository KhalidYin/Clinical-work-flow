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
  role: "Admin" | "Knowledge Author" | "Knowledge Reviewer" | "Release Manager" | "Consumer";
  organization: string;
  permissions: string[];
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
  identitySource: "local-test" | "oidc";
  roles: Session["role"][];
  status: "active" | "disabled";
  lastActiveAt: string | null;
}

export interface UserCollection {
  items: PlatformUser[];
  total: number;
  partial: boolean;
  warnings: string[];
}
