import os from "node:os";
import path from "node:path";
import fs from "node:fs";
import { DatabaseSync } from "node:sqlite";
import assert from "node:assert/strict";
import { it } from "node:test";
import { openDatabase } from "../src/database.js";

it("backfills latest_intent_ref before consumed-authority triggers are installed", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "ls-database-migration-"));
  const databasePath = path.join(root, "continuity.db");
  const legacy = new DatabaseSync(databasePath);

  try {
    legacy.exec(`
      PRAGMA foreign_keys = ON;

      CREATE TABLE objects (
        object_id TEXT PRIMARY KEY,
        object_type TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        canonical_json TEXT NOT NULL,
        created_at TEXT NOT NULL
      );

      CREATE TABLE event_log (
        sequence_number INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        subject_id TEXT NOT NULL,
        object_ref TEXT NOT NULL REFERENCES objects(object_id),
        previous_event_hash TEXT,
        event_hash TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
      );

      CREATE TABLE current_state (
        subject_id TEXT PRIMARY KEY,
        checkpoint_ref TEXT REFERENCES objects(object_id),
        decision_ref TEXT REFERENCES objects(object_id),
        outcome_ref TEXT REFERENCES objects(object_id),
        decision_state TEXT,
        validity_state TEXT NOT NULL,
        resume_posture TEXT NOT NULL,
        pending_approval_ref TEXT REFERENCES objects(object_id),
        expires_at TEXT,
        revalidate_if_json TEXT NOT NULL DEFAULT '[]',
        required_checks_json TEXT NOT NULL DEFAULT '[]',
        updated_at TEXT NOT NULL
      );

      CREATE TABLE pending_approvals (
        approval_id TEXT PRIMARY KEY,
        subject_id TEXT NOT NULL,
        decision_ref TEXT NOT NULL REFERENCES objects(object_id),
        status TEXT NOT NULL,
        expires_at TEXT,
        continuation_id TEXT
      );
    `);

    const insertObject = legacy.prepare(`
      INSERT INTO objects(object_id, object_type, subject_id, canonical_json, created_at)
      VALUES (?, ?, ?, ?, ?)
    `);

    insertObject.run(
      "intent-1",
      "intent",
      "legacy-subject",
      JSON.stringify({ payload: { action: "send_payment" } }),
      "2026-06-28T00:00:00.000Z"
    );
    insertObject.run(
      "decision-1",
      "governance_decision",
      "legacy-subject",
      JSON.stringify({ payload: { intent_ref: "intent-1" } }),
      "2026-06-28T00:00:01.000Z"
    );
    insertObject.run(
      "outcome-1",
      "governance_outcome",
      "legacy-subject",
      JSON.stringify({ payload: { decision_ref: "decision-1" } }),
      "2026-06-28T00:00:02.000Z"
    );

    legacy.prepare(`
      INSERT INTO event_log(event_type, subject_id, object_ref, previous_event_hash, event_hash, created_at)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(
      "object_persisted",
      "legacy-subject",
      "intent-1",
      null,
      "event-intent-1",
      "2026-06-28T00:00:00.000Z"
    );

    legacy.prepare(`
      INSERT INTO current_state(
        subject_id, checkpoint_ref, decision_ref, outcome_ref, decision_state,
        validity_state, resume_posture, pending_approval_ref, expires_at,
        revalidate_if_json, required_checks_json, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      "legacy-subject",
      null,
      "decision-1",
      "outcome-1",
      "allow",
      "active",
      "consumed",
      null,
      null,
      "[]",
      "[]",
      "2026-06-28T00:00:02.000Z"
    );
  } finally {
    legacy.close();
  }

  const migrated = openDatabase(databasePath);
  try {
    const state = migrated.prepare(`
      SELECT latest_intent_ref FROM current_state WHERE subject_id = ?
    `).get("legacy-subject") as { latest_intent_ref: string | null };

    assert.equal(state.latest_intent_ref, "intent-1");

    assert.throws(
      () => migrated.prepare(`
        INSERT INTO objects(object_id, object_type, subject_id, canonical_json, created_at)
        VALUES (?, ?, ?, ?, ?)
      `).run(
        "decision-2",
        "governance_decision",
        "legacy-subject",
        JSON.stringify({ payload: { intent_ref: "intent-1" } }),
        "2026-06-29T00:00:00.000Z"
      ),
      /DECISION_REQUIRES_NEW_INTENT_AFTER_CONSUMED_OUTCOME/
    );
  } finally {
    migrated.close();
    fs.rmSync(root, { recursive: true, force: true });
  }
});
