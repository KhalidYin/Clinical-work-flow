import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { HttpResponse, http } from "msw";

import { API_PATHS, resolveApiPath, type PlatformUser } from "../contracts/knowledgeApi";
import { sourcesFixture } from "../mocks/fixtures";
import { server } from "../mocks/server";
import { createAppRouter } from "../router";

function renderAdmin() {
  const history = createMemoryHistory({ initialEntries: ["/admin"] });
  const router = createAppRouter(history);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

function userCollection(items: PlatformUser[]) {
  return {
    data: { items, total: items.length, partial: false, warnings: [] },
    meta: sourcesFixture.meta,
  };
}

describe("P13 用户与机器身份管理", () => {
  it("创建用户时只提交资料和角色，并一次性展示后端临时密码", async () => {
    const users: PlatformUser[] = [];
    let submitted: Record<string, unknown> | null = null;
    server.use(
      http.get(resolveApiPath(API_PATHS.adminUsers), () =>
        HttpResponse.json(userCollection(users)),
      ),
      http.post(resolveApiPath(API_PATHS.adminUsers), async ({ request }) => {
        submitted = (await request.json()) as Record<string, unknown>;
        users.push({
          userId: "usr-reviewer-new",
          displayName: "张审核",
          email: "reviewer@example.test",
          identitySource: "local_password",
          roles: ["reviewer"],
          status: "active",
          lastActiveAt: null,
        });
        return HttpResponse.json(
          {
            data: {
              userId: "usr-reviewer-new",
              username: "reviewer.zhang",
              temporaryPassword: "temporary-clinical-password-2026",
              mustChangePassword: true,
            },
            meta: sourcesFixture.meta,
          },
          { status: 201 },
        );
      }),
    );
    renderAdmin();

    fireEvent.click(await screen.findByRole("button", { name: "创建用户" }));
    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "Reviewer.Zhang" } });
    fireEvent.change(screen.getByLabelText("显示名称"), { target: { value: "张审核" } });
    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "reviewer@example.test" } });
    fireEvent.click(screen.getByLabelText(/知识审核员/));
    fireEvent.click(screen.getByLabelText(/知识使用者/));
    fireEvent.click(screen.getByRole("button", { name: "创建并生成临时密码" }));

    expect(await screen.findByLabelText("一次性临时密码")).toHaveTextContent(
      "temporary-clinical-password-2026",
    );
    expect(screen.getByText(/关闭后无法再次查看/)).toBeInTheDocument();
    await waitFor(() => expect(submitted).not.toBeNull());
    expect(submitted).toEqual({
      username: "Reviewer.Zhang",
      displayName: "张审核",
      email: "reviewer@example.test",
      roles: ["reviewer"],
    });
    expect(submitted).not.toHaveProperty("password");
    expect(await screen.findByText("本地用户名密码")).toBeInTheDocument();
  });

  it("重置密码和禁用用户均调用后端门禁，服务账号只显示 pool 与 scope", async () => {
    const user: PlatformUser = {
      userId: "usr-reviewer-one",
      displayName: "审核员一",
      email: "reviewer.one@example.test",
      identitySource: "local_password",
      roles: ["reviewer"],
      status: "active",
      lastActiveAt: null,
    };
    let requestedStatus: unknown = null;
    server.use(
      http.get(resolveApiPath(API_PATHS.adminUsers), () =>
        HttpResponse.json(userCollection([user])),
      ),
      http.post(
        resolveApiPath(`${API_PATHS.adminUsers}/${user.userId}/password/reset`),
        () => HttpResponse.json({ data: { userId: user.userId, username: null, temporaryPassword: "reset-clinical-password-2026", mustChangePassword: true }, meta: sourcesFixture.meta }),
      ),
      http.post(
        resolveApiPath(`${API_PATHS.adminUsers}/${user.userId}/status`),
        async ({ request }) => {
          requestedStatus = await request.json();
          user.status = "disabled";
          return HttpResponse.json({ data: { userId: user.userId, status: "disabled" }, meta: sourcesFixture.meta });
        },
      ),
    );
    renderAdmin();

    const row = (await screen.findByText("审核员一")).closest("tr");
    if (!row) throw new Error("用户行不存在");
    fireEvent.click(within(row).getByRole("button", { name: "重置密码" }));
    expect(await screen.findByText("reset-clinical-password-2026")).toBeInTheDocument();
    fireEvent.click(within(row).getByRole("button", { name: "禁用" }));
    await waitFor(() => expect(requestedStatus).toEqual({ status: "disabled" }));

    expect(await screen.findByRole("heading", { name: "服务账号" })).toBeInTheDocument();
    expect(await screen.findByText("文档处理 Worker")).toBeInTheDocument();
    expect(screen.getByText(/source:read/)).toBeInTheDocument();
    expect(screen.queryByText(/P12_DOCUMENT_WORKER_TOKEN|env:\/\/.*WORKER_TOKEN/)).not.toBeInTheDocument();
  });
});
