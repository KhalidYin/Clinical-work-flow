import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { PocState, StudiesResponse } from "./types";

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

describe("Clinical POC Workbench shell", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/api/v1/studies")) {
        return jsonResponse(studiesPayload);
      }
      if (url.endsWith("/poc-state")) {
        return jsonResponse(pocState);
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
});

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response;
}
