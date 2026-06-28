import { DatabaseSync } from "node:sqlite";

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
      object_ref TEXT NOT NULL,
      previous_event_hash TEXT,
      event_hash TEXT NOT NULL UNIQUE,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS current_state (
      subject_id TEXT PRIMARY KEY,
      checkpoint_ref TEXT,
      decision_ref TEXT,
      outcome_ref TEXT,
      validity_state TEXT NOT NULL,
      resume_posture TEXT NOT NULL,
      pending_approval_ref TEXT,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS pending_approvals (
      approval_id TEXT PRIMARY KEY,
      subject_id TEXT NOT NULL,
      decision_ref TEXT NOT NULL,
      status TEXT NOT NULL,
      expires_at TEXT,
      continuation_id TEXT
    );
  `);
  return db;
}
