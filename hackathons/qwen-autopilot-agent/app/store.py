from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any


class ApprovalStore:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or os.getenv("LS_DB_PATH", "/tmp/ls-qwen-approvals.db")
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    assessment_json TEXT NOT NULL,
                    reviewer TEXT,
                    note TEXT,
                    resolved_at TEXT
                )
                """
            )

    def create(self, payload: dict[str, Any], assessment: dict[str, Any]) -> str:
        approval_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO approvals(id, created_at, status, payload_json, assessment_json) VALUES (?, ?, 'PENDING', ?, ?)",
                (approval_id, now, json.dumps(payload), json.dumps(assessment)),
            )
        return approval_id

    def resolve(self, approval_id: str, decision: str, reviewer: str, note: str) -> dict[str, Any] | None:
        status = "APPROVED" if decision == "APPROVE" else "REJECTED"
        resolved_at = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE approvals SET status=?, reviewer=?, note=?, resolved_at=? WHERE id=? AND status='PENDING'",
                (status, reviewer, note, resolved_at, approval_id),
            )
            resolution_applied = cursor.rowcount == 1

        result = self.get(approval_id)
        if result is None:
            return None
        result["resolution_applied"] = resolution_applied
        return result

    def get(self, approval_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "status": row["status"],
            "payload": json.loads(row["payload_json"]),
            "assessment": json.loads(row["assessment_json"]),
            "reviewer": row["reviewer"],
            "note": row["note"],
            "resolved_at": row["resolved_at"],
        }
