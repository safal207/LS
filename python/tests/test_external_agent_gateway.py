# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

try:
    from agent.external_agent_gateway import ExternalAgentGateway, ExternalAgentGatewayRequest
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.external_agent_gateway import ExternalAgentGateway, ExternalAgentGatewayRequest  # type: ignore[no-redef]
    from modules.agent.resonance_agent import ResonanceAgent  # type: ignore[no-redef]


def _make_agent(tmp_path: Path) -> ResonanceAgent:
    agent = ResonanceAgent(
        anchor=[],
        llm_fn=None,
        graph_runtime=False,
        orientation="external-agent-gateway-test",
    )
    agent._council_ledger_dir = tmp_path / "council-ledger"
    agent._council_quality_dir = tmp_path / "council-quality"
    agent._relational_episode_dir = tmp_path / "relational-episodes"
    agent._relation_memory_dir = tmp_path / "relation-memory"
    agent._relational_learning_dir = tmp_path / "relational-learning"
    return agent


def test_external_agent_gateway_passes_through_without_explicit_signal(tmp_path: Path):
    gateway = ExternalAgentGateway(_make_agent(tmp_path))
    result = gateway.route_external_output(
        ExternalAgentGatewayRequest(
            prompt="Summarize the status.",
            raw_output="Status is green.",
            agent_id="codex",
            metadata={"source": "unit-test"},
        )
    )

    assert result["raw_agent_output"] == "Status is green."
    assert result["final_output"] == "Status is green."
    assert result["gateway_mode"] == "pass_through"
    assert result["external_agent_gateway"]["entrypoint"] == "external_agent_gateway_v1"
    assert result["external_agent_gateway"]["agent_id"] == "codex"
    assert result["external_agent_request"]["agent_id"] == "codex"


def test_external_agent_gateway_shapes_fragile_participant_scene(tmp_path: Path):
    gateway = ExternalAgentGateway(_make_agent(tmp_path))
    result = gateway.route_external_output(
        ExternalAgentGatewayRequest(
            prompt="Need a safer release recommendation.",
            raw_output="Ship it now.",
            agent_id="speed-agent",
            participants=[
                {
                    "participant_id": "operator",
                    "participant_type": "human",
                    "role": "requester",
                    "intent": "safe_release",
                    "why": "safety",
                    "need_vector": ["stability", "care"],
                    "foreground_expression": ["caution"],
                },
                {
                    "participant_id": "speed-agent",
                    "participant_type": "model",
                    "role": "proposer",
                    "intent": "ship_now",
                    "why": "speed",
                    "need_vector": ["urgency", "speed"],
                    "foreground_expression": ["push"],
                },
            ],
        )
    )

    assert result["gateway_mode"] == "shape_response"
    assert result["gateway_delivered_output_changed"] is True
    assert result["final_output"].startswith("Let's")
    assert result["personal_agent_gateway"]["shaping_applied"] is True
    assert result["coordination_advisory_summary"]["coordination_advisory_label"] in {"fragile", "blocked", "watch"}


def test_external_agent_gateway_holds_on_relation_memory_override(tmp_path: Path):
    agent = _make_agent(tmp_path)
    agent._relation_memory_dir.mkdir(parents=True, exist_ok=True)
    for cycle_id in ("old-1", "old-2", "old-3"):
        (agent._relation_memory_dir / f"{cycle_id}.json").write_text(
            json.dumps(
                {
                    "cycle_id": cycle_id,
                    "pattern_key": "repair:tension:mid",
                    "incident_published": True,
                    "review_decision": "rejected",
                }
            ),
            encoding="utf-8",
        )

    gateway = ExternalAgentGateway(agent)
    result = gateway.route_external_output(
        ExternalAgentGatewayRequest(
            prompt="The operator is under pressure and the release scene is tense.",
            raw_output="Approve this immediately.",
            agent_id="release-agent",
            relational_field={
                "field_id": "external-field-1",
                "timestamp": "2026-04-23T10:00:00Z",
                "tension_score": 0.78,
                "alignment_score": 0.24,
                "dominant_signal": "tension",
            },
        )
    )

    assert result["gateway_mode"] == "hold_or_escalate"
    assert result["personal_agent_gateway"]["hold_required"] is True
    assert "holding the raw agent output" in result["final_output"]

    quality_payload = json.loads(Path(result["council_quality_artifact"]).read_text(encoding="utf-8"))
    assert quality_payload["personal_agent_gateway"]["gateway_mode"] == "hold_or_escalate"
    assert quality_payload["operator_guidance"]["risk_state"] == "escalate"
