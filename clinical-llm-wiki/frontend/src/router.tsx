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
    path: "/processing",
    eyebrow: "Non-streaming document jobs",
    title: "Processing",
    description: "离散 run、step、attempt 与 checkpoint；不模拟 token 或 chunk stream。",
    phase: "KUI-03 · implementation planned in P2",
  },
  {
    path: "/candidates",
    eyebrow: "Evidence to governed knowledge",
    title: "Candidates",
    description: "机器候选先由作者确认，再交给独立 Reviewer；批准不等于已发布。",
    phase: "KUI-04 · implementation planned in P3",
  },
  {
    path: "/relations",
    eyebrow: "Typed relation evidence",
    title: "Relations",
    description: "关系边必须携带 evidence、方向、状态和 release membership。",
    phase: "KUI-05 · implementation planned in P3",
  },
  {
    path: "/query-lab",
    eyebrow: "Explainable hybrid retrieval",
    title: "Query Lab",
    description: "metadata、FTS、vector 与 bounded relation expansion 分路可解释。",
    phase: "KUI-06 · implementation planned in P4",
  },
  {
    path: "/evaluation",
    eyebrow: "Gold set regression evidence",
    title: "Evaluation",
    description: "指标必须回溯 Gold case、expected evidence、版本与失败类别。",
    phase: "KUI-07 · implementation planned in P5",
  },
  {
    path: "/releases",
    eyebrow: "Immutable publication gate",
    title: "Releases",
    description: "未批准、评估失败、hash drift 或职责分离违规都必须阻断发布。",
    phase: "KUI-08 · implementation planned in P5",
  },
  {
    path: "/audit",
    eyebrow: "Append-only governance events",
    title: "Audit",
    description: "审计记录 actor、action、object、revision、result 与 correlation ID。",
    phase: "KUI-10 · implementation planned in P3",
  },
] as const;

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
