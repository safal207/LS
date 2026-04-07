from __future__ import annotations

from typing import Any


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def network_effect_bonus(
    *,
    verified_given: float,
    verified_received: float,
    total_tasks_last_24h: float,
) -> float:
    total = max(float(total_tasks_last_24h), 1.0)
    bonus = (0.08 * (float(verified_given) / total)) + (0.07 * (float(verified_received) / total))
    return round(min(0.15, max(0.0, bonus)), 4)


def merit_score_from_council_ledger(
    ledger: Any,
    *,
    quality_score: float,
    contribution_score: float,
    trust_multiplier: float = 1.0,
    total_tasks_last_24h: float = 1.0,
) -> dict[str, float]:
    outcome = getattr(ledger, "outcome", None)
    participant_count = len(getattr(ledger, "participants", []) or [])

    speed_score = clamp01(1.0 - (max((getattr(outcome, "operator_intervention_required", False) and 1) or 0, 0) * 0.2))
    reliability_score = clamp01(
        (0.6 * (1.0 if bool(getattr(outcome, "success", False)) else 0.0))
        + (0.4 * (0.0 if bool(getattr(outcome, "drift_detected", False)) else 1.0))
    )
    alignment_score = clamp01(
        (0.55 * clamp01(float(getattr(outcome, "receiver_resonance_score", 0.0) or 0.0)))
        + (0.45 * clamp01(float(getattr(outcome, "path_quality", 0.0) or 0.0)))
    )
    verified_given = max(participant_count - 1, 0)
    verified_received = 1.0 if bool(getattr(outcome, "success", False)) else 0.0
    bonus = network_effect_bonus(
        verified_given=verified_given,
        verified_received=verified_received,
        total_tasks_last_24h=total_tasks_last_24h,
    )

    base_score = (
        0.32 * clamp01(quality_score)
        + 0.28 * speed_score
        + 0.18 * reliability_score
        + 0.12 * clamp01(contribution_score)
        + 0.10 * alignment_score
    )
    merit_score = round(base_score * max(float(trust_multiplier), 0.0) * (1.0 + bonus), 4)

    return {
        "quality_score": round(clamp01(quality_score), 4),
        "speed_score": round(speed_score, 4),
        "reliability_score": round(reliability_score, 4),
        "contribution_score": round(clamp01(contribution_score), 4),
        "alignment_score": round(alignment_score, 4),
        "network_effect_bonus": bonus,
        "trust_multiplier": round(max(float(trust_multiplier), 0.0), 4),
        "merit_score": merit_score,
        "verified_given": float(verified_given),
        "verified_received": float(verified_received),
    }


def build_merit_updates_from_council_ledger(
    ledger: Any,
    *,
    quality_score: float,
    total_tasks_last_24h: float = 1.0,
) -> list[dict[str, float | str]]:
    contribution_breakdown = getattr(getattr(ledger, "attribution", None), "contribution_breakdown", []) or []
    by_model = {entry.model_id: entry for entry in contribution_breakdown}

    updates: list[dict[str, float | str]] = []
    for participant in getattr(ledger, "participants", []) or []:
        model_id = str(getattr(participant, "model_id", ""))
        contribution_score = float(
            getattr(by_model.get(model_id), "total_contribution_score", 0.0) if model_id else 0.0
        )
        trust_multiplier = 1.0 + (0.1 * clamp01(float(getattr(participant, "confidence", 0.0) or 0.0)))
        merit = merit_score_from_council_ledger(
            ledger,
            quality_score=quality_score,
            contribution_score=contribution_score,
            trust_multiplier=trust_multiplier,
            total_tasks_last_24h=total_tasks_last_24h,
        )
        updates.append({"model_id": model_id, **merit})
    return updates
