import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiRequestError, getJson, postJson } from "../api/client";
import {
  API_PATHS,
  rotationCasePath,
  rotationDecisionPath,
  rotationProposalPath,
  type RotationCase,
  type RotationCaseCollection,
  type RotationDecision,
  type RotationDecisionRequest,
  type RotationOutcome,
  type RotationProposalRequest,
} from "../contracts/knowledgeApi";
import type { CandidatesSearch } from "./CandidatesPage";
import styles from "./pages.module.css";

type Notice = { kind: "success" | "error"; title: string; detail: string };

export function RotationQueue({
  search,
  onSearchChange,
}: {
  search: CandidatesSearch;
  onSearchChange: (patch: Partial<CandidatesSearch>) => void;
}) {
  const queryClient = useQueryClient();
  const [outcome, setOutcome] = useState<RotationOutcome | "">("");
  const [targetRevisionId, setTargetRevisionId] = useState("");
  const [proposalRationale, setProposalRationale] = useState("");
  const [decisionRationale, setDecisionRationale] = useState("");
  const [notice, setNotice] = useState<Notice | null>(null);
  const cases = useQuery({
    queryKey: ["rotation-cases"],
    queryFn: ({ signal }) => getJson<RotationCaseCollection>(API_PATHS.rotationCases, signal),
  });
  const filtered = (cases.data?.data.items ?? []).filter(
    (item) => !search.status || item.status === search.status,
  );

  useEffect(() => {
    if (!search.case && filtered[0]) {
      onSearchChange({ case: filtered[0].rotationCaseId });
    }
  }, [filtered, onSearchChange, search.case]);

  const detail = useQuery({
    queryKey: ["rotation-case", search.case],
    queryFn: ({ signal }) => getJson<RotationCase>(rotationCasePath(search.case), signal),
    enabled: Boolean(search.case),
  });
  const rotationCase = detail.data?.data;

  useEffect(() => {
    if (!rotationCase) return;
    setOutcome(rotationCase.proposedOutcome ?? rotationCase.eligibleOutcomes[0] ?? "");
    setTargetRevisionId(rotationCase.proposedTargetKnowledgeRevisionId ?? "");
    setProposalRationale(rotationCase.proposedRationale ?? "");
    setDecisionRationale("");
  }, [rotationCase?.rotationCaseId, rotationCase?.caseVersion]);

  const proposal = useMutation({
    mutationFn: () => {
      if (!rotationCase || !outcome) throw new Error("RotationCase 尚未加载。");
      const request: RotationProposalRequest = {
        expectedCaseVersion: rotationCase.caseVersion,
        outcome,
        targetKnowledgeRevisionId: outcome === "replace" ? targetRevisionId.trim() || null : null,
        rationale: proposalRationale.trim() || null,
        idempotencyKey: rotationIdempotencyKey("proposal", rotationCase),
      };
      return postJson<RotationCase, RotationProposalRequest>(
        rotationProposalPath(rotationCase.rotationCaseId),
        request,
      );
    },
    onSuccess: async (response) => {
      setNotice({
        kind: "success",
        title: "轮转提议已记录",
        detail: `${response.data.rotationCaseId} · case version ${response.data.caseVersion}`,
      });
      await refreshRotationFacts(queryClient, response.data.rotationCaseId);
    },
    onError: (error: Error) => setNotice(rotationError(error)),
  });

  const decision = useMutation({
    mutationFn: () => {
      if (!rotationCase?.proposedOutcome) throw new Error("尚无可供独立审核的轮转提议。");
      const request: RotationDecisionRequest = {
        expectedCaseVersion: rotationCase.caseVersion,
        outcome: rotationCase.proposedOutcome,
        targetKnowledgeRevisionId: rotationCase.proposedTargetKnowledgeRevisionId,
        rationale: decisionRationale.trim() || null,
        idempotencyKey: rotationIdempotencyKey("decision", rotationCase),
      };
      return postJson<RotationDecision, RotationDecisionRequest>(
        rotationDecisionPath(rotationCase.rotationCaseId),
        request,
      );
    },
    onSuccess: async (response) => {
      setNotice({
        kind: "success",
        title: "独立审核决定已记录",
        detail: response.data.receipt.rotationDecisionId,
      });
      queryClient.setQueryData(
        ["rotation-case", response.data.case.rotationCaseId],
        { data: response.data.case, meta: detail.data?.meta },
      );
      await queryClient.invalidateQueries({ queryKey: ["rotation-cases"] });
    },
    onError: async (error: Error) => {
      setNotice(rotationError(error));
      if (error instanceof ApiRequestError && error.code === "stale_rotation_case") {
        await detail.refetch();
      }
    },
  });

  return (
    <section className={styles.page} aria-labelledby="rotation-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>SourceVersion 变化 / 受治理轮转</p>
          <h1 className={styles.title} id="rotation-title">知识轮转队列</h1>
          <p className={styles.lede}>
            页面只提交服务端允许的提议或独立审核动作；最终纳入 Release 仍由发布门禁决定。
          </p>
        </div>
        <div className={styles.headerAside}>
          <label className={styles.asideLabel} htmlFor="rotation-status">状态</label>
          <select
            id="rotation-status"
            value={search.status}
            onChange={(event) => onSearchChange({ status: event.target.value, case: "" })}
          >
            <option value="">全部</option>
            <option value="open">open</option>
            <option value="in_review">in_review</option>
            <option value="decided">decided</option>
            <option value="included_in_release">included_in_release</option>
            <option value="closed">closed</option>
          </select>
        </div>
      </header>

      {cases.isPending ? <div className={styles.statePanel}>正在读取轮转队列…</div> : null}
      {cases.isError ? <div className={`${styles.statePanel} ${styles.error}`} role="alert">无法读取轮转队列。</div> : null}
      {cases.data?.data.partial ? <div className={styles.notice}>△ {cases.data.data.warnings.join("；")}</div> : null}
      {cases.isSuccess && filtered.length === 0 ? <div className={styles.statePanel}>此状态下没有 RotationCase。</div> : null}

      {filtered.length > 0 ? (
        <div className={styles.candidateWorkbench}>
          <aside className={styles.candidateQueue} aria-label="RotationCase 队列">
            <div className={styles.queueHeader}><span>轮转队列</span><span>{filtered.length}</span></div>
            {filtered.map((item) => (
              <button
                className={`${styles.candidatePicker} ${search.case === item.rotationCaseId ? styles.candidatePickerSelected : ""}`}
                type="button"
                key={item.rotationCaseId}
                aria-pressed={search.case === item.rotationCaseId}
                onClick={() => onSearchChange({ case: item.rotationCaseId })}
              >
                <span className={styles.queueMeta}>{item.rotationCaseId} · v{item.caseVersion}</span>
                <strong>{item.knowledgeRevisionId}</strong>
                <span className={styles.queueFoot}><span>{item.status}</span><span>{item.changeTypes.join("、")}</span></span>
              </button>
            ))}
          </aside>
          <div className={styles.candidateStage}>
            {notice ? (
              <div className={`${styles.actionNotice} ${notice.kind === "success" ? styles.actionSuccess : styles.actionFailure}`} role={notice.kind === "success" ? "status" : "alert"}>
                <div><strong>{notice.title}</strong><span>{notice.detail}</span></div>
              </div>
            ) : null}
            {detail.isPending ? <div className={styles.detailState}>正在读取 canonical RotationCase…</div> : null}
            {detail.isError ? <div className={`${styles.detailState} ${styles.error}`}>无法读取 RotationCase 详情。</div> : null}
            {rotationCase ? (
              <RotationCasePanel
                rotationCase={rotationCase}
                outcome={outcome}
                targetRevisionId={targetRevisionId}
                proposalRationale={proposalRationale}
                decisionRationale={decisionRationale}
                pending={proposal.isPending || decision.isPending}
                onOutcomeChange={setOutcome}
                onTargetChange={setTargetRevisionId}
                onProposalRationaleChange={setProposalRationale}
                onDecisionRationaleChange={setDecisionRationale}
                onPropose={() => proposal.mutate()}
                onDecide={() => decision.mutate()}
              />
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function RotationCasePanel({
  rotationCase,
  outcome,
  targetRevisionId,
  proposalRationale,
  decisionRationale,
  pending,
  onOutcomeChange,
  onTargetChange,
  onProposalRationaleChange,
  onDecisionRationaleChange,
  onPropose,
  onDecide,
}: {
  rotationCase: RotationCase;
  outcome: RotationOutcome | "";
  targetRevisionId: string;
  proposalRationale: string;
  decisionRationale: string;
  pending: boolean;
  onOutcomeChange: (value: RotationOutcome) => void;
  onTargetChange: (value: string) => void;
  onProposalRationaleChange: (value: string) => void;
  onDecisionRationaleChange: (value: string) => void;
  onPropose: () => void;
  onDecide: () => void;
}) {
  const canPropose = rotationCase.allowedActions.includes("propose");
  const canDecide = rotationCase.allowedActions.includes("decide");
  return (
    <section className={styles.governanceColumn} aria-labelledby="rotation-case-title">
      <header className={styles.columnHeader}>
        <div><span className={styles.columnIndex}>RotationCase / canonical</span><h2 id="rotation-case-title">{rotationCase.rotationCaseId}</h2></div>
        <span className={styles.panelMeta}>{rotationCase.status} · v{rotationCase.caseVersion}</span>
      </header>
      <div className={styles.columnBody}>
        <dl className={styles.artifactFacts}>
          <div><dt>KnowledgeRevision</dt><dd>{rotationCase.knowledgeRevisionId}</dd></div>
          <div><dt>变化类型</dt><dd>{rotationCase.changeTypes.join("、")}</dd></div>
          <div><dt>已发布于</dt><dd>{rotationCase.releasedInReleaseIds.join("、") || "无"}</dd></div>
          <div><dt>允许动作</dt><dd>{rotationCase.allowedActions.join("、") || "无"}</dd></div>
        </dl>
        {canPropose ? (
          <div className={styles.reviewActions}>
            <label htmlFor="rotation-outcome">拟议动作</label>
            <select id="rotation-outcome" value={outcome} onChange={(event) => onOutcomeChange(event.target.value as RotationOutcome)}>
              {rotationCase.eligibleOutcomes.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            {outcome === "replace" ? (
              <label>替代 KnowledgeRevision<input value={targetRevisionId} onChange={(event) => onTargetChange(event.target.value)} /></label>
            ) : null}
            <label htmlFor="proposal-rationale">提议理由</label>
            <textarea id="proposal-rationale" value={proposalRationale} onChange={(event) => onProposalRationaleChange(event.target.value)} />
            <button className={styles.primaryButton} type="button" disabled={pending || !outcome} onClick={onPropose}>提交轮转提议</button>
          </div>
        ) : null}
        {rotationCase.proposedOutcome ? (
          <div className={styles.gateBanner}>
            <span className={styles.gateNumber}>P</span>
            <div><strong>{rotationCase.proposedOutcome}</strong><p>{rotationCase.proposedRationale || "未提供理由"}</p></div>
          </div>
        ) : null}
        {canDecide ? (
          <div className={styles.reviewActions}>
            <label htmlFor="decision-rationale">决定理由</label>
            <textarea id="decision-rationale" value={decisionRationale} onChange={(event) => onDecisionRationaleChange(event.target.value)} />
            <button className={styles.primaryButton} type="button" disabled={pending} onClick={onDecide}>确认轮转决定</button>
          </div>
        ) : null}
        {rotationCase.receipts.map((receipt) => (
          <article className={styles.evidencePaper} key={receipt.rotationDecisionId}>
            <strong>{receipt.rotationDecisionId}</strong><p>{receipt.outcome} · {receipt.actorId}</p>
          </article>
        ))}
        {!canPropose && !canDecide && rotationCase.receipts.length === 0 ? <p className={styles.readOnlyNote}>当前状态没有可执行动作。</p> : null}
      </div>
    </section>
  );
}

function rotationIdempotencyKey(action: "proposal" | "decision", item: RotationCase): string {
  const nonce = globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  return `ui:rotation-${action}:${item.rotationCaseId}:${item.caseVersion}:${nonce}`.slice(0, 160);
}

function rotationError(error: Error): Notice {
  if (error instanceof ApiRequestError && error.code === "stale_rotation_case") {
    return { kind: "error", title: "RotationCase 已变化", detail: "已重新读取 canonical case，请基于新版本再次决定。" };
  }
  return { kind: "error", title: "轮转治理操作失败", detail: error.message };
}

async function refreshRotationFacts(queryClient: ReturnType<typeof useQueryClient>, rotationCaseId: string) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["rotation-cases"] }),
    queryClient.invalidateQueries({ queryKey: ["rotation-case", rotationCaseId] }),
  ]);
}
