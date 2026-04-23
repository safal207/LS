# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy

try:
    from agent.harmonic_state_model import (
        HarmonicStateMetrics,
        build_harmonic_state_summary,
    )
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.harmonic_state_model import (  # type: ignore[no-redef]
        HarmonicStateMetrics,
        build_harmonic_state_summary,
    )
    from modules.agent.resonance_agent import ResonanceAgent  # type: ignore[no-redef]


_ALLOWED_CENTERS = {
    "coherence",
    "stabilization",
    "translation",
    "reframing",
    "exploration",
    "defense",
    "repair",
    "insufficient_context",
}
_ALLOWED_INTERVALS = {
    "unison",
    "third",
    "fifth",
    "fourth",
    "seventh",
    "tritone",
    "octave",
    "unknown",
}
_ALLOWED_RESOLUTION = {
    "hold_course",
    "stabilize_then_continue",
    "deescalate_then_translate",
    "reframe_then_align",
    "repair_then_resume",
    "gather_context",
    "observe_and_stage",
    "translate_then_decide",
    "stabilize_then_reframe",
    "unknown",
}
_ALLOWED_MODULATION = {
    "none",
    "coherence",
    "stabilization",
    "translation",
    "reframing",
    "exploration",
    "defense",
    "repair",
    "unknown",
}


def _scenario_inputs() -> tuple[dict, dict, dict, dict, dict, float]:
    snapshot = {
        "coordination_state_label": "escalating",
        "coordination_risk": 0.86,
        "dominant_bridge_type": "stabilization_bridge",
        "group_fragmentation_level": "high",
    }
    order = {
        "ordered_edges": [
            {
                "stabilization_label": "urgent_deescalation",
                "stabilization_score": 0.91,
            }
        ]
    }
    advisory = {
        "playbook_alignment_label": "partially_aligned",
        "playbook_alignment_score": 0.48,
        "dominant_bridge_playbook_fit": "translation-led",
    }
    summary = {
        "coordination_advisory_label": "fragile",
        "coordination_readiness": 0.42,
        "primary_intervention_mode": "stabilization_first",
        "playbook_support_level": "medium",
        "top_risk_driver": "fragmentation_pressure",
    }
    policy = {
        "risk_state": "watch",
        "route_strategy": "rerun_and_clarify",
        "safety_mode": "evidence_first",
        "requires_human_review": False,
    }
    return snapshot, order, advisory, summary, policy, 0.28


def _base_item() -> dict:
    return {
        "text": "launch coordination is degrading",
        "_why_strategy": {},
        "_copilot_output": {},
        "_intent": {},
        "_why": {},
        "_llm_backend": {},
        "_path_selection": {"route_key": "r1", "reason": "test"},
        "_graph_runtime": {"mode": "reuse"},
        "_trail_route": {},
        "_coalition": {},
        "_derived_module": {},
        "_care_cycle": {},
        "_network_plan": {},
        "_adequacy_report": {},
        "_observer_report": {},
        "_alignment_report": {
            "alignment_score": 0.31,
            "tension_score": 0.79,
            "participants": [
                {"participant_id": "product"},
                {"participant_id": "security"},
            ],
            "pairwise_hotspots": [
                {
                    "participants": ["product", "security"],
                    "alignment": 0.22,
                    "tension": 0.88,
                    "mismatch_reasons": ["intent_conflict"],
                }
            ],
        },
        "_alignment_outcome": {},
        "_resonance_score": 0.5,
        "_relational_field": {
            "tension_score": 0.74,
            "alignment_score": 0.29,
            "dominant_signal": "tension",
        },
    }


def test_harmonic_state_summary_fallback_contract_is_bounded():
    summary = build_harmonic_state_summary().to_dict()

    assert {
        "harmonic_center",
        "harmonic_interval_label",
        "harmonic_tension",
        "harmonic_stability",
        "resolution_direction",
        "modulation_candidate",
        "harmonic_summary_reason",
    }.issubset(summary.keys())
    assert summary["harmonic_center"] == "insufficient_context"
    assert summary["harmonic_interval_label"] == "unknown"
    assert summary["resolution_direction"] == "gather_context"
    assert summary["modulation_candidate"] == "unknown"
    assert 0.0 <= summary["harmonic_tension"] <= 1.0
    assert 0.0 <= summary["harmonic_stability"] <= 1.0
    assert 0 < len(summary["harmonic_summary_reason"]) <= 140


def test_harmonic_state_summary_detects_structural_dissonance_and_translation_path():
    snapshot, order, advisory, summary, policy, coherence = _scenario_inputs()

    harmonic = build_harmonic_state_summary(
        collective_coordination_snapshot=snapshot,
        bridge_stabilization_order=order,
        bridge_playbook_advisory=advisory,
        coordination_advisory_summary=summary,
        relational_policy_decision=policy,
        relational_coherence=coherence,
    ).to_dict()

    assert harmonic["harmonic_center"] == "stabilization"
    assert harmonic["harmonic_interval_label"] == "tritone"
    assert harmonic["resolution_direction"] == "deescalate_then_translate"
    assert harmonic["modulation_candidate"] == "translation"
    assert harmonic["harmonic_tension"] > harmonic["harmonic_stability"]
    assert 0 < len(harmonic["harmonic_summary_reason"]) <= 140


def test_harmonic_state_summary_does_not_mutate_inputs():
    snapshot, order, advisory, summary, policy, coherence = _scenario_inputs()
    snapshot_before = deepcopy(snapshot)
    order_before = deepcopy(order)
    advisory_before = deepcopy(advisory)
    summary_before = deepcopy(summary)
    policy_before = deepcopy(policy)

    build_harmonic_state_summary(
        collective_coordination_snapshot=snapshot,
        bridge_stabilization_order=order,
        bridge_playbook_advisory=advisory,
        coordination_advisory_summary=summary,
        relational_policy_decision=policy,
        relational_coherence=coherence,
    )

    assert snapshot == snapshot_before
    assert order == order_before
    assert advisory == advisory_before
    assert summary == summary_before
    assert policy == policy_before


def test_harmonic_state_metrics_average_properties_are_bounded():
    metrics = HarmonicStateMetrics(
        calls_total=2,
        summaries_total=2,
        tritone_total=1,
        fifth_total=1,
        modulation_total=1,
        _tension_sum=1.42,
        _stability_sum=0.88,
    )

    payload = metrics.to_dict()
    assert payload["calls_total"] == 2
    assert payload["summaries_total"] == 2
    assert payload["avg_harmonic_tension"] == 0.71
    assert payload["avg_harmonic_stability"] == 0.44


def test_resonance_agent_harmonic_state_accessor_updates_metrics():
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    snapshot, order, advisory, summary, policy, coherence = _scenario_inputs()
    item = _base_item()

    harmonic = agent.get_harmonic_state_summary(
        item,
        collective_coordination_snapshot=snapshot,
        bridge_stabilization_order=order,
        bridge_playbook_advisory=advisory,
        coordination_advisory_summary=summary,
        relational_policy_decision=policy,
        relational_coherence=coherence,
    )
    metrics = agent.get_harmonic_state_metrics()

    assert harmonic["harmonic_center"] == "stabilization"
    assert harmonic["harmonic_interval_label"] == "tritone"
    assert metrics["calls_total"] == 1
    assert metrics["summaries_total"] == 1
    assert metrics["stabilization_center_total"] == 1
    assert metrics["tritone_total"] == 1
    assert metrics["modulation_total"] == 1
    assert metrics["avg_harmonic_tension"] == harmonic["harmonic_tension"]


def test_build_output_emits_harmonic_state_contract():
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    output = agent._build_output(_base_item(), final_output="ok", generation_time=0.01, cycle_id="cid")

    assert isinstance(output["harmonic_state_summary"], dict)
    assert isinstance(output["harmonic_state_metrics"], dict)

    harmonic = output["harmonic_state_summary"]
    assert harmonic["harmonic_center"] in _ALLOWED_CENTERS
    assert harmonic["harmonic_interval_label"] in _ALLOWED_INTERVALS
    assert harmonic["resolution_direction"] in _ALLOWED_RESOLUTION
    assert harmonic["modulation_candidate"] in _ALLOWED_MODULATION
    assert 0.0 <= harmonic["harmonic_tension"] <= 1.0
    assert 0.0 <= harmonic["harmonic_stability"] <= 1.0
    assert 0 < len(harmonic["harmonic_summary_reason"]) <= 140
