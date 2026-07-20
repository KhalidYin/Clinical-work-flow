import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ArtifactPreview } from "./ArtifactPreview";

describe("ArtifactPreview structured clinical artifacts", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders the exact test-only Wiki rules and source locators", async () => {
    globalThis.fetch = vi.fn(async () => jsonResponse({
      artifact: {
        artifact_id: "wiki-context",
        stage_id: "wiki-context",
        artifact_state: "generated",
        artifact_type: "knowledge_context",
        display_name: "ae-wiki-context.json",
        sha256: "a".repeat(64),
        preview_available: true,
      },
      registered_ref: {
        container_id: "clinical-studies",
        relative_path: "SAMPLE-AE-001/work/knowledge/ae-wiki-context.json",
        sha256: "a".repeat(64),
      },
      preview: {
        kind: "json",
        value: {
          scope: "p9-poc-test-only",
          production_eligible: false,
          snapshot: {
            snapshot_id: "snapshot-sdtmig34-core-events-ae-v1",
            version: "1.0.0",
            sha256: "b".repeat(64),
          },
          release: {
            release_id: "release-sdtmig34-proposals-v1",
            source_id: "src-cdisc-sdtmig-3-4",
          },
          rules: [
            {
              rule_id: "proposal-sdtmig34-gold-aeterm-required-v1",
              statement: "AE.AETERM is required as the topic variable.",
              source_version: "SDTMIG 3.4",
              locators: [{ locator_id: "loc-sdtmig34-p137-aeterm-assumption" }],
            },
          ],
        },
      },
    })) as typeof fetch;

    render(<ArtifactPreview artifactId="wiki-context" studyId="SAMPLE-AE-001" />);

    expect(await screen.findByText("测试用 Wiki Context")).toBeInTheDocument();
    expect(screen.getByText("proposal-sdtmig34-gold-aeterm-required-v1")).toBeInTheDocument();
    expect(screen.getByText("loc-sdtmig34-p137-aeterm-assumption")).toBeInTheDocument();
    expect(screen.getByText(/production eligible: false/)).toBeInTheDocument();
  });
});

function jsonResponse(payload: unknown): Response {
  return {
    ok: true,
    status: 200,
    json: async () => payload,
  } as Response;
}
