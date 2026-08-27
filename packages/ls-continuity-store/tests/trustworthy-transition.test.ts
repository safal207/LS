import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import type { DatabaseSync } from "node:sqlite";
import { afterEach, describe, it } from "node:test";
import { canonicalBytes } from "../src/canonicalize.js";
import { openDatabase } from "../src/database.js";
import { sha256Ref } from "../src/hash.js";
import { ContinuityStore } from "../src/store.js";
import {
  assessSnapshotChain,
  assessSnapshotSequence,
  computeEvidenceSetDigest,
  createTransitionSnapshotEnvelope,
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

interface TamperingFixtureCase {
  case_id: string;
  source_case_id: string;
  mutation: {
    dimension: keyof TransitionContinuitySnapshotInput["dimensions"];
    value: string;
  };
  expected_error: string;
}

const fixture = JSON.parse(fs.readFileSync(FIXTURE_PATH, "utf8")) as {
  profile: string;
  cases: FixtureCase[];
  tampering_cases: TamperingFixtureCase[];
};

interface StorageResource {
  root: string;
  databases: Set<DatabaseSync>;
}

const storageResources = new Set<StorageResource>();

afterEach(() => {
  for (const resource of storageResources) {
    for (const database of resource.databases) {
      try {
        database.close();
      } catch {
        // The test may already have closed this handle to simulate restart.
      }
    }
    fs.rmSync(resource.root, { recursive: true, force: true });
  }
  storageResources.clear();
});

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
  const resource = { root, databases: new Set<DatabaseSync>([db]) };
  storageResources.add(resource);
  const store = new ContinuityStore(db, objectsPath);
  const reopen = () => {
    const reopened = openDatabase(databasePath);
    resource.databases.add(reopened);
    return reopened;
  };
  return { root, databasePath, objectsPath, db, store, reopen };
}

function objectPath(objectsPath: string, objectRef: string): string {
  const digest = objectRef.slice("sha256:".length);
  return path.join(objectsPath, digest.slice(0, 2), digest.slice(2, 4), `${digest}.json`);
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
    assert.equal(fixture.tampering_cases.length, 1);
  });

  for (const caseData of fixture.cases) {
    it(`replays ${caseData.case_id} after storage restart`, () => {
      const { objectsPath, db, store, reopen } = storageFixture();
      const { snapshotInput, requestOverride } = materializeCase(caseData);
      const stored = persistTransitionSnapshot(
        store,
        snapshotInput,
        "2030-01-01T00:00:00.000Z"
      );
      const request = buildRequest(stored, requestOverride);
      db.close();

      const reopenedDb = reopen();
      const reopenedStore = new ContinuityStore(reopenedDb, objectsPath);
      const recovered = reopenedStore.load<typeof stored.payload>(stored.object_id);
      const first = evaluateTransitionResume(reopenedStore, recovered.object_id, request);
      const second = evaluateTransitionResume(reopenedStore, recovered.object_id, request);

      assert.deepEqual(second, first);
      assert.equal(first.allowed, caseData.expected.allowed);
      assert.equal(first.posture, caseData.expected.posture);
      assert.equal(first.reason, caseData.expected.reason);
      assert.equal(first.snapshot_ref, stored.object_id);
      assert.deepEqual(first.dimensions, stored.payload.dimensions);
      reopenedDb.close();
    });
  }

  for (const tamperingCase of fixture.tampering_cases) {
    it(`rejects ${tamperingCase.case_id} after storage restart`, () => {
      const source = fixture.cases.find(
        (caseData) => caseData.case_id === tamperingCase.source_case_id
      );
      assert.ok(source);
      const { objectsPath, db, store, reopen } = storageFixture();
      const { snapshotInput } = materializeCase(source);
      const stored = persistTransitionSnapshot(
        store,
        snapshotInput,
        "2030-01-01T00:00:00.000Z"
      );
      const filename = objectPath(objectsPath, stored.object_id);
      const tampered = JSON.parse(fs.readFileSync(filename, "utf8")) as {
        payload: { dimensions: Record<string, unknown> };
      };
      tampered.payload.dimensions[tamperingCase.mutation.dimension] =
        tamperingCase.mutation.value;
      fs.writeFileSync(filename, JSON.stringify(tampered, null, 2));
      db.close();

      const reopenedDb = reopen();
      const reopenedStore = new ContinuityStore(reopenedDb, objectsPath);
      assert.throws(
        () => reopenedStore.load(stored.object_id),
        new RegExp(tamperingCase.expected_error)
      );
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
    assert.deepEqual(assessSnapshotSequence([previous, current]), {
      valid: true,
      reason_codes: ["OK"]
    });
    db.close();
  });

  it("blocks live evaluation of a non-latest snapshot but keeps it reportable", () => {
    const { store } = storageFixture();
    const { snapshotInput } = materializeCase(fixture.cases[0]);
    const initial = persistTransitionSnapshot(
      store,
      snapshotInput,
      "2030-01-01T00:00:00.000Z"
    );
    const deniedInput = structuredClone(snapshotInput);
    deniedInput.dimensions.authority = "DENIED";
    const latest = persistTransitionSnapshot(
      store,
      deniedInput,
      "2030-01-01T00:01:00.000Z",
      initial.object_id
    );
    const request = buildRequest(initial, {
      operation: "resume_side_effect",
      now: "2030-01-01T00:10:00.000Z"
    });

    const stale = evaluateTransitionResume(store, initial.object_id, request);
    assert.equal(stale.allowed, false);
    assert.equal(stale.reason, "SNAPSHOT_NOT_LATEST");

    const current = evaluateTransitionResume(store, latest.object_id, request);
    assert.equal(current.allowed, false);
    assert.equal(current.reason, "AUTHORITY_DENIED");

    const report = evaluateTransitionResume(store, initial.object_id, {
      ...request,
      operation: "report_only"
    });
    assert.equal(report.allowed, true);
    assert.equal(report.reason, "HISTORICAL_REPORT_ONLY");
  });

  it("keeps terminal authority sticky across intermediate snapshots", () => {
    const { store } = storageFixture();
    const { snapshotInput } = materializeCase(fixture.cases[0]);
    snapshotInput.dimensions.authority = "DENIED";
    const denied = persistTransitionSnapshot(
      store,
      snapshotInput,
      "2030-01-01T00:00:00.000Z"
    );
    const pendingInput = structuredClone(snapshotInput);
    pendingInput.dimensions.authority = "PENDING";
    const pending = persistTransitionSnapshot(
      store,
      pendingInput,
      "2030-01-01T00:01:00.000Z",
      denied.object_id
    );
    const validInput = structuredClone(snapshotInput);
    validInput.dimensions.authority = "VALID";
    const invalidReopen = persistTransitionSnapshot(
      store,
      validInput,
      "2030-01-01T00:02:00.000Z",
      pending.object_id
    );

    assert.equal(assessSnapshotChain(denied, pending).valid, true);
    assert.equal(assessSnapshotChain(pending, invalidReopen).valid, true);
    assert.deepEqual(assessSnapshotSequence([denied, pending, invalidReopen]), {
      valid: false,
      reason_codes: ["AUTHORITY_REOPENED_WITHOUT_REAUTHORIZATION"]
    });

    const request = buildRequest(invalidReopen, {
      operation: "resume_side_effect",
      now: "2030-01-01T00:10:00.000Z"
    });
    const result = evaluateTransitionResume(
      store,
      invalidReopen.object_id,
      request
    );
    assert.equal(result.allowed, false);
    assert.equal(result.reason, "SNAPSHOT_CHAIN_INVALID");
  });

  it("rejects rollback from an observed error to unobserved execution", () => {
    const { store } = storageFixture();
    const { snapshotInput } = materializeCase(fixture.cases[0]);
    snapshotInput.dimensions.execution = "OBSERVED_ERRORED";
    snapshotInput.retry = {
      retryable_after_error: true,
      idempotency_key: "retry-errored-transition"
    };
    const errored = persistTransitionSnapshot(
      store,
      snapshotInput,
      "2030-01-01T00:00:00.000Z"
    );
    const rolledBackInput = structuredClone(snapshotInput);
    rolledBackInput.dimensions.execution = "NOT_OBSERVED";
    const rolledBack = persistTransitionSnapshot(
      store,
      rolledBackInput,
      "2030-01-01T00:01:00.000Z",
      errored.object_id
    );

    assert.deepEqual(assessSnapshotSequence([errored, rolledBack]), {
      valid: false,
      reason_codes: ["EXECUTION_ROLLBACK"]
    });
    const result = evaluateTransitionResume(
      store,
      rolledBack.object_id,
      buildRequest(rolledBack, {
        operation: "resume_side_effect",
        now: "2030-01-01T00:02:00.000Z"
      })
    );
    assert.equal(result.allowed, false);
    assert.equal(result.reason, "SNAPSHOT_CHAIN_INVALID");
  });

  it("rejects expiry removal or extension without a new authorization epoch", () => {
    for (const [name, nextExpiry] of [
      ["removed", null],
      ["extended", "2030-01-01T02:00:00.000Z"]
    ] as const) {
      const { store } = storageFixture();
      const { snapshotInput } = materializeCase(fixture.cases[0]);
      snapshotInput.authority_expires_at = "2030-01-01T01:00:00.000Z";
      const previous = persistTransitionSnapshot(
        store,
        snapshotInput,
        "2030-01-01T00:00:00.000Z"
      );
      const changedInput = structuredClone(snapshotInput);
      changedInput.authority_expires_at = nextExpiry;
      const current = persistTransitionSnapshot(
        store,
        changedInput,
        "2030-01-01T00:01:00.000Z",
        previous.object_id
      );

      assert.deepEqual(
        assessSnapshotChain(previous, current),
        {
          valid: false,
          reason_codes: ["AUTHORITY_REOPENED_WITHOUT_REAUTHORIZATION"]
        },
        name
      );
    }
  });

  it("rejects null mandatory digests at creation and stored verification", () => {
    const fields = [
      "action_identity_digest",
      "binding_digest",
      "context_digest"
    ] as const;
    for (const field of fields) {
      const { store } = storageFixture();
      const { snapshotInput } = materializeCase(fixture.cases[0]);
      const invalidInput = structuredClone(snapshotInput);
      (invalidInput as unknown as Record<string, unknown>)[field] = null;
      assert.throws(
        () =>
          createTransitionSnapshotEnvelope(
            invalidInput,
            "2030-01-01T00:00:00.000Z"
          ),
        new RegExp(`${field.toUpperCase()}_INVALID`)
      );

      const envelope = createTransitionSnapshotEnvelope(
        snapshotInput,
        "2030-01-01T00:00:00.000Z"
      );
      (envelope.payload as unknown as Record<string, unknown>)[field] = null;
      const stored = store.persist(envelope);
      assert.throws(
        () => assessSnapshotSequence([stored]),
        new RegExp(`${field.toUpperCase()}_INVALID`)
      );
    }
  });

  it("rejects malformed persisted dimensions before resume evaluation", () => {
    const { store } = storageFixture();
    const { snapshotInput } = materializeCase(fixture.cases[0]);
    const envelope = createTransitionSnapshotEnvelope(
      snapshotInput,
      "2030-01-01T00:00:00.000Z"
    );
    (envelope.payload.dimensions as unknown as Record<string, unknown>).authority =
      "STALE";
    const stored = store.persist(envelope);
    const request = buildRequest(stored, {
      operation: "resume_side_effect",
      now: "2030-01-01T00:10:00.000Z"
    });

    assert.throws(
      () => evaluateTransitionResume(store, stored.object_id, request),
      /AUTHORITY_INVALID/
    );
  });

  it("rejects an empty authority expiry before persistence", () => {
    const { store } = storageFixture();
    const { snapshotInput } = materializeCase(fixture.cases[0]);
    snapshotInput.authority_expires_at = "";
    assert.throws(
      () =>
        persistTransitionSnapshot(
          store,
          snapshotInput,
          "2030-01-01T00:00:00.000Z"
        ),
      /AUTHORITY_EXPIRES_AT_INVALID/
    );
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
