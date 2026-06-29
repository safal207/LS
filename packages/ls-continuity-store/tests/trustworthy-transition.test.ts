import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { canonicalBytes } from "../src/canonicalize.js";
import { openDatabase } from "../src/database.js";
import { sha256Ref } from "../src/hash.js";
import { ContinuityStore } from "../src/store.js";
import {
  assessSnapshotChain,
  computeEvidenceSetDigest,
  evaluateTransitionResume,
  persistTransitionSnapshot,
  type TransitionContinuitySnapshotInput,
  type TransitionResumeRequest
} from "../src/trustworthy-transition.js";

const FIXTURE_PATH = path.join(
  process.cwd(),
  "tests/fixtures/trustworthy-transition-continuity-v0.1.json"
);

interface FixtureCase {
  case_id: string;
  snapshot: TransitionContinuitySnapshotInput;
  request: Partial<TransitionResumeRequest> & {
    operation: TransitionResumeRequest["operation"];
    now: string;
  };
  expected: {
    allowed: boolean;
    posture: string;
    reason: string;
  };
}

const fixture = JSON.parse(fs.readFileSync(FIXTURE_PATH, "utf8")) as {
  profile: string;
  cases: FixtureCase[];
};

function ref(label: string): string {
  return sha256Ref(canonicalBytes({ fixture_ref: label }));
}

function replaceRefs<T>(value: T): T {
  if (typeof value === "string" && value.startsWith("$REF:")) {
    return ref(value.slice("$REF:".length)) as T;
  }
  if (Array.isArray(value)) return value.map((item) => replaceRefs(item)) as T;
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, replaceRefs(item)])
    ) as T;
  }
  return value;
}

function storageFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ls-transition-continuity-"));
  const databasePath = path.join(root, "continuity.db");
  const objectsPath = path.join(root, "objects");
  const db = openDatabase(databasePath);
  const store = new ContinuityStore(db, objectsPath);
  return { root, databasePath, objectsPath, db, store };
}

function materializeCase(caseData: FixtureCase) {
  const snapshotInput = replaceRefs(structuredClone(caseData.snapshot));
  const requestOverride = replaceRefs(structuredClone(caseData.request));
  return { snapshotInput, requestOverride };
}

function buildRequest(
  snapshot: ReturnType<typeof persistTransitionSnapshot>,
  override: FixtureCase["request"]
): TransitionResumeRequest {
  return {
    transition_id: override.transition_id ?? snapshot.payload.transition_id,
    subject_id: override.subject_id ?? snapshot.payload.subject_id,
    action_identity_digest:
      override.action_identity_digest ?? snapshot.payload.action_identity_digest,
    binding_digest: override.binding_digest ?? snapshot.payload.binding_digest,
    operation: override.operation,
    current_evidence_set_digest:
      override.current_evidence_set_digest ?? snapshot.payload.evidence_set_digest,
    current_context_digest:
      override.current_context_digest ?? snapshot.payload.context_digest,
    now: override.now,
    idempotency_key: override.idempotency_key ?? null
  };
}

describe("trustworthy-transition continuity adapter", () => {
  it("publishes the expected profile fixture", () => {
    assert.equal(fixture.profile, "org.ls.trustworthy-transition-continuity.v0.1");
    assert.equal(fixture.cases.length, 10);
  });

  for (const caseData of fixture.cases) {
    it(`replays ${caseData.case_id} after storage restart`, () => {
      const { databasePath, objectsPath, db, store } = storageFixture();
      const { snapshotInput, requestOverride } = materializeCase(caseData);
      const stored = persistTransitionSnapshot(
        store,
        snapshotInput,
        "2030-01-01T00:00:00.000Z"
      );
      const request = buildRequest(stored, requestOverride);
      db.close();

      const reopenedDb = openDatabase(databasePath);
      const reopenedStore = new ContinuityStore(reopenedDb, objectsPath);
      const recovered = reopenedStore.load<typeof stored.payload>(stored.object_id);
      const first = evaluateTransitionResume(recovered, request);
      const second = evaluateTransitionResume(recovered, request);

      assert.deepEqual(second, first);
      assert.equal(first.allowed, caseData.expected.allowed);
      assert.equal(first.posture, caseData.expected.posture);
      assert.equal(first.reason, caseData.expected.reason);
      assert.equal(first.snapshot_ref, stored.object_id);
      assert.deepEqual(first.dimensions, stored.payload.dimensions);
      reopenedDb.close();
    });
  }

  it("does not let a stale historical snapshot reopen a committed side effect", () => {
    const { db, store } = storageFixture();
    const authorizationRef = ref("chain-auth-1");
    const base = persistTransitionSnapshot(
      store,
      {
        transition_id: "chain-001",
        subject_id: "agent:deploy",
        action_identity_digest: ref("chain-action-1"),
        binding_digest: ref("chain-binding-1"),
        record_refs: {
          authorization_ref: authorizationRef,
          observation_refs: [ref("chain-observation-1")],
          response_integrity_ref: ref("chain-integrity-1"),
          causal_audit_ref: ref("chain-causal-1")
        },
        dimensions: {
          authority: "CONSUMED",
          execution: "OBSERVED_EXECUTED",
          response_integrity: "VERIFIED",
          causal_validity: "VALID"
        },
        side_effect_committed: true,
        context_digest: ref("chain-context-1")
      },
      "2030-01-01T00:00:00.000Z"
    );

    const reopened = persistTransitionSnapshot(
      store,
      {
        transition_id: "chain-001",
        subject_id: "agent:deploy",
        action_identity_digest: ref("chain-action-1"),
        binding_digest: ref("chain-binding-1"),
        record_refs: {
          authorization_ref: authorizationRef,
          observation_refs: [],
          response_integrity_ref: null,
          causal_audit_ref: ref("chain-causal-2")
        },
        dimensions: {
          authority: "VALID",
          execution: "NOT_OBSERVED",
          response_integrity: "NOT_EVALUATED",
          causal_validity: "VALID"
        },
        side_effect_committed: false,
        context_digest: ref("chain-context-1")
      },
      "2030-01-01T00:01:00.000Z",
      base.object_id
    );

    const assessment = assessSnapshotChain(base, reopened);
    assert.equal(assessment.valid, false);
    assert.deepEqual(
      new Set(assessment.reason_codes),
      new Set([
        "OBSERVATION_ROLLBACK",
        "SIDE_EFFECT_ROLLBACK",
        "EXECUTION_ROLLBACK",
        "AUTHORITY_REOPENED_WITHOUT_REAUTHORIZATION"
      ])
    );
    db.close();
  });

  it("accepts an explicit new authorization epoch without erasing observations", () => {
    const { db, store } = storageFixture();
    const previousAuthorization = ref("reauth-old");
    const newAuthorization = ref("reauth-new");
    const observation = ref("reauth-observation");
    const common = {
      transition_id: "chain-reauth",
      subject_id: "agent:deploy",
      action_identity_digest: ref("reauth-action"),
      binding_digest: ref("reauth-binding")
    };

    const previous = persistTransitionSnapshot(
      store,
      {
        ...common,
        record_refs: {
          authorization_ref: previousAuthorization,
          observation_refs: [observation],
          response_integrity_ref: ref("reauth-integrity-old"),
          causal_audit_ref: ref("reauth-causal-old")
        },
        dimensions: {
          authority: "EXPIRED",
          execution: "OBSERVED_BLOCKED",
          response_integrity: "VERIFIED",
          causal_validity: "VALID"
        },
        side_effect_committed: false,
        context_digest: ref("reauth-context")
      },
      "2030-01-01T00:00:00.000Z"
    );

    const current = persistTransitionSnapshot(
      store,
      {
        ...common,
        record_refs: {
          authorization_ref: newAuthorization,
          observation_refs: [observation],
          response_integrity_ref: ref("reauth-integrity-new"),
          causal_audit_ref: ref("reauth-causal-new")
        },
        dimensions: {
          authority: "VALID",
          execution: "OBSERVED_BLOCKED",
          response_integrity: "VERIFIED",
          causal_validity: "VALID"
        },
        side_effect_committed: false,
        context_digest: ref("reauth-context"),
        reauthorization_ref: newAuthorization
      },
      "2030-01-01T00:01:00.000Z",
      previous.object_id
    );

    assert.deepEqual(assessSnapshotChain(previous, current), {
      valid: true,
      reason_codes: ["OK"]
    });
    db.close();
  });

  it("binds evidence-set digest to identity, arguments, and all record refs", () => {
    const input = replaceRefs(
      structuredClone(fixture.cases[0].snapshot)
    ) as TransitionContinuitySnapshotInput;
    const first = computeEvidenceSetDigest(input);
    const second = computeEvidenceSetDigest({
      ...input,
      record_refs: {
        ...input.record_refs,
        observation_refs: [ref("new-observation")]
      }
    });
    assert.notEqual(first, second);
  });
});
