import {
  CONTRACT_VERSION,
  type ApiResponse,
  type CurrentRelease,
  type PlatformHealth,
  type Session,
  type SourceCollection,
  type UserCollection,
} from "../contracts/knowledgeApi";

const fixtureTime = "2026-07-29T14:58:00Z";

function fixtureHash(prefix: string): string {
  return prefix.padEnd(64, "0");
}

function response<T>(data: T): ApiResponse<T> {
  return {
    data,
    meta: {
      contractVersion: CONTRACT_VERSION,
      fixture: true,
      generatedAt: fixtureTime,
    },
  };
}

export const sessionFixture = response<Session>({
  actorId: "usr-ke-017",
  displayName: "Kevin Dean",
  principalType: "human",
  roles: ["platform_admin"],
  organization: "Clinical Knowledge Lab",
  permissions: [
    "source:read",
    "processing:read",
    "evidence:read",
    "candidate:read",
    "query:released",
    "admin:read",
    "admin:manage_users",
    "admin:manage_roles",
    "admin:manage_service_accounts",
    "audit:read",
  ],
});

export const healthFixture = response<PlatformHealth>({
  status: "degraded",
  api: "available",
  database: "available",
  objectStore: "available",
  semanticIndex: "disabled",
  checkedAt: fixtureTime,
});

export const releaseFixture = response<CurrentRelease>({
  releaseId: "rel-2026-07-29-001",
  version: "2026.07-d0",
  status: "released",
  indexVersion: "idx-0007",
  releasedAt: "2026-07-29T13:42:11Z",
});

export const sourcesFixture = response<SourceCollection>({
  total: 5,
  partial: false,
  warnings: [],
  items: [
    {
      sourceId: "src-sdtmig-34",
      title: "Study Data Tabulation Model Implementation Guide",
      version: "3.4",
      mediaType: "PDF",
      rights: "licensed",
      status: "released",
      sourceHash: fixtureHash("f4b8d992a713"),
      updatedAt: "2026-07-29T13:41:00Z",
    },
    {
      sourceId: "src-adamig-13",
      title: "Analysis Data Model Implementation Guide",
      version: "1.3",
      mediaType: "PDF",
      rights: "licensed",
      status: "approved",
      sourceHash: fixtureHash("9a60cf74e81d"),
      updatedAt: "2026-07-29T12:18:00Z",
    },
    {
      sourceId: "src-ct-2026q2",
      title: "CDISC Controlled Terminology",
      version: "2026 Q2",
      mediaType: "XLSX",
      rights: "licensed",
      status: "processing",
      sourceHash: fixtureHash("70d1b30ca4f9"),
      updatedAt: "2026-07-29T11:04:00Z",
    },
    {
      sourceId: "src-sop-ae-017",
      title: "AE Derivation Review SOP",
      version: "2.1",
      mediaType: "DOCX",
      rights: "internal",
      status: "candidate",
      sourceHash: fixtureHash("d3f17c269aa2"),
      updatedAt: "2026-07-28T16:43:00Z",
    },
    {
      sourceId: "src-reg-note-01",
      title: "Restricted Regulatory Working Note",
      version: "0.4",
      mediaType: "Markdown",
      rights: "restricted",
      status: "restricted",
      sourceHash: fixtureHash("b5f08043ce91"),
      updatedAt: "2026-07-27T09:22:00Z",
    },
  ],
});

export const usersFixture = response<UserCollection>({
  total: 4,
  partial: false,
  warnings: [],
  items: [
    {
      userId: "usr-ke-017",
      displayName: "Kevin Dean",
      email: "kevin.dean@example.test",
      identitySource: "local_test",
      roles: ["platform_admin"],
      status: "active",
      lastActiveAt: fixtureTime,
    },
    {
      userId: "usr-author-004",
      displayName: "Lin Chen",
      email: "lin.chen@example.test",
      identitySource: "oidc",
      roles: ["knowledge_curator"],
      status: "active",
      lastActiveAt: "2026-07-29T13:37:00Z",
    },
    {
      userId: "usr-review-002",
      displayName: "Mei Zhou",
      email: "mei.zhou@example.test",
      identitySource: "oidc",
      roles: ["reviewer"],
      status: "active",
      lastActiveAt: "2026-07-29T12:55:00Z",
    },
    {
      userId: "usr-release-001",
      displayName: "Arun Rao",
      email: "arun.rao@example.test",
      identitySource: "oidc",
      roles: ["release_manager"],
      status: "disabled",
      lastActiveAt: null,
    },
  ],
});
