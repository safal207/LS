from __future__ import annotations

from .types import GovernanceDecision, HallucinationRisk


def decision_for(rupture_type: str, hallucination_risk: HallucinationRisk) -> GovernanceDecision:
    """Map rupture type and risk to the next safe action."""

    if rupture_type == "missing_pr_context" and hallucination_risk == "high":
        return "hold_until_context"
    if rupture_type == "session_type_mismatch":
        return "repair_before_continue"
    if rupture_type == "memory_write_without_consent":
        return "human_review"
    if rupture_type == "action_without_causal_parent":
        return "human_review"
    if rupture_type == "none":
        return "continue"
    return "validate_context"
