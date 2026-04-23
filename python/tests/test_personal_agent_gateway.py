# -*- coding: utf-8 -*-
from __future__ import annotations

try:
    from agent.personal_agent_gateway import (
        PersonalAgentGatewayMetrics,
        build_personal_agent_gateway_decision,
    )
    from agent.resonance_agent import ResonanceAgent
    from graph.runtime import GraphRuntimeDecision
    from llm.backends.base import LLMResponse
except ImportError:
    from modules.agent.personal_agent_gateway import (  # type: ignore[no-redef]
        PersonalAgentGatewayMetrics,
        build_personal_agent_gateway_decision,
    )
    from modules.agent.resonance_agent import ResonanceAgent  # type: ignore[no-redef]
    from graph.runtime import GraphRuntimeDecision  # type: ignore[no-redef]
    from modules.llm.backends.base import LLMResponse  # type: ignore[no-redef]


def _base_item() -> dict:
    return {
        "text": "gateway test",
        "_why_strategy": {},
        "_copilot_output": {"pre_prompt": "slow + warm"},
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


class _GatewayBackend:
    def generate(self, *args, **kwargs):
        return LLMResponse(
            text="Ship it now.",
            model="gateway-test",
            provider="local",
            latency_ms=5.0,
        )


class _GatewayGraphRuntime:
    def process(self, item, thread_context=None):
        return GraphRuntimeDecision(
            mode="full_run",
            matched_case_id=None,
            similarity=0.0,
            prior_answer=None,
            prior_case=None,
            reason="test-full-run",
        )

    def remember_success(
        self,
        item,
        *,
        answer_text,
        thread_context=None,
        answer_quality=None,
        contributors=None,
    ):
        return None

    def inject_resonance_hints(self, item, *, thread_context=None, top_k=3):
        item["_resonance_hints"] = []
        return []


def test_personal_gateway_passes_through_when_signals_are_calm():
    decision = build_personal_agent_gateway_decision(raw_output="backend answer").to_dict()

    assert decision["gateway_mode"] == "pass_through"
    assert decision["delivered_output"] == "backend answer"
    assert decision["delivered_output_changed"] is False
    assert decision["transformation_label"] == "none"


def test_personal_gateway_shapes_fragile_output():
    decision = build_personal_agent_gateway_decision(
        raw_output="Push the release now.",
        copilot_pre_prompt="slow + warm",
        coordination_advisory_summary={"coordination_advisory_label": "fragile"},
        harmonic_state_summary={
            "harmonic_center": "stabilization",
            "harmonic_interval_label": "tritone",
            "resolution_direction": "deescalate_then_translate",
        },
        relational_policy_decision={"risk_state": "watch"},
    ).to_dict()

    assert decision["gateway_mode"] == "shape_response"
    assert decision["shaping_applied"] is True
    assert decision["delivered_output_changed"] is True
    assert decision["delivered_output"].startswith("Let's slow this down")


def test_personal_gateway_repairs_when_relational_risk_requires_repair():
    decision = build_personal_agent_gateway_decision(
        raw_output="We should decide immediately.",
        copilot_pre_prompt="slow + warm",
        relational_policy_decision={"risk_state": "repair"},
        harmonic_state_summary={
            "harmonic_center": "repair",
            "harmonic_interval_label": "seventh",
            "resolution_direction": "repair_then_resume",
        },
    ).to_dict()

    assert decision["gateway_mode"] == "repair_before_send"
    assert decision["repair_required"] is True
    assert decision["delivered_output"].startswith("Before acting on this")


def test_personal_gateway_holds_when_human_review_is_required():
    decision = build_personal_agent_gateway_decision(
        raw_output="Approve this path immediately.",
        relational_policy_decision={"risk_state": "escalate", "requires_human_review": True},
    ).to_dict()

    assert decision["gateway_mode"] == "hold_or_escalate"
    assert decision["hold_required"] is True
    assert decision["escalation_required"] is True
    assert "holding the raw agent output" in decision["delivered_output"]


def test_personal_gateway_metrics_average_lengths_are_bounded():
    metrics = PersonalAgentGatewayMetrics(
        calls_total=2,
        decisions_total=2,
        pass_through_total=1,
        shape_response_total=1,
        delivered_changed_total=1,
        _raw_excerpt_len_sum=20.0,
        _delivered_excerpt_len_sum=34.0,
    )
    payload = metrics.to_dict()

    assert payload["avg_raw_excerpt_length"] == 10.0
    assert payload["avg_delivered_excerpt_length"] == 17.0


def test_resonance_agent_build_output_exposes_gateway_and_preserves_raw_output():
    agent = ResonanceAgent(anchor=[], llm_fn=None)
    item = _base_item()
    item["_relational_field"] = {
        "tension_score": 0.82,
        "alignment_score": 0.21,
        "dominant_signal": "tension",
    }

    output = agent._build_output(
        item,
        final_output="Ship it now.",
        generation_time=0.01,
        cycle_id="cid-gateway",
    )

    assert output["raw_agent_output"] == "Ship it now."
    assert isinstance(output["personal_agent_gateway"], dict)
    assert isinstance(output["personal_agent_gateway_metrics"], dict)
    assert output["gateway_mode"] in {
        "pass_through",
        "shape_response",
        "repair_before_send",
        "hold_or_escalate",
    }
    assert output["gateway_delivered_output_changed"] is True
    assert output["final_output"] != output["raw_agent_output"]


def test_process_text_routes_raw_output_through_personal_gateway():
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=_GatewayBackend(),
        graph_runtime=_GatewayGraphRuntime(),
        orientation="test",
    )

    def _fake_gateway_context(item):
        item["_personal_agent_signal_present"] = True
        return {
            "coordination_advisory_summary": {"coordination_advisory_label": "fragile"},
            "harmonic_state_summary": {
                "harmonic_center": "stabilization",
                "harmonic_interval_label": "tritone",
                "resolution_direction": "deescalate_then_translate",
            },
            "relational_policy_decision": {"risk_state": "watch", "requires_human_review": False},
        }

    agent._prime_personal_agent_gateway_context = _fake_gateway_context  # type: ignore[method-assign]

    result = agent.process_text("Need a calm rollout recommendation.")

    assert result["raw_agent_output"] == "Ship it now."
    assert result["gateway_mode"] == "shape_response"
    assert result["gateway_delivered_output_changed"] is True
    assert result["final_output"].startswith("Let's slow this down")
