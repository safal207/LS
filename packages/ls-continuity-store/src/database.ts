import { DatabaseSync } from "node:sqlite";

/** Opens the local SQLite store with WAL and evidence-reference constraints enabled. */
export function openDatabase(path: string): DatabaseSync {
  const db = new DatabaseSync(path);
  db.exec("PRAGMA journal_mode = WAL");
  db.exec("PRAGMA foreign_keys = ON");
  db.exec(`
    CREATE TABLE IF NOT EXISTS objects (
      object_id TEXT PRIMARY KEY,
      object_type TEXT NOT NULL,
      subject_id TEXT NOT NULL,
      canonical_json TEXT NOT NULL,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS event_log (
      sequence_number INTEGER PRIMARY KEY AUTOINCREMENT,
      event_type TEXT NOT NULL,
      subject_id TEXT NOT NULL,
      object_ref TEXT NOT NULL REFERENCES objects(object_id),
      previous_event_hash TEXT,
      event_hash TEXT NOT NULL UNIQUE,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS current_state (
      subject_id TEXT PRIMARY KEY,
      latest_intent_ref TEXT REFERENCES objects(object_id),
      checkpoint_ref TEXT REFERENCES objects(object_id),
      decision_ref TEXT REFERENCES objects(object_id),
      outcome_ref TEXT REFERENCES objects(object_id),
      decision_state TEXT CHECK (decision_state IN ('allow', 'deny', 'require_approval', 'revise') OR decision_state IS NULL),
      validity_state TEXT NOT NULL CHECK (validity_state IN ('active', 'expired', 'superseded', 'invalidated')),
      resume_posture TEXT NOT NULL CHECK (resume_posture IN ('retryable', 'requires_revalidation', 'consumed', 'non_retryable', 'pending_approval')),
      pending_approval_ref TEXT REFERENCES objects(object_id),
      expires_at TEXT,
      revalidate_if_json TEXT NOT NULL DEFAULT '[]',
      required_checks_json TEXT NOT NULL DEFAULT '[]',
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS pending_approvals (
      approval_id TEXT PRIMARY KEY,
      subject_id TEXT NOT NULL,
      decision_ref TEXT NOT NULL REFERENCES objects(object_id),
      status TEXT NOT NULL,
      expires_at TEXT,
      continuation_id TEXT
    );

    CREATE TRIGGER IF NOT EXISTS reject_reauthorization_after_consumed_outcome
    BEFORE INSERT ON objects
    WHEN NEW.object_type = 'governance_decision'
      AND EXISTS (
        SELECT 1
        FROM current_state
        WHERE subject_id = NEW.subject_id
          AND latest_intent_ref = json_extract(NEW.canonical_json, '$.payload.intent_ref')
          AND outcome_ref IS NOT NULL
          AND resume_posture = 'consumed'
      )
    BEGIN
      SELECT RAISE(ABORT, 'DECISION_REQUIRES_NEW_INTENT_AFTER_CONSUMED_OUTCOME');
    END;
  `);

  const stateColumns = db.prepare("PRAGMA table_info(current_state)").all() as Array<{ name: string }>;
  if (!stateColumns.some((column) => column.name === "latest_intent_ref")) {
    db.exec("ALTER TABLE current_state ADD COLUMN latest_intent_ref TEXT REFERENCES objects(object_id)");
  }

  return db;
}
