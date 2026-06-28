import os from "node:os";
import path from "node:path";
import fs from "node:fs";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { openDatabase } from "../src/database.js";
import { ContinuityStore } from "../src/store.js";
import { recoverSubject } from "../src/recover.js";
import { evaluateResume } from "../src/resume.js";

const DIGEST = `sha256:${"2".repeat(64)}`;

function makeStore() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ls-review-"));
  const db = openDatabase(path.join(root, "continuity.db"));
  return new ContinuityStore(db, path.join(root, "objects"));
}

function allowDecision(store: ContinuityStore, subject: string, expiresAt: string | null = null) {
  const intent = store.persist({
    schema: "ls.continuity.v1",
    object_type: "intent",
    subject_id: subject,
    created_at: "2026-06-28T00:00:00.000Z",
    payload: { action: "example_action", params_digest: DIGEST }
  });

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

describe("review regressions", () => {
  it("rejects denied decisions that claim retryability", () => {
    const store = makeStore();
    const intent = store.persist({
      schema: "ls.continuity.v1",
      object_type: "intent",
      subject_id: "denied",
      created_at: "2026-06-28T00:00:00.000Z",
      payload: { action: "example_action", params_digest: DIGEST }
    });

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

  it("rejects malformed object references", () => {
    const store = makeStore();
    assert.throws(() => store.load("invalid-ref"), /INVALID_OBJECT_REF/);
  });
});
