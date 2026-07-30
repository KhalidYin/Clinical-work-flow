import {
  CONTRACT_VERSION,
  type ApiResponse,
  type CurrentRelease,
  type PlatformHealth,
  type ProcessingRunCollection,
  type Session,
  type SourceRegistration,
  type SourceCollection,
  type RetryReceipt,
  type CancelReceipt,
  type CandidateCollection,
  type CandidateDetail,
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
  roles: ["platform_admin", "knowledge_curator"],
  organization: "Clinical Knowledge Lab",
  permissions: [
    "source:read",
    "source:register",
    "source:upload",
    "processing:read",
    "processing:start",
    "processing:retry",
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

export const sourceRegistrationFixture = response<SourceRegistration>({
  sourceId: "src-ui-upload",
  sourceVersionId: "srcv-ui-upload-v1",
  runId: "run-ui-upload-v1",
  status: "queued",
  originalObject: {
    objectKey: "sources/src-ui-upload/srcv-ui-upload-v1/source.md",
    sha256: fixtureHash("0f0e0d0c0b0a"),
    mediaType: "text/markdown",
    sizeBytes: 24,
    artifactRole: "original",
  },
});

export const processingRunsFixture = response<ProcessingRunCollection>({
  total: 3,
  partial: false,
  warnings: [],
  items: [
    {
      runId: "run-active-001",
      sourceVersionId: "srcv-ct-2026q2",
      status: "processing",
      createdAt: fixtureTime,
      updatedAt: fixtureTime,
      originalArtifactCount: 1,
      derivedArtifactCount: 2,
      evidenceCount: 0,
      steps: [
        {
          stepId: "step-parse-tables",
          stepKey: "document.parse_tables",
          pool: "document",
          status: "processing",
          dependsOn: ["document.validate"],
          latestAttempt: {
            attemptId: "attempt-parse-tables-1",
            attemptNumber: 1,
            status: "leased",
            errorType: null,
            checkpoint: { sheet: "CT", row: 12 },
            artifactCount: 1,
          },
        },
      ],
    },
    {
      runId: "run-evidence-ready-003",
      sourceVersionId: "srcv-sdtmig-34",
      status: "evidence_ready",
      createdAt: fixtureTime,
      updatedAt: fixtureTime,
      originalArtifactCount: 1,
      derivedArtifactCount: 3,
      evidenceCount: 18,
      steps: [
        {
          stepId: "step-build-evidence",
          stepKey: "document.build_evidence",
          pool: "document",
          status: "succeeded",
          dependsOn: ["document.parse_text", "document.parse_tables"],
          latestAttempt: {
            attemptId: "attempt-build-evidence-1",
            attemptNumber: 1,
            status: "succeeded",
            errorType: null,
            checkpoint: { evidenceCount: 18 },
            artifactCount: 18,
          },
        },
      ],
    },
    {
      runId: "run-failed-002",
      sourceVersionId: "srcv-sap-001",
      status: "failed",
      createdAt: fixtureTime,
      updatedAt: fixtureTime,
      originalArtifactCount: 1,
      derivedArtifactCount: 1,
      evidenceCount: 0,
      steps: [
        {
          stepId: "step-parse-text",
          stepKey: "document.parse_text",
          pool: "document",
          status: "failed",
          dependsOn: ["document.validate"],
          latestAttempt: {
            attemptId: "attempt-parse-text-1",
            attemptNumber: 1,
            status: "failed",
            errorType: "handler_error",
            checkpoint: { page: 4 },
            artifactCount: 0,
          },
        },
      ],
    },
  ],
});

export const retryReceiptFixture = response<RetryReceipt>({
  runId: "run-failed-002",
  stepId: "step-parse-text",
  attemptId: "attempt-parse-text-2",
  status: "queued",
});

export const cancelReceiptFixture = response<CancelReceipt>({
  runId: "run-active-001",
  status: "cancelled",
});

export const candidatesFixture = response<CandidateCollection>({
  total: 2,
  partial: false,
  warnings: [],
  items: [
    {
      candidateId: "cand-ui-aeseq-001",
      candidateGroupId: "candgrp-ui-aeseq",
      runId: "run-ui-aeseq",
      revisionNumber: 1,
      status: "author_confirmation_required",
      knowledgeType: "variable_definition",
      claim: "AESEQ is the sequence identifier within the AE domain.",
      scope: { standard: "SDTM", domain: "AE" },
      applicability: { standardVersion: "3.4" },
      contentSha256: "a".repeat(64),
      evidenceCount: 2,
      relationProposalCount: 1,
      authorActorId: null,
      knowledgeRevisionId: null,
      reviewStatus: null,
    },
    {
      candidateId: "cand-ui-teae-001",
      candidateGroupId: "candgrp-ui-teae",
      runId: "run-ui-teae",
      revisionNumber: 1,
      status: "author_confirmed",
      knowledgeType: "clinical_rule",
      claim: "TEAE applicability is bounded by the confirmed analysis scope.",
      scope: { standard: "ADaM", dataset: "ADAE" },
      applicability: { analysis: "safety" },
      contentSha256: "b".repeat(64),
      evidenceCount: 3,
      relationProposalCount: 2,
      authorActorId: "usr-author-004",
      knowledgeRevisionId: "krev-ui-teae-001",
      reviewStatus: "review_required",
    },
  ],
});

export const candidateDetailsFixture: Record<string, ApiResponse<CandidateDetail>> = {
  "cand-ui-aeseq-001": response<CandidateDetail>({
    ...candidatesFixture.data.items[0],
    parentCandidateId: null,
    conditions: [],
    exceptions: [],
    evidence: [
      {
        evidenceId: "evidence-ui-aeseq-001",
        sourceVersionId: "srcv-sdtmig-34",
        locator: { page: 35, section: "6.2 AE", paragraph: 4 },
        content:
          "AESEQ is the sequence identifier used to uniquely identify a record within the AE domain.",
        contentSha256: "e".repeat(64),
        rights: {
          classification: "licensed",
          storageAllowed: true,
          citationRequired: true,
        },
      },
      {
        evidenceId: "evidence-ui-aeseq-002",
        sourceVersionId: "srcv-sdtmig-34",
        locator: { page: 36, table: "AE domain variables", row: "AESEQ" },
        content: "AESEQ is required for uniquely identifying each AE record.",
        contentSha256: "f".repeat(64),
        rights: {
          classification: "licensed",
          storageAllowed: true,
          citationRequired: true,
        },
      },
    ],
    relationProposals: [
      {
        relationType: "applies_to",
        targetKnowledgeUnitId: "KU-SDTM-AE",
        evidenceIds: ["evidence-ui-aeseq-001"],
        status: "proposed",
      },
    ],
  }),
  "cand-ui-teae-001": response<CandidateDetail>({
    ...candidatesFixture.data.items[1],
    parentCandidateId: null,
    conditions: [],
    exceptions: [],
    evidence: [
      {
        evidenceId: "evidence-ui-teae-001",
        sourceVersionId: "srcv-adamig-13",
        locator: { page: 91, section: "ADAE analysis flags" },
        content:
          "Treatment-emergent flags must be derived within a prospectively defined analysis window.",
        contentSha256: "c".repeat(64),
        rights: {
          classification: "licensed",
          storageAllowed: true,
          citationRequired: true,
        },
      },
    ],
    relationProposals: [
      {
        relationType: "depends_on",
        targetKnowledgeUnitId: "KU-ADSL-TRTSDT",
        evidenceIds: ["evidence-ui-teae-001"],
        status: "proposed",
      },
      {
        relationType: "applies_to",
        targetKnowledgeUnitId: "KU-ADAM-ADAE",
        evidenceIds: ["evidence-ui-teae-001"],
        status: "proposed",
      },
    ],
  }),
};

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
