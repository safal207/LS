from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from .cognitive_transaction import CognitiveTransaction


class CognitiveReducer:
    """Deterministic reducer for rebuilding cognitive state from transactions."""

    def apply(self, state: Dict[str, Any], tx: CognitiveTransaction) -> Dict[str, Any]:
        next_state = deepcopy(state)

        if tx.action == "approve_proposal":
            canonical = next_state.setdefault("canonical", {})
            pid = tx.payload.get("proposal_id")
            if pid is not None:
                canonical[str(pid)] = tx.payload.get("data")

        elif tx.action == "reject_proposal":
            rejected = next_state.setdefault("rejected", [])
            proposal_id = tx.payload.get("proposal_id")
            if proposal_id is not None:
                rejected.append(proposal_id)

        elif tx.action == "detect_contradiction":
            contradictions = next_state.setdefault("contradictions", [])
            contradictions.append(tx.payload)

        elif tx.action in {"belief_update", "canonical_update", "reflection_generated", "edit_proposal"}:
            op = tx.payload.get("op")
            key = tx.payload.get("key")
            if op == "set" and key is not None:
                next_state[key] = tx.payload.get("value")
            elif op == "append" and key is not None:
                next_state.setdefault(key, []).append(tx.payload.get("value"))
            elif op == "extend" and key is not None:
                next_state.setdefault(key, []).extend(tx.payload.get("value", []))

        timeline = next_state.setdefault("cognitive_timeline", [])
        timeline.append(
            {
                "tx_id": tx.tx_id,
                "timestamp": tx.timestamp,
                "actor": tx.actor,
                "action": tx.action,
            }
        )

        return next_state
