export type RunState = "idle" | "running" | "blocked_review" | "blocked_error" | "done";

export type StepState =
  | "pending"
  | "running"
  | "done"
  | "blocked_review"
  | "blocked_error"
  | "skipped";

export type StepKind = "instruction" | "review" | "artifact" | "error" | "complete";

export type ActionId = "run_poc" | "resume" | "refresh" | "open_output_folder";

export interface StudySummary {
  study_id: string;
  title?: string | null;
  run_state?: string;
  current_stage?: string;
}

export interface StudiesResponse {
  studies: StudySummary[];
  partial_errors: Array<Record<string, unknown>>;
}

export interface ArtifactRef {
  artifact_id: string;
  label: string;
  relative_path: string;
  kind: string;
  sha256?: string | null;
  preview_available: boolean;
}

export interface PocStep {
  step_id: string;
  ordinal: number;
  title: string;
  state: StepState;
  kind: StepKind;
  summary: string;
  blocking_reason?: string | null;
  review_id?: string | null;
  artifact_refs: ArtifactRef[];
  evidence_refs: string[];
}

export interface PocActiveStep {
  step_id: string;
  kind: StepKind;
  title: string;
  summary: string;
  blocking_reason?: string | null;
  next_instruction?: string | null;
  review_id?: string | null;
  artifact_refs: ArtifactRef[];
}

export interface PocNextAction {
  action_id: ActionId;
  label: string;
  enabled: boolean;
  reason?: string | null;
  method: "GET" | "POST";
  endpoint: string;
}

export interface PocHealthItem {
  check_id: string;
  severity: "ok" | "warning" | "error";
  summary: string;
  detail?: string | null;
  evidence_refs: string[];
}

export interface PocEvent {
  event_id: string;
  event_type: string;
  occurred_at: string;
  step_id?: string | null;
  summary: string;
  severity: "ok" | "warning" | "error";
  related_refs: Array<Record<string, unknown>>;
}

export interface PocState {
  study_id: string;
  target_artifact: "sdtm_ae_dataset";
  run_id?: string | null;
  run_state: RunState;
  source: Record<string, unknown>;
  knowledge: Record<string, unknown>;
  blocking_reason?: string | null;
  active_step?: PocActiveStep | null;
  steps: PocStep[];
  next_actions: PocNextAction[];
  health: PocHealthItem[];
  events: PocEvent[];
  partial_errors: Array<Record<string, unknown>>;
}

export interface PocRunResponse {
  accepted: boolean;
  run_id: string;
  run_state: RunState;
  state_endpoint: string;
  message: string;
}
