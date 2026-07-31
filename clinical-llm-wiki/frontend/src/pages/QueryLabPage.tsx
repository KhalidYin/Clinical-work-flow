import { useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";

import { ApiRequestError, postJson } from "../api/client";
import {
  API_PATHS,
  type ExplicitGap,
  type RetrievalChannelCapability,
  type RetrievalHit,
  type RetrievalQuery,
  type RetrievalQueryRequest,
  type RetrievalVisibility,
} from "../contracts/knowledgeApi";
import styles from "./pages.module.css";

export interface QueryLabSearch {
  q: string;
  visibility: RetrievalVisibility;
  type: string;
  domain: string;
  depth: number;
  vector: boolean;
}

interface QueryLabPageProps {
  search: QueryLabSearch;
  onSearchChange: (patch: Partial<QueryLabSearch>) => void;
}

const channels = ["metadata", "fts", "vector", "relation"] as const;

export function QueryLabPage({ search, onSearchChange }: QueryLabPageProps) {
  const [draft, setDraft] = useState(search.q);
  useEffect(() => setDraft(search.q), [search.q]);

  const request: RetrievalQueryRequest = {
    query: search.q,
    visibility: search.visibility,
    filters: {
      knowledgeTypes: search.type ? [search.type] : [],
      scope: search.domain ? { domain: search.domain } : {},
      sourceVersionIds: [],
      rightsClassifications: [],
    },
    limit: 10,
    relationDepth: search.depth,
    includeVector: search.vector,
  };
  const result = useQuery({
    queryKey: [
      "knowledge-query",
      search.q,
      search.visibility,
      search.type,
      search.domain,
      search.depth,
      search.vector,
    ],
    queryFn: () => postJson<RetrievalQuery, RetrievalQueryRequest>(API_PATHS.queries, request),
    enabled: Boolean(search.q.trim()),
    retry: false,
  });

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSearchChange({ q: draft.trim() });
  };
  const data = result.data?.data;
  const hasNarrowFilters = Boolean(search.type || search.domain);

  return (
    <section className={styles.page} aria-labelledby="query-lab-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>KUI-06 / governed retrieval observatory</p>
          <h1 className={styles.title} id="query-lab-title">
            Query Lab
          </h1>
          <p className={styles.lede}>
            检查后端实际召回、融合与引用。页面只呈现服务端 rank，不在浏览器中重算分数。
          </p>
        </div>
        <div className={styles.headerAside}>
          <span className={styles.asideLabel}>Production boundary</span>
          <span className={styles.asideValue}>
            {search.visibility === "released" ? "current Release only" : "approved sandbox"}
          </span>
        </div>
      </header>

      <form className={styles.queryForm} onSubmit={submit}>
        <label className={styles.queryPrompt}>
          <span>Knowledge question or exact identifier</span>
          <div>
            <input
              type="search"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="例如：AESEQ 的定义和适用范围"
              aria-label="Knowledge query"
            />
            <button type="submit" disabled={!draft.trim() || result.isFetching}>
              {result.isFetching ? "Querying…" : "Run query"}
            </button>
          </div>
        </label>

        <div className={styles.queryControlGrid}>
          <fieldset>
            <legend>Visibility</legend>
            <div className={styles.segmented}>
              {(["released", "evaluation"] as const).map((visibility) => (
                <button
                  key={visibility}
                  type="button"
                  aria-pressed={search.visibility === visibility}
                  onClick={() => onSearchChange({ visibility })}
                >
                  {visibility}
                </button>
              ))}
            </div>
          </fieldset>
          <label>
            <span>Knowledge type</span>
            <input
              value={search.type}
              onChange={(event) => onSearchChange({ type: event.target.value })}
              placeholder="clinical_rule"
            />
          </label>
          <label>
            <span>Domain</span>
            <input
              value={search.domain}
              onChange={(event) =>
                onSearchChange({ domain: event.target.value.toUpperCase() })
              }
              placeholder="AE"
            />
          </label>
          <label>
            <span>Relation depth</span>
            <select
              value={search.depth}
              onChange={(event) =>
                onSearchChange({ depth: Number(event.target.value) })
              }
            >
              <option value={0}>0 · off</option>
              <option value={1}>1 hop</option>
              <option value={2}>2 hops</option>
            </select>
          </label>
          <label className={styles.queryCheck}>
            <input
              type="checkbox"
              checked={search.vector}
              onChange={(event) => onSearchChange({ vector: event.target.checked })}
            />
            <span>Request vector channel</span>
          </label>
        </div>
      </form>

      {!search.q ? <DefaultQueryState /> : null}
      {result.isPending && search.q ? <QueryLoading /> : null}
      {result.isError ? <QueryError error={result.error} /> : null}
      {data ? (
        <>
          <CapabilityRail capabilities={data.plan.channels} />
          {data.partial ? (
            <div className={styles.queryPartial} role="status">
              <strong>Partial capability</strong>
              <span>
                至少一个检索通道不可用或被明确禁用；现有结果仍保留其后端排名和引用。
              </span>
            </div>
          ) : null}
          <div className={styles.queryWorkspace}>
            <main className={styles.queryResults} aria-live="polite">
              <div className={styles.querySectionHeader}>
                <div>
                  <span className={styles.asideLabel}>Ranked result</span>
                  <h2>{data.hits.length} governed hit{data.hits.length === 1 ? "" : "s"}</h2>
                </div>
                <span className={styles.scopeMeta}>{data.plan.visibility}</span>
              </div>
              {data.hits.length === 0 ? (
                <EmptyQueryState gaps={data.gaps} narrowed={hasNarrowFilters} />
              ) : (
                data.hits.map((hit) => <ResultCard key={hit.knowledgeRevisionId} hit={hit} />)
              )}
            </main>
            <aside className={styles.queryInspector} aria-label="Query plan and explicit gaps">
              <QueryPlanPanel data={data} />
            </aside>
          </div>
        </>
      ) : null}
    </section>
  );
}

function DefaultQueryState() {
  return (
    <div className={styles.queryDefault}>
      <span className={styles.stateSymbol} aria-hidden="true">
        ⌁
      </span>
      <h2 className={styles.stateTitle}>Start with a claim, concept or identifier</h2>
      <p className={styles.stateText}>
        生产模式只查询当前不可变 Release。切换 evaluation 需要后端授予
        <code> evaluation:run </code>权限。
      </p>
    </div>
  );
}

function QueryLoading() {
  return (
    <div className={styles.queryLoading} aria-label="正在执行知识检索" aria-busy="true">
      {channels.map((channel) => (
        <span className={styles.skeleton} key={channel} />
      ))}
    </div>
  );
}

function QueryError({ error }: { error: Error }) {
  const detail =
    error instanceof ApiRequestError && error.status === 403
      ? "当前身份无权进入所选 visibility。evaluation 不会回退为 production 查询。"
      : "Knowledge API 未返回可验证结果；页面不会使用本地假数据补齐。";
  return (
    <div className={`${styles.queryDefault} ${styles.error}`} role="alert">
      <h2 className={styles.stateTitle}>Query failed</h2>
      <p className={styles.stateText}>{detail}</p>
    </div>
  );
}

function CapabilityRail({
  capabilities,
}: {
  capabilities: RetrievalChannelCapability[];
}) {
  const byChannel = new Map(capabilities.map((item) => [item.channel, item]));
  return (
    <section className={styles.capabilityRail} aria-label="Retrieval channel capability">
      {channels.map((channel) => {
        const capability = byChannel.get(channel);
        return (
          <article key={channel} data-state={capability?.state ?? "unavailable"}>
            <header>
              <span>{channel}</span>
              <strong>{capability?.state ?? "unavailable"}</strong>
            </header>
            <b>{capability?.candidateCount ?? 0}</b>
            <small>
              {capability?.version ??
                capability?.reason ??
                "No capability fact returned"}
            </small>
          </article>
        );
      })}
    </section>
  );
}

function ResultCard({ hit }: { hit: RetrievalHit }) {
  return (
    <article className={styles.queryResultCard}>
      <header>
        <span className={styles.queryRank}>#{hit.rank}</span>
        <div>
          <span className={styles.asideLabel}>{hit.knowledgeType}</span>
          <h3>{hit.stableKey}</h3>
        </div>
        <span className={styles.queryScore}>{hit.finalScore.toFixed(6)}</span>
      </header>
      <p className={styles.queryClaim}>{hit.claim}</p>
      <div className={styles.queryContributions}>
        {hit.channelContributions.map((contribution) => (
          <span key={contribution.channel}>
            {contribution.channel} · rank {contribution.rank} · raw{" "}
            {contribution.rawScore.toFixed(4)} · fused{" "}
            {contribution.fusionScore.toFixed(6)}
          </span>
        ))}
      </div>
      {hit.relationPaths.length ? (
        <div className={styles.queryPaths}>
          {hit.relationPaths.map((path, index) => (
            <code key={`${hit.knowledgeRevisionId}-path-${index}`}>
              {path.join(" → ")}
            </code>
          ))}
        </div>
      ) : null}
      <details className={styles.queryEvidence}>
        <summary>{hit.citations.length} canonical citation(s)</summary>
        {hit.citations.map((citation) => (
          <div key={citation.evidenceId}>
            <strong>{citation.sourceTitle}</strong>
            <span>
              {citation.sourceVersion} · {citation.sourceVersionId}
            </span>
            <code>{JSON.stringify(citation.locator)}</code>
            <small>
              Evidence {citation.evidenceId} · sha256:
              {citation.contentSha256.slice(0, 12)}
            </small>
          </div>
        ))}
      </details>
    </article>
  );
}

function EmptyQueryState({
  gaps,
  narrowed,
}: {
  gaps: ExplicitGap[];
  narrowed: boolean;
}) {
  return (
    <div className={styles.queryEmpty}>
      <h3>{narrowed ? "Filters may be too narrow" : "No governed match"}</h3>
      <p>
        {narrowed
          ? "清除 Knowledge type 或 Domain 后重试；系统不会跨 visibility 扩大结果。"
          : "当前 visibility 中没有匹配知识。请检查 explicit gap，而不是把空结果解释为肯定答案。"}
      </p>
      {gaps.map((gap) => (
        <code key={gap.code}>{gap.code}</code>
      ))}
    </div>
  );
}

function QueryPlanPanel({ data }: { data: RetrievalQuery }) {
  return (
    <>
      <section className={styles.queryPlan}>
        <span className={styles.asideLabel}>Backend query plan</span>
        <dl>
          <div>
            <dt>Query ID</dt>
            <dd>{data.plan.queryId}</dd>
          </div>
          <div>
            <dt>Fusion policy</dt>
            <dd>{data.plan.policyVersion}</dd>
          </div>
          <div>
            <dt>Index</dt>
            <dd>{data.plan.indexVersion ?? "not available"}</dd>
          </div>
          <div>
            <dt>Release</dt>
            <dd>{data.plan.releaseScope?.version ?? "evaluation direct"}</dd>
          </div>
          <div>
            <dt>Relation ceiling</dt>
            <dd>{data.plan.relationDepth} hop(s)</dd>
          </div>
        </dl>
      </section>
      <section className={styles.queryGaps}>
        <span className={styles.asideLabel}>Explicit gaps</span>
        {data.gaps.length === 0 ? (
          <p>No explicit gaps reported.</p>
        ) : (
          data.gaps.map((gap) => (
            <article key={`${gap.code}-${gap.channel ?? "all"}`}>
              <strong>{gap.code}</strong>
              <span>{gap.message}</span>
              <small>
                {gap.kind} · {gap.channel ?? "all channels"}
              </small>
            </article>
          ))
        )}
      </section>
    </>
  );
}
