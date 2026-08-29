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
import { SourcesPage } from "./pages/SourcesPage";
import { ProcessingPage } from "./pages/ProcessingPage";
import { CandidatesPage } from "./pages/CandidatesPage";
import { RelationsPage } from "./pages/RelationsPage";
import { AuditPage } from "./pages/AuditPage";
import { QueryLabPage } from "./pages/QueryLabPage";
import { EvaluationPage } from "./pages/EvaluationPage";
import { ReleasesPage } from "./pages/ReleasesPage";

const rootRoute = createRootRoute({
  component: AppShell,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: () => {
    throw redirect({
      to: "/sources",
      search: { q: "", source: "", from: "", to: "", assessment: "", change: "" },
    });
  },
});

const sourcesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/sources",
  validateSearch: (search: Record<string, unknown>) => ({
    q: typeof search.q === "string" ? search.q : "",
    source: typeof search.source === "string" ? search.source : "",
    from: typeof search.from === "string" ? search.from : "",
    to: typeof search.to === "string" ? search.to : "",
    assessment: typeof search.assessment === "string" ? search.assessment : "",
    change: typeof search.change === "string" ? search.change : "",
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
          search: (current) => ({ ...current, q }),
          replace: true,
        });
      }}
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
  validateSearch: (search: Record<string, unknown>) => ({
    run: typeof search.run === "string" ? search.run : "",
    evidence: typeof search.evidence === "string" ? search.evidence : "",
    chunk: typeof search.chunk === "string" ? search.chunk : "",
  }),
  component: ProcessingRoute,
});

function ProcessingRoute() {
  const search = processingRoute.useSearch();
  const navigate = processingRoute.useNavigate();
  return (
    <ProcessingPage
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

const queryLabRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/query-lab",
  validateSearch: (search: Record<string, unknown>) => {
    const parsedTopK = Number(search.top_k);
    return {
      scope: search.scope === "evaluation" ? ("evaluation" as const) : ("" as const),
      evaluation: typeof search.evaluation === "string" ? search.evaluation : "",
      case: typeof search.case === "string" ? search.case : "",
      q: typeof search.q === "string" ? search.q : "",
      release: typeof search.release === "string" ? search.release : "",
      top_k: [5, 10, 20, 50].includes(parsedTopK) ? parsedTopK : 10,
    };
  },
  component: QueryLabRoute,
});

const evaluationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/evaluation",
  validateSearch: (search: Record<string, unknown>) => ({
    suite: typeof search.suite === "string" ? search.suite : "",
    run: typeof search.run === "string" ? search.run : "",
    outcome: ["informational", "passed", "failed"].includes(String(search.outcome))
      ? (search.outcome as "informational" | "passed" | "failed")
      : "" as const,
    baseline: typeof search.baseline === "string" ? search.baseline : "",
  }),
  component: EvaluationRoute,
});

const releasesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/releases",
  validateSearch: (search: Record<string, unknown>) => ({
    candidate: typeof search.candidate === "string" ? search.candidate : "",
    release: typeof search.release === "string" ? search.release : "",
  }),
  component: ReleasesRoute,
});

function ReleasesRoute() {
  const search = releasesRoute.useSearch();
  const navigate = releasesRoute.useNavigate();
  return (
    <ReleasesPage
      candidateId={search.candidate}
      releaseId={search.release}
      onCandidateChange={(candidate) => {
        void navigate({ search: (current) => ({ ...current, candidate }), replace: true });
      }}
      onReleaseChange={(release) => {
        void navigate({ search: (current) => ({ ...current, release }), replace: true });
      }}
    />
  );
}

function EvaluationRoute() {
  const search = evaluationRoute.useSearch();
  const navigate = evaluationRoute.useNavigate();
  return (
    <EvaluationPage
      search={search}
      onSearchChange={(patch) => {
        void navigate({
          search: (current) => ({ ...current, ...patch }),
          replace: true,
        });
      }}
      onReplay={(replay) => {
        void navigate({
          to: "/query-lab",
          search: {
            scope: "evaluation",
            evaluation: replay.evaluationRunId,
            case: replay.caseId,
            q: replay.query ?? "",
            release: "",
            top_k: replay.topK,
          },
        });
      }}
    />
  );
}

function QueryLabRoute() {
  const search = queryLabRoute.useSearch();
  const navigate = queryLabRoute.useNavigate();
  return (
    <QueryLabPage
      search={search}
      onSearchChange={(next) => {
        void navigate({ search: next, replace: true });
      }}
    />
  );
}

const candidatesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/candidates",
  validateSearch: (search: Record<string, unknown>) => ({
    view: search.view === "rotation" ? ("rotation" as const) : ("candidates" as const),
    status: typeof search.status === "string" ? search.status : "",
    case: typeof search.case === "string" ? search.case : "",
  }),
  component: CandidatesRoute,
});

function CandidatesRoute() {
  const search = candidatesRoute.useSearch();
  const navigate = candidatesRoute.useNavigate();
  return (
    <CandidatesPage
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

const relationsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/relations",
  validateSearch: (search: Record<string, unknown>) => ({
    q: typeof search.q === "string" ? search.q : "",
    node: typeof search.node === "string" ? search.node : "",
    depth: search.depth === 2 || search.depth === "2" ? 2 : 1,
    view: search.view === "list" ? ("list" as const) : ("paths" as const),
    release: typeof search.release === "string" ? search.release : "",
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
    entity: typeof search.entity === "string" ? search.entity : "",
    case: typeof search.case === "string" ? search.case : "",
    release: typeof search.release === "string" ? search.release : "",
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

const adminRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/admin",
  component: AdminPage,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  sourcesRoute,
  processingRoute,
  queryLabRoute,
  evaluationRoute,
  releasesRoute,
  candidatesRoute,
  relationsRoute,
  auditRoute,
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
