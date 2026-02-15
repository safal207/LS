from __future__ import annotations

from typing import Any

# Constants
MAX_TRACE_LENGTH = 200
MAX_NORM_CONFLICTS = 5.0

def normalize_traditions(raw: Any) -> dict[str, float]:
    """
    Normalizes traditions from various input formats (dict, list of dicts)
    into a flat dictionary mapping pattern names to strength scores.
    """
    if isinstance(raw, dict):
        return {str(k): float(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return {
            str(item.get("pattern", f"tradition_{idx}")): float(item.get("strength", 0.0))
            for idx, item in enumerate(raw)
            if isinstance(item, dict)
        }
    return {}
