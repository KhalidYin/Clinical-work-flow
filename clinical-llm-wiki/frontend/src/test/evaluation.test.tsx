import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { HttpResponse, http } from "msw";

import { API_PATHS, resolveApiPath } from "../contracts/knowledgeApi";
import { server } from "../mocks/server";
import { createAppRouter } from "../router";

const meta = {
  contractVersion: "knowledge-api.prerelease.v1",
  fixture: false,
  generatedAt: "2026-08-16T08:02:00Z",
};

const summary = {
  evaluationRunId: "evaluation-e9-api-001",
  suiteId: "ich-e9-retrieval-gold",
  suiteVersion: "1.0.0",
  purpose: "retrieval_baseline",
  targetId: "srcv-e9",
  status: "completed",
  outcome: "informational",
  caseCount: 18,
  metrics: { recallAt5: 0.888889, recallAt10: 0.944444 },
  externalModelRequests: 0,
  evaluationNotice: "single_document_retrieval_baseline_not_clinical_quality_certification",
  startedAt: "2026-08-16T08:00:00Z",
  completedAt: "2026-08-16T08:01:00Z",
};

function renderApp(initialEntry = "/evaluation?suite=&run=&outcome=&baseline=") {
  const history = createMemoryHistory({ initialEntries: [initialEntry] });
  const router = createAppRouter(history);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { router };
}

describe("P17 Evaluation governance", () => {
  it("renders authoritative E9 metrics and does not invent a release threshold", async () => {
    let listUrl = "";
    server.use(
      http.get(resolveApiPath(API_PATHS.evaluations), ({ request }) => {
        listUrl = request.url;
        return HttpResponse.json({
          data: { items: [summary], total: 1, partial: false, warnings: [] },
          meta,
        });
      }),
      http.get(resolveApiPath(`${API_PATHS.evaluations}/:runId`), () =>
        HttpResponse.json({
          data: {
            ...summary,
            thresholdChecks: [],
            failureReasons: [],
            caseResults: [
              {
                caseId: "e9-randomisation-bias",
                topic: "Randomisation",
                question: "How does randomisation reduce selection bias?",
                queryId: "query-e9-randomisation",
                outcome: "expected_not_in_top_10",
                failureCategory: "expected_not_retrieved",
                hitAt5: false,
                hitAt10: false,
                firstRelevantRank: null,
                expectedEvidenceIds: ["evidence-e9-randomisation"],
                retrievedEvidenceIds: [],
                replay: {
                  queryLabPath: "/query-lab",
                  evaluationRunId: "evaluation-e9-api-001",
                  caseId: "e9-randomisation-bias",
                  query: "How does randomisation reduce selection bias?",
                  releaseId: null,
                  topK: 10,
                  availability: "candidate_scope_required",
                },
              },
            ],
          },
          meta,
        }),
      ),
    );

    renderApp();

    expect(await screen.findByRole("heading", { name: "质量评估" })).toBeInTheDocument();
    expect(await screen.findByText("88.8889%")).toBeInTheDocument();
    expect(screen.getByText("94.4444%")).toBeInTheDocument();
    expect(screen.getByText("未定义发布阈值")).toBeInTheDocument();
    expect(screen.getByText(/不是临床质量认证/)).toBeInTheDocument();
    expect(await screen.findByText("expected_not_retrieved")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重放此问题" })).toBeDisabled();
    expect(screen.getByText("需要 release-candidate Query Lab scope")).toBeInTheDocument();
    expect(listUrl).toContain("purpose=retrieval_baseline");
  });

  it("starts only a server-registered suite and selects the immutable run", async () => {
    let startBody: Record<string, unknown> | null = null;
    server.use(
      http.get(resolveApiPath(API_PATHS.evaluations), () =>
        HttpResponse.json({
          data: {
            items: [summary],
            total: 1,
            partial: false,
            warnings: [],
            availableSuites: [
              {
                suiteId: "ich-e9-retrieval-gold",
                suiteVersion: "1.0.0",
                documentId: "ICH-E9-1998",
                sourceVersionId: "srcv-e9",
                chunkProfileId: "chunk-profile-ich-e9-poc-v1",
                caseCount: 18,
                sandboxKind: "release_candidate",
                externalModelRequests: 0,
              },
            ],
            allowedActions: ["start"],
          },
          meta,
        }),
      ),
      http.post(resolveApiPath(`${API_PATHS.evaluations}/runs`), async ({ request }) => {
        startBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({
          data: {
            ...summary,
            evaluationRunId: "evaluation-e9-api-002",
            thresholdChecks: [],
            failureReasons: [],
            caseResults: [],
          },
          meta,
        });
      }),
    );

    const { router } = renderApp();

    fireEvent.click(await screen.findByRole("button", { name: "运行所选 Suite" }));

    await waitFor(() => {
      expect(startBody).toEqual({
        suiteId: "ich-e9-retrieval-gold",
        suiteVersion: "1.0.0",
      });
    });
    await waitFor(() => {
      expect(router.state.location.search).toMatchObject({
        suite: "ich-e9-retrieval-gold",
        run: "evaluation-e9-api-002",
      });
    });
    expect(screen.queryByLabelText(/SourceVersion/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/ChunkProfile/i)).not.toBeInTheDocument();
  });

  it("routes an available failed case to server-scoped Query Lab replay", async () => {
    server.use(
      http.get(resolveApiPath(`${API_PATHS.evaluations}/:runId`), () =>
        HttpResponse.json({
          data: {
            ...summary,
            thresholdChecks: [],
            failureReasons: [],
            caseResults: [
              {
                caseId: "e9-randomisation-bias",
                topic: "Randomisation",
                question: "How does randomisation reduce selection bias?",
                queryId: "query-e9-randomisation",
                outcome: "expected_not_in_top_10",
                failureCategory: "expected_not_retrieved",
                hitAt5: false,
                hitAt10: false,
                firstRelevantRank: null,
                expectedEvidenceIds: ["evidence-e9-randomisation"],
                retrievedEvidenceIds: [],
                replay: {
                  queryLabPath: "/query-lab",
                  evaluationRunId: "evaluation-e9-api-001",
                  caseId: "e9-randomisation-bias",
                  query: "How does randomisation reduce selection bias?",
                  releaseId: null,
                  topK: 10,
                  availability: "available",
                },
              },
            ],
          },
          meta,
        }),
      ),
    );
    const { router } = renderApp();

    fireEvent.click(await screen.findByRole("button", { name: "重放此问题" }));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe("/query-lab");
      expect(router.state.location.search).toMatchObject({
        scope: "evaluation",
        evaluation: "evaluation-e9-api-001",
        case: "e9-randomisation-bias",
        q: "How does randomisation reduce selection bias?",
      });
    });
  });

  it("renders the server-computed immutable run regression", async () => {
    server.use(
      http.get(resolveApiPath(API_PATHS.evaluations), () =>
        HttpResponse.json({
          data: {
            items: [
              summary,
              { ...summary, evaluationRunId: "evaluation-e9-api-000" },
            ],
            total: 2,
            partial: false,
            warnings: [],
            availableSuites: [],
            allowedActions: [],
          },
          meta,
        }),
      ),
      http.get(
        resolveApiPath(`${API_PATHS.evaluations}/:runId/regression`),
        ({ request }) => {
          expect(new URL(request.url).searchParams.get("baseline_run_id")).toBe(
            "evaluation-e9-api-000",
          );
          return HttpResponse.json({
            data: {
              evaluationRunId: "evaluation-e9-api-001",
              baselineRunId: "evaluation-e9-api-000",
              suiteId: "ich-e9-retrieval-gold",
              currentSuiteVersion: "1.0.0",
              baselineSuiteVersion: "0.9.0",
              metricDeltas: { recallAt5: 0.055556, recallAt10: 0 },
              counts: { improved: 1, regressed: 0, unchanged: 17, added: 0, removed: 0 },
              caseDiffs: [
                {
                  caseId: "e9-randomisation-bias",
                  change: "improved",
                  baselineOutcome: "expected_not_in_top_10",
                  currentOutcome: "hit_top_5",
                  baselineRank: null,
                  currentRank: 1,
                },
              ],
            },
            meta,
          });
        },
      ),
    );

    renderApp(
      "/evaluation?suite=&run=evaluation-e9-api-001&outcome=&baseline=evaluation-e9-api-000",
    );

    expect(await screen.findByText("Recall@5 +5.5556%")).toBeInTheDocument();
    expect(screen.getByText("改进 1 · 退化 0 · 不变 17")).toBeInTheDocument();
    expect(screen.getByText("e9-randomisation-bias").closest("li")).toHaveTextContent(
      "improved",
    );
  });

  it("persists suite, run and outcome filters in the URL", async () => {
    const { router } = renderApp();
    await screen.findByText("88.8889%");

    fireEvent.change(screen.getByLabelText("Suite"), {
      target: { value: "ich-e9-retrieval-gold" },
    });
    fireEvent.change(screen.getByLabelText("Outcome"), {
      target: { value: "informational" },
    });

    await waitFor(() => {
      expect(router.state.location.search).toMatchObject({
        suite: "ich-e9-retrieval-gold",
        run: "evaluation-e9-api-001",
        outcome: "informational",
      });
    });
  });

  it("keeps empty and error states explicit without falling back to a report file", async () => {
    server.use(
      http.get(resolveApiPath(API_PATHS.evaluations), () =>
        HttpResponse.json({
          data: { items: [], total: 0, partial: false, warnings: [] },
          meta,
        }),
      ),
    );
    renderApp();
    expect(await screen.findByText("没有匹配的 EvaluationRun")).toBeInTheDocument();
    cleanup();

    server.use(
      http.get(resolveApiPath(API_PATHS.evaluations), () =>
        HttpResponse.json({ error: { code: "service_unavailable", message: "down" }, meta }, { status: 503 }),
      ),
    );
    renderApp();
    expect(await screen.findByText("无法读取评估记录")).toBeInTheDocument();
    expect(screen.getByText(/没有回退到本地报告/)).toBeInTheDocument();
  });

  it("surfaces partial integrity warnings returned by the API", async () => {
    server.use(
      http.get(resolveApiPath(API_PATHS.evaluations), () =>
        HttpResponse.json({
          data: {
            items: [summary],
            total: 1,
            partial: true,
            warnings: ["evaluation_run_invalid:evaluation-drifted"],
          },
          meta,
        }),
      ),
    );
    renderApp();

    expect(await screen.findByText(/evaluation_run_invalid:evaluation-drifted/)).toBeInTheDocument();
  });
});
