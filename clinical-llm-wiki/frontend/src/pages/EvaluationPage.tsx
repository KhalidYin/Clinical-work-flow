import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getJson, postJson } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { StatePanel } from "../components/StatePanel";
import {
  API_PATHS,
  evaluationRegressionPath,
  evaluationRunPath,
  type EvaluationCase,
  type EvaluationOutcome,
  type EvaluationRegression,
  type EvaluationRunCollection,
  type EvaluationRunDetail,
  type EvaluationStartRequest,
} from "../contracts/knowledgeApi";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import styles from "./pages.module.css";

export interface EvaluationSearch {
  suite: string;
  run: string;
  outcome: "" | EvaluationOutcome;
  baseline: string;
}

interface EvaluationPageProps {
  search: EvaluationSearch;
  onSearchChange: (patch: Partial<EvaluationSearch>) => void;
  onReplay: (replay: EvaluationCase["replay"]) => void;
}

function percent(value: number): string {
  return `${(value * 100).toFixed(4)}%`;
}

function signedPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(4)}%`;
}

function listPath(search: EvaluationSearch): string {
  const params = new URLSearchParams();
  params.set(
    "purpose",
    search.outcome && search.outcome !== "informational"
      ? "release_gate_synthetic"
      : "retrieval_baseline",
  );
  if (search.suite) params.set("suite_id", search.suite);
  if (search.outcome) params.set("outcome", search.outcome);
  return `${API_PATHS.evaluations}?${params.toString()}`;
}

export function EvaluationPage({ search, onSearchChange, onReplay }: EvaluationPageProps) {
  useDocumentTitle("质量评估");
  const queryClient = useQueryClient();
  const runs = useQuery({
    queryKey: ["evaluation-runs", search.suite, search.outcome],
    queryFn: ({ signal }) => getJson<EvaluationRunCollection>(listPath(search), signal),
    staleTime: 30_000,
  });
  const items = runs.data?.data.items ?? [];
  const selectedRunId = search.run || items[0]?.evaluationRunId || "";
  const detail = useQuery({
    queryKey: ["evaluation-run", selectedRunId],
    queryFn: ({ signal }) =>
      getJson<EvaluationRunDetail>(
        evaluationRunPath(selectedRunId),
        signal,
      ),
    enabled: Boolean(selectedRunId),
    staleTime: 30_000,
  });
  const startSuite = (runs.data?.data.availableSuites ?? []).find(
    (suite) => suite.suiteId === search.suite,
  ) ?? runs.data?.data.availableSuites?.[0];
  const start = useMutation({
    mutationFn: (request: EvaluationStartRequest) =>
      postJson<EvaluationRunDetail, EvaluationStartRequest>(
        `${API_PATHS.evaluations}/runs`,
        request,
      ),
    onSuccess: async (response) => {
      queryClient.setQueryData(
        ["evaluation-run", response.data.evaluationRunId],
        response,
      );
      onSearchChange({
        suite: response.data.suiteId,
        run: response.data.evaluationRunId,
        outcome: response.data.outcome,
        baseline: "",
      });
      await queryClient.invalidateQueries({ queryKey: ["evaluation-runs"] });
    },
  });
  const regression = useQuery({
    queryKey: ["evaluation-regression", selectedRunId, search.baseline],
    queryFn: ({ signal }) =>
      getJson<EvaluationRegression>(
        evaluationRegressionPath(selectedRunId, search.baseline),
        signal,
      ),
    enabled: Boolean(selectedRunId && search.baseline),
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!search.run && items[0]) {
      onSearchChange({ run: items[0].evaluationRunId });
    }
  }, [items, onSearchChange, search.run]);

  const record = detail.data?.data;
  const suites = [...new Set(items.map((item) => item.suiteId))];

  return (
    <section className={styles.page} aria-labelledby="evaluation-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>P17-UI-05 / Immutable EvaluationRun</p>
          <h1 className={styles.title} id="evaluation-title">质量评估</h1>
          <p className={styles.lede}>
            Recall、阈值与逐题结果全部来自 PostgreSQL 中不可变的 EvaluationRun；浏览器不重算通过状态。
          </p>
        </div>
        <div className={styles.headerAside}>
          <span className={styles.asideLabel}>解释边界</span>
          <span className={styles.asideValue}>回归证据 ≠ 临床认证</span>
        </div>
      </header>

      {startSuite && runs.data?.data.allowedActions.includes("start") ? (
        <section className={styles.actionPanel} aria-label="启动评估">
          <div>
            <span className={styles.asideLabel}>服务器登记 Suite</span>
            <strong>{startSuite.suiteId} · {startSuite.suiteVersion}</strong>
            <small>{startSuite.caseCount} cases · {startSuite.documentId} · 零模型请求</small>
          </div>
          <button
            className={styles.primaryButton}
            type="button"
            disabled={start.isPending}
            onClick={() => start.mutate({
              suiteId: startSuite.suiteId,
              suiteVersion: startSuite.suiteVersion,
            })}
          >
            {start.isPending ? "运行中…" : "运行所选 Suite"}
          </button>
          {start.isError ? <small>启动失败；未创建浏览器本地评估结果。</small> : null}
        </section>
      ) : null}

      <section className={styles.evaluationFilters} aria-label="评估筛选">
        <label>
          <span className={styles.asideLabel}>Suite</span>
          <select
            value={search.suite}
            onChange={(event) => onSearchChange({ suite: event.target.value, run: "" })}
          >
            <option value="">最近 E9 baseline</option>
            {suites.map((suite) => <option key={suite} value={suite}>{suite}</option>)}
          </select>
        </label>
        <label>
          <span className={styles.asideLabel}>Run</span>
          <select
            value={selectedRunId}
            onChange={(event) => onSearchChange({ run: event.target.value })}
          >
            {items.map((item) => (
              <option key={item.evaluationRunId} value={item.evaluationRunId}>
                {item.suiteVersion} · {item.evaluationRunId.slice(-8)}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className={styles.asideLabel}>Outcome</span>
          <select
            value={search.outcome}
            onChange={(event) => onSearchChange({
              outcome: event.target.value as EvaluationSearch["outcome"],
              run: "",
            })}
          >
            <option value="">全部</option>
            <option value="informational">informational</option>
            <option value="passed">passed</option>
            <option value="failed">failed</option>
          </select>
        </label>
        <label>
          <span className={styles.asideLabel}>Regression baseline</span>
          <select
            value={search.baseline}
            onChange={(event) => onSearchChange({ baseline: event.target.value })}
          >
            <option value="">不比较</option>
            {items
              .filter((item) => item.evaluationRunId !== selectedRunId)
              .map((item) => (
                <option key={item.evaluationRunId} value={item.evaluationRunId}>
                  {item.suiteVersion} · {item.evaluationRunId.slice(-8)}
                </option>
              ))}
          </select>
        </label>
      </section>

      {runs.isPending ? <LoadingSkeleton rows={4} cols={3} /> : null}
      {runs.isError ? (
        <StatePanel symbol="!" title="无法读取评估记录" text="EvaluationRun API 暂不可用；页面没有回退到本地报告。" error />
      ) : null}
      {runs.data?.data.partial ? (
        <p className={styles.partialNotice}>部分记录完整性校验失败：{runs.data.data.warnings.join(" · ")}</p>
      ) : null}
      {runs.isSuccess && items.length === 0 ? (
        <StatePanel symbol="∅" title="没有匹配的 EvaluationRun" text="当前筛选下没有数据库记录，不以测试 fixture 或报告文件填充。" />
      ) : null}
      {detail.isPending && selectedRunId ? <LoadingSkeleton rows={5} cols={4} /> : null}
      {detail.isError ? (
        <StatePanel symbol="!" title="评估记录不可读取" text="该不可变记录不存在或未通过完整性校验。" error />
      ) : null}

      {record ? (
        <div className={styles.evaluationWorkbench}>
          <section className={styles.evaluationReceipt} aria-label="EvaluationRun 回执">
            <div>
              <span className={styles.asideLabel}>Suite / Version</span>
              <strong>{record.suiteId}</strong>
              <code>{record.suiteVersion}</code>
            </div>
            <div>
              <span className={styles.asideLabel}>Recall@5</span>
              <strong>{percent(record.metrics.recallAt5)}</strong>
              <code>{record.caseCount} cases</code>
            </div>
            <div>
              <span className={styles.asideLabel}>Recall@10</span>
              <strong>{percent(record.metrics.recallAt10)}</strong>
              <code>{record.outcome}</code>
            </div>
            <div>
              <span className={styles.asideLabel}>模型请求</span>
              <strong>{record.externalModelRequests}</strong>
              <code>{record.purpose}</code>
            </div>
          </section>

          <p className={styles.baselineNotice}>
            单文档检索基线，不是临床质量认证
            <code>{record.evaluationNotice}</code>
          </p>

          {regression.isPending && search.baseline ? <LoadingSkeleton rows={2} cols={3} /> : null}
          {regression.isError ? (
            <StatePanel symbol="!" title="无法比较 EvaluationRun" text="仅允许比较同 Suite、同用途的不可变运行。" error />
          ) : null}
          {regression.data ? (
            <section className={styles.thresholdLedger} aria-labelledby="regression-title">
              <div className={styles.sectionHeading}>
                <div>
                  <span className={styles.kicker}>Server diff</span>
                  <h2 id="regression-title">回归差异</h2>
                </div>
              </div>
              <div className={styles.naPanel}>
                <strong>
                  Recall@5 {signedPercent(regression.data.data.metricDeltas.recallAt5)}
                </strong>
                <span>
                  Recall@10 {signedPercent(regression.data.data.metricDeltas.recallAt10)}
                </span>
                <span>
                  改进 {regression.data.data.counts.improved} · 退化 {regression.data.data.counts.regressed} · 不变 {regression.data.data.counts.unchanged}
                </span>
              </div>
              <ol className={styles.evaluationCaseList}>
                {regression.data.data.caseDiffs.map((item) => (
                  <li key={item.caseId} data-state={item.change === "regressed" ? "failed" : "passed"}>
                    <strong>{item.caseId}</strong>
                    <code>{item.change}</code>
                    <span>{item.baselineOutcome ?? "N/A"} → {item.currentOutcome ?? "N/A"}</span>
                  </li>
                ))}
              </ol>
            </section>
          ) : null}

          <section className={styles.thresholdLedger} aria-labelledby="threshold-title">
            <div className={styles.sectionHeading}>
              <div><span className={styles.kicker}>Gate evidence</span><h2 id="threshold-title">阈值检查</h2></div>
            </div>
            {record.thresholdChecks.length === 0 ? (
              <div className={styles.naPanel}>
                <strong>未定义发布阈值</strong>
                <span>E9 retrieval baseline 是 informational，不产生 pass/fail 发布结论。</span>
              </div>
            ) : (
              <ul className={styles.thresholdList}>
                {record.thresholdChecks.map((check) => (
                  <li key={check.metric} data-state={check.passed ? "passed" : "failed"}>
                    <strong>{check.metric}</strong>
                    <span>observed {percent(check.observed)} / minimum {percent(check.minimum)}</span>
                    <b>{check.passed ? "通过" : "阻断"}</b>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section aria-labelledby="case-results-title">
            <div className={styles.sectionHeading}>
              <div><span className={styles.kicker}>Case ledger</span><h2 id="case-results-title">逐题结果</h2></div>
              <span className={styles.count}>{record.caseResults.length} 条可追溯记录</span>
            </div>
            <ol className={styles.evaluationCaseList}>
              {record.caseResults.map((item) => {
                const replayUnavailable = item.replay.availability !== "available";
                return (
                  <li key={item.caseId} data-state={item.failureCategory === "none" ? "passed" : "failed"}>
                    <div className={styles.caseOutcome}>
                      <span>{item.hitAt5 ? "TOP 5" : item.hitAt10 ? "TOP 10" : "MISS"}</span>
                      <code>{item.firstRelevantRank ?? "N/A"}</code>
                    </div>
                    <div className={styles.caseBody}>
                      <div className={styles.caseTitle}>
                        <strong>{item.topic ?? item.caseId}</strong>
                        <code>{item.failureCategory}</code>
                      </div>
                      <p>{item.question ?? "该合成 Gate case 没有自然语言查询。"}</p>
                      <div className={styles.caseEvidence}>
                        <span>Expected: {item.expectedEvidenceIds.join(", ") || "N/A"}</span>
                        <span>Retrieved: {item.retrievedEvidenceIds.join(", ") || "none"}</span>
                      </div>
                      <div className={styles.caseReplay}>
                        <button
                          type="button"
                          disabled={replayUnavailable}
                          onClick={() => onReplay(item.replay)}
                        >
                          重放此问题
                        </button>
                        {item.replay.availability === "candidate_scope_required" ? (
                          <small>需要 release-candidate Query Lab scope</small>
                        ) : item.replay.availability === "query_unavailable" ? (
                          <small>该记录没有可重放查询</small>
                        ) : null}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>
        </div>
      ) : null}
    </section>
  );
}
