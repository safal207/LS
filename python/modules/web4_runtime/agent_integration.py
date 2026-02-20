from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..agent.loop import AgentLoop
from .observability import ObservabilityHub
from .protocol_router import Web4ProtocolRouter


@dataclass
class AgentLoopAdapter:
    agent_loop: AgentLoop
    router: Web4ProtocolRouter
    observability: Optional[ObservabilityHub] = None

    def handle_envelope(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        dispatch_result = self.router.dispatch(envelope)
        if self.observability:
            self.observability.record(
                "envelope_routed",
                {
                    "handled": dispatch_result.router_result.handled,
                    "trust_state": str(self.router._cip.trust_fsm.state),
                    "federation_allowed": dispatch_result.federation_decision.allowed,
                    "federation_reason": dispatch_result.federation_decision.reason,
                    "federation_policy": dispatch_result.federation_decision.policy,
                },
            )
        payload = envelope.get("payload", {})
        response = None
        if dispatch_result.router_result.handled and self.agent_loop.handler:
            response = self.agent_loop.handler(str(payload))
        if dispatch_result.router_result.handled and self.agent_loop.output_queue is not None:
            self.agent_loop.output_queue.put(response)
        return {
            "handled": dispatch_result.router_result.handled,
            "trust_state": str(self.router._cip.trust_fsm.state),
            "response": response,
            "federation_allowed": dispatch_result.federation_decision.allowed,
            "federation_reason": dispatch_result.federation_decision.reason,
            "federation_policy": dispatch_result.federation_decision.policy,
        }
