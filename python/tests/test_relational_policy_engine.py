from __future__ import annotations

from modules.agent.relational_policy_engine import (
    compute_relational_coherence,
    evaluate_relational_policy,
)


def test_policy_engine_uses_evidence_first_without_relational_context() -> None:
    payload = evaluate_relational_policy(None)

    assert payload["risk_state"] == "watch"
    assert payload["approval_posture"] == "evidence_check"
    assert payload["route_strategy"] == "rerun_and_clarify"
    assert payload["safety_mode"] == "evidence_first"
    assert payload["policy_engine_version"] == "relational-policy-v1"
    assert "missing_relational_context" in payload["rule_hits"]


def test_policy_engine_repairs_on_low_relation_safety() -> None:
    payload = evaluate_relational_policy(
        {
            "tension_score": 0.81,
            "alignment_score": 0.24,
            "relation_safety_score": 0.23,
            "recommended_mode": "decompress_and_repair",
        }
    )

    assert payload["risk_state"] == "repair"
    assert payload["approval_posture"] == "hold_and_repair"
    assert payload["route_strategy"] == "repair_then_reroute"
    assert payload["safety_mode"] == "repair_first"
    assert "repair_from_tension_or_low_safety" in payload["rule_hits"]


def test_policy_engine_freezes_on_repeated_bad_memory_pattern() -> None:
    payload = evaluate_relational_policy(
        {
            "tension_score": 0.78,
            "alignment_score": 0.24,
            "relation_safety_score": 0.23,
            "recommended_mode": "decompress_and_repair",
        },
        memory_context={
            "pattern_key": "repair:tension:low",
            "match_count": 3,
            "incident_count": 1,
            "reject_count": 1,
            "approve_count": 0,
            "policy_adjusted": False,
        },
    )

    assert payload["risk_state"] == "escalate"
    assert payload["approval_posture"] == "human_escalation"
    assert payload["route_strategy"] == "freeze_and_escalate"
    assert payload["safety_mode"] == "freeze"
    assert payload["memory_context"]["policy_adjusted"] is True
    assert "memory_freeze_override" in payload["rule_hits"]



def test_compute_relational_coherence_prefers_low_tension_high_alignment() -> None:
    strong = compute_relational_coherence(tension_score=0.1, alignment_score=0.9)
    weak = compute_relational_coherence(tension_score=0.9, alignment_score=0.1)

    assert strong > weak
    assert 0.0 <= strong <= 1.0
    assert 0.0 <= weak <= 1.0


def test_policy_engine_degrades_safe_mode_when_coherence_is_low() -> None:
    payload = evaluate_relational_policy(
        {
            "tension_score": 0.35,
            "alignment_score": 0.7,
            "relation_safety_score": 0.68,
            "relational_coherence": 0.3,
            "recommended_mode": "collaborative_progress",
        }
    )

    assert payload["risk_state"] == "watch"
    assert payload["approval_posture"] == "evidence_check"
    assert payload["route_strategy"] == "validate_current_route"
    assert "low_relational_coherence" in payload["rule_hits"]


def test_policy_engine_escalates_when_coherence_is_critical() -> None:
    payload = evaluate_relational_policy(
        {
            "tension_score": 0.55,
            "alignment_score": 0.52,
            "relation_safety_score": 0.48,
            "relational_coherence": 0.15,
            "recommended_mode": "observe_and_clarify",
        }
    )

    assert payload["risk_state"] == "escalate"
    assert payload["approval_posture"] == "human_escalation"
    assert payload["route_strategy"] == "freeze_and_escalate"
    assert "critical_relational_coherence" in payload["rule_hits"]
    assert payload["relational_coherence"] == 0.15
