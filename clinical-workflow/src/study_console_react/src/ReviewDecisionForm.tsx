import { useCallback, useEffect, useMemo, useState } from "react";

import { getReviews, submitReviewDecision } from "./api";
import type {
  FindingDecisionPayload,
  FindingDecisionValue,
  RejectionReason,
  ReviewFindingSummary,
  ReviewSummary,
} from "./types";

type DecisionDraft = {
  decision?: FindingDecisionValue;
  modified_value?: string;
  rejection_reason?: RejectionReason;
  human_correction?: string;
  comment?: string;
};

const DEFAULT_REVIEWER = "中文审核人";

export function ReviewDecisionForm({
  studyId,
  reviewId,
  onSubmitted,
}: {
  studyId: string;
  reviewId: string;
  onSubmitted: (message: string) => void;
}) {
  const [review, setReview] = useState<ReviewSummary | null>(null);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");
  const [reviewer, setReviewer] = useState(DEFAULT_REVIEWER);
  const [generalNotes, setGeneralNotes] = useState("");
  const [drafts, setDrafts] = useState<Record<string, DecisionDraft>>({});
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);

  const loadReview = useCallback(async () => {
    setLoadState("loading");
    setMessage("");
    try {
      const payload = await getReviews(studyId);
      const current = payload.reviews.find((item) => item.review_id === reviewId) ?? null;
      setReview(current);
      setLoadState("ready");
    } catch (error) {
      setLoadState("error");
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }, [reviewId, studyId]);

  useEffect(() => {
    void loadReview();
  }, [loadReview]);

  const requiredFindings = useMemo(
    () => review?.findings.filter((finding) => !finding.auto_approved) ?? [],
    [review],
  );
  const selectedFinding = useMemo(
    () =>
      review?.findings.find((finding) => finding.finding_id === selectedFindingId) ??
      requiredFindings[0] ??
      review?.findings[0] ??
      null,
    [requiredFindings, review, selectedFindingId],
  );
  const validationIssues = useMemo(
    () => validateDecisionDrafts(requiredFindings, drafts, reviewer),
    [drafts, requiredFindings, reviewer],
  );
  const canSubmit =
    loadState === "ready" &&
    review?.decision_state === "pending" &&
    requiredFindings.length > 0 &&
    validationIssues.length === 0;

  function setFindingDraft(findingId: string, patch: DecisionDraft) {
    setDrafts((current) => ({
      ...current,
      [findingId]: {
        ...current[findingId],
        ...patch,
      },
    }));
  }

  function approveAll() {
    setDrafts(
      Object.fromEntries(
        requiredFindings.map((finding) => [finding.finding_id, { decision: "approved" as const }]),
      ),
    );
  }

  async function submitDecisionReceipt() {
    if (!review || !canSubmit) {
      return;
    }
    const decisions: FindingDecisionPayload[] = requiredFindings.map((finding) =>
      toDecisionPayload(finding, drafts[finding.finding_id]),
    );
    try {
      const accepted = await submitReviewDecision(studyId, review.review_id, {
        review_id: review.review_id,
        packet_sha256: review.packet_sha256,
        reviewer,
        decisions,
        general_notes: generalNotes.trim() || undefined,
      });
      const nextMessage = `DecisionReceipt 已写入：${accepted.decision_receipt_id}`;
      setMessage(nextMessage);
      onSubmitted(nextMessage);
      await loadReview();
    } catch (error) {
      setLoadState("error");
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  if (loadState === "loading") {
    return <div className="notice">正在读取 ReviewPacket…</div>;
  }

  if (!review) {
    return <div className="notice notice-error">未找到当前 ReviewPacket：{reviewId}</div>;
  }

  return (
    <section className="review-form" aria-labelledby="review-form-title">
      <div className="review-form-header">
        <div>
          <p className="eyebrow">UI-05 · Review Gate</p>
          <h4 id="review-form-title">{review.review_id}</h4>
        </div>
        <span className={`status-pill ${review.decision_state === "pending" ? "status-warn" : "status-ok"}`}>
          {review.decision_state}
        </span>
      </div>
      <dl className="review-facts">
        <div>
          <dt>packet hash</dt>
          <dd className="mono">{review.packet_sha256.slice(0, 12)}…</dd>
        </div>
        <div>
          <dt>finding</dt>
          <dd>{review.finding_count}</dd>
        </div>
        <div>
          <dt>urgency</dt>
          <dd>{review.urgency}</dd>
        </div>
      </dl>
      {review.agent_summary ? <p>{review.agent_summary}</p> : null}
      {loadState === "error" || message ? (
        <div className={`notice ${loadState === "error" ? "notice-error" : ""}`} role="status">
          {message}
        </div>
      ) : null}
      <div className="review-controls">
        <label>
          Reviewer
          <input value={reviewer} onChange={(event) => setReviewer(event.target.value)} />
        </label>
        <label>
          General notes
          <textarea value={generalNotes} onChange={(event) => setGeneralNotes(event.target.value)} />
        </label>
      </div>
      {validationIssues.length ? (
        <ul className="validation-list" aria-label="Review form validation">
          {validationIssues.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      ) : null}
      <div className="review-layout">
        <nav className="finding-nav" aria-label="Review findings">
          <ol className="finding-nav-list">
            {review.findings.map((finding, index) => (
              <li key={finding.finding_id}>
                <button
                  aria-current={selectedFinding?.finding_id === finding.finding_id}
                  className="finding-nav-button"
                  type="button"
                  onClick={() => setSelectedFindingId(finding.finding_id)}
                >
                  <span className="mono">{index + 1}/{review.findings.length} · {finding.finding_id}</span>
                  <strong>{finding.title}</strong>
                  <small>{finding.auto_approved ? "auto-approved" : drafts[finding.finding_id]?.decision ?? "待决定"}</small>
                </button>
              </li>
            ))}
          </ol>
        </nav>
        {selectedFinding ? (
          <FindingDecisionCard
            key={selectedFinding.finding_id}
            draft={drafts[selectedFinding.finding_id] ?? {}}
            finding={selectedFinding}
            onChange={(patch) => setFindingDraft(selectedFinding.finding_id, patch)}
          />
        ) : (
          <div className="empty-state">ReviewPacket 没有 finding。</div>
        )}
      </div>
      <div className="review-submit-bar">
        <span className="help-text">
          已决定 {requiredFindings.filter((finding) => drafts[finding.finding_id]?.decision).length}/
          {requiredFindings.length} 个 required finding
        </span>
        <div className="button-row">
          <button
            className="button button-secondary"
            disabled={review.decision_state !== "pending" || requiredFindings.length === 0}
            type="button"
            onClick={approveAll}
          >
            Approve all required findings
          </button>
          <button
            className="button button-primary"
            disabled={!canSubmit}
            type="button"
            onClick={() => void submitDecisionReceipt()}
          >
            Submit DecisionReceipt
          </button>
        </div>
      </div>
    </section>
  );
}

function FindingDecisionCard({
  draft,
  finding,
  onChange,
}: {
  draft: DecisionDraft;
  finding: ReviewFindingSummary;
  onChange: (patch: DecisionDraft) => void;
}) {
  return (
    <article className={`finding-card ${finding.auto_approved ? "finding-card-muted" : ""}`}>
      <div className="finding-card-header">
        <div>
          <h5>{finding.title}</h5>
          <p className="mono">{finding.finding_id}</p>
        </div>
        <span className="status-pill status-muted">{finding.severity}</span>
      </div>
      <p>{finding.rationale}</p>
      <dl className="finding-values">
        <div>
          <dt>current</dt>
          <dd>{finding.current_value || "n/a"}</dd>
        </div>
        <div>
          <dt>proposed</dt>
          <dd>{finding.proposed_value || "n/a"}</dd>
        </div>
        <div>
          <dt>location</dt>
          <dd>{finding.location || "n/a"}</dd>
        </div>
      </dl>
      {finding.evidence_refs.length ? (
        <ul className="evidence-ref-list">
          {finding.evidence_refs.map((ref) => (
            <li key={ref}>{ref}</li>
          ))}
        </ul>
      ) : null}
      {finding.auto_approved ? (
        <p className="help-text">auto-approved finding，不需要人工 DecisionReceipt。</p>
      ) : (
        <div className="decision-grid">
          <label>
            Decision
            <select
              value={draft.decision ?? ""}
              onChange={(event) =>
                onChange({
                  decision: event.target.value as FindingDecisionValue,
                  rejection_reason: event.target.value === "rejected" ? "insufficient_evidence" : undefined,
                })
              }
            >
              <option value="">选择 decision</option>
              <option value="approved">approved</option>
              <option value="rejected">rejected</option>
              <option value="modified">modified</option>
            </select>
          </label>
          {draft.decision === "rejected" ? (
            <>
              <label>
                Rejection reason
                <select
                  value={draft.rejection_reason ?? "insufficient_evidence"}
                  onChange={(event) => onChange({ rejection_reason: event.target.value as RejectionReason })}
                >
                  <option value="insufficient_evidence">insufficient_evidence</option>
                  <option value="incorrect_variable_mapping">incorrect_variable_mapping</option>
                  <option value="incorrect_derivation">incorrect_derivation</option>
                  <option value="wrong_ct_value">wrong_ct_value</option>
                  <option value="missing_variable">missing_variable</option>
                  <option value="other">other</option>
                </select>
              </label>
              {draft.rejection_reason && draft.rejection_reason !== "insufficient_evidence" ? (
                <label>
                  Human correction
                  <textarea
                    value={draft.human_correction ?? ""}
                    onChange={(event) => onChange({ human_correction: event.target.value })}
                  />
                </label>
              ) : null}
            </>
          ) : null}
          {draft.decision === "modified" ? (
            <label>
              Modified value
              <textarea
                value={draft.modified_value ?? ""}
                onChange={(event) => onChange({ modified_value: event.target.value })}
              />
            </label>
          ) : null}
          {draft.decision ? (
            <label>
              Comment
              <textarea value={draft.comment ?? ""} onChange={(event) => onChange({ comment: event.target.value })} />
            </label>
          ) : null}
        </div>
      )}
    </article>
  );
}

function validateDecisionDrafts(
  findings: ReviewFindingSummary[],
  drafts: Record<string, DecisionDraft>,
  reviewer: string,
) {
  const issues: string[] = [];
  if (reviewer.trim().length < 2) {
    issues.push("reviewer 至少需要 2 个字符。");
  }
  for (const finding of findings) {
    const draft = drafts[finding.finding_id];
    if (!draft?.decision) {
      issues.push(`${finding.finding_id} 缺少 decision。`);
      continue;
    }
    if (draft.decision === "modified" && !draft.modified_value?.trim()) {
      issues.push(`${finding.finding_id} modified 需要 modified_value。`);
    }
    if (draft.decision === "rejected") {
      if (!draft.rejection_reason) {
        issues.push(`${finding.finding_id} rejected 需要 rejection_reason。`);
      }
      if (
        draft.rejection_reason &&
        draft.rejection_reason !== "insufficient_evidence" &&
        (draft.human_correction?.trim().length ?? 0) < 10
      ) {
        issues.push(`${finding.finding_id} rejected 非 insufficient_evidence 时需要至少 10 字符 human_correction。`);
      }
    }
  }
  return issues;
}

function toDecisionPayload(
  finding: ReviewFindingSummary,
  draft: DecisionDraft | undefined,
): FindingDecisionPayload {
  if (!draft?.decision) {
    throw new Error(`missing decision for ${finding.finding_id}`);
  }
  const payload: FindingDecisionPayload = {
    finding_id: finding.finding_id,
    decision: draft.decision,
  };
  if (draft.decision === "modified") {
    payload.modified_value = draft.modified_value?.trim();
  }
  if (draft.decision === "rejected") {
    payload.rejection_reason = draft.rejection_reason ?? "insufficient_evidence";
    if (draft.human_correction?.trim()) {
      payload.human_correction = draft.human_correction.trim();
    }
  }
  if (draft.comment?.trim()) {
    payload.comment = draft.comment.trim();
  }
  return payload;
}
