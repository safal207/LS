# -*- coding: utf-8 -*-
"""Tests for bridge_playbook_link — bridge-to-playbook advisory MVP."""
from __future__ import annotations

import copy
import json

try:
    from agent.bridge_playbook_link import (
        BridgePlaybookMetrics,
        _compute_playbook_alignment_score,
        _label_playbook_alignment,
        _match_playbook_step_to_scene,
        build_bridge_playbook_advisory,
    )
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.bridge_playbook_link import (
        BridgePlaybookMetrics,
        _compute_playbook_alignment_score,
        _label_playbook_alignment,
        _match_playbook_step_to_scene,
        build_bridge_playbook_advisory,
    )
    from modules.agent.resonance_agent import ResonanceAgent


def _playbook(*steps: str) -> dict:
    return {
        "current_playbook_id": "pb1",
        "steps": [
            {"phase": f"phase_{idx}", "actions": [text]}
            for idx, text in enumerate(steps, start=1)
        ],
    }


def _bridge_graph(*bridge_types: str) -> dict:
    edges = []
    for idx, btype in enumerate(bridge_types, start=1):
        edges.append(
            {
                "from_party_id": f"p{idx}",
                "to_party_id": f"q{idx}",
                "bridge_type": btype,
                "bridge_priority": max(0.1, 0.9 - idx * 0.05),
                "bridge_strength": max(0.1, 0.85 - idx * 0.04),
                "confidence": 0.8,
            }
        )
    return {
        "edges": edges,
        "highest_priority_edges": list(edges),
        "fragmentation_level": "medium",
    }


def _order(label: str = "early_stabilize") -> dict:
    return {
        "ordered_edges": [
            {
                "stabilization_label": label,
                "bridge_type": "stabilization_bridge",
                "stabilization_score": 0.8,
            }
        ],
        "dominant_stabilization_mode": "high_priority_first",
    }


def _snapshot(dominant_bridge_type: str = "acknowledgment_bridge", risk: float = 0.5) -> dict:
    return {
        "dominant_bridge_type": dominant_bridge_type,
        "coordination_risk": risk,
        "coordination_state_label": "strained",
    }


def test_empty_inputs_return_neutral_advisory():
    adv = build_bridge_playbook_advisory().to_dict()
    assert adv["playbook_alignment_label"] == "insufficient_context"
    assert adv["playbook_alignment_score"] == 0.0
    assert adv["step_links"] == []


def test_playbook_only_builds_best_effort_partial_advisory():
    adv = build_bridge_playbook_advisory(playbook=_playbook("Acknowledge tension and name the concern")).to_dict()
    assert len(adv["step_links"]) == 1
    assert adv["step_links"][0]["link_label"] in {"insufficient_context", "weak_fit"}


def test_playbook_plus_bridge_graph_builds_richer_advisory():
    adv = build_bridge_playbook_advisory(
        playbook=_playbook("Acknowledge tension and shared concern", "Slow down pace before proposing"),
        bridge_graph_state=_bridge_graph("acknowledgment_bridge", "pacing_bridge"),
    ).to_dict()
    assert len(adv["step_links"]) == 2
    assert adv["top_supported_steps"]


def test_full_inputs_build_rich_advisory_with_summary_and_fit():
    adv = build_bridge_playbook_advisory(
        playbook=_playbook("Acknowledge tension and shared concern", "Slow down pace", "Reframe winner/loser framing"),
        bridge_graph_state=_bridge_graph("acknowledgment_bridge", "pacing_bridge", "reframing_bridge"),
        bridge_stabilization_order=_order("urgent_stabilize"),
        collective_snapshot=_snapshot("acknowledgment_bridge", 0.7),
    ).to_dict()
    assert adv["dominant_bridge_playbook_fit"] in {
        "acknowledgment-led",
        "pacing-led",
        "reframing-led",
        "mixed",
    }
    assert isinstance(adv["summary_reason"], str) and adv["summary_reason"]


def test_graph_dominant_bridge_takes_precedence_over_snapshot_hint():
    link = _match_playbook_step_to_scene(
        "Slow down and avoid rushing the sequence",
        _bridge_graph("pacing_bridge"),
        _order(),
        _snapshot("acknowledgment_bridge"),
        step_id="s1",
    ).to_dict()
    assert link["linked_bridge_type"] == "pacing_bridge"
    assert "dominant=pacing_bridge" in link["link_reason"]


def test_identical_input_is_deterministic():
    kwargs = {
        "playbook": _playbook("Acknowledge tension and shared concern", "Slow down pace"),
        "bridge_graph_state": _bridge_graph("acknowledgment_bridge", "pacing_bridge"),
        "bridge_stabilization_order": _order(),
        "collective_snapshot": _snapshot("acknowledgment_bridge", 0.5),
    }
    a1 = build_bridge_playbook_advisory(**kwargs).to_dict()
    a2 = build_bridge_playbook_advisory(**kwargs).to_dict()
    assert a1 == a2


def test_step_linking_acknowledgment_bridge():
    link = _match_playbook_step_to_scene(
        "Acknowledge and name tension directly",
        _bridge_graph("acknowledgment_bridge"),
        _order(),
        _snapshot("acknowledgment_bridge"),
        step_id="s1",
    ).to_dict()
    assert link["linked_bridge_type"] == "acknowledgment_bridge"
    assert link["link_label"] in {"strong_fit", "partial_fit"}


def test_step_linking_pacing_bridge():
    link = _match_playbook_step_to_scene(
        "Slow down and avoid rushing the sequence",
        _bridge_graph("pacing_bridge"),
        _order(),
        _snapshot("pacing_bridge"),
        step_id="s1",
    ).to_dict()
    assert link["linked_bridge_type"] == "pacing_bridge"


def test_step_linking_reframing_bridge():
    link = _match_playbook_step_to_scene(
        "Use mismatch framing and avoid winner/loser narrative",
        _bridge_graph("reframing_bridge"),
        _order(),
        _snapshot("reframing_bridge"),
        step_id="s1",
    ).to_dict()
    assert link["linked_bridge_type"] == "reframing_bridge"


def test_step_linking_translation_bridge():
    link = _match_playbook_step_to_scene(
        "Translate models and clarify lenses before reaction",
        _bridge_graph("translation_bridge"),
        _order(),
        _snapshot("translation_bridge"),
        step_id="s1",
    ).to_dict()
    assert link["linked_bridge_type"] == "translation_bridge"


def test_step_linking_stabilization_bridge():
    link = _match_playbook_step_to_scene(
        "Prioritize de-escalation and restore safety",
        _bridge_graph("stabilization_bridge"),
        _order("urgent_stabilize"),
        _snapshot("stabilization_bridge"),
        step_id="s1",
    ).to_dict()
    assert link["linked_bridge_type"] == "stabilization_bridge"


def test_unrelated_step_is_weak_or_unsupported():
    link = _match_playbook_step_to_scene(
        "Discuss budget spreadsheet formatting",
        _bridge_graph("acknowledgment_bridge"),
        _order(),
        _snapshot("acknowledgment_bridge"),
        step_id="s1",
    ).to_dict()
    assert link["link_label"] in {"weak_fit", "unsupported", "insufficient_context"}


def test_alignment_label_and_score_buckets():
    strong_links = [{"link_label": "strong_fit", "linked_bridge_type": "acknowledgment_bridge", "link_strength": 0.9} for _ in range(3)]
    mixed_links = [
        {"link_label": "strong_fit", "linked_bridge_type": "acknowledgment_bridge", "link_strength": 0.9},
        {"link_label": "partial_fit", "linked_bridge_type": "pacing_bridge", "link_strength": 0.7},
        {"link_label": "weak_fit", "linked_bridge_type": "reframing_bridge", "link_strength": 0.3},
    ]
    weak_links = [{"link_label": "unsupported", "linked_bridge_type": "pacing_bridge", "link_strength": 0.1} for _ in range(3)]

    label_strong, score_strong = _label_playbook_alignment(strong_links, _snapshot("acknowledgment_bridge"))
    label_mixed, score_mixed = _label_playbook_alignment(mixed_links, _snapshot("acknowledgment_bridge"))
    label_weak, score_weak = _label_playbook_alignment(weak_links, _snapshot("acknowledgment_bridge", 0.8))

    assert label_strong in {"well_aligned", "partially_aligned"}
    assert label_mixed in {"partially_aligned", "weakly_aligned"}
    assert label_weak in {"weakly_aligned", "misaligned"}
    assert 0.0 <= score_weak <= score_mixed <= score_strong <= 1.0


def test_score_monotonic_tendencies():
    more_strong = [
        {"link_label": "strong_fit", "linked_bridge_type": "acknowledgment_bridge", "link_strength": 0.9},
        {"link_label": "strong_fit", "linked_bridge_type": "acknowledgment_bridge", "link_strength": 0.9},
    ]
    less_strong = [
        {"link_label": "partial_fit", "linked_bridge_type": "acknowledgment_bridge", "link_strength": 0.6},
        {"link_label": "weak_fit", "linked_bridge_type": "pacing_bridge", "link_strength": 0.3},
    ]
    with_unsupported = less_strong + [{"link_label": "unsupported", "linked_bridge_type": "reframing_bridge", "link_strength": 0.2}]

    s_more = _compute_playbook_alignment_score(more_strong, _snapshot("acknowledgment_bridge"))
    s_less = _compute_playbook_alignment_score(less_strong, _snapshot("acknowledgment_bridge"))
    s_unsupported = _compute_playbook_alignment_score(with_unsupported, _snapshot("acknowledgment_bridge"))

    assert 0.0 <= s_unsupported <= s_less <= s_more <= 1.0


def test_advisory_json_serializable_and_keys_stable_and_bounded():
    many_steps = [f"Acknowledge tension #{i}" for i in range(20)]
    adv = build_bridge_playbook_advisory(
        playbook=_playbook(*many_steps),
        bridge_graph_state=_bridge_graph("acknowledgment_bridge", "pacing_bridge", "reframing_bridge"),
        bridge_stabilization_order=_order(),
        collective_snapshot=_snapshot("acknowledgment_bridge"),
    ).to_dict()

    dumped = json.dumps(adv, ensure_ascii=False)
    assert isinstance(dumped, str)
    assert list(adv.keys()) == [
        "playbook_alignment_label",
        "playbook_alignment_score",
        "step_links",
        "top_supported_steps",
        "top_weak_steps",
        "dominant_bridge_playbook_fit",
        "summary_reason",
    ]
    assert len(adv["step_links"]) <= 10
    assert len(adv["top_supported_steps"]) <= 3
    assert len(adv["top_weak_steps"]) <= 3


def test_summary_reason_uses_full_weak_count_not_top_n_count():
    pb = _playbook(
        "Discuss budget spreadsheet formatting A",
        "Discuss budget spreadsheet formatting B",
        "Discuss budget spreadsheet formatting C",
        "Discuss budget spreadsheet formatting D",
        "Discuss budget spreadsheet formatting E",
    )
    adv = build_bridge_playbook_advisory(
        playbook=pb,
        bridge_graph_state=_bridge_graph("acknowledgment_bridge"),
        bridge_stabilization_order=_order(),
        collective_snapshot=_snapshot("acknowledgment_bridge"),
    ).to_dict()
    assert len(adv["top_weak_steps"]) == 3
    assert "weak steps=5" in adv["summary_reason"]


def test_builder_does_not_mutate_inputs():
    pb = _playbook("Acknowledge tension", "Slow down pace")
    bg = _bridge_graph("acknowledgment_bridge", "pacing_bridge")
    bo = _order("urgent_stabilize")
    cs = _snapshot("acknowledgment_bridge")

    pb_before = copy.deepcopy(pb)
    bg_before = copy.deepcopy(bg)
    bo_before = copy.deepcopy(bo)
    cs_before = copy.deepcopy(cs)

    _ = build_bridge_playbook_advisory(
        playbook=pb,
        bridge_graph_state=bg,
        bridge_stabilization_order=bo,
        collective_snapshot=cs,
    )

    assert pb == pb_before
    assert bg == bg_before
    assert bo == bo_before
    assert cs == cs_before


def test_metrics_to_dict_average_score_and_counters():
    m = BridgePlaybookMetrics()
    assert m.to_dict()["avg_playbook_alignment_score"] == 0.0
    m.advisories_total = 2
    m._alignment_score_sum = 1.4
    m.strong_fit_total = 3
    assert m.to_dict()["avg_playbook_alignment_score"] == 0.7


def test_resonance_agent_accessor_and_metrics_have_no_side_effects():
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    item = {
        "route_key": "keep",
        "graph_mode": "reuse",
        "_path_selection": {"route_key": "keep"},
        "_graph_runtime": {"mode": "reuse"},
    }
    before = copy.deepcopy(item)

    advisory = agent.get_bridge_playbook_advisory(
        item,
        playbook=_playbook("Acknowledge tension and shared concern"),
        bridge_graph_state=_bridge_graph("acknowledgment_bridge"),
        bridge_stabilization_order=_order(),
        collective_snapshot=_snapshot("acknowledgment_bridge"),
    )

    assert isinstance(advisory, dict)
    assert item == before

    metrics = agent.get_bridge_playbook_metrics()
    assert metrics["calls_total"] >= 1
    assert metrics["advisories_total"] >= 1
    assert metrics["step_links_total"] >= 1


def test_bridge_playbook_layer_does_not_change_routing_or_reuse_fields():
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    item = {
        "route_key": "r1",
        "graph_mode": "reuse",
        "_path_selection": {"route_key": "r1", "reason": "test"},
        "_graph_runtime": {"mode": "reuse"},
    }

    _ = agent.get_bridge_playbook_advisory(
        item,
        playbook=_playbook("Slow down pace"),
        bridge_graph_state=_bridge_graph("pacing_bridge"),
    )

    assert item["route_key"] == "r1"
    assert item["graph_mode"] == "reuse"
    assert item["_path_selection"]["route_key"] == "r1"
    assert item["_graph_runtime"]["mode"] == "reuse"
