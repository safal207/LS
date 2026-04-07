from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .contribution_api import ContributionLedger, ContributionRecord
from .reputation_engine import ReputationEngine


def quality_score_from_council_outcome(outcome: Any) -> float:
    path_quality = max(0.0, min(1.0, float(getattr(outcome, "path_quality", 0.0) or 0.0)))
    operator_feedback = max(
        0.0,
        min(1.0, float(getattr(outcome, "operator_feedback_score", 0.0) or 0.0)),
    )
    receiver_resonance = max(
        0.0,
        min(1.0, float(getattr(outcome, "receiver_resonance_score", 0.0) or 0.0)),
    )
    success = 1.0 if bool(getattr(outcome, "success", False)) else 0.0
    return round(
        (0.35 * path_quality)
        + (0.25 * operator_feedback)
        + (0.25 * receiver_resonance)
        + (0.15 * success),
        4,
    )


def build_contribution_records_from_council_ledger(ledger: Any) -> list[ContributionRecord]:
    proposal_id = str(getattr(ledger, "cycle_id", "") or "")
    if not proposal_id:
        return []

    contribution_breakdown = {
        entry.model_id: entry
        for entry in getattr(getattr(ledger, "attribution", None), "contribution_breakdown", []) or []
    }

    records: list[ContributionRecord] = []
    for participant in getattr(ledger, "participants", []) or []:
        breakdown = contribution_breakdown.get(getattr(participant, "model_id", ""))
        total_contribution = float(
            getattr(breakdown, "total_contribution_score", 0.0) if breakdown is not None else 0.0
        )
        receiver_resonance = float(
            getattr(breakdown, "receiver_resonance", getattr(ledger.outcome, "receiver_resonance_score", 0.0))
            if breakdown is not None
            else getattr(ledger.outcome, "receiver_resonance_score", 0.0)
        )
        records.append(
            ContributionRecord(
                proposal_id=proposal_id,
                agent_id=str(getattr(participant, "model_id", "")),
                contribution_type=str(getattr(participant, "model_type", "unknown")),
                impact=round(total_contribution, 4),
                resonance=round(max(0.0, min(1.0, receiver_resonance)), 4),
                accuracy=round(
                    max(
                        0.0,
                        min(
                            1.0,
                            float(
                                getattr(breakdown, "outcome_lift", 0.0)
                                if breakdown is not None
                                else 0.0
                            ),
                        ),
                    ),
                    4,
                ),
            )
        )
    return records


def apply_council_ledger_to_cel(
    ledger: Any,
    *,
    contribution_ledger: ContributionLedger | None = None,
    reputation_engine: ReputationEngine | None = None,
) -> dict[str, Any]:
    contribution_ledger = contribution_ledger or ContributionLedger()
    reputation_engine = reputation_engine or ReputationEngine()

    records = build_contribution_records_from_council_ledger(ledger)
    for record in records:
        contribution_ledger.add(record)

    quality_score = quality_score_from_council_outcome(getattr(ledger, "outcome", None))
    breakdown = getattr(getattr(ledger, "attribution", None), "contribution_breakdown", []) or []
    breakdown_by_model = {entry.model_id: entry for entry in breakdown}

    reputation_updates: list[dict[str, Any]] = []
    for participant in getattr(ledger, "participants", []) or []:
        model_id = str(getattr(participant, "model_id", ""))
        contribution_score = float(
            getattr(breakdown_by_model.get(model_id), "total_contribution_score", 0.0)
            if model_id
            else 0.0
        )
        updated = reputation_engine.update(
            model_id,
            quality_score=quality_score,
            contribution_score=contribution_score,
        )
        reputation_updates.append(asdict(updated))

    return {
        "proposal_id": str(getattr(ledger, "cycle_id", "") or ""),
        "quality_score": quality_score,
        "contribution_records": [asdict(record) for record in records],
        "reputation_updates": reputation_updates,
    }
