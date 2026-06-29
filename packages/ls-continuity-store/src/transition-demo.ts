import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { canonicalBytes } from "./canonicalize.js";
import { openDatabase } from "./database.js";
import { sha256Ref } from "./hash.js";
import { ContinuityStore } from "./store.js";
import {
  evaluateTransitionResume,
  persistTransitionSnapshot
} from "./trustworthy-transition.js";

function ref(label: string): string {
  return sha256Ref(canonicalBytes({ demo_ref: label }));
}

const root = fs.mkdtempSync(path.join(os.tmpdir(), "ls-transition-demo-"));
const databasePath = path.join(root, "continuity.db");
const objectsPath = path.join(root, "objects");

const db = openDatabase(databasePath);
const store = new ContinuityStore(db, objectsPath);
const snapshot = persistTransitionSnapshot(
  store,
  {
    transition_id: "demo-transition-001",
    subject_id: "agent:reporter",
    action_identity_digest: ref("action"),
    binding_digest: ref("binding"),
    record_refs: {
      authorization_ref: ref("authorization"),
      observation_refs: [ref("observation")],
      response_integrity_ref: ref("response-integrity"),
      causal_audit_ref: ref("causal-audit")
    },
    dimensions: {
      authority: "VALID",
      execution: "OBSERVED_EXECUTED",
      response_integrity: "FAILED",
      causal_validity: "VALID"
    },
    side_effect_committed: true,
    authority_expires_at: "2030-01-01T01:00:00.000Z",
    context_digest: ref("runtime-context")
  },
  "2030-01-01T00:00:00.000Z"
);
db.close();

const reopenedDb = openDatabase(databasePath);
const reopenedStore = new ContinuityStore(reopenedDb, objectsPath);
const recovered = reopenedStore.load<typeof snapshot.payload>(snapshot.object_id);

const retryDecision = evaluateTransitionResume(recovered, {
  transition_id: recovered.payload.transition_id,
  subject_id: recovered.payload.subject_id,
  action_identity_digest: recovered.payload.action_identity_digest,
  binding_digest: recovered.payload.binding_digest,
  operation: "retry_side_effect",
  current_evidence_set_digest: recovered.payload.evidence_set_digest,
  current_context_digest: recovered.payload.context_digest,
  now: "2030-01-01T00:10:00.000Z"
});

const reportDecision = evaluateTransitionResume(recovered, {
  transition_id: recovered.payload.transition_id,
  subject_id: recovered.payload.subject_id,
  action_identity_digest: recovered.payload.action_identity_digest,
  binding_digest: recovered.payload.binding_digest,
  operation: "report_only",
  current_evidence_set_digest: ref("newer-evidence"),
  current_context_digest: ref("newer-context"),
  now: "2030-01-01T00:10:00.000Z"
});

console.log(
  JSON.stringify(
    {
      snapshot_ref: snapshot.object_id,
      independent_dimensions: recovered.payload.dimensions,
      retry_decision: retryDecision,
      historical_report_decision: reportDecision
    },
    null,
    2
  )
);

reopenedDb.close();
