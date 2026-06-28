import assert from "node:assert/strict";
import type { ContinuityStore } from "./store.js";
import type { ContinuationState, StoredContinuityObject } from "./types.js";
import { verifyEventChain } from "./verify.js";

function initialState(object: StoredContinuityObject<Record<string, unknown>>): ContinuationState {
  return {
    subject_id: object.subject_id,
    checkpoint_ref: null,
    decision_ref: null,
    outcome_ref: null,
    validity_state: "active",
    resume_posture: "requires_revalidation",
    pending_approval_ref: null,
    updated_at: object.created_at
  };
}

function applyObject(state: ContinuationState | null, object: StoredContinuityObject<Record<string, unknown>>): ContinuationState {
  const next = state ?? initialState(object);
  const payload = object.payload as Record<string, unknown>;

  if (object.object_type === "governance_decision") {
    next.decision_ref = object.object_id;
    next.validity_state = payload.validity_state as ContinuationState["validity_state"];
    next.resume_posture = payload.resume_posture as ContinuationState["resume_posture"];
    next.pending_approval_ref = payload.decision === "require_approval" ? object.object_id : null;
  } else if (object.object_type === "governance_outcome") {
    next.outcome_ref = object.object_id;
    if (payload.side_effect_committed === true || payload.status === "executed") next.resume_posture = "consumed";
    else if (payload.status === "errored") next.resume_posture = "requires_revalidation";
  } else if (object.object_type === "continuation_checkpoint") {
    next.checkpoint_ref = object.object_id;
    next.decision_ref = (payload.latest_decision_ref as string | null | undefined) ?? next.decision_ref;
    next.outcome_ref = (payload.latest_outcome_ref as string | null | undefined) ?? next.outcome_ref;
    next.pending_approval_ref = (payload.pending_approval_ref as string | null | undefined) ?? null;
    next.validity_state = payload.validity_state as ContinuationState["validity_state"];
    next.resume_posture = payload.resume_posture as ContinuationState["resume_posture"];
  }

  next.updated_at = object.created_at;
  return next;
}

export function recoverSubject(store: ContinuityStore, subjectId: string): ContinuationState | null {
  verifyEventChain(store, subjectId);
  let rebuilt: ContinuationState | null = null;
  for (const event of store.listEvents(subjectId)) {
    const object = store.load(event.object_ref as string) as StoredContinuityObject<Record<string, unknown>>;
    rebuilt = applyObject(rebuilt, object);
  }
  const projected = store.getCurrentState(subjectId);
  assert.deepEqual(projected, rebuilt, "CONTINUITY_STATE_MISMATCH");
  return rebuilt;
}
