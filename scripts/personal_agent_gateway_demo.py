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
        "alignment_score": 0.39,
        "tension_score": 0.71,
        "participants": [
            {"participant_id": "product"},
            {"participant_id": "ops"},
            {"participant_id": "security"},
        ],
        "pairwise_hotspots": [
            {
                "participants": ["product", "security"],
                "alignment": 0.31,
                "tension": 0.84,
                "mismatch_reasons": ["intent_conflict", "why_mismatch"],
            },
            {
                "participants": ["product", "ops"],
                "alignment": 0.42,
                "tension": 0.69,
                "mismatch_reasons": ["need_pressure_conflict"],
            },
        ],
    }


def _base_item() -> dict:
    return {
        "text": "The team wants to ship today, but the scene is tense.",
        "_why_strategy": {},
        "_copilot_output": {"pre_prompt": "slow + warm"},
        "_intent": {},
        "_why": {},
        "_llm_backend": {},
        "_path_selection": {"route_key": "r1", "reason": "demo"},
        "_graph_runtime": {"mode": "full_run"},
        "_trail_route": {},
        "_coalition": {},
        "_derived_module": {},
        "_care_cycle": {},
        "_network_plan": {},
        "_adequacy_report": {},
        "_observer_report": {},
        "_alignment_report": _alignment_report(),
        "_alignment_outcome": {},
        "_resonance_score": 0.58,
        "_cycle_id": "gateway-demo",
        "_relational_field": {
            "field_id": "gateway-demo-field",
            "timestamp": "2026-04-23T11:00:00Z",
            "tension_score": 0.61,
            "alignment_score": 0.44,
            "dominant_signal": "tension",
            "background_pressure": "release urgency",
            "foreground_expression": "pressure to decide too early",
        },
    }


def main() -> int:
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    item = _base_item()
    raw_output = "Ship it now and clean up the issues later."

    context = agent._prime_personal_agent_gateway_context(item)
    gateway = agent.get_personal_agent_gateway_decision(
        item,
        raw_output=raw_output,
        coordination_advisory_summary=context.get("coordination_advisory_summary"),
        harmonic_state_summary=context.get("harmonic_state_summary"),
        relational_policy_decision=context.get("relational_policy_decision"),
    )

    payload = {
        "scenario": "release pressure with cross-functional tension",
        "raw_agent_output": raw_output,
        "gateway_mode": gateway.get("gateway_mode"),
        "gateway_reason": gateway.get("gateway_reason"),
        "delivered_output": gateway.get("delivered_output"),
        "coordination_advisory_summary": context.get("coordination_advisory_summary"),
        "harmonic_state_summary": context.get("harmonic_state_summary"),
        "personal_agent_gateway": {
            key: value
            for key, value in gateway.items()
            if key != "delivered_output"
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
