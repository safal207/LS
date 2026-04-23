from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))
MODULES_ROOT = PYTHON_ROOT / "modules"
if str(MODULES_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULES_ROOT))


try:
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.resonance_agent import ResonanceAgent  # type: ignore[no-redef]


def _alignment_report() -> dict:
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


def main() -> int:
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    item = {
        "text": "Cross-functional launch alignment is breaking down.",
        "_alignment_report": _alignment_report(),
        "_relational_field": {
            "tension_score": 0.74,
            "alignment_score": 0.29,
            "dominant_signal": "tension",
        },
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
    harmonic_summary = agent.get_harmonic_state_summary(
        item,
        collective_coordination_snapshot=snapshot,
        bridge_stabilization_order=stabilization_order,
        bridge_playbook_advisory=advisory,
        coordination_advisory_summary=coordination_summary,
    )

    payload = {
        "scenario": "cross-functional release pressure",
        "multi_party_alignment_state": multi_party,
        "bridge_graph_state": bridge_graph,
        "bridge_stabilization_order": stabilization_order,
        "collective_coordination_snapshot": snapshot,
        "bridge_playbook_advisory": advisory,
        "coordination_advisory_summary": coordination_summary,
        "harmonic_state_summary": harmonic_summary,
        "harmonic_state_metrics": agent.get_harmonic_state_metrics(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
