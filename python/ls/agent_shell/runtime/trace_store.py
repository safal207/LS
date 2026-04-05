from __future__ import annotations

from datetime import datetime, timezone

from ls.agent_shell.storage.sqlite_store import SQLiteStore


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TraceStore:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def log(self, task_id: str, message: str, level: str = "info", step_id: str | None = None) -> None:
        self.store.insert(
            "task_logs",
            {
                "task_id": task_id,
                "step_id": step_id,
                "level": level,
                "message": message,
                "created_at": utc_now(),
            },
        )

    def list_logs(self, task_id: str) -> list[dict]:
        return self.store.fetch_all(
            "SELECT step_id, level, message, created_at FROM task_logs WHERE task_id=:task_id ORDER BY id ASC",
            task_id=task_id,
        )
