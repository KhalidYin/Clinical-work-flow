import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { HttpResponse, http } from "msw";

import { API_PATHS, resolveApiPath } from "../contracts/knowledgeApi";
import { sourcesFixture } from "../mocks/fixtures";
import { server } from "../mocks/server";
import { createAppRouter } from "../router";

function renderQueryLab(initialEntry: string) {
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

describe("KUI-06 Query Lab", () => {
  it("starts explicitly, writes the submitted query to URL and renders backend ranking", async () => {
    const router = renderQueryLab(
      "/query-lab?q=&visibility=released&type=&domain=&depth=1&vector=true",
    );

    expect(
      await screen.findByText("Start with a claim, concept or identifier"),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox", { name: "Knowledge query" }), {
      target: { value: "AESEQ" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run query" }));

    expect(await screen.findByText("sdtm.ae.aeseq")).toBeInTheDocument();
    expect(screen.getByText("0.032522")).toBeInTheDocument();
    expect(screen.getByText("Partial capability")).toBeInTheDocument();
    expect(screen.getByText(/1 canonical citation/)).toBeInTheDocument();
    expect(screen.getByText(/Evidence evidence-ui-aeseq-001/)).toBeInTheDocument();
    expect(screen.getByText("rrf-neutral@1.0.0")).toBeInTheDocument();
    await waitFor(() => expect(router.state.location.search.q).toBe("AESEQ"));
  });

  it("distinguishes an empty result from filters that may be too narrow", async () => {
    renderQueryLab(
      "/query-lab?q=missing&type=clinical_rule&domain=AE&visibility=released&depth=1&vector=false",
    );

    expect(await screen.findByText("Filters may be too narrow")).toBeInTheDocument();
    expect(screen.getAllByText("no_matching_released_knowledge").length).toBeGreaterThan(0);
    expect(screen.getByText(/不会跨 visibility 扩大结果/)).toBeInTheDocument();
  });

  it("shows an authorization error without silently falling back to released", async () => {
    server.use(
      http.post(resolveApiPath(API_PATHS.queries), () =>
        HttpResponse.json(
          {
            error: {
              code: "permission_denied",
              message: "The current actor does not have evaluation:run.",
            },
            meta: sourcesFixture.meta,
          },
          { status: 403 },
        ),
      ),
    );
    renderQueryLab(
      "/query-lab?q=TEAE&visibility=evaluation&type=&domain=&depth=1&vector=true",
    );

    expect(await screen.findByText("Query failed")).toBeInTheDocument();
    expect(screen.getByText(/不会回退为 production 查询/)).toBeInTheDocument();
    expect(screen.queryByText("sdtm.ae.aeseq")).not.toBeInTheDocument();
  });
});
