# -*- coding: utf-8 -*-
"""Tests for coordination advisory summary MVP."""
from __future__ import annotations

import copy
import json

try:
    from agent.coordination_advisory_summary import (
        CoordinationAdvisorySummaryMetrics,
        build_coordination_advisory_summary,
    )
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.coordination_advisory_summary import (
        CoordinationAdvisorySummaryMetrics,
        build_coordination_advisory_summary,
    )
    from modules.agent.resonance_agent import ResonanceAgent


_ALLOWED_LABELS = {"ready", "fragile", "blocked", "insufficient_context"}
_ALLOWED_MODES = {
    "stabilization_first",
    "translation_first",
    "reframe_first",
    "pacing_first",
    "acknowledge_first",
    "mixed",
    "unknown",
}
_ALLOWED_SUPPORT = {"high", "medium", "low", "none", "unknown"}
_ALLOWED_RISK = {
    "coordination_risk",
    "fragmentation_pressure",
    "playbook_misalignment",
    "weak_bridge_support",
    "insufficient_context",
    "unknown",
}
_EXPECTED_ORDER = [
    "coordination_advisory_label",
    "coordination_readiness",
    "primary_intervention_mode",
    "playbook_support_level",
    "top_risk_driver",
    "summary_reason",
]


def _summary(cs=None, bo=None, pa=None) -> dict:
    return build_coordination_advisory_summary(
        collective_coordination_snapshot=cs,
        bridge_stabilization_order=bo,
        bridge_playbook_advisory=pa,
    ).to_dict()


def test_empty_inputs_insufficient_context_and_stable_fallbacks():
    out = _summary()
    assert out["coordination_advisory_label"] == "insufficient_context"
    assert out["coordination_readiness"] == 0.0
    assert out["primary_intervention_mode"] == "unknown"
    assert out["playbook_support_level"] == "unknown"
    assert out["top_risk_driver"] == "insufficient_context"
    assert list(out.keys()) == _EXPECTED_ORDER


def test_snapshot_only_best_effort_no_crash_and_bounded_output():
    out = _summary(cs={"coordination_risk": 0.55, "dominant_bridge_type": "translation_bridge"})
    assert out["coordination_advisory_label"] in {"fragile", "insufficient_context"}
    assert 0.0 <= out["coordination_readiness"] <= 1.0
    assert out["primary_intervention_mode"] in _ALLOWED_MODES
    assert 0 < len(out["summary_reason"]) <= 140


def test_advisory_only_maps_playbook_support_and_mode_can_be_unknown():
    out = _summary(pa={"playbook_alignment_label": "partially_aligned", "playbook_alignment_score": 0.5})
    assert out["playbook_support_level"] == "medium"
    assert out["primary_intervention_mode"] == "unknown"


def test_full_inputs_deterministic_and_valid_enums():
    cs = {"coordination_risk": 0.4, "dominant_bridge_type": "stabilization_bridge", "group_fragmentation_level": "medium"}
    bo = {"ordered_edges": [{"stabilization_label": "urgent_stabilize", "stabilization_score": 0.8}]}
    pa = {"playbook_alignment_label": "partially_aligned", "playbook_alignment_score": 0.58, "dominant_bridge_playbook_fit": "stabilization-led"}
    out = _summary(cs=cs, bo=bo, pa=pa)

    assert out["coordination_advisory_label"] in _ALLOWED_LABELS
    assert out["primary_intervention_mode"] in _ALLOWED_MODES
    assert out["top_risk_driver"] in _ALLOWED_RISK


def test_ready_case():
    out = _summary(
        cs={"coordination_risk": 0.12, "dominant_bridge_type": "stabilization_bridge"},
        bo={"ordered_edges": [{"stabilization_label": "urgent_stabilize", "stabilization_score": 0.82}]},
        pa={"playbook_alignment_label": "well_aligned", "playbook_alignment_score": 0.79, "dominant_bridge_playbook_fit": "stabilization-led"},
    )
    assert out["coordination_advisory_label"] == "ready"


def test_blocked_case():
    out = _summary(
        cs={"coordination_risk": 0.9, "coordination_state_label": "escalating"},
        bo={"ordered_edges": [{"stabilization_label": "monitor", "stabilization_score": 0.2}]},
        pa={"playbook_alignment_label": "misaligned", "playbook_alignment_score": 0.1},
    )
    assert out["coordination_advisory_label"] == "blocked"


def test_fragile_case():
    out = _summary(
        cs={"coordination_risk": 0.56, "coordination_state_label": "strained"},
        bo={"ordered_edges": [{"stabilization_label": "monitor", "stabilization_score": 0.5}]},
        pa={"playbook_alignment_label": "weakly_aligned", "playbook_alignment_score": 0.3, "dominant_bridge_playbook_fit": "mixed"},
    )
    assert out["coordination_advisory_label"] == "fragile"


def test_mode_mapping_coverage():
    assert _summary(bo={"ordered_edges": [{"stabilization_label": "urgent_stabilize", "stabilization_score": 0.9}]})["primary_intervention_mode"] == "stabilization_first"
    assert _summary(bo={"ordered_edges": [{"stabilization_label": "translate_models", "stabilization_score": 0.5}]})["primary_intervention_mode"] == "translation_first"
    assert _summary(bo={"ordered_edges": [{"stabilization_label": "reframe_view", "stabilization_score": 0.5}]})["primary_intervention_mode"] == "reframe_first"
    assert _summary(bo={"ordered_edges": [{"stabilization_label": "slow_down", "stabilization_score": 0.5}]})["primary_intervention_mode"] == "pacing_first"
    assert _summary(bo={"ordered_edges": [{"stabilization_label": "ack_tension", "stabilization_score": 0.5}]})["primary_intervention_mode"] == "acknowledge_first"
    assert _summary(pa={"dominant_bridge_playbook_fit": "mixed", "playbook_alignment_score": 0.2})["primary_intervention_mode"] == "mixed"
    assert _summary(cs={"coordination_risk": 0.3})["primary_intervention_mode"] == "unknown"


def test_playbook_support_mapping_all_alignment_labels():
    assert _summary(pa={"playbook_alignment_label": "well_aligned"})["playbook_support_level"] == "high"
    assert _summary(pa={"playbook_alignment_label": "partially_aligned"})["playbook_support_level"] == "medium"
    assert _summary(pa={"playbook_alignment_label": "weakly_aligned"})["playbook_support_level"] == "low"
    assert _summary(pa={"playbook_alignment_label": "misaligned"})["playbook_support_level"] == "none"
    assert _summary(pa={"playbook_alignment_label": "insufficient_context"})["playbook_support_level"] == "unknown"


def test_risk_driver_mapping_required_coverage():
    assert _summary(cs={"coordination_risk": 0.8}, pa={"playbook_alignment_label": "partially_aligned", "playbook_alignment_score": 0.45})["top_risk_driver"] == "coordination_risk"
    assert _summary(cs={"coordination_risk": 0.3}, pa={"playbook_alignment_label": "misaligned", "playbook_alignment_score": 0.1})["top_risk_driver"] == "playbook_misalignment"
    assert _summary(cs={"coordination_risk": 0.2}, bo={"ordered_edges": []}, pa={"playbook_alignment_label": "weakly_aligned", "playbook_alignment_score": 0.2, "dominant_bridge_playbook_fit": "unknown"})["top_risk_driver"] == "weak_bridge_support"
    assert _summary()["top_risk_driver"] == "insufficient_context"


def test_determinism_same_input_same_output():
    cs = {"coordination_risk": 0.42, "dominant_bridge_type": "translation_bridge"}
    bo = {"ordered_edges": [{"stabilization_label": "translate_models", "stabilization_score": 0.5}]}
    pa = {"playbook_alignment_label": "partially_aligned", "playbook_alignment_score": 0.55}
    a = _summary(cs=cs, bo=bo, pa=pa)
    b = _summary(cs=cs, bo=bo, pa=pa)
    assert a == b


def test_no_mutation_of_inputs():
    cs = {"coordination_risk": 0.6, "dominant_bridge_type": "translation_bridge"}
    bo = {"ordered_edges": [{"stabilization_label": "translate", "stabilization_score": 0.7}]}
    pa = {"playbook_alignment_label": "partially_aligned", "playbook_alignment_score": 0.5}
    cs0, bo0, pa0 = copy.deepcopy(cs), copy.deepcopy(bo), copy.deepcopy(pa)
    _summary(cs=cs, bo=bo, pa=pa)
    assert cs == cs0
    assert bo == bo0
    assert pa == pa0


def test_json_serializable_key_order_and_bounded_reason():
    out = _summary(cs={"coordination_risk": 0.45}, pa={"playbook_alignment_label": "partially_aligned", "playbook_alignment_score": 0.5})
    payload = json.dumps(out, ensure_ascii=False)
    assert isinstance(payload, str)
    assert list(out.keys()) == _EXPECTED_ORDER
    assert isinstance(out["summary_reason"], str)
    assert 0 < len(out["summary_reason"]) <= 140


def test_metrics_behavior_and_average_readiness():
    m = CoordinationAdvisorySummaryMetrics()
    for readiness, label, mode in [(0.5, "fragile", "mixed"), (0.8, "ready", "stabilization_first")]:
        m.calls_total += 1
        m.summaries_total += 1
        m._readiness_sum += readiness
        if label == "ready":
            m.ready_total += 1
        else:
            m.fragile_total += 1
        if mode == "mixed":
            m.mixed_total += 1
        else:
            m.stabilization_first_total += 1

    data = m.to_dict()
    assert data["calls_total"] == 2
    assert data["summaries_total"] == 2
    assert data["ready_total"] == 1
    assert data["fragile_total"] == 1
    assert data["avg_coordination_readiness"] == 0.65


def test_resonance_agent_accessor_updates_metrics_and_has_no_side_effects():
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    cs = {"coordination_risk": 0.2, "dominant_bridge_type": "translation_bridge"}
    bo = {"ordered_edges": [{"stabilization_label": "translate", "stabilization_score": 0.6}]}
    pa = {"playbook_alignment_label": "partially_aligned", "playbook_alignment_score": 0.6, "dominant_bridge_playbook_fit": "translation-led"}

    out = agent.get_coordination_advisory_summary({}, cs, bo, pa)
    metrics = agent.get_coordination_advisory_summary_metrics()

    assert isinstance(out, dict)
    assert metrics.get("calls_total", 0) >= 1
    assert metrics.get("summaries_total", 0) >= 1


def test_build_output_integration_smoke_contains_summary_and_metrics_dicts():
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    item = {
        "text": "integration smoke",
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
        "_alignment_report": {},
        "_alignment_outcome": {},
        "_resonance_score": 0.5,
    }
    output = agent._build_output(item, final_output="ok", generation_time=0.01, cycle_id="cid")
    assert "coordination_advisory_summary" in output
    assert "coordination_advisory_summary_metrics" in output
    assert isinstance(output["coordination_advisory_summary"], dict)
    assert isinstance(output["coordination_advisory_summary_metrics"], dict)


def test_output_value_domains():
    out = _summary(cs={"coordination_risk": 0.6}, pa={"playbook_alignment_label": "partially_aligned", "playbook_alignment_score": 0.4})
    assert out["coordination_advisory_label"] in _ALLOWED_LABELS
    assert out["primary_intervention_mode"] in _ALLOWED_MODES
    assert out["playbook_support_level"] in _ALLOWED_SUPPORT
    assert out["top_risk_driver"] in _ALLOWED_RISK
