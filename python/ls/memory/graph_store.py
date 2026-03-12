from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonGraphStore:
    """Simple JSON persistence for memory graphs."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def save(self, graph_data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(graph_data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"nodes": [], "edges": []}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"nodes": [], "edges": []}
        return {
            "nodes": list(data.get("nodes", [])),
            "edges": list(data.get("edges", [])),
        }
