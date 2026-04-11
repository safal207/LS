from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from modules.graph.models import RelationalEdge, ResonanceKnowledgeUnit


POLICY_ENGINE_VERSION = "relational-policy-v1"

# Minimum resonance score for two units to warrant an automatic edge suggestion.
_EDGE_RESONANCE_THRESHOLD = 0.6


def suggest_edge_from_resonance(
    unit_a: ResonanceKnowledgeUnit,
    unit_b: ResonanceKnowledgeUnit,
) -> Optional[RelationalEdge]:
    """Suggest a RelationalEdge between two units based on their resonance signals.

    Returns a ``RelationalEdge`` pointing from *unit_a* to *unit_b* when both
    units have sufficient resonance scores, or ``None`` when the signal is too
    weak.  The caller is responsible for persisting the edge via
    ``MemoryGraphStore.store_relational_edge()``.

    Relation type heuristic:
    - Both intents match → ``reinforces``
    - High alignment on both, different intents → ``specializes``
    - One unit has a much higher score → ``generalizes`` (stronger → weaker)
    - Default fallback → ``reinforces``
    """
    score_a = float(unit_a.resonance_score or 0.0)
    score_b = float(unit_b.resonance_score or 0.0)

    if score_a < _EDGE_RESONANCE_THRESHOLD or score_b < _EDGE_RESONANCE_THRESHOLD:
        return None

    intent_a = str(unit_a.intent or "").lower().strip()
    intent_b = str(unit_b.intent or "").lower().strip()
    align_a = float(unit_a.alignment_score or 0.0)
    align_b = float(unit_b.alignment_score or 0.0)

    if intent_a and intent_b and intent_a == intent_b:
        relation_type = "reinforces"
    elif align_a >= 0.55 and align_b >= 0.55 and intent_a != intent_b:
        relation_type = "specializes"
    elif abs(score_a - score_b) >= 0.2:
        relation_type = "generalizes"
    else:
        relation_type = "reinforces"

    strength = round(min(score_a, score_b), 4)
    return RelationalEdge(
        target_unit_id=unit_b.unit_id,
        relation_type=relation_type,
        strength=strength,
    )


@dataclass
class RelationalPolicyDecision:
    risk_state: str
    suggested_operator_action: str
    approval_posture: str
    route_strategy: str
    safety_mode: str
    requires_human_review: bool
    rerun_required: bool
    memory_context: dict[str, Any] | None = None
    policy_engine_version: str = POLICY_ENGINE_VERSION
    rule_hits: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["rule_hits"] = list(self.rule_hits or [])
        return payload


def evaluate_relational_policy(
    relational: dict[str, Any] | None,
    *,
    memory_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not relational:
        return RelationalPolicyDecision(
            risk_state="watch",
            suggested_operator_action="Request another cycle before approving.",
            approval_posture="evidence_check",
            route_strategy="rerun_and_clarify",
            safety_mode="evidence_first",
            requires_human_review=False,
            rerun_required=True,
            memory_context=memory_context,
            rule_hits=["missing_relational_context"],
        ).to_dict()

    tension_score = float(relational.get("tension_score", 0.0) or 0.0)
    alignment_score = float(relational.get("alignment_score", 0.0) or 0.0)
    relation_safety_score = float(relational.get("relation_safety_score", 0.0) or 0.0)
    recommended_mode = str(relational.get("recommended_mode") or "observe_and_clarify")
    rule_hits: list[str] = []

    if recommended_mode == "decompress_and_repair" or relation_safety_score < 0.3:
        risk_state = "repair"
        action = "Pause approval, reduce tension, and rerun the council after repair."
        approval_posture = "hold_and_repair"
        route_strategy = "repair_then_reroute"
        safety_mode = "repair_first"
        requires_human_review = False
        rerun_required = True
        rule_hits.append("repair_from_tension_or_low_safety")
    elif recommended_mode == "validate_before_solve" or tension_score >= 0.6:
        risk_state = "watch"
        action = "Validate intent and evidence before approving this council outcome."
        approval_posture = "evidence_check"
        route_strategy = "validate_current_route"
        safety_mode = "evidence_first"
        requires_human_review = False
        rerun_required = False
        rule_hits.append("watch_from_validation_bias")
    elif recommended_mode == "collaborative_progress" and alignment_score >= 0.55:
        risk_state = "safe"
        action = "Safe to continue with normal operator review."
        approval_posture = "normal_review"
        route_strategy = "continue_current_route"
        safety_mode = "normal"
        requires_human_review = False
        rerun_required = False
        rule_hits.append("normal_from_high_alignment")
    else:
        risk_state = "escalate" if relation_safety_score < 0.15 else "watch"
        action = (
            "Escalate to a human reviewer before approval."
            if risk_state == "escalate"
            else "Observe the next cycle and clarify ambiguous signals before approval."
        )
        approval_posture = "human_escalation" if risk_state == "escalate" else "evidence_check"
        route_strategy = "freeze_and_escalate" if risk_state == "escalate" else "rerun_and_clarify"
        safety_mode = "human_first" if risk_state == "escalate" else "evidence_first"
        requires_human_review = risk_state == "escalate"
        rerun_required = risk_state != "escalate"
        rule_hits.append("fallback_relational_policy")

    policy_adjusted = False
    if memory_context and int(memory_context.get("match_count") or 0) >= 2:
        repeated_failures = int(memory_context.get("incident_count") or 0) + int(memory_context.get("reject_count") or 0)
        if repeated_failures >= 2 and risk_state in {"watch", "repair"}:
            risk_state = "escalate"
            action = "Escalate to a human reviewer: similar prior relational patterns led to incidents or rejection."
            approval_posture = "human_escalation"
            route_strategy = "freeze_and_escalate"
            safety_mode = "freeze"
            requires_human_review = True
            rerun_required = False
            policy_adjusted = True
            rule_hits.append("memory_freeze_override")
    if memory_context is not None:
        memory_context = {**memory_context, "policy_adjusted": policy_adjusted}

    return RelationalPolicyDecision(
        risk_state=risk_state,
        suggested_operator_action=action,
        approval_posture=approval_posture,
        route_strategy=route_strategy,
        safety_mode=safety_mode,
        requires_human_review=requires_human_review,
        rerun_required=rerun_required,
        memory_context=memory_context,
        rule_hits=rule_hits,
    ).to_dict()
