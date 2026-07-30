import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getJson, postAction } from "../api/client";
import {
  API_PATHS,
  type CancelReceipt,
  type ProcessingRun,
  type ProcessingRunCollection,
  type RetryReceipt,
} from "../contracts/knowledgeApi";
import styles from "./pages.module.css";

const ACTIVE_STATUSES = new Set(["queued", "processing"]);

export function ProcessingPage() {
  const queryClient = useQueryClient();
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["processing-runs"] }),
  });
  const cancel = useMutation({
    mutationFn: (runId: string) =>
      postAction<CancelReceipt>(`${API_PATHS.processingRuns}/${runId}/cancel`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["processing-runs"] }),
  });

  const items = runs.data?.data.items ?? [];

  return (
    <section className={styles.page} aria-labelledby="processing-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>Durable document jobs / no stream semantics</p>
          <h1 className={styles.title} id="processing-title">
            Processing
          </h1>
          <p className={styles.lede}>
            run、step 与 attempt 来自 PostgreSQL 账本。原始对象、派生对象和 Evidence
            分别计数，页面不会模拟 chunk、token 或 watermark。
          </p>
        </div>
        <div className={styles.headerAside}>
          <span className={styles.asideLabel}>Refresh</span>
          <span className={styles.asideValue}>
            {items.some((run) => ACTIVE_STATUSES.has(run.status))
              ? "active · 2s poll"
              : "terminal · stopped"}
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
          <p>正在读取 durable ledger…</p>
        </div>
      ) : null}
      {runs.isError ? (
        <div className={`${styles.statePanel} ${styles.error}`} role="alert">
          <p>无法读取 ProcessingRun；页面不会从对象列表猜测任务状态。</p>
        </div>
      ) : null}
      {runs.isSuccess && items.length === 0 ? (
        <div className={styles.statePanel}>
          <p>尚无处理任务。请先在 Sources 登记合法来源。</p>
        </div>
      ) : null}
      {items.length > 0 ? (
        <div className={styles.runList}>
          {items.map((run) => (
            <RunCard
              key={run.runId}
              run={run}
              onRetry={(stepId) => retry.mutate({ runId: run.runId, stepId })}
              onCancel={() => cancel.mutate(run.runId)}
              actionPending={retry.isPending || cancel.isPending}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}

function RunCard({
  run,
  onRetry,
  onCancel,
  actionPending,
}: {
  run: ProcessingRun;
  onRetry: (stepId: string) => void;
  onCancel: () => void;
  actionPending: boolean;
}) {
  return (
    <article className={styles.runCard}>
      <header className={styles.runHeader}>
        <div>
          <span className={styles.secondary}>{run.runId}</span>
          <h2 className={styles.runTitle}>{run.sourceVersionId}</h2>
        </div>
        <span className={`${styles.status} ${statusClass(run.status)}`}>
          {run.status}
        </span>
      </header>
      <dl className={styles.artifactFacts}>
        <div>
          <dt>Original</dt>
          <dd>{run.originalArtifactCount}</dd>
        </div>
        <div>
          <dt>Derived</dt>
          <dd>{run.derivedArtifactCount}</dd>
        </div>
        <div>
          <dt>Evidence</dt>
          <dd>{run.evidenceCount}</dd>
        </div>
      </dl>
      <ol className={styles.stepList}>
        {run.steps.map((step) => (
          <li className={styles.stepRow} key={step.stepId}>
            <div>
              <span className={styles.primary}>{step.stepKey}</span>
              <span className={styles.secondary}>
                {step.pool} · attempt {step.latestAttempt.attemptNumber} ·{" "}
                {step.latestAttempt.status}
              </span>
              <span className={styles.secondary}>
                depends on: {step.dependsOn.join(", ") || "none"}
              </span>
              {step.latestAttempt.checkpoint ? (
                <code className={styles.checkpoint}>
                  checkpoint · {JSON.stringify(step.latestAttempt.checkpoint)}
                </code>
              ) : null}
            </div>
            {step.status === "failed" ? (
              <button
                className={styles.secondaryButton}
                type="button"
                disabled={actionPending}
                onClick={() => onRetry(step.stepId)}
              >
                Retry linked attempt
              </button>
            ) : (
              <span className={styles.mono}>{step.status}</span>
            )}
          </li>
        ))}
      </ol>
      {ACTIVE_STATUSES.has(run.status) ? (
        <button
          className={styles.dangerButton}
          type="button"
          disabled={actionPending}
          onClick={onCancel}
        >
          Cancel run
        </button>
      ) : null}
    </article>
  );
}

function statusClass(status: string): string {
  const name = `status${status
    .split("_")
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join("")}`;
  return styles[name] ?? "";
}
