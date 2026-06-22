// Authoritative contract: schemas/review/review-protocol.schema.json.
// Keep this thin TypeScript layer in sync through schema drift tests.

export type ReviewType =
  | "sdtm_spec"
  | "adam_spec"
  | "tfl_shell"
  | "tfl_qc"
  | "sap_review"
  | "submission";

export type FindingCategory =
  | "mapping"
  | "derivation"
  | "population"
  | "terminology"
  | "compliance"
  | "formatting";

export type Severity = "critical" | "warning" | "info";
export type Urgency = "normal" | "blocking";
export type DecisionValue = "approved" | "rejected" | "modified";

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

export const REJECTION_REASONS: RejectionReason[] = [
  "wrong_domain_assignment",
  "incorrect_variable_mapping",
  "incorrect_derivation",
  "wrong_ct_value",
  "missing_variable",
  "incorrect_population",
  "incorrect_method",
  "insufficient_evidence",
  "other",
];

export const REJECTION_REASON_LABELS: Record<RejectionReason, string> = {
  wrong_domain_assignment: "Wrong domain assignment",
  incorrect_variable_mapping: "Incorrect variable mapping",
  incorrect_derivation: "Incorrect derivation",
  wrong_ct_value: "Wrong controlled terminology value",
  missing_variable: "Missing variable",
  incorrect_population: "Incorrect population definition",
  incorrect_method: "Incorrect method",
  insufficient_evidence: "Insufficient evidence",
  other: "Other",
};

export interface ReviewFinding {
  id: string;
  category: FindingCategory;
  severity: Severity;
  location: string;
  title: string;
  current_value: string;
  proposed_value: string;
  rationale: string;
  evidence_refs: string[];
  auto_approved: boolean;
}

export interface ReviewPacket {
  review_id: string;
  review_type: ReviewType;
  source_documents: string[];
  agent_summary: string;
  findings: ReviewFinding[];
  urgency: Urgency;
  created_at: string;
  generated_by: string;
  auto_approved_count: number;
}

export interface FindingDecision {
  finding_id: string;
  decision: DecisionValue;
  modified_value?: string;
  rejection_reason?: RejectionReason;
  human_correction?: string;
  reference?: string;
  comment?: string;
}

export interface DecisionReceipt {
  review_id: string;
  reviewer: string;
  timestamp: string;
  decisions: FindingDecision[];
  general_notes?: string;
}

export function validateReviewPacket(value: unknown): string[] {
  const errors: string[] = [];
  const packet = value as Partial<ReviewPacket>;
  const required = [
    "review_id",
    "review_type",
    "source_documents",
    "agent_summary",
    "findings",
    "urgency",
    "created_at",
    "generated_by",
    "auto_approved_count",
  ] as const;

  if (!packet || typeof packet !== "object") {
    return ["Review packet must be an object."];
  }

  for (const field of required) {
    if (packet[field] === undefined || packet[field] === null) {
      errors.push(`ReviewPacket.${field} is required.`);
    }
  }

  if (!Array.isArray(packet.findings) || packet.findings.length === 0) {
    errors.push("ReviewPacket.findings must contain at least one finding.");
  } else {
    for (const finding of packet.findings) {
      errors.push(...validateFinding(finding));
    }
  }

  return errors;
}

export function validateDecisionReceiptForPacket(
  packet: ReviewPacket,
  receipt: DecisionReceipt,
): string[] {
  const errors: string[] = [];
  const findingIds = new Set(packet.findings.map((finding) => finding.id));
  const expectedDecisionIds = new Set(
    packet.findings
      .filter((finding) => !finding.auto_approved)
      .map((finding) => finding.id),
  );

  if (receipt.review_id !== packet.review_id) {
    errors.push("DecisionReceipt.review_id must match ReviewPacket.review_id.");
  }
  if (!receipt.reviewer || receipt.reviewer.trim().length < 2) {
    errors.push("Reviewer is required.");
  }
  if (!receipt.timestamp) {
    errors.push("DecisionReceipt.timestamp is required.");
  }
  if (!Array.isArray(receipt.decisions) || receipt.decisions.length === 0) {
    errors.push("At least one finding decision is required.");
  }

  for (const decision of receipt.decisions || []) {
    if (!findingIds.has(decision.finding_id)) {
      errors.push(`Unknown finding_id: ${decision.finding_id}.`);
    }
    expectedDecisionIds.delete(decision.finding_id);
    errors.push(...validateFindingDecision(decision));
  }

  for (const missing of expectedDecisionIds) {
    errors.push(`Finding ${missing} requires a decision.`);
  }

  return errors;
}

export function validateFindingDecision(decision: FindingDecision): string[] {
  const errors: string[] = [];
  if (!decision.finding_id) {
    errors.push("finding_id is required.");
  }
  if (!decision.decision) {
    errors.push(`Decision for ${decision.finding_id || "(unknown)"} is required.`);
    return errors;
  }

  if (decision.decision === "modified" && !hasText(decision.modified_value)) {
    errors.push(`Decision ${decision.finding_id}: modified_value is required.`);
  }

  if (decision.decision === "rejected") {
    if (!decision.rejection_reason) {
      errors.push(`Decision ${decision.finding_id}: rejection_reason is required.`);
    } else if (!REJECTION_REASONS.includes(decision.rejection_reason)) {
      errors.push(`Decision ${decision.finding_id}: invalid rejection_reason.`);
    } else if (
      decision.rejection_reason !== "insufficient_evidence" &&
      (!hasText(decision.human_correction) || decision.human_correction!.trim().length < 10)
    ) {
      errors.push(
        `Decision ${decision.finding_id}: human_correction must be at least 10 characters.`,
      );
    }
  }

  return errors;
}

function validateFinding(finding: ReviewFinding): string[] {
  const errors: string[] = [];
  const required = [
    "id",
    "category",
    "severity",
    "location",
    "title",
    "current_value",
    "proposed_value",
    "rationale",
    "evidence_refs",
    "auto_approved",
  ] as const;

  for (const field of required) {
    if (finding[field] === undefined || finding[field] === null) {
      errors.push(`ReviewFinding.${field} is required.`);
    }
  }

  if (!Array.isArray(finding.evidence_refs) || finding.evidence_refs.length === 0) {
    errors.push(`Finding ${finding.id || "(unknown)"} requires evidence_refs.`);
  }

  return errors;
}

function hasText(value: string | undefined): boolean {
  return typeof value === "string" && value.trim().length > 0;
}
