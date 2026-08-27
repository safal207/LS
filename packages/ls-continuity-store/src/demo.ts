import fs from "node:fs";
import path from "node:path";
import { openDatabase } from "./database.js";
import { ContinuityStore } from "./store.js";
import { evaluateResume } from "./resume.js";
import { recoverSubject } from "./recover.js";

const dataDir = path.resolve("data");
fs.mkdirSync(dataDir, { recursive: true });
const db = openDatabase(path.join(dataDir, "continuity.db"));
const store = new ContinuityStore(db, path.join(dataDir, "objects"));
const now = new Date().toISOString();
const paramsDigest = `sha256:${"0".repeat(64)}`;

const intent = store.persist({
  schema: "ls.continuity.v1",
  object_type: "intent",
  subject_id: "agent-demo",
  created_at: now,
  payload: {
    action: "example_action",
    target: "user@example.com",
    params_digest: paramsDigest
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
db.close();
