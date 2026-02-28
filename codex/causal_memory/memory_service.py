from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MemoryService:
    """Simple per-user storage for affective Amygdala state."""

    def __init__(self, *, user_id: str = "default", base_dir: Path | None = None) -> None:
        self.user_id = user_id or "default"
        root = base_dir or (Path.home() / ".ghostgpt" / "memory")
        self.base_dir = root
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.base_dir / f"user_{self.user_id}.json"

    def load(self) -> dict[str, Any]:
        if not self.file_path.exists():
            return {}
        try:
            return json.loads(self.file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, payload: dict[str, Any]) -> None:
        safe_payload = dict(payload)
        safe_payload["user_id"] = self.user_id
        self.file_path.write_text(json.dumps(safe_payload, ensure_ascii=False, indent=2), encoding="utf-8")
