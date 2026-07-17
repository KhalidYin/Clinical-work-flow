import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { PocState, ReviewsResponse, StudiesResponse } from "./types";

const studiesPayload: StudiesResponse = {
  studies: [{ study_id: "SAMPLE-AE-001", title: "Sample AE" }],
  partial_errors: [],
};

const pocState: PocState = {
  study_id: "SAMPLE-AE-001",
  target_artifact: "sdtm_ae_dataset",
  run_id: "run-poc-test",
  run_state: "blocked_review",
  source: {
    format: "sas7bdat",
    sha256: "a".repeat(64),
  },
  knowledge: {
    scope: "p9-poc-test-only",
  },
  blocking_reason: "pending review: sdtm_spec_sample_ae_001_mapping_v1_001",
  active_step: {
    step_id: "mapping-spec",
    kind: "review",
    title: "等待人工 Review Gate",
    summary: "POC runner 已在审核点暂停。",
    blocking_reason: "pending review",
    review_id: "sdtm_spec_sample_ae_001_mapping_v1_001",
    artifact_refs: [],
  },
  steps: [
    {
      step_id: "source-intake",
      ordinal: 1,
      title: "Source Intake",
      state: "done",
      kind: "instruction",
      summary: "source ok",
      artifact_refs: [],
      evidence_refs: [],
    },
    {
      step_id: "mapping-spec",
      ordinal: 2,
      title: "MappingSpec",
      state: "blocked_review",
      kind: "review",
      summary: "review required",
      review_id: "sdtm_spec_sample_ae_001_mapping_v1_001",
      artifact_refs: [],
      evidence_refs: [],
    },
  ],
  next_actions: [
    {
      action_id: "run_poc",
      label: "Run POC",
      enabled: false,
      reason: "current state is blocked_review",
      method: "POST",
      endpoint: "/api/v1/studies/SAMPLE-AE-001/poc-runs",
    },
    {
      action_id: "resume",
      label: "Resume",
      enabled: true,
      method: "POST",
      endpoint: "/api/v1/studies/SAMPLE-AE-001/poc-runs/run-poc-test/resume",
    },
    {
      action_id: "refresh",
      label: "Refresh",
      enabled: true,
      method: "GET",
      endpoint: "/api/v1/studies/SAMPLE-AE-001/poc-state",
    },
  ],
  health: [{ check_id: "study", severity: "ok", summary: "Study visible", evidence_refs: [] }],
  events: [
    {
      event_id: "evt-poc-test",
      event_type: "run_blocked_review",
      occurred_at: "2026-07-17T00:00:00+00:00",
      step_id: "mapping-spec",
      summary: "blocked",
      severity: "ok",
      related_refs: [],
    },
  ],
  partial_errors: [],
};

const reviewsPayload: ReviewsResponse = {
  reviews: [
    {
      review_id: "sdtm_spec_sample_ae_001_mapping_v1_001",
      review_type: "sdtm_mapping_spec",
      urgency: "blocking",
      decision_state: "pending",
      finding_count: 2,
      packet_sha256: "b".repeat(64),
      confirmation_sha256: null,
      agent_summary: "请审核 AE MappingSpec。",
      source_documents: ["work/mapping/ae-mapping-spec-candidate.json"],
      created_at: "2026-07-17T00:00:00+00:00",
      findings: [
        {
          finding_id: "F-MAP-001",
          category: "mapping",
          severity: "major",
          location: "AE.AETERM",
          title: "确认 AETERM 映射",
          current_value: "n/a",
          proposed_value: "AE_TERM -> AETERM",
          rationale: "需要人工确认 source label 与 SDTM target 一致。",
          evidence_refs: ["SDTMIG-3.4#AE"],
          auto_approved: false,
        },
        {
          finding_id: "F-MAP-002",
          category: "metadata",
          severity: "minor",
          location: "AE.DOMAIN",
          title: "DOMAIN 固定值",
          current_value: "AE",
          proposed_value: "AE",
          rationale: "DOMAIN 为固定值。",
          evidence_refs: [],
          auto_approved: true,
        },
      ],
    },
  ],
  partial_errors: [],
};

describe("Clinical POC Workbench shell", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/studies")) {
        return jsonResponse(studiesPayload);
      }
      if (url.endsWith("/poc-state")) {
        return jsonResponse(pocState);
      }
      if (url.endsWith("/reviews")) {
        return jsonResponse(reviewsPayload);
      }
      if (url.endsWith("/reviews/sdtm_spec_sample_ae_001_mapping_v1_001/decisions")) {
        const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
        return jsonResponse({
          review_id: body.review_id,
          decision_receipt_id: "sdtm_spec_sample_ae_001_mapping_v1_001_decision",
          written: true,
          idempotency_key: "ui-review-test-key",
        }, 201);
      }
      if (url.endsWith("/poc-runs/run-poc-test/resume")) {
        return jsonResponse({
          accepted: true,
          run_id: "run-poc-test",
          run_state: "blocked_review",
          state_endpoint: "/api/v1/studies/SAMPLE-AE-001/poc-state",
          message: "resumed",
        });
      }
      return jsonResponse({}, 404);
    }) as typeof fetch;
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders header, timeline, active task, and evidence log from poc-state", async () => {
    render(<App />);

    expect(screen.getByText("正在读取 POC 状态…")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "SAMPLE-AE-001" })).toBeInTheDocument();
    expect(screen.getByText("sas7bdat")).toBeInTheDocument();
    expect(screen.getByText("p9-poc-test-only")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "MappingSpec" })).toBeInTheDocument();
    expect(screen.getByText("run_blocked_review")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "sdtm_spec_sample_ae_001_mapping_v1_001" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run POC" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Resume" })).toBeEnabled();
  });

  it("calls resume endpoint and refreshes state", async () => {
    render(<App />);

    const resume = await screen.findByRole("button", { name: "Resume" });
    fireEvent.click(resume);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs/run-poc-test/resume",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("renders blocking review packet and submits a DecisionReceipt", async () => {
    render(<App />);

    expect(await screen.findByText("确认 AETERM 映射")).toBeInTheDocument();
    const submit = screen.getByRole("button", { name: "Submit DecisionReceipt" });
    expect(submit).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Approve all required findings" }));
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/v1/studies/SAMPLE-AE-001/reviews/sdtm_spec_sample_ae_001_mapping_v1_001/decisions",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"decision":"approved"'),
        }),
      );
    });
    expect(await screen.findByText(/DecisionReceipt 已写入/)).toBeInTheDocument();
  });
});

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response;
}
