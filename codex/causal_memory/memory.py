from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import with_file_lock


class MemoryService:
    """Persistent storage for Amygdala long-term state using JSON and file lock."""

    def __init__(self, user_id: str = "default", base_dir: str | Path = "~/.ghostgpt/memory") -> None:
        self.user_id = user_id or "default"
        self.base_dir = Path(base_dir).expanduser()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.base_dir / f"user_{self.user_id}.json"

    def load(self) -> dict[str, Any]:
        try:
            if not self.path.exists():
                return {}
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, PermissionError, OSError):
            return {}

    def save(self, data: dict[str, Any]) -> None:
        def _write() -> None:
            safe_payload = dict(data)
            safe_payload["user_id"] = self.user_id
            self.path.write_text(json.dumps(safe_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        with_file_lock(str(self.path), _write)
