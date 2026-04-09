from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CognitiveStateBridge:
    """Read-only aggregation over LS cognitive state for MCP exposure."""

    def __init__(self, *, task_manager: Any) -> None:
        self._store_path = Path(
            os.environ.get("GRAPH_MEMORY_STORE_PATH", "data/graph_memory/cases.jsonl")
        )
        self._task_manager = task_manager

    def get_resonance_snapshot(
        self,
        *,
        top_k: int = 10,
        min_resonance_score: float = 0.3,
    ) -> dict[str, Any]:
        units = self._load_resonance_snapshot(
            top_k=max(1, int(top_k or 1)),
            min_resonance_score=float(min_resonance_score),
        )
        return {
            "resource": "resonance/snapshot",
            "top_k": max(1, int(top_k or 1)),
            "min_resonance_score": float(min_resonance_score),
            "items": units,
            "last_updated": _utc_now(),
        }

    def _load_resonance_snapshot(
        self,
        *,
        top_k: int,
        min_resonance_score: float,
    ) -> list[dict[str, Any]]:
        path = self._store_path.with_name("resonance_units.jsonl")
        if not path.exists():
            return []
        items: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                row = line.strip()
                if not row:
                    continue
                payload = dict(json.loads(row))
                if float(payload.get("resonance_score", 0.0) or 0.0) <= min_resonance_score:
                    continue
                items.append(payload)
        items.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
        return items[:top_k]

    def get_alignment_current(self) -> dict[str, Any]:
        if hasattr(self._task_manager, "get_alignment_current"):
            payload = dict(self._task_manager.get_alignment_current())
        else:
            payload = {
                "alignment_state": "unavailable",
                "outcomes": [],
                "softening_detected": False,
                "reason": "Alignment provider is not bound in the current runtime.",
            }

        payload["resource"] = "alignment/current"
        payload.setdefault("last_updated", _utc_now())
        return payload

    def get_omni_last_insight(self) -> dict[str, Any]:
        enabled = str(os.environ.get("QWEN_OMNI_ENABLED", "0")).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        if not enabled:
            return {
                "resource": "omni/last-insight",
                "enabled": False,
                "insight": None,
                "reason": "QWEN_OMNI_ENABLED is off",
                "last_updated": _utc_now(),
            }

        insight: dict[str, Any] | None = None
        if hasattr(self._task_manager, "get_omni_last_insight"):
            raw = self._task_manager.get_omni_last_insight()
            insight = dict(raw) if raw else None

        return {
            "resource": "omni/last-insight",
            "enabled": True,
            "insight": insight,
            "last_updated": _utc_now(),
        }

    def get_cognitive_state(
        self,
        *,
        top_k: int = 10,
        min_resonance_score: float = 0.3,
    ) -> dict[str, Any]:
        return {
            "resonance": self.get_resonance_snapshot(
                top_k=top_k,
                min_resonance_score=min_resonance_score,
            ),
            "alignment": self.get_alignment_current(),
            "omni": self.get_omni_last_insight(),
            "last_updated": _utc_now(),
        }
