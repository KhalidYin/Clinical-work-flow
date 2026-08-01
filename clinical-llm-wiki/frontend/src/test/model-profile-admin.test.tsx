import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { delay, HttpResponse, http } from "msw";

import { resolveApiPath } from "../contracts/knowledgeApi";
import { sourcesFixture } from "../mocks/fixtures";
import { server } from "../mocks/server";
import { createAppRouter } from "../router";

const modelProfilesPath = "/api/prerelease/v1/admin/model-profiles";

const profile = {
  profileId: "deepseek-v4-flash-extractor",
  version: "1.0.0",
  provider: "deepseek",
  model: "deepseek-v4-flash",
  deploymentClass: "external_api",
  secretRef: "env://KNOWLEDGE_MODEL_API_KEY",
  endpointRef: "env://KNOWLEDGE_MODEL_ENDPOINT",
  allowedDataBoundaries: ["external_allowed"],
  capabilities: ["structured_generation"],
  timeoutSeconds: 60,
  maxOutputTokens: 4096,
  costPolicy: { maxCostUsd: "0.05" },
  createdAt: "2026-08-01T04:00:00Z",
  connectionState: "not_verified",
  liveEnabled: false,
} as const;

function collection(items = [profile], partial = false, warnings: string[] = []) {
  return {
    data: { items, total: items.length, partial, warnings },
    meta: sourcesFixture.meta,
  };
}

function renderAdmin() {
  const history = createMemoryHistory({ initialEntries: ["/admin"] });
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
}

describe("KUI-09 Model API Configuration", () => {
  it("registers only a versioned secret reference and never offers a live call", async () => {
    let submitted: Record<string, unknown> | null = null;
    server.use(
      http.get(resolveApiPath(modelProfilesPath), () => HttpResponse.json(collection([]))),
      http.post(resolveApiPath(modelProfilesPath), async ({ request }) => {
        submitted = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            data: { profile, created: true },
            meta: sourcesFixture.meta,
          },
          { status: 201 },
        );
      }),
    );
    renderAdmin();

    expect(
      await screen.findByRole("heading", { name: "模型 API 配置" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/保存配置不等于授权实时调用/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/api key|password|secret value/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /测试连接|test connection|运行模型/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "登记 ModelProfile 版本" }));
    fireEvent.change(screen.getByLabelText("配置 ID（Profile ID）"), {
      target: { value: profile.profileId },
    });
    fireEvent.change(screen.getByLabelText("版本（Version）"), {
      target: { value: profile.version },
    });
    fireEvent.change(screen.getByLabelText("提供方（Provider）"), {
      target: { value: profile.provider },
    });
    fireEvent.change(screen.getByLabelText("模型（Model）"), {
      target: { value: profile.model },
    });
    fireEvent.change(screen.getByLabelText("密钥引用（Secret reference）"), {
      target: { value: profile.secretRef },
    });
    fireEvent.change(screen.getByLabelText("端点引用（Endpoint reference）"), {
      target: { value: profile.endpointRef },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存配置版本" }));

    expect(await screen.findByText("配置版本已登记，尚未验证连接或启用实时调用。"))
      .toBeInTheDocument();
    await waitFor(() => expect(submitted).not.toBeNull());
    expect(submitted).toMatchObject({
      profileId: profile.profileId,
      provider: profile.provider,
      secretRef: profile.secretRef,
    });
    expect(submitted).not.toHaveProperty("apiKey");
    expect(submitted).not.toHaveProperty("secretValue");
    expect(await screen.findByText(profile.model)).toBeInTheDocument();
    expect(screen.getByText("未验证")).toBeInTheDocument();
    expect(screen.getByText("实时调用已禁用")).toBeInTheDocument();
  });

  it("shows loading, partial and error states at the configuration surface", async () => {
    server.use(
      http.get(resolveApiPath(modelProfilesPath), async () => {
        await delay(60);
        return HttpResponse.json(
          collection([profile], true, ["one profile could not be projected"]),
        );
      }),
    );
    renderAdmin();

    expect(await screen.findByLabelText("正在读取模型配置")).toHaveAttribute(
      "aria-busy",
      "true",
    );
    expect(await screen.findByText(/one profile could not be projected/)).toBeInTheDocument();

    server.use(
      http.get(resolveApiPath(modelProfilesPath), () =>
        HttpResponse.json(
          {
            error: { code: "service_unavailable", message: "registry unavailable" },
            meta: sourcesFixture.meta,
          },
          { status: 503 },
        ),
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "重新读取模型配置" }));
    expect(await screen.findByText("registry unavailable")).toBeInTheDocument();
  });
});
