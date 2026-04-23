# -*- coding: utf-8 -*-
"""Golden end-to-end coordination stack scenario tests."""
from __future__ import annotations

try:
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.resonance_agent import ResonanceAgent


_ALLOWED_COORDINATION_STATE_LABELS = {
    "coherent",
    "strained",
    "fragmented",
    "unstable",
    "escalating",
}
_ALLOWED_PLAYBOOK_ALIGNMENT_LABELS = {
    "well_aligned",
    "partially_aligned",
    "weakly_aligned",
    "misaligned",
    "insufficient_context",
}
_ALLOWED_BRIDGE_PLAYBOOK_FIT = {
    "acknowledgment-led",
    "pacing-led",
    "reframing-led",
    "translation-led",
    "stabilization-led",
    "mixed",
    "unknown",
}
_ALLOWED_STABILIZATION_MODES = {
    "crisis_first",
    "high_priority_first",
    "quick_wins_first",
    "observe_and_stage",
    "unknown",
}
_ALLOWED_HARMONIC_INTERVALS = {
    "unison",
    "third",
    "fifth",
    "fourth",
    "seventh",
    "tritone",
    "octave",
    "unknown",
}


def _alignment_report_with_nontrivial_tension() -> dict:
    return {
        "alignment_score": 0.31,
        "tension_score": 0.79,
        "participants": [
            {"participant_id": "product"},
            {"participant_id": "design"},
            {"participant_id": "ops"},
            {"participant_id": "security"},
        ],
        "pairwise_hotspots": [
            {
                "participants": ["product", "design"],
                "alignment": 0.22,
                "tension": 0.88,
                "mismatch_reasons": ["intent_conflict", "why_mismatch"],
            },
            {
                "participants": ["product", "ops"],
                "alignment": 0.28,
                "tension": 0.82,
                "mismatch_reasons": ["need_pressure_conflict", "intent_conflict"],
            },
            {
                "participants": ["design", "security"],
                "alignment": 0.34,
                "tension": 0.76,
                "mismatch_reasons": ["why_mismatch", "background_state_divergence"],
            },
            {
                "participants": ["ops", "security"],
                "alignment": 0.41,
                "tension": 0.69,
                "mismatch_reasons": ["need_pressure_conflict"],
            },
        ],
    }


def _playbook_seed_recommendations() -> list[dict]:
    return [
        {
            "strategy_id": "s_deescalate_bridge",
            "effective_rate": 0.83,
            "support_count": 5,
            "recommended_actions": [
                "Acknowledge tension and name the shared concern",
                "Slow the pace and restore safety before proposing",
                "Reframe winner/loser framing into a shared risk lens",
            ],
        },
        {
            "strategy_id": "s_translate_models",
            "effective_rate": 0.71,
            "support_count": 4,
            "recommended_actions": [
                "Translate assumptions across teams before deciding",
                "Clarify internal causes and constraints",
            ],
        },
    ]


def _adoption_traces() -> list[dict]:
    return [
        {"strategy_id": "s_deescalate_bridge", "adoption_label": "partially_adopted", "adoption_score": 0.63},
        {"strategy_id": "s_translate_models", "adoption_label": "adopted", "adoption_score": 0.74},
    ]


def test_coordination_stack_golden_end_to_end_scenario():
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    item = {
        "text": "Cross-functional launch alignment is breaking down.",
        "_alignment_report": _alignment_report_with_nontrivial_tension(),
    }

    playbook = agent.build_alignment_strategy_playbook(
        item,
        _playbook_seed_recommendations(),
        calibration_summary={"overview": {}},
    )
    multi_party = agent.get_multi_party_alignment_state(item, adoption_traces=_adoption_traces())
    bridge_graph = agent.get_bridge_graph_state(item, multi_party_state=multi_party)
    stabilization_order = agent.get_bridge_stabilization_order(
        item,
        bridge_graph_state=bridge_graph,
        multi_party_state=multi_party,
    )
    snapshot = agent.get_collective_coordination_snapshot(
        item,
        multi_party_state=multi_party,
        bridge_graph_state=bridge_graph,
        bridge_stabilization_order=stabilization_order,
    )
    advisory = agent.get_bridge_playbook_advisory(
        item,
        playbook=playbook,
        bridge_graph_state=bridge_graph,
        bridge_stabilization_order=stabilization_order,
        collective_snapshot=snapshot,
    )
    coordination_summary = agent.get_coordination_advisory_summary(
        item,
        collective_coordination_snapshot=snapshot,
        bridge_stabilization_order=stabilization_order,
        bridge_playbook_advisory=advisory,
    )
    harmonic = agent.get_harmonic_state_summary(
        item,
        collective_coordination_snapshot=snapshot,
        bridge_stabilization_order=stabilization_order,
        bridge_playbook_advisory=advisory,
        coordination_advisory_summary=coordination_summary,
        relational_policy_decision={
            "risk_state": "watch",
            "safety_mode": "evidence_first",
            "requires_human_review": False,
        },
        relational_coherence=0.29,
    )

    # Golden scenario outcomes: coherent chain and stable contract values.
    assert multi_party["state_label"] == "escalating"
    assert snapshot["coordination_state_label"] in _ALLOWED_COORDINATION_STATE_LABELS
    assert snapshot["coordination_state_label"] in {"escalating", "unstable", "fragmented"}

    assert bridge_graph["dominant_bridge_type"] == "stabilization_bridge"
    assert snapshot["dominant_bridge_type"] == "stabilization_bridge"

    assert stabilization_order["dominant_stabilization_mode"] in _ALLOWED_STABILIZATION_MODES
    assert snapshot["dominant_stabilization_mode"] in _ALLOWED_STABILIZATION_MODES

    assert advisory["playbook_alignment_label"] in _ALLOWED_PLAYBOOK_ALIGNMENT_LABELS
    assert advisory["dominant_bridge_playbook_fit"] in _ALLOWED_BRIDGE_PLAYBOOK_FIT

    assert isinstance(advisory, dict)
    assert isinstance(coordination_summary, dict)
    assert isinstance(harmonic, dict)
    assert isinstance(agent.get_bridge_playbook_metrics(), dict)
    assert isinstance(agent.get_harmonic_state_metrics(), dict)

    # Meaningful stabilization + playbook richness + boundedness.
    assert len(bridge_graph["highest_priority_edges"]) >= 1
    assert len(stabilization_order["ordered_edges"]) >= 2
    assert len(playbook.get("steps") or []) >= 2
    assert len(advisory["step_links"]) >= 2

    assert coordination_summary["coordination_advisory_label"] in {"fragile", "blocked"}
    assert harmonic["harmonic_center"] == "stabilization"
    assert harmonic["harmonic_interval_label"] in _ALLOWED_HARMONIC_INTERVALS
    assert harmonic["harmonic_interval_label"] == "tritone"
    assert harmonic["modulation_candidate"] in {"translation", "reframing"}
    assert harmonic["resolution_direction"] in {"deescalate_then_translate", "stabilize_then_reframe"}
    assert harmonic["harmonic_tension"] > harmonic["harmonic_stability"]

    assert len(snapshot["top_bridge_candidates"]) <= 3
    assert len(snapshot["top_stabilization_edges"]) <= 3
    assert len(snapshot["top_risk_parties"]) <= 3
    assert len(advisory["step_links"]) <= 10
    assert len(advisory["top_supported_steps"]) <= 3
    assert len(advisory["top_weak_steps"]) <= 3

    assert isinstance(snapshot["summary_reason"], str) and 0 < len(snapshot["summary_reason"]) <= 140
    assert isinstance(stabilization_order["summary_reason"], str) and 0 < len(stabilization_order["summary_reason"]) <= 140
    assert isinstance(advisory["summary_reason"], str) and 0 < len(advisory["summary_reason"]) <= 140
    assert isinstance(harmonic["harmonic_summary_reason"], str) and 0 < len(harmonic["harmonic_summary_reason"]) <= 140
