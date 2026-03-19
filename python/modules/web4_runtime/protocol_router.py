from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from protocols.router import ProtocolRouter, RouterResult
from protocols.trust import TrustTransition
from .cip_runtime import CipRuntime
from .federation_policy import (
    AllowAllFederationPolicy,
    FederationDecision,
    FederationPolicy,
)
from .hcp_runtime import HcpRuntime
from .lip_runtime import LipRuntime


@dataclass
class Web4DispatchResult:
    router_result: RouterResult
    trust_transition: Optional[TrustTransition]
    federation_decision: FederationDecision


class Web4ProtocolRouter:
    def __init__(
        self,
        *,
        cip: CipRuntime,
        hcp: HcpRuntime,
        lip: LipRuntime,
        federation_policy: FederationPolicy | None = None,
    ) -> None:
        self._cip = cip
        self._hcp = hcp
        self._lip = lip
        self._federation_policy = federation_policy or AllowAllFederationPolicy()
        self._router = ProtocolRouter(trust=self._cip.trust_fsm)
        self._router.register_trust_signals()
        self._register_runtime_handlers()

    def _register_runtime_handlers(self) -> None:
        self._router.on("HELLO", lambda env: self._cip.handle_envelope(env))
        self._router.on("HUMAN_STATE", lambda env: self._hcp.handle_envelope(env))
        self._router.on("SOURCE_UPDATE", lambda env: self._lip.defer_if_untrusted(env, self._cip.trust_fsm.state))

    def dispatch(self, envelope: Dict[str, Any]) -> Web4DispatchResult:
        federation_decision = self._federation_policy.evaluate(envelope)
        if not federation_decision.allowed:
            return Web4DispatchResult(
                RouterResult(None, False),
                None,
                federation_decision,
            )
        result = self._router.dispatch(envelope)
        transition = self._cip.handle_envelope(envelope)
        return Web4DispatchResult(result, transition, federation_decision)
