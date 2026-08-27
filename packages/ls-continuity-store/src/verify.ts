import { canonicalBytes } from "./canonicalize.js";
import { sha256Ref } from "./hash.js";
import type { ContinuityStore } from "./store.js";

export function verifyEventChain(store: ContinuityStore, subjectId: string): void {
  const events = store.listEvents(subjectId);
  const eventRefs = events.map((event) => {
    if (typeof event.object_ref !== "string") throw new Error("INVALID_EVENT_REF");
    return event.object_ref;
  });
  const indexedRefs = store.listIndexedObjectRefs(subjectId);
  const sortedEventRefs = [...eventRefs].sort();
  if (
    sortedEventRefs.length !== indexedRefs.length ||
    sortedEventRefs.some((reference, index) => reference !== indexedRefs[index])
  ) {
    throw new Error("EVENT_OBJECT_INDEX_MISMATCH");
  }
  let previous: string | null = null;

  for (const [index, event] of events.entries()) {
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
    store.load(eventRefs[index]);
    previous = event.event_hash as string;
  }
}
