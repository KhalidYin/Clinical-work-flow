import {
  createHashHistory,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
} from "@tanstack/react-router";

import { AppShell } from "./app/AppShell";
import { AdminPage } from "./pages/AdminPage";
import { ScopePage } from "./pages/ScopePage";
import { SourcesPage } from "./pages/SourcesPage";
import { ProcessingPage } from "./pages/ProcessingPage";
import { CandidatesPage } from "./pages/CandidatesPage";
import { RelationsPage } from "./pages/RelationsPage";
import { AuditPage } from "./pages/AuditPage";

const rootRoute = createRootRoute({
  component: AppShell,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: () => {
    throw redirect({ to: "/sources", search: { q: "" } });
  },
});

const sourcesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/sources",
  validateSearch: (search: Record<string, unknown>) => ({
    q: typeof search.q === "string" ? search.q : "",
  }),
  component: SourcesRoute,
});

function SourcesRoute() {
  const search = sourcesRoute.useSearch();
  const navigate = sourcesRoute.useNavigate();

  return (
    <SourcesPage
      query={search.q}
      onQueryChange={(q) => {
        void navigate({
          search: { q },
          replace: true,
        });
      }}
    />
  );
}

const scopeRoutes = [
  {
    path: "/query-lab",
    eyebrow: "可解释混合检索",
    title: "检索实验室",
    description: "元数据、全文检索、向量检索与有界关系扩展均提供可解释路径。",
    phase: "KUI-06 · 计划在 P4 实现",
  },
  {
    path: "/evaluation",
    eyebrow: "黄金集回归证据",
    title: "质量评估",
    description: "指标必须回溯黄金用例、预期证据、版本与失败类别。",
    phase: "KUI-07 · 计划在 P5 实现",
  },
  {
    path: "/releases",
    eyebrow: "不可变发布门禁",
    title: "版本发布",
    description: "未批准、评估失败、hash drift 或职责分离违规都必须阻断发布。",
    phase: "KUI-08 · 计划在 P5 实现",
  },
] as const;

const processingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/processing",
  component: ProcessingPage,
});

const candidatesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/candidates",
  component: CandidatesPage,
});

const relationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/relations",
  validateSearch: (search: Record<string, unknown>) => ({
    q: typeof search.q === "string" ? search.q : "",
    node: typeof search.node === "string" ? search.node : "",
    depth: search.depth === 2 || search.depth === "2" ? 2 : 1,
    view: search.view === "list" ? ("list" as const) : ("paths" as const),
  }),
  component: RelationsRoute,
});

function RelationsRoute() {
  const search = relationsRoute.useSearch();
  const navigate = relationsRoute.useNavigate();
  return (
    <RelationsPage
      search={search}
      onSearchChange={(patch) => {
        void navigate({
          search: (current) => ({ ...current, ...patch }),
          replace: true,
        });
      }}
    />
  );
}

const auditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/audit",
  validateSearch: (search: Record<string, unknown>) => ({
    actor: typeof search.actor === "string" ? search.actor : "",
    action: typeof search.action === "string" ? search.action : "",
    objectType: typeof search.objectType === "string" ? search.objectType : "",
    result: typeof search.result === "string" ? search.result : "",
    cursor: typeof search.cursor === "string" ? search.cursor : "",
    event: typeof search.event === "string" ? search.event : "",
  }),
  component: AuditRoute,
});

function AuditRoute() {
  const search = auditRoute.useSearch();
  const navigate = auditRoute.useNavigate();
  return (
    <AuditPage
      search={search}
      onSearchChange={(patch) => {
        void navigate({
          search: (current) => ({ ...current, ...patch }),
          replace: true,
        });
      }}
    />
  );
}

const generatedScopeRoutes = scopeRoutes.map((scope) =>
  createRoute({
    getParentRoute: () => rootRoute,
    path: scope.path,
    component: () => <ScopePage {...scope} />,
  }),
);

const adminRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin",
  component: AdminPage,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  sourcesRoute,
  processingRoute,
  candidatesRoute,
  relationsRoute,
  auditRoute,
  ...generatedScopeRoutes,
  adminRoute,
]);

type AppHistory = ReturnType<typeof createHashHistory> | ReturnType<typeof createMemoryHistory>;

export function createAppRouter(history: AppHistory = createHashHistory()) {
  return createRouter({
    routeTree,
    history,
    defaultPreload: "intent",
    defaultPreloadStaleTime: 10_000,
    scrollRestoration: true,
  });
}

export type AppRouter = ReturnType<typeof createAppRouter>;

declare module "@tanstack/react-router" {
  interface Register {
    router: AppRouter;
  }
}
