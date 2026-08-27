import assert from "node:assert/strict";
import type { ContinuityStore } from "./store.js";
import type { ContinuationState, StoredContinuityObject } from "./types.js";
import { verifyEventChain } from "./verify.js";

/** Rebuilds one subject state from the ordered object stream. */
export function recoverSubject(store: ContinuityStore, subjectId: string): ContinuationState | null {
  return store.withReadSnapshot(() => {
    verifyEventChain(store, subjectId);
    let rebuilt: ContinuationState | null = null;

    for (const event of store.listEvents(subjectId)) {
      const ref = event["object_ref"];
      if (typeof ref !== "string") throw new Error("INVALID_EVENT_REF");
      const item = store.load(ref) as StoredContinuityObject<Record<string, unknown>>;
      rebuilt = store.deriveNextState(rebuilt, item);
    }

    assert.deepEqual(store.getCurrentState(subjectId), rebuilt, "CONTINUITY_STATE_MISMATCH");
    return rebuilt;
  });
}
