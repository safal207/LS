import type { ContinuationState, ResumeDecision } from "./types.js";

function result(
  state: ContinuationState | null,
  reason: ResumeDecision["reason"],
  checks: string[] = []
): ResumeDecision {
  return {
    allowed: reason === "OK",
    reason,
    checkpoint_ref: state?.checkpoint_ref ?? null,
    required_checks: [...new Set(checks)].sort()
  };
}

/** Evaluates whether the current continuation state may proceed. */
export function evaluateResume(state: ContinuationState | null, now: Date = new Date()): ResumeDecision {
  if (!state) return result(null, "NO_STATE");
  if (state.pending_approval_ref || state.decision_state === "require_approval" || state.resume_posture === "pending_approval") {
    return result(state, "PENDING_APPROVAL");
  }
  if (state.decision_state !== "allow") return result(state, "DECISION_NOT_ALLOWED");

  if (state.expires_at) {
    const deadline = Date.parse(state.expires_at);
    if (!Number.isFinite(deadline)) return result(state, "UNKNOWN_STATE", ["valid_expiry"]);
    if (deadline <= now.getTime()) return result(state, "AUTHORITY_EXPIRED");
  }

  if (state.validity_state === "expired") return result(state, "AUTHORITY_EXPIRED");
  if (state.validity_state === "invalidated" || state.validity_state === "superseded") {
    return result(state, "AUTHORITY_INVALIDATED", ["fresh_decision"]);
  }
  if (state.resume_posture === "consumed") return result(state, "AUTHORITY_CONSUMED");
  if (state.resume_posture === "non_retryable") return result(state, "NON_RETRYABLE");
  if (state.resume_posture === "requires_revalidation" || state.required_checks.length > 0) {
    return result(state, "REVALIDATION_REQUIRED", [...state.revalidate_if, ...state.required_checks]);
  }
  if (state.validity_state === "active" && state.resume_posture === "retryable") {
    return result(state, "OK");
  }
  return result(state, "UNKNOWN_STATE", ["fresh_verification"]);
}
