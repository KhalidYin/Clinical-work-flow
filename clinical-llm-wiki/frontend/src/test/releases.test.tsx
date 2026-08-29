import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { HttpResponse, http } from "msw";

import { resolveApiPath } from "../contracts/knowledgeApi";
import { server } from "../mocks/server";
import { createAppRouter } from "../router";


const workbenchPath = "/api/prerelease/v1/releases/workbench";
const publishPath = "/api/prerelease/v1/releases/release-candidate-ui/publish";
const meta = {
  contractVersion: "knowledge-api.prerelease.v1",
  fixture: false,
  generatedAt: "2026-08-16T10:00:00Z",
};

function workbench(blocked = false) {
  return {
    data: {
      current: {
        releaseId: "release-current-ui",
        version: "2026.08.1",
        status: "released",
        baseReleaseId: null,
        itemCount: 2,
        isCurrent: true,
        createdAt: "2026-08-16T08:00:00Z",
        publishedAt: "2026-08-16T08:05:00Z",
      },
      candidate: {
        releaseId: "release-candidate-ui",
        version: "2026.08.2",
        status: "candidate",
        baseReleaseId: "release-current-ui",
        itemCount: 2,
        isCurrent: false,
        createdAt: "2026-08-16T09:00:00Z",
        publishedAt: null,
      },
      history: [],
      diff: {
        includedCount: 2,
        carriedCount: 1,
        replacedCount: 1,
        addedCount: 0,
        retiredCount: 1,
        includedRevisionIds: ["revision-carried", "revision-replacement"],
        carriedRevisionIds: ["revision-carried"],
        replacedRevisionIds: ["revision-replacement"],
        addedRevisionIds: [],
        retiredRevisionIds: ["revision-retired"],
      },
      gates: [
        { code: "candidate_integrity", passed: true, reason: "candidate_hash_verified" },
        {
          code: "base_release_current",
          passed: !blocked,
          reason: blocked ? "base_release_is_stale" : "base_matches_current",
        },
      ],
      blockers: blocked ? ["base_release_is_stale"] : [],
      allowedActions: blocked ? [] : ["publish"],
    },
    meta,
  };
}

function renderApp(initialEntry = "/releases?candidate=release-candidate-ui&release=") {
  const history = createMemoryHistory({ initialEntries: [initialEntry] });
  const router = createAppRouter(history);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return { router };
}

describe("P17 Release governance workbench", () => {
  it("renders server-computed diff, Gates and candidate URL state", async () => {
    let requestedCandidate = "";
    server.use(
      http.get(resolveApiPath(workbenchPath), ({ request }) => {
        requestedCandidate = new URL(request.url).searchParams.get("candidate_id") ?? "";
        return HttpResponse.json(workbench());
      }),
    );

    renderApp();

    expect(await screen.findByRole("heading", { name: "版本发布" })).toBeInTheDocument();
    expect((await screen.findAllByText("revision-carried")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("revision-replacement").length).toBeGreaterThan(0);
    expect(screen.getByText("revision-retired")).toBeInTheDocument();
    expect(screen.getByText("candidate_hash_verified")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发布候选版本" })).toBeEnabled();
    expect(requestedCandidate).toBe("release-candidate-ui");
  });

  it("sends baseReleaseId and replaces success state with a stale blocker", async () => {
    let calls = 0;
    let publishedBody: unknown = null;
    server.use(
      http.get(resolveApiPath(workbenchPath), () => {
        calls += 1;
        return HttpResponse.json(workbench(calls > 1));
      }),
      http.post(resolveApiPath(publishPath), async ({ request }) => {
        publishedBody = await request.json();
        return HttpResponse.json(
          {
            error: {
              code: "release_publish_blocked",
              message: "current Release changed before publication",
            },
            meta,
          },
          { status: 409 },
        );
      }),
    );
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: "发布候选版本" }));

    expect(await screen.findByText(/current Release changed/)).toBeInTheDocument();
    await waitFor(() => expect(calls).toBeGreaterThan(1));
    expect((await screen.findAllByText("base_release_is_stale")).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "发布候选版本" })).toBeDisabled();
    expect(publishedBody).toEqual({ baseReleaseId: "release-current-ui" });
  });

  it("opens an immutable historical Release from URL even when no candidate exists", async () => {
    let requestedRelease = "";
    server.use(
      http.get(resolveApiPath(workbenchPath), () =>
        HttpResponse.json({
          ...workbench(),
          data: {
            ...workbench().data,
            candidate: null,
            diff: null,
            gates: [],
            blockers: [],
            allowedActions: [],
            history: [
              {
                releaseId: "release-historical-ui",
                version: "2026.07.9",
                status: "released",
                baseReleaseId: "release-earlier-ui",
                itemCount: 1,
                isCurrent: false,
                createdAt: "2026-07-31T08:00:00Z",
                publishedAt: "2026-07-31T08:05:00Z",
              },
            ],
          },
        }),
      ),
      http.get(
        resolveApiPath(
          "/api/prerelease/v1/releases/release-historical-ui/manifest",
        ),
        ({ params }) => {
          requestedRelease = String(params.releaseId ?? "release-historical-ui");
          return HttpResponse.json({
            releaseId: "release-historical-ui",
            version: "2026.07.9",
            manifestSha256: "a".repeat(64),
            manifest: {
              schemaVersion: "p17-release-v1",
              releaseId: "release-historical-ui",
              releaseVersion: "2026.07.9",
              baseReleaseId: "release-earlier-ui",
              evaluationRunId: "evaluation-historical-ui",
              chunkProfileId: "chunk-profile-p17",
              chunkProfileVersion: "v1",
              rotationCaseIds: [],
              dbSchemaRevision: "20260816_0012",
              knowledgeContractVersion: "p17-v1",
              parserProfileVersion: "parser-v1",
              modelProfileVersion: "replay-v1",
              promptProfileVersion: "prompt-v1",
              indexDescriptor: {
                objectKey: "releases/release-historical-ui/index.json",
                sha256: "b".repeat(64),
                mediaType: "application/json",
                sizeBytes: 128,
              },
              items: [
                {
                  knowledgeRevisionId: "revision-historical-ui",
                  contentSha256: "c".repeat(64),
                  disposition: "carry_forward",
                  evidenceIds: ["evidence-historical-ui"],
                  chunkIds: ["chunk-historical-ui"],
                },
              ],
            },
          });
        },
      ),
    );

    const { router } = renderApp(
      "/releases?candidate=&release=release-historical-ui",
    );

    expect(
      await screen.findByRole("heading", { name: "历史 Release 详情" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("revision-historical-ui")).toBeInTheDocument();
    expect(screen.getAllByText("release-historical-ui").length).toBeGreaterThan(0);
    expect(screen.getByText("evidence-historical-ui")).toBeInTheDocument();
    expect(screen.getByText("chunk-historical-ui")).toBeInTheDocument();
    expect(requestedRelease).toBe("release-historical-ui");
    expect(router.state.location.search.release).toBe("release-historical-ui");
  });
});
