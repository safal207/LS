# -*- coding: utf-8 -*-
"""Tests for bridge_graph — structural bridge graph MVP."""
from __future__ import annotations

try:
    from agent.bridge_graph import (
        BRIDGE_TYPE_ACKNOWLEDGMENT,
        BRIDGE_TYPE_PACING,
        BRIDGE_TYPE_REFRAMING,
        BRIDGE_TYPE_STABILIZATION,
        BRIDGE_TYPE_TRANSLATION,
        BridgeGraphMetrics,
        BridgeGraphState,
        _compute_bridge_priority,
        _compute_bridge_strength,
        _infer_bridge_type,
        build_bridge_edges,
        build_bridge_graph_state,
    )
except ImportError:
    from modules.agent.bridge_graph import (
        BRIDGE_TYPE_ACKNOWLEDGMENT,
        BRIDGE_TYPE_PACING,
        BRIDGE_TYPE_REFRAMING,
        BRIDGE_TYPE_STABILIZATION,
        BRIDGE_TYPE_TRANSLATION,
        BridgeGraphMetrics,
        BridgeGraphState,
        _compute_bridge_priority,
        _compute_bridge_strength,
        _infer_bridge_type,
        build_bridge_edges,
        build_bridge_graph_state,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _party(pid, *, label="neutral", tension_axes=None, alignment_gap=0.3, hotspot_count=1):
    return {
        "party_id": pid,
        "position_label": label,
        "tension_axes": tension_axes or [],
        "alignment_gap": alignment_gap,
        "hotspot_count": hotspot_count,
    }


def _multi_party_state(parties, *, state_label="stable", dominant_axis="", convergence=0.5):
    return {
        "parties": parties,
        "state_label": state_label,
        "dominant_tension_axis": dominant_axis,
        "alignment_convergence": convergence,
        "party_count": len(parties),
    }


# ---------------------------------------------------------------------------
# 1. Edge building — fewer than two parties
# ---------------------------------------------------------------------------

def test_empty_parties_returns_no_edges():
    state = _multi_party_state([])
    edges = build_bridge_edges(state)
    assert edges == []


def test_one_party_returns_no_edges():
    state = _multi_party_state([_party("a")])
    edges = build_bridge_edges(state)
    assert edges == []


def test_invalid_input_returns_no_edges():
    assert build_bridge_edges(None) == []   # type: ignore[arg-type]
    assert build_bridge_edges("bad") == []  # type: ignore[arg-type]
    assert build_bridge_edges({}) == []


# ---------------------------------------------------------------------------
# 2. Two parties → one edge
# ---------------------------------------------------------------------------

def test_two_parties_build_one_edge():
    state = _multi_party_state([_party("a"), _party("b")])
    edges = build_bridge_edges(state)
    assert len(edges) == 1


def test_edge_party_ids_correct():
    state = _multi_party_state([_party("alice"), _party("bob")])
    edges = build_bridge_edges(state)
    assert edges[0].from_party_id == "alice"
    assert edges[0].to_party_id == "bob"


# ---------------------------------------------------------------------------
# 3. Several parties → bounded set of edges
# ---------------------------------------------------------------------------

def test_three_parties_build_three_edges():
    state = _multi_party_state([_party("a"), _party("b"), _party("c")])
    edges = build_bridge_edges(state)
    assert len(edges) == 3


def test_edges_bounded_at_ten():
    # 5 parties → max 10 combinations
    parties = [_party(f"p{i}") for i in range(5)]
    state = _multi_party_state(parties)
    edges = build_bridge_edges(state)
    assert len(edges) <= 10


def test_more_than_five_parties_capped():
    # 6 parties → only first 5 used → max 10 edges
    parties = [_party(f"p{i}") for i in range(6)]
    state = _multi_party_state(parties)
    edges = build_bridge_edges(state)
    assert len(edges) <= 10


# ---------------------------------------------------------------------------
# 4. from/to party IDs correct
# ---------------------------------------------------------------------------

def test_edge_party_ids_present_for_all_pairs():
    parties = [_party("x"), _party("y"), _party("z")]
    state = _multi_party_state(parties)
    edges = build_bridge_edges(state)
    pairs = {(e.from_party_id, e.to_party_id) for e in edges}
    assert ("x", "y") in pairs or ("y", "x") in pairs
    assert ("x", "z") in pairs or ("z", "x") in pairs
    assert ("y", "z") in pairs or ("z", "y") in pairs


# ---------------------------------------------------------------------------
# 5. Deterministic: identical input → identical edges
# ---------------------------------------------------------------------------

def test_identical_input_gives_identical_edges():
    state = _multi_party_state([
        _party("a", tension_axes=["why_mismatch"], alignment_gap=0.5),
        _party("b", tension_axes=["intent_conflict"], alignment_gap=0.4),
    ])
    edges1 = build_bridge_edges(state)
    edges2 = build_bridge_edges(state)
    assert [e.to_dict() for e in edges1] == [e.to_dict() for e in edges2]


# ---------------------------------------------------------------------------
# 6-10. Bridge type inference
# ---------------------------------------------------------------------------

def test_escalating_state_gives_stabilization_bridge():
    a = _party("a", label="tension_source", tension_axes=["intent_conflict"])
    b = _party("b", label="responsive")
    bt = _infer_bridge_type(a, b, "escalating")
    assert bt == BRIDGE_TYPE_STABILIZATION


def test_both_tension_source_gives_stabilization_bridge():
    a = _party("a", label="tension_source")
    b = _party("b", label="tension_source")
    bt = _infer_bridge_type(a, b, "diverging")
    assert bt == BRIDGE_TYPE_STABILIZATION


def test_intent_conflict_axis_gives_reframing_bridge():
    a = _party("a", tension_axes=["intent_conflict:x!=y"])
    b = _party("b", tension_axes=["intent_conflict:x!=y"])
    bt = _infer_bridge_type(a, b, "stable")
    assert bt == BRIDGE_TYPE_REFRAMING


def test_pacing_mismatch_gives_pacing_bridge():
    a = _party("a", tension_axes=["background_state_divergence"])
    b = _party("b", tension_axes=["background_state_divergence"])
    bt = _infer_bridge_type(a, b, "stable")
    assert bt == BRIDGE_TYPE_PACING


def test_pressure_conflict_gives_pacing_bridge():
    a = _party("a", tension_axes=["need_pressure_conflict:speed<->accuracy"])
    b = _party("b", tension_axes=["need_pressure_conflict:speed<->accuracy"])
    bt = _infer_bridge_type(a, b, "stable")
    assert bt == BRIDGE_TYPE_PACING


def test_why_mismatch_gives_translation_bridge():
    a = _party("a", tension_axes=["why_mismatch"])
    b = _party("b", tension_axes=["why_mismatch"])
    bt = _infer_bridge_type(a, b, "stable")
    assert bt == BRIDGE_TYPE_TRANSLATION


def test_no_specific_axis_gives_acknowledgment_bridge():
    a = _party("a", tension_axes=[])
    b = _party("b", tension_axes=[])
    bt = _infer_bridge_type(a, b, "stable")
    assert bt == BRIDGE_TYPE_ACKNOWLEDGMENT


def test_bridge_type_fallback_is_deterministic():
    a = _party("a")
    b = _party("b")
    results = {_infer_bridge_type(a, b, "stable") for _ in range(5)}
    assert len(results) == 1


# ---------------------------------------------------------------------------
# 12-13. Score ranges
# ---------------------------------------------------------------------------

def test_bridge_strength_in_range():
    for gap_a in [0.0, 0.3, 0.7, 1.0]:
        for gap_b in [0.0, 0.5, 1.0]:
            a = _party("a", alignment_gap=gap_a)
            b = _party("b", alignment_gap=gap_b)
            s = _compute_bridge_strength(a, b)
            assert 0.0 <= s <= 1.0, f"strength={s} out of range"


def test_bridge_priority_in_range():
    for state in ("stable", "diverging", "escalating", "converging"):
        for gap in [0.0, 0.4, 0.8]:
            a = _party("a", alignment_gap=gap)
            b = _party("b", alignment_gap=gap)
            p = _compute_bridge_priority(a, b, state)
            assert 0.0 <= p <= 1.0, f"priority={p} out of range"


# ---------------------------------------------------------------------------
# 14. Higher risk → higher priority
# ---------------------------------------------------------------------------

def test_escalating_gives_higher_priority_than_stable():
    a = _party("a", alignment_gap=0.5)
    b = _party("b", alignment_gap=0.5)
    p_escalating = _compute_bridge_priority(a, b, "escalating")
    p_stable = _compute_bridge_priority(a, b, "stable")
    assert p_escalating > p_stable


def test_diverging_gives_higher_priority_than_stable():
    a = _party("a", alignment_gap=0.4)
    b = _party("b", alignment_gap=0.4)
    p_diverging = _compute_bridge_priority(a, b, "diverging")
    p_stable = _compute_bridge_priority(a, b, "stable")
    assert p_diverging > p_stable


# ---------------------------------------------------------------------------
# 15. Shared axis increases strength
# ---------------------------------------------------------------------------

def test_shared_axis_increases_strength():
    a_shared = _party("a", tension_axes=["why_mismatch"])
    b_shared = _party("b", tension_axes=["why_mismatch"])
    a_none = _party("a", tension_axes=[])
    b_none = _party("b", tension_axes=[])
    s_shared = _compute_bridge_strength(a_shared, b_shared)
    s_none = _compute_bridge_strength(a_none, b_none)
    assert s_shared > s_none


# ---------------------------------------------------------------------------
# 16. Strong mismatch increases priority
# ---------------------------------------------------------------------------

def test_high_gap_increases_priority():
    a_high = _party("a", alignment_gap=0.8)
    b_high = _party("b", alignment_gap=0.8)
    a_low = _party("a", alignment_gap=0.1)
    b_low = _party("b", alignment_gap=0.1)
    p_high = _compute_bridge_priority(a_high, b_high, "stable")
    p_low = _compute_bridge_priority(a_low, b_low, "stable")
    assert p_high > p_low


def test_tension_source_increases_priority():
    a_ts = _party("a", label="tension_source", alignment_gap=0.4)
    a_neutral = _party("a", label="neutral", alignment_gap=0.4)
    b = _party("b", alignment_gap=0.4)
    p_ts = _compute_bridge_priority(a_ts, b, "stable")
    p_neutral = _compute_bridge_priority(a_neutral, b, "stable")
    assert p_ts > p_neutral


# ---------------------------------------------------------------------------
# 17. Empty graph state is valid
# ---------------------------------------------------------------------------

def test_empty_graph_state_valid():
    result = build_bridge_graph_state({})
    assert isinstance(result, BridgeGraphState)
    d = result.to_dict()
    for key in ("nodes", "edges", "dominant_bridge_type", "highest_priority_edges",
                "bridge_density", "fragmentation_level", "summary_reason"):
        assert key in d


def test_none_multi_party_state_safe():
    result = build_bridge_graph_state(None)  # type: ignore[arg-type]
    assert isinstance(result, BridgeGraphState)
    assert result.edges == []


# ---------------------------------------------------------------------------
# 18. bridge_density computed correctly
# ---------------------------------------------------------------------------

def test_bridge_density_two_parties():
    # 2 parties → 1 possible edge → if 1 built → density = 1.0
    state = _multi_party_state([_party("a"), _party("b")])
    g = build_bridge_graph_state(state)
    assert g.bridge_density == 1.0


def test_bridge_density_three_parties():
    # 3 parties → 3 possible edges → if 3 built → density = 1.0
    state = _multi_party_state([_party("a"), _party("b"), _party("c")])
    g = build_bridge_graph_state(state)
    assert g.bridge_density == 1.0


def test_bridge_density_zero_when_no_parties():
    g = build_bridge_graph_state(_multi_party_state([]))
    assert g.bridge_density == 0.0


# ---------------------------------------------------------------------------
# 19. fragmentation_level
# ---------------------------------------------------------------------------

def test_fragmentation_high_when_no_edges():
    # With no parties, density=0 → high fragmentation
    state_empty = _multi_party_state([])
    g = build_bridge_graph_state(state_empty)
    # With no parties, density=0 → high fragmentation
    assert g.fragmentation_level == "high"


def test_fragmentation_low_when_fully_connected():
    # 2 parties → 1 edge → density 1.0 → low
    state = _multi_party_state([_party("a"), _party("b")])
    g = build_bridge_graph_state(state)
    assert g.fragmentation_level == "low"


def test_fragmentation_levels_valid():
    valid = {"low", "medium", "high"}
    for n in range(0, 5):
        parties = [_party(f"p{i}") for i in range(n)]
        state = _multi_party_state(parties)
        g = build_bridge_graph_state(state)
        assert g.fragmentation_level in valid


# ---------------------------------------------------------------------------
# 20. dominant_bridge_type
# ---------------------------------------------------------------------------

def test_dominant_bridge_type_most_common():
    # Force why_mismatch on all to get translation_bridge
    parties = [
        _party("a", tension_axes=["why_mismatch"], label="responsive"),
        _party("b", tension_axes=["why_mismatch"], label="responsive"),
        _party("c", tension_axes=["why_mismatch"], label="responsive"),
    ]
    state = _multi_party_state(parties, state_label="stable")
    g = build_bridge_graph_state(state)
    assert g.dominant_bridge_type == BRIDGE_TYPE_TRANSLATION


def test_dominant_bridge_type_empty_when_no_edges():
    state = _multi_party_state([])
    g = build_bridge_graph_state(state)
    assert g.dominant_bridge_type == ""


# ---------------------------------------------------------------------------
# 21. highest_priority_edges bounded
# ---------------------------------------------------------------------------

def test_highest_priority_edges_at_most_three():
    parties = [_party(f"p{i}") for i in range(5)]
    state = _multi_party_state(parties)
    g = build_bridge_graph_state(state)
    assert len(g.highest_priority_edges) <= 3


def test_highest_priority_edges_are_top_priority():
    parties = [
        _party("a", alignment_gap=0.9, label="tension_source"),
        _party("b", alignment_gap=0.9, label="tension_source"),
        _party("c", alignment_gap=0.1, label="aligned"),
        _party("d", alignment_gap=0.1, label="aligned"),
    ]
    state = _multi_party_state(parties, state_label="escalating")
    g = build_bridge_graph_state(state)
    if len(g.edges) > 1 and g.highest_priority_edges:
        top_priority = g.highest_priority_edges[0]["bridge_priority"]
        max_priority = max(e["bridge_priority"] for e in g.edges)
        assert abs(top_priority - max_priority) < 1e-4


# ---------------------------------------------------------------------------
# 22. summary_reason explainable
# ---------------------------------------------------------------------------

def test_summary_reason_not_empty_for_valid_state():
    state = _multi_party_state([_party("a"), _party("b")])
    g = build_bridge_graph_state(state)
    assert g.summary_reason != ""


def test_summary_reason_contains_party_count():
    state = _multi_party_state([_party("a"), _party("b")])
    g = build_bridge_graph_state(state)
    assert "2" in g.summary_reason


# ---------------------------------------------------------------------------
# 23-28. Safety: no mutation, no routing changes
# ---------------------------------------------------------------------------

def test_builder_does_not_mutate_multi_party_state():
    parties = [
        _party("a", tension_axes=["why_mismatch"]),
        _party("b", tension_axes=["intent_conflict"]),
    ]
    state = _multi_party_state(parties, state_label="diverging")
    import copy
    original = copy.deepcopy(state)
    build_bridge_graph_state(state)
    assert state == original


def test_builder_does_not_mutate_alignment_report():
    report = {
        "pairwise_hotspots": [{"participants": ["a", "b"], "tension": 0.6}],
        "alignment_score": 0.3,
    }
    state = _multi_party_state([_party("a"), _party("b")])
    import copy
    original_report = copy.deepcopy(report)
    build_bridge_graph_state(state, report)
    assert report == original_report


def test_output_has_no_route_key():
    state = _multi_party_state([_party("a"), _party("b")])
    g = build_bridge_graph_state(state)
    d = g.to_dict()
    assert "route_key" not in d
    assert "graph_mode" not in d
    assert "reuse" not in d


def test_output_has_no_prompt_field():
    state = _multi_party_state([_party("a"), _party("b")])
    g = build_bridge_graph_state(state)
    d = g.to_dict()
    assert "prompt" not in d
    assert "pre_prompt" not in d
    assert "system_prompt" not in d


def test_bridge_edge_has_no_imperative_fields():
    state = _multi_party_state([_party("a"), _party("b")])
    edges = build_bridge_edges(state)
    assert len(edges) == 1
    d = edges[0].to_dict()
    for forbidden in ("action", "instruct", "command", "do_", "must_", "intervention"):
        assert forbidden not in d, f"Imperative field '{forbidden}' found in edge"


# ---------------------------------------------------------------------------
# 30-37. Metrics
# ---------------------------------------------------------------------------

def test_metrics_calls_total_increments():
    m = BridgeGraphMetrics(calls_total=0)
    # Simulate manual increment (metrics are updated by resonance_agent)
    m.calls_total += 1
    assert m.calls_total == 1


def test_metrics_to_dict_has_required_keys():
    m = BridgeGraphMetrics()
    d = m.to_dict()
    required = {
        "calls_total", "graph_states_total", "edges_total", "small_input_total",
        "acknowledgment_bridge_total", "pacing_bridge_total", "reframing_bridge_total",
        "translation_bridge_total", "stabilization_bridge_total",
        "high_fragmentation_total", "avg_bridge_strength", "avg_bridge_priority",
    }
    assert required.issubset(d.keys())


def test_metrics_avg_strength_zero_when_no_edges():
    m = BridgeGraphMetrics()
    assert m.avg_bridge_strength == 0.0


def test_metrics_avg_priority_zero_when_no_edges():
    m = BridgeGraphMetrics()
    assert m.avg_bridge_priority == 0.0


def test_metrics_avg_strength_computed():
    m = BridgeGraphMetrics(edges_total=4, _strength_sum=2.0)
    assert m.avg_bridge_strength == 0.5


def test_metrics_avg_priority_computed():
    m = BridgeGraphMetrics(edges_total=2, _priority_sum=1.2)
    assert abs(m.avg_bridge_priority - 0.6) < 1e-4


def test_metrics_bridge_type_counters_present():
    m = BridgeGraphMetrics(
        acknowledgment_bridge_total=3,
        pacing_bridge_total=1,
    )
    d = m.to_dict()
    assert d["acknowledgment_bridge_total"] == 3
    assert d["pacing_bridge_total"] == 1


# ---------------------------------------------------------------------------
# 38-40. ResonanceAgent integration-style checks (using builder directly)
# ---------------------------------------------------------------------------

def test_accessor_returns_dict_without_side_effects():
    state = _multi_party_state([_party("a"), _party("b")])
    result = build_bridge_graph_state(state)
    d = result.to_dict()
    assert isinstance(d, dict)
    assert "edges" in d
    assert "nodes" in d


def test_missing_multi_party_state_handled_safely():
    # Simulates accessor receiving empty item (no _multi_party_state key)
    item = {}
    mp_state = item.get("_multi_party_state") or {}
    result = build_bridge_graph_state(mp_state)
    assert result.edges == []


def test_existing_alignment_outputs_not_affected():
    # Bridge graph builder never touches alignment_report keys
    report = {"alignment_score": 0.8, "tension_score": 0.2}
    state = _multi_party_state([_party("a"), _party("b")])
    build_bridge_graph_state(state, report)
    # Report still intact
    assert report["alignment_score"] == 0.8
    assert report["tension_score"] == 0.2
