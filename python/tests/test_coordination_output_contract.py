# -*- coding: utf-8 -*-
"""Contract tests for coordination objects in ResonanceAgent._build_output."""
from __future__ import annotations

import json
from pathlib import Path

try:
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.resonance_agent import ResonanceAgent


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
_ALLOWED_COORDINATION_STATE_LABELS = {
    "coherent",
    "strained",
    "fragmented",
    "unstable",
    "escalating",
}
_ALLOWED_STABILIZATION_MODES = {
    "crisis_first",
    "high_priority_first",
    "quick_wins_first",
    "observe_and_stage",
    "unknown",
}


def _base_item() -> dict:
    return {
        "text": "contract test",
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


def test_coordination_output_contract_shape_enums_and_boundedness():
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    output = agent._build_output(_base_item(), final_output="ok", generation_time=0.01, cycle_id="cid")

    required_top_level = {
        "collective_coordination_snapshot",
        "collective_coordination_metrics",
        "bridge_stabilization_order",
        "bridge_stabilization_metrics",
        "bridge_playbook_advisory",
        "bridge_playbook_metrics",
    }
    assert required_top_level.issubset(output.keys())

    for key in required_top_level:
        assert isinstance(output[key], dict)

    snapshot = output["collective_coordination_snapshot"]
    order = output["bridge_stabilization_order"]
    advisory = output["bridge_playbook_advisory"]

    assert {
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
    }.issubset(snapshot.keys())

    assert {
        "ordered_edges",
        "urgent_edges",
        "early_stabilization_edges",
        "quick_win_edges",
        "defer_edges",
        "dominant_stabilization_mode",
        "summary_reason",
    }.issubset(order.keys())

    assert {
        "playbook_alignment_label",
        "playbook_alignment_score",
        "step_links",
        "top_supported_steps",
        "top_weak_steps",
        "dominant_bridge_playbook_fit",
        "summary_reason",
    }.issubset(advisory.keys())

    # Metrics: verify objects and critical stable keys.
    assert {"calls_total", "snapshots_total", "avg_coordination_risk"}.issubset(
        output["collective_coordination_metrics"].keys()
    )
    assert {"calls_total", "orders_total", "avg_stabilization_score"}.issubset(
        output["bridge_stabilization_metrics"].keys()
    )
    assert {"calls_total", "advisories_total", "avg_playbook_alignment_score"}.issubset(
        output["bridge_playbook_metrics"].keys()
    )

    # Enum stability.
    assert snapshot["coordination_state_label"] in _ALLOWED_COORDINATION_STATE_LABELS
    assert snapshot["dominant_stabilization_mode"] in _ALLOWED_STABILIZATION_MODES
    assert order["dominant_stabilization_mode"] in _ALLOWED_STABILIZATION_MODES
    assert advisory["playbook_alignment_label"] in _ALLOWED_PLAYBOOK_ALIGNMENT_LABELS
    assert advisory["dominant_bridge_playbook_fit"] in _ALLOWED_BRIDGE_PLAYBOOK_FIT

    # Boundedness and compact reasons.
    assert len(snapshot["top_bridge_candidates"]) <= 3
    assert len(snapshot["top_stabilization_edges"]) <= 3
    assert len(snapshot["top_risk_parties"]) <= 3
    assert len(advisory["step_links"]) <= 10
    assert len(advisory["top_supported_steps"]) <= 3
    assert len(advisory["top_weak_steps"]) <= 3

    assert isinstance(snapshot["summary_reason"], str) and 0 < len(snapshot["summary_reason"]) <= 140
    assert isinstance(order["summary_reason"], str) and 0 < len(order["summary_reason"]) <= 140
    assert isinstance(advisory["summary_reason"], str) and 0 < len(advisory["summary_reason"]) <= 140


def test_coordination_output_contract_graceful_fallback_empty_shape():
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    weak_item = _base_item()
    weak_item["text"] = ""
    weak_item["_alignment_report"] = {}

    output = agent._build_output(weak_item, final_output="", generation_time=0.0, cycle_id="cid-empty")

    assert isinstance(output["collective_coordination_snapshot"], dict)
    assert isinstance(output["bridge_stabilization_order"], dict)
    assert isinstance(output["bridge_playbook_advisory"], dict)

    snapshot = output["collective_coordination_snapshot"]
    order = output["bridge_stabilization_order"]
    advisory = output["bridge_playbook_advisory"]

    # Fallback enums remain valid, with bounded empty arrays.
    assert snapshot["coordination_state_label"] in _ALLOWED_COORDINATION_STATE_LABELS
    assert snapshot["dominant_stabilization_mode"] in _ALLOWED_STABILIZATION_MODES
    assert order["dominant_stabilization_mode"] in _ALLOWED_STABILIZATION_MODES
    assert advisory["playbook_alignment_label"] in _ALLOWED_PLAYBOOK_ALIGNMENT_LABELS
    assert advisory["dominant_bridge_playbook_fit"] in _ALLOWED_BRIDGE_PLAYBOOK_FIT

    assert snapshot["top_bridge_candidates"] == []
    assert snapshot["top_stabilization_edges"] == []
    assert snapshot["top_risk_parties"] == []
    assert advisory["step_links"] == []
    assert advisory["top_supported_steps"] == []
    assert advisory["top_weak_steps"] == []
def test_build_output_emits_council_ledger_artifact(tmp_path):
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    agent._council_ledger_dir = tmp_path / "council-ledger"
    agent.get_alignment_strategy_recommendations = lambda _item: [
        {
            "strategy_id": "bridge-1",
            "title": "Bridge strategy",
            "summary": "Acknowledge common ground first",
            "support_count": 4,
            "effective_rate": 0.8,
            "recommended_actions": ["common ground", "we both"],
        }
    ]

    item = _base_item()
    item["_llm_backend"] = {"provider": "openai", "model": "gpt-test", "latency_ms": 1200}
    item["_alignment_outcome"] = {
        "guidance_effective": True,
        "post_goal_alignment_score": 0.81,
        "softening_score": 0.73,
    }
    item["_observer_report"] = {"status": "stable"}
    item["_cooperative"] = {
        "participants": ["local:qwen", "web:gpt"],
        "route_key": "mesh:cooperative",
        "trust_score": 0.67,
        "success": True,
    }

    output = agent._build_output(
        item,
        final_output="We both want a safe path and common ground before action.",
        generation_time=0.02,
        cycle_id="cid-ledger",
    )

    artifact_path = output["council_contribution_ledger_artifact"]
    assert artifact_path is not None
    artifact = Path(artifact_path)
    assert artifact.exists()

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["cycle_id"] == "cid-ledger"
    assert payload["task_id"] == "cid-ledger"
    assert payload["final_decision"]["selected_route"] == "r1"
    assert payload["outcome"]["success"] is True
    assert any(p["model_type"] == "primary_llm" for p in payload["participants"])
    assert any(p["model_type"] == "advisory_strategy" for p in payload["participants"])
    assert output["council_contribution_ledger"]["cycle_id"] == "cid-ledger"


def test_build_output_emits_relational_edge_update_preview(tmp_path) -> None:
    try:
        from graph.runtime import GraphMemoryRuntime
    except ImportError:
        from modules.graph.runtime import GraphMemoryRuntime

    agent = ResonanceAgent(
        anchor=[],
        llm_fn=None,
        graph_runtime=GraphMemoryRuntime(store_path=tmp_path / "cases.jsonl"),
    )
    item = _base_item()
    item["_operator_review"] = {"decision": "approved"}
    item["_incident_published"] = False
    item["_relation_edge_strength_before"] = 0.42
    item["_receiver_resonance_score"] = 0.81
    item["_relational_field"] = {
        "alignment_score": 0.24,
        "metadata": {"relational_coherence": 0.66},
    }

    output = agent._build_output(
        item,
        final_output="ok",
        generation_time=0.01,
        cycle_id="cid-edge-preview",
    )

    preview = output["relational_edge_update_preview"]
    policy = output["relational_policy_decision"]
    assert isinstance(preview, dict)
    assert isinstance(policy, dict)
    assert preview["strength_before"] == 0.42
    assert 0.0 <= preview["strength_after"] <= 1.0
    assert preview["strength_after"] > preview["strength_before"]
    assert preview["applied_delta"] > 0.0
    assert preview["review_attention_required"] is False
    assert preview["route_guidance"] == "continue_current_route"
    assert preview["reason_codes"] == [
        "approved_review",
        "high_receiver_resonance",
    ]
    assert output["relational_coherence"] == 0.66
    assert policy["policy_state"] == "continue"
    assert policy["review_attention_required"] is False
    assert policy["escalation_required"] is False


def test_build_output_emits_relational_edge_update_artifact(tmp_path) -> None:
    try:
        from graph.runtime import GraphMemoryRuntime
    except ImportError:
        from modules.graph.runtime import GraphMemoryRuntime

    agent = ResonanceAgent(
        anchor=[],
        llm_fn=None,
        graph_runtime=GraphMemoryRuntime(store_path=tmp_path / "cases.jsonl"),
    )
    agent._relational_edge_update_dir = tmp_path / "relational-edge-updates"
    item = _base_item()
    item["_operator_review"] = {"decision": "rejected"}
    item["_incident_published"] = True
    item["_relation_edge_strength_before"] = 0.64
    item["_receiver_resonance_score"] = 0.21
    item["_relational_field"] = {
        "dominant_signal": "tension",
        "alignment_score": 0.18,
        "metadata": {"relational_coherence": 0.21},
    }

    output = agent._build_output(
        item,
        final_output="ok",
        generation_time=0.01,
        cycle_id="cid-edge-artifact",
    )

    artifact_path = output["relational_edge_update_artifact"]
    assert artifact_path is not None
    artifact = Path(artifact_path)
    assert artifact.exists()

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    policy = output["relational_policy_decision"]
    assert payload["cycle_id"] == "cid-edge-artifact"
    assert payload["pattern_key"] == "tension"
    assert payload["selected_route"] == "r1"
    assert payload["review_decision"] == "rejected"
    assert payload["incident_published"] is True
    assert payload["relational_coherence"] == 0.21
    assert payload["review_attention_required"] is True
    assert payload["route_guidance"] == "validate_current_route"
    assert payload["strength_before"] == 0.64
    assert payload["strength_after"] < payload["strength_before"]
    assert payload["reason_codes"] == [
        "rejected_review",
        "incident_published",
        "low_receiver_resonance",
        "low_relational_coherence",
    ]
    assert policy["policy_state"] == "escalate"
    assert policy["review_attention_required"] is True
    assert policy["escalation_required"] is True


def test_build_output_uses_persisted_relation_edge_strength_from_store(tmp_path) -> None:
    try:
        from graph.runtime import GraphMemoryRuntime
    except ImportError:
        from modules.graph.runtime import GraphMemoryRuntime

    graph_runtime = GraphMemoryRuntime(store_path=tmp_path / "cases.jsonl")
    graph_runtime.store.store_relational_edge_update(
        {
            "cycle_id": "cid-prev",
            "pattern_key": "tension",
            "selected_route": "r1",
            "strength_after": 0.74,
        }
    )
    agent = ResonanceAgent(anchor=[], llm_fn=None, graph_runtime=graph_runtime)
    item = _base_item()
    item["_operator_review"] = {"decision": "approved"}
    item["_receiver_resonance_score"] = 0.9
    item["_relational_field"] = {
        "dominant_signal": "tension",
        "alignment_score": 0.18,
        "metadata": {"relational_coherence": 0.29},
    }

    output = agent._build_output(
        item,
        final_output="ok",
        generation_time=0.01,
        cycle_id="cid-uses-store",
    )

    preview = output["relational_edge_update_preview"]
    policy = output["relational_policy_decision"]
    assert preview["strength_before"] == 0.74
    assert preview["strength_after"] > 0.74
    assert policy["history_match_count"] >= 1


def test_build_output_escalates_when_history_has_multiple_adverse_matches(tmp_path) -> None:
    try:
        from graph.runtime import GraphMemoryRuntime
    except ImportError:
        from modules.graph.runtime import GraphMemoryRuntime

    graph_runtime = GraphMemoryRuntime(store_path=tmp_path / "cases.jsonl")
    graph_runtime.store.store_relational_edge_update(
        {
            "cycle_id": "cid-prev-1",
            "pattern_key": "tension",
            "selected_route": "r1",
            "review_decision": "rejected",
            "incident_published": False,
            "reason_codes": ["low_relational_coherence"],
            "strength_after": 0.31,
        }
    )
    graph_runtime.store.store_relational_edge_update(
        {
            "cycle_id": "cid-prev-2",
            "pattern_key": "tension",
            "selected_route": "r1",
            "review_decision": "closed",
            "incident_published": False,
            "reason_codes": ["low_relational_coherence"],
            "strength_after": 0.24,
        }
    )

    agent = ResonanceAgent(anchor=[], llm_fn=None, graph_runtime=graph_runtime)
    item = _base_item()
    item["_receiver_resonance_score"] = 0.42
    item["_relational_field"] = {
        "dominant_signal": "tension",
        "alignment_score": 0.22,
        "metadata": {"relational_coherence": 0.28},
    }

    output = agent._build_output(
        item,
        final_output="ok",
        generation_time=0.01,
        cycle_id="cid-history-escalate",
    )

    policy = output["relational_policy_decision"]
    assert policy["policy_state"] == "escalate"
    assert policy["review_attention_required"] is True
    assert policy["escalation_required"] is True
    assert policy["adverse_match_count"] >= 2
