import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ArtifactPreview } from "./ArtifactPreview";
import { getPocState, getStudies, resumePocRun, startPocRun } from "./api";
import { ReviewDecisionForm } from "./ReviewDecisionForm";
import type {
  ActionId,
  PocBlocker,
  PocNextAction,
  PocState,
  PocStep,
  PocStepCheck,
  StudySummary,
} from "./types";

type LoadState = "idle" | "loading" | "ready" | "error";
type WorkspaceView = "task" | "input" | "review" | "artifact";

const DEFAULT_STUDY_ID = "SAMPLE-AE-001";

export function App() {
  const [studies, setStudies] = useState<StudySummary[]>([]);
  const [studyId, setStudyId] = useState(DEFAULT_STUDY_ID);
  const [pocState, setPocState] = useState<PocState | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(() => hashSelection().stepId);
  const [workspaceView, setWorkspaceView] = useState<WorkspaceView>(() => hashSelection().view);
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [message, setMessage] = useState("");

  const load = useCallback(
    async (options?: { preserveMessage?: boolean; followActive?: boolean }) => {
      setLoadState("loading");
      if (!options?.preserveMessage) {
        setMessage("");
      }
      try {
        const studiesPayload = await getStudies();
        const nextStudies = studiesPayload.studies;
        setStudies(nextStudies);
        const resolvedStudyId =
          nextStudies.find((study) => study.study_id === studyId)?.study_id ??
          nextStudies.find((study) => study.study_id === DEFAULT_STUDY_ID)?.study_id ??
          nextStudies[0]?.study_id ??
          studyId;
        setStudyId(resolvedStudyId);
        if (!resolvedStudyId) {
          setPocState(null);
          setSelectedArtifactId(null);
          setLoadState("ready");
          return;
        }
        const state = await getPocState(resolvedStudyId);
        setPocState(state);
        const activeStepId = state.active_step?.step_id ?? state.steps[0]?.step_id ?? null;
        setSelectedStepId((current) => {
          const stillExists = current && state.steps.some((step) => step.step_id === current);
          return options?.followActive || !stillExists ? activeStepId : current;
        });
        if (options?.followActive) {
          const active = state.steps.find((step) => step.step_id === activeStepId);
          setSelectedArtifactId(active?.artifact_refs[0]?.artifact_id ?? null);
          if (state.blocker?.review_id && state.next_actions.some((action) => action.action_id === "open_review" && action.enabled)) {
            setWorkspaceView("review");
          } else {
            setWorkspaceView("task");
          }
        }
        setLoadState("ready");
      } catch (error) {
        setLoadState("error");
        setMessage(error instanceof Error ? error.message : String(error));
      }
    },
    [studyId],
  );

  useEffect(() => {
    void load({ followActive: true });
  }, [load]);

  useEffect(() => {
    if (pocState?.run_state !== "running") {
      return;
    }
    const refreshWhenVisible = () => {
      if (!document.hidden) {
        void load({ preserveMessage: true });
      }
    };
    const timer = window.setInterval(refreshWhenVisible, 5000);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [load, pocState?.run_state]);

  const selectedStep = useMemo(() => {
    if (!pocState) {
      return null;
    }
    return (
      pocState.steps.find((step) => step.step_id === selectedStepId) ??
      pocState.steps.find((step) => step.step_id === pocState.active_step?.step_id) ??
      pocState.steps[0] ??
      null
    );
  }, [pocState, selectedStepId]);

  const reviewId = pocState?.blocker?.review_id ?? pocState?.active_step?.review_id ?? null;

  useEffect(() => {
    if (!selectedStep) {
      return;
    }
    writeHashSelection(selectedStep.step_id, workspaceView);
  }, [selectedStep, workspaceView]);

  async function handleAction(actionId: ActionId) {
    const action = pocState?.next_actions.find((item) => item.action_id === actionId);
    if (actionId === "open_review" && action?.enabled) {
      setWorkspaceView("review");
      return;
    }
    if (actionId === "refresh") {
      await load({ preserveMessage: true });
      return;
    }
    if (!studyId || !action?.enabled) {
      return;
    }
    setLoadState("loading");
    try {
      const response =
        actionId === "run_poc"
          ? await startPocRun(studyId)
          : await resumePocRun(
              studyId,
              pocState?.run_id ?? "",
              actionId === "retry_current_step" ? "retry_after_failure" : "review_decision_available",
              reviewId,
            );
      setMessage(`${action.label}: ${response.run_state} · ${response.message}`);
      await load({ preserveMessage: true, followActive: true });
    } catch (error) {
      setLoadState("error");
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  function selectStep(stepId: string) {
    setSelectedStepId(stepId);
    const step = pocState?.steps.find((item) => item.step_id === stepId);
    setSelectedArtifactId(step?.artifact_refs[0]?.artifact_id ?? null);
    setWorkspaceView("task");
  }

  return (
    <main className="workbench-shell" aria-label="SDTM AE POC Workbench">
      <StudyHeader
        loadState={loadState}
        pocState={pocState}
        studies={studies}
        studyId={studyId}
        onStudyChange={setStudyId}
      />

      <CompactRunBar
        loadState={loadState}
        message={message}
        pocState={pocState}
        onAction={(actionId) => void handleAction(actionId)}
      />

      <StageRail
        selectedStepId={selectedStep?.step_id ?? null}
        steps={pocState?.steps ?? []}
        onSelectStep={selectStep}
      />

      <MainWorkspace
        loadState={loadState}
        pocState={pocState}
        reviewId={reviewId}
        selectedArtifactId={selectedArtifactId}
        selectedStep={selectedStep}
        studyId={studyId}
        view={workspaceView}
        onDecisionSubmitted={(nextMessage) => {
          setMessage(nextMessage);
          void load({ preserveMessage: true, followActive: true });
        }}
        onSelectArtifact={setSelectedArtifactId}
        onViewChange={setWorkspaceView}
      />

      <ActivityDrawer
        events={pocState?.events ?? []}
        health={pocState?.health ?? []}
        runId={pocState?.run_id ?? null}
        stepId={selectedStep?.step_id ?? null}
      />
    </main>
  );
}

function StudyHeader({
  loadState,
  pocState,
  studies,
  studyId,
  onStudyChange,
}: {
  loadState: LoadState;
  pocState: PocState | null;
  studies: StudySummary[];
  studyId: string;
  onStudyChange: (studyId: string) => void;
}) {
  return (
    <header className="study-header" data-testid="study-header">
      <div className="study-title">
        <p className="eyebrow">P9.1 · 单机测试用 Workbench</p>
        <h1>{studyId || "未选择 Study"}</h1>
        <p className="subtle">SDTM AE Minimal POC · 当前 Wiki 仅限 p9-poc-test-only</p>
      </div>
      <div className="header-controls">
        <label>
          Study
          <select value={studyId} onChange={(event) => onStudyChange(event.target.value)}>
            {studies.length ? (
              studies.map((study) => (
                <option key={study.study_id} value={study.study_id}>
                  {study.study_id}
                </option>
              ))
            ) : (
              <option value={studyId}>{studyId || "n/a"}</option>
            )}
          </select>
        </label>
        <StatusPill value={loadState === "loading" ? "loading" : pocState?.run_state ?? "n/a"} />
      </div>
      <dl className="header-facts">
        <Fact label="target" value={pocState?.target_artifact ?? "sdtm_ae_dataset"} />
        <Fact label="source" value={valueText(pocState?.source.format)} />
        <Fact label="source hash" value={shortHash(pocState?.source.sha256)} mono />
        <Fact label="knowledge" value={valueText(pocState?.knowledge.scope)} />
      </dl>
    </header>
  );
}

function CompactRunBar({
  loadState,
  message,
  pocState,
  onAction,
}: {
  loadState: LoadState;
  message: string;
  pocState: PocState | null;
  onAction: (actionId: ActionId) => void;
}) {
  const actions = (pocState?.next_actions ?? []).filter((action) =>
    ["run_poc", "retry_current_step", "open_review", "resume", "refresh"].includes(action.action_id),
  );
  const input = pocState?.input_check.summary;
  return (
    <section className="run-bar" aria-labelledby="run-bar-title">
      <h2 id="run-bar-title" className="sr-only">POC run controls</h2>
      <div className="run-fact">
        <span>Input readiness</span>
        <strong>{input ? `${input.required_ready}/${input.required_total}` : "—"}</strong>
        <StatusPill value={input?.status ?? "not_run"} />
      </div>
      <div className="run-fact">
        <span>Current state</span>
        <strong>{pocState?.run_state ?? "loading"}</strong>
        <small className="mono">{pocState?.run_id ?? "run: n/a"}</small>
      </div>
      <div className="run-fact run-fact-blocker">
        <span>Blocker</span>
        <strong>{pocState?.blocker ? `${pocState.blocker.kind} · ${pocState.blocker.code}` : "none"}</strong>
        <small>{pocState?.blocker?.summary ?? input?.message ?? "等待状态。"}</small>
      </div>
      <div className="run-actions" aria-label="Available POC actions">
        {actions.map((action) => (
          <ActionButton
            key={action.action_id}
            action={action}
            disabled={loadState === "loading"}
            onClick={() => onAction(action.action_id)}
          />
        ))}
      </div>
      <div className={`run-message ${loadState === "error" ? "run-message-error" : ""}`} role="status">
        {message || (loadState === "loading" ? "正在读取 POC 状态…" : "状态已同步。")}
      </div>
    </section>
  );
}

function ActionButton({
  action,
  disabled,
  onClick,
}: {
  action: PocNextAction;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={`button ${action.primary ? "button-primary" : "button-ghost"}`}
      disabled={disabled || !action.enabled}
      title={!action.enabled ? action.reason ?? undefined : undefined}
      type="button"
      onClick={onClick}
    >
      {action.label}
    </button>
  );
}

function StageRail({
  selectedStepId,
  steps,
  onSelectStep,
}: {
  selectedStepId: string | null;
  steps: PocStep[];
  onSelectStep: (stepId: string) => void;
}) {
  const railRef = useRef<HTMLOListElement>(null);
  useEffect(() => {
    const selected = railRef.current?.querySelector<HTMLElement>("[aria-current='step']");
    selected?.scrollIntoView?.({ behavior: "smooth", block: "nearest", inline: "center" });
  }, [selectedStepId]);
  return (
    <nav className="stage-rail-panel" aria-label="POC stages">
      {steps.length ? (
        <ol ref={railRef} className="stage-rail">
          {steps.map((step) => (
            <li key={step.step_id}>
              <button
                aria-current={step.step_id === selectedStepId ? "step" : undefined}
                className={`stage-node state-${step.state}`}
                type="button"
                onClick={() => onSelectStep(step.step_id)}
              >
                <span className="stage-index">{step.ordinal}</span>
                <span className="stage-copy">
                  <strong>{step.title}</strong>
                  <small>{step.state}</small>
                </span>
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <div className="empty-state">Runner ledger 尚未生成。</div>
      )}
    </nav>
  );
}

function MainWorkspace({
  loadState,
  pocState,
  reviewId,
  selectedArtifactId,
  selectedStep,
  studyId,
  view,
  onDecisionSubmitted,
  onSelectArtifact,
  onViewChange,
}: {
  loadState: LoadState;
  pocState: PocState | null;
  reviewId: string | null;
  selectedArtifactId: string | null;
  selectedStep: PocStep | null;
  studyId: string;
  view: WorkspaceView;
  onDecisionSubmitted: (message: string) => void;
  onSelectArtifact: (artifactId: string) => void;
  onViewChange: (view: WorkspaceView) => void;
}) {
  const refs = selectedStep?.artifact_refs ?? [];
  const tabs: Array<{ id: WorkspaceView; label: string; disabled?: boolean }> = [
    { id: "task", label: "当前任务" },
    { id: "input", label: "输入与证据" },
    { id: "review", label: "人工审核", disabled: !reviewId },
    { id: "artifact", label: "产物预览", disabled: !refs.length },
  ];
  return (
    <section className="main-workspace" aria-labelledby="workspace-title">
      <div className="workspace-heading">
        <div>
          <p className="eyebrow">UI-04 · Main Workspace</p>
          <h2 id="workspace-title">{selectedStep?.title ?? "当前无可执行任务"}</h2>
        </div>
        {selectedStep ? <StatusPill value={selectedStep.state} /> : null}
      </div>

      {pocState?.blocker ? <BlockerBanner blocker={pocState.blocker} /> : null}
      {loadState === "error" ? <div className="notice notice-error">API 状态读取失败，当前内容可能已过期。</div> : null}
      {pocState?.partial_errors.length ? (
        <div className="notice notice-warn">部分证据读取失败：{pocState.partial_errors.length} 项。</div>
      ) : null}

      <div className="workspace-tabs" role="tablist" aria-label="Main workspace views">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            aria-selected={view === tab.id}
            className="workspace-tab"
            disabled={tab.disabled}
            role="tab"
            type="button"
            onClick={() => onViewChange(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="workspace-body" role="tabpanel">
        {view === "task" ? <TaskView step={selectedStep} activeStep={pocState?.active_step ?? null} /> : null}
        {view === "input" ? (
          <InputEvidence step={selectedStep} inputCheck={pocState?.input_check ?? null} />
        ) : null}
        {view === "review" && reviewId ? (
          <ReviewDecisionForm reviewId={reviewId} studyId={studyId} onSubmitted={onDecisionSubmitted} />
        ) : null}
        {view === "review" && !reviewId ? <div className="empty-state">当前阶段没有 ReviewPacket。</div> : null}
        {view === "artifact" ? (
          <ArtifactWorkspace
            refs={refs}
            selectedArtifactId={selectedArtifactId}
            studyId={studyId}
            onSelectArtifact={onSelectArtifact}
          />
        ) : null}
      </div>
    </section>
  );
}

function BlockerBanner({
  blocker,
}: {
  blocker: PocBlocker;
}) {
  return (
    <aside className={`blocker-banner blocker-${blocker.kind}`} aria-label="Active blocker">
      <div className="blocker-title">
        <span className="blocker-kicker">{blocker.kind} blocker</span>
        <h3>{blocker.summary}</h3>
        <p>{blocker.detail}</p>
      </div>
      <dl className="blocker-facts">
        <Fact label="stage" value={blocker.stage_id} />
        <Fact label="check" value={blocker.code} mono />
        <Fact label="variables" value={blocker.affected_variables.join(", ") || "none"} />
        <Fact label="recovery" value={blocker.recovery_action} />
      </dl>
      {blocker.evidence_refs.length ? (
        <div className="evidence-strip">
          <strong>Evidence</strong>
          {blocker.evidence_refs.map((ref) => <code key={ref}>{ref}</code>)}
        </div>
      ) : null}
    </aside>
  );
}

function TaskView({
  step,
  activeStep,
}: {
  step: PocStep | null;
  activeStep: PocState["active_step"];
}) {
  if (!step) {
    return <div className="empty-state">当前没有 active task；可先运行 Input Check。</div>;
  }
  return (
    <div className="task-view">
      <div className="task-summary">
        <p className="eyebrow">{step.step_id}</p>
        <h3>{step.summary || "该阶段尚无摘要。"}</h3>
        {activeStep?.step_id === step.step_id && activeStep.next_instruction ? <p>{activeStep.next_instruction}</p> : null}
        <dl className="task-times">
          <Fact label="started" value={step.started_at ?? "n/a"} />
          <Fact label="completed" value={step.completed_at ?? "n/a"} />
        </dl>
      </div>
      <CheckList checks={step.checks} />
    </div>
  );
}

function CheckList({ checks }: { checks: PocStepCheck[] }) {
  if (!checks.length) {
    return <div className="empty-state">该阶段尚无 deterministic check。</div>;
  }
  return (
    <ol className="check-list">
      {checks.map((check) => (
        <li key={`${check.check_id}-${check.summary}`}>
          <StatusPill value={check.state} />
          <div>
            <strong>{check.summary}</strong>
            {check.detail ? <p>{check.detail}</p> : null}
            {check.affected_variables.length ? <small>影响：{check.affected_variables.join(", ")}</small> : null}
          </div>
          <code>{check.check_id}</code>
        </li>
      ))}
    </ol>
  );
}

function InputEvidence({
  step,
  inputCheck,
}: {
  step: PocStep | null;
  inputCheck: PocState["input_check"] | null;
}) {
  if (!step) {
    return <div className="empty-state">请选择一个阶段查看输入与证据。</div>;
  }
  if (step.step_id !== "input-check") {
    return <StageEvidence step={step} />;
  }
  if (!inputCheck) {
    return <div className="empty-state">Input Check 尚未生成。</div>;
  }
  return (
    <div className="input-evidence">
      <div className="input-summary">
        <div>
          <p className="eyebrow">Target-scoped readiness</p>
          <h3>{inputCheck.summary.message}</h3>
        </div>
        <StatusPill value={inputCheck.summary.status} />
      </div>
      <section>
        <h3>文件与 parser</h3>
        {inputCheck.files.length ? (
          <div className="table-scroll">
            <table className="evidence-table">
              <thead><tr><th>来源</th><th>格式</th><th>Rows × Cols</th><th>标签</th><th>格式</th><th>值标签</th><th>Parser</th></tr></thead>
              <tbody>
                {inputCheck.files.map((file) => (
                  <tr key={file.source_id}>
                    <td><strong>{file.label}</strong><small>{file.relative_path}</small></td>
                    <td>{file.format}</td>
                    <td>{valueText(file.row_count)} × {valueText(file.column_count)}</td>
                    <td><BooleanStatus value={file.labels_available} /></td>
                    <td><BooleanStatus value={file.formats_available} /></td>
                    <td><BooleanStatus value={file.value_labels_available} /></td>
                    <td><BooleanStatus value={file.parser_available} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <div className="empty-state">未登记 source file。</div>}
      </section>
      <section>
        <h3>目标依赖</h3>
        <div className="dependency-grid">
          {inputCheck.dependencies.map((dependency) => (
            <article key={dependency.input_id} className={dependency.blocking ? "dependency-blocking" : ""}>
              <span>{dependency.requirement}</span>
              <strong>{dependency.label}</strong>
              <StatusPill value={dependency.status} />
              <small>{dependency.detail}</small>
            </article>
          ))}
        </div>
      </section>
      <section>
        <h3>关键变量 profile</h3>
        {inputCheck.variable_profiles.length ? (
          <div className="profile-grid">
            {inputCheck.variable_profiles.map((profile) => (
              <article key={profile.variable}>
                <code>{profile.variable}</code>
                <strong>{profile.label ?? "无标签"}</strong>
                <dl>
                  <Fact label="type" value={profile.data_type ?? "n/a"} />
                  <Fact label="format" value={profile.format ?? "n/a"} />
                  <Fact label="missing" value={valueText(profile.missing_count)} />
                  <Fact label="distinct" value={valueText(profile.distinct_count)} />
                </dl>
              </article>
            ))}
          </div>
        ) : <div className="empty-state">关键变量 profile 尚不可用。</div>}
      </section>
      <StageBoundary step={step} />
    </div>
  );
}

const REVIEW_BOUNDARIES: Record<string, { mode: string; content: string }> = {
  "input-check": {
    mode: "通常不审核",
    content: "文件、hash、parser 与 metadata 可用性由确定性检查负责；只有来源授权或版本范围有争议时进入人工处理。",
  },
  "minimum-information": {
    mode: "条件触发",
    content: "只审核目标、身份来源或条件依赖的业务歧义；缺少 required input 不能通过人工批准绕过。",
  },
  "wiki-context": {
    mode: "条件触发",
    content: "已批准且锁定的测试知识自动加载；规则冲突、locator 断链或适用范围不明确时才暂停审核。",
  },
  "mapping-spec": {
    mode: "必须审核",
    content: "审核 Source→Target、受控 operation、Wiki rule refs、显式 gap 和本次 POC 范围；不审核原始数据是否无缺陷。",
  },
  "program-execution": {
    mode: "执行后审核",
    content: "程序生成与注册 adapter 执行是机器动作；其程序、日志、draft、验证和追溯进入下一阶段审核。",
  },
  "validation-review": {
    mode: "必须审核",
    content: "人工决定 program promotion 和 deferred finding；strong-blocking finding 必须修复并重验，不能靠批准覆盖。",
  },
  "canonical-ae": {
    mode: "不新增审核",
    content: "已有 DecisionReceipt 后按 hash 机械晋升；Canonical 阶段只确认产物和最终 traceability。",
  },
};

function StageEvidence({ step }: { step: PocStep }) {
  const checkEvidence = step.checks.flatMap((check) => check.evidence_refs);
  const evidenceRefs = Array.from(new Set([...step.evidence_refs, ...checkEvidence]));
  return (
    <div className="stage-evidence">
      <section>
        <p className="eyebrow">Selected-stage boundary</p>
        <h3>{step.title} 的输入与决策证据</h3>
        <p className="help-text">这里不重复展示全局数据 profile；原始数据详情只属于 Input Check。</p>
      </section>
      <ReferenceSection title="本阶段输入" refs={step.input_refs} empty="该阶段尚未登记输入引用。" />
      <ReferenceSection title="决策与检查证据" refs={evidenceRefs} empty="该阶段尚未登记决策证据。" />
      <section>
        <h3>本阶段产物</h3>
        {step.artifact_refs.length ? (
          <div className="reference-grid">
            {step.artifact_refs.map((ref) => (
              <article key={ref.artifact_id}>
                <span>{ref.kind}</span>
                <strong>{ref.label}</strong>
                <code>{ref.relative_path}</code>
              </article>
            ))}
          </div>
        ) : <div className="empty-state">该阶段尚未产生受控产物。</div>}
      </section>
      <StageBoundary step={step} />
    </div>
  );
}

function ReferenceSection({
  title,
  refs,
  empty,
}: {
  title: string;
  refs: string[];
  empty: string;
}) {
  return (
    <section>
      <h3>{title}</h3>
      {refs.length ? (
        <div className="reference-grid">
          {refs.map((ref) => <code key={ref}>{ref}</code>)}
        </div>
      ) : <div className="empty-state">{empty}</div>}
    </section>
  );
}

function StageBoundary({ step }: { step: PocStep }) {
  const boundary = REVIEW_BOUNDARIES[step.step_id] ?? {
    mode: "未定义",
    content: "该阶段尚未声明人工审核边界。",
  };
  return (
    <section className="review-boundary">
      <div>
        <p className="eyebrow">Human-loop boundary</p>
        <h3>{boundary.mode}</h3>
      </div>
      <p>{boundary.content}</p>
    </section>
  );
}

function ArtifactWorkspace({
  refs,
  selectedArtifactId,
  studyId,
  onSelectArtifact,
}: {
  refs: PocStep["artifact_refs"];
  selectedArtifactId: string | null;
  studyId: string;
  onSelectArtifact: (artifactId: string) => void;
}) {
  return (
    <div className="artifact-workspace">
      <ArtifactRefs refs={refs} selectedArtifactId={selectedArtifactId} onSelectArtifact={onSelectArtifact} />
      <ArtifactPreview artifactId={selectedArtifactId} studyId={studyId} />
    </div>
  );
}

function ActivityDrawer({
  events,
  health,
  runId,
  stepId,
}: {
  events: PocState["events"];
  health: PocState["health"];
  runId: string | null;
  stepId: string | null;
}) {
  const filtered = events.filter(
    (event) => (!runId || !event.run_id || event.run_id === runId) && (!stepId || event.step_id === stepId),
  );
  return (
    <details className="activity-drawer">
      <summary>
        <span><strong>Activity / Evidence</strong><small>当前 run · {stepId ?? "all stages"}</small></span>
        <span className="status-pill status-muted">{filtered.length} event</span>
      </summary>
      <div className="activity-content">
        <section>
          <h3>Health</h3>
          {health.length ? <ul className="compact-list">{health.map((item) => <li key={item.check_id}><StatusPill value={item.severity} /><span>{item.summary}</span></li>)}</ul> : <p className="empty-state">暂无 health 信息。</p>}
        </section>
        <section>
          <h3>Events</h3>
          {filtered.length ? (
            <ol className="compact-list">
              {filtered.slice().reverse().map((event) => (
                <li key={event.event_id}><code>{event.event_type}</code><span>{event.summary}</span><small>{event.occurred_at}</small></li>
              ))}
            </ol>
          ) : <p className="empty-state">当前 run/step 暂无 event。</p>}
        </section>
      </div>
    </details>
  );
}

function ArtifactRefs({
  onSelectArtifact,
  refs,
  selectedArtifactId,
}: {
  onSelectArtifact: (artifactId: string) => void;
  refs: PocStep["artifact_refs"];
  selectedArtifactId: string | null;
}) {
  if (!refs.length) {
    return <p className="empty-state">当前步骤无 artifact ref。</p>;
  }
  return (
    <ul className="artifact-ref-list">
      {refs.map((ref) => (
        <li key={ref.artifact_id}>
          <button aria-pressed={ref.artifact_id === selectedArtifactId} className="artifact-ref-button" disabled={!ref.preview_available} type="button" onClick={() => onSelectArtifact(ref.artifact_id)}>{ref.label}</button>
          <span className="mono">{shortHash(ref.sha256)}</span>
        </li>
      ))}
    </ul>
  );
}

function Fact({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div><dt>{label}</dt><dd className={mono ? "mono" : undefined}>{value}</dd></div>;
}

function BooleanStatus({ value }: { value?: boolean | null }) {
  return <span className={value === true ? "bool-yes" : value === false ? "bool-no" : "bool-na"}>{value === true ? "yes" : value === false ? "no" : "n/a"}</span>;
}

function StatusPill({ value }: { value: string }) {
  return <span className={`status-pill ${statusClass(value)}`}>{value}</span>;
}

function statusClass(value: string) {
  if (["done", "ok", "pass", "ready", "available"].includes(value)) return "status-ok";
  if (["running", "warning", "loading", "partial", "not_run", "gap"].includes(value)) return "status-warn";
  if (["blocked", "error", "failed", "fail", "invalid", "missing"].includes(value)) return "status-danger";
  return "status-muted";
}

function shortHash(value: unknown) {
  const text = valueText(value);
  return text === "n/a" ? text : `${text.slice(0, 10)}…`;
}

function valueText(value: unknown) {
  if (value === undefined || value === null || value === "") return "n/a";
  return String(value);
}

function hashSelection(): { stepId: string | null; view: WorkspaceView } {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const view = params.get("view");
  return {
    stepId: params.get("step"),
    view: view === "input" || view === "review" || view === "artifact" ? view : "task",
  };
}

function writeHashSelection(stepId: string, view: WorkspaceView) {
  const next = `#step=${encodeURIComponent(stepId)}&view=${view}`;
  if (window.location.hash !== next) window.history.replaceState(null, "", next);
}
