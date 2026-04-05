# -*- coding: utf-8 -*-
"""Tests for collective_coordination snapshot MVP."""
from __future__ import annotations

import copy
import json
import unicodedata
from pathlib import Path

try:
    from agent.collective_coordination import (
        CollectiveCoordinationMetrics,
        _build_primary_fracture_line,
        _build_snapshot_reason,
        _build_top_risk_parties,
        _compute_coordination_risk,
        _label_coordination_state,
        build_collective_coordination_snapshot,
    )
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.collective_coordination import (
        CollectiveCoordinationMetrics,
        _build_primary_fracture_line,
        _build_snapshot_reason,
        _build_top_risk_parties,
        _compute_coordination_risk,
        _label_coordination_state,
        build_collective_coordination_snapshot,
    )
    from modules.agent.resonance_agent import ResonanceAgent


def _multi_party(*, state_label="stable", convergence=0.55, adoption=0.45):
    return {
        "state_label": state_label,
        "alignment_convergence": convergence,
        "adoption_coverage": adoption,
        "dominant_tension_axis": "intent_conflict",
        "parties": [
            {
                "party_id": "a",
                "position_label": "tension_source",
                "alignment_gap": 0.7,
                "hotspot_count": 3,
            },
            {
                "party_id": "b",
                "position_label": "responsive",
                "alignment_gap": 0.5,
                "hotspot_count": 2,
            },
            {
                "party_id": "c",
                "position_label": "neutral",
                "alignment_gap": 0.2,
                "hotspot_count": 0,
            },
            {
                "party_id": "d",
                "position_label": "aligned",
                "alignment_gap": 0.1,
                "hotspot_count": 0,
            },
        ],
    }


def _bridge_graph(*, fragmentation="medium", dominant="reframing_bridge", priority=0.7):
    return {
        "fragmentation_level": fragmentation,
        "dominant_bridge_type": dominant,
        "highest_priority_edges": [
            {
                "from_party_id": "a",
                "to_party_id": "b",
                "bridge_type": dominant,
                "tension_axis": "intent_conflict",
                "bridge_priority": priority,
                "bridge_strength": 0.8,
                "bridge_reason": "high mismatch and tension",
            },
            {
                "from_party_id": "a",
                "to_party_id": "c",
                "bridge_type": "pacing_bridge",
                "tension_axis": "need_pressure_conflict",
                "bridge_priority": 0.64,
                "bridge_strength": 0.72,
            },
            {
                "from_party_id": "b",
                "to_party_id": "c",
                "bridge_type": "translation_bridge",
                "tension_axis": "why_mismatch",
                "bridge_priority": 0.51,
                "bridge_strength": 0.55,
            },
            {
                "from_party_id": "c",
                "to_party_id": "d",
                "bridge_type": "acknowledgment_bridge",
                "tension_axis": "unknown",
                "bridge_priority": 0.40,
                "bridge_strength": 0.40,
            },
        ],
    }


def _stabilization(*, mode="high_priority_first", urgent=1):
    urgent_edges = [
        {
            "rank": 1,
            "from_party_id": "a",
            "to_party_id": "b",
            "stabilization_label": "urgent_stabilize",
            "recommended_timing": "now",
            "stabilization_score": 0.9,
        }
    ][:urgent]
    return {
        "dominant_stabilization_mode": mode,
        "urgent_edges": urgent_edges,
        "ordered_edges": urgent_edges + [
            {
                "rank": 2,
                "from_party_id": "a",
                "to_party_id": "c",
                "stabilization_label": "early_stabilize",
                "recommended_timing": "soon",
                "stabilization_score": 0.72,
            },
            {
                "rank": 3,
                "from_party_id": "b",
                "to_party_id": "c",
                "stabilization_label": "monitor",
                "recommended_timing": "later",
                "stabilization_score": 0.48,
            },
            {
                "rank": 4,
                "from_party_id": "c",
                "to_party_id": "d",
                "stabilization_label": "defer",
                "recommended_timing": "later",
                "stabilization_score": 0.21,
            },
        ],
    }


def test_empty_input_returns_neutral_snapshot():
    snap = build_collective_coordination_snapshot().to_dict()
    assert snap["coordination_state_label"] in {"coherent", "strained", "fragmented", "unstable", "escalating"}
    assert snap["dominant_bridge_type"] == "unknown"
    assert snap["dominant_stabilization_mode"] == "unknown"


def test_partial_inputs_build_snapshot_without_failures():
    only_mp = build_collective_coordination_snapshot(multi_party_state=_multi_party()).to_dict()
    only_bg = build_collective_coordination_snapshot(bridge_graph_state=_bridge_graph()).to_dict()
    only_bo = build_collective_coordination_snapshot(bridge_stabilization_order=_stabilization()).to_dict()
    assert isinstance(only_mp, dict)
    assert isinstance(only_bg, dict)
    assert isinstance(only_bo, dict)


def test_full_input_builds_rich_and_bounded_snapshot():
    snap = build_collective_coordination_snapshot(
        _multi_party(state_label="diverging"),
        _bridge_graph(fragmentation="high", priority=0.86),
        _stabilization(mode="crisis_first", urgent=1),
    ).to_dict()
    assert len(snap["top_bridge_candidates"]) <= 3
    assert len(snap["top_stabilization_edges"]) <= 3
    assert len(snap["top_risk_parties"]) <= 3
    assert snap["primary_fracture_line"] is not None


def test_identical_input_gives_identical_snapshot():
    mp = _multi_party(state_label="stable")
    bg = _bridge_graph(fragmentation="medium")
    bo = _stabilization(mode="observe_and_stage")
    s1 = build_collective_coordination_snapshot(mp, bg, bo).to_dict()
    s2 = build_collective_coordination_snapshot(mp, bg, bo).to_dict()
    assert s1 == s2


def test_coordination_state_label_matrix():
    coherent = _label_coordination_state(
        coordination_risk=0.15,
        multi_party_state={"state_label": "converging"},
        bridge_graph_state={"fragmentation_level": "low"},
        bridge_stabilization_order={"urgent_edges": []},
    )
    strained = _label_coordination_state(
        coordination_risk=0.40,
        multi_party_state={"state_label": "stable"},
        bridge_graph_state={"fragmentation_level": "low"},
        bridge_stabilization_order={"urgent_edges": []},
    )
    fragmented = _label_coordination_state(
        coordination_risk=0.58,
        multi_party_state={"state_label": "stable"},
        bridge_graph_state={"fragmentation_level": "high"},
        bridge_stabilization_order={"urgent_edges": []},
    )
    unstable = _label_coordination_state(
        coordination_risk=0.72,
        multi_party_state={"state_label": "diverging"},
        bridge_graph_state={"fragmentation_level": "medium"},
        bridge_stabilization_order={"urgent_edges": []},
    )
    escalating = _label_coordination_state(
        coordination_risk=0.66,
        multi_party_state={"state_label": "escalating"},
        bridge_graph_state={"fragmentation_level": "high"},
        bridge_stabilization_order={"urgent_edges": [{}, {}]},
    )
    assert coherent == "coherent"
    assert strained == "strained"
    assert fragmented == "fragmented"
    assert unstable == "unstable"
    assert escalating == "escalating"


def test_risk_score_range_and_monotonicity():
    mp = _multi_party(state_label="stable", convergence=0.6, adoption=0.6)
    bg = _bridge_graph(fragmentation="medium", priority=0.5)
    bo = _stabilization(urgent=0)

    low = _compute_coordination_risk(mp, bg, bo)
    high_urgency = _compute_coordination_risk(mp, bg, _stabilization(urgent=1))
    high_fragment = _compute_coordination_risk(mp, _bridge_graph(fragmentation="high", priority=0.5), bo)

    assert 0.0 <= low <= 1.0
    assert 0.0 <= high_urgency <= 1.0
    assert 0.0 <= high_fragment <= 1.0
    assert high_urgency > low
    assert high_fragment > low


def test_fracture_line_build_and_missing_edges_case():
    line = _build_primary_fracture_line(_bridge_graph(), _multi_party())
    assert line is not None
    assert line["from_party_id"] == "a"
    assert _build_primary_fracture_line({"highest_priority_edges": []}, _multi_party()) is None


def test_top_risk_parties_bounded_and_sorted():
    top = _build_top_risk_parties(_multi_party())
    assert len(top) <= 3
    assert top[0]["party_id"] == "a"


def test_dominant_mode_and_type_with_fallback_unknown():
    snap_unknown = build_collective_coordination_snapshot({}, {}, {}).to_dict()
    assert snap_unknown["dominant_bridge_type"] == "unknown"
    assert snap_unknown["dominant_stabilization_mode"] == "unknown"

    snap = build_collective_coordination_snapshot(
        _multi_party(),
        _bridge_graph(dominant="translation_bridge"),
        _stabilization(mode="crisis_first"),
    ).to_dict()
    assert snap["dominant_bridge_type"] == "translation_bridge"
    assert snap["dominant_stabilization_mode"] == "crisis_first"


def test_snapshot_serializable_stable_keys_and_confidence_range():
    snap = build_collective_coordination_snapshot(
        _multi_party(),
        _bridge_graph(),
        _stabilization(),
    ).to_dict()
    assert isinstance(json.dumps(snap, ensure_ascii=False), str)
    assert list(snap.keys()) == [
        "coordination_state_label",
        "coordination_risk",
        "primary_fracture_line",
        "dominant_tension_axis",
        "dominant_bridge_type",
        "dominant_stabilization_mode",
        "group_fragmentation_level",
        "alignment_convergence",
        "adoption_coverage",
        "top_bridge_candidates",
        "top_stabilization_edges",
        "top_risk_parties",
        "summary_reason",
        "confidence",
    ]
    assert 0.0 <= snap["confidence"] <= 1.0


def test_snapshot_reason_is_deterministic_and_explainable():
    s1 = _build_snapshot_reason({
        "coordination_state_label": "unstable",
        "group_fragmentation_level": "high",
        "alignment_convergence": 0.3,
        "urgent_count": 1,
    })
    s2 = _build_snapshot_reason({
        "coordination_state_label": "unstable",
        "group_fragmentation_level": "high",
        "alignment_convergence": 0.3,
        "urgent_count": 1,
    })
    assert s1 == s2
    assert "unstable" in s1


def test_builder_does_not_mutate_inputs():
    mp = _multi_party()
    bg = _bridge_graph()
    bo = _stabilization()
    mp_before = copy.deepcopy(mp)
    bg_before = copy.deepcopy(bg)
    bo_before = copy.deepcopy(bo)

    _ = build_collective_coordination_snapshot(mp, bg, bo)

    assert mp == mp_before
    assert bg == bg_before
    assert bo == bo_before


def test_metrics_to_dict_and_average():
    m = CollectiveCoordinationMetrics()
    assert m.to_dict()["avg_coordination_risk"] == 0.0
    m.snapshots_total = 2
    m._coordination_risk_sum = 1.1
    assert m.to_dict()["avg_coordination_risk"] == 0.55


def test_resonance_agent_accessor_read_only_and_metrics_update():
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    item = {
        "route_key": "keep",
        "graph_mode": "reuse",
        "_path_selection": {"route_key": "keep"},
        "_graph_runtime": {"mode": "reuse"},
    }
    before = copy.deepcopy(item)

    out = agent.get_collective_coordination_snapshot(
        item,
        multi_party_state=_multi_party(state_label="diverging"),
        bridge_graph_state=_bridge_graph(fragmentation="high", priority=0.82),
        bridge_stabilization_order=_stabilization(mode="crisis_first", urgent=1),
    )
    empty = agent.get_collective_coordination_snapshot(item, None, None, None)

    assert isinstance(out, dict)
    assert isinstance(empty, dict)
    assert item == before

    metrics = agent.get_collective_coordination_metrics()
    assert metrics["calls_total"] >= 2
    assert metrics["snapshots_total"] >= 2
    assert metrics["empty_inputs_total"] >= 1
    assert metrics["nonempty_fracture_line_total"] >= 1
    assert metrics["urgent_stabilization_total"] >= 1


def test_collective_coordination_module_has_no_hidden_or_bidi_unicode_controls():
    module_path = Path(__file__).resolve().parents[1] / "modules" / "agent" / "collective_coordination.py"
    text = module_path.read_text(encoding="utf-8")
    for ch in text:
        assert unicodedata.category(ch) != "Cf"
