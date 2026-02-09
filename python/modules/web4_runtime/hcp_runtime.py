from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from ..protocols.hcp import HcpHumanState, HcpIdentity, build_envelope, validate_envelope


@dataclass(frozen=True)
class HcpPolicy:
    max_pressure: int = 7
    required_consent: str = "granted"


@dataclass
class HcpRuntime:
    identity: HcpIdentity
    policy: HcpPolicy = HcpPolicy()

    def build_state_update(
        self,
        receiver: HcpIdentity,
        payload: Dict[str, Any],
        human_state: HcpHumanState,
    ) -> Dict[str, Any]:
        return build_envelope("HUMAN_STATE", self.identity, receiver, payload, human_state)

    def allow_interaction(self, human_state: HcpHumanState) -> bool:
        consent_ok = human_state.consent == self.policy.required_consent
        pressure_ok = human_state.pressure <= self.policy.max_pressure
        return consent_ok and pressure_ok

    def handle_envelope(self, envelope: Dict[str, Any]) -> bool:
        validate_envelope(envelope)
        state = envelope["state"]["human"]
        human_state = HcpHumanState(**state)
        return self.allow_interaction(human_state)
