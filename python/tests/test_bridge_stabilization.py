# -*- coding: utf-8 -*-
"""Tests for bridge_stabilization — advisory bridge ordering MVP."""
from __future__ import annotations

import copy
import json
import unicodedata
from pathlib import Path

try:
    from agent.bridge_stabilization import (
        BridgeStabilizationMetrics,
        _build_stabilization_reason,
        _compute_stabilization_score,
        _label_stabilization_entry,
        build_bridge_stabilization_order,
    )
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.bridge_stabilization import (
        BridgeStabilizationMetrics,
        _build_stabilization_reason,
        _compute_stabilization_score,
        _label_stabilization_entry,
        build_bridge_stabilization_order,
    )
    from modules.agent.resonance_agent import ResonanceAgent


def _edge(
    frm: str,
    to: str,
    *,
    priority: float,
    strength: float,
    bridge_type: str = "acknowledgment_bridge",
    confidence: float = 0.8,
):
    return {
        "from_party_id": frm,
        "to_party_id": to,
        "bridge_type": bridge_type,
        "bridge_priority": priority,
        "bridge_strength": strength,
        "confidence": confidence,
    }


def _graph(edges, *, fragmentation="low", state="stable"):
    return {
        "nodes": ["a", "b", "c"],
        "edges": edges,
        "fragmentation_level": fragmentation,
        "summary_reason": f"3 parties; {len(edges)} edges; state: {state}",
    }


def _mp_state(state="stable"):
    return {"state_label": state, "parties": [{"party_id": "a"}, {"party_id": "b"}]}


def test_empty_graph_returns_empty_order():
    order = build_bridge_stabilization_order({})
    d = order.to_dict()
    assert d["ordered_edges"] == []
    assert d["dominant_stabilization_mode"] == "observe_and_stage"


def test_one_edge_builds_one_entry_with_rank_and_timing():
    order = build_bridge_stabilization_order(
        _graph([_edge("a", "b", priority=0.9, strength=0.7, bridge_type="stabilization_bridge")], state="escalating"),
        _mp_state("escalating"),
    )
    d = order.to_dict()
    assert len(d["ordered_edges"]) == 1
    assert d["ordered_edges"][0]["rank"] == 1
    assert d["ordered_edges"][0]["recommended_timing"] == "now"


def test_multiple_edges_sorted_deterministically_and_stable_for_same_input():
    graph = _graph([
        _edge("a", "b", priority=0.55, strength=0.7),
        _edge("a", "c", priority=0.82, strength=0.51, bridge_type="stabilization_bridge"),
        _edge("b", "c", priority=0.20, strength=0.20),
    ], state="diverging")
    o1 = build_bridge_stabilization_order(graph, _mp_state("diverging")).to_dict()
    o2 = build_bridge_stabilization_order(graph, _mp_state("diverging")).to_dict()
    assert o1 == o2
    assert [e["rank"] for e in o1["ordered_edges"]] == [1, 2, 3]


def test_label_policy_for_all_mvp_labels():
    assert _label_stabilization_entry(
        _edge("a", "b", priority=0.88, strength=0.6, bridge_type="stabilization_bridge"), "escalating", "high"
    ) == "urgent_stabilize"
    assert _label_stabilization_entry(
        _edge("a", "b", priority=0.70, strength=0.8), "stable", "low"
    ) == "early_stabilize"
    assert _label_stabilization_entry(
        _edge("a", "b", priority=0.45, strength=0.82), "stable", "low"
    ) == "quick_win"
    assert _label_stabilization_entry(
        _edge("a", "b", priority=0.40, strength=0.30), "stable", "low"
    ) == "monitor"
    assert _label_stabilization_entry(
        _edge("a", "b", priority=0.10, strength=0.20), "stable", "low"
    ) == "defer"


def test_timing_mapping_for_labels():
    graph = _graph([
        _edge("a", "b", priority=0.9, strength=0.6, bridge_type="stabilization_bridge"),
        _edge("a", "c", priority=0.7, strength=0.9),
        _edge("b", "c", priority=0.2, strength=0.1),
    ], state="escalating")
    order = build_bridge_stabilization_order(graph, _mp_state("escalating")).to_dict()
    labels_to_timing = {e["stabilization_label"]: e["recommended_timing"] for e in order["ordered_edges"]}
    assert labels_to_timing["urgent_stabilize"] == "now"
    assert labels_to_timing["early_stabilize"] == "soon"
    assert labels_to_timing["defer"] == "later"


def test_bounded_output_lists():
    edges = [_edge(f"p{i}", f"q{i}", priority=0.95, strength=0.8, bridge_type="stabilization_bridge") for i in range(7)]
    edges += [_edge(f"u{i}", f"v{i}", priority=0.4, strength=0.85) for i in range(6)]
    edges += [_edge(f"m{i}", f"n{i}", priority=0.1, strength=0.2) for i in range(6)]
    order = build_bridge_stabilization_order(_graph(edges, state="escalating"), _mp_state("escalating")).to_dict()
    assert len(order["ordered_edges"]) <= 10
    assert len(order["urgent_edges"]) <= 3
    assert len(order["quick_win_edges"]) <= 3
    assert len(order["defer_edges"]) <= 3


def test_dominant_mode_and_summary_are_deterministic_and_compact():
    order = build_bridge_stabilization_order(
        _graph([
            _edge("a", "b", priority=0.92, strength=0.8, bridge_type="stabilization_bridge"),
            _edge("a", "c", priority=0.83, strength=0.7, bridge_type="stabilization_bridge"),
        ], state="escalating"),
        _mp_state("escalating"),
    ).to_dict()
    assert order["dominant_stabilization_mode"] == "crisis_first"
    assert "mode=crisis_first" in order["summary_reason"]


def test_output_json_serializable_and_key_stable():
    order = build_bridge_stabilization_order(_graph([_edge("a", "b", priority=0.5, strength=0.6)]), _mp_state())
    dumped = json.dumps(order.to_dict(), ensure_ascii=False)
    assert isinstance(dumped, str)
    keys = list(order.to_dict().keys())
    assert keys == [
        "ordered_edges",
        "urgent_edges",
        "early_stabilization_edges",
        "quick_win_edges",
        "defer_edges",
        "dominant_stabilization_mode",
        "summary_reason",
    ]


def test_scores_range_and_monotonic_tendencies():
    e_low = _edge("a", "b", priority=0.2, strength=0.2)
    e_high_pri = _edge("a", "b", priority=0.9, strength=0.2)
    e_high_str = _edge("a", "b", priority=0.9, strength=0.9)
    s_low = _compute_stabilization_score(e_low, "stable")
    s_high_pri = _compute_stabilization_score(e_high_pri, "stable")
    s_high_str = _compute_stabilization_score(e_high_str, "stable")
    s_escalating = _compute_stabilization_score(e_high_pri, "escalating")

    for s in (s_low, s_high_pri, s_high_str, s_escalating):
        assert 0.0 <= s <= 1.0
    assert s_high_pri > s_low
    assert s_high_str >= s_high_pri
    assert s_escalating > s_high_pri
    assert _compute_stabilization_score(e_high_pri, "escalating") == s_escalating


def test_builder_does_not_mutate_inputs():
    graph = _graph([_edge("a", "b", priority=0.6, strength=0.7)])
    mp_state = _mp_state("stable")
    graph_before = copy.deepcopy(graph)
    mp_before = copy.deepcopy(mp_state)
    build_bridge_stabilization_order(graph, mp_state)
    assert graph == graph_before
    assert mp_state == mp_before


def test_reason_builder_is_short_and_deterministic():
    edge = _edge("a", "b", priority=0.6, strength=0.7)
    r1 = _build_stabilization_reason(edge, "monitor", "stable")
    r2 = _build_stabilization_reason(edge, "monitor", "stable")
    assert r1 == r2
    assert len(r1) <= 120


def test_metrics_to_dict_and_average_score():
    m = BridgeStabilizationMetrics()
    assert m.to_dict()["avg_stabilization_score"] == 0.0
    m.edges_processed_total = 2
    m._stabilization_score_sum = 1.5
    assert m.to_dict()["avg_stabilization_score"] == 0.75


def test_resonance_agent_accessor_is_read_only_and_safe_without_graph():
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    item = {
        "route_key": "keep",
        "graph_mode": "reuse",
        "_path_selection": {"route_key": "keep"},
        "_graph_runtime": {"mode": "reuse"},
    }
    before = copy.deepcopy(item)
    out = agent.get_bridge_stabilization_order(item, bridge_graph_state=None, multi_party_state=None)
    assert isinstance(out, dict)
    assert item == before


def test_resonance_agent_metrics_update_for_non_empty_and_empty_inputs():
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    item = {}

    graph = _graph([_edge("a", "b", priority=0.9, strength=0.7, bridge_type="stabilization_bridge")], state="escalating")
    _ = agent.get_bridge_stabilization_order(item, bridge_graph_state=graph, multi_party_state=_mp_state("escalating"))
    _ = agent.get_bridge_stabilization_order(item, bridge_graph_state={"edges": []}, multi_party_state=_mp_state("stable"))

    metrics = agent.get_bridge_stabilization_metrics()
    assert metrics["calls_total"] >= 2
    assert metrics["orders_total"] >= 1
    assert metrics["edges_processed_total"] >= 1
    assert metrics["empty_inputs_total"] >= 1


def test_bridge_stabilization_module_has_no_hidden_or_bidi_unicode_controls():
    module_path = Path(__file__).resolve().parents[1] / "modules" / "agent" / "bridge_stabilization.py"
    text = module_path.read_text(encoding="utf-8")

    for ch in text:
        # Unicode category Cf includes invisible formatting controls (incl. bidi marks).
        assert unicodedata.category(ch) != "Cf"

