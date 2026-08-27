import { canonicalBytes } from "./canonicalize.js";
import { sha256Ref } from "./hash.js";
import type { ContinuityStore } from "./store.js";

export function verifyEventChain(store: ContinuityStore, subjectId: string): void {
  const events = store.listEvents(subjectId);
  let previous: string | null = null;

  for (const event of events) {
    const body = {
      event_type: event.event_type,
      subject_id: event.subject_id,
      object_ref: event.object_ref,
      previous_event_hash: event.previous_event_hash,
      created_at: event.created_at
    };
    const recomputed = sha256Ref(canonicalBytes(body));
    if (event.previous_event_hash !== previous) throw new Error("EVENT_CHAIN_BROKEN");
    if (event.event_hash !== recomputed) throw new Error("EVENT_HASH_MISMATCH");
    store.load(event.object_ref as string);
    previous = event.event_hash as string;
  }
}
