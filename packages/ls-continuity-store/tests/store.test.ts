import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";
import { openDatabase } from "../src/database.js";
import { ContinuityStore } from "../src/store.js";
import { recoverSubject } from "../src/recover.js";
import { evaluateResume } from "../src/resume.js";

const ZERO_REF = `sha256:${"0".repeat(64)}`;
const ONE_REF = `sha256:${"1".repeat(64)}`;
const fixtures = new Set<ReturnType<typeof fixture>>();

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ls-continuity-"));
  const db = openDatabase(path.join(root, "continuity.db"));
  const store = new ContinuityStore(db, path.join(root, "objects"));
  const value = { root, db, store };
  fixtures.add(value);
  return value;
}

afterEach(() => {
  for (const value of fixtures) {
    value.db.close();
    fs.rmSync(value.root, { recursive: true, force: true });
  }
  fixtures.clear();
});

function persistDecision(store: ContinuityStore, subject = "agent-1", posture = "retryable") {
  const intent = store.persist({
    schema: "ls.continuity.v1",
    object_type: "intent",
    subject_id: subject,
    created_at: new Date().toISOString(),
    payload: { action: "example_action", params_digest: ZERO_REF }
  });

  return store.persist({
    schema: "ls.continuity.v1",
    object_type: "governance_decision",
    subject_id: subject,
    previous_ref: intent.object_id,
    created_at: new Date(Date.now() + 1).toISOString(),
    payload: {
      intent_ref: intent.object_id,
      decision: posture === "pending_approval" ? "require_approval" : "allow",
      validity_state: "active",
      resume_posture: posture,
      expires_at: null,
      revalidate_if: posture === "requires_revalidation" ? ["policy_version"] : []
    }
  });
}

describe("LS Continuity Store", () => {
  it("detects byte tampering", () => {
    const { root, store } = fixture();
    const object = persistDecision(store);
    const digest = object.object_id.slice("sha256:".length);
    const file = path.join(root, "objects", digest.slice(0, 2), digest.slice(2, 4), `${digest}.json`);
    fs.writeFileSync(file, fs.readFileSync(file, "utf8").replace("retryable", "consumed"));
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
      created_at: new Date(Date.now() + 2).toISOString(),
      payload: {
        decision_ref: decision.object_id,
        status: "executed",
        result_digest: ONE_REF,
        side_effect_committed: true
      }
    });
    assert.equal(evaluateResume(recoverSubject(store, "agent-1")).reason, "AUTHORITY_CONSUMED");
  });

  it("keeps pending approval pending after recovery", () => {
    const { store } = fixture();
    persistDecision(store, "agent-2", "pending_approval");
    const state = recoverSubject(store, "agent-2");
    assert.notEqual(state?.pending_approval_ref, null);
    assert.equal(evaluateResume(state).reason, "PENDING_APPROVAL");
  });

  it("requires evidence-specific revalidation", () => {
    const { store } = fixture();
    persistDecision(store, "agent-3", "requires_revalidation");
    const result = evaluateResume(recoverSubject(store, "agent-3"));
    assert.equal(result.reason, "REVALIDATION_REQUIRED");
    assert.deepEqual(result.required_checks, ["policy_version"]);
  });

  it("fails closed when projection diverges from recovery", () => {
    const { db, store } = fixture();
    persistDecision(store, "agent-4");
    db.prepare(`UPDATE current_state SET resume_posture = 'consumed' WHERE subject_id = ?`).run("agent-4");
    assert.throws(() => recoverSubject(store, "agent-4"), /CONTINUITY_STATE_MISMATCH/);
  });
});
