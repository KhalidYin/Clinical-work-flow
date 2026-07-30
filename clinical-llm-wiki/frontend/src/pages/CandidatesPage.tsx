import { useQuery } from "@tanstack/react-query";

import { getJson } from "../api/client";
import {
  API_PATHS,
  type CandidateCollection,
  type CandidateSummary,
} from "../contracts/knowledgeApi";
import styles from "./pages.module.css";

export function CandidatesPage() {
  const candidates = useQuery({
    queryKey: ["candidates"],
    queryFn: ({ signal }) =>
      getJson<CandidateCollection>(API_PATHS.candidates, signal),
  });
  const items = candidates.data?.data.items ?? [];

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
        <div className={styles.candidateGrid}>
          {items.map((candidate) => (
            <CandidateCard candidate={candidate} key={candidate.candidateId} />
          ))}
        </div>
      ) : null}
    </section>
  );
}

function CandidateCard({ candidate }: { candidate: CandidateSummary }) {
  const gate =
    candidate.status === "author_confirmation_required"
      ? "待作者确认"
      : candidate.reviewStatus === "review_required"
        ? "待独立审核"
        : candidate.reviewStatus ?? candidate.status;

  return (
    <article className={styles.candidateCard}>
      <header className={styles.runHeader}>
        <div>
          <span className={styles.secondary}>
            {candidate.candidateId} · revision {candidate.revisionNumber}
          </span>
          <h2 className={styles.candidateClaim}>{candidate.claim}</h2>
        </div>
        <span className={styles.status}>{gate}</span>
      </header>
      <dl className={styles.candidateFacts}>
        <div>
          <dt>Evidence</dt>
          <dd>{candidate.evidenceCount}</dd>
        </div>
        <div>
          <dt>Relation proposals</dt>
          <dd>{candidate.relationProposalCount}</dd>
        </div>
        <div>
          <dt>Type</dt>
          <dd>{candidate.knowledgeType}</dd>
        </div>
      </dl>
      <code className={styles.checkpoint}>
        sha256:{candidate.contentSha256.slice(0, 16)} · {candidate.runId}
      </code>
    </article>
  );
}
