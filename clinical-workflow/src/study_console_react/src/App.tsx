import { useCallback, useEffect, useMemo, useState } from "react";

import { getPocState, getStudies, resumePocRun, startPocRun } from "./api";
import { ReviewDecisionForm } from "./ReviewDecisionForm";
import type { PocNextAction, PocState, PocStep, StudySummary } from "./types";

type LoadState = "idle" | "loading" | "ready" | "error";

const DEFAULT_STUDY_ID = "SAMPLE-AE-001";

export function App() {
  const [studies, setStudies] = useState<StudySummary[]>([]);
  const [studyId, setStudyId] = useState(DEFAULT_STUDY_ID);
  const [pocState, setPocState] = useState<PocState | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [message, setMessage] = useState("");

  const load = useCallback(async (options?: { preserveMessage?: boolean }) => {
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
      if (resolvedStudyId) {
        const state = await getPocState(resolvedStudyId);
        setPocState(state);
        setSelectedStepId((current) => current ?? state.active_step?.step_id ?? state.steps[0]?.step_id);
      } else {
        setPocState(null);
      }
      setLoadState("ready");
    } catch (error) {
      setLoadState("error");
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }, [studyId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!pocState || !["running", "blocked_review"].includes(pocState.run_state)) {
      return;
    }
    const timer = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(timer);
  }, [load, pocState]);

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

  async function handleRunPoc() {
    if (!studyId) {
      return;
    }
    setLoadState("loading");
    try {
      const response = await startPocRun(studyId);
      setMessage(`Run POC: ${response.run_state} · ${response.message}`);
      const state = await getPocState(studyId);
      setPocState(state);
      setSelectedStepId(state.active_step?.step_id ?? state.steps[0]?.step_id ?? null);
      setLoadState("ready");
    } catch (error) {
      setLoadState("error");
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  async function handleResume() {
    if (!studyId || !pocState?.run_id) {
      return;
    }
    setLoadState("loading");
    try {
      const response = await resumePocRun(studyId, pocState.run_id);
      setMessage(`Resume: ${response.run_state} · ${response.message}`);
      const state = await getPocState(studyId);
      setPocState(state);
      setSelectedStepId(state.active_step?.step_id ?? state.steps[0]?.step_id ?? null);
      setLoadState("ready");
    } catch (error) {
      setLoadState("error");
      setMessage(error instanceof Error ? error.message : String(error));
    }
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

      <section className="workbench-grid">
        <RunControl
          loadState={loadState}
          message={message}
          pocState={pocState}
          onRefresh={() => void load()}
          onRunPoc={() => void handleRunPoc()}
          onResume={() => void handleResume()}
        />
        <WorkflowTimeline
          selectedStepId={selectedStep?.step_id ?? null}
          steps={pocState?.steps ?? []}
          onSelectStep={setSelectedStepId}
        />
        <ActiveTaskPanel
          activeStep={pocState?.active_step ?? null}
          selectedStep={selectedStep}
          studyId={studyId}
          onDecisionSubmitted={(nextMessage) => {
            setMessage(nextMessage);
            void load({ preserveMessage: true });
          }}
        />
      </section>

      <EventLog events={pocState?.events ?? []} health={pocState?.health ?? []} />
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
  const sourceHash = valueText(pocState?.source.sha256);
  return (
    <header className="study-header" data-testid="study-header">
      <div>
        <p className="eyebrow">P9.1 · 单机测试用 Workbench</p>
        <h1>{studyId || "未选择 Study"}</h1>
        <p className="subtle">SDTM AE Minimal POC · source/wiki/workflow 状态均来自 API payload</p>
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
        <div>
          <dt>source</dt>
          <dd>{valueText(pocState?.source.format)}</dd>
        </div>
        <div>
          <dt>source hash</dt>
          <dd className="mono">{shortHash(sourceHash)}</dd>
        </div>
        <div>
          <dt>knowledge</dt>
          <dd>{valueText(pocState?.knowledge.scope)}</dd>
        </div>
        <div>
          <dt>blocking</dt>
          <dd>{valueText(pocState?.blocking_reason)}</dd>
        </div>
      </dl>
    </header>
  );
}

function RunControl({
  loadState,
  message,
  pocState,
  onRefresh,
  onRunPoc,
  onResume,
}: {
  loadState: LoadState;
  message: string;
  pocState: PocState | null;
  onRefresh: () => void;
  onRunPoc: () => void;
  onResume: () => void;
}) {
  const actionById = new Map((pocState?.next_actions ?? []).map((action) => [action.action_id, action]));
  const runAction = actionById.get("run_poc");
  const resumeAction = actionById.get("resume");
  return (
    <section className="panel run-control" aria-labelledby="run-control-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">UI-02</p>
          <h2 id="run-control-title">Run Control</h2>
        </div>
        <span className="mono">{pocState?.run_id ?? "run: n/a"}</span>
      </div>
      <div className="button-row">
        <button
          className="button button-primary"
          disabled={loadState === "loading" || !runAction?.enabled}
          type="button"
          onClick={onRunPoc}
        >
          Run POC
        </button>
        <button
          className="button button-secondary"
          disabled={loadState === "loading" || !resumeAction?.enabled}
          type="button"
          onClick={onResume}
        >
          Resume
        </button>
        <button className="button button-ghost" disabled={loadState === "loading"} type="button" onClick={onRefresh}>
          Refresh
        </button>
      </div>
      <ActionReason action={runAction} />
      <ActionReason action={resumeAction} />
      <div className={`notice ${loadState === "error" ? "notice-error" : ""}`} role="status">
        {message || (loadState === "loading" ? "正在读取 POC 状态…" : "等待操作。")}
      </div>
    </section>
  );
}

function WorkflowTimeline({
  selectedStepId,
  steps,
  onSelectStep,
}: {
  selectedStepId: string | null;
  steps: PocStep[];
  onSelectStep: (stepId: string) => void;
}) {
  return (
    <section className="panel timeline-panel" aria-labelledby="timeline-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">UI-03</p>
          <h2 id="timeline-title">Workflow Timeline</h2>
        </div>
        <span className="status-pill status-muted">{steps.length} step</span>
      </div>
      {steps.length ? (
        <ol className="timeline-list">
          {steps.map((step) => (
            <li key={step.step_id}>
              <button
                aria-current={step.step_id === selectedStepId ? "step" : undefined}
                className={`timeline-step state-${step.state}`}
                type="button"
                onClick={() => onSelectStep(step.step_id)}
              >
                <span className="step-index">{step.ordinal}</span>
                <span>
                  <strong>{step.title}</strong>
                  <small>{step.summary || "n/a"}</small>
                </span>
                <StatusPill value={step.state} />
              </button>
            </li>
          ))}
        </ol>
      ) : (
        <div className="empty-state">暂无 timeline。请确认 `/poc-state` payload。</div>
      )}
    </section>
  );
}

function ActiveTaskPanel({
  activeStep,
  onDecisionSubmitted,
  selectedStep,
  studyId,
}: {
  activeStep: PocState["active_step"];
  onDecisionSubmitted: (message: string) => void;
  selectedStep: PocStep | null;
  studyId: string;
}) {
  const display = selectedStep ?? activeStep;
  const reviewId = activeStep?.review_id ?? display?.review_id ?? null;
  return (
    <section className="panel active-task" aria-labelledby="active-task-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">UI-04</p>
          <h2 id="active-task-title">Active Task</h2>
        </div>
        {activeStep?.review_id ? <span className="status-pill status-warn">{activeStep.review_id}</span> : null}
      </div>
      {display ? (
        <article>
          <h3>{display.title}</h3>
          <p>{display.summary || "无摘要。"}</p>
          {"blocking_reason" in display && display.blocking_reason ? (
            <p className="notice notice-error">{display.blocking_reason}</p>
          ) : null}
          {"next_instruction" in display && display.next_instruction ? (
            <p className="notice">{display.next_instruction}</p>
          ) : null}
          <ArtifactRefs refs={display.artifact_refs ?? []} />
          {activeStep?.kind === "review" && reviewId ? (
            <ReviewDecisionForm
              reviewId={reviewId}
              studyId={studyId}
              onSubmitted={onDecisionSubmitted}
            />
          ) : null}
        </article>
      ) : (
        <div className="empty-state">当前没有 active task。</div>
      )}
    </section>
  );
}

function EventLog({ events, health }: { events: PocState["events"]; health: PocState["health"] }) {
  return (
    <section className="panel event-log" aria-labelledby="event-log-title">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">UI-07</p>
          <h2 id="event-log-title">Event / Evidence Log</h2>
        </div>
        <span className="status-pill status-muted">{events.length} event</span>
      </div>
      <div className="evidence-grid">
        <div>
          <h3>Health</h3>
          {health.length ? (
            <ul className="compact-list">
              {health.map((item) => (
                <li key={item.check_id}>
                  <StatusPill value={item.severity} />
                  <span>{item.summary}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="empty-state">暂无 health 信息。</p>
          )}
        </div>
        <div>
          <h3>Events</h3>
          {events.length ? (
            <ol className="compact-list">
              {events
                .slice()
                .reverse()
                .map((event) => (
                  <li key={event.event_id}>
                    <span className="mono">{event.event_type}</span>
                    <span>{event.summary}</span>
                    <small>{event.occurred_at}</small>
                  </li>
                ))}
            </ol>
          ) : (
            <p className="empty-state">暂无 POC runner event。</p>
          )}
        </div>
      </div>
    </section>
  );
}

function ArtifactRefs({ refs }: { refs: PocStep["artifact_refs"] }) {
  if (!refs.length) {
    return <p className="empty-state">当前步骤无 artifact ref。</p>;
  }
  return (
    <ul className="artifact-ref-list">
      {refs.map((ref) => (
        <li key={ref.artifact_id}>
          <span>{ref.label}</span>
          <span className="mono">{shortHash(ref.sha256)}</span>
        </li>
      ))}
    </ul>
  );
}

function ActionReason({ action }: { action?: PocNextAction }) {
  if (!action || action.enabled || !action.reason) {
    return null;
  }
  return <p className="help-text">{action.label}: {action.reason}</p>;
}

function StatusPill({ value }: { value: string }) {
  return <span className={`status-pill ${statusClass(value)}`}>{value}</span>;
}

function statusClass(value: string) {
  if (["done", "ok"].includes(value)) {
    return "status-ok";
  }
  if (["running", "blocked_review", "warning", "loading"].includes(value)) {
    return "status-warn";
  }
  if (["blocked_error", "error", "failed"].includes(value)) {
    return "status-danger";
  }
  return "status-muted";
}

function shortHash(value: unknown) {
  const text = valueText(value);
  return text === "n/a" ? text : `${text.slice(0, 10)}…`;
}

function valueText(value: unknown) {
  if (value === undefined || value === null || value === "") {
    return "n/a";
  }
  return String(value);
}
