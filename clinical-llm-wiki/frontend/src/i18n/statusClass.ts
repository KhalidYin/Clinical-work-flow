import type { RecordStatus, ProcessingRunStatus } from "../contracts/knowledgeApi";
import styles from "../pages/pages.module.css";

const STATUS_CLASS_MAP: Record<string, string> = {
  released: styles.statusReleased,
  approved: styles.statusApproved,
  active: styles.statusActive,
  author_confirmation_required: styles.statusAuthorConfirmationRequired,
  author_confirmed: styles.statusAuthorConfirmed,
  succeeded: styles.statusSucceeded,
  accepted: styles.statusAccepted,
  passed: styles.statusPassed,
  processing: styles.statusProcessing,
  candidate: styles.statusCandidate,
  queued: styles.statusQueued,
  review_required: styles.statusReviewRequired,
  review: styles.statusReview,
  evidence_ready: styles.statusEvidenceReady,
  restricted: styles.statusRestricted,
  disabled: styles.statusDisabled,
  failed: styles.statusFailed,
  cancelled: styles.statusCancelled,
  blocked: styles.statusBlocked,
  expired: styles.statusExpired,
  rejected: styles.statusRejected,
  changes_requested: styles.statusChangesRequested,
  registered: styles.statusRegistered,
  draft: styles.statusDraft,
  superseded: styles.statusSuperseded,
  retired: styles.statusRetired,
  unversioned: styles.statusUnversioned,
  leased: styles.statusLeased,
  not_released: styles.statusNotReleased,
  not_verified: styles.statusNotVerified,
  proposed: styles.statusProposed,
  release_blocked: styles.statusReleaseBlocked,
};

export function statusClass(status: string): string {
  return STATUS_CLASS_MAP[status] ?? "";
}
