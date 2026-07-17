import type {
  ArtifactDetail,
  PocRunResponse,
  PocState,
  ReviewDecisionAccepted,
  ReviewDecisionRequest,
  ReviewsResponse,
  StudiesResponse,
} from "./types";

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = (await response.json().catch(() => ({}))) as T & {
    message?: string;
    code?: string;
  };
  if (!response.ok) {
    throw new Error(payload.message ?? payload.code ?? `HTTP ${response.status}`);
  }
  return payload;
}

export async function getStudies(): Promise<StudiesResponse> {
  return parseResponse<StudiesResponse>(
    await fetch("/api/v1/studies", { headers: { Accept: "application/json" } }),
  );
}

export async function getPocState(studyId: string): Promise<PocState> {
  return parseResponse<PocState>(
    await fetch(`/api/v1/studies/${encodeURIComponent(studyId)}/poc-state`, {
      headers: { Accept: "application/json" },
    }),
  );
}

export async function getArtifactDetail(studyId: string, artifactId: string): Promise<ArtifactDetail> {
  return parseResponse<ArtifactDetail>(
    await fetch(
      `/api/v1/studies/${encodeURIComponent(studyId)}/artifacts/${encodeURIComponent(artifactId)}`,
      {
        headers: { Accept: "application/json" },
      },
    ),
  );
}

export async function startPocRun(studyId: string): Promise<PocRunResponse> {
  return parseResponse<PocRunResponse>(
    await fetch(`/api/v1/studies/${encodeURIComponent(studyId)}/poc-runs`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        target_artifact: "sdtm_ae_dataset",
        intent: "生成 SAMPLE-AE-001 SDTM AE 最小 POC",
      }),
    }),
  );
}

export async function resumePocRun(
  studyId: string,
  runId: string,
  reason: "review_decision_available" | "retry_after_failure",
  reviewId?: string | null,
): Promise<PocRunResponse> {
  return parseResponse<PocRunResponse>(
    await fetch(
      `/api/v1/studies/${encodeURIComponent(studyId)}/poc-runs/${encodeURIComponent(runId)}/resume`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reason, review_id: reviewId ?? undefined }),
      },
    ),
  );
}

export async function getReviews(studyId: string): Promise<ReviewsResponse> {
  return parseResponse<ReviewsResponse>(
    await fetch(`/api/v1/studies/${encodeURIComponent(studyId)}/reviews`, {
      headers: { Accept: "application/json" },
    }),
  );
}

export async function submitReviewDecision(
  studyId: string,
  reviewId: string,
  payload: ReviewDecisionRequest,
): Promise<ReviewDecisionAccepted> {
  return parseResponse<ReviewDecisionAccepted>(
    await fetch(
      `/api/v1/studies/${encodeURIComponent(studyId)}/reviews/${encodeURIComponent(reviewId)}/decisions`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "Idempotency-Key": `ui-review-${Date.now()}-${reviewId}`,
        },
        body: JSON.stringify(payload),
      },
    ),
  );
}
