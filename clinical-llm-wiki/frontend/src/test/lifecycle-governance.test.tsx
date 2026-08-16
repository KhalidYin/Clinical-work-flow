import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { HttpResponse, http } from "msw";

import { API_PATHS, CONTRACT_VERSION, resolveApiPath } from "../contracts/knowledgeApi";
import { server } from "../mocks/server";
import { createAppRouter } from "../router";

const meta = {
  contractVersion: CONTRACT_VERSION,
  fixture: true,
  generatedAt: "2026-08-16T14:00:00Z",
};

function renderApp(initialEntry: string) {
  const history = createMemoryHistory({ initialEntries: [initialEntry] });
  const router = createAppRouter(history);
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { router };
}

const chunkProjection = {
  runId: "run-chunk-001",
  sourceVersionId: "srcv-e9-v1",
  chunkProfile: {
    chunkProfileId: "chunk-profile-e9-v1",
    version: "1.0.0",
    tokenizerId: "deterministic-word-v1",
    targetMinTokens: 80,
    targetMaxTokens: 220,
    hardMaxTokens: 320,
    overlapTokens: 32,
    tableHardMaxTokens: 420,
    formatRules: { preserve_tables: true },
  },
  evidence: [
    {
      evidenceId: "evidence-01",
      sourceVersionId: "srcv-e9-v1",
      sourceArtifactId: "artifact-e9-v1",
      evidenceType: "prose",
      locator: { page: 8, section: "2.1" },
      content: "第一段证据",
      contentSha256: "a".repeat(64),
    },
    {
      evidenceId: "evidence-02",
      sourceVersionId: "srcv-e9-v1",
      sourceArtifactId: "artifact-e9-v1",
      evidenceType: "prose",
      locator: { page: 9, section: "2.2" },
      content: "第二段证据",
      contentSha256: "b".repeat(64),
    },
  ],
  chunks: [
    {
      chunkId: "chunk-01",
      ordinal: 0,
      evidenceType: "prose",
      content: "第一检索块",
      contentSha256: "c".repeat(64),
      tokenCount: 180,
      locator: { page: 8 },
      dataBoundary: "local_processing_only",
      rights: { classification: "licensed" },
      spans: [
        {
          evidenceId: "evidence-01",
          position: 0,
          startOffset: 0,
          endOffset: 6,
          spanRole: "primary",
        },
      ],
    },
    {
      chunkId: "chunk-02",
      ordinal: 1,
      evidenceType: "prose",
      content: "第二检索块",
      contentSha256: "d".repeat(64),
      tokenCount: 200,
      locator: { page: 9 },
      dataBoundary: "local_processing_only",
      rights: { classification: "licensed" },
      spans: [
        {
          evidenceId: "evidence-02",
          position: 0,
          startOffset: 0,
          endOffset: 6,
          spanRole: "primary",
        },
        {
          evidenceId: "evidence-01",
          position: 1,
          startOffset: 4,
          endOffset: 6,
          spanRole: "overlap",
        },
      ],
    },
  ],
  findings: [
    {
      findingId: "finding-01",
      evidenceId: "evidence-02",
      findingType: "boilerplate",
      details: { reason: "footer" },
    },
  ],
};

function rotationCase(overrides: Record<string, unknown> = {}) {
  return {
    rotationCaseId: "rotation-001",
    impactAssessmentId: "impact-001",
    knowledgeRevisionId: "revision-released-001",
    status: "open",
    changeTypes: ["rights_changed"],
    eligibleOutcomes: ["replace", "retire", "no_action"],
    proposedOutcome: null,
    proposedTargetKnowledgeRevisionId: null,
    proposedByActorId: null,
    proposedRationale: null,
    caseVersion: 1,
    includedReleaseId: null,
    releasedInReleaseIds: ["release-001"],
    receipts: [],
    allowedActions: ["propose"],
    createdAt: "2026-08-16T10:00:00Z",
    updatedAt: "2026-08-16T10:00:00Z",
    ...overrides,
  };
}

describe("P17 lifecycle governance UI", () => {
  it("restores Run/Evidence/Chunk URL state and navigates both directions without editing chunks", async () => {
    let projectionCalls = 0;
    server.use(
      http.get(
        resolveApiPath(`${API_PATHS.processingRuns}/run-chunk-001/chunk-projection`),
        () => {
          projectionCalls += 1;
          return HttpResponse.json({ data: chunkProjection, meta });
        },
      ),
    );

    const { router } = renderApp(
      "/processing?run=run-chunk-001&evidence=evidence-02&chunk=chunk-02",
    );

    expect(await screen.findByRole("heading", { name: "Evidence 与 Chunk Inspector" })).toBeInTheDocument();
    expect(await screen.findByText("第二段证据")).toBeInTheDocument();
    expect(screen.getByText("第二检索块")).toBeInTheDocument();
    expect(screen.getByText("200 tokens")).toBeInTheDocument();
    expect(screen.getByText("Overlap 32")).toBeInTheDocument();
    expect(screen.getByText("boilerplate")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /编辑 Chunk/i })).not.toBeInTheDocument();
    expect(projectionCalls).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: /Evidence evidence-01/i }));
    await waitFor(() => {
      expect(router.state.location.search).toMatchObject({
        run: "run-chunk-001",
        evidence: "evidence-01",
        chunk: "chunk-01",
      });
    });
    fireEvent.click(screen.getByRole("button", { name: /Chunk chunk-02/i }));
    await waitFor(() => {
      expect(router.state.location.search).toMatchObject({
        evidence: "evidence-02",
        chunk: "chunk-02",
      });
    });
  });

  it("submits only a server-allowed rotation proposal and refreshes canonical case facts", async () => {
    let proposalBody: Record<string, unknown> | null = null;
    const proposed = rotationCase({
      status: "in_review",
      proposedOutcome: "retire",
      proposedByActorId: "usr-curator",
      proposedRationale: "rights boundary changed",
      caseVersion: 2,
      allowedActions: [],
    });
    server.use(
      http.get(resolveApiPath(API_PATHS.session), () =>
        HttpResponse.json({
          data: {
            actorId: "usr-curator",
            displayName: "Curator",
            principalType: "human",
            roles: ["knowledge_curator"],
            organization: "Clinical Knowledge Lab",
            permissions: ["candidate:read", "candidate:write"],
            mustChangePassword: false,
            sessionExpiresAt: "2026-08-17T00:00:00Z",
          },
          meta,
        }),
      ),
      http.get(resolveApiPath("/api/prerelease/v1/rotation-cases"), () =>
        HttpResponse.json({
          data: { items: [rotationCase()], total: 1, partial: false, warnings: [] },
          meta,
        }),
      ),
      http.get(resolveApiPath("/api/prerelease/v1/rotation-cases/rotation-001"), () =>
        HttpResponse.json({ data: proposalBody ? proposed : rotationCase(), meta }),
      ),
      http.post(
        resolveApiPath("/api/prerelease/v1/rotation-cases/rotation-001/proposal"),
        async ({ request }) => {
          proposalBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({ data: proposed, meta });
        },
      ),
    );

    const { router } = renderApp(
      "/candidates?view=rotation&status=open&case=rotation-001",
    );

    expect((await screen.findAllByText("rights_changed")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("revision-released-001").length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText("拟议动作"), { target: { value: "retire" } });
    fireEvent.change(screen.getByLabelText("提议理由"), {
      target: { value: "rights boundary changed" },
    });
    fireEvent.click(screen.getByRole("button", { name: "提交轮转提议" }));

    await waitFor(() => expect(proposalBody).not.toBeNull());
    expect(proposalBody).toMatchObject({
      expectedCaseVersion: 1,
      outcome: "retire",
      targetKnowledgeRevisionId: null,
      rationale: "rights boundary changed",
    });
    expect(String((proposalBody as unknown as Record<string, unknown>).idempotencyKey)).toMatch(
      /^ui:rotation-proposal:/,
    );
    expect(await screen.findByText("轮转提议已记录")).toBeInTheDocument();
    expect(router.state.location.search).toMatchObject({
      view: "rotation",
      status: "open",
      case: "rotation-001",
    });
  });

  it("shows the unique decision receipt and refreshes after a stale rotation conflict", async () => {
    let detailCalls = 0;
    let decisionCalls = 0;
    const inReview = rotationCase({
      status: "in_review",
      proposedOutcome: "retire",
      proposedByActorId: "usr-curator",
      proposedRationale: "rights boundary changed",
      allowedActions: ["decide"],
    });
    const receipt = {
      rotationDecisionId: "rotation-decision-001",
      rotationCaseId: "rotation-001",
      outcome: "retire",
      expectedCaseVersion: 1,
      targetKnowledgeRevisionId: null,
      actorId: "usr-reviewer",
      actorRole: "reviewer",
      idempotencyKey: "ui:rotation-decision:rotation-001:1",
      rationale: "independent review complete",
      createdAt: "2026-08-16T12:00:00Z",
    };
    server.use(
      http.get(resolveApiPath(API_PATHS.session), () =>
        HttpResponse.json({
          data: {
            actorId: "usr-reviewer",
            displayName: "Reviewer",
            principalType: "human",
            roles: ["reviewer"],
            organization: "Clinical Knowledge Lab",
            permissions: ["candidate:read", "review:decide"],
            mustChangePassword: false,
            sessionExpiresAt: "2026-08-17T00:00:00Z",
          },
          meta,
        }),
      ),
      http.get(resolveApiPath("/api/prerelease/v1/rotation-cases"), () =>
        HttpResponse.json({
          data: { items: [inReview], total: 1, partial: false, warnings: [] },
          meta,
        }),
      ),
      http.get(resolveApiPath("/api/prerelease/v1/rotation-cases/rotation-001"), () => {
        detailCalls += 1;
        return HttpResponse.json({ data: inReview, meta });
      }),
      http.post(
        resolveApiPath("/api/prerelease/v1/rotation-cases/rotation-001/decision"),
        () => {
          decisionCalls += 1;
          if (decisionCalls === 1) {
            return HttpResponse.json(
              {
                error: { code: "stale_rotation_case", message: "case changed" },
                meta,
              },
              { status: 409 },
            );
          }
          return HttpResponse.json({
            data: {
              case: rotationCase({
                status: "decided",
                proposedOutcome: "retire",
                receipts: [receipt],
                allowedActions: [],
              }),
              receipt,
            },
            meta,
          });
        },
      ),
    );

    renderApp("/candidates?view=rotation&status=in_review&case=rotation-001");
    expect(await screen.findByRole("button", { name: "确认轮转决定" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("决定理由"), {
      target: { value: "independent review complete" },
    });
    fireEvent.click(screen.getByRole("button", { name: "确认轮转决定" }));
    expect(await screen.findByText("RotationCase 已变化")).toBeInTheDocument();
    await waitFor(() => expect(detailCalls).toBeGreaterThan(1));

    fireEvent.click(screen.getByRole("button", { name: "确认轮转决定" }));
    expect((await screen.findAllByText("rotation-decision-001")).length).toBeGreaterThan(0);
    expect(screen.getByText("独立审核决定已记录")).toBeInTheDocument();
  });
});
