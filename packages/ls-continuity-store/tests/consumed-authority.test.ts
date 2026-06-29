import os from "node:os";
import path from "node:path";
import fs from "node:fs";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { openDatabase } from "../src/database.js";
import { ContinuityStore } from "../src/store.js";
import { recoverSubject } from "../src/recover.js";
import { evaluateResume } from "../src/resume.js";

const DIGEST = `sha256:${"7".repeat(64)}`;

function makeStore(): ContinuityStore {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ls-consumed-authority-"));
  const db = openDatabase(path.join(root, "continuity.db"));
  return new ContinuityStore(db, path.join(root, "objects"));
}

describe("consumed authority", () => {
  it("requires a new intent before another governance decision", () => {
    const store = makeStore();
    const subject = "consumed-intent";

    const intent = store.persist({
      schema: "ls.continuity.v1",
      object_type: "intent",
      subject_id: subject,
      created_at: "2026-06-29T00:00:00.000Z",
      payload: { action: "send_payment", params_digest: DIGEST }
    });

    const decision = store.persist({
      schema: "ls.continuity.v1",
      object_type: "governance_decision",
      subject_id: subject,
      previous_ref: intent.object_id,
      created_at: "2026-06-29T00:00:01.000Z",
      payload: {
        intent_ref: intent.object_id,
        decision: "allow",
        validity_state: "active",
        resume_posture: "retryable",
        expires_at: null,
        revalidate_if: []
      }
    });

    const outcome = store.persist({
      schema: "ls.continuity.v1",
      object_type: "governance_outcome",
      subject_id: subject,
      previous_ref: decision.object_id,
      created_at: "2026-06-29T00:00:02.000Z",
      payload: {
        decision_ref: decision.object_id,
        status: "executed",
        result_digest: DIGEST,
        side_effect_committed: true
      }
    });

    assert.equal(evaluateResume(recoverSubject(store, subject)).reason, "AUTHORITY_CONSUMED");

    assert.throws(
      () => store.persist({
        schema: "ls.continuity.v1",
        object_type: "governance_decision",
        subject_id: subject,
        previous_ref: outcome.object_id,
        created_at: "2026-06-29T00:00:03.000Z",
        payload: {
          intent_ref: intent.object_id,
          decision: "allow",
          validity_state: "active",
          resume_posture: "retryable",
          expires_at: null,
          revalidate_if: []
        }
      }),
      /DECISION_REQUIRES_NEW_INTENT_AFTER_CONSUMED_OUTCOME/
    );

    const consumedState = recoverSubject(store, subject);
    assert.equal(consumedState?.decision_ref, decision.object_id);
    assert.equal(consumedState?.outcome_ref, outcome.object_id);
    assert.equal(consumedState?.resume_posture, "consumed");
    assert.equal(store.listEvents(subject).length, 3);

    const replacementIntent = store.persist({
      schema: "ls.continuity.v1",
      object_type: "intent",
      subject_id: subject,
      previous_ref: outcome.object_id,
      created_at: "2026-06-29T00:00:04.000Z",
      payload: { action: "send_payment", params_digest: DIGEST }
    });

    assert.doesNotThrow(() => store.persist({
      schema: "ls.continuity.v1",
      object_type: "governance_decision",
      subject_id: subject,
      previous_ref: replacementIntent.object_id,
      created_at: "2026-06-29T00:00:05.000Z",
      payload: {
        intent_ref: replacementIntent.object_id,
        decision: "allow",
        validity_state: "active",
        resume_posture: "retryable",
        expires_at: null,
        revalidate_if: []
      }
    }));

    assert.equal(evaluateResume(recoverSubject(store, subject)).reason, "OK");
  });
});
