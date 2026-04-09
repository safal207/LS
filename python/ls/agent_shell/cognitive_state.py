from __future__ import annotations

import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
        safe_top_k = max(1, int(top_k or 1))
        safe_threshold = float(min_resonance_score)
        units = self._runtime_resonance_snapshot(
            top_k=safe_top_k,
            min_resonance_score=safe_threshold,
        )
        if units is None:
            units = self._file_resonance_snapshot(
                top_k=safe_top_k,
                min_resonance_score=safe_threshold,
            )
        return {
            "resource": "resonance/snapshot",
            "top_k": safe_top_k,
            "min_resonance_score": safe_threshold,
            "items": units,
            "last_updated": _utc_now(),
        }

    def _runtime_resonance_snapshot(
        self,
        *,
        top_k: int,
        min_resonance_score: float,
    ) -> list[dict[str, Any]] | None:
        if not hasattr(self._task_manager, "get_resonance_snapshot"):
            return None
        try:
            rows = self._task_manager.get_resonance_snapshot(
                top_k=top_k,
                min_resonance_score=min_resonance_score,
            )
        except Exception:
            logger.debug("Runtime resonance snapshot failed", exc_info=True)
            return None

        payload: list[dict[str, Any]] = []
        for row in rows or []:
            if hasattr(row, "to_dict"):
                payload.append(dict(row.to_dict()))
            elif isinstance(row, dict):
                payload.append(dict(row))
            else:
                payload.append({"value": row})
        return payload

    def _file_resonance_snapshot(
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
                try:
                    payload = dict(json.loads(row))
                except Exception:
                    logger.debug("Skipping malformed resonance JSONL row")
                    continue
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
            try:
                raw = self._task_manager.get_omni_last_insight()
                insight = dict(raw) if raw else None
            except Exception:
                logger.debug("Runtime omni insight lookup failed", exc_info=True)

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
