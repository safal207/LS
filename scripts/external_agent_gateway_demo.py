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
    from agent.external_agent_gateway import ExternalAgentGateway, ExternalAgentGatewayRequest
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.external_agent_gateway import ExternalAgentGateway, ExternalAgentGatewayRequest  # type: ignore[no-redef]
    from modules.agent.resonance_agent import ResonanceAgent  # type: ignore[no-redef]


def main() -> int:
    artifact_root = ROOT / "artifacts" / "external-agent-gateway-demo"
    agent = ResonanceAgent(
        anchor=[],
        llm_fn=None,
        orientation="external-agent-gateway-demo",
    )
    agent._council_ledger_dir = artifact_root / "council-ledger"
    agent._council_quality_dir = artifact_root / "council-quality"
    agent._relational_episode_dir = artifact_root / "relational-episodes"
    agent._relation_memory_dir = artifact_root / "relation-memory"
    agent._relational_learning_dir = artifact_root / "relational-learning"

    gateway = ExternalAgentGateway(agent, default_orientation="external-agent-gateway-demo")
    request = ExternalAgentGatewayRequest(
        prompt="The team wants to release today, but security and ops are worried.",
        raw_output="Ship it now and clean up the issues later.",
        agent_id="speed-agent",
        agent_type="demo-external-agent",
        participants=[
            {
                "participant_id": "operator",
                "intent": "safe_release",
                "why": "protect users and keep trust",
                "needs": ["care", "stability"],
            },
            {
                "participant_id": "speed-agent",
                "intent": "ship_now",
                "why": "deadline pressure",
                "needs": ["speed", "urgency"],
            },
            {
                "participant_id": "security",
                "intent": "reduce_risk",
                "why": "avoid avoidable incident",
                "needs": ["evidence", "review"],
            },
        ],
        metadata={"demo": True, "source": "scripts/external_agent_gateway_demo.py"},
    )
    result = gateway.route_external_output(request)

    payload = {
        "scenario": "external speed agent under release pressure",
        "external_agent": result.get("external_agent_gateway"),
        "raw_agent_output": result.get("raw_agent_output"),
        "final_output": result.get("final_output"),
        "gateway_mode": result.get("gateway_mode"),
        "gateway_reason": result.get("gateway_reason"),
        "coordination": (
            result.get("personal_agent_gateway_metrics", {})
            .get("coordination_advisory_summary", {})
        ),
        "harmonic_state": (
            result.get("personal_agent_gateway_metrics", {})
            .get("harmonic_state_summary", {})
        ),
        "artifacts": {
            "ledger": result.get("council_contribution_ledger_artifact"),
            "quality": result.get("council_quality_artifact"),
        },
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
