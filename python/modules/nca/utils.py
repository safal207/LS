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

def evaluate_identity_compatibility(
    identity_snapshot: dict[str, Any],
    target: dict[str, Any],
    target_type: str = "intent"
) -> float:
    """
    Shared logic for evaluating compatibility between identity core snapshot
    and a target intent or strategy.

    Args:
        identity_snapshot: Dictionary representation of IdentityCore state.
        target: Dictionary containing intent or strategy data.
        target_type: "intent" or "strategy" to select appropriate logic branches.

    Returns:
        float: Compatibility score [0.0, 1.0].
    """
    mode = str(target.get("desired_mode" if target_type == "intent" else "mode", "balanced")).lower()
    priority = float(target.get("priority" if target_type == "intent" else "strength", 0.5))

    # Access identity fields from snapshot
    core_traits = dict(identity_snapshot.get("core_traits", {}))
    drift_resistance = float(identity_snapshot.get("drift_resistance", 0.7))
    agency_level = float(identity_snapshot.get("agency_level", 0.45))
    identity_integrity = float(identity_snapshot.get("identity_integrity", 0.85))

    consistency = float(core_traits.get("consistency", 0.6))
    adaptability = float(core_traits.get("adaptability", 0.6))
    cooperation = float(core_traits.get("cooperation", 0.6))
    curiosity = float(core_traits.get("curiosity", 0.5))

    mode_fit = 0.6
    if mode == "stabilize":
        mode_fit = 0.5 * consistency + 0.5 * drift_resistance
    elif mode == "explore":
        if target_type == "strategy":
             mode_fit = 0.55 * adaptability + 0.45 * agency_level
        else:
             mode_fit = 0.55 * curiosity + 0.45 * adaptability
    elif mode == "balanced":
        if target_type == "strategy":
            mode_fit = 0.4 * consistency + 0.3 * adaptability + 0.3 * identity_integrity
        else:
            mode_fit = 0.4 * consistency + 0.3 * adaptability + 0.3 * cooperation

    score = 0.0
    if target_type == "intent":
        intent_type = str(target.get("type", "progress")).lower()
        intentpreferenceprofile = dict(identity_snapshot.get("intentpreferenceprofile", {}))
        preferred = float(intentpreferenceprofile.get(intent_type, 0.6))
        intent_resistance = float(identity_snapshot.get("intent_resistance", 0.55))
        resistance_penalty = intent_resistance * max(0.0, priority - agency_level)

        score = (0.4 * preferred) + (0.4 * mode_fit) + (0.2 * identity_integrity) - (0.2 * resistance_penalty)

    elif target_type == "strategy":
        selfdirectionpreference = dict(identity_snapshot.get("selfdirectionpreference", {}))
        preference = float(selfdirectionpreference.get(mode, 0.6))
        alignment = float(target.get("alignment", 0.5))
        autonomy_resistance = float(identity_snapshot.get("autonomy_resistance", 0.45))
        resistance_penalty = autonomy_resistance * max(0.0, priority - agency_level)

        score = (0.35 * preference) + (0.3 * alignment) + (0.2 * mode_fit) + (0.15 * identity_integrity) - (0.2 * resistance_penalty)

    return max(0.0, min(1.0, score))
