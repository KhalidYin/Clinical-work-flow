import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getJson, getRawJson, postJson } from "../api/client";
import { LoadingSkeleton } from "../components/LoadingSkeleton";
import { StatePanel } from "../components/StatePanel";
import {
  API_PATHS,
  releaseManifestPath,
  releasePublishPath,
  type PublishedRelease,
  type ReleasedManifest,
  type ReleaseDiff,
  type ReleasePublishRequest,
  type ReleaseWorkbench,
} from "../contracts/knowledgeApi";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import styles from "./pages.module.css";


interface ReleasesPageProps {
  candidateId: string;
  releaseId: string;
  onCandidateChange: (candidateId: string) => void;
  onReleaseChange: (releaseId: string) => void;
}

const diffRows: Array<{
  key: keyof ReleaseDiff;
  count: keyof ReleaseDiff;
  label: string;
}> = [
  { key: "includedRevisionIds", count: "includedCount", label: "Included" },
  { key: "carriedRevisionIds", count: "carriedCount", label: "Carried" },
  { key: "replacedRevisionIds", count: "replacedCount", label: "Replaced" },
  { key: "addedRevisionIds", count: "addedCount", label: "Added" },
  { key: "retiredRevisionIds", count: "retiredCount", label: "Retired" },
];

function workbenchPath(candidateId: string): string {
  const params = new URLSearchParams();
  if (candidateId) params.set("candidate_id", candidateId);
  const query = params.toString();
  return query ? `${API_PATHS.releaseWorkbench}?${query}` : API_PATHS.releaseWorkbench;
}

export function ReleasesPage({
  candidateId,
  releaseId,
  onCandidateChange,
  onReleaseChange,
}: ReleasesPageProps) {
  useDocumentTitle("版本发布");
  const queryClient = useQueryClient();
  const workbench = useQuery({
    queryKey: ["release-workbench", candidateId],
    queryFn: ({ signal }) => getJson<ReleaseWorkbench>(workbenchPath(candidateId), signal),
    staleTime: 15_000,
  });
  const record = workbench.data?.data;
  const candidate = record?.candidate;
  const historicalRelease = useQuery({
    queryKey: ["released-manifest", releaseId],
    queryFn: ({ signal }) =>
      getRawJson<ReleasedManifest>(releaseManifestPath(releaseId), signal),
    enabled: Boolean(releaseId),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const publish = useMutation({
    mutationFn: () => {
      if (!candidate) throw new Error("没有可发布的候选版本。");
      return postJson<PublishedRelease, ReleasePublishRequest>(
        releasePublishPath(candidate.releaseId),
        { baseReleaseId: candidate.baseReleaseId },
      );
    },
    onSettled: async () => {
      await queryClient.invalidateQueries({ queryKey: ["release-workbench"] });
      await queryClient.invalidateQueries({ queryKey: ["current-release"] });
    },
  });

  useEffect(() => {
    if (!candidateId && candidate) onCandidateChange(candidate.releaseId);
  }, [candidate, candidateId, onCandidateChange]);

  const canPublish = record?.allowedActions.includes("publish") ?? false;
  return (
    <section className={styles.page} aria-labelledby="releases-title">
      <header className={styles.pageHeader}>
        <div>
          <p className={styles.eyebrow}>P17-UI-06 / Immutable publication</p>
          <h1 className={styles.title} id="releases-title">版本发布</h1>
          <p className={styles.lede}>
            候选、差异、Gate 与允许动作均由服务端给出；浏览器只提交候选和 base Release。
          </p>
        </div>
        <div className={styles.headerAside}>
          <span className={styles.asideLabel}>发布语义</span>
          <span className={styles.asideValue}>新 Release + 原子 current 切换</span>
        </div>
      </header>

      {workbench.isPending ? <LoadingSkeleton rows={5} cols={4} /> : null}
      {workbench.isError ? (
        <StatePanel symbol="!" title="无法读取 Release 权威状态" text="数据库、对象或 current pointer 暂不可用；页面不会用 manifest fixture 补值。" error />
      ) : null}
      {workbench.isSuccess && !candidate ? (
        <StatePanel symbol="∅" title="没有待发布候选" text="Release Worker 尚未生成 candidate；历史 Release 保持可寻址。" />
      ) : null}

      {record && candidate ? (
        <div className={styles.releaseWorkbench}>
          <section className={styles.releasePair} aria-label="Current 与 Candidate">
            <article>
              <span className={styles.kicker}>Current</span>
              <strong>{record.current?.version ?? "尚无 Release"}</strong>
              <code>{record.current?.releaseId ?? "N/A"}</code>
              <small>{record.current?.itemCount ?? 0} revisions</small>
            </article>
            <span aria-hidden="true">→</span>
            <article>
              <span className={styles.kicker}>Candidate</span>
              <strong>{candidate.version}</strong>
              <code>{candidate.releaseId}</code>
              <small>base {candidate.baseReleaseId ?? "initial"}</small>
            </article>
          </section>

          {record.diff ? (
            <section aria-labelledby="release-diff-title">
              <div className={styles.sectionHeading}>
                <div><span className={styles.kicker}>Server diff</span><h2 id="release-diff-title">发布差异</h2></div>
              </div>
              <div className={styles.releaseDiffGrid}>
                {diffRows.map((row) => {
                  const ids = record.diff?.[row.key] as string[];
                  const count = record.diff?.[row.count] as number;
                  return (
                    <article key={row.label}>
                      <span>{row.label}</span><strong>{count}</strong>
                      <div>{ids.length ? ids.map((id) => <code key={id}>{id}</code>) : <small>none</small>}</div>
                    </article>
                  );
                })}
              </div>
            </section>
          ) : (
            <p className={styles.partialNotice}>Release 对象或 base manifest 不完整，服务端未返回差异。</p>
          )}

          <section aria-labelledby="release-gates-title">
            <div className={styles.sectionHeading}>
              <div><span className={styles.kicker}>Publication evidence</span><h2 id="release-gates-title">发布 Gate</h2></div>
            </div>
            <ul className={styles.releaseGateList}>
              {record.gates.map((gate) => (
                <li key={gate.code} data-state={gate.passed ? "passed" : "failed"}>
                  <strong>{gate.code}</strong><code>{gate.reason}</code><b>{gate.passed ? "通过" : "阻断"}</b>
                </li>
              ))}
            </ul>
          </section>

          {record.blockers.length ? (
            <div className={styles.releaseBlockers} role="status">
              <strong>发布已阻断</strong>
              {record.blockers.map((blocker) => <code key={blocker}>{blocker}</code>)}
            </div>
          ) : null}
          {publish.isError ? (
            <p className={styles.releaseMutationError} role="alert">{publish.error.message}</p>
          ) : null}
          {publish.isSuccess ? (
            <p className={styles.releaseMutationSuccess} role="status">
              已发布 {publish.data.data.releaseId}；正在刷新 current pointer。
            </p>
          ) : null}
          <div className={styles.releaseActions}>
            <button
              type="button"
              disabled={!canPublish || publish.isPending}
              onClick={() => publish.mutate()}
            >
              {publish.isPending ? "发布中…" : "发布候选版本"}
            </button>
            {!canPublish ? <small>服务端未授予 publish：请检查 Gate、角色与 base Release。</small> : null}
          </div>

        </div>
      ) : null}

      {record ? (
        <section aria-labelledby="release-history-title">
          <div className={styles.sectionHeading}>
            <div><span className={styles.kicker}>Immutable history</span><h2 id="release-history-title">历史版本</h2></div>
          </div>
          {record.history.length ? (
            <ol className={styles.releaseHistory}>
              {record.history.map((item) => (
                <li key={item.releaseId} data-selected={item.releaseId === releaseId}>
                  <strong>{item.version}</strong>
                  <code>{item.releaseId}</code>
                  <span>{item.itemCount} revisions</span>
                  <button type="button" onClick={() => onReleaseChange(item.releaseId)}>
                    {item.releaseId === releaseId ? "正在查看" : "打开历史 Release"}
                  </button>
                </li>
              ))}
            </ol>
          ) : <p className={styles.emptyInline}>尚无历史 Release。</p>}
        </section>
      ) : null}

      {releaseId ? (
        <section aria-labelledby="release-detail-title" className={styles.releaseDetail}>
          <div className={styles.sectionHeading}>
            <div><span className={styles.kicker}>Hash-verified snapshot</span><h2 id="release-detail-title">历史 Release 详情</h2></div>
          </div>
          {historicalRelease.isPending ? <LoadingSkeleton rows={3} cols={3} /> : null}
          {historicalRelease.isError ? (
            <StatePanel symbol="!" title="无法打开历史 Release" text="该 Release 不存在、未发布或 immutable manifest 完整性校验失败。" error />
          ) : null}
          {historicalRelease.data ? (
            <div className={styles.releaseSnapshot}>
              <dl>
                <div><dt>Release</dt><dd><code>{historicalRelease.data.releaseId}</code></dd></div>
                <div><dt>版本</dt><dd>{historicalRelease.data.version}</dd></div>
                <div><dt>Base Release</dt><dd><code>{historicalRelease.data.manifest.baseReleaseId ?? "initial"}</code></dd></div>
                <div><dt>Manifest SHA-256</dt><dd><code>{historicalRelease.data.manifestSha256}</code></dd></div>
                <div><dt>Chunk Profile</dt><dd><code>{historicalRelease.data.manifest.chunkProfileId}@{historicalRelease.data.manifest.chunkProfileVersion}</code></dd></div>
                <div><dt>Index object</dt><dd><code>{historicalRelease.data.manifest.indexDescriptor.objectKey}</code></dd></div>
              </dl>
              <ol className={styles.releaseManifestItems} aria-label="Release immutable membership">
                {historicalRelease.data.manifest.items.map((item) => (
                  <li key={item.knowledgeRevisionId}>
                    <div><strong>{item.knowledgeRevisionId}</strong><span>{item.disposition}</span></div>
                    <p>Evidence {item.evidenceIds.map((id) => <code key={id}>{id}</code>)}</p>
                    <p>Chunks {item.chunkIds.map((id) => <code key={id}>{id}</code>)}</p>
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
