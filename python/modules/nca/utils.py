from __future__ import annotations

from typing import Any

# Constants
MAX_TRACE_LENGTH = 200
MAX_NORM_CONFLICTS = 5.0

def normalize_traditions(raw: Any) -> dict[str, float]:
    """
    Normalizes traditions from various input formats (dict, list of dicts)
    into a flat dictionary mapping pattern names to strength scores.
    Handles non-numeric values gracefully.
    """
    if isinstance(raw, dict):
        result = {}
        for k, v in raw.items():
            try:
                result[str(k)] = float(v)
            except (ValueError, TypeError):
                continue
        return result
    if isinstance(raw, list):
        result = {}
        for idx, item in enumerate(raw):
            if isinstance(item, dict):
                pattern = str(item.get("pattern", f"tradition_{idx}"))
                try:
                    strength = float(item.get("strength", 0.0))
                    result[pattern] = strength
                except (ValueError, TypeError):
                    continue
        return result
    return {}

def get_norm_conflicts(obj: Any) -> list[dict[str, Any]]:
    """
    Retrieves norm conflicts from an object (typically CultureEngine),
    handling different attribute naming conventions (conflicts property vs norm_conflicts field).
    """
    if hasattr(obj, "conflicts"):
        # If it's a property, access it directly
        return list(obj.conflicts)
    # Fallback to direct field access
    return list(getattr(obj, "norm_conflicts", getattr(obj, "normconflicts", [])))
