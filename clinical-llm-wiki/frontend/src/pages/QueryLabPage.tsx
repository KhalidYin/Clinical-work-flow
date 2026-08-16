import { FormEvent, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { postJson } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { StatePanel } from "../components/StatePanel";
import {
  API_PATHS,
  type ReleasedQueryLabRequest,
  type ReleasedQueryLabResult,
  type RetrievalCapability,
  type RetrievalCitation,
} from "../contracts/knowledgeApi";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import styles from "./pages.module.css";

export interface QueryLabSearch {
  q: string;
  release: string;
  top_k: number;
}

interface QueryLabPageProps {
  search: QueryLabSearch;
  onSearchChange: (next: QueryLabSearch) => void;
}

const capabilityRows = [
  ["metadata", "元数据"],
  ["fullText", "全文检索"],
  ["vector", "向量检索"],
  ["relation", "关系扩展"],
  ["generation", "生成模型"],
] as const;

function capabilityLabel(capability: RetrievalCapability): string {
  if (capability.status === "available") return "可用";
  if (capability.status === "degraded") return "降级";
  return "禁用";
}

function locatorLabel(locator: Record<string, unknown>): string {
  if (typeof locator.page === "number") return `第 ${locator.page} 页`;
  if (typeof locator.section === "string") return `章节 ${locator.section}`;
  return JSON.stringify(locator);
}

function citationKey(citation: RetrievalCitation): string {
  return `${citation.evidenceId}:${citation.startOffset}:${citation.endOffset}`;
}

export function QueryLabPage({ search, onSearchChange }: QueryLabPageProps) {
  useDocumentTitle("检索实验室");
  const [draftQuery, setDraftQuery] = useState(search.q);
  const [draftRelease, setDraftRelease] = useState(search.release);
  const [draftTopK, setDraftTopK] = useState(search.top_k);

  useEffect(() => setDraftQuery(search.q), [search.q]);
  useEffect(() => setDraftRelease(search.release), [search.release]);
  useEffect(() => setDraftTopK(search.top_k), [search.top_k]);

  const retrieval = useQuery({
    queryKey: ["immutable-release-query", search.q, search.release, search.top_k],
    queryFn: () =>
      postJson<ReleasedQueryLabResult, ReleasedQueryLabRequest>(
        API_PATHS.releasedQuery,
        {
          query: search.q,
          topK: search.top_k,
          releaseId: search.release || null,
        },
      ),
    enabled: Boolean(search.q.trim()),
    staleTime: 30_000,
  });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const q = draftQuery.trim();
    if (!q) return;
    const next = {
      q,
      release: draftRelease.trim(),
      top_k: Math.min(50, Math.max(1, draftTopK)),
    };
    if (
      next.q === search.q &&
      next.release === search.release &&
      next.top_k === search.top_k
    ) {
      void retrieval.refetch();
      return;
    }
    onSearchChange(next);
  };

  const result = retrieval.data?.data;

  return (
    <section className={styles.page} aria-labelledby="query-lab-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>P17-UI-04 / Immutable Release</p>
          <h1 className={styles.title} id="query-lab-title">检索实验室</h1>
          <p className={styles.lede}>
            只查询 current 或指定历史 Release 中冻结的 Chunk。排序、分路贡献与引用均由
            Knowledge API 返回，浏览器不重算。
          </p>
        </div>
        <div className={styles.headerAside}>
          <span className={styles.asideLabel}>执行边界</span>
          <span className={styles.asideValue}>只读 · 零模型调用</span>
        </div>
      </header>

      <form className={styles.queryForm} onSubmit={submit}>
        <label className={styles.queryField}>
          <span className={styles.asideLabel}>查询已发布知识</span>
          <input
            type="search"
            value={draftQuery}
            placeholder="例如：randomisation 如何降低 selection bias"
            onChange={(event) => setDraftQuery(event.target.value)}
          />
        </label>
        <label>
          <span className={styles.asideLabel}>Release ID（留空使用 current）</span>
          <input
            value={draftRelease}
            placeholder="current"
            onChange={(event) => setDraftRelease(event.target.value)}
          />
        </label>
        <label>
          <span className={styles.asideLabel}>返回数量</span>
          <select
            value={draftTopK}
            onChange={(event) => setDraftTopK(Number(event.target.value))}
          >
            {[5, 10, 20, 50].map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <button className={styles.primaryButton} type="submit" disabled={!draftQuery.trim()}>
          查询 immutable Release
        </button>
      </form>

      {!search.q ? (
        <StatePanel
          symbol="⌕"
          title="等待查询"
          text="输入问题后才会调用检索 API；空查询不会自动运行。"
        />
      ) : null}
      {retrieval.isPending && search.q ? <LoadingSkeleton rows={4} cols={4} /> : null}
      {retrieval.isError ? (
        <StatePanel
          symbol="!"
          title="无法查询 immutable Release"
          text="Release 不存在、完整性验证失败或检索服务暂不可用。权威状态未被前端覆盖。"
          error
        />
      ) : null}

      {result ? (
        <div className={styles.queryResults}>
          <section className={styles.queryReceipt} aria-label="检索回执">
            <div>
              <span className={styles.asideLabel}>已解析 Release</span>
              <strong>{result.releaseVersion}</strong>
              <code>{result.releaseId}</code>
            </div>
            <div>
              <span className={styles.asideLabel}>查询身份</span>
              <strong>{result.hits.length} 个命中</strong>
              <code>{result.queryId}</code>
            </div>
            <div>
              <span className={styles.asideLabel}>调用证据</span>
              <strong>零外部模型请求</strong>
              <code>externalModelRequests = {result.externalModelRequests}</code>
            </div>
          </section>

          <section className={styles.capabilityGrid} aria-label="检索能力">
            {capabilityRows.map(([key, label]) => {
              const capability = result.capabilities[key];
              return (
                <article key={key} data-state={capability.status}>
                  <span className={styles.asideLabel}>{label}</span>
                  <strong>{capabilityLabel(capability)}</strong>
                  <small>{capability.reason ?? "由已发布索引提供"}</small>
                </article>
              );
            })}
          </section>

          <p className={styles.baselineNotice}>
            单文档检索基线，不是临床质量认证
          </p>

          {result.hits.length === 0 ? (
            <StatePanel
              symbol="∅"
              title="没有已发布命中"
              text="API 在该 Release 的冻结 Chunk 成员中没有返回匹配结果。"
            />
          ) : (
            <ol className={styles.retrievalList}>
              {result.hits.map((hit) => (
                <li key={hit.chunkId} className={styles.retrievalHit}>
                  <div className={styles.hitRank}>
                    <span>第 {hit.rank} 位</span>
                    <code>{hit.fusionScore.toFixed(6)}</code>
                  </div>
                  <div className={styles.hitBody}>
                    <div className={styles.hitSource}>
                      <strong>{hit.explanation.sourceTitle}</strong>
                      <span>{hit.explanation.sourceVersion} · {locatorLabel(hit.explanation.locator)}</span>
                    </div>
                    <p>{hit.content}</p>
                    <div className={styles.routeLedger} aria-label={`第 ${hit.rank} 位分路贡献`}>
                      <span>metadata <b>{hit.routeContributions.metadata}</b></span>
                      <span>full text <b>{hit.routeContributions.fullText}</b></span>
                      <span>vector <b>N/A</b></span>
                      <span>relation <b>N/A</b></span>
                    </div>
                    <details className={styles.hitDetails}>
                      <summary>查看 Evidence 引用与 Chunk 解释</summary>
                      <dl>
                        <div><dt>Chunk</dt><dd>{hit.chunkId}</dd></div>
                        <div><dt>Profile</dt><dd>{hit.explanation.chunkProfileId}</dd></div>
                        <div><dt>Token</dt><dd>{hit.explanation.tokenCount}</dd></div>
                        <div><dt>类型</dt><dd>{hit.explanation.evidenceType}</dd></div>
                      </dl>
                      <ul className={styles.citationList}>
                        {hit.citations.map((citation) => (
                          <li key={citationKey(citation)}>
                            <strong>{citation.evidenceId}</strong>
                            <span>{locatorLabel(citation.locator)} · {citation.spanRole}</span>
                            <code>{citation.sourceVersionId}</code>
                          </li>
                        ))}
                      </ul>
                    </details>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      ) : null}
    </section>
  );
}
