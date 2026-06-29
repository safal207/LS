import fs from "node:fs";
import path from "node:path";
import type { DatabaseSync } from "node:sqlite";
import { canonicalBytes } from "./canonicalize.js";
import { sha256Ref } from "./hash.js";
import { envelopeSchema, OBJECT_REF_RE } from "./schema.js";
import type {
  ContinuityEnvelope,
  StoredContinuityObject,
  ContinuationCheckpointPayload,
  GovernanceDecisionPayload,
  GovernanceOutcomePayload,
  ContinuationState,
  IntentPayload
} from "./types.js";

function withoutObjectId<T>(input: ContinuityEnvelope<T>): ContinuityEnvelope<T> {
  const { object_id: _ignored, ...rest } = input;
  return rest;
}

function unique(values: readonly string[]): string[] {
  return [...new Set(values)].sort();
}

/** Local content-addressed continuity store with append-only evidence replay. */
export class ContinuityStore {
  constructor(
    private readonly db: DatabaseSync,
    private readonly objectsDir: string
  ) {
    fs.mkdirSync(objectsDir, { recursive: true });
  }

  /** Persists an immutable object exactly once and updates the rebuildable projection. */
  persist<T extends Record<string, unknown>>(
    input: ContinuityEnvelope<T>
  ): StoredContinuityObject<T> {
    envelopeSchema.parse(input);
    const normalized = withoutObjectId(input);
    const canonical = canonicalBytes(normalized);
    const objectId = sha256Ref(canonical);
    const stored: StoredContinuityObject<T> = { ...normalized, object_id: objectId };

    const filename = this.objectPath(objectId);
    try {
      fs.mkdirSync(path.dirname(filename), { recursive: true });
      fs.writeFileSync(filename, JSON.stringify(stored, null, 2), { flag: "wx" });
    } catch (error) {
      const errno = error as NodeJS.ErrnoException;
      if (errno.code !== "EEXIST") throw error;
      this.assertExistingObjectMatches(filename, objectId, canonical);
    }

    this.db.exec("BEGIN IMMEDIATE");
    try {
      const indexed = this.db.prepare(`SELECT 1 AS present FROM objects WHERE object_id = ?`).get(objectId);
      if (indexed) {
        this.db.exec("COMMIT");
        return stored;
      }

      this.db.prepare(`
        INSERT INTO objects(object_id, object_type, subject_id, canonical_json, created_at)
        VALUES (?, ?, ?, ?, ?)
      `).run(objectId, stored.object_type, stored.subject_id, canonical.toString("utf8"), stored.created_at);

      this.validatePersistReferences(stored as StoredContinuityObject<Record<string, unknown>>);
      this.appendEvent("object_persisted", stored.subject_id, objectId, stored.created_at);
      this.updateProjection(stored as StoredContinuityObject<Record<string, unknown>>);
      this.db.exec("COMMIT");
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }

    return stored;
  }

  /** Loads and revalidates a content-addressed object. */
  load<T = Record<string, unknown>>(objectId: string): StoredContinuityObject<T> {
    if (!OBJECT_REF_RE.test(objectId)) throw new Error("INVALID_OBJECT_REF");
    const filename = this.objectPath(objectId);
    if (!fs.existsSync(filename)) throw new Error("OBJECT_NOT_FOUND");
    const parsed = JSON.parse(fs.readFileSync(filename, "utf8")) as StoredContinuityObject<T>;
    envelopeSchema.parse(parsed);
    const { object_id, ...unsigned } = parsed;
    const recomputed = sha256Ref(canonicalBytes(unsigned));
    if (recomputed !== object_id || object_id !== objectId) {
      throw new Error("OBJECT_HASH_MISMATCH");
    }
    return parsed;
  }

  /** Reads the mutable projection. It is never the source of truth. */
  getCurrentState(subjectId: string): ContinuationState | null {
    const row = this.db.prepare(`SELECT * FROM current_state WHERE subject_id = ?`).get(subjectId) as
      | Record<string, unknown>
      | undefined;
    if (!row) return null;

    return {
      subject_id: row.subject_id as string,
      latest_intent_ref: (row.latest_intent_ref as string | null) ?? null,
      checkpoint_ref: (row.checkpoint_ref as string | null) ?? null,
      decision_ref: (row.decision_ref as string | null) ?? null,
      outcome_ref: (row.outcome_ref as string | null) ?? null,
      decision_state: (row.decision_state as ContinuationState["decision_state"]) ?? null,
      validity_state: row.validity_state as ContinuationState["validity_state"],
      resume_posture: row.resume_posture as ContinuationState["resume_posture"],
      pending_approval_ref: (row.pending_approval_ref as string | null) ?? null,
      expires_at: (row.expires_at as string | null) ?? null,
      revalidate_if: JSON.parse((row.revalidate_if_json as string) ?? "[]") as string[],
      required_checks: JSON.parse((row.required_checks_json as string) ?? "[]") as string[],
      updated_at: row.updated_at as string
    };
  }

  /** Returns ordered evidence events for one subject. */
  listEvents(subjectId: string): Array<Record<string, unknown>> {
    return this.db.prepare(`
      SELECT sequence_number, event_type, subject_id, object_ref, previous_event_hash, event_hash, created_at
      FROM event_log WHERE subject_id = ? ORDER BY sequence_number ASC
    `).all(subjectId) as Array<Record<string, unknown>>;
  }

  /** Executes recovery reads under one SQLite snapshot. */
  withReadSnapshot<T>(callback: () => T): T {
    this.db.exec("BEGIN DEFERRED");
    try {
      const result = callback();
      this.db.exec("COMMIT");
      return result;
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }
  }

  /** Applies one verified evidence object to a deterministic state projection. */
  deriveNextState(
    previous: ContinuationState | null,
    object: StoredContinuityObject<Record<string, unknown>>
  ): ContinuationState {
    const next: ContinuationState = previous
      ? {
          ...previous,
          revalidate_if: [...previous.revalidate_if],
          required_checks: [...previous.required_checks]
        }
      : {
          subject_id: object.subject_id,
          latest_intent_ref: null,
          checkpoint_ref: null,
          decision_ref: null,
          outcome_ref: null,
          decision_state: null,
          validity_state: "active",
          resume_posture: "requires_revalidation",
          pending_approval_ref: null,
          expires_at: null,
          revalidate_if: [],
          required_checks: [],
          updated_at: object.created_at
        };

    if (object.subject_id !== next.subject_id) throw new Error("SUBJECT_MISMATCH");

    if (object.object_type === "intent") {
      next.latest_intent_ref = object.object_id;
      next.checkpoint_ref = null;
      next.decision_ref = null;
      next.outcome_ref = null;
      next.decision_state = null;
      next.validity_state = "active";
      next.resume_posture = "requires_revalidation";
      next.pending_approval_ref = null;
      next.expires_at = null;
      next.revalidate_if = [];
      next.required_checks = ["governance_decision"];
    }

    if (object.object_type === "governance_decision") {
      const payload = object.payload as unknown as GovernanceDecisionPayload;
      if (next.latest_intent_ref !== payload.intent_ref) throw new Error("DECISION_INTENT_NOT_CURRENT");

      const intent = this.load<IntentPayload>(payload.intent_ref);
      if (intent.object_type !== "intent") throw new Error("DECISION_INTENT_TYPE_MISMATCH");
      if (intent.subject_id !== object.subject_id) throw new Error("DECISION_INTENT_SUBJECT_MISMATCH");

      next.decision_ref = object.object_id;
      next.outcome_ref = null;
      next.decision_state = payload.decision;
      next.validity_state = payload.validity_state;
      next.expires_at = payload.expires_at ?? null;
      next.revalidate_if = unique(payload.revalidate_if ?? []);
      next.required_checks = [];
      next.pending_approval_ref = null;

      if (payload.decision === "allow") next.resume_posture = payload.resume_posture;
      else if (payload.decision === "require_approval") {
        next.resume_posture = "pending_approval";
        next.pending_approval_ref = object.object_id;
      } else if (payload.decision === "revise") {
        next.resume_posture = "requires_revalidation";
        next.required_checks = unique([...next.revalidate_if, "revised_decision"]);
      } else {
        next.resume_posture = "non_retryable";
      }
    }

    if (object.object_type === "governance_outcome") {
      const payload = object.payload as unknown as GovernanceOutcomePayload;
      if (payload.decision_ref !== next.decision_ref) throw new Error("OUTCOME_DECISION_MISMATCH");
      const decision = this.load<GovernanceDecisionPayload>(payload.decision_ref);
      if (decision.object_type !== "governance_decision") throw new Error("OUTCOME_DECISION_TYPE_MISMATCH");
      if (decision.subject_id !== object.subject_id) throw new Error("OUTCOME_SUBJECT_MISMATCH");
      if (next.decision_state !== "allow") throw new Error("OUTCOME_WITHOUT_ALLOW");

      next.outcome_ref = object.object_id;
      next.pending_approval_ref = null;
      if (payload.side_effect_committed || payload.status === "executed") {
        next.resume_posture = "consumed";
      } else if (payload.status === "errored") {
        next.resume_posture = "requires_revalidation";
        next.required_checks = unique([...next.required_checks, "retry_safety"]);
      } else {
        next.resume_posture = "non_retryable";
      }
    }

    if (object.object_type === "continuation_checkpoint") {
      const payload = object.payload as unknown as ContinuationCheckpointPayload;
      if (payload.latest_decision_ref !== undefined && payload.latest_decision_ref !== next.decision_ref) {
        throw new Error("CHECKPOINT_DECISION_MISMATCH");
      }
      if (payload.latest_outcome_ref !== undefined && payload.latest_outcome_ref !== next.outcome_ref) {
        throw new Error("CHECKPOINT_OUTCOME_MISMATCH");
      }
      if (payload.pending_approval_ref !== undefined && payload.pending_approval_ref !== next.pending_approval_ref) {
        throw new Error("CHECKPOINT_APPROVAL_MISMATCH");
      }
      if (payload.validity_state !== next.validity_state || payload.resume_posture !== next.resume_posture) {
        throw new Error("CHECKPOINT_AUTHORITY_MISMATCH");
      }

      next.checkpoint_ref = object.object_id;
      next.required_checks = unique([...next.required_checks, ...(payload.required_checks ?? [])]);
    }

    next.updated_at = object.created_at;
    return next;
  }

  private objectPath(objectId: string): string {
    if (!OBJECT_REF_RE.test(objectId)) throw new Error("INVALID_OBJECT_REF");
    const digest = objectId.slice("sha256:".length);
    return path.join(this.objectsDir, digest.slice(0, 2), digest.slice(2, 4), `${digest}.json`);
  }

  private assertExistingObjectMatches(filename: string, objectId: string, canonical: Buffer): void {
    try {
      const existing = JSON.parse(fs.readFileSync(filename, "utf8")) as StoredContinuityObject<Record<string, unknown>>;
      const { object_id: existingId, ...existingUnsigned } = existing;
      if (existingId !== objectId || !canonicalBytes(existingUnsigned).equals(canonical)) {
        throw new Error("CONTENT_ADDRESS_COLLISION");
      }
    } catch (error) {
      if (error instanceof Error && error.message === "CONTENT_ADDRESS_COLLISION") throw error;
      throw new Error("CONTENT_ADDRESS_COLLISION");
    }
  }

  private validatePersistReferences(object: StoredContinuityObject<Record<string, unknown>>): void {
    if (object.object_type !== "governance_decision") return;

    const payload = object.payload as unknown as GovernanceDecisionPayload;
    const indexed = this.db.prepare(`
      SELECT 1 AS present
      FROM event_log AS event
      JOIN objects AS evidence ON evidence.object_id = event.object_ref
      WHERE event.subject_id = ?
        AND event.object_ref = ?
        AND evidence.object_type = 'intent'
        AND evidence.subject_id = ?
      LIMIT 1
    `).get(object.subject_id, payload.intent_ref, object.subject_id);

    if (!indexed) throw new Error("DECISION_INTENT_NOT_INDEXED");

    const latest = this.db.prepare(`
      SELECT event.object_ref
      FROM event_log AS event
      JOIN objects AS evidence ON evidence.object_id = event.object_ref
      WHERE event.subject_id = ? AND evidence.object_type = 'intent'
      ORDER BY event.sequence_number DESC
      LIMIT 1
    `).get(object.subject_id) as { object_ref: string } | undefined;

    if (!latest || latest.object_ref !== payload.intent_ref) {
      throw new Error("DECISION_INTENT_NOT_CURRENT");
    }
  }

  private appendEvent(eventType: string, subjectId: string, objectRef: string, createdAt: string): void {
    const previous = this.db.prepare(`
      SELECT event_hash FROM event_log WHERE subject_id = ? ORDER BY sequence_number DESC LIMIT 1
    `).get(subjectId) as { event_hash: string } | undefined;

    const previousEventHash = previous?.event_hash ?? null;
    const eventBody = {
      event_type: eventType,
      subject_id: subjectId,
      object_ref: objectRef,
      previous_event_hash: previousEventHash,
      created_at: createdAt
    };
    const eventHash = sha256Ref(canonicalBytes(eventBody));

    this.db.prepare(`
      INSERT INTO event_log(event_type, subject_id, object_ref, previous_event_hash, event_hash, created_at)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(eventType, subjectId, objectRef, previousEventHash, eventHash, createdAt);
  }

  private updateProjection(object: StoredContinuityObject<Record<string, unknown>>): void {
    const next = this.deriveNextState(this.getCurrentState(object.subject_id), object);

    this.db.prepare(`
      INSERT INTO current_state(
        subject_id, latest_intent_ref, checkpoint_ref, decision_ref, outcome_ref, decision_state,
        validity_state, resume_posture, pending_approval_ref, expires_at,
        revalidate_if_json, required_checks_json, updated_at
      )
      VALUES (
        @subject_id, @latest_intent_ref, @checkpoint_ref, @decision_ref, @outcome_ref, @decision_state,
        @validity_state, @resume_posture, @pending_approval_ref, @expires_at,
        @revalidate_if_json, @required_checks_json, @updated_at
      )
      ON CONFLICT(subject_id) DO UPDATE SET
        latest_intent_ref = excluded.latest_intent_ref,
        checkpoint_ref = excluded.checkpoint_ref,
        decision_ref = excluded.decision_ref,
        outcome_ref = excluded.outcome_ref,
        decision_state = excluded.decision_state,
        validity_state = excluded.validity_state,
        resume_posture = excluded.resume_posture,
        pending_approval_ref = excluded.pending_approval_ref,
        expires_at = excluded.expires_at,
        revalidate_if_json = excluded.revalidate_if_json,
        required_checks_json = excluded.required_checks_json,
        updated_at = excluded.updated_at
    `).run({
      subject_id: next.subject_id,
      latest_intent_ref: next.latest_intent_ref,
      checkpoint_ref: next.checkpoint_ref,
      decision_ref: next.decision_ref,
      outcome_ref: next.outcome_ref,
      decision_state: next.decision_state,
      validity_state: next.validity_state,
      resume_posture: next.resume_posture,
      pending_approval_ref: next.pending_approval_ref,
      expires_at: next.expires_at,
      revalidate_if_json: JSON.stringify(next.revalidate_if),
      required_checks_json: JSON.stringify(next.required_checks),
      updated_at: next.updated_at
    });
  }
}
