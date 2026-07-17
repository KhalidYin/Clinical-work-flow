export type RunState = "idle" | "running" | "blocked" | "done";

export type StepState =
  | "pending"
  | "running"
  | "done"
  | "blocked"
  | "skipped";

export type StepKind = "instruction" | "review" | "artifact" | "error" | "complete";

export type ActionId =
  | "run_poc"
  | "retry_current_step"
  | "open_review"
  | "resume"
  | "refresh"
  | "open_output_folder";

export type CheckState = "pass" | "warning" | "fail" | "unknown" | "not_applicable";

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

export interface ArtifactSummary {
  artifact_id: string;
  stage_id: string;
  artifact_state: string;
  artifact_type: string;
  display_name: string;
  sha256: string;
  provenance_id?: string | null;
  preview_available: boolean;
}

export type ArtifactPreviewPayload =
  | { kind: "json" | "yaml"; value: unknown }
  | { kind: "csv"; rows: Array<Record<string, string>>; row_count: number }
  | { kind: "text"; value: string };

export interface ArtifactDetail {
  artifact: ArtifactSummary;
  registered_ref: {
    container_id: "clinical-studies";
    relative_path: string;
    sha256: string;
  };
  preview: ArtifactPreviewPayload | null;
}

export interface PocStep {
  step_id: string;
  ordinal: number;
  title: string;
  state: StepState;
  kind: StepKind;
  summary: string;
  started_at?: string | null;
  completed_at?: string | null;
  checks: PocStepCheck[];
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
  primary: boolean;
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
  run_id?: string | null;
  step_id?: string | null;
  summary: string;
  severity: "ok" | "warning" | "error";
  related_refs: Array<Record<string, unknown>>;
}

export interface PocStepCheck {
  check_id: string;
  state: CheckState;
  summary: string;
  detail?: string | null;
  observed?: string | number | boolean | null;
  expected?: string | number | boolean | null;
  affected_variables: string[];
  evidence_refs: string[];
}

export interface PocBlocker {
  kind: "input" | "validation" | "review" | "system";
  stage_id: string;
  code: string;
  summary: string;
  detail: string;
  affected_variables: string[];
  affected_artifacts: string[];
  evidence_refs: string[];
  recovery_action:
    | "provide_input"
    | "repair_input"
    | "install_dependency"
    | "retry_current_step"
    | "submit_review_decision"
    | "resume_after_review"
    | "refresh";
  review_id?: string | null;
  retryable: boolean;
}

export interface PocVariableProfile {
  variable: string;
  label?: string | null;
  data_type?: string | null;
  format?: string | null;
  missing_count?: number | null;
  non_missing_count?: number | null;
  distinct_count?: number | null;
  value_labels_available?: boolean | null;
  evidence_refs: string[];
}

export interface PocInputCheck {
  checked_at?: string | null;
  summary: {
    status: "not_run" | "ready" | "warning" | "blocked" | "partial";
    required_total: number;
    required_ready: number;
    blocking_count: number;
    warning_count: number;
    message: string;
  };
  files: Array<{
    source_id: string;
    label: string;
    relative_path: string;
    format: string;
    exists: boolean;
    sha256?: string | null;
    size_bytes?: number | null;
    parser?: string | null;
    parser_available?: boolean | null;
    row_count?: number | null;
    column_count?: number | null;
    labels_available?: boolean | null;
    formats_available?: boolean | null;
    value_labels_available?: boolean | null;
    warnings: string[];
    evidence_refs: string[];
  }>;
  dependencies: Array<{
    input_id: string;
    label: string;
    requirement: "required" | "conditional" | "optional" | "not_required";
    status: "available" | "missing" | "invalid" | "gap" | "not_required";
    blocking: boolean;
    detail?: string | null;
    evidence_refs: string[];
  }>;
  checks: PocStepCheck[];
  variable_profiles: PocVariableProfile[];
  warnings: string[];
}

export interface PocState {
  schema_version: "2.0";
  study_id: string;
  target_artifact: "sdtm_ae_dataset";
  run_id?: string | null;
  run_state: RunState;
  legacy_run_state?: string | null;
  source: Record<string, unknown>;
  knowledge: Record<string, unknown>;
  input_check: PocInputCheck;
  blocker?: PocBlocker | null;
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

export type ReviewDecisionState = "pending" | "decided" | "confirmed" | "rejected" | "stale" | "invalid";

export type FindingDecisionValue = "approved" | "rejected" | "modified";

export type RejectionReason =
  | "wrong_domain_assignment"
  | "incorrect_variable_mapping"
  | "incorrect_derivation"
  | "wrong_ct_value"
  | "missing_variable"
  | "incorrect_population"
  | "incorrect_method"
  | "insufficient_evidence"
  | "other";

export interface ReviewFindingSummary {
  finding_id: string;
  category: string;
  severity: string;
  location: string;
  title: string;
  current_value: string;
  proposed_value: string;
  rationale: string;
  evidence_refs: string[];
  auto_approved: boolean;
}

export interface ReviewSummary {
  review_id: string;
  review_type: string;
  urgency: "normal" | "blocking";
  decision_state: ReviewDecisionState;
  finding_count: number;
  packet_sha256: string;
  confirmation_sha256?: string | null;
  agent_summary?: string | null;
  source_documents: string[];
  created_at?: string | null;
  findings: ReviewFindingSummary[];
}

export interface ReviewsResponse {
  reviews: ReviewSummary[];
  partial_errors: Array<Record<string, unknown>>;
}

export interface FindingDecisionPayload {
  finding_id: string;
  decision: FindingDecisionValue;
  modified_value?: string;
  rejection_reason?: RejectionReason;
  human_correction?: string;
  reference?: string;
  comment?: string | null;
}

export interface ReviewDecisionRequest {
  review_id: string;
  packet_sha256: string;
  reviewer: string;
  decisions: FindingDecisionPayload[];
  general_notes?: string;
}

export interface ReviewDecisionAccepted {
  review_id: string;
  decision_receipt_id: string;
  written: boolean;
  idempotency_key: string;
}
