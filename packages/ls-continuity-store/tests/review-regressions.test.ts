import os from "node:os";
import path from "node:path";
import fs from "node:fs";
import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";
import { openDatabase } from "../src/database.js";
import { ContinuityStore } from "../src/store.js";
import { recoverSubject } from "../src/recover.js";
import { evaluateResume } from "../src/resume.js";

const DIGEST = `sha256:${"2".repeat(64)}`;
const MISSING_REF = `sha256:${"9".repeat(64)}`;
const fixtures = new Set<ReturnType<typeof makeFixture>>();

function makeFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ls-review-"));
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

function makeStore() {
  return makeFixture().store;
}

function persistIntent(
  store: ContinuityStore,
  subject: string,
  action = "example_action",
  createdAt = "2026-06-28T00:00:00.000Z"
) {
  return store.persist({
    schema: "ls.continuity.v1",
    object_type: "intent",
    subject_id: subject,
    created_at: createdAt,
    payload: { action, params_digest: DIGEST }
  });
}

function allowDecision(store: ContinuityStore, subject: string, expiresAt: string | null = null) {
  const intent = persistIntent(store, subject);

  return store.persist({
    schema: "ls.continuity.v1",
    object_type: "governance_decision",
    subject_id: subject,
    previous_ref: intent.object_id,
    created_at: "2026-06-28T00:00:01.000Z",
    payload: {
      intent_ref: intent.object_id,
      decision: "allow",
      validity_state: "active",
      resume_posture: "retryable",
      expires_at: expiresAt,
      revalidate_if: []
    }
  });
}

function persistAllowForIntent(store: ContinuityStore, subject: string, intentRef: string) {
  return store.persist({
    schema: "ls.continuity.v1",
    object_type: "governance_decision",
    subject_id: subject,
    previous_ref: intentRef,
    created_at: "2026-06-28T00:00:01.000Z",
    payload: {
      intent_ref: intentRef,
      decision: "allow",
      validity_state: "active",
      resume_posture: "retryable",
      expires_at: null,
      revalidate_if: []
    }
  });
}

describe("review regressions", () => {
  it("rejects denied decisions that claim retryability", () => {
    const store = makeStore();
    const intent = persistIntent(store, "denied");

    assert.throws(() => store.persist({
      schema: "ls.continuity.v1",
      object_type: "governance_decision",
      subject_id: "denied",
      previous_ref: intent.object_id,
      created_at: "2026-06-28T00:00:01.000Z",
      payload: {
        intent_ref: intent.object_id,
        decision: "deny",
        validity_state: "active",
        resume_posture: "retryable",
        expires_at: null,
        revalidate_if: []
      }
    }), /resume_posture/);
  });

  it("does not let a checkpoint reopen a consumed action", () => {
    const store = makeStore();
    const decision = allowDecision(store, "checkpoint");
    const outcome = store.persist({
      schema: "ls.continuity.v1",
      object_type: "governance_outcome",
      subject_id: "checkpoint",
      previous_ref: decision.object_id,
      created_at: "2026-06-28T00:00:02.000Z",
      payload: {
        decision_ref: decision.object_id,
        status: "executed",
        result_digest: DIGEST,
        side_effect_committed: true
      }
    });

    assert.throws(() => store.persist({
      schema: "ls.continuity.v1",
      object_type: "continuation_checkpoint",
      subject_id: "checkpoint",
      previous_ref: outcome.object_id,
      created_at: "2026-06-28T00:00:03.000Z",
      payload: {
        latest_decision_ref: decision.object_id,
        latest_outcome_ref: outcome.object_id,
        pending_approval_ref: null,
        validity_state: "active",
        resume_posture: "retryable",
        required_checks: []
      }
    }), /CHECKPOINT_AUTHORITY_MISMATCH/);
  });

  it("enforces the stored expiration time", () => {
    const store = makeStore();
    allowDecision(store, "expiry", "2026-01-01T00:00:00.000Z");
    const state = recoverSubject(store, "expiry");
    assert.equal(evaluateResume(state, new Date("2026-02-01T00:00:00.000Z")).reason, "AUTHORITY_EXPIRED");
  });

  it("stores an equivalent object only once", () => {
    const store = makeStore();
    const first = store.persist({
      schema: "ls.continuity.v1",
      object_type: "intent",
      subject_id: "same",
      created_at: "2026-06-28T00:00:00.000Z",
      payload: { action: "example_action", target: "sample", params_digest: DIGEST }
    });
    const second = store.persist({
      schema: "ls.continuity.v1",
      object_type: "intent",
      subject_id: "same",
      created_at: "2026-06-28T00:00:00.000Z",
      payload: { params_digest: DIGEST, target: "sample", action: "example_action" }
    });

    assert.equal(first.object_id, second.object_id);
    assert.equal(store.listEvents("same").length, 1);
  });

  it("accepts a write-time EEXIST for the same canonical object", () => {
    const store = makeStore();
    const mutableFs = fs as unknown as { writeFileSync: (...args: any[]) => void };
    const originalWrite = mutableFs.writeFileSync;
    let injected = false;

    mutableFs.writeFileSync = (...args: any[]) => {
      const options = args[2] as { flag?: string } | undefined;
      if (!injected && options?.flag === "wx") {
        injected = true;
        originalWrite(...args);
        const error = new Error("simulated concurrent winner") as NodeJS.ErrnoException;
        error.code = "EEXIST";
        throw error;
      }
      originalWrite(...args);
    };

    try {
      const object = persistIntent(store, "race");
      assert.match(object.object_id, /^sha256:[0-9a-f]{64}$/);
      assert.equal(store.listEvents("race").length, 1);
    } finally {
      mutableFs.writeFileSync = originalWrite;
    }
  });

  it("rejects a decision whose intent does not exist", () => {
    const store = makeStore();
    assert.throws(
      () => persistAllowForIntent(store, "missing-intent", MISSING_REF),
      /DECISION_INTENT_NOT_INDEXED/
    );
  });

  it("rejects a decision whose intent_ref points to another object type", () => {
    const store = makeStore();
    const receipt = store.persist({
      schema: "ls.continuity.v1",
      object_type: "verification_receipt",
      subject_id: "wrong-type",
      created_at: "2026-06-28T00:00:00.000Z",
      payload: { verifier: "test" }
    });

    assert.throws(
      () => persistAllowForIntent(store, "wrong-type", receipt.object_id),
      /DECISION_INTENT_TYPE_MISMATCH/
    );
  });

  it("rejects a decision whose intent belongs to another subject", () => {
    const store = makeStore();
    const foreignIntent = persistIntent(store, "subject-a");
    assert.throws(
      () => persistAllowForIntent(store, "subject-b", foreignIntent.object_id),
      /DECISION_INTENT_SUBJECT_MISMATCH/
    );
  });

  it("rejects orphan intent files that were never indexed as evidence", () => {
    const { db, store } = makeFixture();
    const intent = persistIntent(store, "orphan");

    db.prepare("DELETE FROM current_state WHERE subject_id = ?").run("orphan");
    db.prepare("DELETE FROM event_log WHERE subject_id = ?").run("orphan");
    db.prepare("DELETE FROM objects WHERE object_id = ?").run(intent.object_id);

    assert.throws(
      () => persistAllowForIntent(store, "orphan", intent.object_id),
      /DECISION_INTENT_NOT_INDEXED/
    );
  });

  it("rejects a decision for an older intent after a newer intent exists", () => {
    const store = makeStore();
    const first = persistIntent(store, "stale-intent", "first_action", "2026-06-28T00:00:00.000Z");
    const second = persistIntent(store, "stale-intent", "second_action", "2026-06-28T00:00:01.000Z");

    assert.throws(
      () => persistAllowForIntent(store, "stale-intent", first.object_id),
      /DECISION_INTENT_NOT_CURRENT/
    );
    assert.doesNotThrow(() => persistAllowForIntent(store, "stale-intent", second.object_id));
  });

  it("clears prior authority when a new intent is persisted", () => {
    const store = makeStore();
    allowDecision(store, "new-intent");
    assert.equal(evaluateResume(recoverSubject(store, "new-intent")).reason, "OK");

    const nextIntent = persistIntent(
      store,
      "new-intent",
      "second_action",
      "2026-06-28T00:00:02.000Z"
    );
    const state = recoverSubject(store, "new-intent");

    assert.equal(state?.latest_intent_ref, nextIntent.object_id);
    assert.equal(state?.decision_ref, null);
    assert.equal(state?.decision_state, null);
    assert.equal(evaluateResume(state).reason, "DECISION_NOT_ALLOWED");
  });

  it("accepts a decision backed by the current same-subject intent", () => {
    const store = makeStore();
    allowDecision(store, "valid-intent");
    assert.equal(evaluateResume(recoverSubject(store, "valid-intent")).reason, "OK");
  });

  it("rejects malformed object references", () => {
    const store = makeStore();
    assert.throws(() => store.load("invalid-ref"), /INVALID_OBJECT_REF/);
  });
});
