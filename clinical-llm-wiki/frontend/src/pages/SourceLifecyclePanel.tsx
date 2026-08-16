import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getJson, postJson } from "../api/client";
import {
  impactAssessmentPath,
  sourceHistoryPath,
  sourceImpactAssessmentsPath,
  type EvidenceChangeType,
  type ImpactAssessment,
  type ImpactMaterializationRequest,
  type SourceHistory,
} from "../contracts/knowledgeApi";
import styles from "./pages.module.css";

const changeLabels: Record<EvidenceChangeType, string> = {
  unchanged: "未变化",
  moved: "位置变化",
  modified: "内容修改",
  added: "新增",
  removed: "移除",
  rights_changed: "权利变化",
  ambiguous: "待澄清",
};

const changeOrder = Object.keys(changeLabels) as EvidenceChangeType[];

export interface SourceLifecycleSearch {
  source: string;
  from: string;
  to: string;
  assessment: string;
  change: string;
}

interface SourceLifecyclePanelProps {
  search: SourceLifecycleSearch;
  onSearchChange: (patch: Partial<SourceLifecycleSearch>) => void;
}

export function SourceLifecyclePanel({
  search,
  onSearchChange,
}: SourceLifecyclePanelProps) {
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const history = useQuery({
    queryKey: ["source-history", search.source],
    queryFn: ({ signal }) =>
      getJson<SourceHistory>(sourceHistoryPath(search.source), signal),
    enabled: Boolean(search.source),
    staleTime: 30_000,
  });
  const versions = history.data?.data.versions ?? [];
  const fromVersionId = versions.some(
    (version) => version.sourceVersionId === search.from,
  )
    ? search.from
    : (versions[1]?.sourceVersionId ?? "");
  const toVersionId = versions.some(
    (version) => version.sourceVersionId === search.to,
  )
    ? search.to
    : (versions[0]?.sourceVersionId ?? "");
  const selectedSummary =
    history.data?.data.comparisons.find(
      (comparison) => comparison.assessmentId === search.assessment,
    ) ?? history.data?.data.comparisons[0];
  const selectedAssessmentId = selectedSummary?.assessmentId ?? "";
  const assessment = useQuery({
    queryKey: ["impact-assessment", selectedAssessmentId],
    queryFn: ({ signal }) =>
      getJson<ImpactAssessment>(impactAssessmentPath(selectedAssessmentId), signal),
    enabled: Boolean(selectedAssessmentId),
    staleTime: 30_000,
  });
  const filteredImpacts = useMemo(() => {
    const impacts = assessment.data?.data.impacts ?? [];
    return search.change
      ? impacts.filter((impact) => impact.changeType === search.change)
      : impacts;
  }, [assessment.data?.data.impacts, search.change]);

  const materialization = useMutation({
    mutationFn: (request: ImpactMaterializationRequest) =>
      postJson<ImpactAssessment, ImpactMaterializationRequest>(
        sourceImpactAssessmentsPath(search.source),
        request,
      ),
    onSuccess: async (response) => {
      setNotice("比较已完成；结果来自服务端固定 Profile。");
      onSearchChange({
        assessment: response.data.assessmentId,
        change: "",
      });
      await queryClient.invalidateQueries({
        queryKey: ["source-history", search.source],
      });
    },
  });

  if (!search.source) {
    return (
      <div className={styles.panel}>
        <div className={styles.statePanel}>
          <div>
            <span className={styles.stateSymbol} aria-hidden="true">↕</span>
            <h2 className={styles.stateTitle}>版本与影响</h2>
            <p className={styles.stateText}>从来源列表选择一项，查看其完整版本历史与服务端比较结果。</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <section className={styles.adminSection} aria-labelledby="source-lifecycle-title">
      <div className={styles.sectionHeading}>
        <div>
          <p className={styles.eyebrow}>SourceVersion / ImpactAssessment</p>
          <h2 id="source-lifecycle-title">版本与影响</h2>
        </div>
        <span className={styles.mono}>{search.source}</span>
      </div>

      {history.isPending ? <p className={styles.notice}>正在读取版本历史…</p> : null}
      {history.isError ? (
        <p className={styles.formError} role="alert">无法读取服务端版本历史；不会从文件名推断版本。</p>
      ) : null}
      {history.data?.data.partial ? (
        <p className={styles.notice} role="status">
          {history.data.data.warnings.join("；") || "版本历史为部分数据。"}
        </p>
      ) : null}

      {history.isSuccess && versions.length < 2 ? (
        <p className={styles.notice}>至少需要同一 Source 的两个 canonical SourceVersion 才能比较。</p>
      ) : null}

      {history.isSuccess && versions.length >= 2 ? (
        <div className={styles.reviewGrid}>
          <div className={styles.evidenceColumn}>
            <div className={styles.columnHeader}>
              <div>
                <span className={styles.columnIndex}>01 / versions</span>
                <h2>选择比较版本</h2>
              </div>
              <span className={styles.panelMeta}>Profile 由服务端固定</span>
            </div>
            <div className={styles.columnBody}>
              <label>
                <span className={styles.asideLabel}>比较基线</span>
                <select
                  value={fromVersionId}
                  onChange={(event) => onSearchChange({ from: event.target.value })}
                >
                  {versions.map((version) => (
                    <option key={version.sourceVersionId} value={version.sourceVersionId}>
                      {version.version} · {version.sourceVersionId}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span className={styles.asideLabel}>目标版本</span>
                <select
                  value={toVersionId}
                  onChange={(event) => onSearchChange({ to: event.target.value })}
                >
                  {versions.map((version) => (
                    <option key={version.sourceVersionId} value={version.sourceVersionId}>
                      {version.version} · {version.sourceVersionId}
                    </option>
                  ))}
                </select>
              </label>
              {history.data.data.allowedActions.includes("compare") ? (
                <button
                  className={styles.primaryButton}
                  type="button"
                  disabled={
                    materialization.isPending ||
                    !fromVersionId ||
                    !toVersionId ||
                    fromVersionId === toVersionId
                  }
                  onClick={() => {
                    setNotice(null);
                    materialization.mutate({
                      fromSourceVersionId: fromVersionId,
                      toSourceVersionId: toVersionId,
                    });
                  }}
                >
                  {materialization.isPending ? "正在比较…" : "启动版本比较"}
                </button>
              ) : (
                <p className={styles.notice}>当前角色仅可查看比较结果。</p>
              )}
              {materialization.isError ? (
                <p className={styles.formError} role="alert">比较失败；服务端未产生部分计数或轮转状态。</p>
              ) : null}
              {notice ? <p className={styles.receipt} role="status">{notice}</p> : null}
            </div>
          </div>

          <div className={styles.governanceColumn}>
            <div className={styles.columnHeader}>
              <div>
                <span className={styles.columnIndex}>02 / impact</span>
                <h2>比较结果</h2>
              </div>
              <span className={styles.panelMeta}>{selectedSummary?.comparisonProfileVersion ?? "尚无比较"}</span>
            </div>
            <div className={styles.columnBody}>
              {!selectedSummary ? <p className={styles.notice}>尚无已完成比较。</p> : null}
              {selectedSummary ? (
                <>
                  <label>
                    <span className={styles.asideLabel}>已完成比较</span>
                    <select
                      value={selectedAssessmentId}
                      onChange={(event) => {
                        const next = history.data.data.comparisons.find(
                          (item) => item.assessmentId === event.target.value,
                        );
                        onSearchChange({
                          assessment: event.target.value,
                          from: next?.fromSourceVersionId ?? fromVersionId,
                          to: next?.toSourceVersionId ?? toVersionId,
                          change: "",
                        });
                      }}
                    >
                      {history.data.data.comparisons.map((comparison) => (
                        <option key={comparison.assessmentId} value={comparison.assessmentId}>
                          {comparison.fromSourceVersionId} → {comparison.toSourceVersionId}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className={styles.buttonRow}>
                    <span className={styles.receipt}>受影响知识 {selectedSummary.impactSummary.affectedKnowledgeCount}</span>
                    <span className={styles.receipt}>RotationCase {selectedSummary.impactSummary.rotationCaseCount}</span>
                  </div>
                  <div className={styles.buttonRow} aria-label="变化分类计数">
                    {changeOrder.map((change) => (
                      <button
                        className={styles.secondaryButton}
                        type="button"
                        key={change}
                        onClick={() => onSearchChange({
                          assessment: selectedSummary.assessmentId,
                          change,
                        })}
                      >
                        {changeLabels[change]} {selectedSummary.changeCounts[change]}
                      </button>
                    ))}
                  </div>
                  {assessment.isPending ? <p className={styles.notice}>正在读取受影响项…</p> : null}
                  {assessment.isError ? <p className={styles.formError}>无法读取受影响项详情。</p> : null}
                  {assessment.isSuccess && filteredImpacts.length === 0 ? (
                    <p className={styles.notice}>该分类没有受影响 Evidence。</p>
                  ) : null}
                  {filteredImpacts.map((impact) => (
                    <article className={styles.evidencePaper} key={impact.evidenceImpactId}>
                      <span className={styles.evidenceId}>{changeLabels[impact.changeType]} · {impact.mappingBasis}</span>
                      <p className={styles.mono}>
                        {impact.fromEvidenceId ?? "∅"} → {impact.toEvidenceId ?? "∅"}
                      </p>
                      <span className={styles.secondary}>{JSON.stringify(impact.details)}</span>
                    </article>
                  ))}
                </>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
