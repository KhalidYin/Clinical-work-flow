import { useQuery } from "@tanstack/react-query";

import { getJson } from "../api/client";
import {
  API_PATHS,
  type RelationEdge,
  type RelationNode,
  type RelationQuery,
} from "../contracts/knowledgeApi";
import styles from "./pages.module.css";

export interface RelationsSearch {
  q: string;
  node: string;
  depth: number;
  view: "paths" | "list";
}

interface RelationsPageProps {
  search: RelationsSearch;
  onSearchChange: (patch: Partial<RelationsSearch>) => void;
}

function relationPath(params: Record<string, string>): string {
  const query = new URLSearchParams(params);
  return `${API_PATHS.relationQuery}?${query.toString()}`;
}

function nodeLabel(node: RelationNode | undefined, fallback: string): string {
  return node?.stableKey ?? fallback;
}

export function RelationsPage({ search, onSearchChange }: RelationsPageProps) {
  const directory = useQuery({
    queryKey: ["relation-directory", search.q],
    queryFn: ({ signal }) =>
      getJson<RelationQuery>(
        relationPath({ q: search.q, depth: "0" }),
        signal,
      ),
    staleTime: 30_000,
  });
  const graph = useQuery({
    queryKey: ["relation-graph", search.node, search.depth],
    queryFn: ({ signal }) =>
      getJson<RelationQuery>(
        relationPath({
          node_id: search.node,
          depth: String(search.depth),
        }),
        signal,
      ),
    enabled: Boolean(search.node),
    staleTime: 30_000,
  });

  const directoryNodes = directory.data?.data.nodes ?? [];
  const graphData = graph.data?.data;
  const graphNodes = new Map(
    (graphData?.nodes ?? []).map((node) => [node.knowledgeUnitId, node]),
  );

  return (
    <section className={styles.page} aria-labelledby="relations-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>KUI-05 / evidence-bound topology</p>
          <h1 className={styles.title} id="relations-title">
            Relations
          </h1>
          <p className={styles.lede}>
            按方向浏览 typed relation。没有 Evidence 的边不会进入此视图；候选、批准和
            release membership 保持可区分。
          </p>
        </div>
        <div className={styles.headerAside}>
          <span className={styles.asideLabel}>Expansion ceiling</span>
          <span className={styles.asideValue}>2 hops · read only</span>
        </div>
      </header>

      <div className={styles.relationWorkbench}>
        <aside className={styles.relationDirectory} aria-label="Knowledge unit directory">
          <div className={styles.directoryHeader}>
            <label>
              <span className={styles.asideLabel}>Find knowledge unit</span>
              <input
                className={styles.search}
                type="search"
                value={search.q}
                placeholder="stable key、type 或 claim"
                onChange={(event) =>
                  onSearchChange({ q: event.target.value })
                }
              />
            </label>
            <span className={styles.count}>
              {directory.isPending
                ? "loading"
                : `${directoryNodes.length} / ${directory.data?.data.totalNodes ?? 0}`}
            </span>
          </div>

          {directory.isError ? (
            <CompactState
              title="无法读取关系目录"
              text="Knowledge API 没有返回可验证的知识节点。"
              error
            />
          ) : null}
          {directory.isSuccess && directoryNodes.length === 0 ? (
            <CompactState
              title="没有匹配节点"
              text="清除筛选条件，或使用 stable key 搜索。"
            />
          ) : null}
          <div className={styles.nodePickerList}>
            {directoryNodes.map((node) => (
              <button
                className={`${styles.nodePicker} ${
                  search.node === node.knowledgeUnitId ? styles.nodePickerSelected : ""
                }`}
                type="button"
                key={node.knowledgeUnitId}
                onClick={() =>
                  onSearchChange({ node: node.knowledgeUnitId })
                }
              >
                <span className={styles.nodePickerTop}>
                  <strong>{node.stableKey}</strong>
                  <span className={styles.status}>{node.status}</span>
                </span>
                <span>{node.knowledgeType}</span>
                <small>{node.claim ?? "No approved claim"}</small>
              </button>
            ))}
          </div>
        </aside>

        <div className={styles.relationStage}>
          <div className={styles.relationToolbar}>
            <div>
              <span className={styles.asideLabel}>Bounded expansion</span>
              <div className={styles.segmented} aria-label="Relation depth">
                {[1, 2].map((depth) => (
                  <button
                    key={depth}
                    type="button"
                    aria-pressed={search.depth === depth}
                    onClick={() => onSearchChange({ depth })}
                  >
                    {depth} hop
                  </button>
                ))}
              </div>
            </div>
            <div>
              <span className={styles.asideLabel}>View</span>
              <div className={styles.segmented} aria-label="Relation view">
                {(["paths", "list"] as const).map((view) => (
                  <button
                    key={view}
                    type="button"
                    aria-pressed={search.view === view}
                    onClick={() => onSearchChange({ view })}
                  >
                    {view}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {!search.node ? (
            <div className={styles.detailState}>
              <span className={styles.stateSymbol} aria-hidden="true">
                ↗
              </span>
              <h2 className={styles.stateTitle}>选择一个知识节点</h2>
              <p className={styles.stateText}>
                选择后只展开一至两跳，并逐条展示边的原始 Evidence。
              </p>
            </div>
          ) : null}
          {graph.isPending ? <RelationSkeleton /> : null}
          {graph.isError ? (
            <div className={styles.detailState}>
              <h2 className={styles.stateTitle}>关系查询失败</h2>
              <p className={styles.stateText}>
                页面不会从候选文本推断缺失关系，也不会隐藏权限错误。
              </p>
            </div>
          ) : null}
          {graphData?.partial ? (
            <div className={styles.notice} role="status">
              <span aria-hidden="true">△</span>
              <span>{graphData.warnings.join("；") || "关系结果为部分数据。"}</span>
            </div>
          ) : null}
          {graphData && graphData.edges.length === 0 ? (
            <div className={styles.detailState}>
              <h2 className={styles.stateTitle}>没有带 Evidence 的相邻关系</h2>
              <p className={styles.stateText}>
                节点存在，但当前深度内没有可验证的 typed edge。
              </p>
            </div>
          ) : null}
          {graphData && graphData.edges.length > 0 ? (
            search.view === "paths" ? (
              <div className={styles.pathList}>
                {graphData.edges.map((edge) => (
                  <RelationPath
                    key={edge.relationId}
                    edge={edge}
                    source={graphNodes.get(edge.sourceKnowledgeUnitId)}
                    target={graphNodes.get(edge.targetKnowledgeUnitId)}
                  />
                ))}
              </div>
            ) : (
              <RelationTable
                edges={graphData.edges}
                nodes={graphNodes}
              />
            )
          ) : null}
        </div>
      </div>
    </section>
  );
}

function RelationPath({
  edge,
  source,
  target,
}: {
  edge: RelationEdge;
  source?: RelationNode;
  target?: RelationNode;
}) {
  return (
    <article className={styles.pathCard}>
      <div className={styles.pathDiagram}>
        <NodeCard node={source} fallback={edge.sourceKnowledgeUnitId} />
        <div className={styles.edgeMark}>
          <span>{edge.relationType}</span>
          <strong aria-hidden="true">→</strong>
          <small>{edge.status}</small>
        </div>
        <NodeCard node={target} fallback={edge.targetKnowledgeUnitId} />
      </div>
      <div className={styles.edgeEvidence}>
        <span className={styles.sectionLabel}>
          Edge evidence <b>{edge.evidence.length}</b>
        </span>
        {edge.evidence.map((evidence) => (
          <blockquote key={evidence.evidenceId}>
            <p>{evidence.content}</p>
            <footer>
              <span>{evidence.sourceVersionId}</span>
              <span>{JSON.stringify(evidence.locator)}</span>
              <span title={evidence.contentSha256}>
                sha256:{evidence.contentSha256.slice(0, 12)}
              </span>
            </footer>
          </blockquote>
        ))}
      </div>
    </article>
  );
}

function NodeCard({
  node,
  fallback,
}: {
  node: RelationNode | undefined;
  fallback: string;
}) {
  return (
    <div className={styles.graphNode}>
      <span className={styles.asideLabel}>{node?.knowledgeType ?? "unknown node"}</span>
      <strong>{nodeLabel(node, fallback)}</strong>
      <span className={styles.status}>{node?.status ?? "unversioned"}</span>
      {node?.releaseIds.length ? (
        <small>release · {node.releaseIds.join(", ")}</small>
      ) : (
        <small>not in a release</small>
      )}
    </div>
  );
}

function RelationTable({
  edges,
  nodes,
}: {
  edges: RelationEdge[];
  nodes: Map<string, RelationNode>;
}) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Source</th>
            <th>Direction</th>
            <th>Target</th>
            <th>Status</th>
            <th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {edges.map((edge) => (
            <tr key={edge.relationId}>
              <td>{nodeLabel(nodes.get(edge.sourceKnowledgeUnitId), edge.sourceKnowledgeUnitId)}</td>
              <td className={styles.mono}>{edge.relationType} →</td>
              <td>{nodeLabel(nodes.get(edge.targetKnowledgeUnitId), edge.targetKnowledgeUnitId)}</td>
              <td><span className={styles.status}>{edge.status}</span></td>
              <td className={styles.mono}>{edge.evidence.length} verified</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CompactState({
  title,
  text,
  error = false,
}: {
  title: string;
  text: string;
  error?: boolean;
}) {
  return (
    <div className={`${styles.compactState} ${error ? styles.error : ""}`}>
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}

function RelationSkeleton() {
  return (
    <div className={styles.pathList} aria-label="Loading relation evidence">
      {[0, 1].map((item) => (
        <div className={styles.pathCard} key={item}>
          <span className={styles.skeleton} />
          <span className={styles.skeleton} />
          <span className={styles.skeleton} />
        </div>
      ))}
    </div>
  );
}
