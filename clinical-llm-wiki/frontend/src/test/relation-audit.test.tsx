import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { HttpResponse, http } from "msw";

import { API_PATHS, resolveApiPath } from "../contracts/knowledgeApi";
import {
  auditEventsFixture,
  relationDirectoryFixture,
  relationQueryFixture,
  sourcesFixture,
} from "../mocks/fixtures";
import { server } from "../mocks/server";
import { createAppRouter } from "../router";

function renderApp(initialEntry: string) {
  const history = createMemoryHistory({ initialEntries: [initialEntry] });
  const router = createAppRouter(history);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

describe("KUI-05 Relation Explorer", () => {
  it("keeps selected node, depth and view in URL state and shows edge evidence", async () => {
    const router = renderApp("/relations?q=&node=&depth=1&view=paths");

    fireEvent.click(await screen.findByRole("button", { name: /sdtm\.domain\.ae/i }));

    expect(
      await screen.findByText("AESEQ uniquely identifies a record within the AE domain."),
    ).toBeInTheDocument();
    expect(screen.getByText("适用于")).toBeInTheDocument();
    expect(
      screen.getAllByText(/发布版本 · rel-2026-07-29-001/).length,
    ).toBeGreaterThan(0);
    await waitFor(() =>
      expect(router.state.location.search.node).toBe("KU-SDTM-AE"),
    );

    fireEvent.click(screen.getByRole("button", { name: "2 跳" }));
    fireEvent.click(screen.getByRole("button", { name: "列表" }));
    await waitFor(() => {
      expect(router.state.location.search.depth).toBe(2);
      expect(router.state.location.search.view).toBe("list");
    });
    expect(
      await screen.findByRole("columnheader", { name: "方向" }),
    ).toBeInTheDocument();
  });

  it("surfaces a partial relation result instead of hiding missing edges", async () => {
    server.use(
      http.get(resolveApiPath(API_PATHS.relationQuery), ({ request }) => {
        const nodeId = new URL(request.url).searchParams.get("node_id");
        if (!nodeId) {
          return HttpResponse.json({
            ...relationQueryFixture,
            data: {
              ...relationQueryFixture.data,
              rootNodeId: null,
              edges: [],
            },
          });
        }
        return HttpResponse.json({
          ...relationQueryFixture,
          data: {
            ...relationQueryFixture.data,
            rootNodeId: nodeId,
            edges: [],
            partial: true,
            warnings: ["relation rel-missing has no readable evidence"],
          },
        });
      }),
    );
    renderApp("/relations?node=KU-SDTM-AE&depth=1&view=paths&q=");

    expect(
      await screen.findByText("relation rel-missing has no readable evidence"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("没有带 Evidence 的相邻关系"),
    ).toBeInTheDocument();
  });

  it("renders server-projected lifecycle lineage and preserves the release in URL", async () => {
    let requestedRelease: string | null = null;
    server.use(
      http.get(resolveApiPath(API_PATHS.relationQuery), ({ request }) => {
        const url = new URL(request.url);
        const nodeId = url.searchParams.get("node_id");
        if (!nodeId) return HttpResponse.json(relationDirectoryFixture);
        requestedRelease = url.searchParams.get("release_id");
        return HttpResponse.json({
          ...relationQueryFixture,
          data: {
            ...relationQueryFixture.data,
            rootNodeId: nodeId,
            lifecycle: {
              rootKnowledgeRevisionId: "KREV-SDTM-AE-003",
              selectedReleaseId: "rel-2026-07-29-001",
              nodes: [
                {
                  nodeId: "srcv-sdtmig-34",
                  nodeType: "source_version",
                  label: "SDTMIG 3.4",
                  status: "parsed",
                  derived: false,
                },
                {
                  nodeId: "evidence-ui-aeseq-001",
                  nodeType: "evidence",
                  label: "Evidence 6.2 AE",
                  status: "canonical",
                  derived: false,
                },
                {
                  nodeId: "chunk-ui-aeseq-001",
                  nodeType: "retrieval_chunk",
                  label: "Chunk 12",
                  status: "available",
                  derived: true,
                },
                {
                  nodeId: "KREV-SDTM-AE-003",
                  nodeType: "knowledge_revision",
                  label: "sdtm.domain.ae · r3",
                  status: "released",
                  derived: false,
                },
                {
                  nodeId: "rel-2026-07-29-001",
                  nodeType: "release",
                  label: "2026.07-d0",
                  status: "released",
                  derived: false,
                },
              ],
              edges: [
                {
                  sourceNodeId: "srcv-sdtmig-34",
                  targetNodeId: "evidence-ui-aeseq-001",
                  relationType: "contains",
                },
                {
                  sourceNodeId: "evidence-ui-aeseq-001",
                  targetNodeId: "chunk-ui-aeseq-001",
                  relationType: "projected_as",
                },
                {
                  sourceNodeId: "evidence-ui-aeseq-001",
                  targetNodeId: "KREV-SDTM-AE-003",
                  relationType: "supports",
                },
                {
                  sourceNodeId: "KREV-SDTM-AE-003",
                  targetNodeId: "rel-2026-07-29-001",
                  relationType: "included_in",
                },
              ],
              releaseMembership: [
                {
                  releaseId: "rel-2026-07-29-001",
                  version: "2026.07-d0",
                  status: "released",
                  current: true,
                },
              ],
              partial: false,
              warnings: [],
            },
          },
        });
      }),
    );
    const router = renderApp(
      "/relations?q=&node=KU-SDTM-AE&depth=1&view=paths&release=rel-2026-07-29-001",
    );

    expect(
      await screen.findByRole("heading", { name: "生命周期血缘" }),
    ).toBeInTheDocument();
    expect(screen.getByText("检索投影 · derived")).toBeInTheDocument();
    expect(screen.getByText("2026.07-d0 · current")).toBeInTheDocument();
    expect(requestedRelease).toBe("rel-2026-07-29-001");
    expect(router.state.location.search).toMatchObject({
      release: "rel-2026-07-29-001",
    });
  });
});

describe("KUI-10 Audit ledger", () => {
  it("keeps entity, case and release filters in URL and opens the server target", async () => {
    const requested: Record<string, string | null> = {};
    server.use(
      http.get(resolveApiPath(API_PATHS.auditEvents), ({ request }) => {
        const url = new URL(request.url);
        requested.entity = url.searchParams.get("entity_id");
        requested.case = url.searchParams.get("case_id");
        requested.release = url.searchParams.get("release_id");
        return HttpResponse.json({
          ...auditEventsFixture,
          data: {
            ...auditEventsFixture.data,
            total: 1,
            items: [
              {
                auditEventId: "audit-rotation-ui-001",
                actorId: "usr-review-002",
                action: "rotation_case.decided",
                objectType: "rotation_case",
                objectId: "rotation-001",
                runId: null,
                beforeVersion: null,
                afterVersion: null,
                result: "approved",
                correlationId: "rotation-decision-001",
                createdAt: "2026-08-20T08:00:00Z",
                authoritativeTarget: {
                  resourceType: "rotation_case",
                  resourceId: "rotation-001",
                  path: "/candidates?view=rotation&status=&case=rotation-001",
                },
              },
            ],
          },
        });
      }),
    );
    const router = renderApp(
      "/audit?actor=&action=&objectType=&result=&entity=impact-001&case=rotation-001&release=rel-001&cursor=&event=",
    );

    expect(await screen.findByText("rotation-decision-001")).toBeInTheDocument();
    expect(requested).toEqual({
      entity: "impact-001",
      case: "rotation-001",
      release: "rel-001",
    });
    expect(router.state.location.search).toMatchObject({
      entity: "impact-001",
      case: "rotation-001",
      release: "rel-001",
    });
    expect(screen.getByRole("link", { name: "打开权威对象" })).toHaveAttribute(
      "href",
      "#/candidates?view=rotation&status=&case=rotation-001",
    );
  });

  it("stores filters and selection in URL and exposes only the read-only projection", async () => {
    const router = renderApp(
      "/audit?actor=&action=&objectType=&result=&cursor=&event=",
    );

    expect(
      await screen.findByRole("heading", { name: "knowledge_revision.approved" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /knowledge_revision\.approved/i }));
    expect(await screen.findByText("review-aeseq-002")).toBeInTheDocument();
    expect(screen.getByText(/只追加投影/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit|delete/i })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("动作"), {
      target: { value: "author_confirmed" },
    });
    await waitFor(() =>
      expect(router.state.location.search.action).toBe("author_confirmed"),
    );
    expect(
      await screen.findByRole("heading", {
        name: "knowledge_candidate.author_confirmed",
      }),
    ).toBeInTheDocument();
  });

  it("fails visibly when audit permission or repository access is denied", async () => {
    server.use(
      http.get(resolveApiPath(API_PATHS.auditEvents), () =>
        HttpResponse.json(
          {
            error: {
              code: "permission_denied",
              message: "The current actor does not have this permission.",
            },
            meta: sourcesFixture.meta,
          },
          { status: 403 },
        ),
      ),
    );
    renderApp("/audit");

    expect(await screen.findByText("无法读取审计账本")).toBeInTheDocument();
    expect(
      screen.getByText(/页面不会回退到本地假数据/),
    ).toBeInTheDocument();
  });
});
