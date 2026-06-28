import fs from "node:fs";
import path from "node:path";
import type { DatabaseSync } from "node:sqlite";
import { canonicalBytes } from "./canonicalize.js";
import { sha256Ref } from "./hash.js";
import { envelopeSchema } from "./schema.js";
import type {
  ContinuityEnvelope,
  StoredContinuityObject,
  ContinuationCheckpointPayload,
  GovernanceDecisionPayload,
  GovernanceOutcomePayload,
  ContinuationState
} from "./types.js";

function withoutObjectId<T>(input: ContinuityEnvelope<T>): ContinuityEnvelope<T> {
  const { object_id: _ignored, ...rest } = input;
  return rest;
}

export class ContinuityStore {
  constructor(
    private readonly db: DatabaseSync,
    private readonly objectsDir: string
  ) {
    fs.mkdirSync(objectsDir, { recursive: true });
  }

  persist<T extends Record<string, unknown>>(
    input: ContinuityEnvelope<T>
  ): StoredContinuityObject<T> {
    envelopeSchema.parse(input);
    const normalized = withoutObjectId(input);
    const canonical = canonicalBytes(normalized);
    const objectId = sha256Ref(canonical);
    const stored: StoredContinuityObject<T> = { ...normalized, object_id: objectId };

    const filename = this.objectPath(objectId);
    const storedJson = JSON.stringify(stored, null, 2);
    if (fs.existsSync(filename)) {
      const existing = fs.readFileSync(filename, "utf8");
      if (existing !== storedJson) {
        throw new Error("CONTENT_ADDRESS_COLLISION");
      }
    } else {
      fs.mkdirSync(path.dirname(filename), { recursive: true });
      fs.writeFileSync(filename, storedJson, { flag: "wx" });
    }

    this.db.exec("BEGIN IMMEDIATE");
    try {
      this.db.prepare(`
        INSERT OR IGNORE INTO objects(object_id, object_type, subject_id, canonical_json, created_at)
        VALUES (?, ?, ?, ?, ?)
      `).run(objectId, stored.object_type, stored.subject_id, canonical.toString("utf8"), stored.created_at);

      this.appendEvent("object_persisted", stored.subject_id, objectId, stored.created_at);
      this.updateProjection(stored);
      this.db.exec("COMMIT");
    } catch (error) {
      this.db.exec("ROLLBACK");
      throw error;
    }

    return stored;
  }

  load<T = Record<string, unknown>>(objectId: string): StoredContinuityObject<T> {
    const filename = this.objectPath(objectId);
    if (!fs.existsSync(filename)) throw new Error("OBJECT_NOT_FOUND");
    const parsed = JSON.parse(fs.readFileSync(filename, "utf8")) as StoredContinuityObject<T>;
    const { object_id, ...unsigned } = parsed;
    const recomputed = sha256Ref(canonicalBytes(unsigned));
    if (recomputed !== object_id || object_id !== objectId) {
      throw new Error("OBJECT_HASH_MISMATCH");
    }
    return parsed;
  }

  getCurrentState(subjectId: string): ContinuationState | null {
    const row = this.db.prepare(`SELECT * FROM current_state WHERE subject_id = ?`).get(subjectId) as ContinuationState | undefined;
    return row ? { ...row } : null;
  }

  listEvents(subjectId: string): Array<Record<string, unknown>> {
    return this.db.prepare(`
      SELECT sequence_number, event_type, subject_id, object_ref, previous_event_hash, event_hash, created_at
      FROM event_log WHERE subject_id = ? ORDER BY sequence_number ASC
    `).all(subjectId) as Array<Record<string, unknown>>;
  }

  private objectPath(objectId: string): string {
    const digest = objectId.replace(/^sha256:/, "");
    return path.join(this.objectsDir, digest.slice(0, 2), digest.slice(2, 4), `${digest}.json`);
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
      INSERT OR IGNORE INTO event_log(event_type, subject_id, object_ref, previous_event_hash, event_hash, created_at)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(eventType, subjectId, objectRef, previousEventHash, eventHash, createdAt);
  }

  private updateProjection(object: StoredContinuityObject<Record<string, unknown>>): void {
    const previous = this.getCurrentState(object.subject_id);
    const next: ContinuationState = previous ?? {
      subject_id: object.subject_id,
      checkpoint_ref: null,
      decision_ref: null,
      outcome_ref: null,
      validity_state: "active",
      resume_posture: "requires_revalidation",
      pending_approval_ref: null,
      updated_at: object.created_at
    };

    if (object.object_type === "governance_decision") {
      const payload = object.payload as unknown as GovernanceDecisionPayload;
      next.decision_ref = object.object_id;
      next.validity_state = payload.validity_state;
      next.resume_posture = payload.resume_posture;
      next.pending_approval_ref = payload.decision === "require_approval" ? object.object_id : null;
    }

    if (object.object_type === "governance_outcome") {
      const payload = object.payload as unknown as GovernanceOutcomePayload;
      next.outcome_ref = object.object_id;
      if (payload.side_effect_committed || payload.status === "executed") {
        next.resume_posture = "consumed";
      } else if (payload.status === "errored") {
        next.resume_posture = "requires_revalidation";
      }
    }

    if (object.object_type === "continuation_checkpoint") {
      const payload = object.payload as unknown as ContinuationCheckpointPayload;
      next.checkpoint_ref = object.object_id;
      next.decision_ref = payload.latest_decision_ref ?? next.decision_ref;
      next.outcome_ref = payload.latest_outcome_ref ?? next.outcome_ref;
      next.pending_approval_ref = payload.pending_approval_ref ?? null;
      next.validity_state = payload.validity_state;
      next.resume_posture = payload.resume_posture;
    }

    next.updated_at = object.created_at;

    this.db.prepare(`
      INSERT INTO current_state(subject_id, checkpoint_ref, decision_ref, outcome_ref, validity_state, resume_posture, pending_approval_ref, updated_at)
      VALUES (@subject_id, @checkpoint_ref, @decision_ref, @outcome_ref, @validity_state, @resume_posture, @pending_approval_ref, @updated_at)
      ON CONFLICT(subject_id) DO UPDATE SET
        checkpoint_ref = excluded.checkpoint_ref,
        decision_ref = excluded.decision_ref,
        outcome_ref = excluded.outcome_ref,
        validity_state = excluded.validity_state,
        resume_posture = excluded.resume_posture,
        pending_approval_ref = excluded.pending_approval_ref,
        updated_at = excluded.updated_at
    `).run({
      subject_id: next.subject_id,
      checkpoint_ref: next.checkpoint_ref,
      decision_ref: next.decision_ref,
      outcome_ref: next.outcome_ref,
      validity_state: next.validity_state,
      resume_posture: next.resume_posture,
      pending_approval_ref: next.pending_approval_ref,
      updated_at: next.updated_at
    });
  }
}
