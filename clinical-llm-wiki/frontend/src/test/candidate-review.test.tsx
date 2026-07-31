import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createMemoryHistory, RouterProvider } from "@tanstack/react-router";
import { delay, HttpResponse, http } from "msw";

import {
  API_PATHS,
  CONTRACT_VERSION,
  resolveApiPath,
  type ApiResponse,
  type CandidateDetail,
  type Session,
} from "../contracts/knowledgeApi";
import { server } from "../mocks/server";
import { createAppRouter } from "../router";

const fixtureTime = "2026-07-31T01:00:00Z";
const hashA = "a".repeat(64);
const hashB = "b".repeat(64);

function response<T>(data: T): ApiResponse<T> {
  return {
    data,
    meta: {
      contractVersion: CONTRACT_VERSION,
      fixture: true,
      generatedAt: fixtureTime,
    },
  };
}

function renderCandidates() {
  const history = createMemoryHistory({ initialEntries: ["/candidates"] });
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

const authorSession = response<Session>({
  actorId: "usr-author-ui",
  displayName: "Lin Chen",
  principalType: "human",
  roles: ["knowledge_curator"],
  organization: "Clinical Knowledge Lab",
  permissions: ["candidate:read", "candidate:write", "candidate:submit"],
});

const reviewerSession = response<Session>({
  actorId: "usr-reviewer-ui",
  displayName: "Mei Zhou",
  principalType: "human",
  roles: ["reviewer"],
  organization: "Clinical Knowledge Lab",
  permissions: ["candidate:read", "review:decide"],
});

function authorDetail(
  overrides: Partial<CandidateDetail> = {},
): ApiResponse<CandidateDetail> {
  return response({
    candidateId: "cand-ui-aeseq-001",
    candidateGroupId: "candgrp-ui-aeseq",
    parentCandidateId: null,
    runId: "run-ui-aeseq",
    revisionNumber: 1,
    status: "author_confirmation_required",
    knowledgeType: "variable_definition",
    claim: "AESEQ is the sequence identifier within the AE domain.",
    scope: { standard: "SDTM", domain: "AE" },
    applicability: { standardVersion: "3.4" },
    conditions: [],
    exceptions: [],
    contentSha256: hashA,
    evidenceCount: 1,
    relationProposalCount: 1,
    authorActorId: null,
    knowledgeRevisionId: null,
    reviewStatus: null,
    evidence: [
      {
        evidenceId: "evidence-ui-aeseq-001",
        sourceVersionId: "srcv-sdtmig-34",
        locator: { page: 35, section: "6.2 AE", paragraph: 4 },
        content:
          "AESEQ is the sequence identifier used to uniquely identify a record within the AE domain.",
        contentSha256: "e".repeat(64),
        rights: {
          classification: "licensed",
          storageAllowed: true,
          citationRequired: true,
        },
      },
    ],
    relationProposals: [
      {
        relationType: "applies_to",
        targetKnowledgeUnitId: "KU-SDTM-AE",
        evidenceIds: ["evidence-ui-aeseq-001"],
        status: "proposed",
      },
    ],
    advisorySignals: [
      {
        signalType: "explicit_gap",
        description: "The source does not define the sponsor-specific exception.",
        targetKnowledgeUnitId: null,
        evidenceIds: ["evidence-ui-aeseq-001"],
      },
    ],
    originModelInvocationId: "invocation-ui-aeseq-001",
    ...overrides,
  });
}

function reviewerDetail(): ApiResponse<CandidateDetail> {
  return response({
    ...authorDetail().data,
    candidateId: "cand-ui-teae-001",
    candidateGroupId: "candgrp-ui-teae",
    runId: "run-ui-teae",
    status: "author_confirmed",
    knowledgeType: "clinical_rule",
    claim: "TEAE applicability is bounded by the confirmed analysis scope.",
    scope: { standard: "ADaM", dataset: "ADAE" },
    applicability: { analysis: "safety" },
    contentSha256: hashB,
    authorActorId: "usr-author-004",
    knowledgeRevisionId: "krev-ui-teae-001",
    reviewStatus: "review_required",
  });
}

function useAuthorDetailHandler() {
  server.use(
    http.get(resolveApiPath(API_PATHS.session), () => HttpResponse.json(authorSession)),
    http.get(
      resolveApiPath(`${API_PATHS.candidates}/cand-ui-aeseq-001`),
      () => HttpResponse.json(authorDetail()),
    ),
  );
}

describe("KUI-04 Candidate governance workbench", () => {
  it("places immutable evidence, locator and rights before the editable candidate", async () => {
    useAuthorDetailHandler();
    renderCandidates();

    expect(await screen.findByRole("heading", { name: "原始证据" })).toBeInTheDocument();
    expect(
      screen.getByText(/AESEQ is the sequence identifier used to uniquely identify/),
    ).toBeInTheDocument();
    expect(screen.getByText(/page: 35/)).toBeInTheDocument();
    expect(screen.getByText(/licensed/)).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "关系" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "applies_to" })).toBeInTheDocument();
    expect(
      screen.getByText("The source does not define the sponsor-specific exception."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "编辑候选" })).toBeInTheDocument();
  });

  it("returns a changes-requested confirmed revision to the author editing gate", async () => {
    server.use(
      http.get(resolveApiPath(API_PATHS.session), () => HttpResponse.json(authorSession)),
      http.get(
        resolveApiPath(`${API_PATHS.candidates}/cand-ui-aeseq-001`),
        () =>
          HttpResponse.json(
            authorDetail({
              status: "author_confirmed",
              authorActorId: "usr-author-ui",
              knowledgeRevisionId: "krev-ui-aeseq-001",
              reviewStatus: "changes_requested",
            }),
          ),
      ),
    );
    renderCandidates();

    expect(await screen.findByText("作者确认 Gate")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "编辑候选" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "审核通过" }),
    ).not.toBeInTheDocument();
  });

  it("persists the approved-but-unreleased gate after canonical facts reload", async () => {
    server.use(
      http.get(resolveApiPath(API_PATHS.session), () => HttpResponse.json(reviewerSession)),
      http.get(
        resolveApiPath(`${API_PATHS.candidates}/cand-ui-teae-001`),
        () =>
          HttpResponse.json(
            response({
              ...reviewerDetail().data,
              reviewStatus: "approved",
            }),
          ),
      ),
    );
    renderCandidates();

    expect(
      await screen.findByText("审核已批准，但尚未发布"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("该 KnowledgeRevision 尚未进入 immutable release。"),
    ).toBeInTheDocument();
  });

  it("creates revision N+1 from an edited claim and opens the returned candidate", async () => {
    useAuthorDetailHandler();
    let requestBody: Record<string, unknown> | null = null;
    server.use(
      http.post(
        resolveApiPath(`${API_PATHS.candidates}/cand-ui-aeseq-001/revisions`),
        async ({ request }) => {
          requestBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(
            response({
              candidateId: "cand-ui-aeseq-002",
              parentCandidateId: "cand-ui-aeseq-001",
              revisionNumber: 2,
              contentSha256: hashB,
              status: "author_confirmation_required" as const,
            }),
            { status: 201 },
          );
        },
      ),
      http.get(
        resolveApiPath(`${API_PATHS.candidates}/cand-ui-aeseq-002`),
        () =>
          HttpResponse.json(
            authorDetail({
              candidateId: "cand-ui-aeseq-002",
              parentCandidateId: "cand-ui-aeseq-001",
              revisionNumber: 2,
              claim: "AESEQ uniquely identifies each AE record.",
              contentSha256: hashB,
            }),
          ),
      ),
    );
    renderCandidates();

    fireEvent.click(await screen.findByRole("button", { name: "编辑候选" }));
    fireEvent.change(screen.getByRole("textbox", { name: "原子主张" }), {
      target: { value: "AESEQ uniquely identifies each AE record." },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存为 revision 2" }));

    expect(await screen.findByText("已建立 revision 2")).toBeInTheDocument();
    expect(await screen.findByText(/cand-ui-aeseq-002 · revision 2/)).toBeInTheDocument();
    expect(requestBody).toMatchObject({
      expectedRevisionNumber: 1,
      expectedContentSha256: hashA,
      claim: "AESEQ uniquely identifies each AE record.",
      scope: { standard: "SDTM", domain: "AE" },
      applicability: { standardVersion: "3.4" },
      conditions: [],
      exceptions: [],
    });
    expect(
      String(
        (requestBody as Record<string, unknown> | null)?.["idempotencyKey"],
      ),
    ).toMatch(/^ui:revision:/);
  });

  it("submits an exact author confirmation and reports the durable decision", async () => {
    useAuthorDetailHandler();
    let requestBody: Record<string, unknown> | null = null;
    server.use(
      http.post(
        resolveApiPath(`${API_PATHS.candidates}/cand-ui-aeseq-001/author-confirmation`),
        async ({ request }) => {
          requestBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(
            response({
              candidateId: "cand-ui-aeseq-001",
              candidateStatus: "author_confirmed" as const,
              knowledgeRevisionId: "krev-ui-aeseq-001",
              revisionStatus: "review_required" as const,
              decisionId: "decision-author-ui-001",
            }),
          );
        },
      ),
    );
    renderCandidates();

    fireEvent.click(
      await screen.findByRole("button", { name: "确认并提交独立审核" }),
    );

    expect(await screen.findByText(/decision-author-ui-001/)).toBeInTheDocument();
    expect(screen.getByText("已提交独立审核")).toBeInTheDocument();
    expect(requestBody).toMatchObject({
      expectedRevisionNumber: 1,
      expectedContentSha256: hashA,
    });
    expect(
      String(
        (requestBody as Record<string, unknown> | null)?.["idempotencyKey"],
      ),
    ).toMatch(/^ui:author-confirmation:/);
  });

  it("lets only the reviewer decide the exact confirmed revision with rationale", async () => {
    server.use(
      http.get(resolveApiPath(API_PATHS.session), () => HttpResponse.json(reviewerSession)),
      http.get(
        resolveApiPath(`${API_PATHS.candidates}/cand-ui-teae-001`),
        () => HttpResponse.json(reviewerDetail()),
      ),
    );
    let requestBody: Record<string, unknown> | null = null;
    server.use(
      http.post(
        resolveApiPath(
          "/api/prerelease/v1/knowledge-revisions/krev-ui-teae-001/review-decision",
        ),
        async ({ request }) => {
          requestBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(
            response({
              candidateId: "cand-ui-teae-001",
              knowledgeRevisionId: "krev-ui-teae-001",
              revisionStatus: "changes_requested" as const,
              decisionId: "decision-review-ui-001",
            }),
          );
        },
      ),
    );
    renderCandidates();

    expect(await screen.findByText("独立 Reviewer Gate")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "审核通过" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "驳回" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "审核理由" }), {
      target: { value: "请补充治疗窗口的适用边界。" },
    });
    fireEvent.click(screen.getByRole("button", { name: "请求修改" }));

    expect(await screen.findByText("已请求作者建立新 revision")).toBeInTheDocument();
    expect(screen.getByText(/decision-review-ui-001/)).toBeInTheDocument();
    expect(requestBody).toMatchObject({
      candidateId: "cand-ui-teae-001",
      expectedRevisionNumber: 1,
      expectedContentSha256: hashB,
      decision: "changes_requested",
      rationale: "请补充治疗窗口的适用边界。",
    });
    expect(
      String(
        (requestBody as Record<string, unknown> | null)?.["idempotencyKey"],
      ),
    ).toMatch(/^ui:review:/);
  });

  it("fails stale writes visibly and reloads canonical facts instead of claiming success", async () => {
    useAuthorDetailHandler();
    let detailCalls = 0;
    server.use(
      http.get(
        resolveApiPath(`${API_PATHS.candidates}/cand-ui-aeseq-001`),
        () => {
          detailCalls += 1;
          return HttpResponse.json(authorDetail());
        },
      ),
      http.post(
        resolveApiPath(`${API_PATHS.candidates}/cand-ui-aeseq-001/author-confirmation`),
        () =>
          HttpResponse.json(
            {
              error: {
                code: "stale_revision",
                message: "The candidate changed before this decision.",
              },
              meta: authorDetail().meta,
            },
            { status: 409 },
          ),
      ),
    );
    renderCandidates();

    fireEvent.click(
      await screen.findByRole("button", { name: "确认并提交独立审核" }),
    );

    expect(
      await screen.findByText("Candidate 已被更新，本次操作未提交。"),
    ).toBeInTheDocument();
    expect(screen.queryByText("已提交独立审核")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重新加载最新 revision" }));
    await waitFor(() => expect(detailCalls).toBeGreaterThanOrEqual(2));
  });

  it("keeps detail loading and failure states explicit", async () => {
    server.use(
      http.get(resolveApiPath(API_PATHS.session), () => HttpResponse.json(authorSession)),
      http.get(
        resolveApiPath(`${API_PATHS.candidates}/cand-ui-aeseq-001`),
        async () => {
          await delay(80);
          return HttpResponse.json(
            {
              error: { code: "service_unavailable", message: "fixture failure" },
              meta: authorDetail().meta,
            },
            { status: 503 },
          );
        },
      ),
    );
    renderCandidates();

    expect(
      await screen.findByLabelText("正在加载 Candidate 详情"),
    ).toHaveAttribute("aria-busy", "true");
    expect(
      await screen.findByText("无法读取 Candidate 详情；不会显示过期的审核数据。"),
    ).toBeInTheDocument();
  });
});
