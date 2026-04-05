from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sqlite3
import uuid


ALLOWED_MODES = {"read-only", "safe-write", "full-agent"}


class RuntimeValidationError(ValueError):
    """Raised when runtime inputs or state transitions are invalid."""


@dataclass(frozen=True)
class StepRecord:
    id: str
    title: str
    type: str
    needs_approval: bool
    reason: str
    status: str


class TaskManager:
    """Persistent authoritative task runtime backed by SQLite."""

    def __init__(self, db_path: str | Path = ".ls_agent/runtime/runtime.db", artifact_root: str | Path = ".ls_agent/artifacts") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifact_root = Path(artifact_root)
        self.artifact_root.mkdir(parents=True, exist_ok=True)
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
                    prompt TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS steps (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    type TEXT NOT NULL,
                    needs_approval INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    idx INTEGER NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                );

                CREATE TABLE IF NOT EXISTS trace_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    step_id TEXT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    type TEXT NOT NULL,
                    path_or_url TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id)
                );
                """
            )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _task_id() -> str:
        return f"task-{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _artifact_id() -> str:
        return f"artifact-{uuid.uuid4().hex[:8]}"

    def _validate_mode(self, mode: str) -> None:
        if mode not in ALLOWED_MODES:
            raise RuntimeValidationError(f"Unknown mode: {mode}")

    def _assert_task_exists(self, conn: sqlite3.Connection, task_id: str) -> None:
        row = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise RuntimeValidationError(f"Unknown task_id: {task_id}")

    def _assert_step_exists(self, conn: sqlite3.Connection, task_id: str, step_id: str) -> None:
        row = conn.execute(
            "SELECT id FROM steps WHERE id = ? AND task_id = ?",
            (step_id, task_id),
        ).fetchone()
        if row is None:
            raise RuntimeValidationError(f"Unknown step_id: {step_id}")

    def _write_trace(
        self,
        conn: sqlite3.Connection,
        *,
        task_id: str,
        level: str,
        message: str,
        step_id: str | None = None,
    ) -> None:
        conn.execute(
            "INSERT INTO trace_events(task_id, step_id, level, message, created_at) VALUES (?, ?, ?, ?, ?)",
            (task_id, step_id, level, message, self._now_iso()),
        )

    def _update_task_status(self, conn: sqlite3.Connection, task_id: str, status: str, summary: str | None = None) -> None:
        now = self._now_iso()
        conn.execute(
            "UPDATE tasks SET status = ?, summary = COALESCE(?, summary), updated_at = ? WHERE id = ?",
            (status, summary, now, task_id),
        )

    def _serialize_steps(self, conn: sqlite3.Connection, task_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            "SELECT id, title, type, needs_approval, reason, status FROM steps WHERE task_id = ? ORDER BY idx ASC",
            (task_id,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "type": r["type"],
                "status": r["status"],
                "needs_approval": bool(r["needs_approval"]),
                "reason": r["reason"],
            }
            for r in rows
        ]

    def plan_task(self, *, prompt: str, mode: str) -> dict[str, Any]:
        self._validate_mode(mode)
        task_id = self._task_id()
        created_at = self._now_iso()
        step_id = f"{task_id}-step-1"

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tasks(id, prompt, mode, status, summary, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (task_id, prompt, mode, "blocked", None, created_at, created_at),
            )
            conn.execute(
                "INSERT INTO steps(id, task_id, title, type, needs_approval, reason, status, idx) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (step_id, task_id, "Fetch task context", "read", 0, "Need source context before analysis.", "pending", 1),
            )
            self._write_trace(conn, task_id=task_id, step_id=step_id, level="info", message=f"Plan generated for {task_id}")

        return {
            "task_id": task_id,
            "status": "blocked",
            "plan": [
                {
                    "id": step_id,
                    "title": "Fetch task context",
                    "type": "read",
                    "needs_approval": False,
                    "reason": "Need source context before analysis.",
                    "status": "pending",
                }
            ],
            "summary": "Plan generated only.",
        }

    def run_task(self, *, prompt: str, mode: str) -> dict[str, Any]:
        self._validate_mode(mode)
        task_id = self._task_id()
        created_at = self._now_iso()
        step_ids = [f"{task_id}-step-1", f"{task_id}-step-2", f"{task_id}-step-3"]

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tasks(id, prompt, mode, status, summary, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (task_id, prompt, mode, "running", None, created_at, created_at),
            )
            rows = [
                (step_ids[0], task_id, "Read relevant docs", "read", 0, "Collect local context first.", "completed", 1),
                (step_ids[1], task_id, "Draft execution output", "reason", 0, "Prepare bounded advisory output.", "completed", 2),
                (step_ids[2], task_id, "Apply write action", "write", 1, "Write-side effects require explicit approval.", "waiting_approval", 3),
            ]
            conn.executemany(
                "INSERT INTO steps(id, task_id, title, type, needs_approval, reason, status, idx) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            self._write_trace(conn, task_id=task_id, step_id=step_ids[0], level="info", message=f"Running {step_ids[0]}: Read relevant docs")
            self._write_trace(conn, task_id=task_id, step_id=step_ids[1], level="info", message=f"Running {step_ids[1]}: Draft execution output")
            self._write_trace(conn, task_id=task_id, step_id=step_ids[2], level="info", message=f"Approval required for {step_ids[2]}")
            self._update_task_status(conn, task_id, "waiting_approval")

        return {
            "task_id": task_id,
            "status": "waiting_approval",
            "next_action": "approval_required",
            "current_step_id": step_ids[2],
        }

    def resume_task(self, *, task_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            self._assert_task_exists(conn, task_id)
            row = conn.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
            status = row["status"]
            if status == "blocked":
                raise RuntimeValidationError("Cannot resume blocked task without explicit override flow")
            if status == "waiting_approval":
                raise RuntimeValidationError("Cannot resume while waiting approval; use ls_approve or ls_reject")
            self._update_task_status(conn, task_id, "running")
            self._write_trace(conn, task_id=task_id, level="info", message=f"Task {task_id} resumed")
        return {"task_id": task_id, "status": "running"}

    def get_status(self, *, task_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            self._assert_task_exists(conn, task_id)
            task = conn.execute("SELECT id, mode, status, summary FROM tasks WHERE id = ?", (task_id,)).fetchone()
            steps = self._serialize_steps(conn, task_id)
        return {
            "task_id": task["id"],
            "mode": task["mode"],
            "status": task["status"],
            "summary": task["summary"],
            "steps": steps,
        }

    def get_trace(self, *, task_id: str, limit: int = 100) -> dict[str, Any]:
        safe_limit = max(1, min(limit, 500))
        with self._connect() as conn:
            self._assert_task_exists(conn, task_id)
            events = conn.execute(
                "SELECT created_at, level, step_id, message FROM trace_events WHERE task_id = ? ORDER BY id DESC LIMIT ?",
                (task_id, safe_limit),
            ).fetchall()
        serialized = [
            {
                "created_at": e["created_at"],
                "level": e["level"],
                "step_id": e["step_id"],
                "message": e["message"],
            }
            for e in reversed(events)
        ]
        return {"task_id": task_id, "events": serialized}

    def list_artifacts(self, *, task_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            self._assert_task_exists(conn, task_id)
            rows = conn.execute(
                "SELECT id, title, type, path_or_url FROM artifacts WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            ).fetchall()
        artifacts = [dict(row) for row in rows]
        return {"task_id": task_id, "artifacts": artifacts}

    def approve(self, *, task_id: str, step_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            self._assert_task_exists(conn, task_id)
            self._assert_step_exists(conn, task_id, step_id)
            step = conn.execute(
                "SELECT needs_approval, status FROM steps WHERE id = ? AND task_id = ?",
                (step_id, task_id),
            ).fetchone()
            if not step["needs_approval"]:
                raise RuntimeValidationError("Approval is only valid for approval-gated steps")
            if step["status"] not in {"waiting_approval", "pending"}:
                raise RuntimeValidationError("Step is not waiting for approval")

            conn.execute("UPDATE steps SET status = 'completed' WHERE id = ?", (step_id,))
            self._write_trace(conn, task_id=task_id, step_id=step_id, level="info", message=f"Approved {step_id}")

            report_path = self.artifact_root / task_id / "report.md"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            task_prompt = conn.execute("SELECT prompt FROM tasks WHERE id = ?", (task_id,)).fetchone()["prompt"]
            report_path.write_text(f"# Task report\n\nTask: {task_id}\n\nPrompt: {task_prompt}\n", encoding="utf-8")
            conn.execute(
                "INSERT INTO artifacts(id, task_id, title, type, path_or_url, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (self._artifact_id(), task_id, "Task report", "report", str(report_path), self._now_iso()),
            )
            summary = "Task completed with approved side effects; artifact created."
            self._update_task_status(conn, task_id, "completed", summary=summary)
            self._write_trace(conn, task_id=task_id, step_id=step_id, level="info", message=f"Task {task_id} completed")
        return {"task_id": task_id, "step_id": step_id, "status": "approved"}

    def reject(self, *, task_id: str, step_id: str, reason: str) -> dict[str, Any]:
        with self._connect() as conn:
            self._assert_task_exists(conn, task_id)
            self._assert_step_exists(conn, task_id, step_id)
            step = conn.execute(
                "SELECT needs_approval FROM steps WHERE id = ? AND task_id = ?",
                (step_id, task_id),
            ).fetchone()
            if not step["needs_approval"]:
                raise RuntimeValidationError("Rejection is only valid for approval-gated steps")

            conn.execute("UPDATE steps SET status = 'rejected' WHERE id = ?", (step_id,))
            self._update_task_status(conn, task_id, "blocked", summary=f"Task blocked after rejection: {reason}")
            self._write_trace(conn, task_id=task_id, step_id=step_id, level="warning", message=f"Rejected {step_id}: {reason}")
        return {"task_id": task_id, "step_id": step_id, "status": "rejected"}
