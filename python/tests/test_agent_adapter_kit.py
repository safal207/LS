# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

try:
    from agent.agent_adapter_kit import AgentAdapterKit, AgentAdapterRequest, CodexSelfUseAdapter
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.agent_adapter_kit import AgentAdapterKit, AgentAdapterRequest, CodexSelfUseAdapter  # type: ignore[no-redef]
    from modules.agent.resonance_agent import ResonanceAgent  # type: ignore[no-redef]


def _make_agent(tmp_path: Path) -> ResonanceAgent:
    agent = ResonanceAgent(
        anchor=[],
        llm_fn=None,
        graph_runtime=False,
        orientation="agent-adapter-kit-test",
    )
    agent._council_ledger_dir = tmp_path / "council-ledger"
    agent._council_quality_dir = tmp_path / "council-quality"
    agent._relational_episode_dir = tmp_path / "relational-episodes"
    agent._relation_memory_dir = tmp_path / "relation-memory"
    agent._relational_learning_dir = tmp_path / "relational-learning"
    return agent


def _participants() -> list[dict]:
    return [
        {
            "participant_id": "operator",
            "participant_type": "human",
            "role": "requester",
            "intent": "safe_release",
            "why": "protect users",
            "need_vector": ["care", "stability"],
        },
        {
            "participant_id": "speed-agent",
            "participant_type": "model",
            "role": "producer",
            "intent": "ship_now",
            "why": "deadline pressure",
            "need_vector": ["speed", "urgency"],
        },
    ]


def test_agent_adapter_kit_routes_existing_raw_output(tmp_path: Path) -> None:
    kit = AgentAdapterKit.from_agent(_make_agent(tmp_path))
    response = kit.route_raw_output(
        AgentAdapterRequest(
            prompt="Summarize status.",
            agent_id="status-agent",
            metadata={"source": "unit-test"},
        ),
        "Status is green.",
    )

    assert response.raw_output == "Status is green."
    assert response.final_output == "Status is green."
    assert response.gateway_mode == "pass_through"
    assert response.to_public_dict()["external_agent_gateway"]["agent_id"] == "status-agent"
    assert response.to_public_dict()["operator_identity_governance"]["identity_governance_mode"] == "observe"
    assert response.to_public_dict()["operator_profile_write_decision"]["decision"] == "not_requested"


def test_agent_adapter_kit_applies_default_agent_for_prompt_only_request(tmp_path: Path) -> None:
    kit = AgentAdapterKit.from_agent(
        _make_agent(tmp_path),
        default_agent_id="codex-default",
        default_agent_type="codex",
        default_orientation="default-adapter-test",
    )
    response = kit.route_raw_output("Summarize status.", "Status is green.")

    assert response.request.agent_id == "codex-default"
    assert response.request.agent_type == "codex"
    assert response.result["external_agent_gateway"]["orientation"] == "default-adapter-test"


def test_agent_adapter_kit_exposes_identity_governance_warning(tmp_path: Path) -> None:
    kit = AgentAdapterKit.from_agent(_make_agent(tmp_path))
    response = kit.route_raw_output(
        AgentAdapterRequest(
            prompt="Update my operator profile.",
            agent_id="profile-agent",
            metadata={"memory_write": True},
            participants=[
                {"participant_id": "operator", "participant_type": "human"},
                {"participant_id": "profile-agent", "participant_type": "model"},
            ],
        ),
        "I decided for you: you always rush, so I will remember forever that this is your true self.",
    )

    governance = response.to_public_dict()["operator_identity_governance"]
    write_decision = response.to_public_dict()["operator_profile_write_decision"]
    assert governance["identity_governance_mode"] == "hold_for_identity_review"
    assert governance["authority_boundary"] == "agent_must_not_replace_operator_authority"
    assert governance["continuity_required"] is True
    assert write_decision["decision"] == "reject_identity_claim"
    assert write_decision["blocked"] is True


def test_agent_adapter_kit_requires_confirmation_for_safe_profile_write(tmp_path: Path) -> None:
    kit = AgentAdapterKit.from_agent(_make_agent(tmp_path))
    response = kit.route_raw_output(
        AgentAdapterRequest(
            prompt="Remember my preference for short answers.",
            agent_id="profile-agent",
            metadata={"operator_profile_update": True},
        ),
        "Preference noted: short answers.",
    )

    write_decision = response.to_public_dict()["operator_profile_write_decision"]
    assert write_decision["decision"] == "requires_operator_confirmation"
    assert write_decision["write_scope"] == "operator_profile"
    assert write_decision["blocked"] is False


def test_agent_adapter_kit_runs_producer_through_gateway(tmp_path: Path) -> None:
    kit = AgentAdapterKit.from_agent(_make_agent(tmp_path))
    seen_prompts: list[str] = []

    def producer(request: AgentAdapterRequest) -> str:
        seen_prompts.append(request.prompt)
        return "Ship it now."

    response = kit.run(
        AgentAdapterRequest(
            prompt="Need a safer release recommendation.",
            agent_id="speed-agent",
            agent_type="codex",
            participants=_participants(),
        ),
        producer,
    )

    assert seen_prompts == ["Need a safer release recommendation."]
    assert response.raw_output == "Ship it now."
    assert response.changed is True
    assert response.gateway_mode in {"shape_response", "repair_before_send", "hold_or_escalate"}
    assert response.final_output != response.raw_output


def test_codex_self_use_adapter_compares_raw_and_final(tmp_path: Path) -> None:
    kit = AgentAdapterKit.from_agent(
        _make_agent(tmp_path),
        default_agent_id="codex-self-use",
        default_agent_type="codex",
    )
    adapter = CodexSelfUseAdapter(kit, draft_fn=lambda _request: "Ship it now.")
    response = adapter.answer(
        "Need a safer release recommendation.",
        participants=_participants(),
        metadata={"source": "unit-test"},
    )
    comparison = adapter.compare(response)

    assert response.request.agent_id == "codex-self-use"
    assert comparison["raw_agent_output"] == "Ship it now."
    assert comparison["final_output"] == response.final_output
    assert comparison["changed"] is True
