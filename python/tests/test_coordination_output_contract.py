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
_ALLOWED_HARMONIC_CENTERS = {
    "coherence",
    "stabilization",
    "translation",
    "reframing",
    "exploration",
    "defense",
    "repair",
    "insufficient_context",
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
_ALLOWED_HARMONIC_RESOLUTION = {
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
_ALLOWED_HARMONIC_MODULATION = {
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
_ALLOWED_GATEWAY_MODES = {
    "pass_through",
    "shape_response",
    "repair_before_send",
    "hold_or_escalate",
}
_ALLOWED_GATEWAY_POSTURES = {
    "aligned",
    "fragile",
    "repair",
    "escalate",
    "insufficient_context",
}
_ALLOWED_GATEWAY_TRANSFORMATIONS = {
    "none",
    "tonal_wrap",
    "repair_wrap",
    "hold_notice",
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
        "harmonic_state_summary",
        "harmonic_state_metrics",
        "raw_agent_output",
        "personal_agent_gateway",
        "personal_agent_gateway_metrics",
        "gateway_mode",
        "gateway_reason",
        "gateway_delivered_output_changed",
    }
    assert required_top_level.issubset(output.keys())

    for key in {
        "collective_coordination_snapshot",
        "collective_coordination_metrics",
        "bridge_stabilization_order",
        "bridge_stabilization_metrics",
        "bridge_playbook_advisory",
        "bridge_playbook_metrics",
        "harmonic_state_summary",
        "harmonic_state_metrics",
        "personal_agent_gateway",
        "personal_agent_gateway_metrics",
    }:
        assert isinstance(output[key], dict)

    snapshot = output["collective_coordination_snapshot"]
    order = output["bridge_stabilization_order"]
    advisory = output["bridge_playbook_advisory"]
    harmonic = output["harmonic_state_summary"]
    gateway = output["personal_agent_gateway"]

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
    assert {
        "harmonic_center",
        "harmonic_interval_label",
        "harmonic_tension",
        "harmonic_stability",
        "resolution_direction",
        "modulation_candidate",
        "harmonic_summary_reason",
    }.issubset(harmonic.keys())
    assert {
        "gateway_mode",
        "quality_posture",
        "transformation_label",
        "delivered_output_changed",
        "shaping_applied",
        "repair_required",
        "escalation_required",
        "hold_required",
        "coordination_advisory_label",
        "harmonic_center",
        "harmonic_interval_label",
        "resolution_direction",
        "raw_output_excerpt",
        "delivered_output_excerpt",
        "gateway_reason",
    }.issubset(gateway.keys())
    assert "delivered_output" not in gateway

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
    assert {"calls_total", "summaries_total", "avg_harmonic_tension"}.issubset(
        output["harmonic_state_metrics"].keys()
    )
    assert {"calls_total", "decisions_total", "shape_response_total"}.issubset(
        output["personal_agent_gateway_metrics"].keys()
    )

    # Enum stability.
    assert snapshot["coordination_state_label"] in _ALLOWED_COORDINATION_STATE_LABELS
    assert snapshot["dominant_stabilization_mode"] in _ALLOWED_STABILIZATION_MODES
    assert order["dominant_stabilization_mode"] in _ALLOWED_STABILIZATION_MODES
    assert advisory["playbook_alignment_label"] in _ALLOWED_PLAYBOOK_ALIGNMENT_LABELS
    assert advisory["dominant_bridge_playbook_fit"] in _ALLOWED_BRIDGE_PLAYBOOK_FIT
    assert harmonic["harmonic_center"] in _ALLOWED_HARMONIC_CENTERS
    assert harmonic["harmonic_interval_label"] in _ALLOWED_HARMONIC_INTERVALS
    assert harmonic["resolution_direction"] in _ALLOWED_HARMONIC_RESOLUTION
    assert harmonic["modulation_candidate"] in _ALLOWED_HARMONIC_MODULATION
    assert output["gateway_mode"] in _ALLOWED_GATEWAY_MODES
    assert gateway["gateway_mode"] in _ALLOWED_GATEWAY_MODES
    assert gateway["quality_posture"] in _ALLOWED_GATEWAY_POSTURES
    assert gateway["transformation_label"] in _ALLOWED_GATEWAY_TRANSFORMATIONS
    assert gateway["coordination_advisory_label"] in {
        "clear",
        "watch",
        "fragile",
        "blocked",
        "escalate",
        "insufficient_context",
    }
    assert gateway["harmonic_center"] in _ALLOWED_HARMONIC_CENTERS
    assert gateway["harmonic_interval_label"] in _ALLOWED_HARMONIC_INTERVALS
    assert gateway["resolution_direction"] in _ALLOWED_HARMONIC_RESOLUTION

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
    assert isinstance(harmonic["harmonic_summary_reason"], str) and 0 < len(harmonic["harmonic_summary_reason"]) <= 140
    assert isinstance(output["gateway_reason"], str) and 0 < len(output["gateway_reason"]) <= 140
    assert isinstance(gateway["gateway_reason"], str) and 0 < len(gateway["gateway_reason"]) <= 140
    assert isinstance(output["raw_agent_output"], str)
    assert isinstance(output["gateway_delivered_output_changed"], bool)


def test_coordination_output_contract_graceful_fallback_empty_shape():
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    weak_item = _base_item()
    weak_item["text"] = ""
    weak_item["_alignment_report"] = {}

    output = agent._build_output(weak_item, final_output="", generation_time=0.0, cycle_id="cid-empty")

    assert isinstance(output["collective_coordination_snapshot"], dict)
    assert isinstance(output["bridge_stabilization_order"], dict)
    assert isinstance(output["bridge_playbook_advisory"], dict)
    assert isinstance(output["personal_agent_gateway"], dict)
    assert isinstance(output["personal_agent_gateway_metrics"], dict)

    snapshot = output["collective_coordination_snapshot"]
    order = output["bridge_stabilization_order"]
    advisory = output["bridge_playbook_advisory"]
    harmonic = output["harmonic_state_summary"]
    gateway = output["personal_agent_gateway"]

    # Fallback enums remain valid, with bounded empty arrays.
    assert snapshot["coordination_state_label"] in _ALLOWED_COORDINATION_STATE_LABELS
    assert snapshot["dominant_stabilization_mode"] in _ALLOWED_STABILIZATION_MODES
    assert order["dominant_stabilization_mode"] in _ALLOWED_STABILIZATION_MODES
    assert advisory["playbook_alignment_label"] in _ALLOWED_PLAYBOOK_ALIGNMENT_LABELS
    assert advisory["dominant_bridge_playbook_fit"] in _ALLOWED_BRIDGE_PLAYBOOK_FIT
    assert harmonic["harmonic_center"] in _ALLOWED_HARMONIC_CENTERS
    assert harmonic["harmonic_interval_label"] in _ALLOWED_HARMONIC_INTERVALS
    assert harmonic["resolution_direction"] in _ALLOWED_HARMONIC_RESOLUTION
    assert harmonic["modulation_candidate"] in _ALLOWED_HARMONIC_MODULATION
    assert output["gateway_mode"] in _ALLOWED_GATEWAY_MODES
    assert gateway["gateway_mode"] in _ALLOWED_GATEWAY_MODES
    assert gateway["quality_posture"] in _ALLOWED_GATEWAY_POSTURES

    assert snapshot["top_bridge_candidates"] == []
    assert snapshot["top_stabilization_edges"] == []
    assert snapshot["top_risk_parties"] == []
    assert advisory["step_links"] == []
    assert advisory["top_supported_steps"] == []
    assert advisory["top_weak_steps"] == []
    assert output["raw_agent_output"] == ""
    assert gateway["raw_output_excerpt"] == ""
    assert gateway["delivered_output_excerpt"] == ""


def test_build_output_emits_council_ledger_artifact(tmp_path):
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    agent._council_ledger_dir = tmp_path / "council-ledger"
    agent._council_quality_dir = tmp_path / "council-quality"
    agent._relational_episode_dir = tmp_path / "relational-episodes"
    agent._relation_memory_dir = tmp_path / "relation-memory"
    agent._relational_learning_dir = tmp_path / "relational-learning"
    agent._council_quality_dir.mkdir(parents=True, exist_ok=True)
    (agent._council_quality_dir / "old-rule.json").write_text(
        json.dumps(
            {
                "cycle_id": "old-rule",
                "operator_guidance": {
                    "rule_hits": ["repair_from_tension_or_low_safety"],
                    "safety_mode": "repair_first",
                },
                "operator_review": {"decision": "approved"},
                "liminalqa": {"incident": {"published": False}},
            }
        ),
        encoding="utf-8",
    )
    (agent._council_quality_dir / "old-rule-2.json").write_text(
        json.dumps(
            {
                "cycle_id": "old-rule-2",
                "operator_guidance": {
                    "rule_hits": ["repair_from_tension_or_low_safety"],
                    "safety_mode": "repair_first",
                },
                "operator_review": {"decision": "rejected"},
                "liminalqa": {"incident": {"published": True}},
            }
        ),
        encoding="utf-8",
    )
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
    item["_relational_field"] = {
        "field_id": "field-001",
        "timestamp": "2026-04-09T10:00:00Z",
        "tension_score": 0.78,
        "alignment_score": 0.24,
        "dominant_signal": "tension",
        "background_pressure": "deadline pressure",
        "foreground_expression": "friction in wording",
        "notes": ["Needs decompression before approval"],
    }

    output = agent._build_output(
        item,
        final_output="We both want a safe path and common ground before action.",
        generation_time=0.02,
        cycle_id="cid-ledger",
    )

    assert output["raw_agent_output"] == "We both want a safe path and common ground before action."
    assert output["gateway_mode"] == "repair_before_send"
    assert output["gateway_delivered_output_changed"] is True
    assert output["personal_agent_gateway"]["gateway_mode"] == "repair_before_send"
    assert output["personal_agent_gateway"]["repair_required"] is True
    assert output["personal_agent_gateway"]["transformation_label"] == "repair_wrap"
    assert "delivered_output" not in output["personal_agent_gateway"]

    artifact_path = output["council_contribution_ledger_artifact"]
    assert artifact_path is not None
    artifact = Path(artifact_path)
    assert artifact.exists()

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert payload["cycle_id"] == "cid-ledger"
    assert payload["task_id"] == "cid-ledger"
    assert payload["final_decision"]["selected_route"] == "r1"
    assert payload["outcome"]["success"] is True
    assert payload["outcome"]["receiver_type"] == "model"
    assert payload["outcome"]["receiver_acceptance_label"] == "accepted"
    assert payload["outcome"]["receiver_resonance_score"] >= 0.7
    assert any(p["model_type"] == "primary_llm" for p in payload["participants"])
    assert any(p["model_type"] == "advisory_strategy" for p in payload["participants"])
    assert output["council_contribution_ledger"]["cycle_id"] == "cid-ledger"
    assert output["council_cel_sync"] is not None
    assert output["council_cel_sync"]["proposal_id"] == "cid-ledger"
    assert len(output["council_cel_sync"]["reputation_updates"]) >= 1
    assert len(output["council_cel_sync"]["merit_updates"]) >= 1
    assert output["council_cel_sync"]["merit_updates"][0]["network_effect_bonus"] >= 0

    relational_episode_artifact_path = output["relational_episode_artifact"]
    assert relational_episode_artifact_path is not None
    relational_episode_artifact = Path(relational_episode_artifact_path)
    assert relational_episode_artifact.exists()

    relational_episode_payload = json.loads(relational_episode_artifact.read_text(encoding="utf-8"))
    assert relational_episode_payload["cycle_id"] == "cid-ledger"
    assert relational_episode_payload["council_ledger_path"] == artifact_path
    assert relational_episode_payload["selected_route"] == "r1"
    assert relational_episode_payload["relational_field"]["field_id"] == "field-001"
    assert relational_episode_payload["relational_summary"]["dominant_signal"] == "tension"
    assert relational_episode_payload["relational_summary"]["recommended_mode"] == "decompress_and_repair"
    assert relational_episode_payload["operator_guidance"]["risk_state"] == "repair"
    assert relational_episode_payload["operator_guidance"]["approval_posture"] == "hold_and_repair"
    assert relational_episode_payload["operator_guidance"]["route_strategy"] == "repair_then_reroute"
    assert relational_episode_payload["operator_guidance"]["rerun_required"] is True
    assert relational_episode_payload["personal_agent_gateway"]["gateway_mode"] == "repair_before_send"
    assert relational_episode_payload["personal_agent_gateway"]["repair_required"] is True

    relation_memory_artifact_path = output["relation_memory_artifact"]
    assert relation_memory_artifact_path is not None
    relation_memory_artifact = Path(relation_memory_artifact_path)
    assert relation_memory_artifact.exists()

    relation_memory_payload = json.loads(relation_memory_artifact.read_text(encoding="utf-8"))
    assert relation_memory_payload["cycle_id"] == "cid-ledger"
    assert relation_memory_payload["risk_state"] == "repair"
    assert relation_memory_payload["dominant_signal"] == "tension"
    assert relation_memory_payload["pattern_key"].startswith("repair:tension:")
    assert relation_memory_payload["personal_agent_gateway"]["gateway_mode"] == "repair_before_send"

    quality_artifact_path = output["council_quality_artifact"]
    assert quality_artifact_path is not None
    quality_artifact = Path(quality_artifact_path)
    assert quality_artifact.exists()

    quality_payload = json.loads(quality_artifact.read_text(encoding="utf-8"))
    assert quality_payload["cycle_id"] == "cid-ledger"
    assert quality_payload["council_ledger_path"] == artifact_path
    assert quality_payload["relational_episode_path"] == relational_episode_artifact_path
    assert quality_payload["relation_memory_path"] == relation_memory_artifact_path
    assert quality_payload["quality_score"] == output["council_cel_sync"]["quality_score"]
    assert quality_payload["relation_adjusted_quality_score"] <= quality_payload["quality_score"]
    assert quality_payload["relational_field"]["tension_score"] == 0.78
    assert quality_payload["relational_field"]["alignment_score"] == 0.24
    assert quality_payload["relational_field"]["relation_safety_score"] == 0.23
    assert quality_payload["relational_field"]["recommended_mode"] == "decompress_and_repair"
    assert quality_payload["operator_guidance"]["risk_state"] == "repair"
    assert quality_payload["operator_guidance"]["approval_posture"] == "hold_and_repair"
    assert quality_payload["operator_guidance"]["route_strategy"] == "repair_then_reroute"
    assert quality_payload["operator_guidance"]["safety_mode"] == "repair_first"
    assert quality_payload["operator_guidance"]["policy_engine_version"] == "relational-policy-v1"
    assert "repair_from_tension_or_low_safety" in quality_payload["operator_guidance"]["rule_hits"]
    assert quality_payload["operator_guidance"]["requires_human_review"] is False
    assert "Pause approval" in quality_payload["operator_guidance"]["suggested_operator_action"]
    assert quality_payload["council_outcome"]["selected_route"] == "r1"
    assert quality_payload["council_outcome"]["route_strategy"] == "repair_then_reroute"
    assert quality_payload["council_outcome"]["safety_mode"] == "repair_first"
    assert quality_payload["council_outcome"]["route_memory_adjusted"] is False
    assert quality_payload["council_outcome"]["route_memory_match_count"] == 0
    assert quality_payload["personal_agent_gateway"]["gateway_mode"] == "repair_before_send"
    assert quality_payload["personal_agent_gateway"]["repair_required"] is True
    assert quality_payload["attribution"]["best_contributor_model_id"] != "n/a"
    assert len(quality_payload["cel"]["contribution_records"]) >= 1
    assert len(quality_payload["cel"]["reputation_updates"]) >= 1
    assert len(quality_payload["cel"]["merit_updates"]) >= 1
    assert quality_payload["liminalqa"]["published"] is False

    learning_artifact_path = output["relational_learning_artifact"]
    assert learning_artifact_path is not None
    learning_payload = json.loads(Path(learning_artifact_path).read_text(encoding="utf-8"))
    assert learning_payload["cycle_id"] == "cid-ledger"
    assert learning_payload["current_safety_mode"] == "repair_first"
    assert "repair_from_tension_or_low_safety" in learning_payload["current_rule_hits"]
    assert learning_payload["heuristic_count"] >= 1
    assert learning_payload["top_effective_rules"][0]["rule"] == "repair_from_tension_or_low_safety"
    assert learning_payload["top_effective_rules"][0]["seen"] == 2


def test_relation_memory_can_escalate_repeated_bad_pattern(tmp_path):
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    agent._council_ledger_dir = tmp_path / "council-ledger"
    agent._council_quality_dir = tmp_path / "council-quality"
    agent._relational_episode_dir = tmp_path / "relational-episodes"
    agent._relation_memory_dir = tmp_path / "relation-memory"
    agent._relation_memory_dir.mkdir(parents=True, exist_ok=True)
    prior_patterns = [
        ("old-1", "repair:tension:low", "rejected"),
        ("old-2", "repair:tension:low", "closed"),
        ("old-3", "repair:tension:mid", "rejected"),
        ("old-4", "repair:tension:mid", "closed"),
        ("old-5", "repair:tension:high", "rejected"),
        ("old-6", "repair:tension:high", "closed"),
    ]
    for cycle_id, pattern_key, review_decision in prior_patterns:
        (agent._relation_memory_dir / f"{cycle_id}.json").write_text(
            json.dumps(
                {
                    "cycle_id": cycle_id,
                    "pattern_key": pattern_key,
                    "incident_published": True,
                    "review_decision": review_decision,
                }
            ),
            encoding="utf-8",
        )

    item = _base_item()
    item["_llm_backend"] = {"provider": "openai", "model": "gpt-test", "latency_ms": 1200}
    item["_relational_field"] = {
        "field_id": "field-001",
        "timestamp": "2026-04-09T10:00:00Z",
        "tension_score": 0.78,
        "alignment_score": 0.24,
        "dominant_signal": "tension",
    }

    output = agent._build_output(
        item,
        final_output="Escalate this path.",
        generation_time=0.02,
        cycle_id="cid-memory-escalate",
    )

    quality_payload = json.loads(Path(output["council_quality_artifact"]).read_text(encoding="utf-8"))
    assert quality_payload["operator_guidance"]["risk_state"] == "escalate"
    assert quality_payload["operator_guidance"]["approval_posture"] == "human_escalation"
    assert quality_payload["operator_guidance"]["safety_mode"] == "freeze"
    assert quality_payload["operator_guidance"]["policy_engine_version"] == "relational-policy-v1"
    assert "memory_freeze_override" in quality_payload["operator_guidance"]["rule_hits"]
    assert quality_payload["operator_guidance"]["memory_context"]["policy_adjusted"] is True
    assert quality_payload["personal_agent_gateway"]["gateway_mode"] == "hold_or_escalate"
    assert quality_payload["personal_agent_gateway"]["hold_required"] is True
