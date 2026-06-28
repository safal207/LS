import type { ContinuationState, ResumeDecision } from "./types.js";

export function evaluateResume(state: ContinuationState | null): ResumeDecision {
  if (!state) return { allowed: false, reason: "NO_STATE", checkpoint_ref: null, required_checks: [] };
  if (state.pending_approval_ref || state.resume_posture === "pending_approval") return { allowed: false, reason: "PENDING_APPROVAL", checkpoint_ref: state.checkpoint_ref, required_checks: [] };
  if (state.validity_state === "expired") return { allowed: false, reason: "AUTHORITY_EXPIRED", checkpoint_ref: state.checkpoint_ref, required_checks: [] };
  if (state.validity_state === "invalidated" || state.validity_state === "superseded") return { allowed: false, reason: "AUTHORITY_INVALIDATED", checkpoint_ref: state.checkpoint_ref, required_checks: ["fresh_decision"] };
  if (state.resume_posture === "consumed") return { allowed: false, reason: "AUTHORITY_CONSUMED", checkpoint_ref: state.checkpoint_ref, required_checks: [] };
  if (state.resume_posture === "requires_revalidation") return { allowed: false, reason: "REVALIDATION_REQUIRED", checkpoint_ref: state.checkpoint_ref, required_checks: ["policy_version", "target_state"] };
  if (state.resume_posture === "non_retryable") return { allowed: false, reason: "NON_RETRYABLE", checkpoint_ref: state.checkpoint_ref, required_checks: [] };
  return { allowed: true, reason: "OK", checkpoint_ref: state.checkpoint_ref, required_checks: [] };
}
