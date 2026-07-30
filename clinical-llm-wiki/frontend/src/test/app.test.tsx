import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { delay, HttpResponse, http } from "msw";

import { API_PATHS, resolveApiPath } from "../contracts/knowledgeApi";
import { sourcesFixture } from "../mocks/fixtures";
import { server } from "../mocks/server";
import { createAppRouter } from "../router";

function renderApp(initialEntry = "/sources?q=") {
  const history = createMemoryHistory({ initialEntries: [initialEntry] });
  const router = createAppRouter(history);
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );

  return { router };
}

describe("Knowledge Ledger App Shell", () => {
  it("renders API-backed platform facts and registered sources", async () => {
    renderApp();

    expect(await screen.findByRole("heading", { name: "Sources" })).toBeInTheDocument();
    expect(await screen.findByText("2026.07-d0")).toBeInTheDocument();
    expect(screen.getByText("Kevin Dean")).toBeInTheDocument();
    expect(
      screen.getByText("Study Data Tabulation Model Implementation Guide"),
    ).toBeInTheDocument();
    expect(screen.getByText("sha256:f4b8d992a713")).toBeInTheDocument();
  });

  it("writes the source filter to URL state and filters rows", async () => {
    const { router } = renderApp();

    const input = await screen.findByRole("searchbox", { name: "Filter registered sources" });
    fireEvent.change(input, { target: { value: "ADaM" } });

    expect(await screen.findByText("Analysis Data Model Implementation Guide")).toBeInTheDocument();
    expect(
      screen.queryByText("Study Data Tabulation Model Implementation Guide"),
    ).not.toBeInTheDocument();
    await waitFor(() => expect(router.state.location.search.q).toBe("ADaM"));
  });

  it("renders an explicit loading state before source evidence arrives", async () => {
    server.use(
      http.get(resolveApiPath(API_PATHS.sources), async () => {
        await delay(80);
        return HttpResponse.json(sourcesFixture);
      }),
    );

    renderApp();

    expect(await screen.findByRole("heading", { name: "Sources" })).toBeInTheDocument();
    expect(screen.getByLabelText("正在加载来源")).toHaveAttribute("aria-busy", "true");
    expect(
      await screen.findByText("Study Data Tabulation Model Implementation Guide"),
    ).toBeInTheDocument();
  });

  it("keeps empty, error and partial source states evidence-driven", async () => {
    server.use(
      http.get(resolveApiPath(API_PATHS.sources), () =>
        HttpResponse.json({
          ...sourcesFixture,
          data: {
            items: [],
            total: 0,
            partial: false,
            warnings: [],
          },
        }),
      ),
    );
    renderApp();
    expect(await screen.findByText("尚未登记来源")).toBeInTheDocument();
    cleanup();

    server.use(
      http.get(resolveApiPath(API_PATHS.sources), () =>
        HttpResponse.json({ message: "fixture failure" }, { status: 503 }),
      ),
    );
    renderApp();
    expect(await screen.findByText("无法读取来源登记")).toBeInTheDocument();
    cleanup();

    server.use(
      http.get(resolveApiPath(API_PATHS.sources), () =>
        HttpResponse.json({
          ...sourcesFixture,
          data: {
            ...sourcesFixture.data,
            items: [sourcesFixture.data.items[0]],
            total: 5,
            partial: true,
            warnings: ["ObjectStore 状态延迟；当前仅显示已验证记录。"],
          },
        }),
      ),
    );
    renderApp();
    expect(
      await screen.findByText("ObjectStore 状态延迟；当前仅显示已验证记录。"),
    ).toBeInTheDocument();
  });

  it("registers a SourceVersion and reports the durable run without calling it Evidence", async () => {
    let receivedIdempotencyKey: string | null = null;
    server.use(
      http.post(resolveApiPath(API_PATHS.sources), ({ request }) => {
        receivedIdempotencyKey = request.headers.get("Idempotency-Key");
        return HttpResponse.json(
          {
            data: {
              sourceId: "src-ui-upload",
              sourceVersionId: "srcv-ui-upload-v1",
              runId: "run-ui-upload-v1",
              status: "queued",
              originalObject: {
                objectKey: "sources/src-ui-upload/srcv-ui-upload-v1/source.md",
                sha256: "1".repeat(64),
                mediaType: "text/markdown",
                sizeBytes: 6,
                artifactRole: "original",
              },
            },
            meta: sourcesFixture.meta,
          },
          { status: 202 },
        );
      }),
    );
    Object.defineProperty(window, "crypto", {
      configurable: true,
      value: {
        subtle: {
          digest: async () => new Uint8Array(32).fill(1).buffer,
        },
      },
    });
    Object.defineProperty(File.prototype, "arrayBuffer", {
      configurable: true,
      value: async () => new TextEncoder().encode("# Rule").buffer,
    });
    renderApp();

    fireEvent.click(await screen.findByText("登记新 SourceVersion"));
    fireEvent.change(screen.getByLabelText("Source ID"), {
      target: { value: "src-ui-upload" },
    });
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "UI upload" },
    });
    fireEvent.change(screen.getByLabelText("Version"), {
      target: { value: "1.0" },
    });
    const file = new File(["# Rule"], "rule.md", { type: "text/markdown" });
    fireEvent.change(screen.getByLabelText("Source file"), {
      target: { files: [file] },
    });
    const submit = screen.getByRole("button", { name: "登记并启动处理" });
    fireEvent.submit(submit.closest("form")!);

    expect(await screen.findByText(/run-ui-upload-v1/)).toBeInTheDocument();
    expect(receivedIdempotencyKey).toMatch(/^ui:src-ui-upload:1\.0:/);
    expect(screen.getByText(/原始对象仍不是 Evidence/)).toBeInTheDocument();
  });

  it("renders durable processing DAG facts and retries only the failed step", async () => {
    let retryCalls = 0;
    server.use(
      http.post(
        resolveApiPath(
          `${API_PATHS.processingRuns}/run-failed-002/steps/step-parse-text/retry`,
        ),
        () => {
          retryCalls += 1;
          return HttpResponse.json(
            {
              data: {
                runId: "run-failed-002",
                stepId: "step-parse-text",
                attemptId: "attempt-parse-text-2",
                status: "queued",
              },
              meta: sourcesFixture.meta,
            },
            { status: 202 },
          );
        },
      ),
    );
    renderApp("/processing");

    expect(await screen.findByRole("heading", { name: "Processing" })).toBeInTheDocument();
    expect(await screen.findByText("document.parse_tables")).toBeInTheDocument();
    expect(screen.getAllByText("Original")).toHaveLength(2);
    expect(screen.getAllByText("Derived")).toHaveLength(2);
    expect(screen.getAllByText("Evidence")).toHaveLength(2);
    expect(screen.getAllByText(/checkpoint ·/)).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Retry linked attempt" }));
    await waitFor(() => expect(retryCalls).toBe(1));
  });

  it("navigates to Admin and renders product roles without credentials", async () => {
    renderApp();

    fireEvent.click(await screen.findByRole("link", { name: /Admin/ }));
    expect(await screen.findByRole("heading", { name: "Admin" })).toBeInTheDocument();
    expect(await screen.findByText("Knowledge Reviewer")).toBeInTheDocument();
    expect(screen.getByText("Secrets never echoed")).toBeInTheDocument();
    expect(screen.queryByText(/password|token value/i)).not.toBeInTheDocument();
  });
});
