# -*- coding: utf-8 -*-
"""External agent gateway.

Normalizes raw output from an external agent into the LS runtime contract and
routes it through the same personal-layer delivery path used by ResonanceAgent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from .resonance_agent import ResonanceAgent


def _as_text(value: Any) -> str:
    return str(value or "")


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _participant_ids(participants: list[Any]) -> list[str]:
    output: list[str] = []
    for raw in participants:
        if isinstance(raw, dict):
            participant_id = str(raw.get("participant_id") or raw.get("id") or "").strip()
            if participant_id:
                output.append(participant_id)
        else:
            text = str(raw or "").strip()
            if text:
                output.append(text)
    return output


@dataclass
class ExternalAgentGatewayRequest:
    prompt: str
    raw_output: str
    agent_id: str = "external-agent"
    agent_type: str = "external"
    orientation: str = "external-agent-gateway"
    pre_prompt: str = "slow + warm"
    participants: list[Any] = field(default_factory=list)
    interaction_scope: str = "human-agent"
    metadata: dict[str, Any] = field(default_factory=dict)
    thread_context: Any = None
    alignment_report: dict[str, Any] | None = None
    relational_field: dict[str, Any] | None = None
    intent: dict[str, Any] | None = None
    why: dict[str, Any] | None = None
    cycle_id: str = ""
    generation_time: float = 0.0
    route_key: str = "external>gateway"

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "ExternalAgentGatewayRequest":
        data = dict(payload or {})
        return cls(
            prompt=_as_text(data.get("prompt")),
            raw_output=_as_text(data.get("raw_output")),
            agent_id=_as_text(data.get("agent_id")) or "external-agent",
            agent_type=_as_text(data.get("agent_type")) or "external",
            orientation=_as_text(data.get("orientation")) or "external-agent-gateway",
            pre_prompt=_as_text(data.get("pre_prompt")) or "slow + warm",
            participants=_as_list(data.get("participants")),
            interaction_scope=_as_text(data.get("interaction_scope")) or "human-agent",
            metadata=_as_dict(data.get("metadata")),
            thread_context=data.get("thread_context"),
            alignment_report=_as_dict(data.get("alignment_report")) or None,
            relational_field=_as_dict(data.get("relational_field")) or None,
            intent=_as_dict(data.get("intent")) or None,
            why=_as_dict(data.get("why")) or None,
            cycle_id=_as_text(data.get("cycle_id")),
            generation_time=float(data.get("generation_time") or 0.0),
            route_key=_as_text(data.get("route_key")) or "external>gateway",
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "orientation": self.orientation,
            "interaction_scope": self.interaction_scope,
            "participants_count": len(self.participants),
            "metadata": dict(self.metadata),
            "cycle_id": self.cycle_id,
            "route_key": self.route_key,
        }


class ExternalAgentGateway:
    """Route external agent output through the LS personal layer."""

    def __init__(
        self,
        agent: "ResonanceAgent",
        *,
        default_orientation: str = "external-agent-gateway",
    ) -> None:
        self._agent = agent
        self._default_orientation = str(default_orientation or "external-agent-gateway")

    def _coerce_request(
        self,
        request: ExternalAgentGatewayRequest | dict[str, Any],
    ) -> ExternalAgentGatewayRequest:
        if isinstance(request, ExternalAgentGatewayRequest):
            return request
        return ExternalAgentGatewayRequest.from_dict(request)

    def normalize_request(
        self,
        request: ExternalAgentGatewayRequest | dict[str, Any],
    ) -> tuple[ExternalAgentGatewayRequest, dict[str, Any]]:
        req = self._coerce_request(request)
        cycle_id = req.cycle_id or str(uuid4())
        route_key = req.route_key or "external>gateway"
        item = {
            "text": str(req.prompt or ""),
            "thread_context": req.thread_context,
            "participants": list(req.participants or []),
            "interaction_scope": str(req.interaction_scope or "human-agent"),
            "_interaction_scope": str(req.interaction_scope or "human-agent"),
            "_copilot_output": {"pre_prompt": str(req.pre_prompt or "slow + warm")},
            "_operator_response_output": {"pre_prompt": str(req.pre_prompt or "slow + warm")},
            "_intent": dict(req.intent or {}),
            "_why": dict(req.why or {}),
            "_why_strategy": {},
            "_llm_backend": {
                "provider": str(req.agent_type or "external"),
                "model": str(req.agent_id or "external-agent"),
                "latency_ms": round(float(req.generation_time or 0.0) * 1000.0, 2),
                "error": None,
                "was_fallback_used": False,
                "fallback_from": None,
                "fallback_to": None,
            },
            "_path_selection": {
                "route_key": route_key,
                "reason": "external-agent-gateway-v1",
            },
            "_graph_runtime": {
                "mode": "external_gateway",
                "reason": "external-agent-gateway-v1",
            },
            "_trail_route": {},
            "_coalition": {},
            "_derived_module": {},
            "_care_cycle": {},
            "_network_plan": {},
            "_adequacy_report": {},
            "_observer_report": {},
            "_alignment_outcome": {},
            "_resonance_score": 0.5,
            "_cycle_id": cycle_id,
            "_external_agent_request": {
                "agent_id": str(req.agent_id or "external-agent"),
                "agent_type": str(req.agent_type or "external"),
                "orientation": str(req.orientation or self._default_orientation),
                "interaction_scope": str(req.interaction_scope or "human-agent"),
                "metadata": dict(req.metadata or {}),
                "route_key": route_key,
            },
        }
        if req.alignment_report:
            item["_alignment_report"] = dict(req.alignment_report)
        if req.relational_field:
            item["_relational_field"] = dict(req.relational_field)
            item["_relational_field_source"] = "external"
        return req, item

    def _derive_missing_signals(self, item: dict[str, Any]) -> None:
        participants = list(item.get("participants") or [])
        participant_ids = _participant_ids(participants)
        interaction_scope = str(
            item.get("interaction_scope")
            or item.get("_interaction_scope")
            or "human-agent"
        )
        context = {
            "intent": item.get("_intent") or item.get("intent"),
            "why": item.get("_why") or item.get("why"),
            "interaction_scope": interaction_scope,
            "cycle_id": item.get("_cycle_id"),
            "source": "external_agent_gateway_v1",
        }

        if not isinstance(item.get("_relational_field"), dict) and getattr(self._agent, "_relational_analyzer", None):
            try:
                snapshot = self._agent._relational_analyzer.analyze(
                    text=str(item.get("text") or ""),
                    participants=participant_ids,
                    interaction_scope=interaction_scope,
                    context=context,
                )
                item["_relational_field"] = snapshot.to_dict()
                item["_relational_field_source"] = "derived"
            except Exception:
                pass

        if not isinstance(item.get("_alignment_report"), dict) and getattr(self._agent, "_alignment_analyzer", None):
            try:
                report = self._agent._alignment_analyzer.analyze(
                    participants=participants,
                    context=context,
                )
                item["_alignment_report"] = report.to_dict()
            except Exception:
                pass

    def route_external_output(
        self,
        request: ExternalAgentGatewayRequest | dict[str, Any],
    ) -> dict[str, Any]:
        req, item = self.normalize_request(request)
        self._derive_missing_signals(item)

        raw_output = str(req.raw_output or "")
        cycle_id = str(item.get("_cycle_id") or req.cycle_id or str(uuid4()))
        generation_time = max(0.0, float(req.generation_time or 0.0))

        gateway_context = self._agent._prime_personal_agent_gateway_context(item)
        gateway_decision = self._agent.get_personal_agent_gateway_decision(
            item,
            raw_output=raw_output,
            coordination_advisory_summary=gateway_context.get("coordination_advisory_summary"),
            harmonic_state_summary=gateway_context.get("harmonic_state_summary"),
            relational_policy_decision=gateway_context.get("relational_policy_decision"),
        )

        item["_raw_agent_output"] = raw_output
        item["_personal_agent_gateway"] = gateway_decision
        final_output = str(gateway_decision.get("delivered_output") or raw_output)

        base_score = float(item.get("_resonance_score", 0.5) or 0.5)
        response_score = self._agent._rate_response(final_output, item)
        goal_alignment_score = self._agent._goal_alignment_score(final_output, item)
        item["_goal_alignment_score"] = goal_alignment_score
        item["_resonance_score"] = round(
            (base_score * 0.55 + response_score * 0.25 + goal_alignment_score * 0.20),
            3,
        )
        self._agent._record_alignment_outcome(
            item,
            response_text=final_output,
            response_score=response_score,
            goal_alignment_score=goal_alignment_score,
        )
        self._agent._maybe_store_alignment_memory_unit(item, final_output)

        result = self._agent._build_output(
            item,
            final_output=final_output,
            generation_time=generation_time,
            cycle_id=cycle_id,
        )
        result["external_agent_gateway"] = {
            "entrypoint": "external_agent_gateway_v1",
            "agent_id": str(req.agent_id or "external-agent"),
            "agent_type": str(req.agent_type or "external"),
            "interaction_scope": str(req.interaction_scope or "human-agent"),
            "orientation": str(req.orientation or self._default_orientation),
            "metadata": dict(req.metadata or {}),
            "participants_count": len(list(req.participants or [])),
        }
        result["external_agent_request"] = req.to_public_dict()
        return result
