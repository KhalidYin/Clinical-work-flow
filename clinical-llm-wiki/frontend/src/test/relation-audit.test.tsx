import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { HttpResponse, http } from "msw";

import { API_PATHS, resolveApiPath } from "../contracts/knowledgeApi";
import { relationQueryFixture, sourcesFixture } from "../mocks/fixtures";
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
});

describe("KUI-10 Audit ledger", () => {
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
