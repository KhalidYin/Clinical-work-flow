import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiRequestError, getJson, postJson } from "../api/client";
import {
  API_PATHS,
  type AuthorConfirmation,
  type AuthorConfirmationRequest,
  type CandidateCollection,
  type CandidateDetail,
  type CandidateRevision,
  type CandidateRevisionRequest,
  type CandidateSummary,
  type ReviewDecision,
  type ReviewDecisionOutcome,
  type ReviewDecisionRequest,
  type Session,
} from "../contracts/knowledgeApi";
import styles from "./pages.module.css";

interface ActionNotice {
  kind: "success" | "conflict" | "error";
  title: string;
  detail: string;
}

interface CandidateDraft {
  claim: string;
  scope: string;
  applicability: string;
  conditions: string;
  exceptions: string;
}

export function CandidatesPage() {
  const queryClient = useQueryClient();
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<CandidateDraft | null>(null);
  const [rationale, setRationale] = useState("");
  const [notice, setNotice] = useState<ActionNotice | null>(null);

  const session = useQuery({
    queryKey: ["session"],
    queryFn: ({ signal }) => getJson<Session>(API_PATHS.session, signal),
    staleTime: 60_000,
  });
  const candidates = useQuery({
    queryKey: ["candidates"],
    queryFn: ({ signal }) =>
      getJson<CandidateCollection>(API_PATHS.candidates, signal),
  });
  const items = candidates.data?.data.items ?? [];
  const sessionData = session.data?.data;

  useEffect(() => {
    if (selectedCandidateId || items.length === 0 || !sessionData) {
      return;
    }
    setSelectedCandidateId(preferredCandidate(items, sessionData).candidateId);
  }, [items, selectedCandidateId, sessionData]);

  const detail = useQuery({
    queryKey: ["candidate", selectedCandidateId],
    queryFn: ({ signal }) =>
      getJson<CandidateDetail>(`${API_PATHS.candidates}/${selectedCandidateId}`, signal),
    enabled: Boolean(selectedCandidateId),
  });
  const candidate = detail.data?.data;

  useEffect(() => {
    if (!candidate) {
      return;
    }
    setEditing(false);
    setRationale("");
    setDraft(toDraft(candidate));
  }, [candidate?.candidateId, candidate?.contentSha256]);

  const revise = useMutation({
    mutationFn: async () => {
      if (!candidate || !draft) {
        throw new Error("Candidate detail is not available.");
      }
      const request: CandidateRevisionRequest = {
        expectedRevisionNumber: candidate.revisionNumber,
        expectedContentSha256: candidate.contentSha256,
        claim: draft.claim.trim(),
        scope: parseRecord(draft.scope, "适用范围"),
        applicability: parseRecord(draft.applicability, "Applicability"),
        conditions: parseRecordList(draft.conditions, "Conditions"),
        exceptions: parseRecordList(draft.exceptions, "Exceptions"),
        idempotencyKey: idempotencyKey("revision", candidate),
      };
      if (!request.claim) {
        throw new Error("原子主张不能为空。");
      }
      return postJson<CandidateRevision, CandidateRevisionRequest>(
        `${API_PATHS.candidates}/${candidate.candidateId}/revisions`,
        request,
      );
    },
    onSuccess: (response) => {
      setNotice({
        kind: "success",
        title: `已建立 revision ${response.data.revisionNumber}`,
        detail: `新 Candidate ${response.data.candidateId} 已返回作者确认 Gate；旧 revision 保持不可覆盖。`,
      });
      setEditing(false);
      setSelectedCandidateId(response.data.candidateId);
      void queryClient.invalidateQueries({ queryKey: ["candidates"] });
    },
    onError: (error) => setNotice(toActionError(error)),
  });

  const confirm = useMutation({
    mutationFn: async () => {
      if (!candidate) {
        throw new Error("Candidate detail is not available.");
      }
      const request: AuthorConfirmationRequest = {
        expectedRevisionNumber: candidate.revisionNumber,
        expectedContentSha256: candidate.contentSha256,
        idempotencyKey: idempotencyKey("author-confirmation", candidate),
      };
      return postJson<AuthorConfirmation, AuthorConfirmationRequest>(
        `${API_PATHS.candidates}/${candidate.candidateId}/author-confirmation`,
        request,
      );
    },
    onSuccess: (response) => {
      setNotice({
        kind: "success",
        title: "已提交独立审核",
        detail: `${response.data.decisionId} · ${response.data.knowledgeRevisionId}`,
      });
      void refreshCandidateFacts(queryClient, candidate?.candidateId);
    },
    onError: (error) => setNotice(toActionError(error)),
  });

  const review = useMutation({
    mutationFn: async (decision: ReviewDecisionOutcome) => {
      if (!candidate?.knowledgeRevisionId) {
        throw new Error("Confirmed knowledge revision is not available.");
      }
      const request: ReviewDecisionRequest = {
        candidateId: candidate.candidateId,
        expectedRevisionNumber: candidate.revisionNumber,
        expectedContentSha256: candidate.contentSha256,
        decision,
        idempotencyKey: idempotencyKey("review", candidate),
        rationale: rationale.trim() || null,
      };
      return postJson<ReviewDecision, ReviewDecisionRequest>(
        `${API_PATHS.knowledgeRevisions}/${candidate.knowledgeRevisionId}/review-decision`,
        request,
      );
    },
    onSuccess: (response) => {
      const title =
        response.data.revisionStatus === "changes_requested"
          ? "已请求作者建立新 revision"
          : response.data.revisionStatus === "approved"
            ? "审核已批准，但尚未发布"
            : "审核已驳回";
      setNotice({
        kind: "success",
        title,
        detail: `${response.data.decisionId} · ${response.data.knowledgeRevisionId}`,
      });
      void refreshCandidateFacts(queryClient, candidate?.candidateId);
    },
    onError: (error) => setNotice(toActionError(error)),
  });

  const isMutating = revise.isPending || confirm.isPending || review.isPending;
  const canonicalNotice: ActionNotice | null =
    candidate?.reviewStatus === "approved"
      ? {
          kind: "success",
          title: "审核已批准，但尚未发布",
          detail: "该 KnowledgeRevision 尚未进入 immutable release。",
        }
      : null;
  const visibleNotice = notice ?? canonicalNotice;

  function selectCandidate(candidateId: string) {
    setSelectedCandidateId(candidateId);
    setNotice(null);
    setEditing(false);
  }

  function beginEdit() {
    if (!candidate) {
      return;
    }
    setDraft(toDraft(candidate));
    setNotice(null);
    setEditing(true);
  }

  function reloadCanonicalRevision() {
    setNotice(null);
    void queryClient.invalidateQueries({ queryKey: ["candidates"] });
    void detail.refetch();
  }

  return (
    <section className={styles.page} aria-labelledby="candidates-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Evidence to governed knowledge</p>
          <h1 className={styles.title} id="candidates-title">
            Candidates
          </h1>
          <p className={styles.lede}>
            Candidate revision 先由作者确认，再由独立 Reviewer
            决策；approved 仍不可供生产检索，只有 immutable release 可被消费。
          </p>
        </div>
        <div className={styles.headerAside}>
          <span className={styles.asideLabel}>Gate records</span>
          <span className={styles.asideValue}>{items.length}</span>
        </div>
      </header>

      {candidates.data?.data.partial ? (
        <div className={styles.notice} role="status">
          △ {candidates.data.data.warnings.join("；")}
        </div>
      ) : null}
      {candidates.isPending ? (
        <div className={styles.statePanel} aria-busy="true">
          <p>正在读取 Candidate governance facts…</p>
        </div>
      ) : null}
      {candidates.isError ? (
        <div className={`${styles.statePanel} ${styles.error}`} role="alert">
          <p>无法读取 Candidate；页面不会从 ProcessingRun 状态伪造候选。</p>
        </div>
      ) : null}
      {candidates.isSuccess && items.length === 0 ? (
        <div className={styles.statePanel}>
          <p>尚无 Candidate。Evidence ready 不等于等待作者确认。</p>
        </div>
      ) : null}

      {items.length > 0 ? (
        <div className={styles.candidateWorkbench}>
          <aside className={styles.candidateQueue} aria-label="Candidate 审核队列">
            <div className={styles.queueHeader}>
              <span>Governance queue</span>
              <span>{items.length.toString().padStart(2, "0")}</span>
            </div>
            {items.map((item) => (
              <CandidatePicker
                candidate={item}
                key={item.candidateId}
                selected={selectedCandidateId === item.candidateId}
                onSelect={() => selectCandidate(item.candidateId)}
              />
            ))}
          </aside>

          <div className={styles.candidateStage}>
            {visibleNotice ? (
              <div
                className={`${styles.actionNotice} ${
                  visibleNotice.kind === "success"
                    ? styles.actionSuccess
                    : styles.actionFailure
                }`}
                role={visibleNotice.kind === "success" ? "status" : "alert"}
              >
                <div>
                  <strong>{visibleNotice.title}</strong>
                  <span>{visibleNotice.detail}</span>
                </div>
                {visibleNotice.kind === "conflict" ? (
                  <button
                    className={styles.secondaryButton}
                    type="button"
                    onClick={reloadCanonicalRevision}
                  >
                    重新加载最新 revision
                  </button>
                ) : null}
              </div>
            ) : null}

            {selectedCandidateId && detail.isPending ? (
              <div
                className={styles.detailState}
                aria-label="正在加载 Candidate 详情"
                aria-busy="true"
              >
                <span className={styles.skeleton} />
                <span className={styles.skeleton} />
                <span className={styles.skeleton} />
              </div>
            ) : null}
            {selectedCandidateId && detail.isError ? (
              <div className={`${styles.detailState} ${styles.error}`} role="alert">
                无法读取 Candidate 详情；不会显示过期的审核数据。
              </div>
            ) : null}
            {candidate && draft ? (
              <CandidateReviewPanel
                candidate={candidate}
                draft={draft}
                editing={editing}
                isMutating={isMutating}
                rationale={rationale}
                session={sessionData}
                onBeginEdit={beginEdit}
                onCancelEdit={() => setEditing(false)}
                onDraftChange={setDraft}
                onRationaleChange={setRationale}
                onSaveRevision={() => revise.mutate()}
                onConfirm={() => confirm.mutate()}
                onReview={(decision) => review.mutate(decision)}
              />
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function CandidatePicker({
  candidate,
  selected,
  onSelect,
}: {
  candidate: CandidateSummary;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      className={`${styles.candidatePicker} ${
        selected ? styles.candidatePickerSelected : ""
      }`}
      type="button"
      aria-pressed={selected}
      onClick={onSelect}
    >
      <span className={styles.queueMeta}>
        {candidate.candidateId} · revision {candidate.revisionNumber}
      </span>
      <strong>{candidate.claim}</strong>
      <span className={styles.queueFoot}>
        <span className={styles.status}>{gateLabel(candidate)}</span>
        <span>{candidate.evidenceCount} evidence</span>
      </span>
    </button>
  );
}

function CandidateReviewPanel({
  candidate,
  draft,
  editing,
  isMutating,
  rationale,
  session,
  onBeginEdit,
  onCancelEdit,
  onDraftChange,
  onRationaleChange,
  onSaveRevision,
  onConfirm,
  onReview,
}: {
  candidate: CandidateDetail;
  draft: CandidateDraft;
  editing: boolean;
  isMutating: boolean;
  rationale: string;
  session: Session | undefined;
  onBeginEdit: () => void;
  onCancelEdit: () => void;
  onDraftChange: (draft: CandidateDraft) => void;
  onRationaleChange: (value: string) => void;
  onSaveRevision: () => void;
  onConfirm: () => void;
  onReview: (decision: ReviewDecisionOutcome) => void;
}) {
  const canWrite = Boolean(session?.permissions.includes("candidate:write"));
  const canSubmit = Boolean(session?.permissions.includes("candidate:submit"));
  const canReview = Boolean(session?.permissions.includes("review:decide"));
  const authorGate =
    candidate.status === "author_confirmation_required" ||
    (candidate.status === "author_confirmed" &&
      candidate.reviewStatus === "changes_requested");
  const reviewerGate =
    candidate.status === "author_confirmed" &&
    candidate.reviewStatus === "review_required" &&
    Boolean(candidate.knowledgeRevisionId);
  const ownCandidate = Boolean(
    session && candidate.authorActorId && session.actorId === candidate.authorActorId,
  );
  const rationaleRequired = rationale.trim().length === 0;

  return (
    <div className={styles.reviewGrid}>
      <section className={styles.evidenceColumn} aria-labelledby="evidence-title">
        <header className={styles.columnHeader}>
          <div>
            <span className={styles.columnIndex}>01 / Ground truth</span>
            <h2 id="evidence-title">原始证据</h2>
          </div>
          <span className={styles.panelMeta}>SOURCE HASH VERIFIED</span>
        </header>
        <div className={styles.columnBody}>
          {candidate.evidence.map((evidence) => (
            <article className={styles.evidencePaper} key={evidence.evidenceId}>
              <span className={styles.evidenceId}>{evidence.evidenceId}</span>
              <p>{evidence.content}</p>
              <dl className={styles.evidenceMeta}>
                <div>
                  <dt>Locator</dt>
                  <dd>{formatRecord(evidence.locator)}</dd>
                </div>
                <div>
                  <dt>Rights</dt>
                  <dd>{formatRecord(evidence.rights)}</dd>
                </div>
                <div>
                  <dt>Source</dt>
                  <dd>{evidence.sourceVersionId}</dd>
                </div>
              </dl>
              <code className={styles.hashLine}>
                sha256:{evidence.contentSha256}
              </code>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.governanceColumn} aria-labelledby="candidate-detail-title">
        <header className={styles.columnHeader}>
          <div>
            <span className={styles.columnIndex}>02 / Human judgment</span>
            <h2 id="candidate-detail-title">知识候选</h2>
          </div>
          <span className={styles.panelMeta}>
            {candidate.candidateId} · revision {candidate.revisionNumber}
          </span>
        </header>
        <div className={styles.columnBody}>
          <div className={styles.gateBanner}>
            <span className={styles.gateNumber}>{reviewerGate ? "2" : "1"}</span>
            <div>
              <strong>{reviewerGate ? "独立 Reviewer Gate" : "作者确认 Gate"}</strong>
              <p>
                {reviewerGate
                  ? "审核精确 revision；approved 仍需 Release Gate 才能被消费。"
                  : "确认 claim、范围、适用性和关系建议忠于左侧证据。"}
              </p>
            </div>
          </div>

          {editing ? (
            <CandidateEditor
              candidate={candidate}
              draft={draft}
              disabled={isMutating}
              onChange={onDraftChange}
            />
          ) : (
            <CandidateReadView candidate={candidate} />
          )}

          <AdvisorySignalTable candidate={candidate} />
          <RelationProposalTable candidate={candidate} />

          {authorGate && canWrite && !editing ? (
            <button
              className={styles.secondaryButton}
              type="button"
              disabled={isMutating}
              onClick={onBeginEdit}
            >
              编辑候选
            </button>
          ) : null}
          {editing ? (
            <div className={styles.buttonRow}>
              <button
                className={styles.primaryButton}
                type="button"
                disabled={isMutating}
                onClick={onSaveRevision}
              >
                保存为 revision {candidate.revisionNumber + 1}
              </button>
              <button
                className={styles.secondaryButton}
                type="button"
                disabled={isMutating}
                onClick={onCancelEdit}
              >
                取消编辑
              </button>
            </div>
          ) : null}
          {authorGate && canSubmit && !editing ? (
            <button
              className={styles.primaryButton}
              type="button"
              disabled={isMutating}
              onClick={onConfirm}
            >
              确认并提交独立审核
            </button>
          ) : null}

          {reviewerGate && canReview && ownCandidate ? (
            <div className={styles.sodWarning} role="alert">
              作者不能审核自己的 Candidate；后端职责分离 Gate 仍会拒绝该操作。
            </div>
          ) : null}
          {reviewerGate && canReview && !ownCandidate ? (
            <div className={styles.reviewActions}>
              <label htmlFor="review-rationale">审核理由</label>
              <textarea
                id="review-rationale"
                value={rationale}
                maxLength={4000}
                onChange={(event) => onRationaleChange(event.target.value)}
                placeholder="驳回或请求修改时必须说明可执行原因。"
              />
              <div className={styles.buttonRow}>
                <button
                  className={styles.primaryButton}
                  type="button"
                  disabled={isMutating}
                  onClick={() => onReview("approved")}
                >
                  审核通过
                </button>
                <button
                  className={styles.secondaryButton}
                  type="button"
                  disabled={isMutating || rationaleRequired}
                  onClick={() => onReview("changes_requested")}
                >
                  请求修改
                </button>
                <button
                  className={styles.dangerButton}
                  type="button"
                  disabled={isMutating || rationaleRequired}
                  onClick={() => onReview("rejected")}
                >
                  驳回
                </button>
              </div>
            </div>
          ) : null}

          {!editing && !canSubmit && !canReview ? (
            <p className={styles.readOnlyNote}>
              当前身份为只读视图；操作能力由后端会话权限决定。
            </p>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function CandidateReadView({ candidate }: { candidate: CandidateDetail }) {
  return (
    <div className={styles.candidateReadView}>
      <div>
        <span>原子主张</span>
        <p>{candidate.claim}</p>
      </div>
      <div className={styles.recordPair}>
        <div>
          <span>Scope</span>
          <pre>{pretty(candidate.scope)}</pre>
        </div>
        <div>
          <span>Applicability</span>
          <pre>{pretty(candidate.applicability)}</pre>
        </div>
      </div>
      <code className={styles.hashLine}>sha256:{candidate.contentSha256}</code>
    </div>
  );
}

function CandidateEditor({
  candidate,
  draft,
  disabled,
  onChange,
}: {
  candidate: CandidateDetail;
  draft: CandidateDraft;
  disabled: boolean;
  onChange: (draft: CandidateDraft) => void;
}) {
  const update = (key: keyof CandidateDraft, value: string) =>
    onChange({ ...draft, [key]: value });

  return (
    <div className={styles.editor}>
      <label htmlFor="candidate-claim">原子主张</label>
      <textarea
        id="candidate-claim"
        value={draft.claim}
        disabled={disabled}
        onChange={(event) => update("claim", event.target.value)}
      />
      <div className={styles.editorPair}>
        <label>
          适用范围（JSON object）
          <textarea
            value={draft.scope}
            disabled={disabled}
            onChange={(event) => update("scope", event.target.value)}
          />
        </label>
        <label>
          Applicability（JSON object）
          <textarea
            value={draft.applicability}
            disabled={disabled}
            onChange={(event) => update("applicability", event.target.value)}
          />
        </label>
        <label>
          Conditions（JSON array）
          <textarea
            value={draft.conditions}
            disabled={disabled}
            onChange={(event) => update("conditions", event.target.value)}
          />
        </label>
        <label>
          Exceptions（JSON array）
          <textarea
            value={draft.exceptions}
            disabled={disabled}
            onChange={(event) => update("exceptions", event.target.value)}
          />
        </label>
      </div>
      <p className={styles.editNote}>
        保存会建立 revision {candidate.revisionNumber + 1}，不会覆盖当前事实。
      </p>
    </div>
  );
}

function AdvisorySignalTable({ candidate }: { candidate: CandidateDetail }) {
  return (
    <div className={styles.relationSection}>
      <div className={styles.sectionLabel}>
        <span>模型提示</span>
        <span>Advisory only · {candidate.advisorySignals.length}</span>
      </div>
      {candidate.originModelInvocationId ? (
        <code className={styles.hashLine}>
          invocation:{candidate.originModelInvocationId}
        </code>
      ) : null}
      {candidate.advisorySignals.length === 0 ? (
        <p className={styles.readOnlyNote}>
          没有 duplicate / conflict / gap 提示；这不代表人工核验已完成。
        </p>
      ) : (
        <div className={styles.relationTableWrap}>
          <table className={styles.relationTable}>
            <thead>
              <tr>
                <th>类型</th>
                <th>说明</th>
                <th>目标</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {candidate.advisorySignals.map((signal) => (
                <tr
                  key={`${signal.signalType}:${signal.targetKnowledgeUnitId ?? "gap"}`}
                >
                  <td>{signal.signalType}</td>
                  <td>{signal.description}</td>
                  <td>{signal.targetKnowledgeUnitId ?? "N/A"}</td>
                  <td>{signal.evidenceIds.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function RelationProposalTable({ candidate }: { candidate: CandidateDetail }) {
  return (
    <div className={styles.relationSection}>
      <div className={styles.sectionLabel}>
        <span>关系建议</span>
        <span>Proposal only · {candidate.relationProposals.length}</span>
      </div>
      {candidate.relationProposals.length === 0 ? (
        <p className={styles.readOnlyNote}>此 Candidate 没有关系建议。</p>
      ) : (
        <div className={styles.relationTableWrap}>
          <table className={styles.relationTable}>
            <thead>
              <tr>
                <th>关系</th>
                <th>目标</th>
                <th>Evidence</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {candidate.relationProposals.map((proposal) => (
                <tr
                  key={`${proposal.relationType}:${proposal.targetKnowledgeUnitId}`}
                >
                  <td>{proposal.relationType}</td>
                  <td>{proposal.targetKnowledgeUnitId}</td>
                  <td>{proposal.evidenceIds.join(", ")}</td>
                  <td>{proposal.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function preferredCandidate(items: CandidateSummary[], session: Session): CandidateSummary {
  if (session.permissions.includes("review:decide")) {
    const reviewable = items.find(
      (candidate) =>
        candidate.reviewStatus === "review_required" &&
        candidate.authorActorId !== session.actorId,
    );
    if (reviewable) {
      return reviewable;
    }
  }
  if (
    session.permissions.includes("candidate:write") ||
    session.permissions.includes("candidate:submit")
  ) {
    const authorable = items.find(
      (candidate) =>
        candidate.status === "author_confirmation_required" ||
        candidate.reviewStatus === "changes_requested",
    );
    if (authorable) {
      return authorable;
    }
  }
  return items[0];
}

function gateLabel(candidate: CandidateSummary): string {
  if (candidate.status === "author_confirmation_required") {
    return "待作者确认";
  }
  if (candidate.reviewStatus === "changes_requested") {
    return "待作者修订";
  }
  if (candidate.reviewStatus === "review_required") {
    return "待独立审核";
  }
  return candidate.reviewStatus ?? candidate.status;
}

function toDraft(candidate: CandidateDetail): CandidateDraft {
  return {
    claim: candidate.claim,
    scope: pretty(candidate.scope),
    applicability: pretty(candidate.applicability),
    conditions: pretty(candidate.conditions),
    exceptions: pretty(candidate.exceptions),
  };
}

function parseRecord(value: string, label: string): Record<string, unknown> {
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error(`${label} 必须是 JSON object。`);
  }
  if (Object.keys(parsed).length === 0) {
    throw new Error(`${label} 不能为空。`);
  }
  return parsed as Record<string, unknown>;
}

function parseRecordList(value: string, label: string): Record<string, unknown>[] {
  const parsed = JSON.parse(value) as unknown;
  if (
    !Array.isArray(parsed) ||
    parsed.some((item) => !item || Array.isArray(item) || typeof item !== "object")
  ) {
    throw new Error(`${label} 必须是 JSON object array。`);
  }
  return parsed as Record<string, unknown>[];
}

function pretty(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function formatRecord(value: Record<string, unknown>): string {
  return Object.entries(value)
    .map(([key, item]) => `${key}: ${String(item)}`)
    .join(" · ");
}

function idempotencyKey(action: string, candidate: CandidateDetail): string {
  const nonce =
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return `ui:${action}:${candidate.candidateId}:${candidate.revisionNumber}:${nonce}`.slice(
    0,
    160,
  );
}

function toActionError(error: Error): ActionNotice {
  if (error instanceof ApiRequestError && error.code === "stale_revision") {
    return {
      kind: "conflict",
      title: "Candidate 已被更新，本次操作未提交。",
      detail: "请重新加载 canonical revision，再基于新的 hash 作出决定。",
    };
  }
  return {
    kind: "error",
    title: "治理操作失败",
    detail: error.message,
  };
}

async function refreshCandidateFacts(
  queryClient: ReturnType<typeof useQueryClient>,
  candidateId: string | undefined,
) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["candidates"] }),
    candidateId
      ? queryClient.invalidateQueries({ queryKey: ["candidate", candidateId] })
      : Promise.resolve(),
  ]);
}
