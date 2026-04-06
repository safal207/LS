from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    summary TEXT
                );
                CREATE TABLE IF NOT EXISTS steps (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    type TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    needs_approval INTEGER NOT NULL DEFAULT 0,
                    inputs_json TEXT NOT NULL,
                    outputs_json TEXT NOT NULL,
                    started_at TEXT,
                    ended_at TEXT
                );
                CREATE TABLE IF NOT EXISTS tool_calls (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    result_summary TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    path_or_url TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    step_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    payload_preview TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS task_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    step_id TEXT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def insert(self, table: str, payload: dict[str, Any]) -> None:
        keys = ", ".join(payload)
        placeholders = ", ".join([":" + k for k in payload])
        with self._connect() as conn:
            conn.execute(
                f"INSERT INTO {table} ({keys}) VALUES ({placeholders})",
                payload,
            )

    def update(self, table: str, where_key: str, where_value: str, **fields: Any) -> None:
        assignments = ", ".join([f"{key} = :{key}" for key in fields])
        fields["where_value"] = where_value
        with self._connect() as conn:
            conn.execute(
                f"UPDATE {table} SET {assignments} WHERE {where_key} = :where_value",
                fields,
            )

    def fetch_one(self, query: str, **params: Any) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def fetch_all(self, query: str, **params: Any) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]


def to_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False)


def from_json(raw: str) -> dict[str, Any]:
    return json.loads(raw) if raw else {}
