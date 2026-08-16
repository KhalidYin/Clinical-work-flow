import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { HttpResponse, http } from "msw";

import { API_PATHS, resolveApiPath } from "../contracts/knowledgeApi";
import { releasedQueryFixture } from "../mocks/fixtures";
import { server } from "../mocks/server";
import { createAppRouter } from "../router";

function renderApp(initialEntry = "/query-lab?q=&release=&top_k=10") {
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
  return { router };
}

describe("P17 Query Lab", () => {
  it("does not query on an empty default and restores submitted state from the URL", async () => {
    let calls = 0;
    let receivedBody: Record<string, unknown> | null = null;
    server.use(
      http.post(resolveApiPath(API_PATHS.releasedQuery), async ({ request }) => {
        calls += 1;
        receivedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(releasedQueryFixture);
      }),
    );
    const { router } = renderApp();

    expect(await screen.findByRole("heading", { name: "检索实验室" })).toBeInTheDocument();
    expect(calls).toBe(0);
    fireEvent.change(screen.getByRole("searchbox", { name: "查询已发布知识" }), {
      target: { value: "randomisation selection bias" },
    });
    fireEvent.change(screen.getByLabelText("Release ID（留空使用 current）"), {
      target: { value: "rel-historical" },
    });
    fireEvent.change(screen.getByLabelText("返回数量"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "查询 immutable Release" }));

    await waitFor(() => expect(calls).toBe(1));
    expect(receivedBody).toEqual({
      query: "randomisation selection bias",
      topK: 5,
      releaseId: "rel-historical",
    });
    await waitFor(() => {
      expect(router.state.location.search).toEqual({
        q: "randomisation selection bias",
        release: "rel-historical",
        top_k: 5,
      });
    });
  });

  it("renders API rank, degraded routes and canonical Evidence without recomputing", async () => {
    renderApp("/query-lab?q=randomisation&release=rel-historical&top_k=5");

    expect(await screen.findByText("第 7 位")).toBeInTheDocument();
    expect(screen.getByText("向量检索").closest("article")).toHaveTextContent(
      "embedding_profile_not_configured",
    );
    expect(screen.getByText("关系扩展").closest("article")).toHaveTextContent(
      "relation_route_not_enabled_for_e9_poc",
    );
    expect(screen.getByText("零外部模型请求")).toBeInTheDocument();
    fireEvent.click(screen.getByText("查看 Evidence 引用与 Chunk 解释"));
    expect(screen.getByText("evidence-e9-randomisation")).toBeInTheDocument();
    expect(screen.getAllByText(/第 8 页/)).toHaveLength(2);
    expect(screen.getByText("单文档检索基线，不是临床质量认证")).toBeInTheDocument();
  });
});
