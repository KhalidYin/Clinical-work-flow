import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { HttpResponse, http } from "msw";

import {
  CONTRACT_VERSION,
  impactAssessmentPath,
  resolveApiPath,
  sourceHistoryPath,
  sourceImpactAssessmentsPath,
} from "../contracts/knowledgeApi";
import { server } from "../mocks/server";
import { createAppRouter } from "../router";

const meta = {
  contractVersion: CONTRACT_VERSION,
  fixture: true,
  generatedAt: "2026-08-16T14:20:00Z",
};

const changeCounts = {
  unchanged: 0,
  moved: 0,
  modified: 1,
  added: 0,
  removed: 0,
  rights_changed: 0,
  ambiguous: 0,
};

const assessment = {
  assessmentId: "impact-ui-001",
  fromSourceVersionId: "srcv-ui-old",
  toSourceVersionId: "srcv-ui-new",
  comparisonProfileVersion: "evidence-comparison-v1",
  changeCounts,
  impactSummary: { affectedKnowledgeCount: 1, rotationCaseCount: 1 },
  impacts: [
    {
      evidenceImpactId: "eimpact-ui-001",
      changeType: "modified",
      fromEvidenceId: "evidence-ui-old",
      toEvidenceId: "evidence-ui-new",
      mappingBasis: "locator_exact",
      details: { section: "6.2" },
    },
  ],
  createdAt: "2026-08-16T14:20:00Z",
};

const history = {
  sourceId: "src-sdtmig-34",
  title: "Study Data Tabulation Model Implementation Guide",
  versions: [
    {
      sourceVersionId: "srcv-ui-new",
      version: "3.4",
      status: "registered",
      rights: { classification: "licensed", storageAllowed: true },
      dataBoundary: "enterprise_provider_only",
      sourceHash: "a".repeat(64),
      effectiveDate: null,
      createdAt: "2026-08-16T14:00:00Z",
    },
    {
      sourceVersionId: "srcv-ui-old",
      version: "3.3",
      status: "released",
      rights: { classification: "licensed", storageAllowed: true },
      dataBoundary: "enterprise_provider_only",
      sourceHash: "b".repeat(64),
      effectiveDate: null,
      createdAt: "2025-08-16T14:00:00Z",
    },
  ],
  comparisons: [assessment],
  allowedActions: ["compare"],
  partial: false,
  warnings: [],
};

function renderApp(initialEntry: string) {
  const historyState = createMemoryHistory({ initialEntries: [initialEntry] });
  const router = createAppRouter(historyState);
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

describe("SourceVersion lifecycle governance", () => {
  it("restores source/version/assessment URL and shows server counts and impacts", async () => {
    server.use(
      http.get(resolveApiPath(sourceHistoryPath(history.sourceId)), () =>
        HttpResponse.json({ data: history, meta }),
      ),
      http.get(resolveApiPath(impactAssessmentPath(assessment.assessmentId)), () =>
        HttpResponse.json({ data: assessment, meta }),
      ),
    );
    const { router } = renderApp(
      "/sources?q=&source=src-sdtmig-34&from=srcv-ui-old&to=srcv-ui-new&assessment=impact-ui-001&change=modified",
    );

    expect(await screen.findByRole("heading", { name: "版本与影响" })).toBeInTheDocument();
    expect(await screen.findAllByRole("option", { name: "3.3 · srcv-ui-old" })).toHaveLength(2);
    expect(screen.getAllByRole("option", { name: "3.4 · srcv-ui-new" })).toHaveLength(2);
    expect(screen.getByText("受影响知识 1")).toBeInTheDocument();
    expect(screen.getByText("RotationCase 1")).toBeInTheDocument();
    expect(screen.getByText("evidence-ui-old → evidence-ui-new")).toBeInTheDocument();
    expect(router.state.location.search).toMatchObject({
      source: "src-sdtmig-34",
      from: "srcv-ui-old",
      to: "srcv-ui-new",
      assessment: "impact-ui-001",
      change: "modified",
    });
  });

  it("submits only version identities and uses the server-profiled result", async () => {
    let submitted: unknown = null;
    server.use(
      http.get(resolveApiPath(sourceHistoryPath(history.sourceId)), () =>
        HttpResponse.json({ data: history, meta }),
      ),
      http.post(
        resolveApiPath(sourceImpactAssessmentsPath(history.sourceId)),
        async ({ request }) => {
          submitted = await request.json();
          return HttpResponse.json({ data: assessment, meta });
        },
      ),
      http.get(resolveApiPath(impactAssessmentPath(assessment.assessmentId)), () =>
        HttpResponse.json({ data: assessment, meta }),
      ),
    );
    const { router } = renderApp(
      "/sources?q=&source=src-sdtmig-34&from=srcv-ui-old&to=srcv-ui-new",
    );

    fireEvent.click(await screen.findByRole("button", { name: "启动版本比较" }));

    await waitFor(() => {
      expect(submitted).toEqual({
        fromSourceVersionId: "srcv-ui-old",
        toSourceVersionId: "srcv-ui-new",
      });
    });
    expect(await screen.findByText("比较已完成；结果来自服务端固定 Profile。"))
      .toBeInTheDocument();
    await waitFor(() => {
      expect(router.state.location.search).toMatchObject({
        assessment: "impact-ui-001",
      });
    });
  });
});
