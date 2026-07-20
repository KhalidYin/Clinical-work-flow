import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { PocState, ReviewsResponse, StudiesResponse } from "./types";

const REVIEW_ID = "sdtm_spec_sample_ae_001_mapping_v1_001";

const studiesPayload: StudiesResponse = {
  studies: [{ study_id: "SAMPLE-AE-001", title: "Sample AE" }],
  partial_errors: [],
};

const basePocState: PocState = {
  schema_version: "2.0",
  study_id: "SAMPLE-AE-001",
  target_artifact: "sdtm_ae_dataset",
  run_id: "run-poc-test",
  run_state: "blocked",
  legacy_run_state: "blocked_review",
  source: {
    format: "sas7bdat",
    sha256: "a".repeat(64),
  },
  knowledge: {
    scope: "p9-poc-test-only",
  },
  input_check: {
    checked_at: "2026-07-17T00:00:00+00:00",
    summary: {
      status: "warning",
      required_total: 1,
      required_ready: 1,
      blocking_count: 0,
      warning_count: 1,
      message: "原始 AE 数据已就绪；值标签不可用不阻断当前目标。",
    },
    files: [
      {
        source_id: "raw-ae",
        label: "AE SAS source",
        relative_path: "input/raw/ae.sas7bdat",
        format: "sas7bdat",
        exists: true,
        sha256: "a".repeat(64),
        size_bytes: 4096,
        parser: "pyreadstat",
        parser_available: true,
        row_count: 1066,
        column_count: 73,
        labels_available: true,
        formats_available: true,
        value_labels_available: false,
        warnings: ["值标签不可用"],
        evidence_refs: ["input/raw/ae.sas7bdat"],
      },
    ],
    dependencies: [
      {
        input_id: "source-data",
        label: "原始 AE 数据",
        requirement: "required",
        status: "available",
        blocking: false,
        detail: "SAS7BDAT 可解析。",
        evidence_refs: ["input/raw/ae.sas7bdat"],
      },
      ...["Protocol", "SAP", "CRF"].map((label) => ({
        input_id: label.toLowerCase(),
        label,
        requirement: "not_required" as const,
        status: "not_required" as const,
        blocking: false,
        detail: "当前 SDTM AE 最小目标不要求该输入。",
        evidence_refs: [],
      })),
    ],
    checks: [
      {
        check_id: "INPUT-SOURCE-PARSER",
        state: "pass",
        summary: "SAS7BDAT parser 可用",
        observed: true,
        expected: true,
        affected_variables: [],
        evidence_refs: ["input/raw/ae.sas7bdat"],
      },
    ],
    variable_profiles: [
      {
        variable: "AETERM",
        label: "Reported Term for the Adverse Event",
        data_type: "character",
        format: "$200.",
        missing_count: 128,
        non_missing_count: 938,
        distinct_count: 412,
        value_labels_available: false,
        evidence_refs: ["input/raw/ae.sas7bdat#AETERM"],
      },
    ],
    warnings: ["value labels unavailable"],
  },
  blocker: {
    kind: "review",
    stage_id: "mapping-spec",
    code: "review_decision_required",
    summary: "MappingSpec 等待人工审核",
    detail: "ReviewPacket 已生成；提交 DecisionReceipt 后才可继续。",
    affected_variables: ["AETERM"],
    affected_artifacts: ["work/mapping/ae-mapping-spec-candidate.json"],
    evidence_refs: [`.review_queue/${REVIEW_ID}.json`],
    recovery_action: "submit_review_decision",
    review_id: REVIEW_ID,
    retryable: false,
  },
  blocking_reason: "pending review",
  active_step: {
    step_id: "mapping-spec",
    kind: "review",
    title: "MappingSpec",
    summary: "POC runner 已在审核点暂停。",
    blocking_reason: "pending review",
    next_instruction: "审核 MappingSpec 后提交 DecisionReceipt。",
    review_id: REVIEW_ID,
    artifact_refs: [mappingArtifact()],
  },
  steps: [
    {
      step_id: "input-check",
      ordinal: 1,
      title: "Input Check",
      state: "done",
      kind: "instruction",
      summary: "source ready with one non-blocking warning",
      checks: [
        {
          check_id: "INPUT-SOURCE-PARSER",
          state: "pass",
          summary: "SAS7BDAT parser 可用",
          affected_variables: [],
          evidence_refs: ["input/raw/ae.sas7bdat"],
        },
      ],
      input_refs: ["source-inventory.yaml", "input/raw/ae.sas7bdat"],
      artifact_refs: [],
      evidence_refs: ["input/raw/ae.sas7bdat"],
    },
    {
      step_id: "mapping-spec",
      ordinal: 2,
      title: "MappingSpec",
      state: "blocked",
      kind: "review",
      summary: "review required",
      checks: [
        {
          check_id: "MAPPING-REVIEW-GATE",
          state: "fail",
          summary: "DecisionReceipt 尚未提交",
          affected_variables: ["AETERM"],
          evidence_refs: [`.review_queue/${REVIEW_ID}.json`],
        },
      ],
      blocking_reason: "pending review",
      review_id: REVIEW_ID,
      input_refs: ["work/derived/edc/source-metadata.json", "work/knowledge/ae-wiki-context.json"],
      artifact_refs: [mappingArtifact()],
      evidence_refs: [`.review_queue/${REVIEW_ID}.json`],
    },
  ],
  next_actions: [
    {
      action_id: "run_poc",
      label: "Run POC",
      enabled: false,
      primary: false,
      reason: "current run is blocked",
      method: "POST",
      endpoint: "/api/v1/studies/SAMPLE-AE-001/poc-runs",
    },
    {
      action_id: "retry_current_step",
      label: "Retry current stage",
      enabled: false,
      primary: false,
      reason: "review blocker is not retryable",
      method: "POST",
      endpoint: "/api/v1/studies/SAMPLE-AE-001/poc-runs/run-poc-test/resume",
    },
    {
      action_id: "open_review",
      label: "Open review",
      enabled: true,
      primary: true,
      method: "GET",
      endpoint: `/api/v1/studies/SAMPLE-AE-001/reviews/${REVIEW_ID}`,
    },
    {
      action_id: "resume",
      label: "Resume",
      enabled: false,
      primary: false,
      reason: "DecisionReceipt is not available",
      method: "POST",
      endpoint: "/api/v1/studies/SAMPLE-AE-001/poc-runs/run-poc-test/resume",
    },
    {
      action_id: "refresh",
      label: "Refresh",
      enabled: true,
      primary: false,
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
      run_id: "run-poc-test",
      step_id: "mapping-spec",
      summary: "blocked",
      severity: "warning",
      related_refs: [],
    },
  ],
  partial_errors: [],
};

const reviewsPayload: ReviewsResponse = {
  reviews: [
    {
      review_id: REVIEW_ID,
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

let currentPocState: PocState;
let failStudiesRequest = false;

describe("Clinical POC Workbench shell", () => {
  beforeEach(() => {
    currentPocState = structuredClone(basePocState);
    failStudiesRequest = false;
    window.history.replaceState(null, "", "/");
    globalThis.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/api/v1/studies")) {
        if (failStudiesRequest) throw new Error("Application API unavailable");
        return jsonResponse(studiesPayload);
      }
      if (url.endsWith("/poc-state")) return jsonResponse(currentPocState);
      if (url.endsWith("/reviews")) return jsonResponse(reviewsPayload);
      if (url.endsWith("/artifacts/work-mapping-ae-spec")) {
        return jsonResponse({
          artifact: {
            artifact_id: "work-mapping-ae-spec",
            stage_id: "sdtm_spec",
            artifact_state: "draft",
            artifact_type: "mapping_spec",
            display_name: "work/mapping/ae-mapping-spec-candidate.json",
            sha256: "c".repeat(64),
            provenance_id: null,
            preview_available: true,
          },
          registered_ref: {
            container_id: "clinical-studies",
            relative_path: "SAMPLE-AE-001/work/mapping/ae-mapping-spec-candidate.json",
            sha256: "c".repeat(64),
          },
          preview: {
            kind: "json",
            value: {
              spec_id: "ae-mapping-spec-sample-ae-001-v1",
              status: "candidate",
              target_dataset: "AE",
              source: { relative_path: "input/raw/ae.sas7bdat", sha256: "a".repeat(64) },
              knowledge: { snapshot_id: "snapshot-sdtmig34-core-events-ae-v1" },
              mappings: [
                {
                  mapping_id: "map-aeterm",
                  target_variable: "AETERM",
                  source_variables: ["AETERM"],
                  operation: "copy_trim",
                  parameters: {},
                  rule_refs: ["proposal-sdtmig34-gold-aeterm-required-v1"],
                  review_status: "review_required",
                },
              ],
              explicit_gaps: [
                {
                  gap_id: "gap-controlled-value-labels",
                  affects_variables: ["AESEV"],
                  description: "Value labels unavailable",
                },
              ],
            },
          },
        });
      }
      if (url.endsWith(`/reviews/${REVIEW_ID}/decisions`)) {
        const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
        return jsonResponse(
          {
            review_id: body.review_id,
            decision_receipt_id: `${REVIEW_ID}_decision`,
            written: true,
            idempotency_key: "ui-review-test-key",
          },
          201,
        );
      }
      if (url.endsWith("/poc-runs/run-poc-test/resume")) {
        return jsonResponse({
          accepted: true,
          run_id: "run-poc-test",
          run_state: "blocked",
          state_endpoint: "/api/v1/studies/SAMPLE-AE-001/poc-state",
          message: "action accepted",
        });
      }
      return jsonResponse({}, 404);
    }) as typeof fetch;
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders the test-only header, compact run bar, horizontal stages, and collapsed activity", async () => {
    render(<App />);

    expect(screen.getByText("正在读取 POC 状态…")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "SAMPLE-AE-001" })).toBeInTheDocument();
    expect(screen.getByText("p9-poc-test-only")).toBeInTheDocument();
    expect(screen.getByText("1/1")).toBeInTheDocument();
    expect(screen.getByText("review · review_decision_required")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "POC stages" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Input Check/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /MappingSpec/ })).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("Activity / Evidence").closest("details")).not.toHaveAttribute("open");
    expect(screen.getByRole("button", { name: "Open review" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Run POC" })).toBeDisabled();
  });

  it("shows target-scoped source metadata, optional dependencies, and variable profile", async () => {
    render(<App />);

    await screen.findByRole("heading", { name: REVIEW_ID });
    fireEvent.click(screen.getByRole("button", { name: /Input Check/ }));
    fireEvent.click(screen.getByRole("tab", { name: "输入与证据" }));

    expect(screen.getByText("1066 × 73")).toBeInTheDocument();
    expect(screen.getByText("Reported Term for the Adverse Event")).toBeInTheDocument();
    expect(screen.getByText("128")).toBeInTheDocument();
    expect(screen.getAllByText("not_required")).toHaveLength(6);
    expect(window.location.hash).toBe("#step=input-check&view=input");
  });

  it("shows selected-stage inputs and evidence without repeating the global input profile", async () => {
    render(<App />);

    await screen.findByRole("heading", { name: REVIEW_ID });
    fireEvent.click(screen.getByRole("button", { name: /MappingSpec/ }));
    fireEvent.click(screen.getByRole("tab", { name: "输入与证据" }));

    expect(screen.getByRole("heading", { name: "本阶段输入" })).toBeInTheDocument();
    expect(screen.getByText("work/knowledge/ae-wiki-context.json")).toBeInTheDocument();
    expect(screen.getAllByText(`.review_queue/${REVIEW_ID}.json`)).toHaveLength(2);
    expect(screen.queryByText("1066 × 73")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "必须审核" })).toBeInTheDocument();
  });

  it("renders one finding workspace at a time and submits a DecisionReceipt", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: "确认 AETERM 映射" })).toBeInTheDocument();
    expect(document.querySelectorAll(".finding-card")).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: /DOMAIN 固定值/ }));
    expect(screen.getByRole("heading", { name: "DOMAIN 固定值" })).toBeInTheDocument();
    expect(document.querySelectorAll(".finding-card")).toHaveLength(1);

    const submit = screen.getByRole("button", { name: "Submit DecisionReceipt" });
    expect(submit).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Approve all required findings" }));
    expect(submit).toBeEnabled();
    fireEvent.click(submit);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        `/api/v1/studies/SAMPLE-AE-001/reviews/${REVIEW_ID}/decisions`,
        expect.objectContaining({ method: "POST", body: expect.stringContaining('"decision":"approved"') }),
      );
    });
    expect(await screen.findByText(/DecisionReceipt 已写入/)).toBeInTheDocument();
  });

  it("calls resume only when the backend exposes it as enabled", async () => {
    currentPocState.next_actions = currentPocState.next_actions.map((action) =>
      action.action_id === "open_review"
        ? { ...action, enabled: false, primary: false }
        : action.action_id === "resume"
          ? { ...action, enabled: true, primary: true, reason: undefined }
          : action,
    );
    currentPocState.blocker = {
      ...currentPocState.blocker!,
      recovery_action: "resume_after_review",
    };
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Resume" }));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs/run-poc-test/resume",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"reason":"review_decision_available"'),
        }),
      );
    });
  });

  it("uses retry_after_failure for an enabled validation recovery", async () => {
    currentPocState.blocker = {
      kind: "validation",
      stage_id: "mapping-spec",
      code: "mapping_validation_failed",
      summary: "MappingSpec 校验失败",
      detail: "修复候选产物后可重试当前阶段。",
      affected_variables: ["AETERM"],
      affected_artifacts: ["work/mapping/ae-mapping-spec-candidate.json"],
      evidence_refs: ["work/mapping/validation-report.json"],
      recovery_action: "retry_current_step",
      retryable: true,
    };
    currentPocState.next_actions = currentPocState.next_actions.map((action) =>
      action.action_id === "open_review"
        ? { ...action, enabled: false, primary: false }
        : action.action_id === "retry_current_step"
          ? { ...action, enabled: true, primary: true, reason: undefined }
          : action,
    );
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Retry current stage" }));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        "/api/v1/studies/SAMPLE-AE-001/poc-runs/run-poc-test/resume",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"reason":"retry_after_failure"'),
        }),
      );
    });
  });

  it("opens an artifact in the main workspace without a third column", async () => {
    render(<App />);

    await screen.findByRole("heading", { name: REVIEW_ID });
    fireEvent.click(screen.getByRole("button", { name: /MappingSpec/ }));
    fireEvent.click(screen.getByRole("tab", { name: "产物预览" }));

    expect(await screen.findByRole("heading", { name: "work/mapping/ae-mapping-spec-candidate.json" })).toBeInTheDocument();
    expect(await screen.findByText("Mapping 决策")).toBeInTheDocument();
    expect(screen.getByText("copy_trim")).toBeInTheDocument();
    expect(screen.getByText("proposal-sdtmig34-gold-aeterm-required-v1")).toBeInTheDocument();
    expect(screen.getByText("gap-controlled-value-labels")).toBeInTheDocument();
    expect(screen.getByText("SAMPLE-AE-001/work/mapping/ae-mapping-spec-candidate.json")).toBeInTheDocument();
  });

  it("does not poll a blocked run and surfaces partial evidence failures", async () => {
    const intervalSpy = vi.spyOn(window, "setInterval");
    currentPocState.partial_errors = [{ source: "audit", message: "truncated" }];
    render(<App />);
    expect(await screen.findByText("部分证据读取失败：1 项。")).toBeInTheDocument();
    expect(intervalSpy.mock.calls.some(([, delay]) => delay === 5000)).toBe(false);
  });

  it("renders API error state without inventing workflow progress", async () => {
    failStudiesRequest = true;
    render(<App />);

    expect(await screen.findByText("Application API unavailable")).toBeInTheDocument();
    expect(screen.getByText("API 状态读取失败，当前内容可能已过期。")).toBeInTheDocument();
    expect(screen.getByText("Runner ledger 尚未生成。")).toBeInTheDocument();
  });
});

function mappingArtifact() {
  return {
    artifact_id: "work-mapping-ae-spec",
    label: "work/mapping/ae-mapping-spec-candidate.json",
    relative_path: "work/mapping/ae-mapping-spec-candidate.json",
    kind: "json",
    sha256: "c".repeat(64),
    preview_available: true,
  };
}

function jsonResponse(payload: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
  } as Response;
}
