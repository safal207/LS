from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from .causal import CausalGraph


@dataclass
class SharedCausalGraph:
    """Aggregates causal transitions from many agents into a shared layer."""

    max_transitions: int = 500
    transitions: deque[dict[str, Any]] = field(default_factory=deque)
    agent_transitions: dict[str, deque[dict[str, Any]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.transitions.maxlen != self.max_transitions:
            self.transitions = deque(self.transitions, maxlen=self.max_transitions)

    def merge(self, agent_graph: CausalGraph, *, agent_id: str = "unknown") -> None:
        bucket = self.agent_transitions.setdefault(agent_id, deque(maxlen=self.max_transitions))
        for item in list(agent_graph.transitions):
            transition = {
                "agent_id": agent_id,
                "action": item.get("action", "idle"),
                "delta": float(item.get("delta", 0.0)),
                "state_before": dict(item.get("state_before", {})),
                "state_after": dict(item.get("state_after", {})),
            }
            self.transitions.append(transition)
            bucket.append(transition)

    def estimate_collective_effect(self, action: str) -> float:
        deltas = [float(item["delta"]) for item in self.transitions if item.get("action") == action]
        if not deltas:
            return 0.0
        return sum(deltas) / len(deltas)

    def predict_collective_outcome(self, action: str) -> dict[str, Any]:
        action_transitions = [item for item in self.transitions if item.get("action") == action]
        if not action_transitions:
            return {
                "collective_effect": 0.0,
                "collective_drift": 0.0,
                "agent_contributions": {},
            }

        collective_effect = self.estimate_collective_effect(action)
        drift_count = sum(1 for item in action_transitions if float(item.get("delta", 0.0)) < 0)
        collective_drift = drift_count / max(1, len(action_transitions))

        contributions: dict[str, float] = {}
        for item in action_transitions:
            agent_id = str(item.get("agent_id", "unknown"))
            contributions.setdefault(agent_id, 0.0)
            contributions[agent_id] += float(item.get("delta", 0.0))

        return {
            "collective_effect": collective_effect,
            "collective_drift": collective_drift,
            "agent_contributions": contributions,
        }

    def snapshot(self) -> dict[str, Any]:
        action_set = {str(item.get("action", "idle")) for item in self.transitions}
        by_action = {action: self.predict_collective_outcome(action) for action in sorted(action_set)}
        return {
            "max_transitions": self.max_transitions,
            "transition_count": len(self.transitions),
            "by_action": by_action,
        }

    # Compatibility aliases for requested naming.
    def estimatecollectiveeffect(self, action: str) -> float:
        return self.estimate_collective_effect(action)

    def predictcollectiveoutcome(self, action: str) -> dict[str, Any]:
        return self.predict_collective_outcome(action)
