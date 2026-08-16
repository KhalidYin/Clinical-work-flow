import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getJson, postAction } from "../api/client";
import {
  API_PATHS,
  chunkProjectionPath,
  type ChunkProjection,
  type CancelReceipt,
  type ProcessingRun,
  type ProcessingRunCollection,
  type RetryReceipt,
} from "../contracts/knowledgeApi";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { statusLabel, workerPoolLabel } from "../i18n/labels";
import { statusClass } from "../i18n/statusClass";
import styles from "./pages.module.css";

const ACTIVE_STATUSES = new Set(["queued", "processing"]);

interface ProcessingSearch {
  run: string;
  evidence: string;
  chunk: string;
}

export function ProcessingPage({
  search = { run: "", evidence: "", chunk: "" },
  onSearchChange = () => undefined,
}: {
  search?: ProcessingSearch;
  onSearchChange?: (patch: Partial<ProcessingSearch>) => void;
}) {
  useDocumentTitle("处理任务");
  const queryClient = useQueryClient();
  const [pendingAction, setPendingAction] = useState<{
    runId: string;
    stepId?: string;
  } | null>(null);
  const runs = useQuery({
    queryKey: ["processing-runs"],
    queryFn: ({ signal }) =>
      getJson<ProcessingRunCollection>(API_PATHS.processingRuns, signal),
    refetchInterval: (query) => {
      const data = query.state.data?.data;
      return data?.items.some((run) => ACTIVE_STATUSES.has(run.status)) ? 2_000 : false;
    },
  });
  const retry = useMutation({
    mutationFn: ({ runId, stepId }: { runId: string; stepId: string }) =>
      postAction<RetryReceipt>(
        `${API_PATHS.processingRuns}/${runId}/steps/${stepId}/retry`,
      ),
    onSuccess: () => {
      setPendingAction(null);
      void queryClient.invalidateQueries({ queryKey: ["processing-runs"] });
    },
    onError: () => setPendingAction(null),
  });
  const cancel = useMutation({
    mutationFn: (runId: string) =>
      postAction<CancelReceipt>(`${API_PATHS.processingRuns}/${runId}/cancel`),
    onSuccess: () => {
      setPendingAction(null);
      void queryClient.invalidateQueries({ queryKey: ["processing-runs"] });
    },
    onError: () => setPendingAction(null),
  });

  const items = runs.data?.data.items ?? [];
  const projection = useQuery({
    queryKey: ["chunk-projection", search.run],
    queryFn: ({ signal }) =>
      getJson<ChunkProjection>(chunkProjectionPath(search.run), signal),
    enabled: Boolean(search.run),
  });

  return (
    <section className={styles.page} aria-labelledby="processing-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>持久化文档任务 / 非流式语义</p>
          <h1 className={styles.title} id="processing-title">
            处理任务
          </h1>
          <p className={styles.lede}>
            运行、步骤与尝试记录来自 PostgreSQL 账本。原始对象、派生对象和证据
            分别计数，页面不会模拟分块、令牌或进度水位。
          </p>
        </div>
        <div className={styles.headerAside}>
          <span className={styles.asideLabel}>刷新策略</span>
          <span className={styles.asideValue}>
            {items.some((run) => ACTIVE_STATUSES.has(run.status))
              ? "活跃 · 每 2 秒轮询"
              : "终态 · 已停止轮询"}
          </span>
        </div>
      </header>

      {runs.data?.data.partial ? (
        <div className={styles.notice} role="status">
          △ {runs.data.data.warnings.join("；") || "当前仅显示部分任务。"}
        </div>
      ) : null}
      {runs.isPending ? (
        <div className={styles.statePanel} aria-busy="true">
          <p>正在读取持久化任务账本…</p>
        </div>
      ) : null}
      {runs.isError ? (
        <div className={`${styles.statePanel} ${styles.error}`} role="alert">
          <p>无法读取处理任务；页面不会从对象列表猜测任务状态。</p>
        </div>
      ) : null}
      {runs.isSuccess && items.length === 0 ? (
        <div className={styles.statePanel}>
          <p>尚无处理任务。请先在来源管理中登记合法来源。</p>
        </div>
      ) : null}
      {items.length > 0 ? (
        <div className={styles.runList}>
          {items.map((run) => (
            <RunCard
              key={run.runId}
              run={run}
              onRetry={(stepId) => {
                setPendingAction({ runId: run.runId, stepId });
                retry.mutate({ runId: run.runId, stepId });
              }}
              onCancel={() => {
                setPendingAction({ runId: run.runId });
                cancel.mutate(run.runId);
              }}
              pendingRunId={pendingAction?.runId ?? null}
              pendingStepId={pendingAction?.stepId ?? null}
              onInspect={() =>
                onSearchChange({ run: run.runId, evidence: "", chunk: "" })
              }
            />
          ))}
        </div>
      ) : null}
      {search.run ? (
        <ChunkInspector
          projection={projection.data?.data}
          isPending={projection.isPending}
          isError={projection.isError}
          selectedEvidenceId={search.evidence}
          selectedChunkId={search.chunk}
          onSearchChange={onSearchChange}
        />
      ) : null}
    </section>
  );
}

function RunCard({
  run,
  onRetry,
  onCancel,
  pendingRunId,
  pendingStepId,
  onInspect,
}: {
  run: ProcessingRun;
  onRetry: (stepId: string) => void;
  onCancel: () => void;
  pendingRunId: string | null;
  pendingStepId: string | null;
  onInspect: () => void;
}) {
  return (
    <article className={styles.runCard}>
      <header className={styles.runHeader}>
        <div>
          <span className={styles.secondary}>{run.runId}</span>
          <h2 className={styles.runTitle}>{run.sourceVersionId}</h2>
        </div>
        <span className={`${styles.status} ${statusClass(run.status)}`}>
          {statusLabel(run.status)}
        </span>
      </header>
      <dl className={styles.artifactFacts}>
        <div>
          <dt>原始对象</dt>
          <dd>{run.originalArtifactCount}</dd>
        </div>
        <div>
          <dt>派生对象</dt>
          <dd>{run.derivedArtifactCount}</dd>
        </div>
        <div>
          <dt>证据</dt>
          <dd>{run.evidenceCount}</dd>
        </div>
      </dl>
      {run.status === "evidence_ready" ? (
        <p className={styles.gateNote}>
          Evidence 已就绪；尚无可供作者确认的 Candidate。
        </p>
      ) : null}
      <ol className={styles.stepList}>
        {run.steps.map((step) => (
          <li className={styles.stepRow} key={step.stepId}>
            <div>
              <span className={styles.primary}>{step.stepKey}</span>
              <span className={styles.secondary}>
                {workerPoolLabel(step.pool)} · 第 {step.latestAttempt.attemptNumber} 次尝试 ·{" "}
                {statusLabel(step.latestAttempt.status)}
              </span>
              <span className={styles.secondary}>
                依赖：{step.dependsOn.join("、") || "无"}
              </span>
              {step.latestAttempt.checkpoint ? (
                <code className={styles.checkpoint}>
                  检查点 · {JSON.stringify(step.latestAttempt.checkpoint)}
                </code>
              ) : null}
            </div>
            {step.status === "failed" ? (
              <button
                className={styles.secondaryButton}
                type="button"
                disabled={pendingRunId === run.runId && pendingStepId === step.stepId}
                onClick={() => onRetry(step.stepId)}
              >
                {pendingRunId === run.runId && pendingStepId === step.stepId
                  ? "重试中…"
                  : "重试关联尝试"}
              </button>
            ) : (
              <span className={styles.mono}>{statusLabel(step.status)}</span>
            )}
          </li>
        ))}
      </ol>
      {ACTIVE_STATUSES.has(run.status) ? (
        <button
          className={styles.dangerButton}
          type="button"
          disabled={pendingRunId === run.runId}
          onClick={onCancel}
        >
          {pendingRunId === run.runId ? "取消中…" : "取消任务"}
        </button>
      ) : null}
      <button className={styles.secondaryButton} type="button" onClick={onInspect}>
        查看 Evidence / Chunk
      </button>
    </article>
  );
}

function ChunkInspector({
  projection,
  isPending,
  isError,
  selectedEvidenceId,
  selectedChunkId,
  onSearchChange,
}: {
  projection: ChunkProjection | undefined;
  isPending: boolean;
  isError: boolean;
  selectedEvidenceId: string;
  selectedChunkId: string;
  onSearchChange: (patch: Partial<ProcessingSearch>) => void;
}) {
  const evidence =
    projection?.evidence.find((item) => item.evidenceId === selectedEvidenceId) ??
    projection?.evidence[0];
  const chunk =
    projection?.chunks.find((item) => item.chunkId === selectedChunkId) ??
    projection?.chunks.find((item) =>
      item.spans.some((span) => span.evidenceId === evidence?.evidenceId),
    ) ??
    projection?.chunks[0];

  function selectEvidence(evidenceId: string) {
    const matchingChunk = projection?.chunks.find((item) =>
      item.spans.some(
        (span) => span.evidenceId === evidenceId && span.spanRole === "primary",
      ),
    );
    onSearchChange({ evidence: evidenceId, chunk: matchingChunk?.chunkId ?? "" });
  }

  function selectChunk(chunkId: string) {
    const matchingChunk = projection?.chunks.find((item) => item.chunkId === chunkId);
    const primary = matchingChunk?.spans.find((span) => span.spanRole === "primary");
    onSearchChange({ chunk: chunkId, evidence: primary?.evidenceId ?? "" });
  }

  return (
    <section className={styles.runCard} aria-labelledby="chunk-inspector-title">
      <header className={styles.runHeader}>
        <div>
          <span className={styles.secondary}>只读治理投影</span>
          <h2 className={styles.runTitle} id="chunk-inspector-title">
            Evidence 与 Chunk Inspector
          </h2>
        </div>
        {projection ? <span className={styles.mono}>{projection.runId}</span> : null}
      </header>
      {isPending ? <div className={styles.statePanel}>正在读取 Chunk 投影…</div> : null}
      {isError ? (
        <div className={`${styles.statePanel} ${styles.error}`} role="alert">
          无法读取 Chunk 投影；不会从运行计数猜测分块内容。
        </div>
      ) : null}
      {projection ? (
        <>
          <dl className={styles.artifactFacts}>
            <div><dt>Profile</dt><dd>{projection.chunkProfile.chunkProfileId}</dd></div>
            <div><dt>目标范围</dt><dd>{projection.chunkProfile.targetMinTokens}–{projection.chunkProfile.targetMaxTokens}</dd></div>
            <div><dt>硬上限</dt><dd>{projection.chunkProfile.hardMaxTokens}</dd></div>
            <div><dt>重叠</dt><dd>Overlap {projection.chunkProfile.overlapTokens}</dd></div>
          </dl>
          <div className={styles.reviewGrid}>
            <section className={styles.evidenceColumn} aria-label="Evidence 列表与详情">
              <div className={styles.buttonRow}>
                {projection.evidence.map((item) => (
                  <button
                    className={styles.secondaryButton}
                    type="button"
                    key={item.evidenceId}
                    aria-pressed={item.evidenceId === evidence?.evidenceId}
                    onClick={() => selectEvidence(item.evidenceId)}
                  >
                    Evidence {item.evidenceId}
                  </button>
                ))}
              </div>
              {evidence ? (
                <article className={styles.evidencePaper}>
                  <strong>{evidence.evidenceId}</strong>
                  <p>{evidence.content}</p>
                  <span className={styles.secondary}>{formatRecord(evidence.locator)}</span>
                  <code className={styles.hashLine}>sha256:{evidence.contentSha256}</code>
                </article>
              ) : <p>此投影没有 Evidence。</p>}
            </section>
            <section className={styles.governanceColumn} aria-label="Chunk 列表与详情">
              <div className={styles.buttonRow}>
                {projection.chunks.map((item) => (
                  <button
                    className={styles.secondaryButton}
                    type="button"
                    key={item.chunkId}
                    aria-pressed={item.chunkId === chunk?.chunkId}
                    onClick={() => selectChunk(item.chunkId)}
                  >
                    Chunk {item.chunkId}
                  </button>
                ))}
              </div>
              {chunk ? (
                <article className={styles.evidencePaper}>
                  <strong>{chunk.chunkId}</strong>
                  <span className={styles.secondary}>{chunk.tokenCount} tokens</span>
                  <p>{chunk.content}</p>
                  <span className={styles.secondary}>边界：{chunk.dataBoundary}</span>
                  <span className={styles.secondary}>定位：{formatRecord(chunk.locator)}</span>
                  <span className={styles.secondary}>权利：{formatRecord(chunk.rights)}</span>
                  <ul>
                    {chunk.spans.map((span) => (
                      <li key={`${span.evidenceId}:${span.position}`}>
                        {span.spanRole} · {span.evidenceId} · {span.startOffset}–{span.endOffset}
                      </li>
                    ))}
                  </ul>
                </article>
              ) : <p>此投影没有 Chunk。</p>}
            </section>
          </div>
          {projection.findings.length > 0 ? (
            <div className={styles.notice} role="status">
              <span>质量发现：</span>
              {projection.findings.map((item) => (
                <span key={item.findingId}>{item.findingType}</span>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function formatRecord(value: Record<string, unknown>): string {
  return Object.entries(value).map(([key, item]) => `${key}: ${String(item)}`).join(" · ");
}
