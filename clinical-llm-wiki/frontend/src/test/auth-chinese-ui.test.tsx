import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { HttpResponse, http } from "msw";

import { API_PATHS, resolveApiPath } from "../contracts/knowledgeApi";
import { sourcesFixture } from "../mocks/fixtures";
import { server } from "../mocks/server";
import { createAppRouter } from "../router";

function renderApp(initialEntry = "/sources?q=") {
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
}

describe("P13 中文密码会话合同", () => {
  it("未认证用户只看到中文用户名和密码表单", async () => {
    server.use(
      http.get(resolveApiPath(API_PATHS.session), () =>
        HttpResponse.json(
          {
            error: { code: "authentication_required", message: "需要登录。" },
            meta: sourcesFixture.meta,
          },
          { status: 401 },
        ),
      ),
    );
    renderApp("/candidates");

    expect(await screen.findByRole("heading", { name: "登录临床知识台账" })).toBeInTheDocument();
    expect(screen.getByLabelText("用户名")).toBeInTheDocument();
    expect(screen.getByLabelText("密码")).toBeInTheDocument();
    expect(screen.queryByText(/access token|bearer/i)).not.toBeInTheDocument();
    expect(window.sessionStorage.getItem("knowledgeLedgerBearerToken")).toBeNull();
  });

  it("已登录应用壳显示完整中文一级导航", async () => {
    renderApp();

    for (const label of [
      "来源管理",
      "处理任务",
      "知识候选",
      "关系浏览",
      "检索实验室",
      "质量评估",
      "版本发布",
      "审计记录",
      "系统管理",
    ]) {
      expect(await screen.findByRole("link", { name: new RegExp(label) })).toBeInTheDocument();
    }
  });
});
