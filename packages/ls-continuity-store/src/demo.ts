import path from "node:path";
import { openDatabase } from "./database.js";
import { ContinuityStore } from "./store.js";
import { evaluateResume } from "./resume.js";
import { recoverSubject } from "./recover.js";

const db = openDatabase(path.resolve("data/continuity.db"));
const store = new ContinuityStore(db, path.resolve("data/objects"));
const now = new Date().toISOString();

const intent = store.persist({
  schema: "ls.continuity.v1",
  object_type: "intent",
  subject_id: "agent-demo",
  created_at: now,
  payload: {
    action: "send_email",
    target: "user@example.com",
    params_digest: "sha256:example"
  }
});

store.persist({
  schema: "ls.continuity.v1",
  object_type: "governance_decision",
  subject_id: "agent-demo",
  previous_ref: intent.object_id,
  created_at: new Date(Date.now() + 1).toISOString(),
  payload: {
    intent_ref: intent.object_id,
    decision: "allow",
    validity_state: "active",
    resume_posture: "retryable",
    expires_at: null,
    revalidate_if: ["target_changed", "policy_changed"]
  }
});

const state = recoverSubject(store, "agent-demo");
console.log(JSON.stringify({ state, resume: evaluateResume(state) }, null, 2));
