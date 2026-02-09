from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from python.modules.protocols.router import ProtocolRouter, RouterResult
from python.modules.protocols.trust import TrustTransition
from .cip_runtime import CipRuntime
from .hcp_runtime import HcpRuntime
from .lip_runtime import LipRuntime


@dataclass
class Web4DispatchResult:
    router_result: RouterResult
    trust_transition: Optional[TrustTransition]


class Web4ProtocolRouter:
    def __init__(
        self,
        *,
        cip: CipRuntime,
        hcp: HcpRuntime,
        lip: LipRuntime,
    ) -> None:
        self._cip = cip
        self._hcp = hcp
        self._lip = lip
        self._router = ProtocolRouter(trust=self._cip.trust_fsm)
        self._router.register_trust_signals()
        self._register_runtime_handlers()

    def _register_runtime_handlers(self) -> None:
        self._router.on("HELLO", lambda env: self._cip.handle_envelope(env))
        self._router.on("HUMAN_STATE", lambda env: self._hcp.handle_envelope(env))
        self._router.on("SOURCE_UPDATE", lambda env: self._lip.defer_if_untrusted(env, self._cip.trust_fsm.state))

    def dispatch(self, envelope: Dict[str, Any]) -> Web4DispatchResult:
        result = self._router.dispatch(envelope)
        transition = self._cip.handle_envelope(envelope)
        return Web4DispatchResult(result, transition)
