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
import { QueryLabPage } from "./pages/QueryLabPage";

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
] as const;

const queryLabRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/query-lab",
  validateSearch: (search: Record<string, unknown>) => ({
    q: typeof search.q === "string" ? search.q : "",
    visibility:
      search.visibility === "evaluation"
        ? ("evaluation" as const)
        : ("released" as const),
    type: typeof search.type === "string" ? search.type : "",
    domain: typeof search.domain === "string" ? search.domain : "",
    depth:
      search.depth === 0 || search.depth === "0"
        ? 0
        : search.depth === 2 || search.depth === "2"
          ? 2
          : 1,
    vector: search.vector !== false && search.vector !== "false",
  }),
  component: QueryLabRoute,
});

function QueryLabRoute() {
  const search = queryLabRoute.useSearch();
  const navigate = queryLabRoute.useNavigate();
  return (
    <QueryLabPage
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
  queryLabRoute,
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
