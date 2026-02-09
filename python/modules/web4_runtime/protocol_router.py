from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..protocols.router import ProtocolRouter, RouterResult
from ..protocols.trust import TrustTransition
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
        def _handle_hello(env: Dict[str, Any]) -> None:
            self._cip.handle_envelope(env)

        def _handle_human(env: Dict[str, Any]) -> None:
            self._hcp.handle_envelope(env)

        def _handle_source(env: Dict[str, Any]) -> None:
            self._lip.defer_if_untrusted(env, self._cip.trust_fsm.state)

        self._router.on("HELLO", _handle_hello)
        self._router.on("HUMAN_STATE", _handle_human)
        self._router.on("SOURCE_UPDATE", _handle_source)

    def dispatch(self, envelope: Dict[str, Any]) -> Web4DispatchResult:
        result = self._router.dispatch(envelope)
        transition = self._cip.handle_envelope(envelope)
        return Web4DispatchResult(result, transition)
