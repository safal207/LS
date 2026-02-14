from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CausalGraph:
    """Lightweight directed causal graph over state-action-state transitions."""

    max_transitions: int = 200
    transitions: deque[dict[str, Any]] = field(default_factory=deque)
    edge_stats: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.transitions.maxlen != self.max_transitions:
            self.transitions = deque(self.transitions, maxlen=self.max_transitions)

    @staticmethod
    def _state_value(state: dict[str, Any] | None, key: str, default: int = 0) -> int:
        if not isinstance(state, dict):
            return default
        return int(state.get(key, default))

    def _outcome_delta(self, state_before: dict[str, Any], state_after: dict[str, Any]) -> float:
        goal = self._state_value(state_before, "goal_position", self._state_value(state_after, "goal_position", 0))
        before_pos = self._state_value(state_before, "agent_position", 0)
        after_pos = self._state_value(state_after, "agent_position", before_pos)
        return float(abs(goal - before_pos) - abs(goal - after_pos))

    def _edge_key(self, state_before: dict[str, Any], action: str, state_after: dict[str, Any]) -> str:
        before_pos = self._state_value(state_before, "agent_position", 0)
        after_pos = self._state_value(state_after, "agent_position", before_pos)
        return f"s:{before_pos}|a:{action}|s:{after_pos}"

    def record_transition(self, state_before: dict[str, Any], action: str, state_after: dict[str, Any]) -> None:
        delta = self._outcome_delta(state_before, state_after)
        transition = {
            "state_before": dict(state_before),
            "action": action,
            "state_after": dict(state_after),
            "delta": delta,
        }
        self.transitions.append(transition)

        key = self._edge_key(state_before, action, state_after)
        stats = self.edge_stats.setdefault(key, {"count": 0, "delta_sum": 0.0, "action": action, "from": {}, "to": {}})
        stats["count"] += 1
        stats["delta_sum"] += delta
        stats["from"] = {"agent_position": self._state_value(state_before, "agent_position", 0)}
        stats["to"] = {"agent_position": self._state_value(state_after, "agent_position", 0)}
        stats["probability"] = stats["count"] / max(1, len(self.transitions))
        stats["avg_delta"] = stats["delta_sum"] / max(1, stats["count"])

    def estimate_causal_effect(self, action: str) -> float:
        deltas = [float(item["delta"]) for item in self.transitions if item.get("action") == action]
        if not deltas:
            return 0.0
        return sum(deltas) / len(deltas)

    def predict_outcome(self, action: str) -> dict[str, float]:
        effect = self.estimate_causal_effect(action)
        action_transitions = [item for item in self.transitions if item.get("action") == action]
        if not action_transitions:
            return {"expected_delta": 0.0, "drift_probability": 0.0, "success_probability": 0.0}
        drift_count = sum(1 for item in action_transitions if float(item.get("delta", 0.0)) < 0)
        success_count = sum(1 for item in action_transitions if float(item.get("delta", 0.0)) > 0)
        total = max(1, len(action_transitions))
        return {
            "expected_delta": effect,
            "drift_probability": drift_count / total,
            "success_probability": success_count / total,
        }

    def recent_transitions(self, limit: int = 10) -> list[dict[str, Any]]:
        return list(self.transitions)[-max(1, limit) :]

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_transitions": self.max_transitions,
            "transition_count": len(self.transitions),
            "edges": dict(self.edge_stats),
            "recent": self.recent_transitions(limit=15),
        }

    # Compatibility aliases for requested naming.
    def recordtransition(self, statebefore: dict[str, Any], action: str, state_after: dict[str, Any]) -> None:
        self.record_transition(statebefore, action, state_after)

    def estimatecausaleffect(self, action: str) -> float:
        return self.estimate_causal_effect(action)

