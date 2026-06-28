import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { openDatabase } from "../src/database.js";
import { ContinuityStore } from "../src/store.js";
import { recoverSubject } from "../src/recover.js";
import { evaluateResume } from "../src/resume.js";

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ls-continuity-"));
  const db = openDatabase(path.join(root, "continuity.db"));
  const store = new ContinuityStore(db, path.join(root, "objects"));
  return { root, db, store };
}

function persistDecision(store: ContinuityStore, subject = "agent-1", posture = "retryable") {
  return store.persist({
    schema: "ls.continuity.v1",
    object_type: "governance_decision",
    subject_id: subject,
    created_at: new Date().toISOString(),
    payload: {
      intent_ref: "sha256:intent",
      decision: posture === "pending_approval" ? "require_approval" : "allow",
      validity_state: "active",
      resume_posture: posture,
      expires_at: null,
      revalidate_if: []
    }
  });
}

describe("LS Continuity Store", () => {
  it("detects byte tampering", () => {
    const { root, store } = fixture();
    const object = persistDecision(store);
    const digest = object.object_id.replace("sha256:", "");
    const file = path.join(root, "objects", digest.slice(0, 2), digest.slice(2, 4), `${digest}.json`);
    const data = fs.readFileSync(file, "utf8").replace("retryable", "consumed");
    fs.writeFileSync(file, data);
    assert.throws(() => store.load(object.object_id), /OBJECT_HASH_MISMATCH/);
  });

  it("marks executed authority as consumed", () => {
    const { store } = fixture();
    const decision = persistDecision(store);
    store.persist({
      schema: "ls.continuity.v1",
      object_type: "governance_outcome",
      subject_id: "agent-1",
      previous_ref: decision.object_id,
      created_at: new Date(Date.now() + 1).toISOString(),
      payload: {
        decision_ref: decision.object_id,
        status: "executed",
        result_digest: "sha256:result",
        side_effect_committed: true
      }
    });
    const state = recoverSubject(store, "agent-1");
    assert.equal(evaluateResume(state).reason, "AUTHORITY_CONSUMED");
  });

  it("keeps pending approval pending after recovery", () => {
    const { store } = fixture();
    persistDecision(store, "agent-2", "pending_approval");
    const state = recoverSubject(store, "agent-2");
    assert.notEqual(state?.pending_approval_ref, null);
    assert.equal(evaluateResume(state).reason, "PENDING_APPROVAL");
  });

  it("requires revalidation when context drift is recorded", () => {
    const { store } = fixture();
    persistDecision(store, "agent-3", "requires_revalidation");
    const state = recoverSubject(store, "agent-3");
    assert.equal(evaluateResume(state).reason, "REVALIDATION_REQUIRED");
  });

  it("fails closed when projection diverges from recovery", () => {
    const { db, store } = fixture();
    persistDecision(store, "agent-4", "retryable");
    db.prepare(`UPDATE current_state SET resume_posture = 'consumed' WHERE subject_id = ?`).run("agent-4");
    assert.throws(() => recoverSubject(store, "agent-4"), /CONTINUITY_STATE_MISMATCH/);
  });
});
