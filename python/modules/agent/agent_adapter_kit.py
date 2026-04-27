# -*- coding: utf-8 -*-
"""Small adapter kit for routing external agents through LS."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from time import perf_counter
from typing import Any, Callable, TYPE_CHECKING

from .external_agent_gateway import ExternalAgentGateway, ExternalAgentGatewayRequest

if TYPE_CHECKING:
    from .resonance_agent import ResonanceAgent


RawOutputProducer = Callable[["AgentAdapterRequest"], Any]


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


def _extract_raw_output(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("raw_output", "output", "text", "content", "answer", "final_output"):
            if key in value:
                return str(value.get(key) or "")
    return str(value or "")


@dataclass
class AgentAdapterRequest:
    """Public request contract for agents that want LS as a delivery layer."""

    prompt: str
    agent_id: str = "external-agent"
    agent_type: str = "external"
    orientation: str = "agent-adapter-kit"
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
    route_key: str = "external>adapter-kit"

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "AgentAdapterRequest":
        data = dict(payload or {})
        return cls(
            prompt=str(data.get("prompt") or ""),
            agent_id=str(data.get("agent_id") or "external-agent"),
            agent_type=str(data.get("agent_type") or "external"),
            orientation=str(data.get("orientation") or "agent-adapter-kit"),
            pre_prompt=str(data.get("pre_prompt") or "slow + warm"),
            participants=_as_list(data.get("participants")),
            interaction_scope=str(data.get("interaction_scope") or "human-agent"),
            metadata=_as_dict(data.get("metadata")),
            thread_context=data.get("thread_context"),
            alignment_report=_as_dict(data.get("alignment_report")) or None,
            relational_field=_as_dict(data.get("relational_field")) or None,
            intent=_as_dict(data.get("intent")) or None,
            why=_as_dict(data.get("why")) or None,
            cycle_id=str(data.get("cycle_id") or ""),
            route_key=str(data.get("route_key") or "external>adapter-kit"),
        )

    def to_gateway_request(
        self,
        raw_output: str,
        *,
        generation_time: float = 0.0,
    ) -> ExternalAgentGatewayRequest:
        return ExternalAgentGatewayRequest(
            prompt=self.prompt,
            raw_output=raw_output,
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            orientation=self.orientation,
            pre_prompt=self.pre_prompt,
            participants=list(self.participants),
            interaction_scope=self.interaction_scope,
            metadata=dict(self.metadata),
            thread_context=self.thread_context,
            alignment_report=dict(self.alignment_report or {}) or None,
            relational_field=dict(self.relational_field or {}) or None,
            intent=dict(self.intent or {}) or None,
            why=dict(self.why or {}) or None,
            cycle_id=self.cycle_id,
            generation_time=generation_time,
            route_key=self.route_key,
        )


@dataclass
class AgentAdapterResponse:
    request: AgentAdapterRequest
    raw_output: str
    final_output: str
    gateway_mode: str
    gateway_reason: str
    changed: bool
    cycle_id: str
    result: dict[str, Any] = field(repr=False)

    @property
    def artifacts(self) -> dict[str, str | None]:
        return {
            "ledger": self.result.get("council_contribution_ledger_artifact"),
            "quality": self.result.get("council_quality_artifact"),
        }

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "agent_id": self.request.agent_id,
            "agent_type": self.request.agent_type,
            "prompt": self.request.prompt,
            "raw_agent_output": self.raw_output,
            "final_output": self.final_output,
            "gateway_mode": self.gateway_mode,
            "gateway_reason": self.gateway_reason,
            "changed": self.changed,
            "artifacts": self.artifacts,
            "external_agent_gateway": self.result.get("external_agent_gateway"),
        }


class AgentAdapterKit:
    """Stable facade for connecting agents to the LS personal layer."""

    def __init__(
        self,
        gateway: ExternalAgentGateway,
        *,
        default_agent_id: str = "external-agent",
        default_agent_type: str = "external",
        default_orientation: str = "agent-adapter-kit",
    ) -> None:
        self._gateway = gateway
        self._default_agent_id = str(default_agent_id or "external-agent")
        self._default_agent_type = str(default_agent_type or "external")
        self._default_orientation = str(default_orientation or "agent-adapter-kit")

    @classmethod
    def from_agent(
        cls,
        agent: "ResonanceAgent",
        *,
        default_agent_id: str = "external-agent",
        default_agent_type: str = "external",
        default_orientation: str = "agent-adapter-kit",
    ) -> "AgentAdapterKit":
        gateway = ExternalAgentGateway(agent, default_orientation=default_orientation)
        return cls(
            gateway,
            default_agent_id=default_agent_id,
            default_agent_type=default_agent_type,
            default_orientation=default_orientation,
        )

    def _coerce_request(self, request: AgentAdapterRequest | dict[str, Any] | str) -> AgentAdapterRequest:
        if isinstance(request, AgentAdapterRequest):
            req = request
        elif isinstance(request, dict):
            req = AgentAdapterRequest.from_dict(request)
        else:
            req = AgentAdapterRequest(prompt=str(request or ""))
        agent_id = req.agent_id
        if not agent_id or agent_id == "external-agent":
            agent_id = self._default_agent_id
        agent_type = req.agent_type
        if not agent_type or agent_type == "external":
            agent_type = self._default_agent_type
        orientation = req.orientation
        if not orientation or orientation == "agent-adapter-kit":
            orientation = self._default_orientation
        return replace(
            req,
            agent_id=agent_id,
            agent_type=agent_type,
            orientation=orientation,
        )

    def route_raw_output(
        self,
        request: AgentAdapterRequest | dict[str, Any] | str,
        raw_output: Any,
        *,
        generation_time: float = 0.0,
    ) -> AgentAdapterResponse:
        req = self._coerce_request(request)
        text = _extract_raw_output(raw_output)
        result = self._gateway.route_external_output(
            req.to_gateway_request(text, generation_time=generation_time)
        )
        return self._response_from_result(req, text, result)

    def run(
        self,
        request: AgentAdapterRequest | dict[str, Any] | str,
        raw_output_producer: RawOutputProducer,
    ) -> AgentAdapterResponse:
        req = self._coerce_request(request)
        started = perf_counter()
        produced = raw_output_producer(req)
        generation_time = max(0.0, perf_counter() - started)
        return self.route_raw_output(req, produced, generation_time=generation_time)

    def _response_from_result(
        self,
        request: AgentAdapterRequest,
        raw_output: str,
        result: dict[str, Any],
    ) -> AgentAdapterResponse:
        return AgentAdapterResponse(
            request=request,
            raw_output=str(result.get("raw_agent_output") or raw_output or ""),
            final_output=str(result.get("final_output") or ""),
            gateway_mode=str(result.get("gateway_mode") or "pass_through"),
            gateway_reason=str(result.get("gateway_reason") or ""),
            changed=bool(result.get("gateway_delivered_output_changed", False)),
            cycle_id=str(result.get("cycle_id") or request.cycle_id or ""),
            result=result,
        )


class CodexSelfUseAdapter:
    """Tiny self-use adapter: draft first, then let LS decide final delivery."""

    def __init__(
        self,
        kit: AgentAdapterKit,
        draft_fn: RawOutputProducer,
        *,
        agent_id: str = "codex-self-use",
        agent_type: str = "codex",
    ) -> None:
        self._kit = kit
        self._draft_fn = draft_fn
        self._agent_id = str(agent_id or "codex-self-use")
        self._agent_type = str(agent_type or "codex")

    def answer(
        self,
        prompt: str,
        *,
        participants: list[Any] | None = None,
        metadata: dict[str, Any] | None = None,
        orientation: str = "codex-self-use-adapter",
        interaction_scope: str = "human-agent",
    ) -> AgentAdapterResponse:
        request = AgentAdapterRequest(
            prompt=prompt,
            agent_id=self._agent_id,
            agent_type=self._agent_type,
            orientation=orientation,
            participants=list(participants or []),
            interaction_scope=interaction_scope,
            metadata={
                "adapter_name": "codex-self-use",
                **dict(metadata or {}),
            },
        )
        return self._kit.run(request, self._draft_fn)

    @staticmethod
    def compare(response: AgentAdapterResponse) -> dict[str, Any]:
        return {
            "raw_agent_output": response.raw_output,
            "final_output": response.final_output,
            "changed": response.changed,
            "gateway_mode": response.gateway_mode,
            "gateway_reason": response.gateway_reason,
        }
