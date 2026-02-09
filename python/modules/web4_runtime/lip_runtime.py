from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List
from collections import deque

from ..protocols.lip import LipIdentity, LipSource, build_envelope, validate_envelope
from ..protocols.trust import TrustState


@dataclass
class LipRuntime:
    identity: LipIdentity
    _deferred: Deque[Dict[str, Any]] = field(default_factory=deque, init=False)

    def build_source_update(
        self,
        receiver: LipIdentity,
        payload: Dict[str, Any],
        source: LipSource,
    ) -> Dict[str, Any]:
        return build_envelope("SOURCE_UPDATE", self.identity, receiver, payload, source)

    def defer_if_untrusted(self, envelope: Dict[str, Any], trust_state: TrustState) -> bool:
        validate_envelope(envelope)
        if trust_state != TrustState.TRUSTED:
            self._deferred.append(envelope)
            return True
        return False

    def release_deferred(self, trust_state: TrustState) -> List[Dict[str, Any]]:
        if trust_state != TrustState.TRUSTED:
            return []
        released: List[Dict[str, Any]] = list(self._deferred)
        self._deferred.clear()
        return released
